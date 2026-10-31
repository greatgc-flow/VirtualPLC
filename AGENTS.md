# Working on VirtualPLC

This file is for agents developing this repository. For product usage, run
`virtual-plc guide` or `.venv/Scripts/python.exe -m virtual_plc guide`.

## Workflow

- Windows venv: `.venv/Scripts/python.exe`; POSIX: `.venv/bin/python`.
- Install locally: `python -m pip install -e . -r requirements-dev.txt`.
- Behavior changes require TDD: add tests, observe RED, implement GREEN, update docs.
- Run `.venv/Scripts/python.exe -m pytest -q` before reporting completion.
- Tests bind port 0 and use the real installed pymcprotocol client where applicable.
- Keep runtime code small and stdlib only; generate transport/profile cases.
- On Windows sandbox temp ACL failures, a process-local mkdir mode workaround is
  acceptable; remove temporary helpers afterward and report its use.

## Sources of truth

- `virtual_plc/__main__.py:build_parser` owns CLI flags, defaults and help.
- `virtual_plc/profiles.py` and command dispatch tables own profile/device/command data.
- `virtual_plc/ethernet.py` owns runnable defaults and reference-only
  FX5/RnCPU facts/unknowns; `guide ethernet --json` projects both.
- [VerySimpleGuide](https://github.com/greatgc-flow/VerySimpleGuide):
  prefer minimal CLI, explicit overrides and verifiable behavior.
- `virtual_plc/guide.py` owns compact English usage prose; tables are generated.
- README marked `guide:run` recipes must match guide run (test-enforced).
- README is the human entry point; docs/BEHAVIOR.md and docs/FAULTS.md explain semantics.
- Update docs/DESIGN.md when design decisions or open items change.
- `requirements-dev.txt` is the only exact oracle pin; test_oracle_pin.py checks it.
- The wheel hash is checked only for its recorded version. Keep the full suite and
  tests/test_client_coverage.py green after bumps; cover methods/constants/lookup names.

## Do not

- Do not commit or publish unless the user requests it.
- Do not add dependencies or duplicate option/device/command tables in guide prose.
- Do not label simulator policies as verified physical PLC behavior.
- Do not access direct Memory concurrently with wire requests; use clients.
- Do not expose the simulator to production networks or real equipment.
