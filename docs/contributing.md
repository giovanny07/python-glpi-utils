# Contributing

Thanks for your interest in contributing to **python-glpi-utils**!

---

## Development setup

```bash
git clone https://github.com/giovanny07/python-glpi-utils
cd python-glpi-utils
pip install -e ".[async,dev]"
```

---

## Running the tests

```bash
pytest
```

Run with coverage:

```bash
pytest --cov=glpi_utils --cov-report=term-missing
```

Run for a specific Python version (requires `tox` or `pyenv`):

```bash
pytest --python=3.11
```

All tests must pass before submitting a PR. The CI runs the full suite
on Python 3.9 to 3.13 automatically.

---

## Code style

The project lints with [Ruff](https://docs.astral.sh/ruff/) (rules in `ruff.toml`) and
type-checks with [mypy](https://mypy.readthedocs.io/) in strict mode (settings in
`setup.cfg`). CI runs both on every pull request:

```bash
ruff check .
mypy glpi_utils
```

Annotations keep `typing.Optional` rather than `X | None`, because the library
supports Python 3.9.

Integration tests against a real GLPI live in `tests/integration` and are skipped
unless `GLPI_IT_URL` is set. `.github/scripts/glpi_it_setup.sh` prepares a
`glpi/glpi` container and prints the variables they need; CI runs them on
GLPI 10.0, 11.0 and 12.0.

---

## Submitting a pull request

1. Fork the repo and create a branch: `git checkout -b feat/my-feature`
2. Make your changes
3. Add or update tests — coverage should not decrease
4. Run `pytest`, `ruff check`, and `mypy` locally
5. Commit with a clear message (see below)
6. Push and open a PR against `main`

### Commit message format

```
type: short description

Optional longer explanation.
```

Types: `feat`, `fix`, `docs`, `chore`, `test`, `refactor`

Examples:

```
feat: add bulk_create helper to ItemProxy
fix: handle empty Content-Range header gracefully
docs: add OAuth2 guide
chore: bump aiohttp to 3.10
```

---

## Reporting bugs

Open an issue at
[github.com/giovanny07/python-glpi-utils/issues](https://github.com/giovanny07/python-glpi-utils/issues)
and include:

- Python version (`python --version`)
- Library version (`pip show glpi-utils`)
- GLPI version
- Minimal code to reproduce the issue
- Full traceback

---

## Suggesting features

Open an issue with the label `enhancement` and describe:

- The use case
- What the API could look like
- Whether you'd be willing to implement it

---

## Project structure

```
python-glpi-utils/
├── glpi_utils/
│   ├── __init__.py      # Public exports
│   ├── api.py           # GlpiAPI (sync, legacy)
│   ├── aio.py           # AsyncGlpiAPI (async, legacy)
│   ├── oauth.py         # GlpiOAuthClient / AsyncGlpiOAuthClient
│   ├── _resource.py     # ItemProxy / AsyncItemProxy
│   ├── exceptions.py    # Exception hierarchy
│   ├── logger.py        # SensitiveFilter, EmptyHandler
│   └── version.py       # GLPIVersion
├── tests/               # pytest test suite (262 tests)
├── docs/                # MkDocs documentation
├── examples/            # Usage examples
├── .github/workflows/   # CI (tests) + CD (release + docs)
├── setup.cfg            # Package metadata and config
└── mkdocs.yml           # Documentation config
```

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

By contributing you agree that your contributions will be licensed under the
[GNU Affero General Public License v3.0 or later](https://github.com/giovanny07/python-glpi-utils/blob/main/LICENSE)
(AGPL-3.0-or-later). New source files start with:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2025-2026 Giovanny Rodriguez, Imagunet
```
