"""
glpi_utils.version
~~~~~~~~~~~~~~~~~~

GLPIVersion – a comparable wrapper around GLPI API version strings.

Examples
--------
>>> v = GLPIVersion("11.0.0")
>>> v.major
11
>>> v.minor
0
>>> v > "10.0"
True
>>> v == 11.0
True
"""

from __future__ import annotations

import re
from typing import Any, Union


_VersionLike = Union[str, int, float, "GLPIVersion"]


class GLPIVersion:
    """Represents a GLPI API version and supports rich comparisons.

    Parameters
    ----------
    version : str
        Version string as returned by ``/apirest.php/getGlpiVersion``,
        e.g. ``"11.0.0"``.
    """

    _RE = re.compile(r"^(\d+)(?:\.(\d+)(?:\.(\d+))?)?")

    def __init__(self, version: str) -> None:
        match = self._RE.match(str(version))
        if not match or not match.group(0):
            raise ValueError(f"Cannot parse version string: {version!r}")
        self._major = int(match.group(1))
        self._minor = int(match.group(2) or 0)
        self._patch = int(match.group(3) or 0)
        self._raw = str(version)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def major(self) -> int:
        """Major version number (e.g. ``11`` for ``11.0.0``)."""
        return self._major

    @property
    def minor(self) -> int:
        """Minor version number (e.g. ``0`` for ``11.0.0``)."""
        return self._minor

    @property
    def patch(self) -> int:
        """Patch version number (e.g. ``0`` for ``11.0.0``)."""
        return self._patch

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _as_tuple(self) -> tuple[int, int, int]:
        return (self._major, self._minor, self._patch)

    @classmethod
    def _coerce(cls, other: _VersionLike) -> tuple[int, int, int]:
        if isinstance(other, GLPIVersion):
            return other._as_tuple()
        s = str(float(other)) if isinstance(other, (int, float)) else str(other)
        # Normalise "11" → "11.0.0", "11.0" → "11.0.0"
        parts = s.split(".")
        while len(parts) < 3:
            parts.append("0")
        return tuple(int(p) for p in parts[:3])  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Rich comparisons
    # ------------------------------------------------------------------

    def __eq__(self, other: object) -> bool:
        try:
            return self._as_tuple() == self._coerce(other)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return NotImplemented

    def __lt__(self, other: _VersionLike) -> bool:
        return self._as_tuple() < self._coerce(other)

    def __le__(self, other: _VersionLike) -> bool:
        return self._as_tuple() <= self._coerce(other)

    def __gt__(self, other: _VersionLike) -> bool:
        return self._as_tuple() > self._coerce(other)

    def __ge__(self, other: _VersionLike) -> bool:
        return self._as_tuple() >= self._coerce(other)

    def __hash__(self) -> int:
        return hash(self._as_tuple())

    # ------------------------------------------------------------------
    # String representations
    # ------------------------------------------------------------------

    def __str__(self) -> str:
        return self._raw

    def __repr__(self) -> str:
        return f"GLPIVersion({self._raw!r})"
