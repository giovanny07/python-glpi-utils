"""
Basic usage — synchronous client (GlpiAPI)
Works with GLPI 9.1, 10.x and 11.x via /apirest.php

Usage:
    export GLPI_URL=https://glpi.example.com
    export GLPI_APP_TOKEN=your_app_token
    export GLPI_USER_TOKEN=your_user_token
    python3 basic_usage.py
"""

import os
from glpi_utils import GlpiAPI, GlpiNotFoundError, GlpiPermissionError

URL       = os.environ.get("GLPI_URL",        "https://glpi.example.com")
APP_TOKEN = os.environ.get("GLPI_APP_TOKEN",  "")
TOKEN     = os.environ.get("GLPI_USER_TOKEN", "")


def sep(title):
    print(f"\n{'─'*50}\n  {title}\n{'─'*50}")


with GlpiAPI(url=URL, app_token=APP_TOKEN) as api:
    api.login(user_token=TOKEN)

    # ── Version ────────────────────────────────────────
    sep("Version")
    print(f"GLPI version : {api.version}")
    print(f"Is 10+       : {api.version >= 10}")
    print(f"Is 11+       : {api.version >= 11}")

    # ── Read tickets — use real IDs from get_all ────────
    sep("Read tickets")
    tickets = api.ticket.get_all(range="0-4", expand_dropdowns=True)
    print(f"First {len(tickets)} ticket(s):")
    for t in tickets:
        print(f"  [{t['id']}] {t['name']} — status: {t['status']}")

    if tickets:
        real_id = tickets[0]["id"]
        t = api.ticket.get(real_id, expand_dropdowns=True)
        print(f"\nDetail #{real_id}: {t['name']}")

    # ── Pagination ──────────────────────────────────────
    sep("Pagination")
    all_tickets = api.ticket.get_all_pages()
    print(f"Total tickets: {len(all_tickets)}")

    for i, page in enumerate(api.ticket.iter_pages(page_size=20), 1):
        print(f"  Page {i}: {len(page)} tickets")

    # ── Create / Update / Delete ────────────────────────
    sep("CRUD")
    new = api.ticket.create({
        "name"    : "Test glpi-utils",
        "content" : "Ticket created by python-glpi-utils test script.",
        "type"    : 1,
        "status"  : 1,
        "urgency" : 3,
        "impact"  : 3,
        "priority": 3,
    })
    print(f"Created  #{new['id']}")

    api.ticket.update({"id": new["id"], "status": 2})
    print(f"Updated  #{new['id']} → status=2")

    api.ticket.delete({"id": new["id"]}, force_purge=True)
    print(f"Deleted  #{new['id']}")

    # ── Sub-items ───────────────────────────────────────
    sep("Sub-items")
    if tickets:
        real_id = tickets[0]["id"]
        followups = api.ticket.get_sub_items(real_id, "ITILFollowup")
        print(f"Ticket #{real_id} — {len(followups)} followup(s)")
        # add_sub_item requires write permission on the ticket's entity
        # api.ticket.add_sub_item(real_id, "ITILFollowup", {"content": "test", "is_private": 0})

    # ── Other item types ────────────────────────────────
    sep("Other item types")
    users    = api.user.get_all(range="0-4")
    print(f"Users      : {[u['name'] for u in users]}")
    entities = api.entity.get_all(range="0-4", expand_dropdowns=True)
    print(f"Entities   : {[e['name'] for e in entities]}")
    cats     = api.item("ITILCategory").get_all(range="0-4")
    print(f"Categories : {[c['name'] for c in cats]}")

    # ── Session utilities ───────────────────────────────
    sep("Session")
    profiles = api.get_my_profiles()
    print(f"Profiles : {[p['name'] for p in profiles]}")
    ents     = api.get_my_entities(is_recursive=True)
    print(f"Entities : {[e['name'] for e in ents]}")

    # ── Error handling ──────────────────────────────────
    sep("Error handling")
    try:
        api.ticket.get(999999999)
    except GlpiNotFoundError:
        print("GlpiNotFoundError ✓")
    except GlpiPermissionError:
        print("GlpiPermissionError ✓ (ticket exists but no access)")

sep("Done — all sections completed ✓")
