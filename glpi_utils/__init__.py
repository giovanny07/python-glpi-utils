"""
python-glpi-utils
~~~~~~~~~~~~~~~~~

A Python library for working with the GLPI 11 REST API.

Supports both synchronous and asynchronous I/O.

Basic usage (sync):

    from glpi_utils import GlpiAPI

    api = GlpiAPI(url="https://glpi.example.com")
    api.login(username="glpi", password="glpi")

    tickets = api.ticket.get_all(range="0-49")
    for ticket in tickets:
        print(ticket["name"])

    api.logout()

Basic usage (async):

    import asyncio
    from glpi_utils import AsyncGlpiAPI

    async def main():
        api = AsyncGlpiAPI(url="https://glpi.example.com")
        await api.login(username="glpi", password="glpi")
        tickets = await api.ticket.get_all(range="0-49")
        for ticket in tickets:
            print(ticket["name"])
        await api.logout()

    asyncio.run(main())

:license: MIT, see LICENSE for details.
"""

from .api import GlpiAPI
from .aio import AsyncGlpiAPI
from .exceptions import (
    GlpiError,
    GlpiAPIError,
    GlpiAuthError,
    GlpiNotFoundError,
    GlpiPermissionError,
)
from .version import GLPIVersion

__version__ = "1.0.0"
__all__ = [
    "GlpiAPI",
    "AsyncGlpiAPI",
    "GlpiError",
    "GlpiAPIError",
    "GlpiAuthError",
    "GlpiNotFoundError",
    "GlpiPermissionError",
    "GLPIVersion",
]
