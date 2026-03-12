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

All 262 tests must pass before submitting a PR. The CI runs the full suite
on Python 3.9 – 3.13 automatically.

---

## Code style

The project uses [Ruff](https://docs.astral.sh/ruff/) for linting and formatting:

```bash
ruff check glpi_utils/
ruff format glpi_utils/
```

Type hints are checked with [mypy](https://mypy.readthedocs.io/):

```bash
mypy glpi_utils/
```

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

## License

By contributing you agree that your contributions will be licensed under the
[MIT License](https://github.com/giovanny07/python-glpi-utils/blob/main/LICENSE).
