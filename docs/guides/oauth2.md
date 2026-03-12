# OAuth2 (High-level API)

GLPI 11 introduced a modern REST API at `/api.php` that uses OAuth2 for
authentication. Use `GlpiOAuthClient` or `AsyncGlpiOAuthClient` for this.

---

## Setup in GLPI

1. Go to **Setup → OAuth2 applications → Add**
2. Set a name and note the **Client ID** and **Client Secret**
3. Set allowed grant types: `client_credentials` and/or `password`
4. Save

---

## Client credentials grant

For service accounts and automation — no user interaction needed:

```python
from glpi_utils.oauth import GlpiOAuthClient

with GlpiOAuthClient(
    url="https://glpi.example.com",
    client_id="my-app",
    client_secret="my-secret",
) as api:
    api.authenticate()
    tickets = api.ticket.get_all_pages()
    print(f"{len(tickets)} tickets")
```

---

## Password grant

For user-delegated access:

```python
api = GlpiOAuthClient(
    url="https://glpi.example.com",
    client_id="my-app",
    client_secret="my-secret",
)
api.authenticate(username="glpi", password="glpi")
computers = api.computer.get_all_pages()
api.close()
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
    ) as api:
        await api.authenticate()

        # All pages
        tickets = await api.ticket.get_all_pages()

        # Stream large datasets
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
with GlpiOAuthClient(url="...", client_id="x", client_secret="y") as api:
    api.authenticate()
    # Script runs for several hours...
    # Token renewal happens automatically in the background.
    for page in api.ticket.iter_pages():
        process(page)
```

---

## Environment variables

```bash
export GLPI_URL=https://glpi.example.com
export GLPI_OAUTH_CLIENT_ID=my-app
export GLPI_OAUTH_CLIENT_SECRET=my-secret

# Only needed for password grant
export GLPI_OAUTH_USERNAME=glpi
export GLPI_OAUTH_PASSWORD=glpi
```

```python
api = GlpiOAuthClient()   # reads all from env
api.authenticate()
```

---

## Full CRUD support

`GlpiOAuthClient` exposes the same interface as `GlpiAPI`:

```python
# Read
ticket = api.ticket.get(1)
all    = api.ticket.get_all_pages()

# Create / Update / Delete
new = api.ticket.create({"name": "Test", "content": "..."})
api.ticket.update({"id": new["id"], "status": 2})
api.ticket.delete({"id": new["id"]})

# Sub-items
api.ticket.add_sub_item(1, "ITILFollowup", {"content": "Update"})

# Search
api.ticket.search(criteria=[...])
```
