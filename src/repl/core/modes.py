"""Parsing of chmod MODE: octal and symbolic forms."""

import re

_OCTAL_RE = re.compile(r"0?[0-7]{3}")
_CLAUSE_RE = re.compile(r"([ugoa]*)((?:[+\-=][rwx]*)+)")
_OP_RE = re.compile(r"[+\-=][rwx]*")

# "=" clears these first
_ROLE_MASK = {"u": 0o700, "g": 0o070, "o": 0o007}

_ROLE_PERM_BIT = {
    "u": {"r": 0o400, "w": 0o200, "x": 0o100},
    "g": {"r": 0o040, "w": 0o020, "x": 0o010},
    "o": {"r": 0o004, "w": 0o002, "x": 0o001},
}


class ModeError(Exception):
    """Invalid chmod MODE."""

    pass


def parse_mode(spec: str, current_mode: int) -> int:
    """Apply chmod MODE to ``current_mode`` and return the new mode.

    Octal replaces everything, symbolic works on top of ``current_mode``.
    Raises ModeError if the spec is invalid.
    """
    if _OCTAL_RE.fullmatch(spec):
        return int(spec, 8)
    return _parse_symbolic(spec, current_mode)


def _apply_op(mode: int, op: str, role: str, perms: str) -> int:
    """Apply one ``+``/``-``/``=`` with ``perms`` (``rwx``) to one role."""
    bits = 0
    for perm in perms:
        bits |= _ROLE_PERM_BIT[role][perm]
    if op == "+":
        return mode | bits
    if op == "-":
        return mode & ~bits
    return (mode & ~_ROLE_MASK[role]) | bits


def _parse_symbolic(spec: str, current_mode: int) -> int:
    """Apply a comma-separated symbolic MODE (``u+x,go-w``)."""
    mode = current_mode
    for clause in spec.split(","):
        match = _CLAUSE_RE.fullmatch(clause)
        if not match or not match.group(2):
            raise ModeError(spec)

        who = match.group(1)
        roles = set("ugo") if not who or "a" in who else set(who)

        for op_group in _OP_RE.findall(match.group(2)):
            op, perms = op_group[0], op_group[1:]
            for role in roles:
                mode = _apply_op(mode, op, role, perms)
    return mode & 0o777


def looks_like_symbolic_mode(spec: str) -> bool:
    """Tell a MODE like ``-x`` from a real option (for chmod)."""
    try:
        parse_mode(spec, 0)
    except ModeError:
        return False
    return True
