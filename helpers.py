"""Shared utility helpers used across handlers."""
import re

_MD_SPECIAL = re.compile(r"([_*\[\]`])")


def escape_md(text) -> str:
    """Escape Markdown V1 special chars in user-supplied strings.

    Use this before interpolating any user-controlled value (full_name,
    username, gmail, free-text input) into a message sent with
    parse_mode='Markdown'.
    """
    if text is None:
        return ""
    return _MD_SPECIAL.sub(r"\\\1", str(text))
