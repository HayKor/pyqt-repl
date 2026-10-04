import getpass
import os
import socket


def username() -> str:
    """Return the current user's login name.

    Falls back to the ``USER`` environment variable, then to ``"user"``,
    since ``getpass.getuser()`` can raise on minimal/containerized systems
    that lack the usual user database entries.
    """
    try:
        return getpass.getuser()
    except Exception:
        return os.environ.get("USER", "user")


def hostname() -> str:
    """Return the machine's hostname."""
    return socket.gethostname()


def window_title() -> str:
    """Build the main window title: ``Эмулятор - [user@host]``."""
    return f"Эмулятор - [{username()}@{hostname()}]"
