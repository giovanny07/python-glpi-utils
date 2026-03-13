"""
Basic usage — asynchronous client (AsyncGlpiAPI)
Works with GLPI 9.1, 10.x and 11.x via /apirest.php

Requirements:
    pip install glpi-utils[async]

Usage:
    export GLPI_URL=https://glpi.example.com
    export GLPI_APP_TOKEN=your_app_token
    export GLPI_USER_TOKEN=your_user_token
    python3 basic_async.py
"""

import asyncio
import os
from glpi_utils import AsyncGlpiAPI, GlpiNotFoundError

URL       = os.environ.get("GLPI_URL",        "https://glpi.example.com")
APP_TOKEN = os.environ.get("GLPI_APP_TOKEN",  "")
TOKEN     = os.environ.get("GLPI_USER_TOKEN", "")


def sep(title):
    print(f"\n{'─'*50}\n  {title}\n{'─'*50}")


async def main():
    async with AsyncGlpiAPI(url=URL, app_token=APP_TOKEN) as api:
        await api.login(user_token=TOKEN)

        # ── Version ────────────────────────────────────
        sep("Version")
        version = await api.get_version()
        print(f"GLPI version : {version}")
        print(f"Is 10+       : {version >= 10}")
        print(f"Is 11+       : {version >= 11}")

        # ── Read tickets ────────────────────────────────
        sep("Read tickets")
        tickets = await api.ticket.get_all(range="0-4", expand_dropdowns=True)
        for t in tickets:
            print(f"  [{t['id']}] {t['name']}")

        if tickets:
            real_id = tickets[0]["id"]
            t = await api.ticket.get(real_id)
            print(f"\nDetail #{real_id}: {t['name']}")

        # ── Pagination ──────────────────────────────────
        sep("Pagination")
        all_tickets = await api.ticket.get_all_pages()
        print(f"Total: {len(all_tickets)} tickets")

        i = 0
        async for page in api.ticket.iter_pages(page_size=20):
            i += 1
            print(f"  Page {i}: {len(page)} tickets")

        # ── CRUD ────────────────────────────────────────
        sep("CRUD")
        new = await api.ticket.create({
            "name"    : "Test async glpi-utils",
            "content" : "Ticket created by AsyncGlpiAPI test script.",
            "type"    : 1,
            "status"  : 1,
            "urgency" : 3,
            "impact"  : 3,
            "priority": 3,
        })
        print(f"Created  #{new['id']}")

        await api.ticket.update({"id": new["id"], "status": 2})
        print(f"Updated  #{new['id']} → status=2")

        await api.ticket.delete({"id": new["id"]}, force_purge=True)
        print(f"Deleted  #{new['id']}")

        # ── Error handling ──────────────────────────────
        sep("Error handling")
        try:
            await api.ticket.get(999999999)
        except GlpiNotFoundError:
            print("GlpiNotFoundError ✓")

    sep("Done — all sections completed ✓")


asyncio.run(main())
