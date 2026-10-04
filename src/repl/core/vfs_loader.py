import base64
import binascii
import hashlib
import re
from pathlib import Path
from xml.etree import ElementTree as ET

from .errors import VFSLoadError
from .vfs import (
    DEFAULT_DIR_MODE,
    DEFAULT_FILE_MODE,
    DEFAULT_GROUP,
    DEFAULT_OWNER,
    VDir,
    VFile,
    VFS,
    VNode,
)

_VALID_ROOT_ATTRS = frozenset({"name", "mode", "owner", "group"})
_VALID_DIR_ATTRS = frozenset({"name", "mode", "owner", "group"})
_VALID_FILE_ATTRS = frozenset({"name", "mode", "owner", "group", "encoding"})
_MODE_RE = re.compile(r"^0?[0-7]{3}$")


class _FormatError(Exception):
    """Internal: one VFS-schema violation, wrapped as ``VFSLoadError`` by ``load_vfs``."""


def load_vfs(path: Path) -> VFS:
    """Load and parse the VFS image at ``path``.

    Raises ``VFSLoadError`` (bash-styled message) if the file cannot be
    read, is not well-formed XML, or does not follow the VFS schema.
    """
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        raise VFSLoadError(f"repl: vfs: {path}: No such file or directory") from None
    except IsADirectoryError:
        raise VFSLoadError(f"repl: vfs: {path}: Is a directory") from None
    except PermissionError:
        raise VFSLoadError(f"repl: vfs: {path}: Permission denied") from None

    try:
        root_elem = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise VFSLoadError(f"repl: vfs: {path}: invalid XML: {exc}") from exc

    try:
        name, root = _parse_root(root_elem, path)
    except _FormatError as exc:
        raise VFSLoadError(f"repl: vfs: {path}: invalid format: {exc}") from exc

    sha256 = hashlib.sha256(raw).hexdigest()
    return VFS(name=name, sha256=sha256, root=root, source=path)


def describe(vfs: VFS) -> str:
    """Format the ``[vfs] loaded ...`` message printed at startup."""
    dirs, files = _count(vfs.root)
    return f"[vfs] loaded '{vfs.name}' ({dirs} dirs, {files} files)"


def _count(node: VDir) -> tuple[int, int]:
    dirs = 0
    files = 0
    for child in node.children.values():
        if isinstance(child, VDir):
            dirs += 1
            sub_dirs, sub_files = _count(child)
            dirs += sub_dirs
            files += sub_files
        else:
            files += 1
    return dirs, files


def _parse_root(elem: ET.Element, path: Path) -> tuple[str, VDir]:
    if elem.tag != "vfs":
        raise _FormatError(f"root element must be <vfs>, got <{elem.tag}>")
    _check_attrs(elem, _VALID_ROOT_ATTRS, "<vfs>")
    _check_no_text(elem, "<vfs>")

    name = elem.get("name") or path.stem
    mode = _parse_mode(elem.get("mode"), DEFAULT_DIR_MODE)
    owner = elem.get("owner", DEFAULT_OWNER)
    group = elem.get("group", DEFAULT_GROUP)
    children = _parse_children(elem, "/")
    return name, VDir(name="", mode=mode, owner=owner, group=group, children=children)


def _parse_children(elem: ET.Element, dir_path: str) -> dict[str, VNode]:
    children: dict[str, VNode] = {}
    for child in elem:
        if child.tag == "dir":
            name = _validate_name(child.get("name"), "dir")
            _check_unique(children, name, dir_path)
            children[name] = _parse_dir(child, name, _join(dir_path, name))
        elif child.tag == "file":
            name = _validate_name(child.get("name"), "file")
            _check_unique(children, name, dir_path)
            children[name] = _parse_file(child, name, _join(dir_path, name))
        else:
            raise _FormatError(f"unknown element <{child.tag}> in {dir_path}")
    return children


def _parse_dir(elem: ET.Element, name: str, dir_path: str) -> VDir:
    _check_attrs(elem, _VALID_DIR_ATTRS, f"<dir> {dir_path}")
    _check_no_text(elem, f"<dir> {dir_path}")
    mode = _parse_mode(elem.get("mode"), DEFAULT_DIR_MODE)
    owner = elem.get("owner", DEFAULT_OWNER)
    group = elem.get("group", DEFAULT_GROUP)
    children = _parse_children(elem, dir_path)
    return VDir(name=name, mode=mode, owner=owner, group=group, children=children)


def _parse_file(elem: ET.Element, name: str, file_path: str) -> VFile:
    _check_attrs(elem, _VALID_FILE_ATTRS, f"<file> {file_path}")
    if len(elem) > 0:
        raise _FormatError(f"<file> must not have child elements ({file_path})")
    mode = _parse_mode(elem.get("mode"), DEFAULT_FILE_MODE)
    owner = elem.get("owner", DEFAULT_OWNER)
    group = elem.get("group", DEFAULT_GROUP)
    encoding = elem.get("encoding", "text")
    text = elem.text or ""

    if encoding == "text":
        data = text.encode("utf-8")
    elif encoding == "base64":
        cleaned = "".join(text.split())
        try:
            data = base64.b64decode(cleaned, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise _FormatError(f"invalid base64 in {file_path}: {exc}") from exc
    else:
        raise _FormatError(f"unknown encoding {encoding!r} on {file_path}")

    return VFile(name=name, mode=mode, owner=owner, group=group, data=data)


def _parse_mode(value: str | None, default: int) -> int:
    if value is None:
        return default
    if not _MODE_RE.fullmatch(value):
        raise _FormatError(f"invalid mode {value!r}")
    return int(value, 8)


def _validate_name(name: str | None, kind: str) -> str:
    if not name:
        raise _FormatError(f"missing name for <{kind}>")
    if "/" in name or name in (".", ".."):
        raise _FormatError(f"invalid name {name!r}")
    return name


def _check_attrs(elem: ET.Element, valid: frozenset[str], context: str) -> None:
    unknown = set(elem.attrib) - valid
    if unknown:
        raise _FormatError(f"unknown attribute {sorted(unknown)[0]!r} on {context}")


def _check_no_text(elem: ET.Element, context: str) -> None:
    if elem.text and elem.text.strip():
        raise _FormatError(f"unexpected text in {context}")


def _check_unique(children: dict[str, VNode], name: str, dir_path: str) -> None:
    if name in children:
        raise _FormatError(f'duplicate name "{name}" in {dir_path}')


def _join(dir_path: str, name: str) -> str:
    return name if dir_path == "/" else f"{dir_path}/{name}"
