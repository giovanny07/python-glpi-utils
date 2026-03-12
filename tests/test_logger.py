"""
tests/test_logger.py
~~~~~~~~~~~~~~~~~~~~

Tests for SensitiveFilter, EmptyHandler, mask_secret, and hide_sensitive.
"""

from __future__ import annotations

import logging
import unittest

from glpi_utils.logger import EmptyHandler, SensitiveFilter, hide_sensitive, mask_secret


class TestMaskSecret(unittest.TestCase):

    def test_long_value_shows_ends(self):
        result = mask_secret("q56hqkniwot8wntb3z1qarka5atf365taaa2uyjrn")
        self.assertTrue(result.startswith("q56h"))
        self.assertTrue(result.endswith("jrn"))  # last 4 would be "jrn" but 4 chars = "jrna"
        self.assertIn("****", result)

    def test_short_value_returns_mask(self):
        self.assertEqual(mask_secret("abc"), "********")

    def test_empty_returns_mask(self):
        self.assertEqual(mask_secret(""), "********")

    def test_exact_threshold_returns_mask(self):
        # value length <= mask_len + show_len*2 → full mask
        result = mask_secret("12345678", show_len=4)
        self.assertEqual(result, "********")

    def test_zero_show_len(self):
        self.assertEqual(mask_secret("supersecret", show_len=0), "********")

    def test_long_token_partially_visible(self):
        token = "a" * 32
        result = mask_secret(token, show_len=4)
        self.assertTrue(result.startswith("aaaa"))
        self.assertTrue(result.endswith("aaaa"))
        self.assertIn("****", result)


class TestHideSensitive(unittest.TestCase):

    def test_masks_password_key(self):
        data = {"username": "admin", "password": "supersecret"}
        result = hide_sensitive(data)
        self.assertEqual(result["username"], "admin")
        self.assertNotEqual(result["password"], "supersecret")
        self.assertIn("*", result["password"])

    def test_masks_token_key(self):
        data = {"token": "abc123token"}
        result = hide_sensitive(data)
        self.assertIn("*", result["token"])

    def test_masks_user_token_key(self):
        data = {"user_token": "q56hqkniwot8wntb3z1qarka5atf365taaa2uyjrn"}
        result = hide_sensitive(data)
        self.assertIn("*", result["user_token"])

    def test_masks_authorization_key(self):
        data = {"Authorization": "Basic dXNlcjpwYXNz"}
        result = hide_sensitive(data)
        self.assertIn("*", result["Authorization"])

    def test_masks_session_token_key(self):
        data = {"session_token": "abc123abc123abc123abc123abc123ab"}
        result = hide_sensitive(data)
        self.assertIn("*", result["session_token"])

    def test_masks_app_token_key(self):
        data = {"App-Token": "mytoken123"}
        result = hide_sensitive(data)
        self.assertIn("*", result["App-Token"])

    def test_non_sensitive_keys_untouched(self):
        data = {"id": 1, "name": "Test ticket", "status": 4}
        result = hide_sensitive(data)
        self.assertEqual(result, data)

    def test_nested_dict(self):
        data = {"user": {"password": "secret", "id": 5}}
        result = hide_sensitive(data)
        self.assertIn("*", result["user"]["password"])
        self.assertEqual(result["user"]["id"], 5)

    def test_list_of_dicts(self):
        data = [{"password": "x"}, {"name": "ok"}]
        result = hide_sensitive(data)
        self.assertIn("*", result[0]["password"])
        self.assertEqual(result[1]["name"], "ok")

    def test_tuple_preserved(self):
        data = ({"password": "x"},)
        result = hide_sensitive(data)
        self.assertIsInstance(result, tuple)
        self.assertIn("*", result[0]["password"])

    def test_raw_hex_token_masked(self):
        # 32-char hex string that looks like a session token
        token = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4"
        result = hide_sensitive(token)
        self.assertIn("*", result)

    def test_regular_string_untouched(self):
        self.assertEqual(hide_sensitive("hello world"), "hello world")

    def test_scalar_int_untouched(self):
        self.assertEqual(hide_sensitive(42), 42)

    def test_none_untouched(self):
        self.assertIsNone(hide_sensitive(None))

    def test_original_dict_not_mutated(self):
        data = {"password": "secret"}
        original_value = data["password"]
        hide_sensitive(data)
        self.assertEqual(data["password"], original_value)

    def test_depth_guard(self):
        # Very deep nesting should not recurse infinitely
        data = {"k": "v"}
        for _ in range(15):
            data = {"nested": data}
        # Should return without error
        result = hide_sensitive(data)
        self.assertIsNotNone(result)


class TestSensitiveFilter(unittest.TestCase):

    def _make_record(self, msg: str, args=None) -> logging.LogRecord:
        record = logging.LogRecord(
            name="glpi_utils", level=logging.DEBUG,
            pathname="", lineno=0, msg=msg,
            args=args or (), exc_info=None,
        )
        return record

    def test_filter_returns_true(self):
        f = SensitiveFilter()
        record = self._make_record("test")
        self.assertTrue(f.filter(record))

    def test_dict_args_masked(self):
        f = SensitiveFilter()
        record = self._make_record("login %s", {"password": "mysecret", "user": "admin"})
        f.filter(record)
        self.assertIn("*", record.args["password"])
        self.assertEqual(record.args["user"], "admin")

    def test_tuple_with_dict_args_masked(self):
        f = SensitiveFilter()
        record = self._make_record(
            "request %s %s",
            ({"password": "secret"}, "https://example.com"),
        )
        f.filter(record)
        self.assertIn("*", record.args[0]["password"])
        self.assertEqual(record.args[1], "https://example.com")

    def test_plain_tuple_args_unchanged(self):
        f = SensitiveFilter()
        record = self._make_record("status %s %s", ("200", "OK"))
        f.filter(record)
        self.assertEqual(record.args, ("200", "OK"))

    def test_no_args_unchanged(self):
        f = SensitiveFilter()
        record = self._make_record("simple message")
        f.filter(record)
        self.assertEqual(record.args, ())


class TestEmptyHandler(unittest.TestCase):

    def test_emit_does_not_raise(self):
        handler = EmptyHandler()
        record = logging.LogRecord(
            name="test", level=logging.DEBUG,
            pathname="", lineno=0, msg="test",
            args=(), exc_info=None,
        )
        handler.emit(record)  # should not raise

    def test_is_logging_handler(self):
        self.assertIsInstance(EmptyHandler(), logging.Handler)

    def test_attached_to_api_logger(self):
        # EmptyHandler is attached to glpi_utils.api (and glpi_utils.aio)
        import glpi_utils.api  # ensure module is imported
        logger = logging.getLogger("glpi_utils.api")
        handler_types = [type(h) for h in logger.handlers]
        self.assertIn(EmptyHandler, handler_types)

    def test_sensitive_filter_attached_to_api_logger(self):
        import glpi_utils.api
        logger = logging.getLogger("glpi_utils.api")
        filter_types = [type(f) for f in logger.filters]
        self.assertIn(SensitiveFilter, filter_types)


if __name__ == "__main__":
    unittest.main()
