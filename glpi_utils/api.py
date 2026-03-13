"""
glpi_utils.api
~~~~~~~~~~~~~~

Synchronous GLPI REST API client (legacy ``/apirest.php``).

GLPI 11 ships with two parallel APIs:

* **Legacy API** (``/apirest.php``) – session-token based, stable.
* **High-level API** (``/api.php``) – OAuth2-based, introduced in GLPI 11.
  See :mod:`glpi_utils.aio_oauth` for the OAuth2 client.
"""

from __future__ import annotations

import logging
import os
from base64 import b64encode
from typing import Any, Iterator, Optional

import requests
from requests import Response, Session

from ._resource import ItemProxy
from .exceptions import (
    GlpiAPIError,
    GlpiAuthError,
    GlpiConnectionError,
    GlpiNotFoundError,
    GlpiPermissionError,
)
from .logger import EmptyHandler, SensitiveFilter
from .version import GLPIVersion

log = logging.getLogger(__name__)
log.addHandler(EmptyHandler())
log.addFilter(SensitiveFilter())

# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

#: Default page size used by :meth:`GlpiAPI.get_all_items` when no ``range``
#: is supplied.  GLPI's own default is also 50 items per page.
DEFAULT_PAGE_SIZE = 50

_ITEMTYPE_MAP: dict = {
    "ticket":           "Ticket",
    "computer":         "Computer",
    "monitor":          "Monitor",
    "printer":          "Printer",
    "networkequipment": "NetworkEquipment",
    "software":         "Software",
    "user":             "User",
    "group":            "Group",
    "entity":           "Entity",
    "location":         "Location",
    "category":         "ITILCategory",
    "problem":          "Problem",
    "change":           "Change",
    "project":          "Project",
    "projecttask":      "ProjectTask",
    "document":         "Document",
    "contract":         "Contract",
    "supplier":         "Supplier",
    "contact":          "Contact",
    "knowledgebase":    "KnowbaseItem",
    "followup":         "ITILFollowup",
    "solution":         "ITILSolution",
    "task":             "TicketTask",
    "validation":       "TicketValidation",
    "log":              "Log",
}


# ──────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────────────


def _raise_for_glpi_error(response: Response) -> None:
    """Inspect a GLPI API response and raise an appropriate exception."""
    status = response.status_code

    if status in (200, 201, 206):
        return

    try:
        body = response.json()
        if isinstance(body, list) and len(body) >= 2:
            error_code, message = str(body[0]), str(body[1])
        elif isinstance(body, dict):
            error_code = body.get("error", str(status))
            message = body.get("message", response.text)
        else:
            error_code, message = str(status), response.text
    except Exception:
        error_code, message = str(status), response.text

    log.debug("GLPI API error %s – %s: %s", status, error_code, message)

    if status == 401 or "SESSION" in error_code or "AUTH" in error_code:
        raise GlpiAuthError(message, status_code=status, error_code=error_code)
    if status == 403:
        raise GlpiPermissionError(message, status_code=status, error_code=error_code)
    if status == 404:
        raise GlpiNotFoundError(message, status_code=status, error_code=error_code)

    raise GlpiAPIError(message, status_code=status, error_code=error_code)


def _boolify_params(params: dict) -> dict:
    """Convert Python ``bool`` values to GLPI-expected ``0``/``1`` integers."""
    return {k: int(v) if isinstance(v, bool) else v for k, v in params.items()}


def _parse_content_range(header: str) -> Optional[int]:
    """Parse GLPI's ``Content-Range`` header and return the total item count.

    GLPI sends ``Content-Range: 0-49/1337`` where ``1337`` is the grand total.
    Returns ``None`` if the header is absent or malformed.
    """
    if not header:
        return None
    try:
        # Format: "<start>-<end>/<total>"
        total_part = header.split("/")[-1].strip()
        return int(total_part)
    except (ValueError, IndexError):
        return None


# ──────────────────────────────────────────────────────────────────────────────
# Main class
# ──────────────────────────────────────────────────────────────────────────────


