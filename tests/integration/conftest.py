# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2025-2026 Giovanny Rodriguez, Imagunet
"""
Integration tests against a real GLPI server.

Skipped unless GLPI_IT_URL is set. .github/scripts/glpi_it_setup.sh prepares
a glpi/glpi container and prints the variables:

    GLPI_IT_URL            base URL, e.g. http://localhost:8080
    GLPI_IT_VERSION        GLPI version, e.g. 12.0.0
    GLPI_IT_CLIENT_ID      OAuth client (GLPI 11+ only)
    GLPI_IT_CLIENT_SECRET

The tests log in as the default glpi/glpi super-admin and create data; only
point them at a throwaway instance.
"""

from __future__ import annotations

import os
import uuid

import pytest

from glpi_utils import GlpiAPI, GLPIVersion
from glpi_utils.oauth import GlpiOAuthClient

URL = os.environ.get("GLPI_IT_URL", "")
USER, PASSWORD = "glpi", "glpi"
#: More than the High-Level API's default page (100), to catch pagination bugs.
MIN_LOCATIONS = 130


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if URL:
        return
    skip = pytest.mark.skip(reason="GLPI_IT_URL not set (integration tests need a real GLPI)")
    for item in items:
        if "integration" in item.nodeid:
            item.add_marker(skip)


@pytest.fixture(scope="session")
def glpi_version() -> GLPIVersion:
    return GLPIVersion(os.environ["GLPI_IT_VERSION"])


@pytest.fixture(scope="session")
def run_id() -> str:
    return uuid.uuid4().hex[:8]


@pytest.fixture(scope="session")
def legacy():
    api = GlpiAPI(url=URL)
    api.login(username=USER, password=PASSWORD)
    yield api
    api.logout()


@pytest.fixture(scope="session")
def many_locations(legacy: GlpiAPI, run_id: str) -> int:
    """Make sure at least MIN_LOCATIONS locations exist; return the count."""
    have = len(legacy.location.get_all_pages())
    if have < MIN_LOCATIONS:
        legacy.location.create([{"name": f"it-{run_id}-{i}"} for i in range(MIN_LOCATIONS - have)])
    return len(legacy.location.get_all_pages())


def _hl_versions() -> list:
    major = GLPIVersion(os.environ.get("GLPI_IT_VERSION", "0")).major
    if major >= 12:
        return [None, "2.3", "3.0"]
    if major >= 11:
        return [None, "2.3"]
    return []


_NO_HL_API = [pytest.param(None, marks=pytest.mark.skip(reason="High-Level API needs GLPI 11+"))]


@pytest.fixture(scope="session", params=_hl_versions() or _NO_HL_API, ids=lambda v: f"hlapi-{v or 'default'}")
def oauth(request):
    api = GlpiOAuthClient(
        url=URL,
        client_id=os.environ.get("GLPI_IT_CLIENT_ID"),
        client_secret=os.environ.get("GLPI_IT_CLIENT_SECRET"),
        username=USER,
        password=PASSWORD,
        api_version=request.param,
    )
    api.authenticate()
    yield api
    api.close()
