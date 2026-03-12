"""
tests/test_oauth.py
~~~~~~~~~~~~~~~~~~~

Tests for GlpiOAuthClient (sync) and AsyncGlpiOAuthClient (async).
All HTTP calls are mocked – no live GLPI server required.
"""

from __future__ import annotations

import os
import time
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from glpi_utils.exceptions import GlpiAuthError, GlpiConnectionError, GlpiNotFoundError
from glpi_utils.logger import SensitiveFilter
from glpi_utils.oauth import AsyncGlpiOAuthClient, GlpiOAuthClient, _TokenStore


# ──────────────────────────────────────────────────────────────────────────────
# _TokenStore
# ──────────────────────────────────────────────────────────────────────────────

class TestTokenStore(unittest.TestCase):

    def test_initially_invalid(self):
        ts = _TokenStore()
        self.assertFalse(ts.is_valid())

    def test_valid_after_store(self):
        ts = _TokenStore()
        ts.store("mytoken", expires_in=3600)
        self.assertTrue(ts.is_valid())

    def test_expired_token_invalid(self):
        ts = _TokenStore()
        ts.store("mytoken", expires_in=0)  # immediately expired (buffer kicks in)
        # expires_in=0 → expires_at = now - 30 → already expired
        self.assertFalse(ts.is_valid())

    def test_clear_invalidates(self):
        ts = _TokenStore()
        ts.store("token", expires_in=3600)
        ts.clear()
        self.assertFalse(ts.is_valid())
        self.assertIsNone(ts.access_token)


# ──────────────────────────────────────────────────────────────────────────────
# GlpiOAuthClient – init
# ──────────────────────────────────────────────────────────────────────────────

class TestGlpiOAuthClientInit(unittest.TestCase):

    def test_missing_url_raises(self):
        with self.assertRaises(ValueError):
            GlpiOAuthClient(url="")

    def test_url_trailing_slash_stripped(self):
        api = GlpiOAuthClient(url="https://glpi.example.com/")
        self.assertEqual(api._url, "https://glpi.example.com")

    def test_url_from_env(self):
        with patch.dict(os.environ, {"GLPI_URL": "https://env.example.com"}):
            api = GlpiOAuthClient()
            self.assertEqual(api._url, "https://env.example.com")

    def test_client_id_from_env(self):
        with patch.dict(os.environ, {
            "GLPI_URL": "https://glpi.example.com",
            "GLPI_OAUTH_CLIENT_ID": "env-client",
        }):
            api = GlpiOAuthClient()
            self.assertEqual(api._client_id, "env-client")

    def test_token_url(self):
        api = GlpiOAuthClient(url="https://glpi.example.com")
        self.assertEqual(api._token_url, "https://glpi.example.com/api.php/token")

    def test_api_url(self):
        api = GlpiOAuthClient(url="https://glpi.example.com")
        self.assertEqual(api._api_url, "https://glpi.example.com/api.php")

    def test_not_authenticated_raises_on_request(self):
        api = GlpiOAuthClient(url="https://glpi.example.com", client_id="x", client_secret="y")
        with self.assertRaises(GlpiAuthError):
            api._auth_headers()

    def test_unknown_attr_raises(self):
        api = GlpiOAuthClient(url="https://glpi.example.com")
        with self.assertRaises(AttributeError):
            _ = api.nonexistent_xyz

    def test_item_proxy_for_custom_type(self):
        api = GlpiOAuthClient(url="https://glpi.example.com")
        proxy = api.item("KnowbaseItem")
        self.assertEqual(proxy._itemtype, "KnowbaseItem")

    def test_all_builtin_aliases_resolve(self):
        api = GlpiOAuthClient(url="https://glpi.example.com")
        for alias in ["ticket", "computer", "user", "group"]:
            proxy = getattr(api, alias)
            self.assertIsNotNone(proxy)


# ──────────────────────────────────────────────────────────────────────────────
# GlpiOAuthClient – authentication
# ──────────────────────────────────────────────────────────────────────────────

def _mock_token_response(access_token="test_access_token", expires_in=3600, status=200):
    m = MagicMock()
    m.status_code = status
    m.json.return_value = {
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": expires_in,
    }
    m.text = ""
    return m


