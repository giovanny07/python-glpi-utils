"""
tests/test_glpi_utils.py
~~~~~~~~~~~~~~~~~~~~~~~~

Unit tests for python-glpi-utils.  These tests do NOT require a live GLPI
server – all HTTP calls are mocked.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from glpi_utils import GlpiAPI, GlpiAPIError, GlpiAuthError, GlpiNotFoundError
from glpi_utils.version import GLPIVersion


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _mock_response(status_code: int = 200, json_data=None, content: bool = True):
    mock = MagicMock()
    mock.status_code = status_code
    mock.content = content
    mock.json.return_value = json_data or {}
    mock.text = str(json_data)
    return mock


# ──────────────────────────────────────────────────────────────────────────────
# GLPIVersion tests
# ──────────────────────────────────────────────────────────────────────────────


class TestGLPIVersion(unittest.TestCase):
    def test_parse_full(self):
        v = GLPIVersion("11.0.3")
        self.assertEqual(v.major, 11)
        self.assertEqual(v.minor, 0)
        self.assertEqual(v.patch, 3)

    def test_parse_short(self):
        v = GLPIVersion("10.0")
        self.assertEqual(v.major, 10)
        self.assertEqual(v.minor, 0)
        self.assertEqual(v.patch, 0)

    def test_compare_gt(self):
        v = GLPIVersion("11.0.0")
        self.assertTrue(v > "10.0")
        self.assertTrue(v > 10.0)
        self.assertFalse(v > "11.0.0")

    def test_compare_eq(self):
        v = GLPIVersion("11.0.0")
        self.assertEqual(v, "11.0.0")
        self.assertEqual(v, 11.0)
        self.assertEqual(v, GLPIVersion("11.0.0"))

    def test_str(self):
        self.assertEqual(str(GLPIVersion("11.0.1")), "11.0.1")

    def test_repr(self):
        self.assertIn("11.0.1", repr(GLPIVersion("11.0.1")))

    def test_invalid(self):
        with self.assertRaises(ValueError):
            GLPIVersion("not-a-version")


# ──────────────────────────────────────────────────────────────────────────────
# GlpiAPI unit tests (mocked HTTP)
# ──────────────────────────────────────────────────────────────────────────────


class TestGlpiAPIInit(unittest.TestCase):
    def test_missing_url(self):
        with self.assertRaises(ValueError):
            GlpiAPI(url="")

    def test_url_normalised(self):
        api = GlpiAPI(url="https://glpi.example.com/")
        self.assertEqual(api._url, "https://glpi.example.com")


class TestGlpiAPIAuth(unittest.TestCase):
    def _make_api(self) -> GlpiAPI:
        return GlpiAPI(url="https://glpi.example.com", app_token="testtoken")

    @patch("requests.Session.request")
    def test_login_username_password(self, mock_req):
        mock_req.return_value = _mock_response(200, {"session_token": "abc123"})
        api = self._make_api()
        api.login(username="admin", password="secret")
        self.assertEqual(api._session_token, "abc123")

    @patch("requests.Session.request")
    def test_login_user_token(self, mock_req):
        mock_req.return_value = _mock_response(200, {"session_token": "tok999"})
        api = self._make_api()
        api.login(user_token="mytoken")
        self.assertEqual(api._session_token, "tok999")

    def test_login_no_credentials(self):
        api = self._make_api()
        with self.assertRaises(GlpiAuthError):
            api.login()

    @patch("requests.Session.request")
    def test_logout(self, mock_req):
        mock_req.return_value = _mock_response(200, {"session_token": "abc"})
        api = self._make_api()
        api.login(username="a", password="b")
        mock_req.return_value = _mock_response(200, {})
        api.logout()
        self.assertIsNone(api._session_token)


class TestGlpiAPIErrors(unittest.TestCase):
    def _make_api(self) -> GlpiAPI:
        api = GlpiAPI(url="https://glpi.example.com")
        api._session_token = "fake_token"
        return api

    @patch("requests.Session.request")
    def test_404_raises_not_found(self, mock_req):
        mock_req.return_value = _mock_response(
            404, ["ERROR_ITEM_NOT_FOUND", "Item not found"]
        )
        api = self._make_api()
        with self.assertRaises(GlpiNotFoundError):
            api.get_item("Ticket", 9999)

    @patch("requests.Session.request")
    def test_401_raises_auth_error(self, mock_req):
        mock_req.return_value = _mock_response(
            401, ["ERROR_SESSION_TOKEN_INVALID", "Bad token"]
        )
        api = self._make_api()
        with self.assertRaises(GlpiAuthError):
            api.get_item("Ticket", 1)

    @patch("requests.Session.request")
    def test_500_raises_api_error(self, mock_req):
        mock_req.return_value = _mock_response(
            500, ["ERROR_GLPI_SQL", "SQL error"]
        )
        api = self._make_api()
        with self.assertRaises(GlpiAPIError):
            api.get_item("Ticket", 1)


class TestGlpiAPIItemCRUD(unittest.TestCase):
    def _make_api(self) -> GlpiAPI:
        api = GlpiAPI(url="https://glpi.example.com")
        api._session_token = "fake_token"
        return api

    @patch("requests.Session.request")
    def test_get_item(self, mock_req):
        ticket_data = {"id": 1, "name": "Test ticket", "status": 1}
        mock_req.return_value = _mock_response(200, ticket_data)
        api = self._make_api()
        result = api.get_item("Ticket", 1)
        self.assertEqual(result["id"], 1)

    @patch("requests.Session.request")
    def test_get_all_items(self, mock_req):
        tickets = [{"id": 1, "name": "T1"}, {"id": 2, "name": "T2"}]
        mock_req.return_value = _mock_response(200, tickets)
        api = self._make_api()
        result = api.get_all_items("Ticket")
        self.assertEqual(len(result), 2)

    @patch("requests.Session.request")
    def test_create_item(self, mock_req):
        mock_req.return_value = _mock_response(201, {"id": 42, "message": ""})
        api = self._make_api()
        result = api.create_item("Ticket", {"name": "New ticket", "content": "desc"})
        self.assertEqual(result["id"], 42)

    @patch("requests.Session.request")
    def test_update_item(self, mock_req):
        mock_req.return_value = _mock_response(200, [{"1": True, "message": ""}])
        api = self._make_api()
        result = api.update_item("Ticket", {"id": 1, "name": "Updated"})
        self.assertIsInstance(result, list)

    @patch("requests.Session.request")
    def test_delete_item(self, mock_req):
        mock_req.return_value = _mock_response(200, [{"1": True, "message": ""}])
        api = self._make_api()
        result = api.delete_item("Ticket", {"id": 1})
        self.assertIsInstance(result, list)


class TestItemProxy(unittest.TestCase):
    def _make_api(self) -> GlpiAPI:
        api = GlpiAPI(url="https://glpi.example.com")
        api._session_token = "fake_token"
        return api

    @patch("requests.Session.request")
    def test_ticket_proxy_get(self, mock_req):
        mock_req.return_value = _mock_response(200, {"id": 5, "name": "Demo"})
        api = self._make_api()
        result = api.ticket.get(5)
        self.assertEqual(result["id"], 5)

    def test_unknown_attr_raises(self):
        api = self._make_api()
        with self.assertRaises(AttributeError):
            _ = api.nonexistentitemtype_xyz

    def test_item_method_returns_proxy(self):
        api = self._make_api()
        proxy = api.item("KnowbaseItem")
        self.assertEqual(proxy._itemtype, "KnowbaseItem")


class TestContextManager(unittest.TestCase):
    @patch("requests.Session.request")
    def test_context_manager_calls_logout(self, mock_req):
        mock_req.return_value = _mock_response(200, {"session_token": "ctx_tok"})
        with GlpiAPI(url="https://glpi.example.com") as api:
            api.login(username="a", password="b")
            mock_req.return_value = _mock_response(200, {})
        # After __exit__, session token should be cleared
        self.assertIsNone(api._session_token)


if __name__ == "__main__":
    unittest.main()
