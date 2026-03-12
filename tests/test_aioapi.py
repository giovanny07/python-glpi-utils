"""
tests/test_aioapi.py
~~~~~~~~~~~~~~~~~~~~

Tests for AsyncGlpiAPI (asynchronous client).
Uses pytest-asyncio + aiohttp mocking. No live server required.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from glpi_utils import AsyncGlpiAPI, GlpiAuthError
from glpi_utils.exceptions import GlpiConnectionError
from glpi_utils.version import GLPIVersion


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _make_async_api(session_token: str = "async_fake_token") -> AsyncGlpiAPI:
    api = AsyncGlpiAPI(url="https://glpi.example.com", app_token="testapptoken")
    api._session_token = session_token
    return api


def _mock_aiohttp_response(status: int = 200, json_data=None):
    """Build a fake aiohttp response context manager."""
    response = MagicMock()
    response.status = status
    response.content_length = 100
    response.json = AsyncMock(return_value=json_data if json_data is not None else {})
    response.text = AsyncMock(return_value=str(json_data))

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=response)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


# ──────────────────────────────────────────────────────────────────────────────
# Init tests (sync - no async needed)
# ──────────────────────────────────────────────────────────────────────────────


class TestAsyncGlpiAPIInit(unittest.TestCase):

    def test_missing_url_raises(self):
        with self.assertRaises(ValueError):
            AsyncGlpiAPI(url="")

    def test_url_trailing_slash_stripped(self):
        api = AsyncGlpiAPI(url="https://glpi.example.com/")
        self.assertEqual(api._url, "https://glpi.example.com")

    def test_url_from_env(self):
        with patch.dict(os.environ, {"GLPI_URL": "https://env.example.com"}):
            api = AsyncGlpiAPI()
            self.assertEqual(api._url, "https://env.example.com")

    def test_base_url_property(self):
        api = AsyncGlpiAPI(url="https://glpi.example.com")
        self.assertEqual(api._base_url, "https://glpi.example.com/apirest.php")

    def test_version_none_before_fetch(self):
        api = AsyncGlpiAPI(url="https://glpi.example.com")
        self.assertIsNone(api.version)

    def test_no_aiohttp_raises_import_error(self):
        import sys
        aiohttp_backup = sys.modules.get("aiohttp")
        sys.modules["aiohttp"] = None  # type: ignore
        try:
            with self.assertRaises(ImportError):
                AsyncGlpiAPI(url="https://glpi.example.com")
        finally:
            if aiohttp_backup is not None:
                sys.modules["aiohttp"] = aiohttp_backup
            else:
                sys.modules.pop("aiohttp", None)

    def test_item_proxy_for_custom_type(self):
        api = _make_async_api()
        proxy = api.item("KnowbaseItem")
        self.assertEqual(proxy._itemtype, "KnowbaseItem")

    def test_unknown_attr_raises(self):
        api = _make_async_api()
        with self.assertRaises(AttributeError):
            _ = api.nonexistenttype_xyz

    def test_proxy_repr(self):
        api = _make_async_api()
        self.assertIn("Ticket", repr(api.ticket))


# ──────────────────────────────────────────────────────────────────────────────
# Async tests via pytest-asyncio
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_async_login_username_password():
    api = AsyncGlpiAPI(url="https://glpi.example.com")
    mock_cm = _mock_aiohttp_response(200, {"session_token": "async_tok"})

    with patch("aiohttp.ClientSession.request", return_value=mock_cm):
        await api.login(username="admin", password="secret")

    assert api._session_token == "async_tok"


@pytest.mark.asyncio
async def test_async_login_user_token():
    api = AsyncGlpiAPI(url="https://glpi.example.com")
    mock_cm = _mock_aiohttp_response(200, {"session_token": "user_tok_val"})

    with patch("aiohttp.ClientSession.request", return_value=mock_cm):
        await api.login(user_token="mypersonaltoken")

    assert api._session_token == "user_tok_val"


@pytest.mark.asyncio
async def test_async_login_no_credentials_raises():
    api = AsyncGlpiAPI(url="https://glpi.example.com")
    with pytest.raises(GlpiAuthError):
        await api.login()


@pytest.mark.asyncio
async def test_async_logout_clears_token():
    api = _make_async_api()
    mock_cm = _mock_aiohttp_response(200, {})

    with patch("aiohttp.ClientSession.request", return_value=mock_cm):
        await api.logout()

    assert api._session_token is None


@pytest.mark.asyncio
async def test_async_get_version():
    api = _make_async_api()
    mock_cm = _mock_aiohttp_response(200, {"glpi_version": "11.0.0"})

    with patch("aiohttp.ClientSession.request", return_value=mock_cm):
        v = await api.get_version()

    assert isinstance(v, GLPIVersion)
    assert v == "11.0.0"
    assert api.version == v  # cached


@pytest.mark.asyncio
async def test_async_get_item():
    api = _make_async_api()
    mock_cm = _mock_aiohttp_response(200, {"id": 1, "name": "Async ticket"})

    with patch("aiohttp.ClientSession.request", return_value=mock_cm):
        result = await api.get_item("Ticket", 1)

    assert result["id"] == 1


@pytest.mark.asyncio
async def test_async_get_all_items():
    api = _make_async_api()
    mock_cm = _mock_aiohttp_response(200, [{"id": 1}, {"id": 2}])

    with patch("aiohttp.ClientSession.request", return_value=mock_cm):
        result = await api.get_all_items("Ticket")

    assert len(result) == 2


@pytest.mark.asyncio
async def test_async_create_item():
    api = _make_async_api()
    mock_cm = _mock_aiohttp_response(201, {"id": 55, "message": ""})

    with patch("aiohttp.ClientSession.request", return_value=mock_cm):
        result = await api.create_item("Ticket", {"name": "New", "content": "x"})

    assert result["id"] == 55


@pytest.mark.asyncio
async def test_async_update_item():
    api = _make_async_api()
    mock_cm = _mock_aiohttp_response(200, [{"1": True}])

    with patch("aiohttp.ClientSession.request", return_value=mock_cm):
        result = await api.update_item("Ticket", {"id": 1, "name": "Updated"})

    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_async_delete_item():
    api = _make_async_api()
    mock_cm = _mock_aiohttp_response(200, [{"1": True}])

    with patch("aiohttp.ClientSession.request", return_value=mock_cm):
        result = await api.delete_item("Ticket", {"id": 1})

    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_async_get_sub_items():
    api = _make_async_api()
    mock_cm = _mock_aiohttp_response(200, [{"id": 1, "content": "note"}])

    with patch("aiohttp.ClientSession.request", return_value=mock_cm):
        result = await api.get_sub_items("Ticket", 10, "ITILFollowup")

    assert len(result) == 1


@pytest.mark.asyncio
async def test_async_add_sub_item():
    api = _make_async_api()
    mock_cm = _mock_aiohttp_response(201, {"id": 9})

    with patch("aiohttp.ClientSession.request", return_value=mock_cm):
        result = await api.add_sub_item("Ticket", 1, "ITILFollowup", {"content": "x"})

    assert result["id"] == 9


@pytest.mark.asyncio
async def test_async_proxy_get():
    api = _make_async_api()
    mock_cm = _mock_aiohttp_response(200, {"id": 3, "name": "via proxy"})

    with patch("aiohttp.ClientSession.request", return_value=mock_cm):
        result = await api.ticket.get(3)

    assert result["id"] == 3


@pytest.mark.asyncio
async def test_async_context_manager():
    mock_cm = _mock_aiohttp_response(200, {"session_token": "ctx_async"})

    with patch("aiohttp.ClientSession.request", return_value=mock_cm):
        async with AsyncGlpiAPI(url="https://glpi.example.com") as api:
            await api.login(username="a", password="b")
            logout_cm = _mock_aiohttp_response(200, {})
            with patch("aiohttp.ClientSession.request", return_value=logout_cm):
                pass  # exit will call logout

    assert api._session_token is None


@pytest.mark.asyncio
async def test_async_search():
    api = _make_async_api()
    mock_cm = _mock_aiohttp_response(200, {"totalcount": 10, "data": []})

    with patch("aiohttp.ClientSession.request", return_value=mock_cm):
        result = await api.search("Ticket")

    assert result["totalcount"] == 10
