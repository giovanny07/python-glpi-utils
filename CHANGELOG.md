# Changelog

All notable changes to **python-glpi-utils** are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.4.1] – 2026-03-16

### Added

- **`_HLAPI_ROUTE_MAP`**: Complete route map for the GLPI 11 High-Level API (`/api.php`).
  The HL API uses namespaced paths instead of flat itemtypes. 35 itemtypes mapped across
  5 namespaces: `Assistance/`, `Assets/`, `Administration/`, `Management/`, `Dropdowns/`,
  `Knowledgebase/` and `Project/`.
- **`_hl_route(itemtype)`** helper: Resolves any GLPI itemtype to its correct HL API path.
  Falls back to the itemtype name as-is for unmapped types (plugins, custom assets).

### Changed

- **`GlpiOAuthClient` / `AsyncGlpiOAuthClient`** now accept `username` and `password`
  in the constructor. They are used automatically in `authenticate()` and token refresh,
  removing the need to pass credentials on every call.
- **`client_credentials` grant**: Documented as unsupported for the `api` scope in GLPI 11
  (only works for `inventory`). The `password` grant is the recommended method for scripts.
- **Update operations** now use `PATCH /{route}/{id}` instead of `PUT` — GLPI 11 HL API
  only accepts `GET`, `PATCH`, `DELETE` on individual resources.
- **Create operations** now send the object directly as the JSON body (no `{"input": ...}`
  wrapper) — HL API v2 does not use the legacy input wrapper.
- **Delete operations** now use `DELETE /{route}/{id}` with no request body.

### Fixed

- **`__getattr__` recursion bug** in both OAuth clients: accessing `api.ticket` triggered
  recursive `__getattr__` calls when `_proxies` was not yet in `__dict__`, causing the proxy
  to be created with a corrupted session reference. The `Authorization: Bearer` header was
  never sent, resulting in `ERROR_UNAUTHENTICATED` on every request after `authenticate()`.
  Fixed by using `object.__getattribute__` to access `_proxies` safely.
- **`Content-Type: application/json` on GET requests**: GLPI 11 interprets this header as
  requiring a JSON body, returning `"Cuerpo JSON inválido"` on GET requests that have no
  body. Fixed by only including `Content-Type` when there is a JSON payload.
- **Token endpoint**: Fixed `_token_url` construction when the base URL included
  `/api.php/v2.2` — the token endpoint is always `/api.php/token` regardless of API version.

---

## [1.4.0] – 2026-03-16

### Added

- **`_HLAPI_ROUTE_MAP`** (initial version): First namespace-aware route map for the GLPI 11
  High-Level API. Covered core itemtypes: `Assistance/Ticket`, `Assets/Computer`,
  `Administration/User`, etc.
- **`_hl_route(itemtype)`** helper introduced to resolve itemtypes to their HL API paths.

### Changed

- **CRUD operations adapted for HL API v2 semantics**:
  - `create_item`: body sent directly without `{"input": ...}` wrapper.
  - `update_item`: uses `PATCH /{route}/{id}` with ID extracted from input dict.
  - `delete_item`: uses `DELETE /{route}/{id}` with no request body.

---

## [1.3.9] – 2026-03-16

### Added

- **`_HLAPI_ROUTE_MAP`** (preliminary): Initial route map covering `Assistance/Ticket`,
  `Assets/Computer`, `Administration/User`, `Management/Contract` and a subset of other
  common itemtypes, derived from the GLPI 11 Swagger endpoint list.

---

## [1.3.8] – 2026-03-16

### Fixed

- **`Content-Type: application/json` on GET requests**: `_auth_headers()` previously
  included `Content-Type` on every request. GLPI 11 interprets this header as requiring
  a valid JSON body, returning `"Cuerpo JSON inválido"` (400) on GET requests with no body.
  Fixed with a `with_content_type` flag — only sent when a JSON payload is present.

---

## [1.3.7] – 2026-03-16

### Fixed

- **Token URL construction**: `_token_url` now always resolves to `/api.php/token`
  regardless of what the base URL contains. Passing a URL with `/api.php/v2.2` no longer
  causes double-path issues on the token and API endpoints.

---

## [1.3.6] – 2026-03-16

### Changed

- **`GlpiOAuthClient` / `AsyncGlpiOAuthClient`** ahora aceptan `username` y `password` en el constructor. Estos se usan automáticamente en `authenticate()` y en re-autenticaciones (`_ensure_token`), evitando tener que pasarlos en cada llamada.
- **`client_credentials` grant documentado como no soportado** para el scope `api` en GLPI 11 (solo funciona para `inventory`). El grant recomendado es `password`.

### Fixed

- Re-autenticación automática (`_ensure_token`) fallaba silenciosamente cuando no se pasaban username/password en `authenticate()` inicial.

---

## [1.3.5] – 2026-03-16

### Fixed

- **`GlpiOAuthClient` / `AsyncGlpiOAuthClient` — `__getattr__` recursion bug:**
  Accessing `api.ticket` (o cualquier proxy) disparaba recursión en `__getattr__`
  cuando `_proxies` no existía aún en `__dict__`, dejando el proxy sin sesión válida.
  El header `Authorization: Bearer` nunca se enviaba → `ERROR_UNAUTHENTICATED`.
  Fix: usar `object.__getattribute__` para acceder a `_proxies` de forma segura.

---

## [1.3.4] – 2026-03-12

### Changed

- **GLPI compatibility clarified across all docs:** The legacy REST API (`/apirest.php`)
  supports **GLPI ≥ 9.1** (tested on 9.x, 10.x and 11.x), not just GLPI 11 as previously
  documented. Confirmed working on GLPI 10.0.19.
- **OAuth2 scope made explicit:** All documentation pages now clearly state that
  `GlpiOAuthClient` / `AsyncGlpiOAuthClient` require **GLPI 11+**. An admonition warning
  was added to the OAuth2 guide.
- Updated `README.md` — requirements table now shows `GLPI ≥ 9.1`, examples use
  `GLPIVersion('10.0.19')`, compatibility note added.
- Updated `setup.cfg` description to `GLPI REST API (9.1+, 10.x, 11.x)`.
- Updated `mkdocs.yml` site description.
- Updated `docs/index.md` — added GLPI compatibility table.
- Updated `docs/guides/installation.md` — added per-client compatibility table,
  version bumped to 1.3.4.
- Updated `docs/guides/authentication.md` and `docs/guides/oauth2.md` — GLPI version
  requirements made explicit throughout.

---

## [1.3.3] – 2026-03-12

### Fixed

- **Version detection:** `cfg_glpi.version` is the correct key in GLPI 10.x — not `glpi_version`.
  The version property now probes `cfg_glpi.version` → `cfg_glpi.glpi_version` → `glpi_version`
  → `getFullSession` fallback, making it robust across GLPI 9.x / 10.x / 11.x.
- **HTTP 206 Partial Content not accepted:** GLPI returns 206 (not 200) for paginated list
  responses. `_raise_for_glpi_error` previously treated 206 as an error, causing `get_all`
  and `get_all_pages` to raise `GlpiAPIError` with the first ticket as the "error message".
  Fixed in `api.py` and `oauth.py`.

### Changed

- **GLPI compatibility clarified:** The legacy REST API (`/apirest.php`) works with
  **GLPI 9.1 and above** (not just 11.x as previously documented). Confirmed working
  on GLPI 10.0.19. OAuth2 (`/api.php`) remains GLPI 11+ only.
- Updated `README.md`, `setup.cfg`, `mkdocs.yml` and all documentation pages to reflect
  `GLPI ≥ 9.1` support for the legacy API clients.

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
