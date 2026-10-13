"""
glpi_utils.oauth
~~~~~~~~~~~~~~~~

OAuth2 client for the GLPI **High-level API** (``/api.php``), GLPI 11 and 12.

GLPI 11 introduced a second, modern REST API alongside the legacy one
(HL API 2.x). GLPI 12 adds HL API 3.0 and keeps 2.3. Unversioned requests
get the server's newest version; pass ``api_version`` to pin one.

This module provides:

* :class:`GlpiOAuthClient`  – synchronous OAuth2 client (``requests``)
* :class:`AsyncGlpiOAuthClient` – asynchronous OAuth2 client (``aiohttp``)

Both expose the same CRUD operations as the legacy API clients but
authenticate via Bearer tokens instead of session tokens.

OAuth2 endpoints
----------------
* Token:  ``POST /api.php/token``
* API:    ``/api.php/{namespace}/{itemtype}`` or ``/api.php/v{X.Y}/...`` when pinned

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
``GLPI_OAUTH_USERNAME``, ``GLPI_OAUTH_PASSWORD``, ``GLPI_API_VERSION``
"""

from __future__ import annotations

import logging
import os
import re
import time
from typing import Any, AsyncIterator, Iterator, Optional

import requests
from requests import Session

from ._resource import AsyncItemProxy, ItemProxy
from .api import DEFAULT_PAGE_SIZE, _ITEMTYPE_MAP, _boolify_params, _parse_content_range

# ──────────────────────────────────────────────────────────────────────────────
# High-Level API route map (namespaced paths under /api.php), valid for
# HL API 2.3 (GLPI 11/12) and 3.0 (GLPI 12) unless noted.
# Keys match the aliases in _ITEMTYPE_MAP; values are the actual API paths.
# ──────────────────────────────────────────────────────────────────────────────
_HLAPI_ROUTE_MAP: dict = {
    # Assistance
    "Ticket":              "Assistance/Ticket",
    "Problem":             "Assistance/Problem",
    "Change":              "Assistance/Change",
    "RecurringTicket":     "Assistance/RecurringTicket",
    "RecurringChange":     "Assistance/RecurringChange",
    # Timeline sub-items also resolve here so get_item("ITILFollowup", ...)
    # keeps working; sub-item calls use _HLAPI_SUBITEM_MAP below.
    "ITILFollowup":        "Timeline/Followup",
    "ITILSolution":        "Timeline/Solution",
    "TicketTask":          "Timeline/Task",
    "TicketValidation":    "Timeline/Validation",
    # Assets
    "Computer":            "Assets/Computer",
    "Monitor":             "Assets/Monitor",
    "Printer":             "Assets/Printer",
    "NetworkEquipment":    "Assets/NetworkEquipment",
    "Software":            "Assets/Software",
    # /Assets/SoftwareLicense was deprecated in v2.4 and removed in v3.0;
    # Management/License serves the same itemtype on every version.
    "SoftwareLicense":     "Management/License",
    "Phone":               "Assets/Phone",
    "Peripheral":          "Assets/Peripheral",
    "Certificate":         "Assets/Certificate",
    "Appliance":           "Assets/Appliance",
    "Enclosure":           "Assets/Enclosure",
    "Rack":                "Assets/Rack",
    "PDU":                 "Assets/PDU",
    "Cable":               "Assets/Cable",
    "Unmanaged":           "Assets/Unmanaged",
    # Administration
    "User":                "Administration/User",
    "Group":               "Administration/Group",
    "Entity":              "Administration/Entity",
    "Profile":             "Administration/Profile",
    "UserCategory":        "Administration/UserCategory",
    "UserTitle":           "Administration/UserTitle",
    # Management
    "Contract":            "Management/Contract",
    "Supplier":            "Management/Supplier",
    "Contact":             "Management/Contact",
    "Document":            "Management/Document",
    "Budget":              "Management/Budget",
    "Domain":              "Management/Domain",
    "License":             "Management/License",
    "Cluster":             "Management/Cluster",
    # Dropdowns
    "ITILCategory":        "Dropdowns/ITILCategory",
    "Location":            "Dropdowns/Location",
    "State":               "Dropdowns/State",
    "Manufacturer":        "Dropdowns/Manufacturer",
    "RequestType":         "Dropdowns/RequestType",
    "SolutionType":        "Dropdowns/SolutionType",
    "TaskCategory":        "Dropdowns/TaskCategory",
    "Calendar":            "Dropdowns/Calendar",
    # Knowledgebase
    "KnowbaseItem":        "Knowledgebase/Article",
    # Removed in HL API v3.0 (GLPI 12 turned KB categories into articles)
    "KnowledgebaseCategory": "Knowledgebase/Category",
    # Project
    "Project":             "Project",
    "ProjectTask":         "Project/Task",
}

