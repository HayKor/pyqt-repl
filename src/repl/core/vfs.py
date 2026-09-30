"""In-memory virtual file system: node types and path resolution.

Everything here lives in memory only; nothing in this module ever touches
the real file system for VFS data. Path handling is implemented from
scratch (splitting on ``/``, handling ``.``/``..``) rather than with
``os.path``/``pathlib``, since those operate on the real OS/file system and
its separator conventions, not the VFS's.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .errors import VFSPathError

DEFAULT_DIR_MODE = 0o755
DEFAULT_FILE_MODE = 0o644
DEFAULT_OWNER = "root"
DEFAULT_GROUP = "root"


@dataclass
class VNode:
    """Common metadata shared by every VFS node."""

    name: str
    mode: int
    owner: str
    group: str


@dataclass
class VFile(VNode):
    """A regular file: its content lives entirely in ``data``."""

    data: bytes = b""

    @property
    def size(self) -> int:
        return len(self.data)


@dataclass
class VDir(VNode):
    """A directory: a name -> node mapping of its direct children."""

    children: dict[str, VNode] = field(default_factory=dict)


@dataclass
class VFS:
    """A loaded (or empty) virtual file system."""

    name: str
    sha256: str
    root: VDir
    source: Path | None = None

    @property
    def loaded(self) -> bool:
        """True once a real XML image backs this VFS (``source`` is set)."""
        return self.source is not None

    @classmethod
    def empty(cls) -> VFS:
        """The default VFS used before ``--vfs`` is loaded: just ``/``."""
        root = VDir(name="", mode=DEFAULT_DIR_MODE, owner=DEFAULT_OWNER, group=DEFAULT_GROUP)
        return cls(name="<none>", sha256="", root=root, source=None)

    def normalize(self, path: str, cwd: str = "/") -> str:
        """Return the absolute, canonical form of ``path``.

        ``path`` is resolved relative to ``cwd`` unless it is itself
        absolute (starts with ``/``). ``.`` components are dropped, ``..``
        pops the last component (staying at ``/`` if already there), and
        repeated/trailing slashes collapse away.
        """
        if path.startswith("/"):
            parts: list[str] = []
        else:
            parts = [c for c in cwd.split("/") if c]

        for component in path.split("/"):
            if component in ("", "."):
                continue
            if component == "..":
                if parts:
                    parts.pop()
            else:
                parts.append(component)

        return "/" + "/".join(parts)

    def resolve(self, path: str, cwd: str = "/") -> VNode:
        """Resolve ``path`` (relative to ``cwd``) to the node it names.

        Raises ``VFSPathError`` with ``path`` as given (not normalized) and
        a bash-styled reason: ``"No such file or directory"`` when a
        component is missing, or ``"Not a directory"`` when a non-final
        component (or a trailing-slash path, e.g. ``"file/"``) names a
        file instead of a directory.
        """
        normalized = self.normalize(path, cwd)
        trailing_slash = normalized != "/" and path.rstrip() != "" and path.rstrip().endswith("/")

        node: VNode = self.root
        if normalized != "/":
            for component in normalized.split("/")[1:]:
                if not isinstance(node, VDir):
                    raise VFSPathError(path, "Not a directory")
                child = node.children.get(component)
                if child is None:
                    raise VFSPathError(path, "No such file or directory")
                node = child

        if trailing_slash and isinstance(node, VFile):
            raise VFSPathError(path, "Not a directory")
        return node
