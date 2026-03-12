# Logging

The library is **silent by default** — no output unless you configure a handler.

---

## Enable debug logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)

from glpi_utils import GlpiAPI
api = GlpiAPI(url="https://glpi.example.com")
api.login(username="glpi", password="glpi")
```

This shows every HTTP request and response status on `stderr`.

---

## SensitiveFilter

Passwords, tokens and session IDs are **masked automatically** by
`SensitiveFilter`, which is attached to the library's loggers by default.

Example — what you see in the logs:

```
DEBUG glpi_utils.api GET https://glpi.example.com/apirest.php/initSession
DEBUG glpi_utils.api Response 200
DEBUG glpi_utils.api Session established.
```

The `Authorization` header value and session token never appear in plain text.

---

## Add your own handler with masking

```python
import logging
from glpi_utils import SensitiveFilter

handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s — %(message)s"))
handler.addFilter(SensitiveFilter())

logging.getLogger("glpi_utils").addHandler(handler)
logging.getLogger("glpi_utils").setLevel(logging.DEBUG)
```

---

## Log to a file

```python
import logging
from glpi_utils import SensitiveFilter

handler = logging.FileHandler("glpi.log")
handler.addFilter(SensitiveFilter())

logging.getLogger("glpi_utils").addHandler(handler)
logging.getLogger("glpi_utils").setLevel(logging.DEBUG)
```

---

## Use mask_secret in your own code

```python
from glpi_utils.logger import mask_secret, hide_sensitive

print(mask_secret("q56hqkniwot8wntb3z1qarka5atf365taaa2uyjrn"))
# q56h********jrna

data = {"user": "admin", "password": "supersecret", "id": 42}
print(hide_sensitive(data))
# {'user': 'admin', 'password': '********', 'id': 42}
```