# Sub-items of an ITIL object (Ticket, Change, Problem) live under
# ``/Assistance/{itemtype}/{id}/Timeline/...``.
_HLAPI_SUBITEM_MAP: dict = {
    "ITILFollowup":        "Timeline/Followup",
    "ITILSolution":        "Timeline/Solution",
    "TicketTask":          "Timeline/Task",
    "ChangeTask":          "Timeline/Task",
    "ProblemTask":         "Timeline/Task",
    "TicketValidation":    "Timeline/Validation",
    "ChangeValidation":    "Timeline/Validation",
    "Document":            "Timeline/Document",
}


def _hl_route(itemtype: str) -> str:
    """Return the High-Level API path for the given GLPI itemtype."""
    return _HLAPI_ROUTE_MAP.get(itemtype, itemtype)


def _hl_subitem_route(itemtype: str) -> str:
    """Return the path segment of a sub-item under its parent resource."""
    return _HLAPI_SUBITEM_MAP.get(itemtype) or _hl_route(itemtype)


_API_VERSION_RE = re.compile(r"^v?(\d+(?:\.\d+)?)$", re.IGNORECASE)


def _normalize_api_version(version: Any) -> Optional[str]:
    """Turn ``"3"``, ``3.0``, ``"v2.3"`` into the URL prefix ``"v3"``/``"v3.0"``/``"v2.3"``.

    ``None`` or ``""`` means "no prefix": the server then answers with its
    newest HL API version (2.3 on GLPI 11, 3.0 on GLPI 12).
    """
    if version is None or version == "":
        return None
    match = _API_VERSION_RE.match(str(version).strip())
    if not match:
        raise ValueError(
            f"Invalid High-Level API version {version!r}. Use e.g. '2', '2.3' or '3.0'."
        )
    number = match.group(1)
    if number.split(".")[0] == "1":
        raise ValueError(
            "API version 1 is the legacy REST API; use GlpiAPI / AsyncGlpiAPI for it."
        )
    return f"v{number}"