class TestGlpiOAuthClientAuth(unittest.TestCase):

    @patch("requests.Session.post")
    def test_client_credentials_grant(self, mock_post):
        mock_post.return_value = _mock_token_response()
        api = GlpiOAuthClient(
            url="https://glpi.example.com",
            client_id="my-app",
            client_secret="secret",
        )
        api.authenticate()
        self.assertTrue(api._token.is_valid())
        self.assertEqual(api._token.access_token, "test_access_token")

    @patch("requests.Session.post")
    def test_password_grant(self, mock_post):
        mock_post.return_value = _mock_token_response("user_token_val")
        api = GlpiOAuthClient(
            url="https://glpi.example.com",
            client_id="my-app",
            client_secret="secret",
        )
        api.authenticate(username="admin", password="glpi")
        payload = mock_post.call_args[1]["data"]
        self.assertEqual(payload["grant_type"], "password")
        self.assertEqual(payload["username"], "admin")
        self.assertEqual(api._token.access_token, "user_token_val")

    @patch("requests.Session.post")
    def test_scope_is_api(self, mock_post):
        mock_post.return_value = _mock_token_response()
        api = GlpiOAuthClient(url="https://glpi.example.com", client_id="x", client_secret="y")
        api.authenticate()
        payload = mock_post.call_args[1]["data"]
        self.assertEqual(payload["scope"], "api")

    def test_no_client_id_raises(self):
        api = GlpiOAuthClient(url="https://glpi.example.com")
        with self.assertRaises(GlpiAuthError):
            api.authenticate()

    def test_client_credentials_without_secret_raises(self):
        api = GlpiOAuthClient(url="https://glpi.example.com", client_id="x")
        with self.assertRaises(GlpiAuthError):
            api.authenticate()

    @patch("requests.Session.post")
    def test_failed_token_response_raises(self, mock_post):
        m = MagicMock()
        m.status_code = 401
        m.json.return_value = {"error": "invalid_client", "error_description": "Bad creds"}
        m.text = "bad"
        mock_post.return_value = m
        api = GlpiOAuthClient(url="https://glpi.example.com", client_id="x", client_secret="y")
        with self.assertRaises(GlpiAuthError):
            api.authenticate()

    @patch("requests.Session.post")
    def test_auth_from_env_vars(self, mock_post):
        mock_post.return_value = _mock_token_response()
        with patch.dict(os.environ, {
            "GLPI_URL": "https://glpi.example.com",
            "GLPI_OAUTH_CLIENT_ID": "env-app",
            "GLPI_OAUTH_CLIENT_SECRET": "env-secret",
        }):
            api = GlpiOAuthClient()
            api.authenticate()
        self.assertTrue(api._token.is_valid())

    def test_token_auto_refresh_calls_ensure_token(self):
        """_ensure_token re-authenticates when token is expired."""
        api = GlpiOAuthClient(url="https://glpi.example.com", client_id="x", client_secret="y")
        api._token.store("old_token", expires_in=0)  # force expired

        with patch.object(api, "authenticate") as mock_auth:
            # Call _ensure_token directly (it's what _request_with_headers uses)
            api._ensure_token()
        mock_auth.assert_called_once()

    def test_valid_token_skips_reauthentication(self):
        """_ensure_token does NOT re-authenticate when token is still valid."""
        api = GlpiOAuthClient(url="https://glpi.example.com", client_id="x", client_secret="y")
        api._token.store("valid_token", expires_in=3600)

        with patch.object(api, "authenticate") as mock_auth:
            api._ensure_token()
        mock_auth.assert_not_called()


# ──────────────────────────────────────────────────────────────────────────────
# GlpiOAuthClient – CRUD
# ──────────────────────────────────────────────────────────────────────────────

def _make_oauth_api(token="bearer_tok") -> GlpiOAuthClient:
    api = GlpiOAuthClient(
        url="https://glpi.example.com",
        client_id="app",
        client_secret="secret",
    )
    api._token.store(token, expires_in=3600)
    return api


def _mock_oauth_response(status=200, json_data=None):
    m = MagicMock()
    m.status_code = status
    m.content = b"x"
    m.json.return_value = json_data if json_data is not None else {}
    m.text = str(json_data)
    m.headers = {}
    return m


