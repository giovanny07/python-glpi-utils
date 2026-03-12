"""
tests/test_version.py
~~~~~~~~~~~~~~~~~~~~~

Tests for GLPIVersion – parsing, comparisons, edge cases.
"""

from __future__ import annotations

import unittest

from glpi_utils.version import GLPIVersion


class TestGLPIVersionParsing(unittest.TestCase):

    def test_parse_full_semver(self):
        v = GLPIVersion("11.0.3")
        self.assertEqual(v.major, 11)
        self.assertEqual(v.minor, 0)
        self.assertEqual(v.patch, 3)

    def test_parse_two_parts(self):
        v = GLPIVersion("10.0")
        self.assertEqual(v.major, 10)
        self.assertEqual(v.minor, 0)
        self.assertEqual(v.patch, 0)

    def test_parse_major_only(self):
        v = GLPIVersion("9")
        self.assertEqual(v.major, 9)
        self.assertEqual(v.minor, 0)
        self.assertEqual(v.patch, 0)

    def test_raw_string_preserved(self):
        self.assertEqual(str(GLPIVersion("11.0.1")), "11.0.1")

    def test_repr_contains_version(self):
        self.assertIn("11.0.1", repr(GLPIVersion("11.0.1")))

    def test_invalid_string_raises(self):
        with self.assertRaises(ValueError):
            GLPIVersion("not-a-version")

    def test_empty_string_raises(self):
        with self.assertRaises(ValueError):
            GLPIVersion("")


class TestGLPIVersionComparisons(unittest.TestCase):

    def setUp(self):
        self.v11 = GLPIVersion("11.0.0")

    # --- equality ---

    def test_eq_string_full(self):
        self.assertEqual(self.v11, "11.0.0")

    def test_eq_string_short(self):
        self.assertEqual(self.v11, "11.0")

    def test_eq_float(self):
        self.assertEqual(self.v11, 11.0)

    def test_eq_int(self):
        self.assertEqual(self.v11, 11)

    def test_eq_glpiversion(self):
        self.assertEqual(self.v11, GLPIVersion("11.0.0"))

    def test_neq_different_minor(self):
        self.assertNotEqual(self.v11, GLPIVersion("11.1.0"))

    def test_neq_different_patch(self):
        self.assertNotEqual(self.v11, GLPIVersion("11.0.1"))

    # --- greater than ---

    def test_gt_string(self):
        self.assertTrue(self.v11 > "10.0")

    def test_gt_float(self):
        self.assertTrue(self.v11 > 10.0)

    def test_not_gt_equal(self):
        self.assertFalse(self.v11 > "11.0.0")

    def test_not_gt_newer(self):
        self.assertFalse(self.v11 > GLPIVersion("11.0.1"))

    # --- less than ---

    def test_lt_string(self):
        self.assertTrue(self.v11 < "12.0")

    def test_not_lt_equal(self):
        self.assertFalse(self.v11 < "11.0.0")

    # --- gte / lte ---

    def test_gte_equal(self):
        self.assertTrue(self.v11 >= "11.0.0")

    def test_gte_greater(self):
        self.assertTrue(self.v11 >= "10.0")

    def test_lte_equal(self):
        self.assertTrue(self.v11 <= "11.0.0")

    def test_lte_less(self):
        self.assertTrue(self.v11 <= "12.0")

    # --- hash (usable as dict key / set member) ---

    def test_hashable(self):
        versions = {GLPIVersion("11.0.0"), GLPIVersion("11.0.0"), GLPIVersion("10.0.0")}
        self.assertEqual(len(versions), 2)

    # --- patch ordering ---

    def test_patch_ordering(self):
        self.assertTrue(GLPIVersion("11.0.2") > GLPIVersion("11.0.1"))
        self.assertTrue(GLPIVersion("11.0.0") < GLPIVersion("11.0.1"))


if __name__ == "__main__":
    unittest.main()
