"""
glpi_utils.logger
~~~~~~~~~~~~~~~~~

Logging utilities for python-glpi-utils.

``EmptyHandler``
    Attached to the library's root logger so it stays silent by default.
    The caller decides whether to enable logging and at what level.

``SensitiveFilter``
    A ``logging.Filter`` that masks passwords, tokens and session identifiers
    before they reach any log handler.  Prevents credential leakage when
    debug logging is enabled in production.

    Fields masked (value replaced with ``****``, preserving 4 chars on each
    side for longer strings):

    * ``password`` / ``current_passwd``
    * ``token`` / ``user_token``
    * ``auth`` / ``Authorization`` header values
    * ``session_token`` / ``Session-Token`` header values
    * ``App-Token`` header values
"""

from __future__ import annotations

import logging
import re
from typing import Any

# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

_MASK = "********"
_SHOW_LEN = 4  # characters shown on each end of a long secret

# Field names whose values should always be masked
_SENSITIVE_FIELDS = {
    "password",
    "current_passwd",
    "passwd",
    "token",
    "user_token",
    "auth",
    "session_token",
    # HTTP header names (case-insensitive handled separately)
    "authorization",
    "session-token",
    "app-token",
}

# Regex that matches a full 32-char hex token (Zabbix-style session id pattern)
_TOKEN_RE = re.compile(r"^[A-Fa-f0-9]{32}$")


# ──────────────────────────────────────────────────────────────────────────────
# Public helpers
# ──────────────────────────────────────────────────────────────────────────────


def mask_secret(value: str, show_len: int = _SHOW_LEN) -> str:
    """Replace the middle portion of *value* with ``****``.

    Parameters
    ----------
    value : str
        The raw secret string.
    show_len : int
        Number of characters to reveal on each side.  If the string is too
        short relative to the mask length, returns the mask only.

    Returns
    -------
    str
        Masked string, e.g. ``"grod********2uyjrn"``.
    """
    if not value:
        return _MASK
    if show_len == 0 or len(value) <= (len(_MASK) + show_len * 2):
        return _MASK
    return f"{value[:show_len]}{_MASK}{value[-show_len:]}"


def hide_sensitive(data: Any, _depth: int = 0) -> Any:
    """Recursively mask sensitive values inside *data*.

    Accepts ``dict``, ``list``, or scalar values.  Non-sensitive values are
    returned unchanged.  Dicts and lists are deep-copied (shallow) so the
    original object is never mutated.

    Parameters
    ----------
    data : Any
        Input data — typically the ``args`` of a log record.
    _depth : int
        Internal recursion guard (max depth 10).

    Returns
    -------
    Any
        Data with sensitive field values replaced by the mask.
    """
    if _depth > 10:
        return data

    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            key_lower = str(key).lower()
            if key_lower in _SENSITIVE_FIELDS:
                result[key] = mask_secret(str(value)) if isinstance(value, str) else _MASK
            else:
                result[key] = hide_sensitive(value, _depth + 1)
        return result

    if isinstance(data, (list, tuple)):
        masked = [hide_sensitive(item, _depth + 1) for item in data]
        return type(data)(masked)

    if isinstance(data, str) and _TOKEN_RE.match(data):
        # Looks like a raw session token / hex ID on its own
        return mask_secret(data)

    return data


# ──────────────────────────────────────────────────────────────────────────────
# Logging classes
# ──────────────────────────────────────────────────────────────────────────────


class EmptyHandler(logging.Handler):
    """A no-op handler so the library never emits output by default.

    Attach it to the ``glpi_utils`` logger to suppress the
    *"No handlers could be found"* warning while still allowing the caller
    to add their own handlers.
    """

    def emit(self, record: logging.LogRecord) -> None:  # noqa: D102
        pass


class SensitiveFilter(logging.Filter):
    """Filter that scrubs sensitive data from log records before emission.

    Intercepts ``record.args`` (both ``dict`` and ``tuple`` forms) and
    replaces sensitive field values with :func:`mask_secret`.

    Usage::

        import logging
        from glpi_utils.logger import SensitiveFilter

        handler = logging.StreamHandler()
        handler.addFilter(SensitiveFilter())
        logging.getLogger("glpi_utils").addHandler(handler)
        logging.getLogger("glpi_utils").setLevel(logging.DEBUG)
    """

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D102
        if isinstance(record.args, dict):
            record.args = hide_sensitive(record.args)
        elif isinstance(record.args, tuple):
            record.args = tuple(
                hide_sensitive(arg) if isinstance(arg, (dict, list)) else arg
                for arg in record.args
            )
        return True