class TestGlpiOAuthClientCRUD(unittest.TestCase):

    def setUp(self):
        self.api = _make_oauth_api()

    @patch("requests.Session.request")
    def test_get_item(self, mock_req):
        mock_req.return_value = _mock_oauth_response(200, {"id": 1, "name": "Test"})
        result = self.api.get_item("Ticket", 1)
        self.assertEqual(result["id"], 1)

    @patch("requests.Session.request")
    def test_bearer_token_in_header(self, mock_req):
        mock_req.return_value = _mock_oauth_response(200, {"id": 1})
        self.api.get_item("Ticket", 1)
        headers = mock_req.call_args[1]["headers"]
        self.assertTrue(headers["Authorization"].startswith("Bearer "))

    @patch("requests.Session.request")
    def test_get_all_items(self, mock_req):
        mock_req.return_value = _mock_oauth_response(200, [{"id": 1}, {"id": 2}])
        result = self.api.get_all_items("Ticket")
        self.assertEqual(len(result), 2)

    @patch("requests.Session.request")
    def test_create_item(self, mock_req):
        mock_req.return_value = _mock_oauth_response(201, {"id": 42})
        result = self.api.create_item("Ticket", {"name": "T", "content": "C"})
        self.assertEqual(result["id"], 42)

    @patch("requests.Session.request")
    def test_update_item(self, mock_req):
        mock_req.return_value = _mock_oauth_response(200, [{"1": True}])
        result = self.api.update_item("Ticket", {"id": 1, "name": "Updated"})
        self.assertIsInstance(result, list)

    @patch("requests.Session.request")
    def test_delete_item(self, mock_req):
        mock_req.return_value = _mock_oauth_response(200, [{"1": True}])
        result = self.api.delete_item("Ticket", {"id": 1})
        self.assertIsInstance(result, list)

    @patch("requests.Session.request")
    def test_search(self, mock_req):
        mock_req.return_value = _mock_oauth_response(200, {"totalcount": 3, "data": []})
        result = self.api.search("Ticket")
        self.assertEqual(result["totalcount"], 3)

    @patch("requests.Session.request")
    def test_get_sub_items(self, mock_req):
        mock_req.return_value = _mock_oauth_response(200, [{"id": 1}])
        result = self.api.get_sub_items("Ticket", 10, "ITILFollowup")
        self.assertEqual(len(result), 1)

    @patch("requests.Session.request")
    def test_404_raises_not_found(self, mock_req):
        mock_req.return_value = _mock_oauth_response(
            404, {"error": "ERROR_ITEM_NOT_FOUND", "message": "Not found"}
        )
        with self.assertRaises(GlpiNotFoundError):
            self.api.get_item("Ticket", 9999)

    @patch("requests.Session.request")
    def test_proxy_get(self, mock_req):
        mock_req.return_value = _mock_oauth_response(200, {"id": 5})
        result = self.api.ticket.get(5)
        self.assertEqual(result["id"], 5)

    @patch("requests.Session.request")
    def test_proxy_get_all_pages(self, mock_req):
        items = [{"id": i} for i in range(3)]
        m = _mock_oauth_response(200, items)
        m.headers = {"Content-Range": "0-2/3"}
        mock_req.return_value = m
        result = self.api.ticket.get_all_pages()
        self.assertEqual(len(result), 3)

    def test_context_manager(self):
        with GlpiOAuthClient(
            url="https://glpi.example.com", client_id="x", client_secret="y"
        ) as api:
            api._token.store("tok", 3600)
        self.assertFalse(api._token.is_valid())


# ──────────────────────────────────────────────────────────────────────────────
# AsyncGlpiOAuthClient – init
# ──────────────────────────────────────────────────────────────────────────────

class TestAsyncGlpiOAuthClientInit(unittest.TestCase):

    def test_missing_url_raises(self):
        with self.assertRaises(ValueError):
            AsyncGlpiOAuthClient(url="")

    def test_url_trailing_slash_stripped(self):
        api = AsyncGlpiOAuthClient(url="https://glpi.example.com/")
        self.assertEqual(api._url, "https://glpi.example.com")

    def test_token_url(self):
        api = AsyncGlpiOAuthClient(url="https://glpi.example.com")
        self.assertEqual(api._token_url, "https://glpi.example.com/api.php/token")

    def test_no_aiohttp_raises(self):
        import sys
        backup = sys.modules.get("aiohttp")
        sys.modules["aiohttp"] = None  # type: ignore
        try:
            with self.assertRaises(ImportError):
                AsyncGlpiOAuthClient(url="https://glpi.example.com")
        finally:
            if backup is not None:
                sys.modules["aiohttp"] = backup
            else:
                sys.modules.pop("aiohttp", None)


