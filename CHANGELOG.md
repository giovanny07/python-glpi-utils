# Changelog

All notable changes to **python-glpi-utils** are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.2.0] – 2025-03-01

### Added

- **Auto-pagination (`get_all_pages` / `iter_pages`)** — both sync and async clients now expose two new methods:
  - `get_all_pages(itemtype, page_size=50, **kwargs)` — fetches every item across all pages and returns a flat list. Uses the `Content-Range` response header from GLPI to know the total, with a partial-page fallback for servers that omit the header.
  - `iter_pages(itemtype, page_size=50, **kwargs)` — memory-efficient generator/async generator that yields one page at a time.
  - Both methods are also available on all `ItemProxy` / `AsyncItemProxy` objects: `api.ticket.get_all_pages()`, `api.computer.iter_pages(page_size=100)`, etc.
- **`glpi_utils.logger` module** — new logging utilities:
  - `SensitiveFilter` — `logging.Filter` that masks passwords, tokens, session IDs and Authorization headers before they reach any log handler. Attached automatically to the `glpi_utils.api` and `glpi_utils.aio` loggers.
  - `EmptyHandler` — silent no-op handler so the library never emits output by default.
  - `mask_secret(value)` — helper that reveals only the first/last 4 characters of a secret.
  - `hide_sensitive(data)` — recursively sanitizes dicts, lists and tuples.
- **`GlpiOAuthClient`** — new synchronous client for the GLPI 11 **High-level API** (`/api.php`):
  - OAuth2 `client_credentials` grant (service accounts, automation).
  - OAuth2 `password` grant (username + password).
  - Automatic token refresh — re-authenticates transparently when the Bearer token expires.
  - Full CRUD + sub-items + pagination (`get_all_pages`, `iter_pages`) — identical interface to `GlpiAPI`.
  - Environment variable support: `GLPI_OAUTH_CLIENT_ID`, `GLPI_OAUTH_CLIENT_SECRET`, `GLPI_OAUTH_USERNAME`, `GLPI_OAUTH_PASSWORD`.
- **`AsyncGlpiOAuthClient`** — async counterpart to `GlpiOAuthClient`, powered by `aiohttp`.
- **`glpi_utils.api._parse_content_range`** — internal helper that parses GLPI's `Content-Range: 0-49/1337` header.

### Changed

- `glpi_utils.api.get_all_items` docstring updated to mention `get_all_pages` as the preferred method for full dataset retrieval.
- `glpi_utils.aio.AsyncGlpiAPI._request` now delegates to `_request_with_headers` (DRY refactor).
- `glpi_utils/_resource.py` — `ItemProxy` and `AsyncItemProxy` now expose `get_all_pages` and `iter_pages`.
- `glpi_utils/__init__.py` — exports `GlpiOAuthClient`, `AsyncGlpiOAuthClient`, `SensitiveFilter`, `EmptyHandler`.

### Tests

- Added 102 new tests across three new test modules (262 total, up from 160):
  - `tests/test_pagination.py` — 19 tests: `_parse_content_range`, multi-page sync, async, `iter_pages`, proxy forwarding.
  - `tests/test_logger.py` — 22 tests: `mask_secret`, `hide_sensitive` (nested dicts, lists, tuples, depth guard), `SensitiveFilter`, `EmptyHandler`.
  - `tests/test_oauth.py` — 61 tests: `_TokenStore`, `GlpiOAuthClient` (init, auth flows, CRUD, pagination, proxy, context manager), `AsyncGlpiOAuthClient` (init, auth, CRUD, pagination, proxy, context manager).

---

## [1.1.0] – 2025-01-15

### Added

- **`tests/__init__.py`** – proper package marker so test discovery works consistently across all tools and CI runners (mirrors pattern from `zabbix-utils`).
- **`tests/common.py`** – shared test helpers (`mock_response`, `make_api`) to avoid repetition across test modules.
- **`tests/test_version.py`** – dedicated test module for `GLPIVersion` (22 assertions: parsing, comparisons, hash, edge cases).
- **`tests/test_api.py`** – comprehensive sync API tests split into focused classes: init, auth, errors, version, CRUD, sub-items, session utilities, ItemProxy (covers all 25 built-in aliases, caching, error messages, HTTP method verification, bool→int param conversion).
- **`tests/test_aioapi.py`** – full async client coverage using `pytest-asyncio` (login flows, CRUD, sub-items, context manager, version fetch).
- **`tests/test_exceptions.py`** – exception hierarchy, attribute storage, `repr`, `str`, and inheritance chain.

