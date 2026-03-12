"""
tests/test_exceptions.py
~~~~~~~~~~~~~~~~~~~~~~~~

Tests for the exception hierarchy.
"""

from __future__ import annotations

import unittest

from glpi_utils.exceptions import (
    GlpiAPIError,
    GlpiAuthError,
    GlpiConnectionError,
    GlpiError,
    GlpiNotFoundError,
    GlpiPermissionError,
)


class TestExceptionHierarchy(unittest.TestCase):

    def test_glpi_api_error_is_glpi_error(self):
        self.assertTrue(issubclass(GlpiAPIError, GlpiError))

    def test_glpi_auth_error_is_glpi_api_error(self):
        self.assertTrue(issubclass(GlpiAuthError, GlpiAPIError))

    def test_glpi_not_found_is_glpi_api_error(self):
        self.assertTrue(issubclass(GlpiNotFoundError, GlpiAPIError))

    def test_glpi_permission_error_is_glpi_api_error(self):
        self.assertTrue(issubclass(GlpiPermissionError, GlpiAPIError))

    def test_glpi_connection_error_is_glpi_error(self):
        self.assertTrue(issubclass(GlpiConnectionError, GlpiError))

    def test_all_catchable_as_glpi_error(self):
        exceptions = [
            GlpiAPIError("msg"),
            GlpiAuthError("msg"),
            GlpiNotFoundError("msg"),
            GlpiPermissionError("msg"),
            GlpiConnectionError("msg"),
        ]
        for exc in exceptions:
            self.assertIsInstance(exc, GlpiError)


class TestGlpiAPIErrorAttributes(unittest.TestCase):

    def test_message_stored(self):
        exc = GlpiAPIError("Something went wrong")
        self.assertEqual(exc.message, "Something went wrong")

    def test_status_code_stored(self):
        exc = GlpiAPIError("err", status_code=500)
        self.assertEqual(exc.status_code, 500)

    def test_error_code_stored(self):
        exc = GlpiAPIError("err", error_code="ERROR_GLPI_SQL")
        self.assertEqual(exc.error_code, "ERROR_GLPI_SQL")

    def test_defaults_are_none(self):
        exc = GlpiAPIError("err")
        self.assertIsNone(exc.status_code)
        self.assertIsNone(exc.error_code)

    def test_repr_contains_status_and_code(self):
        exc = GlpiAPIError("err", status_code=404, error_code="ERROR_ITEM_NOT_FOUND")
        r = repr(exc)
        self.assertIn("404", r)
        self.assertIn("ERROR_ITEM_NOT_FOUND", r)

    def test_str_is_message(self):
        exc = GlpiAPIError("Something went wrong", status_code=500)
        self.assertEqual(str(exc), "Something went wrong")

    def test_auth_error_attributes(self):
        exc = GlpiAuthError("Bad creds", status_code=401, error_code="ERROR_SESSION_TOKEN_INVALID")
        self.assertEqual(exc.status_code, 401)
        self.assertIsInstance(exc, GlpiAPIError)

    def test_not_found_attributes(self):
        exc = GlpiNotFoundError("Not found", status_code=404, error_code="ERROR_ITEM_NOT_FOUND")
        self.assertEqual(exc.status_code, 404)

    def test_permission_error_attributes(self):
        exc = GlpiPermissionError("No rights", status_code=403)
        self.assertEqual(exc.status_code, 403)

    def test_connection_error_is_plain(self):
        exc = GlpiConnectionError("Cannot reach server")
        self.assertEqual(str(exc), "Cannot reach server")


if __name__ == "__main__":
    unittest.main()
