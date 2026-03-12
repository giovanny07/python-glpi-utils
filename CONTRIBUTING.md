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

# Lint + format
ruff check glpi_utils/
ruff format glpi_utils/

# Type check
mypy glpi_utils/
```

All 262 tests must pass. CI runs on Python 3.9 – 3.13.

---

## Reporting bugs

Open an issue at [github.com/giovanny07/python-glpi-utils/issues](https://github.com/giovanny07/python-glpi-utils/issues).

Include: Python version, library version, GLPI version, minimal reproduction, full traceback.
