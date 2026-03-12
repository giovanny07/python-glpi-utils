# CRUD Operations

All clients expose the same set of methods. Examples use the sync `GlpiAPI` but the interface is identical for `AsyncGlpiAPI` and the OAuth2 clients (just add `await`).

## Item-type accessors

Access any GLPI item type as an attribute:

```python
api.ticket          # Ticket
api.computer        # Computer
api.user            # User
api.group           # Group
api.entity          # Entity
api.location        # Location
api.category        # ITILCategory
api.problem         # Problem
api.change          # Change
api.project         # Project
api.projecttask     # ProjectTask
api.document        # Document
api.contract        # Contract
api.knowledgebase   # KnowbaseItem
api.followup        # ITILFollowup
api.solution        # ITILSolution
api.task            # TicketTask
```

For any other item type use `api.item()`:

```python
proxy = api.item("KnowbaseItem")
proxy = api.item("ReservationItem")
```

---

## Read

### Single item

```python
ticket = api.ticket.get(1)
ticket = api.ticket.get(1, expand_dropdowns=True, with_logs=True)
```

### Single page

```python
tickets = api.ticket.get_all(range="0-49")
tickets = api.ticket.get_all(sort="date_mod", order="DESC")
```

### All pages (auto-pagination)

```python
tickets = api.ticket.get_all_pages()
tickets = api.ticket.get_all_pages(page_size=100, is_deleted=False)
```

See [Auto-pagination](pagination.md) for details.

### Search engine

```python
results = api.ticket.search(
    criteria=[
        {"field": 12, "searchtype": "equals", "value": 1},   # status = New
        {"field": 5,  "searchtype": "equals", "value": 3},   # type = Incident
    ],
    forcedisplay=[1, 3, 12, 15],
    range="0-49",
)
print(f"Found {results['totalcount']} tickets")
for item in results.get("data", []):
    print(item)
```

---

## Create

```python
# Single item
new = api.ticket.create({
    "name": "Service degraded",
    "content": "Users report slow response times.",
    "type": 1,       # Incident
    "status": 1,     # New
    "urgency": 3,    # Medium
    "impact": 3,
    "priority": 3,
})
print(f"Created ticket #{new['id']}")

# Bulk create
results = api.ticket.create([
    {"name": "Ticket A", "content": "..."},
    {"name": "Ticket B", "content": "..."},
])
```

---

## Update

Each item dict must contain an `"id"` key:

```python
# Single update
api.ticket.update({"id": 42, "status": 2})   # Assigned

# Bulk update
api.ticket.update([
    {"id": 1, "status": 5},
    {"id": 2, "status": 5},
])
```

---

## Delete

```python
# Move to trash
api.ticket.delete({"id": 42})

# Permanent delete (bypass trash)
api.ticket.delete({"id": 42}, force_purge=True)

# Bulk delete
api.ticket.delete([{"id": 1}, {"id": 2}], force_purge=True)
```

---

## Sub-items

Sub-items are linked resources — followups, tasks, solutions, network ports, etc.

```python
# Read sub-items
followups = api.ticket.get_sub_items(1, "ITILFollowup")
tasks     = api.ticket.get_sub_items(1, "TicketTask")

# Add a followup
api.ticket.add_sub_item(1, "ITILFollowup", {
    "content": "Confirmed issue on node 3. Investigating.",
    "is_private": 0,
})

# Add a task
api.ticket.add_sub_item(1, "TicketTask", {
    "content": "Restart affected services.",
    "state": 1,       # Todo
    "taskcategories_id": 0,
})

# Add a solution
api.ticket.add_sub_item(1, "ITILSolution", {
    "content": "Restarted service on node 3. Issue resolved.",
    "solutiontypes_id": 1,
})
```

---

## Session utilities

```python
# Profiles
profiles = api.get_my_profiles()
api.set_active_profile(profile_id=4)

# Entities
entities = api.get_my_entities(is_recursive=True)
api.set_active_entity(entity_id=2, is_recursive=True)

# Full session info
session = api.get_full_session()
```