# ──────────────────────────────────────────────────────────────────────────────
# AsyncGlpiOAuthClient – async tests
# ──────────────────────────────────────────────────────────────────────────────

def _async_token_response(access_token="async_bearer", expires_in=3600, status=200):
    body = {"access_token": access_token, "expires_in": expires_in, "token_type": "Bearer"}
    resp = MagicMock()
    resp.status = status
    resp.json = AsyncMock(return_value=body)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=resp)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


def _async_api_response(json_data, status=200, content_range=""):
    resp = MagicMock()
    resp.status = status
    resp.content_length = 100
    resp.headers = {"Content-Range": content_range} if content_range else {}
    resp.json = AsyncMock(return_value=json_data)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=resp)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


@pytest.mark.asyncio
async def test_async_oauth_authenticate_client_credentials():
    api = AsyncGlpiOAuthClient(
        url="https://glpi.example.com",
        client_id="my-app",
        client_secret="secret",
    )
    mock_cm = _async_token_response()
    with patch("aiohttp.ClientSession.post", return_value=mock_cm):
        await api.authenticate()
    assert api._token.is_valid()
    assert api._token.access_token == "async_bearer"


@pytest.mark.asyncio
async def test_async_oauth_no_client_id_raises():
    api = AsyncGlpiOAuthClient(url="https://glpi.example.com")
    with pytest.raises(GlpiAuthError):
        await api.authenticate()


@pytest.mark.asyncio
async def test_async_oauth_failed_token_raises():
    api = AsyncGlpiOAuthClient(
        url="https://glpi.example.com", client_id="x", client_secret="y"
    )
    resp = MagicMock()
    resp.status = 401
    resp.json = AsyncMock(return_value={"error": "invalid_client", "error_description": "bad"})
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=resp)
    cm.__aexit__ = AsyncMock(return_value=False)

    with patch("aiohttp.ClientSession.post", return_value=cm):
        with pytest.raises(GlpiAuthError):
            await api.authenticate()


@pytest.mark.asyncio
async def test_async_oauth_get_item():
    api = AsyncGlpiOAuthClient(
        url="https://glpi.example.com", client_id="x", client_secret="y"
    )
    api._token.store("bearer_tok", 3600)
    mock_cm = _async_api_response({"id": 1, "name": "Async ticket"})
    with patch("aiohttp.ClientSession.request", return_value=mock_cm):
        result = await api.get_item("Ticket", 1)
    assert result["id"] == 1


@pytest.mark.asyncio
async def test_async_oauth_get_all_pages():
    api = AsyncGlpiOAuthClient(
        url="https://glpi.example.com", client_id="x", client_secret="y"
    )
    api._token.store("bearer_tok", 3600)
    items = [{"id": i} for i in range(5)]
    mock_cm = _async_api_response(items, content_range="0-4/5")
    with patch("aiohttp.ClientSession.request", return_value=mock_cm):
        result = await api.get_all_pages("Ticket")
    assert len(result) == 5


@pytest.mark.asyncio
async def test_async_oauth_iter_pages():
    api = AsyncGlpiOAuthClient(
        url="https://glpi.example.com", client_id="x", client_secret="y"
    )
    api._token.store("bearer_tok", 3600)
    items = [{"id": 1}, {"id": 2}]
    mock_cm = _async_api_response(items)
    with patch("aiohttp.ClientSession.request", return_value=mock_cm):
        pages = []
        async for page in api.iter_pages("Ticket"):
            pages.append(page)
    assert len(pages) == 1
    assert len(pages[0]) == 2


@pytest.mark.asyncio
async def test_async_oauth_proxy():
    api = AsyncGlpiOAuthClient(
        url="https://glpi.example.com", client_id="x", client_secret="y"
    )
    api._token.store("bearer_tok", 3600)
    mock_cm = _async_api_response({"id": 7})
    with patch("aiohttp.ClientSession.request", return_value=mock_cm):
        result = await api.ticket.get(7)
    assert result["id"] == 7


@pytest.mark.asyncio
async def test_async_oauth_context_manager():
    api = AsyncGlpiOAuthClient(
        url="https://glpi.example.com", client_id="x", client_secret="y"
    )
    mock_token_cm = _async_token_response()
    with patch("aiohttp.ClientSession.post", return_value=mock_token_cm):
        async with api:
            await api.authenticate()
    assert not api._token.is_valid()


if __name__ == "__main__":
    unittest.main()
