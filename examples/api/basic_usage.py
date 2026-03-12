"""
examples/api/basic_usage.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Demonstrates common patterns using GlpiAPI (synchronous).
"""

from glpi_utils import GlpiAPI

# ── Connection ───────────────────────────────────────────────────────────────

api = GlpiAPI(
    url="https://glpi.example.com",
    app_token="YOUR_APP_TOKEN",   # optional but recommended
)

# Option A: username + password
api.login(username="glpi", password="glpi")

# Option B: personal API token (from user profile → Remote access key)
# api.login(user_token="q56hqkniwot8wntb3z1qarka5atf365taaa2uyjrn")

# Option C: environment variables GLPI_URL / GLPI_USER / GLPI_PASSWORD
# api = GlpiAPI()
# api.login()

print("GLPI version:", api.version)

# ── Tickets ──────────────────────────────────────────────────────────────────

# List the first 10 open tickets
tickets = api.ticket.get_all(range="0-9", expand_dropdowns=True)
for t in tickets:
    print(f"[{t['id']}] {t['name']} – status: {t.get('status')}")

# Get a single ticket with all followups
ticket = api.ticket.get(1, with_logs=True)
print(ticket["name"])

# Create a ticket
new_ticket = api.ticket.create({
    "name": "Server unreachable",
    "content": "The monitoring server is not responding to ICMP.",
    "itilcategories_id": 5,
    "urgency": 3,
    "impact": 3,
    "priority": 3,
    "type": 1,          # Incident
    "status": 1,        # New
})
print("Created ticket ID:", new_ticket["id"])

# Add a followup to the ticket
api.ticket.add_sub_item(
    new_ticket["id"],
    "ITILFollowup",
    {
        "content": "Checked connectivity – switch port appears down.",
        "is_private": 0,
    },
)

# Close the ticket
api.ticket.update({"id": new_ticket["id"], "status": 6})  # 6 = Closed

# ── Computers / Assets ───────────────────────────────────────────────────────

computers = api.computer.get_all(
    searchText={"name": "web-srv"},
    expand_dropdowns=True,
)
for c in computers:
    print(c["name"], "–", c.get("states_id"))

# ── Search engine ────────────────────────────────────────────────────────────

results = api.ticket.search(
    criteria=[
        {"field": 12, "searchtype": "equals", "value": 1},   # status = New
        {"field": 5,  "searchtype": "contains", "value": "network"},
    ],
    forcedisplay=[1, 3, 12, 15],
    range="0-24",
    sort=19,
    order="DESC",
)
print("Total matching tickets:", results.get("totalcount"))

# ── Custom item types ─────────────────────────────────────────────────────────

# Anything not in the built-in aliases:
kb = api.item("KnowbaseItem")
articles = kb.get_all(range="0-4")
for a in articles:
    print(a["id"], a.get("name"))

# ── Session management ───────────────────────────────────────────────────────

print("Active profile:", api.get_active_profile()["name"])
entities = api.get_my_entities()
print("Accessible entities:", [e["name"] for e in entities])

# ── Logout ───────────────────────────────────────────────────────────────────
api.logout()

# ── Context manager (auto-logout) ────────────────────────────────────────────
with GlpiAPI(url="https://glpi.example.com", app_token="YOUR_APP_TOKEN") as g:
    g.login(username="glpi", password="glpi")
    users = g.user.get_all(range="0-4")
    print([u["name"] for u in users])
