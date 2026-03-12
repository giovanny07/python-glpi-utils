# Changelog

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
