"""
examples/async_api/basic_async.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Demonstrates common patterns using AsyncGlpiAPI.

Requires: pip install glpi-utils[async]
"""

import asyncio
from glpi_utils import AsyncGlpiAPI


async def main():
    # ── Connection ────────────────────────────────────────────────────────────
    api = AsyncGlpiAPI(
        url="https://glpi.example.com",
        app_token="YOUR_APP_TOKEN",
    )
    await api.login(username="glpi", password="glpi")

    version = await api.get_version()
    print("GLPI version:", version)

    # ── Tickets ───────────────────────────────────────────────────────────────
    tickets = await api.ticket.get_all(range="0-9", expand_dropdowns=True)
    for t in tickets:
        print(f"[{t['id']}] {t['name']}")

    ticket = await api.ticket.get(1)
    print("Ticket name:", ticket["name"])

    # ── Concurrent requests ───────────────────────────────────────────────────
    # Fetch tickets, computers and users in parallel
    tickets_task  = asyncio.create_task(api.ticket.get_all(range="0-49"))
    computers_task = asyncio.create_task(api.computer.get_all(range="0-49"))
    users_task     = asyncio.create_task(api.user.get_all(range="0-49"))

    tickets, computers, users = await asyncio.gather(
        tickets_task, computers_task, users_task
    )
    print(f"Tickets: {len(tickets)}, Computers: {len(computers)}, Users: {len(users)}")

    # ── Create + followup in one flow ─────────────────────────────────────────
    new_ticket = await api.ticket.create({
        "name": "Async test ticket",
        "content": "Created via AsyncGlpiAPI",
        "type": 1,
        "status": 1,
    })

    await api.ticket.add_sub_item(
        new_ticket["id"],
        "ITILFollowup",
        {"content": "Automated followup.", "is_private": 0},
    )

    await api.ticket.delete({"id": new_ticket["id"]}, force_purge=True)

    await api.logout()


async def context_manager_example():
    """Using the async context manager for auto-cleanup."""
    async with AsyncGlpiAPI(url="https://glpi.example.com") as api:
        await api.login(username="glpi", password="glpi")
        version = await api.get_version()
        print("Version:", version)
        # logout + session close happen automatically on exit


if __name__ == "__main__":
    asyncio.run(main())
