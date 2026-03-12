# Authentication

## Legacy API (`/apirest.php`)

Three methods are supported — sync and async use the same interface.

### Username + password

```python
api.login(username="glpi", password="glpi")
```

Uses HTTP Basic Auth against `initSession`.

### Personal API token

```python
api.login(user_token="q56hqkniwot8wntb3z1qarka5atf365taaa2uyjrn")
```

The personal token is found in GLPI under *Preferences → Remote access key*.

### Environment variables

```bash
export GLPI_URL=https://glpi.example.com
export GLPI_APP_TOKEN=your_app_token       # optional
export GLPI_USER=glpi
export GLPI_PASSWORD=glpi
# or
export GLPI_USER_TOKEN=your_personal_token
```

```python
api = GlpiAPI()   # GLPI_URL + GLPI_APP_TOKEN
api.login()       # GLPI_USER/GLPI_PASSWORD or GLPI_USER_TOKEN
```

### Logout

```python
api.logout()
```

Or use a context manager — it calls `logout()` automatically:

```python
with GlpiAPI(url="https://glpi.example.com") as api:
    api.login(username="glpi", password="glpi")
    # ... work ...
# logout() called here automatically
```

---

## High-level API (`/api.php`) — OAuth2

GLPI 11 introduced a modern OAuth2-based API. Use `GlpiOAuthClient` or `AsyncGlpiOAuthClient`.

### Client credentials grant

For service accounts and automation scripts:

```python
from glpi_utils.oauth import GlpiOAuthClient

api = GlpiOAuthClient(
    url="https://glpi.example.com",
    client_id="my-app",
    client_secret="my-secret",
)
api.authenticate()
```

### Password grant

For user-delegated access:

```python
api = GlpiOAuthClient(
    url="https://glpi.example.com",
    client_id="my-app",
    client_secret="my-secret",
)
api.authenticate(username="glpi", password="glpi")
```

### Automatic token refresh

The OAuth2 clients refresh the Bearer token automatically when it expires — no manual intervention needed:

```python
with GlpiOAuthClient(url="...", client_id="x", client_secret="y") as api:
    api.authenticate()
    # Token expires after 1h by default.
    # If your script runs longer, the client re-authenticates transparently.
    for page in api.ticket.iter_pages():
        process(page)
```

### Environment variables

```bash
export GLPI_URL=https://glpi.example.com
export GLPI_OAUTH_CLIENT_ID=my-app
export GLPI_OAUTH_CLIENT_SECRET=my-secret
export GLPI_OAUTH_USERNAME=glpi        # for password grant
export GLPI_OAUTH_PASSWORD=glpi        # for password grant
```

```python
api = GlpiOAuthClient()  # reads all from env
api.authenticate()
```

---

## Which client should I use?

| Scenario | Recommended client |
|----------|--------------------|
| Scripts, automation, most use cases | `GlpiAPI` |
| Async frameworks (FastAPI, etc.) | `AsyncGlpiAPI` |
| GLPI 11 OAuth2 app registered | `GlpiOAuthClient` |
| Async + OAuth2 | `AsyncGlpiOAuthClient` |
