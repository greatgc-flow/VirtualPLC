# VirtualPLC

Virtual Mitsubishi MC protocol PLC for local testing. Not for industrial use.

**Status:** v2 M0 scaffold on `v2/m0`; runtime modules are docstring-only stubs.
The local environment exists, but installing pytest and the pinned client, and
running pytest, are blocked by shell network restrictions in this workspace.
M1 will add the Q-profile 3E binary server. See [DESIGN](docs/DESIGN.md) and
[migration notes](docs/MIGRATION.md).

With Python 3.10 or newer and PyPI access, run from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pip download --no-deps --only-binary=:all: --require-hashes -r tests/oracle_pin.txt -d .venv/oracle
.\.venv\Scripts\python.exe -m pip install --no-index --find-links .venv/oracle --require-hashes -r tests/oracle_pin.txt
.\.venv\Scripts\python.exe -m pytest -q
```

On POSIX, use `.venv/bin/python` for the commands after environment creation.
Runtime dependencies are stdlib only; pytest is the development extra, and
`pymcprotocol==0.3.0` is a separate test oracle. The pin test checks the installed
version and, when the downloaded wheel is retained, its SHA256 and installed
package source. Missing oracle installations fail the test.

`tests/tables.py` contains immutable profiles, device codes/bases, commands,
and explicit reasons for excluding combinations from the M1 positive matrix.
The migrated JSONL holds future scenario inputs; M0 does not run a PLC server.
