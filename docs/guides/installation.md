# Installation

## Requirements

| Dependency | Version |
|------------|---------|
| Python     | ≥ 3.9   |
| GLPI       | ≥ 10.0  |
| requests   | ≥ 2.28  |
| aiohttp    | ≥ 3.9 *(async only)* |

### GLPI version compatibility

| Client | Endpoint | GLPI version |
|--------|----------|-------------|
| `GlpiAPI` / `AsyncGlpiAPI` | `/apirest.php` | **10.0, 11.x, 12.x** |
| `GlpiOAuthClient` / `AsyncGlpiOAuthClient` | `/api.php` | **11.0.6+, 12.x** |

The OAuth2 high-level API (`/api.php`) was introduced in GLPI 11. GLPI 9.x is not supported. Tested in CI against real servers: the latest patch of GLPI 10.0, 11.0 and 12.0, on every pull request and weekly.

---

## From PyPI

Standard install (synchronous client only):

```bash
pip install glpi-utils
```

With async support (`AsyncGlpiAPI`, `AsyncGlpiOAuthClient`):

```bash
pip install glpi-utils[async]
```

---

## From source

```bash
git clone https://github.com/giovanny07/python-glpi-utils
cd python-glpi-utils
pip install -e ".[async]"
```

For development (includes test and lint tools):

```bash
pip install -e ".[async,dev]"
```

---

## Verify installation

```python
import glpi_utils
print(glpi_utils.__version__)  # 1.3.4
```

---

## GLPI prerequisites

Before using the library your GLPI server needs:

1. **REST API enabled** — *Setup → General → API → Enable REST API*
2. **Application token** (optional but recommended) — *Setup → General → API → Add API client*
3. **User token** (optional) — user profile page → *Remote access key*

For the OAuth2 client (`/api.php`) — GLPI 11+ only:

4. **OAuth2 application** registered in GLPI — *Setup → OAuth2 applications*
