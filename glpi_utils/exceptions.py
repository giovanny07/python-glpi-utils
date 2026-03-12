"""
glpi_utils.exceptions
~~~~~~~~~~~~~~~~~~~~~

Exception hierarchy for python-glpi-utils.

    GlpiError                   ← base for all library errors
    ├── GlpiAPIError            ← server returned an API-level error
    │   ├── GlpiAuthError       ← 401 / session invalid
    │   ├── GlpiNotFoundError   ← 404 item not found
    │   └── GlpiPermissionError ← 403 insufficient rights
    └── GlpiConnectionError     ← network / transport error
"""

from typing import Optional


class GlpiError(Exception):
    """Base exception for all glpi_utils errors."""


class GlpiConnectionError(GlpiError):
    """Raised when a network or transport error occurs."""


class GlpiAPIError(GlpiError):
    """Raised when the GLPI server returns an API-level error response.

    Attributes
    ----------
    status_code : int or None
        HTTP status code returned by the server.
    error_code : str or None
        GLPI error identifier (e.g. ``"ERROR_SESSION_TOKEN_INVALID"``).
    message : str
        Human-readable error message.
    """

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        error_code: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.message = message

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"status_code={self.status_code!r}, "
            f"error_code={self.error_code!r}, "
            f"message={self.message!r})"
        )


class GlpiAuthError(GlpiAPIError):
    """Raised on authentication failures (HTTP 401 or invalid session token)."""


class GlpiNotFoundError(GlpiAPIError):
    """Raised when the requested resource does not exist (HTTP 404)."""


class GlpiPermissionError(GlpiAPIError):
    """Raised when the authenticated user lacks the required rights (HTTP 403)."""
