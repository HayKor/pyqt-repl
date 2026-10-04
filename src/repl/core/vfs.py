from dataclasses import dataclass, field
from pathlib import Path

from .errors import VFSPathError

DEFAULT_DIR_MODE = 0o755
DEFAULT_FILE_MODE = 0o644
DEFAULT_OWNER = "root"
DEFAULT_GROUP = "root"


@dataclass
class VNode:
    name: str
    mode: int
    owner: str
    group: str


@dataclass
class VFile(VNode):
    data: bytes = b""

    @property
    def size(self) -> int:
        return len(self.data)


@dataclass
class VDir(VNode):
    children: dict[str, VNode] = field(default_factory=dict)


@dataclass
class VFS:
    name: str
    sha256: str
    root: VDir
    source: Path | None = None

    @property
    def loaded(self) -> bool:
        return self.source is not None

    @classmethod
    def empty(cls) -> VFS:
        # just "/", used when there's no --vfs
        root = VDir(name="", mode=DEFAULT_DIR_MODE, owner=DEFAULT_OWNER, group=DEFAULT_GROUP)
        return cls(name="<none>", sha256="", root=root, source=None)

    def normalize(self, path: str, cwd: str = "/") -> str:
        # no os.path here on purpose, it's the real fs's rules not ours
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
        # errors show the path as typed, like bash
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

        # "file/" is an error too
        if trailing_slash and isinstance(node, VFile):
            raise VFSPathError(path, "Not a directory")
        return node
