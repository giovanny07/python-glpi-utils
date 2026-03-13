"""
Basic usage — OAuth2 clients (GLPI 11+ only)
Uses /api.php with client_credentials or password grant.

Requirements:
    pip install glpi-utils[async]   # for AsyncGlpiOAuthClient
    pip install glpi-utils           # for GlpiOAuthClient only

Setup in GLPI:
    Setup → OAuth2 applications → Add
    Note the client_id and client_secret.

Usage:
    export GLPI_URL=https://glpi.example.com
    export GLPI_OAUTH_CLIENT_ID=your_client_id
    export GLPI_OAUTH_CLIENT_SECRET=your_client_secret
    python3 basic_oauth2.py
"""

import asyncio
import os
from glpi_utils.oauth import GlpiOAuthClient, AsyncGlpiOAuthClient
from glpi_utils import GlpiNotFoundError

URL    = os.environ.get("GLPI_URL",                "https://glpi.example.com")
CID    = os.environ.get("GLPI_OAUTH_CLIENT_ID",    "")
SECRET = os.environ.get("GLPI_OAUTH_CLIENT_SECRET","")


def sep(title):
    print(f"\n{'─'*50}\n  {title}\n{'─'*50}")


# ── Sync OAuth2 ────────────────────────────────────────────
sep("Sync — GlpiOAuthClient (client_credentials)")

with GlpiOAuthClient(url=URL, client_id=CID, client_secret=SECRET) as api:
    api.authenticate()

    tickets = api.ticket.get_all(range="0-4", expand_dropdowns=True)
    print(f"First {len(tickets)} ticket(s):")
    for t in tickets:
        print(f"  [{t['id']}] {t['name']}")

    all_tickets = api.ticket.get_all_pages()
    print(f"\nTotal tickets: {len(all_tickets)}")

    if tickets:
        real_id = tickets[0]["id"]
        followups = api.ticket.get_sub_items(real_id, "ITILFollowup")
        print(f"Ticket #{real_id} — {len(followups)} followup(s)")

    try:
        api.ticket.get(999999999)
    except GlpiNotFoundError:
        print("GlpiNotFoundError ✓")


# ── Async OAuth2 ───────────────────────────────────────────
sep("Async — AsyncGlpiOAuthClient (client_credentials)")


async def main_async():
    async with AsyncGlpiOAuthClient(
        url=URL, client_id=CID, client_secret=SECRET
    ) as api:
        await api.authenticate()

        tickets = await api.ticket.get_all(range="0-4", expand_dropdowns=True)
        print(f"First {len(tickets)} ticket(s):")
        for t in tickets:
            print(f"  [{t['id']}] {t['name']}")

        all_tickets = await api.ticket.get_all_pages()
        print(f"\nTotal tickets: {len(all_tickets)}")

        i = 0
        async for page in api.ticket.iter_pages(page_size=20):
            i += 1
            print(f"  Page {i}: {len(page)} tickets")

        try:
            await api.ticket.get(999999999)
        except GlpiNotFoundError:
            print("GlpiNotFoundError ✓")


asyncio.run(main_async())

sep("Done — all sections completed ✓")
