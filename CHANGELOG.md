# Changelog

All notable changes to **python-glpi-utils** are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
