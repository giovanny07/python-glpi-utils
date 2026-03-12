# python-glpi-utils

[![Tests](https://github.com/giovanny07/python-glpi-utils/actions/workflows/tests.yaml/badge.svg)](https://github.com/giovanny07/python-glpi-utils/actions/workflows/tests.yaml)
[![PyPI version](https://img.shields.io/pypi/v/glpi-utils.svg)](https://pypi.org/project/glpi-utils/)
[![Python versions](https://img.shields.io/pypi/pyversions/glpi-utils.svg)](https://pypi.org/project/glpi-utils/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/giovanny07/python-glpi-utils/blob/main/LICENSE)

**python-glpi-utils** is a Python library for working with the [GLPI 11](https://glpi-project.org/) REST API.

---

## Features

- 🔄 **Synchronous** client (`GlpiAPI`) powered by `requests`
- ⚡ **Asynchronous** client (`AsyncGlpiAPI`) powered by `aiohttp`
- 🔐 **OAuth2** clients (`GlpiOAuthClient` / `AsyncGlpiOAuthClient`) for the GLPI 11 high-level API with automatic token refresh
- 📄 **Auto-pagination** — fetch every item across all pages with a single call (`get_all_pages` / `iter_pages`)
- 🧩 **Fluent accessors** — write `api.ticket.get(1)` instead of building raw HTTP calls
- 🔒 **`SensitiveFilter`** — masks passwords and tokens in debug logs automatically
- 📦 **Clean exception hierarchy** — catch exactly what you need
- ✅ **262 tests** across Python 3.9 – 3.13

---

## Installation

```bash
pip install glpi-utils
```

With async support:

```bash
pip install glpi-utils[async]
```

---

## Quick example

```python
from glpi_utils import GlpiAPI

with GlpiAPI(url="https://glpi.example.com", app_token="YOUR_APP_TOKEN") as api:
    api.login(username="glpi", password="glpi")

    # All tickets — automatic pagination
    tickets = api.ticket.get_all_pages()
    print(f"Total tickets: {len(tickets)}")

    # Create a ticket
    new = api.ticket.create({
        "name": "Service degraded",
        "content": "Users report slow response times.",
        "type": 1,
        "status": 1,
    })
    print(f"Created ticket #{new['id']}")
```

---

## Supported APIs

| Client | Endpoint | Auth |
|--------|----------|------|
| `GlpiAPI` | `/apirest.php` | Session token |
| `AsyncGlpiAPI` | `/apirest.php` | Session token |
| `GlpiOAuthClient` | `/api.php` | OAuth2 Bearer |
| `AsyncGlpiOAuthClient` | `/api.php` | OAuth2 Bearer |

---

## Next steps

- [Installation](guides/installation.md)
- [Quick Start](guides/quickstart.md)
- [Authentication](guides/authentication.md)
- [API Reference](api/glpi_api.md)
