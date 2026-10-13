# python-glpi-utils

[![Tests](https://github.com/giovanny07/python-glpi-utils/actions/workflows/tests.yaml/badge.svg)](https://github.com/giovanny07/python-glpi-utils/actions/workflows/tests.yaml)
[![PyPI version](https://img.shields.io/pypi/v/glpi-utils.svg)](https://pypi.org/project/glpi-utils/)
[![Python versions](https://img.shields.io/pypi/pyversions/glpi-utils.svg)](https://pypi.org/project/glpi-utils/)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://github.com/giovanny07/python-glpi-utils/blob/main/LICENSE)

Python client for [GLPI](https://glpi-project.org/) that handles both of its APIs for you: the legacy REST API and the OAuth2 High-Level API, sync or async, with pagination and token refresh built in.

You write `api.ticket.get_all_pages()` instead of managing session tokens, `Content-Range` headers, OAuth2 expiry and the different URL layout of each API. Licensed under the [AGPL-3.0-or-later](https://github.com/giovanny07/python-glpi-utils/blob/main/LICENSE) since 2.0.0 (1.5.0 and earlier remain MIT). Python 3.9+, depends on `requests` (plus `aiohttp` for the async clients).

```bash
pip install glpi-utils      # imported as glpi_utils
```

```python
from glpi_utils import GlpiAPI

with GlpiAPI(url="https://glpi.example.com") as api:      # logs out on exit
    api.login(username="glpi", password="glpi")
    print(api.version)                                     # GLPI server version: 12.0.0

    ticket = api.ticket.create({"name": "srv-db01 unreachable", "content": "ICMP loss 100%"})
    api.ticket.add_sub_item(ticket["id"], "ITILFollowup", {"content": "On-call notified"})

    for t in api.ticket.get_all_pages():                   # every page, fetched for you
        print(t["id"], t["name"])                          # one line per ticket, e.g. 7 srv-db01 unreachable
```

## Why this one

The most used alternative on PyPI is [`glpi-api`](https://github.com/unistra/python-glpi-api). Choose by what you need:

| | python-glpi-utils | glpi-api |
|---|---|---|
| Legacy REST API (`/apirest.php`) | yes | yes |
| High-Level API with OAuth2 (`/api.php`, GLPI 11 and 12) | yes, with API version pinning | no |
| Async client (`aiohttp`) | yes | no |
| Fetch every page in one call | `get_all_pages()` / `iter_pages()` | no |
| Legacy search engine by field *name* (mapped to numeric search-option IDs) | no, pass the IDs | yes (`field_id`, `list_search_options`) |
| `get_multiple_items`, `download_document` | no | yes |
| License | AGPL-3.0-or-later | GPL-3.0 |

If you only call the legacy API synchronously and want to search it by field names, `glpi-api` is the more established choice. Use this library for async code or for the High-Level API of GLPI 11 and 12. Both libraries work with the legacy API on GLPI 12.

## Install

```bash
pip install glpi-utils             # GlpiAPI, GlpiOAuthClient
pip install "glpi-utils[async]"    # adds AsyncGlpiAPI, AsyncGlpiOAuthClient
```

On the GLPI side, enable the API in *Setup → General → API*. For the legacy API, pass `app_token=` only if your GLPI API client defines one. For the High-Level API, add an OAuth client in *Setup → OAuth clients* with the `Password` grant and the `api` scope.

## Clients

| Sync / async | GLPI API | Auth | GLPI versions |
|---|---|---|---|
| `GlpiAPI` / `AsyncGlpiAPI` | legacy `/apirest.php` | username + password, or personal `user_token` | 10.0 and later |
| `GlpiOAuthClient` / `AsyncGlpiOAuthClient` | High-Level `/api.php` | OAuth2 password grant, token refreshed automatically | 11.0.6 and later, 12 |

```python
from glpi_utils.oauth import GlpiOAuthClient

with GlpiOAuthClient(url="https://glpi.example.com", client_id="...", client_secret="...",
                     username="svc-api", password="...", api_version="2.3") as api:
    api.authenticate()
    api.search("Ticket", filter="status.id==1;name=like=*srv*", limit=20)
```

**Pin `api_version` on the OAuth2 clients.** If you leave it out, the server picks its newest High-Level API version: 2.3 on GLPI 11, 3.0 on GLPI 12. The two return different schemas. Pinning `"2.3"` keeps code written for GLPI 11 working on 12 (12.0.0 only adds a few fields to 2.3 and drops the `Plug` dropdowns); you miss the endpoints added in 3.0, such as login-session management. `filter` takes [RSQL](https://github.com/jirutka/rsql-parser) expressions over field names. See the [OAuth2 guide](https://giovanny07.github.io/python-glpi-utils/guides/oauth2/) for the differences.

All clients share the same accessors (`api.ticket`, `api.computer`, `api.user`, … or `api.item("AnyItemtype")`), CRUD methods, sub-items, typed exceptions (`GlpiAuthError`, `GlpiNotFoundError`, `GlpiPermissionError`…) and debug logging with passwords and tokens masked. Settings can come from environment variables (`GLPI_URL`, `GLPI_USER`, `GLPI_USER_TOKEN`, `GLPI_OAUTH_CLIENT_ID`, `GLPI_API_VERSION`…).

## Documentation

Guides and API reference: **https://giovanny07.github.io/python-glpi-utils/**

- [Quick start](https://giovanny07.github.io/python-glpi-utils/guides/quickstart/) and [authentication](https://giovanny07.github.io/python-glpi-utils/guides/authentication/)
- [CRUD, sub-items and the search engine](https://giovanny07.github.io/python-glpi-utils/guides/crud/)
- [Pagination](https://giovanny07.github.io/python-glpi-utils/guides/pagination/)
- [OAuth2 and the High-Level API](https://giovanny07.github.io/python-glpi-utils/guides/oauth2/), including GLPI 12 / API 3.0
- [Error handling](https://giovanny07.github.io/python-glpi-utils/guides/error_handling/) and [logging](https://giovanny07.github.io/python-glpi-utils/guides/logging/)
- Runnable scripts in [`examples/`](https://github.com/giovanny07/python-glpi-utils/tree/main/examples)

## Status

Beta, actively maintained. Releases follow [semantic versioning](https://semver.org/) and every change is listed in the [CHANGELOG](https://github.com/giovanny07/python-glpi-utils/blob/main/CHANGELOG.md). The legacy clients are the most stable part. The OAuth2 clients follow GLPI's High-Level API, which is still evolving, and their behaviour changed in 1.4 and 1.5.

The plan is to declare the library stable in 2.1.0. That needs four consecutive weeks of passing integration runs against GLPI 10, 11 and 12, counted from 2026-10-13, with no change to the public API in that time. From then on, the public API is every name exported by `glpi_utils` and `glpi_utils.oauth` that does not start with an underscore. Removing or changing any of those names will need a new major version, and will be preceded by at least one minor release in which the old form emits a `DeprecationWarning`.

Unit tests run in CI on Python 3.9 to 3.13. Integration tests run both clients, sync and async, against official `glpi/glpi` containers: the latest patch of GLPI 10.0 (legacy API), 11.0 and 12.0 (legacy API and every High-Level API version the server offers), on every pull request and weekly. GLPI 9.x is not supported.

## Contributing

Bug reports with your GLPI version and a traceback are the most useful contribution: [open an issue](https://github.com/giovanny07/python-glpi-utils/issues). For code, see the [contributing guide](https://github.com/giovanny07/python-glpi-utils/blob/main/CONTRIBUTING.md).

## License

Copyright (C) 2025-2026 Giovanny Rodriguez, Imagunet.

This program is free software: you can redistribute it and/or modify it under the terms of the [GNU Affero General Public License](https://github.com/giovanny07/python-glpi-utils/blob/main/LICENSE) as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. It is distributed WITHOUT ANY WARRANTY; see the license for details.

Releases up to and including 1.5.0 were published under the MIT License and remain available under it.
