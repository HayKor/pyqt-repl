import getpass
import os
import socket


def username() -> str:
    # getuser() can blow up in containers without a passwd entry
    try:
        return getpass.getuser()
    except Exception:
        return os.environ.get("USER", "user")


def hostname() -> str:
    return socket.gethostname()


def window_title() -> str:
    return f"Эмулятор - [{username()}@{hostname()}]"
