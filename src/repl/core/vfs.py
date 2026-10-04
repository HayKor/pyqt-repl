"""In-memory virtual file system model and path resolution."""

from dataclasses import dataclass, field
from pathlib import Path

from .errors import VFSPathError

DEFAULT_DIR_MODE = 0o755
DEFAULT_FILE_MODE = 0o644
DEFAULT_OWNER = "root"
DEFAULT_GROUP = "root"


@dataclass
class VNode:
    """Common metadata of a VFS node; ``mode`` holds only permission bits."""

    name: str
    mode: int
    owner: str
    group: str


@dataclass
class VFile(VNode):
    """File with its content as bytes."""

    data: bytes = b""

    @property
    def size(self) -> int:
        """Size of the content in bytes."""
        return len(self.data)


@dataclass
class VDir(VNode):
    """Directory; children are keyed by name."""

    children: dict[str, VNode] = field(default_factory=dict)


@dataclass
class VFS:
    """Whole in-memory file system plus where it came from."""

    name: str
    sha256: str
    root: VDir
    source: Path | None = None

    @property
    def loaded(self) -> bool:
        """True if the VFS was loaded from a file (``--vfs``)."""
        return self.source is not None

    @classmethod
    def empty(cls) -> VFS:
        """Return a VFS with just "/", used when there is no ``--vfs``."""
        root = VDir(
            name="",
            mode=DEFAULT_DIR_MODE,
            owner=DEFAULT_OWNER,
            group=DEFAULT_GROUP,
        )
        return cls(name="<none>", sha256="", root=root, source=None)

    def normalize(self, path: str, cwd: str = "/") -> str:
        """Make an absolute path out of ``path`` relative to ``cwd``.

        No os.path on purpose: those are the real file system's rules.
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
        """Find the node for ``path``; raises VFSPathError.

        Errors show the path as typed, like bash.
        """
        normalized = self.normalize(path, cwd)
        trailing_slash = (
            normalized != "/"
            and path.rstrip() != ""
            and path.rstrip().endswith("/")
        )

        node: VNode = self.root
        if normalized != "/":
            for component in normalized.split("/")[1:]:
                if not isinstance(node, VDir):
                    raise VFSPathError(path, "Not a directory")
                child = node.children.get(component)
                if child is None:
                    raise VFSPathError(path, "No such file or directory")
                node = child

        # "file/" is an error too
        if trailing_slash and isinstance(node, VFile):
            raise VFSPathError(path, "Not a directory")
        return node
