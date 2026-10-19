# M4 P0 runtime contract expansion (2026-10-20)

**Branch:** `feat/m1-3e-binary-tdd`; **PR:** #1 Draft; **release:** HOLD.

## Verified local Python 3.11+ evidence
- Integration command (from repo root):
  `MC_SIM_ADAPTER_MODULE=virtual_plc.test_adapter python -m pytest tests/test_virtual_plc.py tests/test_m4_p0_case_ids_v2.py suite/tests/domain suite/tests/static suite/tests/live/test_wire_cases.py -q --server-cmd 'python -m virtual_plc --host {host} --port {port}' --junitxml=m4_v2_all.xml`
- 206 pytest testcases PASS, plus 5 subtests PASS. These overlap across levels.
- Exact CASE-ID JUnit gate: **118/199 P0 observed PASS (unattested)** = 45 prior live + 73 new, 81 NOT_RUN, 0 FAIL, 0 SKIP; 88 anonymous regression tests excluded, no duplicates.
- New P0 cases cover loopback TCP requests, frame split/coalescence, unsupported commands, bit/word boundaries, data preservation, wrong route, port collision, session quota, deterministic malformed frames, slowloris absolute frame deadline, and atomicity.
- New server: only configured Q-profile default route accepted, session cap 16 (was 24), absolute per-frame deadline; slow drip cannot indefinitely reset each recv timeout.
- Catalog (208 total / P0 199) remains byte-identical. No historic baseline or prior evidence overwritten.

## Gating
- **G0-C open:** real `pymcprotocol==0.3.0` wheel unavailable on local executor; source review is not a passing integration test.
- **G0-E open:** provisional 0xC059 simulated error; vendor model-specific official end codes not attested.
- **G1/G2:** 81 P0 unique CASE-IDs remain NOT_RUN. Newly observed 118 are not formal release attestations.
- **G3:** no Linux/Windows independently executed CI, production hardware validation, performance load certification, or safety approval.
- **G4 HOLD:** `main` unmerged, automated CI workflows disabled.

## Reproduction guards
Run only on `127.0.0.1` and never against physical PLCs. No credentials, plant topology, or private test data committed. Preserve full raw JUnit and gate JSON in local output, not as unreviewed blanket PASS in the repository.
