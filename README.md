# python-glpi-utils

[![Tests](https://github.com/giovanny07/python-glpi-utils/actions/workflows/tests.yaml/badge.svg)](https://github.com/giovanny07/python-glpi-utils/actions/workflows/tests.yaml)
[![PyPI version](https://img.shields.io/pypi/v/glpi-utils.svg)](https://pypi.org/project/glpi-utils/)
[![Python versions](https://img.shields.io/pypi/pyversions/glpi-utils.svg)](https://pypi.org/project/glpi-utils/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**python-glpi-utils** is a Python library for working with the [GLPI](https://glpi-project.org/) REST API.

It provides:

- A **synchronous** client (`GlpiAPI`) powered by `requests`.
- An **asynchronous** client (`AsyncGlpiAPI`) powered by `aiohttp`.
- **OAuth2 clients** (`GlpiOAuthClient` / `AsyncGlpiOAuthClient`) for the GLPI 11+ high-level API (`/api.php`) with automatic token refresh.
- **Auto-pagination** (`get_all_pages` / `iter_pages`) — fetch every item across all pages with one call.
- Fluent **item-type accessors** (`api.ticket`, `api.computer`, `api.user`, …) so you write `api.ticket.get_all_pages()` instead of building raw HTTP calls.
- A `SensitiveFilter` that masks passwords and tokens in debug logs automatically.
- A **`GLPIVersion`** helper for comparing GLPI versions.
- A clean **exception hierarchy** so you can catch exactly what you need.

> **Compatibility:**
> - Legacy REST API (`/apirest.php`): **GLPI 9.1 and above** (tested on 10.x and 11.x)
> - High-level OAuth2 API (`/api.php`): **GLPI 11.0.6+** recommended (11.0.5 has permission bugs)

---

## Requirements

| Dependency | Version |
|------------|---------|
| Python     | ≥ 3.9   |
| GLPI       | ≥ 9.1   |
| requests   | ≥ 2.28  |
| aiohttp    | ≥ 3.9 *(async only)* |

---

## Installation

### From PyPI

```bash
pip install glpi-utils
```

With async support:

```bash
pip install glpi-utils[async]
```

### From source

```bash
git clone https://github.com/giovanny07/python-glpi-utils
cd python-glpi-utils
pip install -e .[async]
```

---

## Quick start

### Synchronous

```python
from glpi_utils import GlpiAPI

api = GlpiAPI(url="https://glpi.example.com", app_token="YOUR_APP_TOKEN")
api.login(username="glpi", password="glpi")

print("GLPI version:", api.version)   # GLPIVersion('10.0.19')
print(api.version > 10.0)             # True

tickets = api.ticket.get_all(range="0-9", expand_dropdowns=True)
for t in tickets:
    print(f"[{t['id']}] {t['name']}")

api.logout()
```

### Asynchronous

```python
import asyncio
from glpi_utils import AsyncGlpiAPI

async def main():
    api = AsyncGlpiAPI(url="https://glpi.example.com")
    await api.login(username="glpi", password="glpi")

    version = await api.get_version()
    print("GLPI version:", version)

    tickets = await api.ticket.get_all(range="0-9")
    for t in tickets:
        print(f"[{t['id']}] {t['name']}")

    await api.logout()

asyncio.run(main())
```

### Context manager (auto-logout)

```python
# Sync
with GlpiAPI(url="https://glpi.example.com") as api:
    api.login(username="glpi", password="glpi")
    print(api.version)

# Async
async with AsyncGlpiAPI(url="https://glpi.example.com") as api:
    await api.login(username="glpi", password="glpi")
    version = await api.get_version()
```

---

## Authentication

Three methods are supported (sync and async):

```python
# 1. Username + password (Basic Auth)
api.login(username="glpi", password="glpi")

# 2. Personal API token (from user profile → Remote access key)
api.login(user_token="q56hqkniwot8wntb3z1qarka5atf365taaa2uyjrn")

# 3. Environment variables (no arguments needed)
#    GLPI_URL, GLPI_USER, GLPI_PASSWORD, GLPI_USER_TOKEN, GLPI_APP_TOKEN
api = GlpiAPI()   # reads GLPI_URL
api.login()       # reads GLPI_USER + GLPI_PASSWORD or GLPI_USER_TOKEN
```

---

## Item-type accessors

All standard GLPI item types are available as attributes:

| Attribute           | GLPI itemtype      |
|---------------------|--------------------|
| `api.ticket`        | `Ticket`           |
| `api.computer`      | `Computer`         |
| `api.monitor`       | `Monitor`          |
| `api.printer`       | `Printer`          |
| `api.networkequipment` | `NetworkEquipment` |
| `api.software`      | `Software`         |
| `api.user`          | `User`             |
| `api.group`         | `Group`            |
| `api.entity`        | `Entity`           |
| `api.location`      | `Location`         |
| `api.category`      | `ITILCategory`     |
| `api.problem`       | `Problem`          |
| `api.change`        | `Change`           |
| `api.project`       | `Project`          |
| `api.projecttask`   | `ProjectTask`      |
| `api.document`      | `Document`         |
| `api.contract`      | `Contract`         |
| `api.knowledgebase` | `KnowbaseItem`     |
| `api.followup`      | `ITILFollowup`     |
| `api.solution`      | `ITILSolution`     |
| `api.task`          | `TicketTask`       |

For any other item type use `api.item("YourItemtype")`:

```python
proxy = api.item("KnowbaseItem")
articles = proxy.get_all(range="0-4")
```

---

## Auto-pagination

By default `get_all()` returns a single page (50 items). Use `get_all_pages()` to retrieve everything automatically:

```python
# All tickets — pagination handled transparently
all_tickets = api.ticket.get_all_pages()

# With filters
open_tickets = api.ticket.get_all_pages(
    sort="date_mod",
    order="DESC",
    is_deleted=False,
)

# Custom page size (fewer round-trips on fast networks)
computers = api.computer.get_all_pages(page_size=100, expand_dropdowns=True)

print(f"Total: {len(all_tickets)} tickets")
```

For large datasets, use `iter_pages()` to process items batch by batch without loading everything into RAM:

```python
total = 0
for page in api.ticket.iter_pages(page_size=100):
    for ticket in page:
        process(ticket)
        total += 1
print(f"Processed {total} tickets")

# Async version
async for page in api.ticket.iter_pages(page_size=100):
    for ticket in page:
        await process(ticket)
```

---

## OAuth2 (High-level API — GLPI 11+ only)

> **Requires GLPI 11.0.6+** for full support. GLPI 11.0.5 has a known bug where
> `DELETE` and `Timeline` sub-items (`Followup`, `Task`, `Solution`) return
> `ERROR_RIGHT_MISSING` regardless of profile permissions.

For the GLPI 11 high-level API (`/api.php`), use the OAuth2 clients.

**Setup in GLPI:** Setup → OAuth clients → Add → Grants: `Password` → Scopes: `api`

> The `client_credentials` grant is **not supported** for the `api` scope in GLPI 11
> (only works for `inventory`). Always use the `password` grant.

```python
from glpi_utils.oauth import GlpiOAuthClient

# Pass username/password in constructor — used automatically on authenticate()
# and on any token refresh (no need to pass them again).
with GlpiOAuthClient(
    url="https://glpi.example.com",
    client_id="my-app",
    client_secret="my-secret",
    username="glpi",
    password="glpi",
) as api:
    api.authenticate()

    # Read
    tickets = api.ticket.get_all_pages()

    # Create / Update / Delete
    new = api.ticket.create({
        "name": "Test", "content": "...",
        "type": 1, "status": 1, "urgency": 3, "impact": 3, "priority": 3,
    })
    api.ticket.update({"id": new["id"], "status": 2})
    api.ticket.delete({"id": new["id"]})

    # Timeline sub-items
    api.ticket.add_sub_item(new["id"], "ITILFollowup", {
        "content": "Work in progress.", "is_private": 0,
    })
```

```python
# Async
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

The OAuth2 clients support all the same CRUD, sub-item, search and pagination
methods as `GlpiAPI`. Itemtypes are mapped to their namespaced HL API paths
automatically (`Ticket` → `Assistance/Ticket`, `Computer` → `Assets/Computer`, etc.).

Environment variables: `GLPI_OAUTH_CLIENT_ID`, `GLPI_OAUTH_CLIENT_SECRET`,
`GLPI_OAUTH_USERNAME`, `GLPI_OAUTH_PASSWORD`.

---

## CRUD operations

Every item-type accessor exposes the same set of methods:

```python
# Read
ticket  = api.ticket.get(1, expand_dropdowns=True)
tickets = api.ticket.get_all(range="0-49", sort="date_mod", order="DESC")

# Search engine
results = api.ticket.search(
    criteria=[{"field": 12, "searchtype": "equals", "value": 1}],
    forcedisplay=[1, 3, 12],
    range="0-49",
)

# Create
new = api.ticket.create({
    "name": "Service degraded",
    "content": "Users report slow response times.",
    "type": 1,
    "status": 1,
    "urgency": 3,
    "impact": 3,
    "priority": 3,
})

# Update (id required)
api.ticket.update({"id": new["id"], "status": 2})   # Assigned

# Delete
api.ticket.delete({"id": new["id"]})                 # to trash
api.ticket.delete({"id": new["id"]}, force_purge=True)  # permanent
```

### Sub-items (followups, tasks, solutions)

```python
# Read followups
followups = api.ticket.get_sub_items(1, "ITILFollowup")

# Add a followup
api.ticket.add_sub_item(1, "ITILFollowup", {
    "content": "Confirmed issue on node 3.",
    "is_private": 0,
})
```

---

## GLPIVersion

```python
ver = api.version
print(type(ver).__name__, ver)   # GLPIVersion 10.0.19

print(ver > 10.0)       # True
print(ver == "10.0.19") # True
print(ver.major)        # 10
print(ver.minor)        # 0
print(ver.patch)        # 19
```

---

## Error handling

```python
from glpi_utils import (
    GlpiError,
    GlpiAPIError,
    GlpiAuthError,
    GlpiNotFoundError,
    GlpiPermissionError,
)

try:
    ticket = api.ticket.get(99999)
except GlpiNotFoundError:
    print("Ticket does not exist")
except GlpiPermissionError:
    print("Insufficient rights")
except GlpiAuthError:
    print("Session expired – re-login")
except GlpiAPIError as e:
    print(f"API error {e.error_code}: {e.message}")
except GlpiError:
    print("Generic library error")
```

---

## Enabling debug logging

The library is silent by default. Enable with standard `logging`:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

from glpi_utils import GlpiAPI
api = GlpiAPI(url="https://glpi.example.com")
api.login(username="glpi", password="glpi")
```

Passwords, tokens and session IDs are **masked automatically** by `SensitiveFilter`. To add your own handler with masking:

```python
from glpi_utils import SensitiveFilter

handler = logging.StreamHandler()
handler.addFilter(SensitiveFilter())
logging.getLogger("glpi_utils").addHandler(handler)
logging.getLogger("glpi_utils").setLevel(logging.DEBUG)
```

---

## Running the tests

```bash
pip install -e ".[async,dev]"
pytest
```

---

## License

**python-glpi-utils** is distributed under the [MIT License](LICENSE).
