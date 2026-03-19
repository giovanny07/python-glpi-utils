"""
OAuth2 example — GLPI 11 High-Level API
========================================
Requires GLPI 11.0.6+ for full support (DELETE + Timeline sub-items).

Setup in GLPI:
    Setup → OAuth clients → Add
    Grants: Password
    Scopes: api

Usage:
    export GLPI_URL=https://glpi.example.com
    export GLPI_OAUTH_CLIENT_ID=your_client_id
    export GLPI_OAUTH_CLIENT_SECRET=your_client_secret
    export GLPI_OAUTH_USERNAME=glpi
    export GLPI_OAUTH_PASSWORD=glpi
    python3 basic_oauth2.py
"""

import asyncio
import os

from glpi_utils.oauth import AsyncGlpiOAuthClient, GlpiOAuthClient

URL    = os.environ.get("GLPI_URL", "https://glpi.example.com")
CID    = os.environ.get("GLPI_OAUTH_CLIENT_ID", "")
SECRET = os.environ.get("GLPI_OAUTH_CLIENT_SECRET", "")
USER   = os.environ.get("GLPI_OAUTH_USERNAME", "glpi")
PASSWD = os.environ.get("GLPI_OAUTH_PASSWORD", "glpi")


# ── Sync ─────────────────────────────────────────────────────────────────────

print("\n── Sync ──")
with GlpiOAuthClient(
    url=URL,
    client_id=CID,
    client_secret=SECRET,
    username=USER,
    password=PASSWD,
) as api:
    api.authenticate()
    print("Authenticated ✓")

    # Read
    tickets = api.ticket.get_all(range="0-4", expand_dropdowns=True)
    print(f"First {len(tickets)} ticket(s):")
    for t in tickets:
        print(f"  [{t['id']}] {t['name']} — status: {t['status']}")

    # Pagination
    all_tickets = api.ticket.get_all_pages()
    print(f"Total tickets: {len(all_tickets)}")

    # CRUD
    new = api.ticket.create({
        "name": "Test glpi-utils OAuth2",
        "content": "Created by python-glpi-utils.",
        "type": 1, "status": 1, "urgency": 3, "impact": 3, "priority": 3,
    })
    print(f"Created  #{new['id']}")

    api.ticket.update({"id": new["id"], "status": 2})
    print(f"Updated  #{new['id']} → status=2")

    api.ticket.add_sub_item(new["id"], "ITILFollowup", {
        "content": "Followup from python-glpi-utils.", "is_private": 0,
    })
    print(f"Followup added to #{new['id']}")

    api.ticket.delete({"id": new["id"]})
    print(f"Deleted  #{new['id']}")


# ── Async ─────────────────────────────────────────────────────────────────────

async def main():
    print("\n── Async ──")
    async with AsyncGlpiOAuthClient(
        url=URL,
        client_id=CID,
        client_secret=SECRET,
        username=USER,
        password=PASSWD,
    ) as api:
        await api.authenticate()
        print("Authenticated ✓")

        tickets = await api.ticket.get_all(range="0-4", expand_dropdowns=True)
        print(f"First {len(tickets)} ticket(s):")
        for t in tickets:
            print(f"  [{t['id']}] {t['name']}")

        all_tickets = await api.ticket.get_all_pages()
        print(f"Total tickets: {len(all_tickets)}")

        new = await api.ticket.create({
            "name": "Test glpi-utils OAuth2 async",
            "content": "Created by python-glpi-utils async.",
            "type": 1, "status": 1, "urgency": 3, "impact": 3, "priority": 3,
        })
        print(f"Created  #{new['id']}")

        await api.ticket.update({"id": new["id"], "status": 2})
        print(f"Updated  #{new['id']} → status=2")

        await api.ticket.delete({"id": new["id"]})
        print(f"Deleted  #{new['id']}")


asyncio.run(main())
print("\n✅ Done")
