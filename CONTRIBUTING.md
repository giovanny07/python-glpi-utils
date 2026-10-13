# Contributing to python-glpi-utils

Thanks for your interest in contributing!

The full contributing guide lives in the documentation:
👉 **[https://giovanny07.github.io/python-glpi-utils/contributing/](https://giovanny07.github.io/python-glpi-utils/contributing/)**

---

## Quick reference

```bash
# Setup
git clone https://github.com/giovanny07/python-glpi-utils
cd python-glpi-utils
pip install -e ".[async,dev]"

# Test
pytest

# Lint and type check (CI runs both)
ruff check .
mypy glpi_utils
```

All tests must pass. CI runs on Python 3.9 to 3.13. For changes that touch HTTP behaviour, say which GLPI version you tested against.

---

## Sign your commits (DCO)

Every commit must carry a sign-off certifying the
[Developer Certificate of Origin 1.1](https://github.com/giovanny07/python-glpi-utils/blob/main/DCO):
that you wrote the change, or otherwise have the right to submit it under the
project's license. Add it with `-s`:

```bash
git commit -s -m "fix: ..."
# adds: Signed-off-by: Your Name <you@example.com>
```

The sign-off must use the same email as the commit author. A CI check (`DCO`)
blocks pull requests with unsigned commits. To sign off commits you already made:

```bash
git rebase --signoff origin/main
git push --force-with-lease
```

---

## License

Contributions are accepted under the [AGPL-3.0-or-later](https://github.com/giovanny07/python-glpi-utils/blob/main/LICENSE).
New source files start with an `SPDX-License-Identifier: AGPL-3.0-or-later` header.

---

## Reporting bugs

Open an issue at [github.com/giovanny07/python-glpi-utils/issues](https://github.com/giovanny07/python-glpi-utils/issues).

Include: Python version, library version, GLPI version, minimal reproduction, full traceback.
