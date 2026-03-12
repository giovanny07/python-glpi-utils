# Error Handling

## Exception hierarchy

```
GlpiError
├── GlpiAPIError          ← HTTP error from GLPI (has status_code, error_code)
│   ├── GlpiAuthError     ← 401 / session expired
│   ├── GlpiNotFoundError ← 404 item not found
│   └── GlpiPermissionError ← 403 insufficient rights
└── GlpiConnectionError   ← network / timeout
```

---

## Basic usage

```python
from glpi_utils import (
    GlpiError,
    GlpiAPIError,
    GlpiAuthError,
    GlpiNotFoundError,
    GlpiPermissionError,
    GlpiConnectionError,
)

try:
    ticket = api.ticket.get(99999)
except GlpiNotFoundError:
    print("Ticket does not exist")
except GlpiPermissionError:
    print("Insufficient rights for this item")
except GlpiAuthError:
    print("Session expired — re-login")
except GlpiConnectionError as e:
    print(f"Network error: {e}")
except GlpiAPIError as e:
    print(f"API error {e.error_code} (HTTP {e.status_code}): {e}")
except GlpiError:
    print("Generic library error")
```

---

## Exception attributes

`GlpiAPIError` and its subclasses carry extra context:

```python
try:
    api.ticket.get(0)
except GlpiAPIError as e:
    print(e.status_code)   # int  — HTTP status code, e.g. 404
    print(e.error_code)    # str  — GLPI error code, e.g. "ERROR_ITEM_NOT_FOUND"
    print(str(e))          # str  — human-readable message
```

---

## Session expiry

GLPI sessions expire after inactivity. The recommended pattern is to wrap
your work in a context manager so logout is always called, and catch
`GlpiAuthError` to re-login if needed in long-running scripts:

```python
def run():
    with GlpiAPI(url="https://glpi.example.com") as api:
        api.login(username="glpi", password="glpi")
        try:
            return api.ticket.get_all_pages()
        except GlpiAuthError:
            api.login(username="glpi", password="glpi")
            return api.ticket.get_all_pages()
```

For long-running processes, prefer the OAuth2 clients — they refresh tokens
automatically.

---

## Connection errors

`GlpiConnectionError` wraps both connection failures and timeouts:

```python
from glpi_utils import GlpiAPI, GlpiConnectionError

try:
    api = GlpiAPI(url="https://glpi.example.com", timeout=10)
    api.login(username="glpi", password="glpi")
except GlpiConnectionError as e:
    print(f"Could not reach GLPI: {e}")
```
