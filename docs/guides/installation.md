# Installation

## Requirements

| Dependency | Version         |
|------------|-----------------|
| Python     | ≥ 3.9           |
| GLPI       | 11.x            |
| requests   | ≥ 2.28          |
| aiohttp    | ≥ 3.9 *(async only)* |

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
pip install -e .[async]
```

For development (includes test and lint tools):

```bash
pip install -e ".[async,dev]"
```

---

## Verify installation

```python
import glpi_utils
print(glpi_utils.__version__)  # 1.2.0
```

---

## GLPI prerequisites

Before using the library your GLPI server needs:

1. **REST API enabled** — *Setup → General → API → Enable REST API*
2. **Application token** (optional but recommended) — *Setup → General → API → Add API client*
3. **User token** (optional) — user profile page → *Remote access key*

For the OAuth2 client (`/api.php`) you also need:

4. **OAuth2 application** registered in GLPI — *Setup → OAuth2 applications*
