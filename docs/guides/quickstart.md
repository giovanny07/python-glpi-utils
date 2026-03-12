# Quick Start

## Synchronous

```python
from glpi_utils import GlpiAPI

api = GlpiAPI(url="https://glpi.example.com", app_token="YOUR_APP_TOKEN")
api.login(username="glpi", password="glpi")

# Server version
print(api.version)        # GLPIVersion('11.0.0')
print(api.version > 10.0) # True

# Fetch tickets (single page)
tickets = api.ticket.get_all(range="0-9", expand_dropdowns=True)

# Fetch ALL tickets (auto-pagination)
all_tickets = api.ticket.get_all_pages()
print(f"{len(all_tickets)} tickets total")

api.logout()
```

## Asynchronous

```python
import asyncio
from glpi_utils import AsyncGlpiAPI

async def main():
    api = AsyncGlpiAPI(url="https://glpi.example.com")
    await api.login(username="glpi", password="glpi")

    version = await api.get_version()
    print(f"GLPI {version}")

    all_tickets = await api.ticket.get_all_pages()
    print(f"{len(all_tickets)} tickets total")

    await api.logout()

asyncio.run(main())
```

## Context manager (recommended)

The context manager calls `logout()` automatically — even if an exception occurs:

```python
# Sync
with GlpiAPI(url="https://glpi.example.com") as api:
    api.login(username="glpi", password="glpi")
    computers = api.computer.get_all_pages()

# Async
async with AsyncGlpiAPI(url="https://glpi.example.com") as api:
    await api.login(username="glpi", password="glpi")
    computers = await api.computer.get_all_pages()
```

## OAuth2

```python
from glpi_utils.oauth import GlpiOAuthClient

with GlpiOAuthClient(
    url="https://glpi.example.com",
    client_id="my-app",
    client_secret="my-secret",
) as api:
    api.authenticate()
    tickets = api.ticket.get_all_pages()
```

## Environment variables

Avoid hardcoding credentials by using environment variables:

```bash
export GLPI_URL=https://glpi.example.com
export GLPI_APP_TOKEN=your_app_token
export GLPI_USER=glpi
export GLPI_PASSWORD=glpi
```

```python
api = GlpiAPI()   # reads GLPI_URL + GLPI_APP_TOKEN
api.login()       # reads GLPI_USER + GLPI_PASSWORD
```
