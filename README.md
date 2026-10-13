# python-glpi-utils

[![Tests](https://github.com/giovanny07/python-glpi-utils/actions/workflows/tests.yaml/badge.svg)](https://github.com/giovanny07/python-glpi-utils/actions/workflows/tests.yaml)
[![PyPI version](https://img.shields.io/pypi/v/glpi-utils.svg)](https://pypi.org/project/glpi-utils/)
[![Python versions](https://img.shields.io/pypi/pyversions/glpi-utils.svg)](https://pypi.org/project/glpi-utils/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/giovanny07/python-glpi-utils/blob/main/LICENSE)

Python client for [GLPI](https://glpi-project.org/) that handles both of its APIs for you: the legacy REST API and the OAuth2 High-Level API, sync or async, with pagination and token refresh built in.

You write `api.ticket.get_all_pages()` instead of managing session tokens, `Content-Range` headers, OAuth2 expiry and the different URL layout of each API. MIT licensed, Python 3.9+, one runtime dependency (`requests`; `aiohttp` for async).

```python
from glpi_utils import GlpiAPI

with GlpiAPI(url="https://glpi.example.com") as api:      # logs out on exit
    api.login(username="glpi", password="glpi")
    print(api.version)                                     # 12.0.0

    ticket = api.ticket.create({"name": "srv-db01 unreachable", "content": "ICMP loss 100%"})
    api.ticket.add_sub_item(ticket["id"], "ITILFollowup", {"content": "On-call notified"})

    for t in api.ticket.get_all_pages():                   # every page, fetched for you
        print(t["id"], t["name"])                          # 7 srv-db01 unreachable
```

## Why this one

The most used alternative on PyPI is [`glpi-api`](https://github.com/unistra/python-glpi-api). Choose by what you need:

| | python-glpi-utils | glpi-api |
|---|---|---|
| Legacy REST API (`/apirest.php`) | yes | yes |
| High-Level API with OAuth2 (`/api.php`, GLPI 11 and 12) | yes, with HL API version pinning | no |
| Async client (`aiohttp`) | yes | no |
| Fetch every page in one call | `get_all_pages()` / `iter_pages()` | no |
| Search by field *name* instead of search-option ID | no | yes (`field_id`, `list_search_options`) |
| `get_multiple_items`, `download_document` | no | yes |

If you only call the legacy API synchronously and want to search by field names, `glpi-api` is the more established choice. Use this library for async code, the High-Level API, or GLPI 11/12 deployments where OAuth2 is the supported path.

## Install

```bash
pip install glpi-utils             # sync clients
pip install "glpi-utils[async]"    # + AsyncGlpiAPI / AsyncGlpiOAuthClient
```

On the GLPI side, enable the API in *Setup → General → API*. For the legacy API, create an API client there if you need an App-Token. For the High-Level API, add an OAuth client in *Setup → OAuth clients* with the `Password` grant and the `api` scope.

## The four clients

| Client | GLPI API | Auth | GLPI versions |
|---|---|---|---|
| `GlpiAPI` / `AsyncGlpiAPI` | legacy `/apirest.php` | username + password, or personal `user_token`; optional App-Token | 9.1 and later |
| `GlpiOAuthClient` / `AsyncGlpiOAuthClient` | High-Level `/api.php` | OAuth2 password grant, token refreshed automatically | 11.0.6 and later, 12 |

```python
from glpi_utils.oauth import GlpiOAuthClient

with GlpiOAuthClient(url="https://glpi.example.com", client_id="...", client_secret="...",
                     username="svc-api", password="...", api_version="2.3") as api:
    api.authenticate()
    api.search("Ticket", filter="status.id==1;name=like=*srv*", limit=20)
```

**Pin `api_version` on the OAuth2 clients.** Without it, GLPI 12 answers with High-Level API 3.0, whose schemas differ from 2.3 on GLPI 11. `api_version="2.3"` works on both. See the [OAuth2 guide](https://giovanny07.github.io/python-glpi-utils/guides/oauth2/) for the differences.

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

Tested in CI on Python 3.9 to 3.13 with mocked HTTP. Tested by hand against real servers for 1.5.0 (2026-10-13): GLPI 10.0.28 (legacy API), 11.0.9 and 12.0.0 (legacy API, High-Level API 2.3 and 3.0). Older GLPI 9.x and 10.x releases are expected to work with the legacy clients but are not tested.

## Contributing

Bug reports with your GLPI version and a traceback are the most useful contribution: [open an issue](https://github.com/giovanny07/python-glpi-utils/issues). For code, see the [contributing guide](https://github.com/giovanny07/python-glpi-utils/blob/main/CONTRIBUTING.md).

## License

[MIT](https://github.com/giovanny07/python-glpi-utils/blob/main/LICENSE).
