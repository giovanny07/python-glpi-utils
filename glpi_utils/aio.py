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
from typing import Any, AsyncIterator, Optional

from ._resource import AsyncItemProxy
from .api import DEFAULT_PAGE_SIZE, _ITEMTYPE_MAP, _boolify_params, _parse_content_range, _raise_for_glpi_error
from .exceptions import GlpiAPIError, GlpiAuthError, GlpiConnectionError
from .logger import EmptyHandler, SensitiveFilter
from .version import GLPIVersion

log = logging.getLogger(__name__)
log.addHandler(EmptyHandler())
log.addFilter(SensitiveFilter())


class AsyncGlpiAPI:
    """Asynchronous client for the GLPI 11 legacy REST API (``/apirest.php``).

    Must be used with ``await``::

        import asyncio
        from glpi_utils import AsyncGlpiAPI

        async def main():
            api = AsyncGlpiAPI(url="https://glpi.example.com")
            await api.login(username="glpi", password="glpi")

            # Single page
            tickets = await api.ticket.get_all()

            # All pages automatically
            all_tickets = await api.ticket.get_all_pages()

            # Memory-efficient iteration
            async for page in api.ticket.iter_pages(page_size=100):
                for ticket in page:
                    process(ticket)

            await api.logout()

        asyncio.run(main())

    Can also be used as an async context manager::

        async with AsyncGlpiAPI(url="https://glpi.example.com") as api:
            await api.login(username="glpi", password="glpi")
            version = await api.get_version()

    Parameters
    ----------
    url : str or None
    app_token : str or None
    verify_ssl : bool
    timeout : int
    """

    def __init__(
        self,
        url: Optional[str] = None,
        app_token: Optional[str] = None,
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
            raise ValueError("A GLPI URL is required. Pass url= or set GLPI_URL.")
        self._app_token = app_token or os.environ.get("GLPI_APP_TOKEN")
        self._verify_ssl = verify_ssl
        self._timeout = timeout

        self._session_token: Optional[str] = None
        self._http: Any = None
        self._version: Optional[GLPIVersion] = None
        self._proxies: dict = {}

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

    def _default_headers(self) -> dict:
        headers: dict = {"Content-Type": "application/json"}
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
        headers: Optional[dict] = None,
        params: Optional[dict] = None,
        json: Any = None,
    ) -> Any:
        body, _ = await self._request_with_headers(
            method, path, headers=headers, params=params, json=json
        )
        return body

    async def _request_with_headers(
        self,
        method: str,
        path: str,
        *,
        headers: Optional[dict] = None,
        params: Optional[dict] = None,
        json: Any = None,
    ) -> tuple:
        """Like ``_request`` but returns ``(body, response_headers)``."""
        import aiohttp

        url = f"{self._base_url}/{path.lstrip('/')}"
        merged_headers = {**self._default_headers(), **(headers or {})}

        log.debug("ASYNC %s %s params=%s", method.upper(), url, params)

        http = self._get_http()
        timeout = aiohttp.ClientTimeout(total=self._timeout)

        try:
            async with http.request(
                method, url,
                headers=merged_headers,
                params=params,
                json=json,
                timeout=timeout,
            ) as response:
                status = response.status
                resp_headers = dict(response.headers)
                log.debug("Response %s from %s", status, url)

                if status == 204 or response.content_length == 0:
                    return None, resp_headers

                body = await response.json(content_type=None)

                class _FakeResponse:
                    status_code = status
                    content = True

                    def json(self_):
                        return body

                    text = str(body)

                _raise_for_glpi_error(_FakeResponse())  # type: ignore[arg-type]
                return body, resp_headers

        except aiohttp.ClientConnectorError as exc:
            raise GlpiConnectionError(f"Cannot reach GLPI at {self._url}: {exc}") from exc
        except aiohttp.ServerTimeoutError as exc:
            raise GlpiConnectionError(f"Request timed out: {exc}") from exc

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    async def login(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        user_token: Optional[str] = None,
    ) -> None:
        """Authenticate and obtain a session token."""
        username   = username   or os.environ.get("GLPI_USER")
        password   = password   or os.environ.get("GLPI_PASSWORD")
        user_token = user_token or os.environ.get("GLPI_USER_TOKEN")

        auth_headers: dict = {}

        if user_token:
            auth_headers["Authorization"] = f"user_token {user_token}"
        elif username and password:
            credentials = b64encode(f"{username}:{password}".encode()).decode()
            auth_headers["Authorization"] = f"Basic {credentials}"
        else:
            raise GlpiAuthError("Provide username+password or user_token.")

        data = await self._request("GET", "initSession", headers=auth_headers)
        self._session_token = data["session_token"]
        log.debug("Async session established.")

    async def logout(self) -> None:
        """Terminate the active GLPI session."""
        if self._session_token:
            try:
                await self._request("GET", "killSession")
            finally:
                self._session_token = None
                log.debug("Async session terminated.")

    # ------------------------------------------------------------------
    # Version
    # ------------------------------------------------------------------

    @property
    def version(self) -> Optional[GLPIVersion]:
        """Return cached version (call ``await api.get_version()`` to fetch)."""
        return self._version

    async def get_version(self) -> GLPIVersion:
        """Fetch and cache the GLPI server version."""
        raw = None
        try:
            data = await self._request("GET", "getGlpiConfig")
            raw = (
                (data.get("cfg_glpi") or {}).get("version")
                or (data.get("cfg_glpi") or {}).get("glpi_version")
                or data.get("glpi_version")
                or data.get("version")
            )
        except GlpiAPIError:
            raw = None
        if not raw:
            try:
                session = await self._request("GET", "getFullSession")
                raw = (
                    (session.get("session") or {}).get("glpi_version")
                    or session.get("glpi_version")
                )
            except GlpiAPIError:
                raw = None
        self._version = GLPIVersion(raw or "0.0.0")
        return self._version

    # ------------------------------------------------------------------
    # Session utilities
    # ------------------------------------------------------------------

    async def get_my_profiles(self) -> list:
        return (await self._request("GET", "getMyProfiles"))["myprofiles"]

    async def get_active_profile(self) -> dict:
        return (await self._request("GET", "getActiveProfile"))["active_profile"]

    async def set_active_profile(self, profile_id: int) -> None:
        await self._request("POST", "changeActiveProfile", json={"profiles_id": profile_id})

    async def get_my_entities(self, is_recursive: bool = False) -> list:
        return (
            await self._request(
                "GET", "getMyEntities", params={"is_recursive": int(is_recursive)}
            )
        )["myentities"]

    async def get_active_entities(self) -> dict:
        return (await self._request("GET", "getActiveEntities"))["active_entity"]

    async def set_active_entity(self, entity_id: int, is_recursive: bool = False) -> None:
        await self._request(
            "POST", "changeActiveEntities",
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

    async def get_all_items(self, itemtype: str, **kwargs: Any) -> list:
        """Return a single page of items (default range ``0-49``).

        Use :meth:`get_all_pages` to retrieve all items automatically.
        """
        params = _boolify_params(kwargs)
        if "range" not in params:
            params["range"] = f"0-{DEFAULT_PAGE_SIZE - 1}"
        return await self._request("GET", itemtype, params=params)

    async def get_all_pages(
        self,
        itemtype: str,
        page_size: int = DEFAULT_PAGE_SIZE,
        **kwargs: Any,
    ) -> list:
        """Fetch **all** items of *itemtype* by iterating pages automatically.

        Parameters
        ----------
        itemtype : str
        page_size : int
            Items per request (default: 50).
        **kwargs
            Extra GLPI parameters: ``sort``, ``order``, ``searchText``,
            ``is_deleted``, ``expand_dropdowns``, etc.

        Returns
        -------
        list
            All matching items as a flat list of dicts.
        """
        results: list = []
        async for page in self.iter_pages(itemtype, page_size=page_size, **kwargs):
            results.extend(page)
        return results

    async def iter_pages(
        self,
        itemtype: str,
        page_size: int = DEFAULT_PAGE_SIZE,
        **kwargs: Any,
    ) -> AsyncIterator[list]:
        """Yield one page of items at a time asynchronously.

        Parameters
        ----------
        itemtype : str
        page_size : int
        **kwargs
            Same as :meth:`get_all_pages`.

        Yields
        ------
        list
            One page per iteration.
        """
        params = _boolify_params(kwargs)
        start = 0
        fetched = 0

        while True:
            end = start + page_size - 1
            params["range"] = f"{start}-{end}"

            page_items, resp_headers = await self._request_with_headers(
                "GET", itemtype, params=params
            )

            if not page_items:
                return

            fetched += len(page_items)
            yield page_items

            total = _parse_content_range(resp_headers.get("Content-Range", ""))

            if total is not None and fetched >= total:
                return
            if len(page_items) < page_size:
                return

            start += page_size

    async def search(self, itemtype: str, **kwargs: Any) -> dict:
        params = _boolify_params(kwargs)
        return await self._request("GET", f"search/{itemtype}", params=params)

    async def create_item(self, itemtype: str, input_data: Any, **kwargs: Any) -> Any:
        payload: dict = {"input": input_data}
        payload.update(kwargs)
        return await self._request("POST", itemtype, json=payload)

    async def update_item(self, itemtype: str, input_data: Any, **kwargs: Any) -> list:
        payload: dict = {"input": input_data}
        payload.update(kwargs)
        return await self._request("PUT", itemtype, json=payload)

    async def delete_item(
        self,
        itemtype: str,
        input_data: Any,
        force_purge: bool = False,
        history: bool = True,
    ) -> list:
        payload: dict = {
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
    ) -> list:
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
        payload: dict = {"input": input_data}
        payload.update(kwargs)
        return await self._request(
            "POST", f"{itemtype}/{item_id}/{sub_itemtype}", json=payload
        )

    async def list_item_types(self) -> list:
        return await self._request("GET", "listItemtypes")
