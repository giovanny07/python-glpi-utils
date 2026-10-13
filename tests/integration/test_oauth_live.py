# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2025-2026 Giovanny Rodriguez, Imagunet
"""High-Level API (GlpiOAuthClient / AsyncGlpiOAuthClient) against a real GLPI 11+."""

from __future__ import annotations

import os

from glpi_utils.oauth import AsyncGlpiOAuthClient, GlpiOAuthClient

from .conftest import PASSWORD, URL, USER


def test_server_version(oauth: GlpiOAuthClient, glpi_version) -> None:
    assert oauth.get_version() == glpi_version


def test_api_versions_offered(oauth: GlpiOAuthClient, glpi_version) -> None:
    versions = {v["version"] for v in oauth.get_api_versions()}
    assert "2.3.0" in versions
    if glpi_version.major >= 12:
        assert "3.0.0" in versions


def test_pagination_past_default_limit(oauth: GlpiOAuthClient, many_locations: int) -> None:
    # The HL API ignores "range" and defaults to 100 items: 1.4.5 duplicated
    # the first 100 and never returned the rest.
    ids = [i["id"] for i in oauth.location.get_all_pages(page_size=50)]
    assert len(ids) == many_locations
    assert len(set(ids)) == len(ids)


def test_get_all_translates_range(oauth: GlpiOAuthClient, many_locations: int) -> None:
    assert len(oauth.location.get_all(range="0-9")) == 10


def test_ticket_lifecycle(oauth: GlpiOAuthClient, run_id: str) -> None:
    name = f"it-hl-{run_id}-{oauth.api_version or 'default'}"
    tid = oauth.ticket.create({"name": name, "content": "integration test"})["id"]
    try:
        oauth.update_item("Ticket", {"id": tid, "name": name + "-upd"})
        assert oauth.get_item("Ticket", tid)["name"] == name + "-upd"
        oauth.add_sub_item("Ticket", tid, "ITILFollowup", {"content": "followup"})
        assert len(oauth.get_sub_items("Ticket", tid, "ITILFollowup")) == 1
        assert [t["id"] for t in oauth.search("Ticket", filter=f"name=={name}-upd")] == [tid]
    finally:
        oauth.delete_item("Ticket", {"id": tid})


def test_software_license_route(oauth: GlpiOAuthClient) -> None:
    assert isinstance(oauth.item("SoftwareLicense").get_all(), list)


async def test_async_client(oauth: GlpiOAuthClient, glpi_version, many_locations: int) -> None:
    async with AsyncGlpiOAuthClient(
        url=URL,
        client_id=os.environ.get("GLPI_IT_CLIENT_ID"),
        client_secret=os.environ.get("GLPI_IT_CLIENT_SECRET"),
        username=USER,
        password=PASSWORD,
        api_version=oauth.api_version,
    ) as api:
        await api.authenticate()
        assert await api.get_version() == glpi_version
        ids = [i["id"] for i in await api.location.get_all_pages(page_size=50)]
        assert len(ids) == many_locations == len(set(ids))
