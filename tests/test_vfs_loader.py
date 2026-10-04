"""Tests for loading the VFS from XML images."""

import stat
import hashlib
from pathlib import Path

import pytest

from repl.core.errors import VFSLoadError
from repl.core.vfs import VDir, VFile
from repl.core.vfs_loader import describe, load_vfs

_VFS_DIR = Path(__file__).resolve().parent.parent / "vfs"
_BROKEN_DIR = _VFS_DIR / "broken"


def perms(mode: int) -> str:
    """Render permission bits like ``ls -l`` does: ``rwxr-xr-x``."""
    return stat.filemode(mode)[1:]


def test_load_minimal() -> None:
    vfs = load_vfs(_VFS_DIR / "minimal.xml")
    assert vfs.name == "minimal"
    assert vfs.loaded is True
    assert vfs.root.children == {}
    assert (
        vfs.sha256
        == hashlib.sha256((_VFS_DIR / "minimal.xml").read_bytes()).hexdigest()
    )


def test_load_multi_structure() -> None:
    vfs = load_vfs(_VFS_DIR / "multi.xml")
    assert vfs.name == "multi"
    assert set(vfs.root.children) == {"readme.txt", ".hidden", "logo.bin"}

    readme = vfs.root.children["readme.txt"]
    assert isinstance(readme, VFile)
    assert perms(readme.mode) == "rw-r--r--"  # default file mode
    assert readme.owner == "root"  # default owner
    assert (
        readme.data == b"Welcome to the multi VFS.\n"
        b"It has a few plain files in the root directory.\n"
    )

    logo = vfs.root.children["logo.bin"]
    assert isinstance(logo, VFile)
    import base64

    assert logo.data == base64.b64decode("iVBORw0KGgo=")


def test_load_deep_structure_and_defaults() -> None:
    vfs = load_vfs(_VFS_DIR / "deep.xml")
    assert vfs.name == "deep"

    home = vfs.root.children["home"]
    assert isinstance(home, VDir)
    assert perms(home.mode) == "rwxr-xr-x"  # default dir mode
    assert (
        home.owner == "root"
    )  # default owner (not inherited from root <vfs owner="root">)

    user = home.children["user"]
    assert isinstance(user, VDir)
    assert user.owner == "user"
    assert user.group == "user"


def test_load_deep_files_and_modes() -> None:
    vfs = load_vfs(_VFS_DIR / "deep.xml")
    user = vfs.root.children["home"].children["user"]
    notes = user.children["docs"].children["notes.txt"]
    assert isinstance(notes, VFile)
    assert perms(notes.mode) == "rw-r--r--"
    assert notes.owner == "user"
    assert notes.data.endswith(b"\n")

    tool = vfs.root.children["usr"].children["bin"].children["tool"]
    assert isinstance(tool, VFile)
    assert perms(tool.mode) == "rwxr-xr-x"

    tmp = vfs.root.children["tmp"]
    assert isinstance(tmp, VDir)
    assert perms(tmp.mode) == "rwxrwxrwx"
    assert tmp.children == {}


def test_load_name_defaults_to_file_stem(tmp_path: Path) -> None:
    path = tmp_path / "my_fs.xml"
    path.write_text("<vfs/>")
    vfs = load_vfs(path)
    assert vfs.name == "my_fs"


def test_sha256_matches_raw_bytes() -> None:
    path = _VFS_DIR / "deep.xml"
    vfs = load_vfs(path)
    assert vfs.sha256 == hashlib.sha256(path.read_bytes()).hexdigest()


def test_describe_counts_dirs_and_files() -> None:
    vfs = load_vfs(_VFS_DIR / "deep.xml")
    assert describe(vfs) == "[vfs] loaded 'deep' (11 dirs, 7 files)"


def test_describe_empty_vfs() -> None:
    vfs = load_vfs(_VFS_DIR / "minimal.xml")
    assert describe(vfs) == "[vfs] loaded 'minimal' (0 dirs, 0 files)"


def test_load_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing.xml"
    with pytest.raises(VFSLoadError, match="No such file or directory"):
        load_vfs(missing)


def test_load_directory_instead_of_file(tmp_path: Path) -> None:
    with pytest.raises(VFSLoadError, match="Is a directory"):
        load_vfs(tmp_path)


def test_load_not_xml() -> None:
    with pytest.raises(VFSLoadError, match="invalid XML"):
        load_vfs(_BROKEN_DIR / "not_xml.xml")


def test_load_wrong_root_element() -> None:
    with pytest.raises(
        VFSLoadError, match=r"invalid format: root element must be <vfs>"
    ):
        load_vfs(_BROKEN_DIR / "wrong_root.xml")


def test_load_bad_base64() -> None:
    with pytest.raises(VFSLoadError, match="invalid format: invalid base64"):
        load_vfs(_BROKEN_DIR / "bad_base64.xml")


def test_load_duplicate_name() -> None:
    with pytest.raises(VFSLoadError, match=r'duplicate name "a" in home'):
        load_vfs(_BROKEN_DIR / "duplicate.xml")


def test_load_bad_mode() -> None:
    with pytest.raises(VFSLoadError, match=r"invalid mode '999'"):
        load_vfs(_BROKEN_DIR / "bad_mode.xml")


def test_load_unknown_element(tmp_path: Path) -> None:
    path = tmp_path / "unknown_elem.xml"
    path.write_text("<vfs><symlink name='x'/></vfs>")
    with pytest.raises(VFSLoadError, match="unknown element <symlink>"):
        load_vfs(path)


def test_load_unknown_attribute(tmp_path: Path) -> None:
    path = tmp_path / "unknown_attr.xml"
    path.write_text('<vfs><dir name="a" color="red"/></vfs>')
    with pytest.raises(VFSLoadError, match="unknown attribute 'color'"):
        load_vfs(path)


def test_load_file_with_child_elements(tmp_path: Path) -> None:
    path = tmp_path / "file_with_children.xml"
    path.write_text('<vfs><file name="a"><dir name="b"/></file></vfs>')
    with pytest.raises(VFSLoadError, match="must not have child elements"):
        load_vfs(path)


def test_load_missing_name(tmp_path: Path) -> None:
    path = tmp_path / "missing_name.xml"
    path.write_text("<vfs><dir/></vfs>")
    with pytest.raises(VFSLoadError, match="missing name"):
        load_vfs(path)


def test_load_name_with_slash(tmp_path: Path) -> None:
    path = tmp_path / "slash_name.xml"
    path.write_text('<vfs><dir name="a/b"/></vfs>')
    with pytest.raises(VFSLoadError, match=r"invalid name 'a/b'"):
        load_vfs(path)


def test_load_name_dot_dot(tmp_path: Path) -> None:
    path = tmp_path / "dotdot_name.xml"
    path.write_text('<vfs><dir name=".."/></vfs>')
    with pytest.raises(VFSLoadError, match=r"invalid name '\.\.'"):
        load_vfs(path)
