"""Real user/host information for the prompt and window title."""

import getpass
import os
import socket


def username() -> str:
    """Return the user name; fall back to $USER without a passwd entry."""
    try:
        return getpass.getuser()
    except Exception:
        return os.environ.get("USER", "user")


def hostname() -> str:
    """Host name of the machine."""
    return socket.gethostname()


def window_title() -> str:
    """Return the main window title with the real user and host."""
    return f"Эмулятор - [{username()}@{hostname()}]"