def _page_params(params: dict, page_size: int) -> dict:
    """Return a copy of *params* with HL API ``start``/``limit`` pagination.

    The HL API ignores the legacy ``range`` parameter and falls back to its
    default limit (100), so a ``range="a-b"`` kwarg is translated here.
    """
    out = dict(params)
    raw_range = out.pop("range", None)
    if raw_range is not None and "start" not in out and "limit" not in out:
        first, last = (int(x) for x in str(raw_range).split("-", 1))
        out["start"], out["limit"] = first, last - first + 1
    out.setdefault("start", 0)
    out.setdefault("limit", page_size)
    return out
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
    """Synchronous OAuth2 client for the GLPI 11/12 High-level API (``/api.php``).

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
    api_version : str or None
        High-Level API version to pin, e.g. ``"2.3"`` or ``"3.0"``
        (``/api.php/v2.3``, ``/api.php/v3.0``). ``None`` sends unversioned
        requests, which the server answers with its newest version: 2.3 on
        GLPI 11, **3.0 on GLPI 12**. Pin it in production so a GLPI upgrade
        does not change response schemas under you.
        Falls back to ``GLPI_API_VERSION``.
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
        api_version: Optional[str] = None,
    ) -> None:
        self._url = (url or os.environ.get("GLPI_URL", "")).rstrip("/")
        if not self._url:
            raise ValueError("A GLPI URL is required. Pass url= or set GLPI_URL.")

        self._client_id = client_id or os.environ.get("GLPI_OAUTH_CLIENT_ID")
        self._client_secret = client_secret or os.environ.get("GLPI_OAUTH_CLIENT_SECRET")
        self._username = username or os.environ.get("GLPI_OAUTH_USERNAME")
        self._password = password or os.environ.get("GLPI_OAUTH_PASSWORD")
        self._api_version = _normalize_api_version(
            api_version or os.environ.get("GLPI_API_VERSION")
        )
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
        if self._api_version:
            return f"{self._url}/api.php/{self._api_version}"
        return f"{self._url}/api.php"

    @property
    def api_version(self) -> Optional[str]:
        """Pinned HL API version prefix (e.g. ``"v3.0"``), or ``None``."""
        return self._api_version

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
        """Fetch and cache the GLPI server version.

        Reads ``GET /Setup/Config/core/version`` (needs read access to the
        general setup); the API root does not expose the GLPI version.
        """
        data = self._request("GET", "Setup/Config/core/version")
        raw = data.get("value") if isinstance(data, dict) else None
        self._version = GLPIVersion(raw or "0.0.0")
        return self._version

    def get_api_versions(self) -> list:
        """Return the API versions the server offers (``GET /api.php/``).

        Each entry has ``api_version`` (major), ``version`` and ``endpoint``.
        GLPI 11 lists 1.0.0 and 2.0.0-2.3.0; GLPI 12 lists 1.0.0, 2.3.0 and 3.0.0.
        """
        self._ensure_token()
        try:
            resp = self._http.get(
                f"{self._url}/api.php/",
                headers=self._auth_headers(),
                verify=self._verify_ssl,
                timeout=self._timeout,
            )
        except requests.exceptions.RequestException as exc:
            raise GlpiConnectionError(f"Cannot reach GLPI at {self._url}: {exc}") from exc
        body = resp.json()
        _raise_for_oauth_error(resp.status_code, body, resp.text)
        return list(body.get("api_versions", []))

    # ------------------------------------------------------------------
    # Item CRUD
    # ------------------------------------------------------------------

    def get_item(self, itemtype: str, item_id: int, **kwargs: Any) -> dict:
        """Return a single item by ID."""
        params = _boolify_params(kwargs)
        return self._request("GET", f"{_hl_route(itemtype)}/{item_id}", params=params)

    def get_all_items(self, itemtype: str, **kwargs: Any) -> list:
        """Return a single page of items (``start``/``limit``; ``range="a-b"`` is translated)."""
        params = _page_params(_boolify_params(kwargs), DEFAULT_PAGE_SIZE)
        return self._request("GET", _hl_route(itemtype), params=params)

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
        base = _boolify_params(kwargs)
        base.pop("range", None)
        start = 0
        fetched = 0

        while True:
            params = {**base, "start": start, "limit": page_size}
            page_items, resp_headers = self._request_with_headers("GET", _hl_route(itemtype), params=params)

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

    def search(self, itemtype: str, filter: Optional[str] = None, **kwargs: Any) -> list:
        """Search a collection with an RSQL *filter*, e.g. ``"name=like=*srv*;status.id==1"``.

        Extra kwargs (``start``, ``limit``, ``sort``) are passed as query parameters.
        """
        params = _boolify_params(kwargs)
        if filter:
            params["filter"] = filter
        return self._request("GET", _hl_route(itemtype), params=params)

    def create_item(self, itemtype: str, input_data: Any, **kwargs: Any) -> Any:
        """Create one or several items."""
        # HL API v2: POST body is the object directly, no {input:} wrapper
        if isinstance(input_data, dict):
            body = dict(input_data)
            body.update(kwargs)
        else:
            body = input_data
        return self._request("POST", _hl_route(itemtype), json=body)

    def update_item(self, itemtype: str, input_data: Any, **kwargs: Any) -> list:
        """Update one or several items."""
        # HL API v2: PUT /{route}/{id} with fields in body (no wrapper)
        if isinstance(input_data, dict) and "id" in input_data:
            item_id = input_data["id"]
            body = {k: v for k, v in input_data.items() if k != "id"}
            body.update(kwargs)
            return self._request("PATCH", f"{_hl_route(itemtype)}/{item_id}", json=body)
        # Fallback for list input (bulk) - not natively supported in HL API
        payload: dict = {"input": input_data}
        payload.update(kwargs)
        return self._request("PATCH", _hl_route(itemtype), json=payload)

    def delete_item(
        self,
        itemtype: str,
        input_data: Any,
        force_purge: bool = False,
        history: bool = True,
    ) -> list:
        """Delete one or several items."""
        # HL API v2: DELETE /{route}/{id}
        if isinstance(input_data, dict) and "id" in input_data:
            item_id = input_data["id"]
            return self._request("DELETE", f"{_hl_route(itemtype)}/{item_id}")
        payload: dict = {"input": input_data}
        return self._request("DELETE", _hl_route(itemtype), json=payload)

    def get_sub_items(
        self, itemtype: str, item_id: int, sub_itemtype: str, **kwargs: Any
    ) -> list:
        """Return sub-items of a parent item."""
        params = _boolify_params(kwargs)
        return self._request("GET", f"{_hl_route(itemtype)}/{item_id}/{_hl_subitem_route(sub_itemtype)}", params=params)

    def add_sub_item(
        self, itemtype: str, item_id: int, sub_itemtype: str, input_data: dict, **kwargs: Any
    ) -> dict:
        """Add a sub-item to a parent resource."""
        # HL API v2: body is the object directly, no {"input":...} wrapper
        body = dict(input_data)
        body.update(kwargs)
        return self._request("POST", f"{_hl_route(itemtype)}/{item_id}/{_hl_subitem_route(sub_itemtype)}", json=body)


# ──────────────────────────────────────────────────────────────────────────────
# Asynchronous client
# ──────────────────────────────────────────────────────────────────────────────


class AsyncGlpiOAuthClient:
    """Asynchronous OAuth2 client for the GLPI 11/12 High-level API (``/api.php``).

    Parameters
    ----------
    url : str or None
    client_id : str or None
    client_secret : str or None
    verify_ssl : bool
    timeout : int
    api_version : str or None
        See :class:`GlpiOAuthClient`.

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
        api_version: Optional[str] = None,
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
        self._api_version = _normalize_api_version(
            api_version or os.environ.get("GLPI_API_VERSION")
        )
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
        if self._api_version:
            return f"{self._url}/api.php/{self._api_version}"
        return f"{self._url}/api.php"

    @property
    def api_version(self) -> Optional[str]:
        """Pinned HL API version prefix (e.g. ``"v3.0"``), or ``None``."""
        return self._api_version

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
        return await self._request("GET", f"{_hl_route(itemtype)}/{item_id}", params=_boolify_params(kwargs))

    async def get_all_items(self, itemtype: str, **kwargs: Any) -> list:
        params = _page_params(_boolify_params(kwargs), DEFAULT_PAGE_SIZE)
        return await self._request("GET", _hl_route(itemtype), params=params)

    async def get_all_pages(self, itemtype: str, page_size: int = DEFAULT_PAGE_SIZE, **kwargs: Any) -> list:
        results: list = []
        async for page in self.iter_pages(itemtype, page_size=page_size, **kwargs):
            results.extend(page)
        return results

    async def iter_pages(
        self, itemtype: str, page_size: int = DEFAULT_PAGE_SIZE, **kwargs: Any
    ) -> AsyncIterator[list]:
        base = _boolify_params(kwargs)
        base.pop("range", None)
        start = 0
        fetched = 0
        while True:
            params = {**base, "start": start, "limit": page_size}
            page_items, resp_headers = await self._request_with_headers("GET", _hl_route(itemtype), params=params)
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

    async def search(self, itemtype: str, filter: Optional[str] = None, **kwargs: Any) -> list:
        params = _boolify_params(kwargs)
        if filter:
            params["filter"] = filter
        return await self._request("GET", _hl_route(itemtype), params=params)

    async def create_item(self, itemtype: str, input_data: Any, **kwargs: Any) -> Any:
        if isinstance(input_data, dict):
            body = dict(input_data)
            body.update(kwargs)
        else:
            body = input_data
        return await self._request("POST", _hl_route(itemtype), json=body)

    async def update_item(self, itemtype: str, input_data: Any, **kwargs: Any) -> list:
        if isinstance(input_data, dict) and "id" in input_data:
            item_id = input_data["id"]
            body = {k: v for k, v in input_data.items() if k != "id"}
            body.update(kwargs)
            return await self._request("PATCH", f"{_hl_route(itemtype)}/{item_id}", json=body)
        payload: dict = {"input": input_data}
        payload.update(kwargs)
        return await self._request("PATCH", _hl_route(itemtype), json=payload)

    async def delete_item(self, itemtype: str, input_data: Any, force_purge: bool = False, history: bool = True) -> list:
        if isinstance(input_data, dict) and "id" in input_data:
            item_id = input_data["id"]
            return await self._request("DELETE", f"{_hl_route(itemtype)}/{item_id}")
        return await self._request("DELETE", _hl_route(itemtype), json={"input": input_data})

    async def get_sub_items(self, itemtype: str, item_id: int, sub_itemtype: str, **kwargs: Any) -> list:
        return await self._request("GET", f"{_hl_route(itemtype)}/{item_id}/{_hl_subitem_route(sub_itemtype)}", params=_boolify_params(kwargs))

    async def add_sub_item(self, itemtype: str, item_id: int, sub_itemtype: str, input_data: dict, **kwargs: Any) -> dict:
        body = dict(input_data)
        body.update(kwargs)
        return await self._request("POST", f"{_hl_route(itemtype)}/{item_id}/{_hl_subitem_route(sub_itemtype)}", json=body)

    @property
    def version(self) -> Optional[GLPIVersion]:
        return self._version

    async def get_version(self) -> GLPIVersion:
        """Fetch and cache the GLPI server version (``GET /Setup/Config/core/version``)."""
        data = await self._request("GET", "Setup/Config/core/version")
        raw = data.get("value") if isinstance(data, dict) else None
        self._version = GLPIVersion(raw or "0.0.0")
        return self._version

    async def get_api_versions(self) -> list:
        """Return the API versions the server offers (``GET /api.php/``)."""
        import aiohttp

        await self._ensure_token()
        http = self._get_http()
        try:
            async with http.get(
                f"{self._url}/api.php/",
                headers=self._auth_headers(),
                timeout=aiohttp.ClientTimeout(total=self._timeout),
            ) as resp:
                body = await resp.json(content_type=None)
                _raise_for_oauth_error(resp.status, body, "")
                return list(body.get("api_versions", []))
        except aiohttp.ClientConnectorError as exc:
            raise GlpiConnectionError(f"Cannot reach GLPI at {self._url}: {exc}") from exc
