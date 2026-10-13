"""
tests/test_glpi12.py
~~~~~~~~~~~~~~~~~~~~

Tests for GLPI 12 support in the High-Level API clients:

* ``api_version`` pinning (``/api.php/v2.3`` vs ``/api.php/v3.0``)
* ``start``/``limit`` pagination (the HL API ignores ``range``)
* route fixes (Timeline documents, software licenses)
* server version and API version discovery
* RSQL ``filter`` search

Behaviour was checked against live GLPI 11.0.9 and 12.0.0 instances.
All HTTP calls here are mocked.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from glpi_utils.oauth import (
    AsyncGlpiOAuthClient,
    GlpiOAuthClient,
    _hl_route,
    _hl_subitem_route,
    _normalize_api_version,
)


def _make_api(**kwargs) -> GlpiOAuthClient:
    api = GlpiOAuthClient(url="https://glpi.example.com", client_id="app", client_secret="s", **kwargs)
    api._token.store("tok", expires_in=3600)
    return api


def _resp(status=200, json_data=None, content_range=""):
    m = MagicMock()
    m.status_code = status
    m.content = b"x"
    m.json.return_value = json_data if json_data is not None else {}
    m.text = str(json_data)
    m.headers = {"Content-Range": content_range} if content_range else {}
    return m


# ──────────────────────────────────────────────────────────────────────────────
# API version pinning
# ──────────────────────────────────────────────────────────────────────────────

class TestNormalizeApiVersion(unittest.TestCase):

    def test_none_means_server_default(self):
        self.assertIsNone(_normalize_api_version(None))
        self.assertIsNone(_normalize_api_version(""))

    def test_major_only(self):
        self.assertEqual(_normalize_api_version("3"), "v3")
        self.assertEqual(_normalize_api_version(2), "v2")

    def test_major_minor(self):
        self.assertEqual(_normalize_api_version("2.3"), "v2.3")
        self.assertEqual(_normalize_api_version("v3.0"), "v3.0")
        self.assertEqual(_normalize_api_version("V3.0"), "v3.0")

    def test_float_input(self):
        self.assertEqual(_normalize_api_version(2.3), "v2.3")

    def test_legacy_v1_rejected(self):
        with self.assertRaises(ValueError):
            _normalize_api_version("1")

    def test_garbage_rejected(self):
        with self.assertRaises(ValueError):
            _normalize_api_version("latest")


class TestApiVersionUrls(unittest.TestCase):

    def test_default_is_unversioned(self):
        api = GlpiOAuthClient(url="https://glpi.example.com")
        self.assertEqual(api._api_url, "https://glpi.example.com/api.php")
        self.assertIsNone(api.api_version)

    def test_pinned_v3(self):
        api = GlpiOAuthClient(url="https://glpi.example.com", api_version="3.0")
        self.assertEqual(api._api_url, "https://glpi.example.com/api.php/v3.0")
        self.assertEqual(api.api_version, "v3.0")

    def test_pinned_v2(self):
        api = GlpiOAuthClient(url="https://glpi.example.com", api_version="2")
        self.assertEqual(api._api_url, "https://glpi.example.com/api.php/v2")

    def test_token_url_never_versioned(self):
        api = GlpiOAuthClient(url="https://glpi.example.com", api_version="3.0")
        self.assertEqual(api._token_url, "https://glpi.example.com/api.php/token")

    def test_env_var(self):
        with patch.dict(os.environ, {"GLPI_URL": "https://glpi.example.com", "GLPI_API_VERSION": "2.3"}):
            api = GlpiOAuthClient()
        self.assertEqual(api._api_url, "https://glpi.example.com/api.php/v2.3")

    def test_async_pinned(self):
        api = AsyncGlpiOAuthClient(url="https://glpi.example.com", api_version="v3.0")
        self.assertEqual(api._api_url, "https://glpi.example.com/api.php/v3.0")
        self.assertEqual(api._token_url, "https://glpi.example.com/api.php/token")

    @patch("requests.Session.request")
    def test_request_goes_to_pinned_prefix(self, mock_req):
        mock_req.return_value = _resp(200, {"id": 1})
        _make_api(api_version="3.0").get_item("Ticket", 1)
        self.assertEqual(mock_req.call_args[0][1], "https://glpi.example.com/api.php/v3.0/Assistance/Ticket/1")


# ──────────────────────────────────────────────────────────────────────────────
# Pagination: start / limit
# ──────────────────────────────────────────────────────────────────────────────

class TestStartLimitPagination(unittest.TestCase):

    @patch("requests.Session.request")
    def test_get_all_items_uses_start_limit(self, mock_req):
        mock_req.return_value = _resp(200, [{"id": 1}])
        _make_api().get_all_items("Ticket")
        params = mock_req.call_args[1]["params"]
        self.assertEqual(params["start"], 0)
        self.assertEqual(params["limit"], 50)
        self.assertNotIn("range", params)

    @patch("requests.Session.request")
    def test_range_kwarg_is_translated(self, mock_req):
        mock_req.return_value = _resp(200, [{"id": 1}])
        _make_api().get_all_items("Ticket", range="10-19")
        params = mock_req.call_args[1]["params"]
        self.assertEqual((params["start"], params["limit"]), (10, 10))
        self.assertNotIn("range", params)

    @patch("requests.Session.request")
    def test_explicit_start_limit_kept(self, mock_req):
        mock_req.return_value = _resp(200, [{"id": 1}])
        _make_api().get_all_items("Ticket", start=5, limit=3)
        params = mock_req.call_args[1]["params"]
        self.assertEqual((params["start"], params["limit"]), (5, 3))

    @patch("requests.Session.request")
    def test_iter_pages_advances_start(self, mock_req):
        mock_req.side_effect = [
            _resp(206, [{"id": 1}, {"id": 2}], "0-1/5"),
            _resp(206, [{"id": 3}, {"id": 4}], "2-3/5"),
            _resp(200, [{"id": 5}], "4-4/5"),
        ]
        items = _make_api().get_all_pages("User", page_size=2)
        self.assertEqual([i["id"] for i in items], [1, 2, 3, 4, 5])
        starts = [c[1]["params"]["start"] for c in mock_req.call_args_list]
        limits = {c[1]["params"]["limit"] for c in mock_req.call_args_list}
        self.assertEqual(starts, [0, 2, 4])
        self.assertEqual(limits, {2})
        for c in mock_req.call_args_list:
            self.assertNotIn("range", c[1]["params"])

    @patch("requests.Session.request")
    def test_iter_pages_does_not_mutate_between_pages(self, mock_req):
        """Each request must carry its own params dict (no shared mutation)."""
        mock_req.side_effect = [
            _resp(206, [{"id": 1}], "0-0/2"),
            _resp(200, [{"id": 2}], "1-1/2"),
        ]
        list(_make_api().iter_pages("User", page_size=1, filter="name=like=*a*"))
        first, second = (c[1]["params"] for c in mock_req.call_args_list)
        self.assertEqual(first["filter"], "name=like=*a*")
        self.assertEqual((first["start"], second["start"]), (0, 1))


def _async_resp(json_data, status=200, content_range=""):
    resp = MagicMock()
    resp.status = status
    resp.content_length = 100
    resp.headers = {"Content-Range": content_range} if content_range else {}
    resp.json = AsyncMock(return_value=json_data)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=resp)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


def _make_async_api(**kwargs) -> AsyncGlpiOAuthClient:
    api = AsyncGlpiOAuthClient(url="https://glpi.example.com", client_id="x", client_secret="y", **kwargs)
    api._token.store("tok", 3600)
    return api


@pytest.mark.asyncio
async def test_async_iter_pages_uses_start_limit():
    api = _make_async_api()
    responses = [
        _async_resp([{"id": 1}, {"id": 2}], 206, "0-1/3"),
        _async_resp([{"id": 3}], 200, "2-2/3"),
    ]
    with patch("aiohttp.ClientSession.request", side_effect=responses) as mock_req:
        items = await api.get_all_pages("User", page_size=2)
    assert [i["id"] for i in items] == [1, 2, 3]
    params = [c[1]["params"] for c in mock_req.call_args_list]
    assert [p["start"] for p in params] == [0, 2]
    assert all("range" not in p for p in params)


@pytest.mark.asyncio
async def test_async_pinned_version_in_url():
    api = _make_async_api(api_version="2.3")
    with patch("aiohttp.ClientSession.request", return_value=_async_resp({"id": 1})) as mock_req:
        await api.get_item("Ticket", 1)
    assert mock_req.call_args[0][1] == "https://glpi.example.com/api.php/v2.3/Assistance/Ticket/1"


# ──────────────────────────────────────────────────────────────────────────────
# Route fixes
# ──────────────────────────────────────────────────────────────────────────────

class TestRouteFixes(unittest.TestCase):

    def test_document_item_is_management(self):
        self.assertEqual(_hl_route("Document"), "Management/Document")

    def test_document_subitem_is_timeline(self):
        self.assertEqual(_hl_subitem_route("Document"), "Timeline/Document")

    def test_followup_subitem_is_timeline(self):
        self.assertEqual(_hl_subitem_route("ITILFollowup"), "Timeline/Followup")

    def test_unknown_subitem_falls_back_to_item_route(self):
        self.assertEqual(_hl_subitem_route("Infocom"), "Infocom")

    def test_software_license_is_management_license(self):
        # /Assets/SoftwareLicense was deprecated in v2.4 and removed in v3.0
        self.assertEqual(_hl_route("SoftwareLicense"), "Management/License")

    @patch("requests.Session.request")
    def test_add_document_to_ticket_timeline(self, mock_req):
        mock_req.return_value = _resp(201, {"id": 3})
        _make_api().add_sub_item("Ticket", 7, "Document", {"name": "log.txt"})
        self.assertIn("Assistance/Ticket/7/Timeline/Document", mock_req.call_args[0][1])


# ──────────────────────────────────────────────────────────────────────────────
# Discovery
# ──────────────────────────────────────────────────────────────────────────────

class TestDiscovery(unittest.TestCase):

    @patch("requests.Session.request")
    def test_get_version_reads_core_config(self, mock_req):
        mock_req.return_value = _resp(200, {"context": "core", "name": "version", "value": "12.0.0"})
        api = _make_api()
        v = api.get_version()
        self.assertEqual(str(v), "12.0.0")
        self.assertIs(api.version, v)
        self.assertIn("Setup/Config/core/version", mock_req.call_args[0][1])

    @patch("requests.Session.request")
    def test_get_api_versions(self, mock_req):
        mock_req.return_value = _resp(200, {
            "message": "Welcome to GLPI API",
            "api_versions": [
                {"api_version": "2", "version": "2.3.0", "endpoint": "http://x/api.php/v2.3"},
                {"api_version": "3", "version": "3.0.0", "endpoint": "http://x/api.php/v3.0"},
            ],
        })
        versions = _make_api(api_version="3.0").get_api_versions()
        self.assertEqual([v["version"] for v in versions], ["2.3.0", "3.0.0"])
        # Root listing is always read from the unversioned endpoint
        self.assertEqual(mock_req.call_args[0][1], "https://glpi.example.com/api.php/")


@pytest.mark.asyncio
async def test_async_get_version():
    api = _make_async_api()
    body = {"context": "core", "name": "version", "value": "11.0.9"}
    with patch("aiohttp.ClientSession.request", return_value=_async_resp(body)):
        v = await api.get_version()
    assert str(v) == "11.0.9"


# ──────────────────────────────────────────────────────────────────────────────
# Search (RSQL filter)
# ──────────────────────────────────────────────────────────────────────────────

class TestSearch(unittest.TestCase):

    @patch("requests.Session.request")
    def test_search_sends_filter_to_collection_route(self, mock_req):
        mock_req.return_value = _resp(200, [{"id": 1}])
        result = _make_api().search("Ticket", filter="status.id==1", limit=10)
        url = mock_req.call_args[0][1]
        params = mock_req.call_args[1]["params"]
        self.assertTrue(url.endswith("/api.php/Assistance/Ticket"))
        self.assertNotIn("search/", url)
        self.assertEqual(params["filter"], "status.id==1")
        self.assertEqual(params["limit"], 10)
        self.assertEqual(result, [{"id": 1}])


if __name__ == "__main__":
    unittest.main()
