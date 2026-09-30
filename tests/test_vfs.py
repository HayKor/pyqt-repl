from __future__ import annotations

import pytest

from repl.core.errors import VFSPathError
from repl.core.vfs import VDir, VFile, VFS


def make_vfs() -> VFS:
    notes = VFile(name="notes.txt", mode=0o644, owner="user", group="user", data=b"hi\n")
    docs = VDir(name="docs", mode=0o755, owner="user", group="user", children={"notes.txt": notes})
    user = VDir(name="user", mode=0o755, owner="user", group="user", children={"docs": docs})
    home = VDir(name="home", mode=0o755, owner="root", group="root", children={"user": user})
    root = VDir(name="", mode=0o755, owner="root", group="root", children={"home": home})
    return VFS(name="test", sha256="deadbeef", root=root)


def test_empty_vfs() -> None:
    vfs = VFS.empty()
    assert vfs.loaded is False
    assert vfs.name == "<none>"
    assert vfs.resolve("/") is vfs.root
    assert vfs.root.children == {}


def test_loaded_flag_set_once_source_present(tmp_path) -> None:
    vfs = make_vfs()
    assert vfs.loaded is False
    vfs.source = tmp_path / "fs.xml"
    assert vfs.loaded is True


class TestNormalize:
    def test_root(self) -> None:
        vfs = make_vfs()
        assert vfs.normalize("/") == "/"

    def test_dot_and_double_dot(self) -> None:
        vfs = make_vfs()
        assert vfs.normalize("/home/./user") == "/home/user"
        assert vfs.normalize("/home/user/..") == "/home"

    def test_double_dot_at_root_stays_at_root(self) -> None:
        vfs = make_vfs()
        assert vfs.normalize("/..") == "/"
        assert vfs.normalize("/../../..") == "/"

    def test_collapses_repeated_slashes(self) -> None:
        vfs = make_vfs()
        assert vfs.normalize("//home//user//") == "/home/user"

    def test_relative_to_cwd(self) -> None:
        vfs = make_vfs()
        assert vfs.normalize("docs", cwd="/home/user") == "/home/user/docs"
        assert vfs.normalize("../user", cwd="/home/user") == "/home/user"
        assert vfs.normalize(".", cwd="/home/user") == "/home/user"

    def test_absolute_path_ignores_cwd(self) -> None:
        vfs = make_vfs()
        assert vfs.normalize("/home", cwd="/home/user/docs") == "/home"


class TestResolve:
    def test_resolve_root(self) -> None:
        vfs = make_vfs()
        assert vfs.resolve("/") is vfs.root

    def test_resolve_file(self) -> None:
        vfs = make_vfs()
        node = vfs.resolve("/home/user/docs/notes.txt")
        assert isinstance(node, VFile)
        assert node.name == "notes.txt"

    def test_resolve_relative_to_cwd(self) -> None:
        vfs = make_vfs()
        node = vfs.resolve("docs/notes.txt", cwd="/home/user")
        assert isinstance(node, VFile)

    def test_not_found(self) -> None:
        vfs = make_vfs()
        with pytest.raises(VFSPathError) as exc_info:
            vfs.resolve("/home/nope")
        assert str(exc_info.value) == "/home/nope: No such file or directory"

    def test_intermediate_component_is_a_file(self) -> None:
        vfs = make_vfs()
        with pytest.raises(VFSPathError) as exc_info:
            vfs.resolve("/home/user/docs/notes.txt/more")
        assert str(exc_info.value) == "/home/user/docs/notes.txt/more: Not a directory"

    def test_trailing_slash_on_a_file(self) -> None:
        vfs = make_vfs()
        with pytest.raises(VFSPathError) as exc_info:
            vfs.resolve("/home/user/docs/notes.txt/")
        assert str(exc_info.value) == "/home/user/docs/notes.txt/: Not a directory"

    def test_trailing_slash_on_a_directory_is_fine(self) -> None:
        vfs = make_vfs()
        node = vfs.resolve("/home/user/docs/")
        assert isinstance(node, VDir)
        assert node.name == "docs"
