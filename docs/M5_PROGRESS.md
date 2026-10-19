# M5 status — 2026-10-20

## Status / scope
- Work repository: public `greatgc-flow/VirtualPLC`; working Draft PR #1; no merge.
- Server: loopback-only 3E Binary/TCP, D-word / M-bit prototype; NOT a physical PLC substitute.
- Baseline: 208 catalog entries, 199 P0, immutable original catalogue SHA-256 `31415a1c0813aa28364883a24e006c5d8d4ff5ad8db171409ec4551a02f2fa7f`.
- M4: 118 P0 uniquely observed, not attested. M5: **35 new disjoint P0 case IDs** (27 runtime + 8 governance), measured by JUnit `case_id` properties. **153/199 P0 observed PASS, 46 NOT_RUN** on local Linux Python 3.13.5; **0 externally attested**. The M5 evidence archives the three constituent JUnit reports and a reproducible merged exact-ID report. Includes additional 88 anonymous tests, not counted as P0 CASE-ID.
- Test count: 161 base unit/static/domain + 45 independent TCP live + 35 new = **241 pytest PASS**; plus 5 `unittest` subtests. Tests from different groups measure overlapping behavior; never add as unique P0 count.

## M5 implementation
- `virtual_plc/scenario.py`: only in-process atomic D/M seed/reset/snapshot; no exposed control API; rejects invalid map values before all mutations.
- `virtual_plc/config.py`: stdlib TOML parser and strict schema; TCP host hardcoded to IPv4 loopback; optional port, D/M sizes, max body length.
- `virtual_plc/server.py`: configurable bounded `max_body` with 12..4096 checks, previously fixed M4 maximum 4096; no remote bind.
- `virtual_plc/__main__.py`: config parsed before socket is ever created, incompatible/invalid config rejects startup.
- `scripts/release_gate.py`: independent conservative local precheck never emits approval from self-reported test results; release requires separately reviewed evidence and human authority.
- `tests/test_m5_p0_case_ids.py`: CASE-ID qualified raw golden packets, concurrency, atomicity, reset, TOML edge cases, process spawn/killed state volatility, mutated frames, security guard.
- `tests/test_m5_governance.py`: catalog crosslinks, scoped support matrix, stdlib imports, injected scope errors, missing external evidence blocks promotion, unlicensed upstream blocks release.
- `scripts/run_m5.py`: reproducible multi-phase suite with mirrored stdout and local JUnit evidence for Windows/Linux.

## Pending gates / limitations
- **G0-C:** pinned `pymcprotocol==0.3.0` wheel has official PyPI SHA-256 `614217d43fbf8d9e409c1928993cbb4339d17828c1002c1766ce900aaee12dd6`; outbound internet is blocked in the execution environment and the wheel could not be downloaded. **No real-client PASS**. Existing optional tests stay opt-in.
- **G0-E:** vendor CPU/model/firmware-specific end-codes and station routing have not been confirmed; `0xC059` remains a simulator placeholder. DO NOT claim vendor fidelity.
- **G1/G2:** 46 P0 CASE-IDs remain NOT_RUN, including real-client, G3 telemetry, governance change handling and five manual gates.
- **G3:** Windows real execution, load/latency percentiles, RSS, OS stop handling not independently verified.
- **G4:** no release attestation. Keep main unmerged, draft PR, CI disabled; public repo has synthetic data only.

## Reproduce

`python -m pip install 'pytest>=8,<10'` then `python scripts/run_m5.py --output evidence/m5_run`.

To avoid launching TCP tests (quicker smoke): `python scripts/run_m5.py --fast`.

Opt-in to the client integration tests only with an independently fetched, SHA-256 verified official wheel and an isolated local test environment. Never connect tests to production PLCs.
