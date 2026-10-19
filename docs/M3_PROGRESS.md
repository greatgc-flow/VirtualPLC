# M3 — Full test-suite integration and verification (2026-10-19)

## Repository state
- Repository: `greatgc-flow/VirtualPLC` (PUBLIC)
- Branch: `feat/m1-3e-binary-tdd`; Draft PR #1, **not merged**
- Release decision: **HOLD**; real PLC substitution is not authorized.

## Provenance completion
- Imported the complete source baseline: 74 files (original suite, full v1.1 design, test executors, static validator and pytest config) from `VirtualPLC_M1_TDD_GitHub_Handoff_20261019.zip`.
- The imported 208-case catalogue contains 199 P0 cases and 9 deferred cases; 69 legacy test IDs remain mapped.
- Per-file Git Blob SHA-1 verification against the original archive: **74/74 match**, including the CSV CRLF correction.
- Use `python scripts/verify_repo_baseline.py` to continuously verify file integrity and case counts.
- Hash manifests are verifiable provenance, not proof of a vendor-certified protocol.

## Validation boundaries
- Local offline archive tests: 20 static and 19 domain tests passed. The wire suite had previously recorded 45 passing cases in the M1/M2 package; M3 reconfirmation is partial and MUST NOT silently replace recorded results.
- Real `pymcprotocol==0.3.0` compatibility remains **NOT_RUN** because the external wheel is unavailable in this execution environment (no authenticated new result).
- Windows CI and Linux GitHub CI have not passed; the workflow stays quarantined at `docs/workflow-templates/manual-validation.yml`.
- Existing observed 45 P0 CASE-IDs do not prove 199 P0 completed; **at least 154 P0 evidence rows remain unauthenticated**.

## Verification commands
```bash
python scripts/verify_repo_baseline.py
python scripts/validate_suite.py
python -m unittest discover -s suite/tests/static -p 'test_*.py' -v
MC_SIM_ADAPTER_MODULE=virtual_plc.test_adapter python -m pytest suite/tests/domain -q
python -m pytest suite/tests/live/test_wire_cases.py -q --server-cmd 'python -m virtual_plc --host {host} --port {port}'
python -m pytest tests/test_virtual_plc.py -q
# Only on a trusted dev host, after installing the SHA-256 pinned wheel:
VIRTUALPLC_RUN_PYMC=1 python -m pytest tests/compat -q
```

## Feedback loop and fail-closed gates
1. Specification or code change -> case and requirement mapping impact review.
2. Failing test and captured evidence -> minimal code fix -> focused regression -> all relevant regressions.
3. Successful test run -> JUnit exact CASE-ID reconciliation -> provenance manifest update when tracked source changes.
4. Any missing/failed/untested P0 -> HOLD, never silently relabel.
5. Model-specific end codes, response payload semantics, external real-client wire captures, cross-platform verification and scenario gates remain OPEN.

Do not publicly publish private PLC addresses, customers, production data, credentials or internal traces.
