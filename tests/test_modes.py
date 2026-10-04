"""Tests for chmod MODE parsing."""

import stat
import pytest

from repl.core.modes import ModeError, looks_like_symbolic_mode, parse_mode

# octal


def perms(mode: int) -> str:
    """Render permission bits like ``ls -l`` does: ``rwxr-xr-x``."""
    return stat.filemode(mode)[1:]


def test_octal_replaces_bits_wholesale() -> None:
    assert perms(parse_mode("755", 0o000)) == "rwxr-xr-x"


def test_octal_with_leading_zero() -> None:
    assert perms(parse_mode("0644", 0o777)) == "rw-r--r--"


def test_octal_ignores_current_mode() -> None:
    assert perms(parse_mode("700", 0o644)) == "rwx------"


def test_octal_rejects_special_bits() -> None:
    with pytest.raises(ModeError):
        parse_mode("4755", 0o644)


def test_octal_rejects_too_few_digits() -> None:
    with pytest.raises(ModeError):
        parse_mode("75", 0o644)


def test_octal_rejects_bad_digit() -> None:
    with pytest.raises(ModeError):
        parse_mode("789", 0o644)


# symbolic: single clause


def test_symbolic_add_bit_for_owner() -> None:
    assert perms(parse_mode("u+x", 0o644)) == "rwxr--r--"


def test_symbolic_remove_bit_for_group_and_other() -> None:
    assert perms(parse_mode("go-r", 0o644)) == "rw-------"


def test_symbolic_empty_who_means_all() -> None:
    assert perms(parse_mode("+x", 0o644)) == "rwxr-xr-x"


def test_symbolic_a_means_all() -> None:
    assert perms(parse_mode("a=r", 0o777)) == "r--r--r--"


def test_symbolic_assign_empty_perms_clears_role() -> None:
    assert perms(parse_mode("o=", 0o777)) == "rwxrwx---"


def test_symbolic_assign_only_touches_named_role() -> None:
    # group/other stay as they were
    assert perms(parse_mode("u=rwx", 0o022)) == "rwx-w--w-"


# symbolic: comma lists and multi-op clauses


def test_symbolic_comma_list() -> None:
    assert perms(parse_mode("u=rwx,g=rx,o=", 0o000)) == "rwxr-x---"


def test_symbolic_multiple_ops_in_one_clause_apply_in_order() -> None:
    assert perms(parse_mode("u+x-w", 0o600)) == "r-x------"


def test_symbolic_minus_x_removes_execute_for_everyone() -> None:
    assert perms(parse_mode("-x", 0o755)) == "rw-r--r--"


# symbolic: rejected forms


def test_symbolic_rejects_capital_x() -> None:
    with pytest.raises(ModeError):
        parse_mode("u+X", 0o644)


def test_symbolic_rejects_setuid_s() -> None:
    with pytest.raises(ModeError):
        parse_mode("u+s", 0o644)


def test_symbolic_rejects_sticky_t() -> None:
    with pytest.raises(ModeError):
        parse_mode("+t", 0o644)


def test_symbolic_rejects_role_copy() -> None:
    with pytest.raises(ModeError):
        parse_mode("u=g", 0o644)


def test_rejects_empty_spec() -> None:
    with pytest.raises(ModeError):
        parse_mode("", 0o644)


def test_rejects_garbage() -> None:
    with pytest.raises(ModeError):
        parse_mode("xyz", 0o644)


def test_rejects_trailing_comma() -> None:
    with pytest.raises(ModeError):
        parse_mode("u+x,", 0o644)


# looks_like_symbolic_mode


def test_looks_like_symbolic_mode_true_for_dash_x() -> None:
    assert looks_like_symbolic_mode("-x") is True


def test_looks_like_symbolic_mode_true_for_dash_w() -> None:
    assert looks_like_symbolic_mode("-w") is True


def test_looks_like_symbolic_mode_false_for_dash_capital_r() -> None:
    assert looks_like_symbolic_mode("-R") is False


def test_looks_like_symbolic_mode_false_for_unknown_option() -> None:
    assert looks_like_symbolic_mode("-z") is False
