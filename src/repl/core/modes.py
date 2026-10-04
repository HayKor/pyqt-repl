import re

_OCTAL_RE = re.compile(r"0?[0-7]{3}")
_CLAUSE_RE = re.compile(r"([ugoa]*)((?:[+\-=][rwx]*)+)")
_OP_RE = re.compile(r"[+\-=][rwx]*")

# Bits touched by "=" for a given role (used to clear before setting).
_ROLE_MASK = {"u": 0o700, "g": 0o070, "o": 0o007}

# Bit for a given (role, permission letter) pair.
_ROLE_PERM_BIT = {
    "u": {"r": 0o400, "w": 0o200, "x": 0o100},
    "g": {"r": 0o040, "w": 0o020, "x": 0o010},
    "o": {"r": 0o004, "w": 0o002, "x": 0o001},
}


class ModeError(Exception):
    """Raised by ``parse_mode`` for a MODE spec that fails to parse."""


def parse_mode(spec: str, current_mode: int) -> int:
    """Return the permission bits (0..0o777) that ``spec`` produces.

    ``current_mode`` is the node's existing permission bits, used as the
    base for a symbolic spec (ignored by an octal one, which replaces the
    bits wholesale). Raises ``ModeError`` if ``spec`` matches neither
    grammar.
    """
    if _OCTAL_RE.fullmatch(spec):
        return int(spec, 8)
    return _parse_symbolic(spec, current_mode)


def _parse_symbolic(spec: str, current_mode: int) -> int:
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
                bits = 0
                for perm in perms:
                    bits |= _ROLE_PERM_BIT[role][perm]
                if op == "+":
                    mode |= bits
                elif op == "-":
                    mode &= ~bits
                else:  # "="
                    mode = (mode & ~_ROLE_MASK[role]) | bits
    return mode & 0o777


def looks_like_symbolic_mode(spec: str) -> bool:
    """True if ``spec`` parses as a symbolic MODE (regardless of octal).

    Used to decide whether a ``-``-prefixed argument such as ``-x`` is the
    MODE operand (as GNU ``chmod -x file`` treats it) rather than an
    unrecognized option; the octal grammar never starts with ``-``, so
    trying to apply ``spec`` to a dummy ``current_mode`` of ``0`` is an
    exact structural check.
    """
    try:
        parse_mode(spec, 0)
    except ModeError:
        return False
    return True
