!!! warning "GLPI 11+ only"
    The OAuth2 high-level API (`/api.php`) was introduced in GLPI 11. If you are running GLPI 9.x or 10.x, use `GlpiAPI` or `AsyncGlpiAPI` instead.

!!! warning "GLPI 11.0.6+ recommended"
    `DELETE` and `Timeline` sub-item endpoints (`Followup`, `Task`, `Solution`) return
    `ERROR_RIGHT_MISSING` in GLPI 11.0.5 regardless of profile permissions. This bug was
    fixed in **GLPI 11.0.6**. Upgrade before using these operations via the HL API.

# OAuth2 (High-level API)

GLPI 11 introduced a modern REST API at `/api.php` that uses OAuth2 for
authentication. Use `GlpiOAuthClient` or `AsyncGlpiOAuthClient` for this.

---

## Setup in GLPI

1. Go to **Setup → OAuth clients → Add**
2. Set a name, note the **Client ID** and **Client Secret**
3. Set **Grants**: `Password` (required for API access)
4. Set **Scopes**: `api`
5. Save

!!! note "client_credentials grant"
    The `client_credentials` grant is **not supported** for the `api` scope in GLPI 11.
    It only works for the `inventory` scope. Always use the `password` grant for
    ticket/asset API access.

---

## Password grant (recommended)

Pass `username` and `password` in the constructor — they are used automatically
on `authenticate()` and on any token refresh:

```python
from glpi_utils.oauth import GlpiOAuthClient

with GlpiOAuthClient(
    url="https://glpi.example.com",
    client_id="my-app",
    client_secret="my-secret",
    username="glpi",
    password="glpi",
) as api:
    api.authenticate()
    tickets = api.ticket.get_all_pages()
    print(f"{len(tickets)} tickets")
```

---

## Async

```python
import asyncio
from glpi_utils.oauth import AsyncGlpiOAuthClient

async def main():
    async with AsyncGlpiOAuthClient(
        url="https://glpi.example.com",
        client_id="my-app",
        client_secret="my-secret",
        username="glpi",
        password="glpi",
    ) as api:
        await api.authenticate()

        tickets = await api.ticket.get_all_pages()

        async for page in api.ticket.iter_pages(page_size=100):
            for ticket in page:
                print(ticket["name"])

asyncio.run(main())
```

---

## Automatic token refresh

Bearer tokens expire (default 1 hour in GLPI). The clients re-authenticate
transparently when the token is about to expire — no manual handling needed:

```python
with GlpiOAuthClient(
    url="...", client_id="x", client_secret="y",
    username="glpi", password="glpi",
) as api:
    api.authenticate()
    # Script runs for several hours — token renewal is automatic.
    for page in api.ticket.iter_pages():
        process(page)
```

---

## Environment variables

```bash
export GLPI_URL=https://glpi.example.com
export GLPI_OAUTH_CLIENT_ID=my-app
export GLPI_OAUTH_CLIENT_SECRET=my-secret
export GLPI_OAUTH_USERNAME=glpi
export GLPI_OAUTH_PASSWORD=glpi
```

```python
api = GlpiOAuthClient()   # reads all from env
api.authenticate()
```

---

## Full CRUD support

`GlpiOAuthClient` exposes the same interface as `GlpiAPI`. Internally, itemtypes
are mapped to their namespaced HL API paths automatically (`Ticket` →
`Assistance/Ticket`, `Computer` → `Assets/Computer`, etc.):

```python
# Read
ticket = api.ticket.get(1)
all    = api.ticket.get_all_pages()

# Create / Update / Delete
new = api.ticket.create({
    "name": "Test", "content": "...",
    "type": 1, "status": 1, "urgency": 3, "impact": 3, "priority": 3,
})
api.ticket.update({"id": new["id"], "status": 2})
api.ticket.delete({"id": new["id"]})

# Timeline sub-items (Followup, Task, Solution, Validation)
api.ticket.add_sub_item(new["id"], "ITILFollowup", {
    "content": "Work in progress.", "is_private": 0,
})
followups = api.ticket.get_sub_items(new["id"], "ITILFollowup")

# Non-standard itemtypes — pass full path
api.item("Assets/Socket").get_all()
```

---

## HL API route map

The GLPI 11 High-Level API groups resources into namespaces. The library maps
the standard itemtype names automatically:

| Alias / Itemtype | HL API path |
|-----------------|-------------|
| `ticket` | `Assistance/Ticket` |
| `problem` | `Assistance/Problem` |
| `change` | `Assistance/Change` |
| `computer` | `Assets/Computer` |
| `monitor` | `Assets/Monitor` |
| `printer` | `Assets/Printer` |
| `networkequipment` | `Assets/NetworkEquipment` |
| `software` | `Assets/Software` |
| `user` | `Administration/User` |
| `group` | `Administration/Group` |
| `entity` | `Administration/Entity` |
| `contract` | `Management/Contract` |
| `supplier` | `Management/Supplier` |
| `document` | `Management/Document` |
| `category` | `Dropdowns/ITILCategory` |
| `knowledgebase` | `Knowledgebase/Article` |
| `ITILFollowup` | `Timeline/Followup` *(sub-item only)* |
| `TicketTask` | `Timeline/Task` *(sub-item only)* |
| `ITILSolution` | `Timeline/Solution` *(sub-item only)* |

For unmapped itemtypes (plugins, custom assets), pass the full path directly:
`api.item("Assets/Custom/MyType")`.