class GlpiAPI:
    """Synchronous client for the GLPI 11 legacy REST API (``/apirest.php``).

    Parameters
    ----------
    url : str or None
        Base URL of the GLPI server, e.g. ``"https://glpi.example.com"``.
        Can be supplied via the ``GLPI_URL`` environment variable.
    app_token : str or None
        Application token configured in *Setup → General → API*.
        Optional but recommended for production use.
        Can be supplied via ``GLPI_APP_TOKEN``.
    verify_ssl : bool
        Verify the server's TLS certificate (default: ``True``).
    timeout : int
        HTTP request timeout in seconds (default: ``30``).

    Examples
    --------
    Authenticate with username / password::

        from glpi_utils import GlpiAPI

        api = GlpiAPI(url="https://glpi.example.com", app_token="xxxx")
        api.login(username="glpi", password="glpi")

        # Fetch a single page
        tickets = api.ticket.get_all(range="0-9")

        # Fetch ALL tickets automatically (auto-pagination)
        all_tickets = api.ticket.get_all_pages()

        api.logout()

    Authenticate with a personal API token::

        api = GlpiAPI(url="https://glpi.example.com")
        api.login(user_token="q56hqkniwot8wntb3z1qarka5atf365taaa2uyjrn")

    As a context manager::

        with GlpiAPI(url="https://glpi.example.com") as api:
            api.login(username="glpi", password="glpi")
            print(api.version)
    """

    def __init__(
        self,
        url: Optional[str] = None,
        app_token: Optional[str] = None,
        verify_ssl: bool = True,
        timeout: int = 30,
    ) -> None:
        self._url = (url or os.environ.get("GLPI_URL", "")).rstrip("/")
        if not self._url:
            raise ValueError(
                "A GLPI URL is required. Pass url= or set GLPI_URL environment variable."
            )
        self._app_token = app_token or os.environ.get("GLPI_APP_TOKEN")
        self._verify_ssl = verify_ssl
        self._timeout = timeout

        self._session_token: Optional[str] = None
        self._http = Session()
        self._version: Optional[GLPIVersion] = None
        self._proxies: dict = {}

    # ------------------------------------------------------------------
    # Context-manager support
    # ------------------------------------------------------------------

    def __enter__(self) -> "GlpiAPI":
        return self

    def __exit__(self, *_: Any) -> None:
        if self._session_token:
            try:
                self.logout()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Fluent item-type accessors  api.ticket / api.computer / …
    # ------------------------------------------------------------------

    def __getattr__(self, name: str) -> ItemProxy:
        lower = name.lower()
        if lower in _ITEMTYPE_MAP:
            if lower not in self._proxies:
                self._proxies[lower] = ItemProxy(self, _ITEMTYPE_MAP[lower])
            return self._proxies[lower]
        raise AttributeError(
            f"{self.__class__.__name__!r} object has no attribute {name!r}. "
            "Use api.item('YourItemtype') to access non-standard item types."
        )

    def item(self, itemtype: str) -> ItemProxy:
        """Return an :class:`~glpi_utils._resource.ItemProxy` for any itemtype.

        Parameters
        ----------
        itemtype : str
            GLPI itemtype name (case-sensitive), e.g. ``"Ticket"``.
        """
        if itemtype not in self._proxies:
            self._proxies[itemtype] = ItemProxy(self, itemtype)
        return self._proxies[itemtype]

    # ------------------------------------------------------------------
    # Internal HTTP layer
    # ------------------------------------------------------------------

    @property
    def _base_url(self) -> str:
        return f"{self._url}/apirest.php"

    def _default_headers(self) -> dict:
        headers: dict = {"Content-Type": "application/json"}
        if self._app_token:
            headers["App-Token"] = self._app_token
        if self._session_token:
            headers["Session-Token"] = self._session_token
        return headers

    def _request(
        self,
        method: str,
        path: str,
        *,
        headers: Optional[dict] = None,
        params: Optional[dict] = None,
        json: Any = None,
    ) -> Any:
        url = f"{self._base_url}/{path.lstrip('/')}"
        merged = {**self._default_headers(), **(headers or {})}

        log.debug("%s %s  params=%s", method.upper(), url, params)

        try:
            response = self._http.request(
                method, url,
                headers=merged,
                params=params,
                json=json,
                verify=self._verify_ssl,
                timeout=self._timeout,
            )
        except requests.exceptions.ConnectionError as exc:
            raise GlpiConnectionError(f"Cannot reach GLPI at {self._url}: {exc}") from exc
        except requests.exceptions.Timeout as exc:
            raise GlpiConnectionError(f"Request timed out after {self._timeout}s: {exc}") from exc

        log.debug("Response %s from %s", response.status_code, url)

        if response.status_code == 204 or not response.content:
            return None

        _raise_for_glpi_error(response)
        return response.json()

    def _request_with_headers(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict] = None,
        json: Any = None,
    ) -> tuple:
        """Like ``_request`` but returns ``(body, response_headers)``."""
        url = f"{self._base_url}/{path.lstrip('/')}"
        merged = self._default_headers()

        log.debug("%s %s  params=%s", method.upper(), url, params)

        try:
            response = self._http.request(
                method, url,
                headers=merged,
                params=params,
                json=json,
                verify=self._verify_ssl,
                timeout=self._timeout,
            )
        except requests.exceptions.ConnectionError as exc:
            raise GlpiConnectionError(f"Cannot reach GLPI at {self._url}: {exc}") from exc
        except requests.exceptions.Timeout as exc:
            raise GlpiConnectionError(f"Request timed out after {self._timeout}s: {exc}") from exc

        log.debug("Response %s from %s", response.status_code, url)

        if response.status_code == 204 or not response.content:
            return None, response.headers

        _raise_for_glpi_error(response)
        return response.json(), response.headers

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def login(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        user_token: Optional[str] = None,
    ) -> None:
        """Authenticate against GLPI and store the session token.

        Parameters
        ----------
        username : str or None
        password : str or None
        user_token : str or None
            Personal API token from the user profile page (*Remote access key*).

        Environment variables
        ---------------------
        ``GLPI_USER``, ``GLPI_PASSWORD``, ``GLPI_USER_TOKEN``
        """
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
            raise GlpiAuthError(
                "Provide username+password or user_token (or set "
                "GLPI_USER/GLPI_PASSWORD/GLPI_USER_TOKEN)."
            )

        data = self._request("GET", "initSession", headers=auth_headers)
        self._session_token = data["session_token"]
        log.debug("Session established.")

    def logout(self) -> None:
        """Terminate the active GLPI session."""
        if self._session_token:
            try:
                self._request("GET", "killSession")
            finally:
                self._session_token = None
                log.debug("Session terminated.")

    # ------------------------------------------------------------------
    # Version
    # ------------------------------------------------------------------

    @property
    def version(self) -> GLPIVersion:
        """GLPI server version as a :class:`~glpi_utils.version.GLPIVersion`."""
        if self._version is None:
            try:
                data = self._request("GET", "getGlpiConfig")
                # GLPI 10/11: version is in cfg_glpi.glpi_version
                raw = (
                    (data.get("cfg_glpi") or {}).get("version")
                    or (data.get("cfg_glpi") or {}).get("glpi_version")
                    or data.get("glpi_version")
                    or data.get("version")
                )
            except GlpiAPIError:
                raw = None
            if not raw:
                # Fallback: read from full session
                try:
                    session = self._request("GET", "getFullSession")
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

    def get_my_profiles(self) -> list:
        """Return profiles available to the current user."""
        return self._request("GET", "getMyProfiles")["myprofiles"]

    def get_active_profile(self) -> dict:
        """Return the currently active profile."""
        return self._request("GET", "getActiveProfile")["active_profile"]

    def set_active_profile(self, profile_id: int) -> None:
        """Switch to a different profile."""
        self._request("POST", "changeActiveProfile", json={"profiles_id": profile_id})

    def get_my_entities(self, is_recursive: bool = False) -> list:
        """Return entities accessible to the current user."""
        return self._request(
            "GET", "getMyEntities", params={"is_recursive": int(is_recursive)}
        )["myentities"]

    def get_active_entities(self) -> dict:
        """Return the current active entity context."""
        return self._request("GET", "getActiveEntities")["active_entity"]

    def set_active_entity(self, entity_id: int, is_recursive: bool = False) -> None:
        """Switch the active entity context."""
        self._request(
            "POST",
            "changeActiveEntities",
            json={"entities_id": entity_id, "is_recursive": int(is_recursive)},
        )

    def get_full_session(self) -> dict:
        """Return the full PHP session data."""
        return self._request("GET", "getFullSession")["session"]

    def get_glpi_config(self) -> dict:
        """Return global GLPI configuration."""
        return self._request("GET", "getGlpiConfig")

    # ------------------------------------------------------------------
    # Item CRUD
    # ------------------------------------------------------------------

    def get_item(self, itemtype: str, item_id: int, **kwargs: Any) -> dict:
        """Return a single item by ID.

        Parameters
        ----------
        itemtype : str
        item_id : int
        **kwargs
            Extra query parameters: ``expand_dropdowns``, ``with_logs``,
            ``with_networkports``, ``with_infocoms``, etc.
        """
        params = _boolify_params(kwargs)
        return self._request("GET", f"{itemtype}/{item_id}", params=params)

    def get_all_items(self, itemtype: str, **kwargs: Any) -> list:
        """Return a **single page** of items.

        Use :meth:`get_all_pages` to retrieve every item across all pages
        automatically.

        Parameters
        ----------
        itemtype : str
        **kwargs
            ``range`` (default ``"0-49"``), ``sort``, ``order``,
            ``searchText``, ``is_deleted``, ``expand_dropdowns``, etc.
        """
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
        """Fetch **all** items of *itemtype* by iterating pages automatically.

        GLPI paginates results via a ``range`` query parameter (``0-49``,
        ``50-99``, …) and reports the grand total in the ``Content-Range``
        response header (``0-49/1337``).  This method handles all of that
        transparently and returns a single flat list.

        Parameters
        ----------
        itemtype : str
            GLPI itemtype, e.g. ``"Ticket"``.
        page_size : int
            Items per request (default: 50).  Increase for fewer round-trips
            on large datasets; decrease if responses are slow.
        **kwargs
            Extra GLPI parameters passed to every page request: ``sort``,
            ``order``, ``searchText``, ``is_deleted``,
            ``expand_dropdowns``, etc.  Do **not** pass ``range`` here —
            it is managed internally.

        Returns
        -------
        list
            All matching items as a flat list of dicts.

        Examples
        --------
        ::

            # All open tickets, sorted by date
            tickets = api.get_all_pages(
                "Ticket",
                sort="date_mod",
                order="DESC",
                searchText={"status": "1"},
            )

            # Via the fluent proxy
            computers = api.computer.get_all_pages(expand_dropdowns=True)
        """
        params = _boolify_params(kwargs)
        results: list = []
        start = 0

        while True:
            end = start + page_size - 1
            params["range"] = f"{start}-{end}"

            page_items, resp_headers = self._request_with_headers(
                "GET", itemtype, params=params
            )

            if not page_items:
                break

            results.extend(page_items)

            total = _parse_content_range(
                resp_headers.get("Content-Range", "")
            )

            log.debug(
                "Paginating %s: fetched %d/%s items (range %s-%s)",
                itemtype, len(results), total or "?", start, end,
            )

            # Stop if we know the grand total and have reached it
            if total is not None and len(results) >= total:
                break

            # Stop if GLPI returned fewer items than requested
            # (last partial page — no Content-Range header on some versions)
            if len(page_items) < page_size:
                break

            start += page_size

        return results

    def iter_pages(
        self,
        itemtype: str,
        page_size: int = DEFAULT_PAGE_SIZE,
        **kwargs: Any,
    ) -> Iterator[list]:
        """Yield one page of items at a time.

        Memory-efficient alternative to :meth:`get_all_pages` for very large
        datasets where you want to process each batch immediately rather than
        accumulating everything in RAM.

        Parameters
        ----------
        itemtype : str
        page_size : int
        **kwargs
            Same as :meth:`get_all_pages`.

        Yields
        ------
        list
            One page (list of dicts) per iteration.

        Examples
        --------
        ::

            for page in api.iter_pages("Ticket", page_size=100):
                for ticket in page:
                    process(ticket)
        """
        params = _boolify_params(kwargs)
        start = 0
        fetched = 0

        while True:
            end = start + page_size - 1
            params["range"] = f"{start}-{end}"

            page_items, resp_headers = self._request_with_headers(
                "GET", itemtype, params=params
            )

            if not page_items:
                return

            fetched += len(page_items)
            yield page_items

            total = _parse_content_range(
                resp_headers.get("Content-Range", "")
            )

            if total is not None and fetched >= total:
                return
            if len(page_items) < page_size:
                return

            start += page_size

    def search(self, itemtype: str, **kwargs: Any) -> dict:
        """Run the GLPI search engine.

        Parameters
        ----------
        itemtype : str
            ``"AllAssets"`` for a cross-type search.
        **kwargs
            ``criteria``, ``metacriteria``, ``sort``, ``order``,
            ``range``, ``forcedisplay``, ``rawdata``, ``withindexes``.
        """
        params = _boolify_params(kwargs)
        return self._request("GET", f"search/{itemtype}", params=params)

    def create_item(self, itemtype: str, input_data: Any, **kwargs: Any) -> Any:
        """Create one or several items."""
        payload: dict = {"input": input_data}
        payload.update(kwargs)
        return self._request("POST", itemtype, json=payload)

    def update_item(self, itemtype: str, input_data: Any, **kwargs: Any) -> list:
        """Update one or several items. Each dict must contain an ``"id"`` key."""
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
        """Delete one or several items.

        Parameters
        ----------
        force_purge : bool
            Bypass the trash and permanently delete.
        history : bool
            Whether to log the deletion in history.
        """
        payload: dict = {
            "input": input_data,
            "force_purge": int(force_purge),
            "history": int(history),
        }
        return self._request("DELETE", itemtype, json=payload)

    # ------------------------------------------------------------------
    # Sub-items
    # ------------------------------------------------------------------

    def get_sub_items(
        self,
        itemtype: str,
        item_id: int,
        sub_itemtype: str,
        **kwargs: Any,
    ) -> list:
        """Return sub-items (e.g. followups, tasks, solutions of a ticket)."""
        params = _boolify_params(kwargs)
        return self._request(
            "GET", f"{itemtype}/{item_id}/{sub_itemtype}", params=params
        )

    def add_sub_item(
        self,
        itemtype: str,
        item_id: int,
        sub_itemtype: str,
        input_data: dict,
        **kwargs: Any,
    ) -> dict:
        """Add a sub-item to a parent resource."""
        payload: dict = {"input": input_data}
        payload.update(kwargs)
        return self._request(
            "POST", f"{itemtype}/{item_id}/{sub_itemtype}", json=payload
        )

    # ------------------------------------------------------------------
    # Misc
    # ------------------------------------------------------------------

    def list_item_types(self) -> list:
        """Return all available item-type names in this GLPI instance."""
        return self._request("GET", "listItemtypes")

    def upload_document(self, file_path: str, document_name: Optional[str] = None) -> dict:
        """Upload a file as a GLPI Document.

        Parameters
        ----------
        file_path : str
            Local path to the file to upload.
        document_name : str or None
            Display name. Defaults to the file basename.
        """
        import json as _json
        from pathlib import Path

        fp = Path(file_path)
        name = document_name or fp.name
        manifest = _json.dumps({"input": {"name": name, "filename": [fp.name]}})
        url = f"{self._base_url}/Document"
        headers = {k: v for k, v in self._default_headers().items() if k != "Content-Type"}

        with fp.open("rb") as fh:
            response = self._http.post(
                url, headers=headers,
                files={
                    "uploadManifest": (None, manifest, "application/json"),
                    "filename[0]": (fp.name, fh),
                },
                verify=self._verify_ssl,
                timeout=self._timeout,
            )
        _raise_for_glpi_error(response)
        return response.json()


from .exceptions import GlpiError  # noqa: E402
