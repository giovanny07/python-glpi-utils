# python-glpi-utils

[![Tests](https://github.com/yourusername/python-glpi-utils/actions/workflows/tests.yaml/badge.svg)](https://github.com/yourusername/python-glpi-utils/actions/workflows/tests.yaml)
[![PyPI version](https://img.shields.io/pypi/v/glpi-utils.svg)](https://pypi.org/project/glpi-utils/)
[![Python versions](https://img.shields.io/pypi/pyversions/glpi-utils.svg)](https://pypi.org/project/glpi-utils/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**python-glpi-utils** is a Python library for working with the [GLPI 11](https://glpi-project.org/) REST API.

It provides:

- A **synchronous** client (`GlpiAPI`) powered by `requests`.
- An **asynchronous** client (`AsyncGlpiAPI`) powered by `aiohttp`.
- Fluent **item-type accessors** (`api.ticket`, `api.computer`, `api.user`, …) so you write `api.ticket.get(1)` instead of building raw HTTP calls.
- A **`GLPIVersion`** helper for comparing GLPI API versions.
- A clean **exception hierarchy** so you can catch exactly what you need.

> **Scope:** This library targets the GLPI 11 legacy REST API (`/apirest.php`).  
> OAuth2 support for the high-level API (`/api.php`) is planned for a future release.

---

## Requirements

| Dependency | Version |
|------------|---------|
| Python     | ≥ 3.9   |
| GLPI       | 11.x    |
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
git clone https://github.com/yourusername/python-glpi-utils
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

print("GLPI version:", api.version)   # GLPIVersion('11.0.0')
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
print(type(ver).__name__, ver)   # GLPIVersion 11.0.0

print(ver > 10.0)      # True
print(ver == "11.0.0") # True
print(ver.major)       # 11
print(ver.minor)       # 0
print(ver.patch)       # 0
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

```python
import logging
logging.basicConfig(level=logging.DEBUG)

from glpi_utils import GlpiAPI
api = GlpiAPI(url="https://glpi.example.com")
api.login(username="glpi", password="glpi")
```

---

## Running the tests

```bash
pip install -e .[async]
pip install -r requirements-dev.txt
pytest
```

---

## License

**python-glpi-utils** is distributed under the [MIT License](LICENSE).
