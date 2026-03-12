"""
glpi_utils.aio
~~~~~~~~~~~~~~

Asynchronous GLPI REST API client powered by ``aiohttp``.

The public interface mirrors :class:`~glpi_utils.api.GlpiAPI` exactly so
callers can swap between sync and async with minimal changes.

Requires the optional ``aiohttp`` dependency::

    pip install glpi-utils[async]
"""

from __future__ import annotations

import logging
import os
from base64 import b64encode
from typing import Any

from ._resource import AsyncItemProxy
from .api import _ITEMTYPE_MAP, _boolify_params, _raise_for_glpi_error
from .exceptions import GlpiAuthError, GlpiConnectionError
from .version import GLPIVersion

log = logging.getLogger(__name__)


class AsyncGlpiAPI:
    """Asynchronous client for the GLPI 11 legacy REST API.

    Must be used with ``await``::

        import asyncio
        from glpi_utils import AsyncGlpiAPI

        async def main():
            api = AsyncGlpiAPI(url="https://glpi.example.com")
            await api.login(username="glpi", password="glpi")
            tickets = await api.ticket.get_all()
            await api.logout()

        asyncio.run(main())

    Can also be used as an async context manager::

        async with AsyncGlpiAPI(url="https://glpi.example.com") as api:
            await api.login(username="glpi", password="glpi")
            print(api.version)

    Parameters
    ----------
    url : str | None
    app_token : str | None
    verify_ssl : bool
    timeout : int
    """

    def __init__(
        self,
        url: str | None = None,
        app_token: str | None = None,
        verify_ssl: bool = True,
        timeout: int = 30,
    ) -> None:
        try:
            import aiohttp  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "AsyncGlpiAPI requires 'aiohttp'. "
                "Install it with: pip install glpi-utils[async]"
            ) from exc

        self._url = (url or os.environ.get("GLPI_URL", "")).rstrip("/")
        if not self._url:
            raise ValueError(
                "A GLPI URL is required. Pass url= or set GLPI_URL."
            )
        self._app_token = app_token or os.environ.get("GLPI_APP_TOKEN")
        self._verify_ssl = verify_ssl
        self._timeout = timeout

        self._session_token: str | None = None
        self._http: Any = None  # aiohttp.ClientSession, created lazily
        self._version: GLPIVersion | None = None
        self._proxies: dict[str, AsyncItemProxy] = {}

    # ------------------------------------------------------------------
    # Async context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "AsyncGlpiAPI":
        return self

    async def __aexit__(self, *_: Any) -> None:
        if self._session_token:
            try:
                await self.logout()
            except Exception:
                pass
        if self._http and not self._http.closed:
            await self._http.close()

    # ------------------------------------------------------------------
    # Fluent accessors
    # ------------------------------------------------------------------

    def __getattr__(self, name: str) -> AsyncItemProxy:
        lower = name.lower()
        if lower in _ITEMTYPE_MAP:
            if lower not in self._proxies:
                self._proxies[lower] = AsyncItemProxy(self, _ITEMTYPE_MAP[lower])
            return self._proxies[lower]
        raise AttributeError(
            f"{self.__class__.__name__!r} has no attribute {name!r}. "
            "Use api.item('YourItemtype') for non-standard item types."
        )

    def item(self, itemtype: str) -> AsyncItemProxy:
        """Return an :class:`~glpi_utils._resource.AsyncItemProxy` for any itemtype."""
        if itemtype not in self._proxies:
            self._proxies[itemtype] = AsyncItemProxy(self, itemtype)
        return self._proxies[itemtype]

    # ------------------------------------------------------------------
    # Internal HTTP helpers
    # ------------------------------------------------------------------

    @property
    def _base_url(self) -> str:
        return f"{self._url}/apirest.php"

    def _get_http(self) -> Any:
        """Lazily create the aiohttp ClientSession."""
        import aiohttp

        if self._http is None or self._http.closed:
            connector = aiohttp.TCPConnector(ssl=self._verify_ssl)
            self._http = aiohttp.ClientSession(connector=connector)
        return self._http

    def _default_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._app_token:
            headers["App-Token"] = self._app_token
        if self._session_token:
            headers["Session-Token"] = self._session_token
        return headers

    async def _request(
        self,
        method: str,
        path: str,
        *,
        headers: dict | None = None,
        params: dict | None = None,
        json: Any = None,
    ) -> Any:
        import aiohttp

        url = f"{self._base_url}/{path.lstrip('/')}"
        merged_headers = {**self._default_headers(), **(headers or {})}

        log.debug("ASYNC %s %s params=%s", method.upper(), url, params)

        http = self._get_http()
        timeout = aiohttp.ClientTimeout(total=self._timeout)

        try:
            async with http.request(
                method,
                url,
                headers=merged_headers,
                params=params,
                json=json,
                timeout=timeout,
            ) as response:
                status = response.status
                log.debug("Response %s from %s", status, url)

                if status == 204 or response.content_length == 0:
                    return None

                body = await response.json(content_type=None)

                # Build a minimal sync-compatible response object for the helper
                class _FakeResponse:
                    status_code = status
                    content = True

                    def json(self_):
                        return body

                    text = str(body)

                _raise_for_glpi_error(_FakeResponse())  # type: ignore[arg-type]
                return body

        except aiohttp.ClientConnectorError as exc:
            raise GlpiConnectionError(f"Cannot reach GLPI at {self._url}: {exc}") from exc
        except aiohttp.ServerTimeoutError as exc:
            raise GlpiConnectionError(f"Request timed out: {exc}") from exc

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    async def login(
        self,
        username: str | None = None,
        password: str | None = None,
        user_token: str | None = None,
    ) -> None:
        """Authenticate and obtain a session token."""
        username = username or os.environ.get("GLPI_USER")
        password = password or os.environ.get("GLPI_PASSWORD")
        user_token = user_token or os.environ.get("GLPI_USER_TOKEN")

        auth_headers: dict[str, str] = {}

        if user_token:
            auth_headers["Authorization"] = f"user_token {user_token}"
        elif username and password:
            credentials = b64encode(f"{username}:{password}".encode()).decode()
            auth_headers["Authorization"] = f"Basic {credentials}"
        else:
            raise GlpiAuthError(
                "Provide username+password or user_token."
            )

        data = await self._request("GET", "initSession", headers=auth_headers)
        self._session_token = data["session_token"]

    async def logout(self) -> None:
        """Terminate the active GLPI session."""
        if self._session_token:
            try:
                await self._request("GET", "killSession")
            finally:
                self._session_token = None

    # ------------------------------------------------------------------
    # Version
    # ------------------------------------------------------------------

    @property
    def version(self) -> GLPIVersion | None:
        """Return cached version (call ``await api.get_version()`` to fetch)."""
        return self._version

    async def get_version(self) -> GLPIVersion:
        """Fetch and cache the GLPI server version."""
        data = await self._request("GET", "getGlpiVersion")
        self._version = GLPIVersion(data.get("glpi_version", "0.0.0"))
        return self._version

    # ------------------------------------------------------------------
    # Session utilities
    # ------------------------------------------------------------------

    async def get_my_profiles(self) -> list[dict]:
        return (await self._request("GET", "getMyProfiles"))["myprofiles"]

    async def get_active_profile(self) -> dict:
        return (await self._request("GET", "getActiveProfile"))["active_profile"]

    async def set_active_profile(self, profile_id: int) -> None:
        await self._request("POST", "changeActiveProfile", json={"profiles_id": profile_id})

    async def get_my_entities(self, is_recursive: bool = False) -> list[dict]:
        return (
            await self._request(
                "GET", "getMyEntities", params={"is_recursive": int(is_recursive)}
            )
        )["myentities"]

    async def get_active_entities(self) -> dict:
        return (await self._request("GET", "getActiveEntities"))["active_entity"]

    async def set_active_entity(self, entity_id: int, is_recursive: bool = False) -> None:
        await self._request(
            "POST",
            "changeActiveEntities",
            json={"entities_id": entity_id, "is_recursive": int(is_recursive)},
        )

    async def get_full_session(self) -> dict:
        return (await self._request("GET", "getFullSession"))["session"]

    # ------------------------------------------------------------------
    # Item CRUD
    # ------------------------------------------------------------------

    async def get_item(self, itemtype: str, item_id: int, **kwargs: Any) -> dict:
        params = _boolify_params(kwargs)
        return await self._request("GET", f"{itemtype}/{item_id}", params=params)

    async def get_all_items(self, itemtype: str, **kwargs: Any) -> list[dict]:
        params = _boolify_params(kwargs)
        if "range" not in params:
            params["range"] = "0-49"
        return await self._request("GET", itemtype, params=params)

    async def search(self, itemtype: str, **kwargs: Any) -> dict:
        params = _boolify_params(kwargs)
        return await self._request("GET", f"search/{itemtype}", params=params)

    async def create_item(
        self, itemtype: str, input_data: dict | list[dict], **kwargs: Any
    ) -> dict | list:
        payload: dict[str, Any] = {"input": input_data}
        payload.update(kwargs)
        return await self._request("POST", itemtype, json=payload)

    async def update_item(
        self, itemtype: str, input_data: dict | list[dict], **kwargs: Any
    ) -> list:
        payload: dict[str, Any] = {"input": input_data}
        payload.update(kwargs)
        return await self._request("PUT", itemtype, json=payload)

    async def delete_item(
        self,
        itemtype: str,
        input_data: dict | list[dict],
        force_purge: bool = False,
        history: bool = True,
    ) -> list:
        payload: dict[str, Any] = {
            "input": input_data,
            "force_purge": int(force_purge),
            "history": int(history),
        }
        return await self._request("DELETE", itemtype, json=payload)

    # ------------------------------------------------------------------
    # Sub-items
    # ------------------------------------------------------------------

    async def get_sub_items(
        self, itemtype: str, item_id: int, sub_itemtype: str, **kwargs: Any
    ) -> list[dict]:
        params = _boolify_params(kwargs)
        return await self._request(
            "GET", f"{itemtype}/{item_id}/{sub_itemtype}", params=params
        )

    async def add_sub_item(
        self,
        itemtype: str,
        item_id: int,
        sub_itemtype: str,
        input_data: dict,
        **kwargs: Any,
    ) -> dict:
        payload: dict[str, Any] = {"input": input_data}
        payload.update(kwargs)
        return await self._request(
            "POST", f"{itemtype}/{item_id}/{sub_itemtype}", json=payload
        )

    async def list_item_types(self) -> list[str]:
        return await self._request("GET", "listItemtypes")
