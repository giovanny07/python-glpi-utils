# Quick Start

## Environment variables (recommended)

Avoid hardcoding credentials — set these before running any script:

```bash
export GLPI_URL=https://glpi.example.com
export GLPI_APP_TOKEN=your_app_token       # optional but recommended
export GLPI_USER_TOKEN=your_user_token     # personal token from your profile
# or
export GLPI_USER=glpi
export GLPI_PASSWORD=glpi
```

---

## Synchronous

```python
import os
from glpi_utils import GlpiAPI, GlpiNotFoundError

with GlpiAPI(url=os.environ["GLPI_URL"],
             app_token=os.environ.get("GLPI_APP_TOKEN", "")) as api:
    api.login(user_token=os.environ["GLPI_USER_TOKEN"])

    # Version
    print(f"GLPI {api.version}")     # GLPI 10.0.19
    print(api.version >= 10)         # True

    # Always use a real ID from get_all — don't hardcode IDs
    tickets = api.ticket.get_all(range="0-4", expand_dropdowns=True)
    for t in tickets:
        print(f"[{t['id']}] {t['name']}")

    if tickets:
        detail = api.ticket.get(tickets[0]["id"])
        print(detail["name"])

    # All tickets with auto-pagination
    all_tickets = api.ticket.get_all_pages()
    print(f"Total: {len(all_tickets)} tickets")

    # Create / update / delete
    new = api.ticket.create({
        "name": "Service degraded",
        "content": "Users report slow response times.",
        "type": 1, "status": 1, "urgency": 3, "impact": 3, "priority": 3,
    })
    api.ticket.update({"id": new["id"], "status": 2})
    api.ticket.delete({"id": new["id"]}, force_purge=True)

    # Error handling
    try:
        api.ticket.get(999999999)
    except GlpiNotFoundError:
        print("Not found ✓")
```

---

## Asynchronous

```python
import asyncio, os
from glpi_utils import AsyncGlpiAPI, GlpiNotFoundError

async def main():
    async with AsyncGlpiAPI(url=os.environ["GLPI_URL"],
                            app_token=os.environ.get("GLPI_APP_TOKEN", "")) as api:
        await api.login(user_token=os.environ["GLPI_USER_TOKEN"])

        version = await api.get_version()
        print(f"GLPI {version}")

        tickets = await api.ticket.get_all(range="0-4", expand_dropdowns=True)
        for t in tickets:
            print(f"[{t['id']}] {t['name']}")

        all_tickets = await api.ticket.get_all_pages()
        print(f"Total: {len(all_tickets)} tickets")

        async for page in api.ticket.iter_pages(page_size=20):
            print(f"Page with {len(page)} tickets")

asyncio.run(main())
```

---

## OAuth2 (GLPI 11.0.6+ recommended)

```bash
export GLPI_URL=https://glpi.example.com
export GLPI_OAUTH_CLIENT_ID=your_client_id
export GLPI_OAUTH_CLIENT_SECRET=your_client_secret
export GLPI_OAUTH_USERNAME=glpi
export GLPI_OAUTH_PASSWORD=glpi
```

```python
import asyncio, os
from glpi_utils.oauth import GlpiOAuthClient, AsyncGlpiOAuthClient

# Sync — pass username/password in constructor for automatic token refresh
with GlpiOAuthClient(
    url=os.environ["GLPI_URL"],
    client_id=os.environ["GLPI_OAUTH_CLIENT_ID"],
    client_secret=os.environ["GLPI_OAUTH_CLIENT_SECRET"],
    username=os.environ["GLPI_OAUTH_USERNAME"],
    password=os.environ["GLPI_OAUTH_PASSWORD"],
) as api:
    api.authenticate()
    tickets = api.ticket.get_all_pages()
    print(f"Total: {len(tickets)} tickets")

# Async
async def main():
    async with AsyncGlpiOAuthClient(
        url=os.environ["GLPI_URL"],
        client_id=os.environ["GLPI_OAUTH_CLIENT_ID"],
        client_secret=os.environ["GLPI_OAUTH_CLIENT_SECRET"],
        username=os.environ["GLPI_OAUTH_USERNAME"],
        password=os.environ["GLPI_OAUTH_PASSWORD"],
    ) as api:
        await api.authenticate()
        tickets = await api.ticket.get_all_pages()
        print(f"Total: {len(tickets)} tickets")

asyncio.run(main())
```

---

## Full example scripts

The `examples/` directory in the repository has ready-to-run scripts:

| Script | Description |
|--------|-------------|
| `examples/api/basic_usage.py` | Sync client — version, CRUD, pagination, sub-items, error handling |
| `examples/async_api/basic_async.py` | Async client — same coverage |
| `examples/oauth2/basic_oauth2.py` | OAuth2 sync + async — GLPI 11+ |
