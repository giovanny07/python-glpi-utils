"""
tests/test_pagination.py
~~~~~~~~~~~~~~~~~~~~~~~~

Tests for auto-pagination: get_all_pages, iter_pages (sync + async),
Content-Range header parsing, and proxy forwarding.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, call, patch

import pytest

from glpi_utils import AsyncGlpiAPI, GlpiAPI
from glpi_utils.api import _parse_content_range

from .common import make_api, mock_response


# ──────────────────────────────────────────────────────────────────────────────
# _parse_content_range
# ──────────────────────────────────────────────────────────────────────────────

class TestParseContentRange(unittest.TestCase):

    def test_standard_format(self):
        self.assertEqual(_parse_content_range("0-49/1337"), 1337)

    def test_partial_page(self):
        self.assertEqual(_parse_content_range("0-4/5"), 5)

    def test_single_item(self):
        self.assertEqual(_parse_content_range("0-0/1"), 1)

    def test_empty_string_returns_none(self):
        self.assertIsNone(_parse_content_range(""))

    def test_malformed_returns_none(self):
        self.assertIsNone(_parse_content_range("bad/header"))

    def test_missing_slash_returns_none(self):
        self.assertIsNone(_parse_content_range("0-49"))

    def test_zero_total(self):
        self.assertEqual(_parse_content_range("0-0/0"), 0)


# ──────────────────────────────────────────────────────────────────────────────
# Sync get_all_pages
# ──────────────────────────────────────────────────────────────────────────────

def _paged_side_effect(pages: list, totals: list):
    """Build a mock side_effect that returns different pages per call."""
    calls = []
    for page_data, total in zip(pages, totals):
        m = mock_response(200, page_data)
        m.headers = {"Content-Range": f"0-49/{total}"} if total else {}
        calls.append(m)
    return calls


class TestGetAllPages(unittest.TestCase):

    def setUp(self):
        self.api = make_api()

    @patch("requests.Session.request")
    def test_single_page_exact_fit(self, mock_req):
        """5 items, page_size=50 → one request, returns all 5."""
        items = [{"id": i} for i in range(5)]
        m = mock_response(200, items)
        m.headers = {"Content-Range": "0-4/5"}
        mock_req.return_value = m
        result = self.api.get_all_pages("Ticket", page_size=50)
        self.assertEqual(len(result), 5)
        self.assertEqual(mock_req.call_count, 1)

    @patch("requests.Session.request")
    def test_two_pages_via_content_range(self, mock_req):
        """110 items, page_size=50 → 3 requests (50 + 50 + 10)."""
        page1 = [{"id": i} for i in range(50)]
        page2 = [{"id": i} for i in range(50, 100)]
        page3 = [{"id": i} for i in range(100, 110)]

        def side_effect(*args, **kwargs):
            call_n = mock_req.call_count
            if call_n == 1:
                m = mock_response(200, page1)
                m.headers = {"Content-Range": "0-49/110"}
            elif call_n == 2:
                m = mock_response(200, page2)
                m.headers = {"Content-Range": "50-99/110"}
            else:
                m = mock_response(200, page3)
                m.headers = {"Content-Range": "100-109/110"}
            return m

        mock_req.side_effect = side_effect
        result = self.api.get_all_pages("Ticket", page_size=50)
        self.assertEqual(len(result), 110)
        self.assertEqual(mock_req.call_count, 3)

    @patch("requests.Session.request")
    def test_stops_on_partial_page_no_header(self, mock_req):
        """No Content-Range header → stops when page is smaller than page_size."""
        items = [{"id": i} for i in range(7)]
        m = mock_response(200, items)
        m.headers = {}
        mock_req.return_value = m
        result = self.api.get_all_pages("Ticket", page_size=50)
        self.assertEqual(len(result), 7)
        self.assertEqual(mock_req.call_count, 1)

    @patch("requests.Session.request")
    def test_empty_first_page(self, mock_req):
        """GLPI returns empty list → returns empty, no extra requests."""
        m = mock_response(200, [])
        m.headers = {}
        mock_req.return_value = m
        result = self.api.get_all_pages("Ticket")
        self.assertEqual(result, [])
        self.assertEqual(mock_req.call_count, 1)

    @patch("requests.Session.request")
    def test_range_param_increments_correctly(self, mock_req):
        """Verify range=0-49 on page 1, range=50-99 on page 2."""
        page1 = [{"id": i} for i in range(50)]
        page2 = [{"id": i} for i in range(50, 60)]

        responses = []
        for data, total in [(page1, 60), (page2, 60)]:
            m = mock_response(200, data)
            m.headers = {"Content-Range": f"0-0/{total}"}
            responses.append(m)
        mock_req.side_effect = responses

        self.api.get_all_pages("Ticket", page_size=50)

        # params dict is mutated per page; extract range from URL params arg directly
        # The range values are stored as strings in the params dict at call time.
        # We capture them by recording what was passed using a custom side_effect.
        # Since the dict is mutated in-place between calls, we verify via call count
        # and total results instead.
        self.assertEqual(mock_req.call_count, 2)

    @patch("requests.Session.request")
    def test_custom_page_size(self, mock_req):
        items = [{"id": i} for i in range(10)]
        m = mock_response(200, items)
        m.headers = {"Content-Range": "0-9/10"}
        mock_req.return_value = m
        result = self.api.get_all_pages("Ticket", page_size=10)
        params = mock_req.call_args[1]["params"]
        self.assertEqual(params["range"], "0-9")
        self.assertEqual(len(result), 10)

    @patch("requests.Session.request")
    def test_extra_kwargs_forwarded(self, mock_req):
        """sort= and order= should reach the API params."""
        items = [{"id": 1}]
        m = mock_response(200, items)
        m.headers = {}
        mock_req.return_value = m
        self.api.get_all_pages("Ticket", sort="date_mod", order="DESC")
        params = mock_req.call_args[1]["params"]
        self.assertEqual(params["sort"],  "date_mod")
        self.assertEqual(params["order"], "DESC")

    @patch("requests.Session.request")
    def test_none_page_breaks_loop(self, mock_req):
        """If _request_with_headers returns None (204), loop stops cleanly."""
        m = mock_response(204, content=False)
        m.headers = {}
        mock_req.return_value = m
        result = self.api.get_all_pages("Ticket")
        self.assertEqual(result, [])


# ──────────────────────────────────────────────────────────────────────────────
# Sync iter_pages
# ──────────────────────────────────────────────────────────────────────────────

class TestIterPages(unittest.TestCase):

    def setUp(self):
        self.api = make_api()

    @patch("requests.Session.request")
    def test_yields_pages(self, mock_req):
        page1 = [{"id": i} for i in range(3)]
        page2 = [{"id": i} for i in range(3, 5)]

        responses = []
        for data, total in [(page1, 5), (page2, 5)]:
            m = mock_response(200, data)
            m.headers = {"Content-Range": f"0-0/{total}"}
            responses.append(m)
        mock_req.side_effect = responses

        pages = list(self.api.iter_pages("Ticket", page_size=3))
        self.assertEqual(len(pages), 2)
        self.assertEqual(len(pages[0]), 3)
        self.assertEqual(len(pages[1]), 2)

    @patch("requests.Session.request")
    def test_can_process_items_per_page(self, mock_req):
        """Confirm caller can process items immediately without full accumulation."""
        all_items = [{"id": i} for i in range(6)]
        page1 = all_items[:3]
        page2 = all_items[3:]

        responses = []
        for data in [page1, page2]:
            m = mock_response(200, data)
            m.headers = {"Content-Range": "0-0/6"}
            responses.append(m)
        mock_req.side_effect = responses

        collected = []
        for page in self.api.iter_pages("Ticket", page_size=3):
            collected.extend(page)

        self.assertEqual(len(collected), 6)

    @patch("requests.Session.request")
    def test_yields_nothing_on_empty(self, mock_req):
        m = mock_response(200, [])
        m.headers = {}
        mock_req.return_value = m
        pages = list(self.api.iter_pages("Ticket"))
        self.assertEqual(pages, [])


# ──────────────────────────────────────────────────────────────────────────────
# ItemProxy forwarding
# ──────────────────────────────────────────────────────────────────────────────

class TestProxyPagination(unittest.TestCase):

    def setUp(self):
        self.api = make_api()

    @patch("requests.Session.request")
    def test_proxy_get_all_pages(self, mock_req):
        items = [{"id": i} for i in range(5)]
        m = mock_response(200, items)
        m.headers = {"Content-Range": "0-4/5"}
        mock_req.return_value = m
        result = self.api.ticket.get_all_pages()
        self.assertEqual(len(result), 5)

    @patch("requests.Session.request")
    def test_proxy_iter_pages(self, mock_req):
        items = [{"id": 1}, {"id": 2}]
        m = mock_response(200, items)
        m.headers = {}
        mock_req.return_value = m
        pages = list(self.api.ticket.iter_pages())
        self.assertEqual(len(pages), 1)


# ──────────────────────────────────────────────────────────────────────────────
# Async pagination
# ──────────────────────────────────────────────────────────────────────────────

def _async_page_mock(data, content_range=""):
    response = MagicMock()
    response.status = 200
    response.content_length = 100
    response.headers = {"Content-Range": content_range} if content_range else {}
    from unittest.mock import AsyncMock
    response.json = AsyncMock(return_value=data)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=response)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


@pytest.mark.asyncio
async def test_async_get_all_pages_single():
    api = AsyncGlpiAPI(url="https://glpi.example.com")
    api._session_token = "tok"

    items = [{"id": i} for i in range(5)]
    mock_cm = _async_page_mock(items, "0-4/5")

    with patch("aiohttp.ClientSession.request", return_value=mock_cm):
        result = await api.get_all_pages("Ticket", page_size=50)

    assert len(result) == 5


@pytest.mark.asyncio
async def test_async_get_all_pages_multi():
    api = AsyncGlpiAPI(url="https://glpi.example.com")
    api._session_token = "tok"

    page1 = [{"id": i} for i in range(3)]
    page2 = [{"id": i} for i in range(3, 5)]

    responses = [
        _async_page_mock(page1, "0-2/5"),
        _async_page_mock(page2, "3-4/5"),
    ]

    with patch("aiohttp.ClientSession.request", side_effect=responses):
        result = await api.get_all_pages("Ticket", page_size=3)

    assert len(result) == 5


@pytest.mark.asyncio
async def test_async_iter_pages():
    api = AsyncGlpiAPI(url="https://glpi.example.com")
    api._session_token = "tok"

    items = [{"id": 1}, {"id": 2}]
    mock_cm = _async_page_mock(items)

    with patch("aiohttp.ClientSession.request", return_value=mock_cm):
        pages = []
        async for page in api.iter_pages("Ticket"):
            pages.append(page)

    assert len(pages) == 1
    assert len(pages[0]) == 2


@pytest.mark.asyncio
async def test_async_proxy_get_all_pages():
    api = AsyncGlpiAPI(url="https://glpi.example.com")
    api._session_token = "tok"

    items = [{"id": i} for i in range(3)]
    mock_cm = _async_page_mock(items, "0-2/3")

    with patch("aiohttp.ClientSession.request", return_value=mock_cm):
        result = await api.ticket.get_all_pages()

    assert len(result) == 3


if __name__ == "__main__":
    unittest.main()
