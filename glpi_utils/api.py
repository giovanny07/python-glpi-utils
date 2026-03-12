"""
glpi_utils.api
~~~~~~~~~~~~~~

Synchronous GLPI REST API client.

GLPI 11 ships with two parallel APIs:

* **Legacy API** (``/apirest.php``) – session-token based, stable, the one
  this module targets for maximum compatibility.
* **High-level API** (``/api.php``) – OAuth2-based, introduced in GLPI 11.

This implementation focuses on the legacy API because it remains the most
broadly supported mechanism for automation and scripts as of GLPI 11.
OAuth2 support via the high-level API can be added in a future release.
"""

from __future__ import annotations

import logging
import os
from base64 import b64encode
from typing import Any, Optional

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
from .version import GLPIVersion

log = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Module-level helpers
# ──────────────────────────────────────────────────────────────────────────────

_ITEMTYPE_MAP: dict = {
    # attr name  →  GLPI itemtype
    "ticket": "Ticket",
    "computer": "Computer",
    "monitor": "Monitor",
    "printer": "Printer",
    "networkequipment": "NetworkEquipment",
    "software": "Software",
    "user": "User",
    "group": "Group",
    "entity": "Entity",
    "location": "Location",
    "category": "ITILCategory",
    "problem": "Problem",
    "change": "Change",
    "project": "Project",
    "projecttask": "ProjectTask",
    "document": "Document",
    "contract": "Contract",
    "supplier": "Supplier",
    "contact": "Contact",
    "knowledgebase": "KnowbaseItem",
    "followup": "ITILFollowup",
    "solution": "ITILSolution",
    "task": "TicketTask",
    "validation": "TicketValidation",
    "log": "Log",
}


def _raise_for_glpi_error(response: Response) -> None:
    """Inspect a GLPI API response and raise an appropriate exception."""
    status = response.status_code

    if status == 200 or status == 201:
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
        Application token configured in GLPI → Setup → General → API.
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
        tickets = api.ticket.get_all(range="0-9")
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

        # Cached ItemProxy instances
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
    # Fluent item-type accessor (api.ticket, api.computer, …)
    # ------------------------------------------------------------------

    def __getattr__(self, name: str) -> ItemProxy:
        lower = name.lower()
        if lower in _ITEMTYPE_MAP:
            if lower not in self._proxies:
                self._proxies[lower] = ItemProxy(self, _ITEMTYPE_MAP[lower])
            return self._proxies[lower]
        raise AttributeError(
            f"{self.__class__.__name__!r} object has no attribute {name!r}. "
            f"Use api.item('YourItemtype') to access non-standard item types."
        )

    def item(self, itemtype: str) -> ItemProxy:
        """Return an :class:`~glpi_utils._resource.ItemProxy` for any itemtype.

        Parameters
        ----------
        itemtype : str
            GLPI itemtype name (case-sensitive), e.g. ``"Ticket"``, ``"KnowbaseItem"``.
        """
        if itemtype not in self._proxies:
            self._proxies[itemtype] = ItemProxy(self, itemtype)
        return self._proxies[itemtype]

    # ------------------------------------------------------------------
    # Internal HTTP helpers
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
        merged_headers = {**self._default_headers(), **(headers or {})}

        log.debug("%s %s params=%s", method.upper(), url, params)

        try:
            response = self._http.request(
                method,
                url,
                headers=merged_headers,
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
        _raise_for_glpi_error(response)

        if response.status_code == 204 or not response.content:
            return None
        return response.json()

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

        Call **one** of the following parameter combinations:

        * ``username`` + ``password`` – basic-auth credentials.
        * ``user_token`` – personal API token from the user profile page.

        Environment-variable fallbacks: ``GLPI_USER``, ``GLPI_PASSWORD``,
        ``GLPI_USER_TOKEN``.

        Parameters
        ----------
        username : str or None
        password : str or None
        user_token : str or None
        """
        username = username or os.environ.get("GLPI_USER")
        password = password or os.environ.get("GLPI_PASSWORD")
        user_token = user_token or os.environ.get("GLPI_USER_TOKEN")

        auth_headers: dict = {}

        if user_token:
            auth_headers["Authorization"] = f"user_token {user_token}"
        elif username and password:
            credentials = b64encode(f"{username}:{password}".encode()).decode()
            auth_headers["Authorization"] = f"Basic {credentials}"
        else:
            raise GlpiAuthError(
                "Provide username+password or user_token (or set the corresponding "
                "environment variables GLPI_USER/GLPI_PASSWORD/GLPI_USER_TOKEN)."
            )

        data = self._request("GET", "initSession", headers=auth_headers)
        self._session_token = data["session_token"]
        log.debug("Session established (token length=%d)", len(self._session_token))

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
        """Return the GLPI server version as a :class:`~glpi_utils.version.GLPIVersion`."""
        if self._version is None:
            data = self._request("GET", "getGlpiVersion")
            self._version = GLPIVersion(data.get("glpi_version", "0.0.0"))
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
        return self._request("GET", "getGlpiVersion")

    # ------------------------------------------------------------------
    # Item CRUD
    # ------------------------------------------------------------------

    def get_item(self, itemtype: str, item_id: int, **kwargs: Any) -> dict:
        """Return a single item by ID."""
        params = _boolify_params(kwargs)
        return self._request("GET", f"{itemtype}/{item_id}", params=params)

    def get_all_items(self, itemtype: str, **kwargs: Any) -> list:
        """Return all items of *itemtype* (handles pagination automatically)."""
        params = _boolify_params(kwargs)
        if "range" not in params:
            params["range"] = "0-49"
        return self._request("GET", itemtype, params=params)

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
        """Update one or several items. Each item dict must contain an ``"id"`` key."""
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
        """Return sub-items of a given type for a parent item."""
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
    # List item types
    # ------------------------------------------------------------------

    def list_item_types(self) -> list:
        """Return the list of available item-type names in this GLPI instance."""
        return self._request("GET", "listItemtypes")

    # ------------------------------------------------------------------
    # Documents
    # ------------------------------------------------------------------

    def upload_document(self, file_path: str, document_name: Optional[str] = None) -> dict:
        """Upload a file as a GLPI Document.

        Parameters
        ----------
        file_path : str
            Local path to the file to upload.
        document_name : str or None
            Optional display name. Defaults to the file basename.
        """
        import json as _json
        from pathlib import Path

        file_path_obj = Path(file_path)
        name = document_name or file_path_obj.name

        manifest = _json.dumps(
            {"input": {"name": name, "filename": [file_path_obj.name]}}
        )
        url = f"{self._base_url}/Document"
        headers = {k: v for k, v in self._default_headers().items() if k != "Content-Type"}

        with file_path_obj.open("rb") as fh:
            response = self._http.post(
                url,
                headers=headers,
                files={
                    "uploadManifest": (None, manifest, "application/json"),
                    "filename[0]": (file_path_obj.name, fh),
                },
                verify=self._verify_ssl,
                timeout=self._timeout,
            )
        _raise_for_glpi_error(response)
        return response.json()


# ──────────────────────────────────────────────────────────────────────────────
# Utilities
# ──────────────────────────────────────────────────────────────────────────────


def _boolify_params(params: dict) -> dict:
    """Convert Python booleans to GLPI-expected ``0``/``1`` integers."""
    return {k: int(v) if isinstance(v, bool) else v for k, v in params.items()}


from .exceptions import GlpiError  # noqa: E402
