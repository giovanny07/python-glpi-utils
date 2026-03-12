# Changelog

All notable changes to **python-glpi-utils** are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.3.0] – 2026-03-12

### Added

- **MkDocs documentation site** — full documentation published to GitHub Pages at
  `https://giovanny07.github.io/python-glpi-utils/`, built with
  [MkDocs Material](https://squidfunk.github.io/mkdocs-material/) and
  [mkdocstrings](https://mkdocstrings.github.io/):
  - Getting Started guides: Installation, Quick Start, Authentication.
  - How-to guides: CRUD Operations, Auto-pagination, OAuth2, Error Handling, Logging.
  - Full API Reference auto-generated from docstrings: `GlpiAPI`, `AsyncGlpiAPI`,
    `GlpiOAuthClient`, `AsyncGlpiOAuthClient`, exceptions, `GLPIVersion`, logger utilities.
- **`CONTRIBUTING.md`** — contributing guide covering development setup, running tests,
  code style (Ruff + mypy), PR workflow, commit message format, and bug reporting.
- **GitHub Actions `docs.yaml` workflow** — automatically deploys the MkDocs site to
  GitHub Pages on every push to `main`.
- **GitHub Actions `release.yaml` workflow** — automatically builds and publishes to PyPI
  when a `v*.*.*` tag is pushed. Requires `PYPI_API_TOKEN` secret in repository settings.
- **`mkdocs.yml`** — MkDocs configuration with Material theme, dark/light toggle,
  navigation tabs, search, and `mkdocstrings` plugin for API auto-documentation.

### Fixed

- **CI: `aiohttp` not installed in test runner** — changed `pip install -e .` to
  `pip install -e ".[async]"` in `.github/workflows/tests.yaml`. This caused all
  async tests (`AsyncGlpiAPI`, `AsyncGlpiOAuthClient`) to fail on the GitHub Actions
  runner despite passing locally. All 262 tests now pass on Python 3.9 – 3.13.

### Changed

- `requirements-dev.txt` — added MkDocs dependencies:
  `mkdocs`, `mkdocs-material`, `mkdocstrings[python]`, `mkdocs-autorefs`.
- `setup.cfg` `[dev]` extras — same MkDocs dependencies added for `pip install -e ".[dev]"`.

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
  - `tests/test_pagination.py` — 19 tests.
  - `tests/test_logger.py` — 22 tests.
  - `tests/test_oauth.py` — 61 tests.

---

## [1.1.0] – 2025-01-15

### Added

- `tests/__init__.py` — package marker for consistent test discovery across tools and CI.
- `tests/common.py` — shared helpers (`mock_response`, `make_api`).
- `tests/test_version.py` — 22 tests for `GLPIVersion`.
- `tests/test_api.py` — comprehensive sync API tests (init, auth, errors, version, CRUD, sub-items, session, ItemProxy).
- `tests/test_aioapi.py` — full async client coverage with `pytest-asyncio`.
- `tests/test_exceptions.py` — exception hierarchy, attributes, repr, str.

### Changed

- `setup.cfg`: added `asyncio_mode = auto` and `asyncio_default_fixture_loop_scope = function`.

### Fixed

- Replaced `X | None` syntax (Python 3.10+) with `Optional[X]` for Python 3.9 compatibility across all modules.

---

## [1.0.0] – 2025-01-01

### Added

- **`GlpiAPI`** — synchronous client for the GLPI 11 legacy REST API (`/apirest.php`).
- **`AsyncGlpiAPI`** — asynchronous client powered by `aiohttp`.
- Fluent item-type accessors: `api.ticket`, `api.computer`, `api.user`, … and `api.item("AnyItemtype")`.
- **`GLPIVersion`** — comparable version wrapper with rich comparisons.
- Full exception hierarchy: `GlpiError`, `GlpiAPIError`, `GlpiAuthError`, `GlpiNotFoundError`, `GlpiPermissionError`, `GlpiConnectionError`.
- Authentication: username/password, personal user token, environment variables.
- CRUD operations, sub-item operations, session utilities, document upload.
- Context-manager support for sync and async clients.
- GitHub Actions CI across Python 3.9 → 3.13.
