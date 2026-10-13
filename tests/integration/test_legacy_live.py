# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2025-2026 Giovanny Rodriguez, Imagunet
"""Legacy REST API (GlpiAPI / AsyncGlpiAPI) against a real GLPI."""

from __future__ import annotations

import pytest

from glpi_utils import AsyncGlpiAPI, GlpiAPI, GlpiNotFoundError

from .conftest import PASSWORD, URL, USER


def test_version_matches_server(legacy: GlpiAPI, glpi_version) -> None:
    assert legacy.version == glpi_version


def test_session_helpers(legacy: GlpiAPI) -> None:
    assert legacy.get_my_profiles()
    assert legacy.get_my_entities()
    assert "glpiID" in legacy.get_full_session()


@pytest.mark.parametrize("page_size", [7, 50])
def test_get_all_pages_returns_every_item_once(legacy: GlpiAPI, many_locations: int, page_size: int) -> None:
    items = legacy.location.get_all_pages(page_size=page_size)
    ids = [i["id"] for i in items]
    assert len(ids) == many_locations
    assert len(set(ids)) == len(ids)


def test_ticket_lifecycle_with_sub_items(legacy: GlpiAPI, run_id: str) -> None:
    name = f"it-legacy-{run_id}"
    tid = legacy.ticket.create({"name": name, "content": "integration test"})["id"]
    try:
        legacy.ticket.update({"id": tid, "status": 2})
        assert legacy.ticket.get(tid)["status"] == 2

        # GLPI does not take the parent from the URL; add_sub_item fills it in.
        legacy.ticket.add_sub_item(tid, "ITILFollowup", {"content": "followup"})
        legacy.ticket.add_sub_item(tid, "TicketTask", {"content": "task"})
        legacy.ticket.add_sub_item(tid, "ITILSolution", {"content": "solution"})
        assert len(legacy.ticket.get_sub_items(tid, "ITILFollowup")) == 1
        assert len(legacy.ticket.get_sub_items(tid, "TicketTask")) == 1

        found = legacy.ticket.search(
            criteria=[{"field": 1, "searchtype": "contains", "value": name}],
            forcedisplay=[1, 2],
        )
        assert found["totalcount"] == 1
    finally:
        legacy.ticket.delete({"id": tid}, force_purge=True)
    with pytest.raises(GlpiNotFoundError):
        legacy.ticket.get(tid)


async def test_async_client(many_locations: int, glpi_version) -> None:
    async with AsyncGlpiAPI(url=URL) as api:
        await api.login(username=USER, password=PASSWORD)
        assert await api.get_version() == glpi_version
        ids = [i["id"] for i in await api.location.get_all_pages(page_size=50)]
        assert len(ids) == many_locations == len(set(ids))
