"""
tests/common.py
~~~~~~~~~~~~~~~

Shared test helpers, fixtures and base classes used across all test modules.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from glpi_utils import GlpiAPI


def mock_response(status_code: int = 200, json_data=None, content: bool = True):
    """Build a fake requests.Response for mocking."""
    mock = MagicMock()
    mock.status_code = status_code
    mock.content = b"x" if content else b""
    mock.json.return_value = json_data if json_data is not None else {}
    mock.text = str(json_data)
    return mock


def make_api(session_token: str = "fake_token") -> GlpiAPI:
    """Return a GlpiAPI instance with a pre-set session token (no login needed)."""
    api = GlpiAPI(url="https://glpi.example.com", app_token="testapptoken")
    api._session_token = session_token
    return api