### Changed

- `setup.cfg`: added `asyncio_mode = auto` and `asyncio_default_fixture_loop_scope = function` for `pytest-asyncio` compatibility.
- `setup.cfg`: `pytest-asyncio >= 0.23` already listed in `[dev]` extras.

### Fixed

- Replaced `X | None` union type syntax (Python 3.10+) with `Optional[X]` from `typing` for full Python 3.9 compatibility across `exceptions.py`, `api.py`, `aio.py`, `_resource.py`, and `version.py`.

---

## [1.0.0] – 2025-01-01

### Added

- **`GlpiAPI`** – synchronous client for the GLPI 11 legacy REST API (`/apirest.php`).
- **`AsyncGlpiAPI`** – asynchronous client powered by `aiohttp`.
- **Fluent item-type accessors** – `api.ticket`, `api.computer`, `api.user`, … and `api.item("AnyItemtype")` for custom types.
- **`GLPIVersion`** – comparable wrapper around GLPI version strings with rich comparisons (`>`, `==`, etc.).
- **Full exception hierarchy**: `GlpiError`, `GlpiAPIError`, `GlpiAuthError`, `GlpiNotFoundError`, `GlpiPermissionError`, `GlpiConnectionError`.
- **Authentication**: username/password (Basic Auth), personal user token, and environment variable support (`GLPI_URL`, `GLPI_USER`, `GLPI_PASSWORD`, `GLPI_USER_TOKEN`, `GLPI_APP_TOKEN`).
- **CRUD operations**: `get`, `get_all`, `search`, `create`, `update`, `delete` for all GLPI item types.
- **Sub-item operations**: `get_sub_items`, `add_sub_item` (followups, tasks, solutions, …).
- **Session utilities**: `get_my_profiles`, `set_active_profile`, `get_my_entities`, `set_active_entity`, `get_full_session`.
- **Document upload** via multipart form.
- Context-manager support for both sync and async clients.
- GitHub Actions workflow for CI across Python 3.9 → 3.13.

### Notes

- Targets GLPI 11 (legacy `apirest.php` API).
- OAuth2 / High-level API (`api.php`) support is planned for a future release.


All notable changes to **python-glpi-utils** are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] – 2025-01-01

### Added

- **`GlpiAPI`** – synchronous client for the GLPI 11 legacy REST API (`/apirest.php`).
- **`AsyncGlpiAPI`** – asynchronous client powered by `aiohttp`.
- **Fluent item-type accessors** – `api.ticket`, `api.computer`, `api.user`, … and `api.item("AnyItemtype")` for custom types.
- **`GLPIVersion`** – comparable wrapper around GLPI version strings with rich comparisons (`>`, `==`, etc.).
- **Full exception hierarchy**: `GlpiError`, `GlpiAPIError`, `GlpiAuthError`, `GlpiNotFoundError`, `GlpiPermissionError`, `GlpiConnectionError`.
- **Authentication**: username/password (Basic Auth), personal user token, and environment variable support (`GLPI_URL`, `GLPI_USER`, `GLPI_PASSWORD`, `GLPI_USER_TOKEN`, `GLPI_APP_TOKEN`).
- **CRUD operations**: `get`, `get_all`, `search`, `create`, `update`, `delete` for all GLPI item types.
- **Sub-item operations**: `get_sub_items`, `add_sub_item` (followups, tasks, solutions, …).
- **Session utilities**: `get_my_profiles`, `set_active_profile`, `get_my_entities`, `set_active_entity`, `get_full_session`.
- **Document upload** via multipart form.
- Context-manager support for both sync and async clients.
- Unit tests with mocked HTTP (no live server required).
- GitHub Actions workflows for tests and compatibility checks.

### Notes

- Targets GLPI 11 (legacy `apirest.php` API).
- OAuth2 / High-level API (`api.php`) support is planned for a future release.
