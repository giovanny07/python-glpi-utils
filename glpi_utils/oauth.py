"""
glpi_utils.oauth
~~~~~~~~~~~~~~~~

OAuth2 client for the GLPI 11 **High-level API** (``/api.php``).

GLPI 11 introduced a second, modern REST API alongside the legacy one.
It uses OAuth2 *Client Credentials* flow for machine-to-machine access
and *Authorization Code* flow for user-delegated access.

This module provides:

* :class:`GlpiOAuthClient`  – synchronous OAuth2 client (``requests``)
* :class:`AsyncGlpiOAuthClient` – asynchronous OAuth2 client (``aiohttp``)

Both expose the same CRUD operations as the legacy API clients but
authenticate via Bearer tokens instead of session tokens.

OAuth2 endpoints (GLPI 11)
--------------------------
* Token:  ``POST /api.php/token``
* API:    ``/api.php/{itemtype}``

Supported grant types
---------------------
* ``client_credentials``  – Service accounts, automation scripts
* ``password``            – Username + password (Resource Owner Password)

Usage (sync)::

    from glpi_utils.oauth import GlpiOAuthClient

    api = GlpiOAuthClient(
        url="https://glpi.example.com",
        client_id="my-app",
        client_secret="secret",
    )
    api.authenticate()                        # client_credentials grant
    tickets = api.ticket.get_all_pages()
    api.close()

Usage (async)::

    from glpi_utils.oauth import AsyncGlpiOAuthClient

    async with AsyncGlpiOAuthClient(
        url="https://glpi.example.com",
        client_id="my-app",
        client_secret="secret",
    ) as api:
        await api.authenticate()
        tickets = await api.ticket.get_all_pages()

Environment variables
---------------------
``GLPI_URL``, ``GLPI_OAUTH_CLIENT_ID``, ``GLPI_OAUTH_CLIENT_SECRET``,
``GLPI_OAUTH_USERNAME``, ``GLPI_OAUTH_PASSWORD``
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, AsyncIterator, Iterator, Optional

import requests
from requests import Session

from ._resource import AsyncItemProxy, ItemProxy
from .api import DEFAULT_PAGE_SIZE, _ITEMTYPE_MAP, _boolify_params, _parse_content_range
from .exceptions import GlpiAPIError, GlpiAuthError, GlpiConnectionError, GlpiNotFoundError, GlpiPermissionError
from .logger import EmptyHandler, SensitiveFilter
from .version import GLPIVersion

log = logging.getLogger(__name__)
log.addHandler(EmptyHandler())
log.addFilter(SensitiveFilter())

# ──────────────────────────────────────────────────────────────────────────────
# Token store
# ──────────────────────────────────────────────────────────────────────────────

#: Seconds before actual expiry at which the token is considered stale.
_TOKEN_REFRESH_BUFFER = 30


class _TokenStore:
    """Holds an OAuth2 Bearer token and tracks its expiry."""

    def __init__(self) -> None:
        self.access_token: Optional[str] = None
        self._expires_at: float = 0.0

    def store(self, token: str, expires_in: int) -> None:
        self.access_token = token
        self._expires_at = time.monotonic() + expires_in - _TOKEN_REFRESH_BUFFER

    def is_valid(self) -> bool:
        return bool(self.access_token) and time.monotonic() < self._expires_at

    def clear(self) -> None:
        self.access_token = None
        self._expires_at = 0.0


# ──────────────────────────────────────────────────────────────────────────────
# Shared response helper
# ──────────────────────────────────────────────────────────────────────────────


def _raise_for_oauth_error(status: int, body: Any, text: str = "") -> None:
    """Raise an appropriate exception based on HTTP status and body."""
    if status in (200, 201, 206):
        return

    if isinstance(body, dict):
        error_code = body.get("error", str(status))
        message = body.get("message") or body.get("error_description", text)
    elif isinstance(body, list) and len(body) >= 2:
        error_code, message = str(body[0]), str(body[1])
    else:
        error_code, message = str(status), text

    if status == 401:
        raise GlpiAuthError(message, status_code=status, error_code=error_code)
    if status == 403:
        raise GlpiPermissionError(message, status_code=status, error_code=error_code)
    if status == 404:
        raise GlpiNotFoundError(message, status_code=status, error_code=error_code)

    raise GlpiAPIError(message, status_code=status, error_code=error_code)


# ──────────────────────────────────────────────────────────────────────────────
# Synchronous client
# ──────────────────────────────────────────────────────────────────────────────


class GlpiOAuthClient:
    """Synchronous OAuth2 client for the GLPI 11 High-level API (``/api.php``).

    Parameters
    ----------
    url : str or None
        Base URL, e.g. ``"https://glpi.example.com"``.
        Falls back to ``GLPI_URL``.
    client_id : str or None
        OAuth2 client ID. Falls back to ``GLPI_OAUTH_CLIENT_ID``.
    client_secret : str or None
        OAuth2 client secret. Falls back to ``GLPI_OAUTH_CLIENT_SECRET``.
    verify_ssl : bool
        Verify TLS certificates (default: ``True``).
    timeout : int
        HTTP timeout in seconds (default: ``30``).
    """

    def __init__(
        self,
        url: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        verify_ssl: bool = True,
        timeout: int = 30,
    ) -> None:
        self._url = (url or os.environ.get("GLPI_URL", "")).rstrip("/")
        if not self._url:
            raise ValueError("A GLPI URL is required. Pass url= or set GLPI_URL.")

        self._client_id = client_id or os.environ.get("GLPI_OAUTH_CLIENT_ID")
        self._client_secret = client_secret or os.environ.get("GLPI_OAUTH_CLIENT_SECRET")
        self._username = username or os.environ.get("GLPI_OAUTH_USERNAME")
        self._password = password or os.environ.get("GLPI_OAUTH_PASSWORD")
        self._verify_ssl = verify_ssl
        self._timeout = timeout

        self._token = _TokenStore()
        self._http = Session()
        self._version: Optional[GLPIVersion] = None
        self._proxies: dict = {}

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "GlpiOAuthClient":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def close(self) -> None:
        """Close the underlying HTTP session."""
        self._http.close()
        self._token.clear()

    # ------------------------------------------------------------------
    # Fluent accessors
    # ------------------------------------------------------------------

    def __getattr__(self, name: str) -> ItemProxy:
        # Use object.__getattribute__ to avoid recursive __getattr__ calls
        # when _proxies itself hasn't been set yet.
        try:
            proxies = object.__getattribute__(self, "_proxies")
        except AttributeError:
            proxies = {}
            object.__setattr__(self, "_proxies", proxies)

        lower = name.lower()
        if lower in _ITEMTYPE_MAP:
            if lower not in proxies:
                proxies[lower] = ItemProxy(self, _ITEMTYPE_MAP[lower])  # type: ignore[arg-type]
            return proxies[lower]
        raise AttributeError(
            f"{self.__class__.__name__!r} has no attribute {name!r}. "
            "Use api.item('YourItemtype') for non-standard item types."
        )

    def item(self, itemtype: str) -> ItemProxy:
        """Return an :class:`~glpi_utils._resource.ItemProxy` for any itemtype."""
        try:
            proxies = object.__getattribute__(self, "_proxies")
        except AttributeError:
            proxies = {}
            object.__setattr__(self, "_proxies", proxies)
        if itemtype not in proxies:
            proxies[itemtype] = ItemProxy(self, itemtype)  # type: ignore[arg-type]
        return proxies[itemtype]

    # ------------------------------------------------------------------
    # URL helpers
    # ------------------------------------------------------------------

    @property
    def _token_url(self) -> str:
        return f"{self._url}/api.php/token"

    @property
    def _api_url(self) -> str:
        return f"{self._url}/api.php"

    def _auth_headers(self, with_content_type: bool = False) -> dict:
        token = self._token.access_token
        if not token:
            raise GlpiAuthError("Not authenticated. Call authenticate() first.")
        headers = {"Authorization": f"Bearer {token}"}
        if with_content_type:
            headers["Content-Type"] = "application/json"
        return headers

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def authenticate(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> None:
        """Obtain an OAuth2 Bearer token.

        Parameters
        ----------
        username : str or None
            If provided (along with *password*), uses the ``password`` grant.
            Otherwise uses ``client_credentials``.
            Falls back to constructor username or ``GLPI_OAUTH_USERNAME``.
        password : str or None
        """
        if not self._client_id:
            raise GlpiAuthError(
                "client_id is required. Pass it or set GLPI_OAUTH_CLIENT_ID."
            )

        username = username or self._username
        password = password or self._password

        if username and password:
            payload = {
                "grant_type": "password",
                "client_id": self._client_id,
                "client_secret": self._client_secret or "",
                "username": username,
                "password": password,
                "scope": "api",
            }
            grant = "password"
        else:
            if not self._client_secret:
                raise GlpiAuthError(
                    "client_secret is required for client_credentials grant. "
                    "Set GLPI_OAUTH_CLIENT_SECRET or pass client_secret=."
                )
            payload = {
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "scope": "api",
            }
            grant = "client_credentials"

        log.debug("OAuth2 token request (grant=%s)", grant)

        try:
            resp = self._http.post(
                self._token_url,
                data=payload,
                verify=self._verify_ssl,
                timeout=self._timeout,
            )
        except requests.exceptions.ConnectionError as exc:
            raise GlpiConnectionError(f"Cannot reach GLPI at {self._url}: {exc}") from exc
        except requests.exceptions.Timeout as exc:
            raise GlpiConnectionError(f"Token request timed out: {exc}") from exc

        body = resp.json()
        if resp.status_code not in (200, 201) or "access_token" not in body:
            error = body.get("error", str(resp.status_code))
            desc  = body.get("error_description", resp.text)
            raise GlpiAuthError(
                f"OAuth2 token request failed ({error}): {desc}",
                status_code=resp.status_code,
                error_code=error,
            )

        self._token.store(body["access_token"], int(body.get("expires_in", 3600)))
        log.debug("OAuth2 token obtained (expires_in=%s).", body.get("expires_in"))

    def _ensure_token(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> None:
        """Re-authenticate automatically if the token has expired."""
        if not self._token.is_valid():
            log.debug("Token expired or missing — re-authenticating.")
            self.authenticate(username=username, password=password)

    # ------------------------------------------------------------------
    # Internal HTTP helpers
    # ------------------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict] = None,
        json: Any = None,
    ) -> Any:
        body, _ = self._request_with_headers(method, path, params=params, json=json)
        return body

    def _request_with_headers(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict] = None,
        json: Any = None,
    ) -> tuple:
        self._ensure_token()
        url = f"{self._api_url}/{path.lstrip('/')}"
        log.debug("%s %s params=%s", method.upper(), url, params)

        try:
            resp = self._http.request(
                method, url,
                headers=self._auth_headers(with_content_type=json is not None),
                params=params,
                json=json,
                verify=self._verify_ssl,
                timeout=self._timeout,
            )
        except requests.exceptions.ConnectionError as exc:
            raise GlpiConnectionError(f"Cannot reach GLPI at {self._url}: {exc}") from exc
        except requests.exceptions.Timeout as exc:
            raise GlpiConnectionError(f"Request timed out: {exc}") from exc

        log.debug("Response %s from %s", resp.status_code, url)

        if resp.status_code == 204 or not resp.content:
            return None, dict(resp.headers)

        try:
            body = resp.json()
        except Exception:
            body = resp.text

        _raise_for_oauth_error(resp.status_code, body, resp.text)
        return body, dict(resp.headers)

    # ------------------------------------------------------------------
    # Version
    # ------------------------------------------------------------------

    @property
    def version(self) -> Optional[GLPIVersion]:
        """Return cached server version."""
        return self._version

    def get_version(self) -> GLPIVersion:
        """Fetch and cache the GLPI server version."""
        data = self._request("GET", "")
        # High-level API root returns server info
        raw = data.get("glpi_version") if isinstance(data, dict) else None
        self._version = GLPIVersion(raw or "0.0.0")
        return self._version

    # ------------------------------------------------------------------
    # Item CRUD
    # ------------------------------------------------------------------

    def get_item(self, itemtype: str, item_id: int, **kwargs: Any) -> dict:
        """Return a single item by ID."""
        params = _boolify_params(kwargs)
        return self._request("GET", f"{itemtype}/{item_id}", params=params)

    def get_all_items(self, itemtype: str, **kwargs: Any) -> list:
        """Return a single page of items."""
        params = _boolify_params(kwargs)
        if "range" not in params:
            params["range"] = f"0-{DEFAULT_PAGE_SIZE - 1}"
        return self._request("GET", itemtype, params=params)

    def get_all_pages(
        self,
        itemtype: str,
        page_size: int = DEFAULT_PAGE_SIZE,
        **kwargs: Any,
    ) -> list:
        """Fetch all items across all pages automatically."""
        return list(item for page in self.iter_pages(itemtype, page_size=page_size, **kwargs) for item in page)

    def iter_pages(
        self,
        itemtype: str,
        page_size: int = DEFAULT_PAGE_SIZE,
        **kwargs: Any,
    ) -> Iterator[list]:
        """Yield one page of items at a time."""
        params = _boolify_params(kwargs)
        start = 0
        fetched = 0

        while True:
            end = start + page_size - 1
            params["range"] = f"{start}-{end}"

            page_items, resp_headers = self._request_with_headers("GET", itemtype, params=params)

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

    def search(self, itemtype: str, **kwargs: Any) -> dict:
        """Run the GLPI search engine."""
        params = _boolify_params(kwargs)
        return self._request("GET", f"search/{itemtype}", params=params)

    def create_item(self, itemtype: str, input_data: Any, **kwargs: Any) -> Any:
        """Create one or several items."""
        payload: dict = {"input": input_data}
        payload.update(kwargs)
        return self._request("POST", itemtype, json=payload)

    def update_item(self, itemtype: str, input_data: Any, **kwargs: Any) -> list:
        """Update one or several items."""
        payload: dict = {"input": input_data}
        payload.update(kwargs)
        return self._request("PUT", itemtype, json=payload)

    def delete_item(
        self,
        itemtype: str,
        input_data: Any,
        force_purge: bool = False,
        history: bool = True,
    ) -> list:
        """Delete one or several items."""
        payload: dict = {
            "input": input_data,
            "force_purge": int(force_purge),
            "history": int(history),
        }
        return self._request("DELETE", itemtype, json=payload)

    def get_sub_items(
        self, itemtype: str, item_id: int, sub_itemtype: str, **kwargs: Any
    ) -> list:
        """Return sub-items of a parent item."""
        params = _boolify_params(kwargs)
        return self._request("GET", f"{itemtype}/{item_id}/{sub_itemtype}", params=params)

    def add_sub_item(
        self, itemtype: str, item_id: int, sub_itemtype: str, input_data: dict, **kwargs: Any
    ) -> dict:
        """Add a sub-item to a parent resource."""
        payload: dict = {"input": input_data}
        payload.update(kwargs)
        return self._request("POST", f"{itemtype}/{item_id}/{sub_itemtype}", json=payload)


# ──────────────────────────────────────────────────────────────────────────────
# Asynchronous client
# ──────────────────────────────────────────────────────────────────────────────


class AsyncGlpiOAuthClient:
    """Asynchronous OAuth2 client for the GLPI 11 High-level API (``/api.php``).

    Parameters
    ----------
    url : str or None
    client_id : str or None
    client_secret : str or None
    verify_ssl : bool
    timeout : int

    Examples
    --------
    ::

        async with AsyncGlpiOAuthClient(
            url="https://glpi.example.com",
            client_id="my-app",
            client_secret="secret",
        ) as api:
            await api.authenticate()
            tickets = await api.ticket.get_all_pages()
    """

    def __init__(
        self,
        url: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        verify_ssl: bool = True,
        timeout: int = 30,
    ) -> None:
        try:
            import aiohttp  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "AsyncGlpiOAuthClient requires 'aiohttp'. "
                "Install it with: pip install glpi-utils[async]"
            ) from exc

        self._url = (url or os.environ.get("GLPI_URL", "")).rstrip("/")
        if not self._url:
            raise ValueError("A GLPI URL is required. Pass url= or set GLPI_URL.")

        self._client_id = client_id or os.environ.get("GLPI_OAUTH_CLIENT_ID")
        self._client_secret = client_secret or os.environ.get("GLPI_OAUTH_CLIENT_SECRET")
        self._username = username or os.environ.get("GLPI_OAUTH_USERNAME")
        self._password = password or os.environ.get("GLPI_OAUTH_PASSWORD")
        self._verify_ssl = verify_ssl
        self._timeout = timeout

        self._token = _TokenStore()
        self._http: Any = None
        self._version: Optional[GLPIVersion] = None
        self._proxies: dict = {}

    async def __aenter__(self) -> "AsyncGlpiOAuthClient":
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    async def close(self) -> None:
        """Close the underlying aiohttp session."""
        if self._http and not self._http.closed:
            await self._http.close()
        self._token.clear()

    # ------------------------------------------------------------------
    # Fluent accessors
    # ------------------------------------------------------------------

    def __getattr__(self, name: str) -> AsyncItemProxy:
        try:
            proxies = object.__getattribute__(self, "_proxies")
        except AttributeError:
            proxies = {}
            object.__setattr__(self, "_proxies", proxies)

        lower = name.lower()
        if lower in _ITEMTYPE_MAP:
            if lower not in proxies:
                proxies[lower] = AsyncItemProxy(self, _ITEMTYPE_MAP[lower])  # type: ignore[arg-type]
            return proxies[lower]
        raise AttributeError(
            f"{self.__class__.__name__!r} has no attribute {name!r}. "
            "Use api.item('YourItemtype') for non-standard item types."
        )

    def item(self, itemtype: str) -> AsyncItemProxy:
        try:
            proxies = object.__getattribute__(self, "_proxies")
        except AttributeError:
            proxies = {}
            object.__setattr__(self, "_proxies", proxies)
        if itemtype not in proxies:
            proxies[itemtype] = AsyncItemProxy(self, itemtype)  # type: ignore[arg-type]
        return proxies[itemtype]

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    @property
    def _token_url(self) -> str:
        return f"{self._url}/api.php/token"

    @property
    def _api_url(self) -> str:
        return f"{self._url}/api.php"

    def _get_http(self) -> Any:
        import aiohttp

        if self._http is None or self._http.closed:
            connector = aiohttp.TCPConnector(ssl=self._verify_ssl)
            self._http = aiohttp.ClientSession(connector=connector)
        return self._http

    def _auth_headers(self, with_content_type: bool = False) -> dict:
        if not self._token.access_token:
            raise GlpiAuthError("Not authenticated. Call await authenticate() first.")
        headers = {"Authorization": f"Bearer {self._token.access_token}"}
        if with_content_type:
            headers["Content-Type"] = "application/json"
        return headers

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    async def authenticate(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> None:
        """Obtain an OAuth2 Bearer token asynchronously."""
        import aiohttp

        if not self._client_id:
            raise GlpiAuthError("client_id is required. Set GLPI_OAUTH_CLIENT_ID.")

        username = username or self._username
        password = password or self._password

        if username and password:
            payload = {
                "grant_type": "password",
                "client_id": self._client_id,
                "client_secret": self._client_secret or "",
                "username": username,
                "password": password,
                "scope": "api",
            }
            grant = "password"
        else:
            if not self._client_secret:
                raise GlpiAuthError(
                    "client_secret is required for client_credentials grant."
                )
            payload = {
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "scope": "api",
            }
            grant = "client_credentials"

        log.debug("Async OAuth2 token request (grant=%s)", grant)

        http = self._get_http()
        timeout = aiohttp.ClientTimeout(total=self._timeout)

        try:
            async with http.post(
                self._token_url, data=payload, timeout=timeout
            ) as resp:
                body = await resp.json(content_type=None)
                if resp.status not in (200, 201) or "access_token" not in body:
                    error = body.get("error", str(resp.status))
                    desc  = body.get("error_description", "")
                    raise GlpiAuthError(
                        f"OAuth2 token request failed ({error}): {desc}",
                        status_code=resp.status,
                        error_code=error,
                    )
                self._token.store(body["access_token"], int(body.get("expires_in", 3600)))
                log.debug("Async OAuth2 token obtained.")
        except aiohttp.ClientConnectorError as exc:
            raise GlpiConnectionError(f"Cannot reach GLPI at {self._url}: {exc}") from exc

    async def _ensure_token(self) -> None:
        if not self._token.is_valid():
            await self.authenticate()

    # ------------------------------------------------------------------
    # Internal HTTP helpers
    # ------------------------------------------------------------------

    async def _request(self, method: str, path: str, *, params: Optional[dict] = None, json: Any = None) -> Any:
        body, _ = await self._request_with_headers(method, path, params=params, json=json)
        return body

    async def _request_with_headers(
        self, method: str, path: str, *, params: Optional[dict] = None, json: Any = None
    ) -> tuple:
        import aiohttp

        await self._ensure_token()
        url = f"{self._api_url}/{path.lstrip('/')}"
        log.debug("ASYNC %s %s params=%s", method.upper(), url, params)

        http = self._get_http()
        timeout = aiohttp.ClientTimeout(total=self._timeout)

        try:
            async with http.request(
                method, url,
                headers=self._auth_headers(with_content_type=json is not None),
                params=params,
                json=json,
                timeout=timeout,
            ) as resp:
                resp_headers = dict(resp.headers)
                if resp.status == 204 or resp.content_length == 0:
                    return None, resp_headers
                body = await resp.json(content_type=None)
                _raise_for_oauth_error(resp.status, body, "")
                return body, resp_headers
        except aiohttp.ClientConnectorError as exc:
            raise GlpiConnectionError(f"Cannot reach GLPI at {self._url}: {exc}") from exc
        except aiohttp.ServerTimeoutError as exc:
            raise GlpiConnectionError(f"Request timed out: {exc}") from exc

    # ------------------------------------------------------------------
    # CRUD + pagination  (mirrors GlpiOAuthClient)
    # ------------------------------------------------------------------

    async def get_item(self, itemtype: str, item_id: int, **kwargs: Any) -> dict:
        return await self._request("GET", f"{itemtype}/{item_id}", params=_boolify_params(kwargs))

    async def get_all_items(self, itemtype: str, **kwargs: Any) -> list:
        params = _boolify_params(kwargs)
        if "range" not in params:
            params["range"] = f"0-{DEFAULT_PAGE_SIZE - 1}"
        return await self._request("GET", itemtype, params=params)

    async def get_all_pages(self, itemtype: str, page_size: int = DEFAULT_PAGE_SIZE, **kwargs: Any) -> list:
        results: list = []
        async for page in self.iter_pages(itemtype, page_size=page_size, **kwargs):
            results.extend(page)
        return results

    async def iter_pages(
        self, itemtype: str, page_size: int = DEFAULT_PAGE_SIZE, **kwargs: Any
    ) -> AsyncIterator[list]:
        params = _boolify_params(kwargs)
        start = 0
        fetched = 0
        while True:
            end = start + page_size - 1
            params["range"] = f"{start}-{end}"
            page_items, resp_headers = await self._request_with_headers("GET", itemtype, params=params)
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
        return await self._request("GET", f"search/{itemtype}", params=_boolify_params(kwargs))

    async def create_item(self, itemtype: str, input_data: Any, **kwargs: Any) -> Any:
        payload: dict = {"input": input_data}
        payload.update(kwargs)
        return await self._request("POST", itemtype, json=payload)

    async def update_item(self, itemtype: str, input_data: Any, **kwargs: Any) -> list:
        payload: dict = {"input": input_data}
        payload.update(kwargs)
        return await self._request("PUT", itemtype, json=payload)

    async def delete_item(self, itemtype: str, input_data: Any, force_purge: bool = False, history: bool = True) -> list:
        return await self._request("DELETE", itemtype, json={
            "input": input_data, "force_purge": int(force_purge), "history": int(history),
        })

    async def get_sub_items(self, itemtype: str, item_id: int, sub_itemtype: str, **kwargs: Any) -> list:
        return await self._request("GET", f"{itemtype}/{item_id}/{sub_itemtype}", params=_boolify_params(kwargs))

    async def add_sub_item(self, itemtype: str, item_id: int, sub_itemtype: str, input_data: dict, **kwargs: Any) -> dict:
        payload: dict = {"input": input_data}
        payload.update(kwargs)
        return await self._request("POST", f"{itemtype}/{item_id}/{sub_itemtype}", json=payload)

    @property
    def version(self) -> Optional[GLPIVersion]:
        return self._version
