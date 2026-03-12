"""
tests/test_api.py
~~~~~~~~~~~~~~~~~

Tests for GlpiAPI (synchronous client).
All HTTP calls are mocked – no live GLPI server required.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, call, patch

import requests

from glpi_utils import GlpiAPI, GlpiAPIError, GlpiAuthError, GlpiNotFoundError
from glpi_utils.exceptions import GlpiConnectionError, GlpiPermissionError
from glpi_utils.version import GLPIVersion

from .common import make_api, mock_response


# ──────────────────────────────────────────────────────────────────────────────
# Initialisation
# ──────────────────────────────────────────────────────────────────────────────


class TestGlpiAPIInit(unittest.TestCase):

    def test_missing_url_raises(self):
        with self.assertRaises(ValueError):
            GlpiAPI(url="")

    def test_missing_url_no_env_raises(self):
        with patch.dict(os.environ, {}, clear=True):
            # Ensure GLPI_URL is not set
            os.environ.pop("GLPI_URL", None)
            with self.assertRaises(ValueError):
                GlpiAPI()

    def test_url_trailing_slash_stripped(self):
        api = GlpiAPI(url="https://glpi.example.com/")
        self.assertEqual(api._url, "https://glpi.example.com")

    def test_url_from_env(self):
        with patch.dict(os.environ, {"GLPI_URL": "https://env.example.com"}):
            api = GlpiAPI()
            self.assertEqual(api._url, "https://env.example.com")

    def test_app_token_from_env(self):
        with patch.dict(os.environ, {
            "GLPI_URL": "https://env.example.com",
            "GLPI_APP_TOKEN": "envtoken",
        }):
            api = GlpiAPI()
            self.assertEqual(api._app_token, "envtoken")

    def test_base_url_property(self):
        api = GlpiAPI(url="https://glpi.example.com")
        self.assertEqual(api._base_url, "https://glpi.example.com/apirest.php")

    def test_default_headers_include_content_type(self):
        api = make_api()
        headers = api._default_headers()
        self.assertEqual(headers["Content-Type"], "application/json")

    def test_default_headers_include_app_token(self):
        api = make_api()
        headers = api._default_headers()
        self.assertEqual(headers["App-Token"], "testapptoken")

    def test_default_headers_include_session_token(self):
        api = make_api(session_token="mysession")
        headers = api._default_headers()
        self.assertEqual(headers["Session-Token"], "mysession")


# ──────────────────────────────────────────────────────────────────────────────
# Authentication
# ──────────────────────────────────────────────────────────────────────────────


class TestGlpiAPIAuthentication(unittest.TestCase):

    @patch("requests.Session.request")
    def test_login_username_password(self, mock_req):
        mock_req.return_value = mock_response(200, {"session_token": "abc123"})
        api = GlpiAPI(url="https://glpi.example.com")
        api.login(username="admin", password="secret")
        self.assertEqual(api._session_token, "abc123")

    @patch("requests.Session.request")
    def test_login_user_token(self, mock_req):
        mock_req.return_value = mock_response(200, {"session_token": "tok999"})
        api = GlpiAPI(url="https://glpi.example.com")
        api.login(user_token="myusertoken")
        self.assertEqual(api._session_token, "tok999")

    @patch("requests.Session.request")
    def test_login_from_env_vars(self, mock_req):
        mock_req.return_value = mock_response(200, {"session_token": "envtok"})
        with patch.dict(os.environ, {
            "GLPI_URL": "https://glpi.example.com",
            "GLPI_USER": "envuser",
            "GLPI_PASSWORD": "envpass",
        }):
            api = GlpiAPI()
            api.login()
            self.assertEqual(api._session_token, "envtok")

    def test_login_no_credentials_raises(self):
        api = GlpiAPI(url="https://glpi.example.com")
        with self.assertRaises(GlpiAuthError):
            api.login()

    @patch("requests.Session.request")
    def test_login_sets_basic_auth_header(self, mock_req):
        mock_req.return_value = mock_response(200, {"session_token": "x"})
        api = GlpiAPI(url="https://glpi.example.com")
        api.login(username="user", password="pass")
        call_kwargs = mock_req.call_args
        auth_header = call_kwargs[1]["headers"].get("Authorization", "")
        self.assertTrue(auth_header.startswith("Basic "))

    @patch("requests.Session.request")
    def test_login_sets_user_token_header(self, mock_req):
        mock_req.return_value = mock_response(200, {"session_token": "x"})
        api = GlpiAPI(url="https://glpi.example.com")
        api.login(user_token="mytok")
        call_kwargs = mock_req.call_args
        auth_header = call_kwargs[1]["headers"].get("Authorization", "")
        self.assertEqual(auth_header, "user_token mytok")

    @patch("requests.Session.request")
    def test_logout_clears_session_token(self, mock_req):
        mock_req.return_value = mock_response(200, {"session_token": "abc"})
        api = GlpiAPI(url="https://glpi.example.com")
        api.login(username="a", password="b")
        mock_req.return_value = mock_response(200, {})
        api.logout()
        self.assertIsNone(api._session_token)

    @patch("requests.Session.request")
    def test_logout_without_session_is_noop(self, mock_req):
        api = GlpiAPI(url="https://glpi.example.com")
        api.logout()  # should not raise
        mock_req.assert_not_called()

    @patch("requests.Session.request")
    def test_context_manager_calls_logout(self, mock_req):
        mock_req.return_value = mock_response(200, {"session_token": "ctx"})
        with GlpiAPI(url="https://glpi.example.com") as api:
            api.login(username="a", password="b")
            mock_req.return_value = mock_response(200, {})
        self.assertIsNone(api._session_token)

    @patch("requests.Session.request")
    def test_context_manager_survives_logout_error(self, mock_req):
        mock_req.return_value = mock_response(200, {"session_token": "ctx"})
        with GlpiAPI(url="https://glpi.example.com") as api:
            api.login(username="a", password="b")
            # Simulate logout failure
            mock_req.side_effect = Exception("network gone")
        # Should not propagate the exception
        self.assertIsNone(api._session_token)


# ──────────────────────────────────────────────────────────────────────────────
# Error handling
# ──────────────────────────────────────────────────────────────────────────────


class TestGlpiAPIErrorHandling(unittest.TestCase):

    def setUp(self):
        self.api = make_api()

    @patch("requests.Session.request")
    def test_404_raises_not_found(self, mock_req):
        mock_req.return_value = mock_response(404, ["ERROR_ITEM_NOT_FOUND", "Item not found"])
        with self.assertRaises(GlpiNotFoundError) as ctx:
            self.api.get_item("Ticket", 9999)
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.error_code, "ERROR_ITEM_NOT_FOUND")

    @patch("requests.Session.request")
    def test_401_raises_auth_error(self, mock_req):
        mock_req.return_value = mock_response(
            401, ["ERROR_SESSION_TOKEN_INVALID", "Bad token"]
        )
        with self.assertRaises(GlpiAuthError) as ctx:
            self.api.get_item("Ticket", 1)
        self.assertEqual(ctx.exception.status_code, 401)

    @patch("requests.Session.request")
    def test_403_raises_permission_error(self, mock_req):
        mock_req.return_value = mock_response(403, ["ERROR_RIGHT_MISSING", "No rights"])
        with self.assertRaises(GlpiPermissionError):
            self.api.get_item("Ticket", 1)

    @patch("requests.Session.request")
    def test_500_raises_api_error(self, mock_req):
        mock_req.return_value = mock_response(500, ["ERROR_GLPI_SQL", "SQL error"])
        with self.assertRaises(GlpiAPIError) as ctx:
            self.api.get_item("Ticket", 1)
        self.assertEqual(ctx.exception.status_code, 500)

    @patch("requests.Session.request")
    def test_api_error_has_message_attribute(self, mock_req):
        mock_req.return_value = mock_response(500, ["ERROR_GLPI_SQL", "A SQL error occurred"])
        with self.assertRaises(GlpiAPIError) as ctx:
            self.api.get_item("Ticket", 1)
        self.assertEqual(ctx.exception.message, "A SQL error occurred")

    @patch("requests.Session.request")
    def test_connection_error_raises_glpi_connection_error(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("refused")
        with self.assertRaises(GlpiConnectionError):
            self.api.get_item("Ticket", 1)

    @patch("requests.Session.request")
    def test_timeout_raises_glpi_connection_error(self, mock_req):
        mock_req.side_effect = requests.exceptions.Timeout("timed out")
        with self.assertRaises(GlpiConnectionError):
            self.api.get_item("Ticket", 1)

    @patch("requests.Session.request")
    def test_204_returns_none(self, mock_req):
        mock_req.return_value = mock_response(204, content=False)
        result = self.api.get_item("Ticket", 1)
        self.assertIsNone(result)

    @patch("requests.Session.request")
    def test_error_repr_contains_key_info(self, mock_req):
        mock_req.return_value = mock_response(404, ["ERROR_ITEM_NOT_FOUND", "Not found"])
        with self.assertRaises(GlpiNotFoundError) as ctx:
            self.api.get_item("Ticket", 1)
        r = repr(ctx.exception)
        self.assertIn("404", r)
        self.assertIn("ERROR_ITEM_NOT_FOUND", r)


# ──────────────────────────────────────────────────────────────────────────────
# Version
# ──────────────────────────────────────────────────────────────────────────────


class TestGlpiAPIVersion(unittest.TestCase):

    @patch("requests.Session.request")
    def test_version_returns_glpiversion(self, mock_req):
        mock_req.return_value = mock_response(200, {"glpi_version": "11.0.0"})
        api = make_api()
        v = api.version
        self.assertIsInstance(v, GLPIVersion)
        self.assertEqual(v, "11.0.0")

    @patch("requests.Session.request")
    def test_version_cached_after_first_call(self, mock_req):
        mock_req.return_value = mock_response(200, {"glpi_version": "11.0.0"})
        api = make_api()
        _ = api.version
        _ = api.version
        # Should only call the API once
        self.assertEqual(mock_req.call_count, 1)

    @patch("requests.Session.request")
    def test_version_comparison_works(self, mock_req):
        mock_req.return_value = mock_response(200, {"glpi_version": "11.0.0"})
        api = make_api()
        self.assertTrue(api.version > 10.0)
        self.assertTrue(api.version >= "11.0.0")


# ──────────────────────────────────────────────────────────────────────────────
# CRUD operations
# ──────────────────────────────────────────────────────────────────────────────


class TestGlpiAPIItemCRUD(unittest.TestCase):

    def setUp(self):
        self.api = make_api()

    @patch("requests.Session.request")
    def test_get_item_returns_dict(self, mock_req):
        mock_req.return_value = mock_response(200, {"id": 1, "name": "Test"})
        result = self.api.get_item("Ticket", 1)
        self.assertEqual(result["id"], 1)

    @patch("requests.Session.request")
    def test_get_item_passes_kwargs_as_params(self, mock_req):
        mock_req.return_value = mock_response(200, {"id": 1})
        self.api.get_item("Ticket", 1, expand_dropdowns=True)
        params = mock_req.call_args[1]["params"]
        self.assertEqual(params.get("expand_dropdowns"), 1)

    @patch("requests.Session.request")
    def test_get_item_bool_params_converted_to_int(self, mock_req):
        mock_req.return_value = mock_response(200, {"id": 1})
        self.api.get_item("Ticket", 1, with_logs=True, is_deleted=False)
        params = mock_req.call_args[1]["params"]
        self.assertEqual(params["with_logs"], 1)
        self.assertEqual(params["is_deleted"], 0)

    @patch("requests.Session.request")
    def test_get_all_items_returns_list(self, mock_req):
        mock_req.return_value = mock_response(200, [{"id": 1}, {"id": 2}])
        result = self.api.get_all_items("Ticket")
        self.assertEqual(len(result), 2)

    @patch("requests.Session.request")
    def test_get_all_items_default_range(self, mock_req):
        mock_req.return_value = mock_response(200, [])
        self.api.get_all_items("Ticket")
        params = mock_req.call_args[1]["params"]
        self.assertEqual(params["range"], "0-49")

    @patch("requests.Session.request")
    def test_get_all_items_custom_range(self, mock_req):
        mock_req.return_value = mock_response(200, [])
        self.api.get_all_items("Ticket", range="50-99")
        params = mock_req.call_args[1]["params"]
        self.assertEqual(params["range"], "50-99")

    @patch("requests.Session.request")
    def test_create_item_single(self, mock_req):
        mock_req.return_value = mock_response(201, {"id": 42, "message": ""})
        result = self.api.create_item("Ticket", {"name": "New", "content": "desc"})
        self.assertEqual(result["id"], 42)

    @patch("requests.Session.request")
    def test_create_item_sends_input_key(self, mock_req):
        mock_req.return_value = mock_response(201, {"id": 1})
        self.api.create_item("Ticket", {"name": "T"})
        payload = mock_req.call_args[1]["json"]
        self.assertIn("input", payload)

    @patch("requests.Session.request")
    def test_create_item_bulk(self, mock_req):
        mock_req.return_value = mock_response(201, [{"id": 1}, {"id": 2}])
        result = self.api.create_item("Ticket", [{"name": "T1"}, {"name": "T2"}])
        self.assertIsInstance(result, list)

    @patch("requests.Session.request")
    def test_update_item(self, mock_req):
        mock_req.return_value = mock_response(200, [{"1": True, "message": ""}])
        result = self.api.update_item("Ticket", {"id": 1, "name": "Updated"})
        self.assertIsInstance(result, list)

    @patch("requests.Session.request")
    def test_update_uses_put_method(self, mock_req):
        mock_req.return_value = mock_response(200, [{"1": True}])
        self.api.update_item("Ticket", {"id": 1, "name": "x"})
        self.assertEqual(mock_req.call_args[0][0], "PUT")

    @patch("requests.Session.request")
    def test_delete_item(self, mock_req):
        mock_req.return_value = mock_response(200, [{"1": True}])
        result = self.api.delete_item("Ticket", {"id": 1})
        self.assertIsInstance(result, list)

    @patch("requests.Session.request")
    def test_delete_force_purge_sent(self, mock_req):
        mock_req.return_value = mock_response(200, [{"1": True}])
        self.api.delete_item("Ticket", {"id": 1}, force_purge=True)
        payload = mock_req.call_args[1]["json"]
        self.assertEqual(payload["force_purge"], 1)

    @patch("requests.Session.request")
    def test_delete_uses_delete_method(self, mock_req):
        mock_req.return_value = mock_response(200, [{"1": True}])
        self.api.delete_item("Ticket", {"id": 1})
        self.assertEqual(mock_req.call_args[0][0], "DELETE")

    @patch("requests.Session.request")
    def test_search_returns_dict(self, mock_req):
        mock_req.return_value = mock_response(200, {"totalcount": 5, "data": []})
        result = self.api.search("Ticket")
        self.assertIsInstance(result, dict)
        self.assertEqual(result["totalcount"], 5)


# ──────────────────────────────────────────────────────────────────────────────
# Sub-items
# ──────────────────────────────────────────────────────────────────────────────


class TestGlpiAPISubItems(unittest.TestCase):

    def setUp(self):
        self.api = make_api()

    @patch("requests.Session.request")
    def test_get_sub_items(self, mock_req):
        followups = [{"id": 1, "content": "First note"}, {"id": 2, "content": "Second note"}]
        mock_req.return_value = mock_response(200, followups)
        result = self.api.get_sub_items("Ticket", 10, "ITILFollowup")
        self.assertEqual(len(result), 2)

    @patch("requests.Session.request")
    def test_get_sub_items_url_structure(self, mock_req):
        mock_req.return_value = mock_response(200, [])
        self.api.get_sub_items("Ticket", 10, "ITILFollowup")
        url = mock_req.call_args[0][1]
        self.assertIn("Ticket/10/ITILFollowup", url)

    @patch("requests.Session.request")
    def test_add_sub_item(self, mock_req):
        mock_req.return_value = mock_response(201, {"id": 5, "message": ""})
        result = self.api.add_sub_item(
            "Ticket", 10, "ITILFollowup", {"content": "Added note", "is_private": 0}
        )
        self.assertEqual(result["id"], 5)

    @patch("requests.Session.request")
    def test_add_sub_item_uses_post(self, mock_req):
        mock_req.return_value = mock_response(201, {"id": 1})
        self.api.add_sub_item("Ticket", 1, "ITILFollowup", {"content": "x"})
        self.assertEqual(mock_req.call_args[0][0], "POST")


# ──────────────────────────────────────────────────────────────────────────────
# Session utilities
# ──────────────────────────────────────────────────────────────────────────────


class TestGlpiAPISessionUtils(unittest.TestCase):

    def setUp(self):
        self.api = make_api()

    @patch("requests.Session.request")
    def test_get_my_profiles(self, mock_req):
        mock_req.return_value = mock_response(
            200, {"myprofiles": [{"id": 1, "name": "Super-Admin"}]}
        )
        profiles = self.api.get_my_profiles()
        self.assertEqual(profiles[0]["name"], "Super-Admin")

    @patch("requests.Session.request")
    def test_get_active_profile(self, mock_req):
        mock_req.return_value = mock_response(
            200, {"active_profile": {"id": 4, "name": "Technician"}}
        )
        profile = self.api.get_active_profile()
        self.assertEqual(profile["name"], "Technician")

    @patch("requests.Session.request")
    def test_get_my_entities(self, mock_req):
        mock_req.return_value = mock_response(
            200, {"myentities": [{"id": 0, "name": "Root entity"}]}
        )
        entities = self.api.get_my_entities()
        self.assertEqual(entities[0]["id"], 0)

    @patch("requests.Session.request")
    def test_get_my_entities_recursive_param(self, mock_req):
        mock_req.return_value = mock_response(200, {"myentities": []})
        self.api.get_my_entities(is_recursive=True)
        params = mock_req.call_args[1]["params"]
        self.assertEqual(params["is_recursive"], 1)

    @patch("requests.Session.request")
    def test_get_full_session(self, mock_req):
        mock_req.return_value = mock_response(200, {"session": {"glpi_plugins": []}})
        session = self.api.get_full_session()
        self.assertIn("glpi_plugins", session)


# ──────────────────────────────────────────────────────────────────────────────
# ItemProxy fluent interface
# ──────────────────────────────────────────────────────────────────────────────


class TestItemProxy(unittest.TestCase):

    def setUp(self):
        self.api = make_api()

    @patch("requests.Session.request")
    def test_ticket_proxy_get(self, mock_req):
        mock_req.return_value = mock_response(200, {"id": 5, "name": "Demo"})
        result = self.api.ticket.get(5)
        self.assertEqual(result["id"], 5)

    @patch("requests.Session.request")
    def test_ticket_proxy_get_all(self, mock_req):
        mock_req.return_value = mock_response(200, [{"id": 1}, {"id": 2}])
        result = self.api.ticket.get_all()
        self.assertEqual(len(result), 2)

    @patch("requests.Session.request")
    def test_ticket_proxy_create(self, mock_req):
        mock_req.return_value = mock_response(201, {"id": 99})
        result = self.api.ticket.create({"name": "T", "content": "C"})
        self.assertEqual(result["id"], 99)

    @patch("requests.Session.request")
    def test_ticket_proxy_update(self, mock_req):
        mock_req.return_value = mock_response(200, [{"1": True}])
        result = self.api.ticket.update({"id": 1, "name": "Updated"})
        self.assertIsInstance(result, list)

    @patch("requests.Session.request")
    def test_ticket_proxy_delete(self, mock_req):
        mock_req.return_value = mock_response(200, [{"1": True}])
        result = self.api.ticket.delete({"id": 1})
        self.assertIsInstance(result, list)

    @patch("requests.Session.request")
    def test_ticket_proxy_delete_force_purge(self, mock_req):
        mock_req.return_value = mock_response(200, [{"1": True}])
        self.api.ticket.delete({"id": 1}, force_purge=True)
        payload = mock_req.call_args[1]["json"]
        self.assertEqual(payload["force_purge"], 1)

    @patch("requests.Session.request")
    def test_computer_proxy(self, mock_req):
        mock_req.return_value = mock_response(200, {"id": 3, "name": "SRV-01"})
        result = self.api.computer.get(3)
        self.assertEqual(result["name"], "SRV-01")

    @patch("requests.Session.request")
    def test_proxy_add_sub_item(self, mock_req):
        mock_req.return_value = mock_response(201, {"id": 7})
        result = self.api.ticket.add_sub_item(1, "ITILFollowup", {"content": "note"})
        self.assertEqual(result["id"], 7)

    @patch("requests.Session.request")
    def test_proxy_get_sub_items(self, mock_req):
        mock_req.return_value = mock_response(200, [{"id": 1}, {"id": 2}])
        result = self.api.ticket.get_sub_items(1, "ITILFollowup")
        self.assertEqual(len(result), 2)

    def test_unknown_attr_raises_attribute_error(self):
        with self.assertRaises(AttributeError):
            _ = self.api.nonexistentitemtype_xyz

    def test_item_method_returns_proxy_for_custom_type(self):
        proxy = self.api.item("KnowbaseItem")
        self.assertEqual(proxy._itemtype, "KnowbaseItem")

    def test_proxy_cached(self):
        proxy1 = self.api.ticket
        proxy2 = self.api.ticket
        self.assertIs(proxy1, proxy2)

    def test_all_builtin_aliases_resolve(self):
        expected_aliases = [
            "ticket", "computer", "monitor", "printer", "networkequipment",
            "software", "user", "group", "entity", "location", "category",
            "problem", "change", "project", "projecttask", "document",
            "contract", "supplier", "contact", "knowledgebase",
            "followup", "solution", "task", "validation", "log",
        ]
        for alias in expected_aliases:
            proxy = getattr(self.api, alias)
            self.assertIsNotNone(proxy, f"Alias '{alias}' returned None")

    def test_proxy_repr(self):
        self.assertIn("Ticket", repr(self.api.ticket))


if __name__ == "__main__":
    unittest.main()
