# VirtualPLC — Mitsubishi MC/SLMP virtual PLC

**M1: experimental, loopback-only 3E Binary TCP PLC simulator.**

This repository is **public**. No private production logs, site addresses, tokens or confidential PLC tag maps belong here.

## Scope
- Supported in M1: 3E Binary over TCP, D word and M bit batch read/write (0401/1401), atomic volatile memory, multiple TCP clients, TCP split/coalesced framing, invalid-message rejection.
- Excluded/unverified: 4E/ASCII, UDP, random device operations, authentic PLC scan/ladder/runtime behavior, field device compatibility, vendor error-code fidelity, remote deployment.
- Invalid decoded operations currently respond with provisional simulator code 0xC059; **not a validated Mitsubishi error code**.

## Quick start (Python >=3.10)

Install test dependency with: `python -m pip install 'pytest>=8,<10'`

Start server: `python -m virtual_plc --host 127.0.0.1 --port 5000`

Run checked-in regression tests: `python -m pytest tests -q`

In the full offline M1/TDD package, the legacy 208-case catalogue is separate from these concise GitHub smoke tests; see `docs/M1_STATUS.md` for coverage boundaries.

## Risk controls
- Server refuses all host addresses except 127.0.0.1.
- There is **no** path that connects to a real PLC.
- No credentials or production access.
- GitHub Actions is manual-only to prevent unsolicited runs.

## Gates and evidence
A local development run passed 19 domain tests, 45 TCP/protocol cases, and 48 supplementary regression tests (their assertions overlap). This is **not** a claim that the 199 P0 test cases or vendor-client interoperability have passed. Project release remains **HOLD**.

See `docs/M1_STATUS.md` for exact scope, reproducible steps and next work.
