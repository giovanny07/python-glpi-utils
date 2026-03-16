"""
glpi_utils
~~~~~~~~~~

Python library for the GLPI 11 REST API.

Clients
-------
* :class:`GlpiAPI`             – Sync client, legacy API (``/apirest.php``)
* :class:`AsyncGlpiAPI`        – Async client, legacy API (``/apirest.php``)
* :class:`GlpiOAuthClient`     – Sync client, high-level API (``/api.php``, OAuth2)
* :class:`AsyncGlpiOAuthClient`– Async client, high-level API (``/api.php``, OAuth2)

Exceptions
----------
* :exc:`GlpiError`             – Base exception
* :exc:`GlpiAPIError`          – API-level error (includes status_code, error_code)
* :exc:`GlpiAuthError`         – Authentication / session errors
* :exc:`GlpiNotFoundError`     – 404 Not Found
* :exc:`GlpiPermissionError`   – 403 Forbidden
* :exc:`GlpiConnectionError`   – Network/connectivity errors

Utilities
---------
* :class:`GLPIVersion`         – Comparable version helper
* :class:`SensitiveFilter`     – Logging filter that masks credentials
* :class:`EmptyHandler`        – Silent handler (library default)
"""

from .api import GlpiAPI
from .aio import AsyncGlpiAPI
from .oauth import AsyncGlpiOAuthClient, GlpiOAuthClient
from .exceptions import (
    GlpiAPIError,
    GlpiAuthError,
    GlpiConnectionError,
    GlpiError,
    GlpiNotFoundError,
    GlpiPermissionError,
)
from .logger import EmptyHandler, SensitiveFilter
from .version import GLPIVersion

__version__ = "1.4.3"

__all__ = [
    # Clients
    "GlpiAPI",
    "AsyncGlpiAPI",
    "GlpiOAuthClient",
    "AsyncGlpiOAuthClient",
    # Exceptions
    "GlpiError",
    "GlpiAPIError",
    "GlpiAuthError",
    "GlpiNotFoundError",
    "GlpiPermissionError",
    "GlpiConnectionError",
    # Utilities
    "GLPIVersion",
    "SensitiveFilter",
    "EmptyHandler",
]
