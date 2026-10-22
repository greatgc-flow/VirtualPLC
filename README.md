## M27 CURRENT — offline descriptive evidence triage (2026-10-22)

`RUN_M27_LOCAL_COMPARE.cmd` verifies M26 multi-run output hashes, JUnit, source/workload comparability, and optional user-owned latency/RSS thresholds without modifying source evidence. See `docs/M27_PROGRESS.md` and `M27_GATES.json`. **Release HOLD; original M26 results are historical until independently replayed.** PR #1 remains Draft; no CI activation or merge.

## M26 CURRENT (2026-10-21)

Latest milestones are documented in `docs/M26_PROGRESS.md`, `M26_GATES.json`, and `M27_HANDOFF.md`. Use `RUN_M26_LOCAL_REPEATS.cmd` on a clean local checkout to perform opt-in bounded repetitions (3..30 runs), each keeping exact console output, JUnit, report and hashes. **Local P0 observed 183/199; 16 external P0 HOLD. Release HOLD, no automated CI or merge.** Earlier milestone figures below are retained only as historical records.

# VirtualPLC — MC/SLMP simulator (experimental)

**M9 on Draft PR #1 — local-only, not a real Mitsubishi PLC.** Public repository; no production data or PLC IPs.

Supported test slice: 3E Binary/TCP, D word and M bit batch 0401/1401, 127.0.0.1 only. Atomic volatile memory, bounded frame and session handling, optional TOML config and explicit route allowlist, in-process seed/reset/snapshot for isolated tests. 4E/ASCII, vendor error-code fidelity, scan/ladder, real hardware and remote bind are **NOT supported/verified**.

## Run

Requires **Python >=3.11** (stdlib `tomllib`).

```sh
python -m pip install 'pytest>=8,<10'
python -m virtual_plc --host 127.0.0.1 --port 5000
python -m pytest tests/test_m8_route.py tests/test_m8_evidence.py tests/test_m8_merge.py -q
python scripts/merge_m8_evidence.py --junit-dir evidence/m8_run --out evidence/NEW_M8_RUN
```

On Windows, use `py -3.11` or `python` consistently. The script mirrors the console output into evidence logs alongside JUnit. Test traffic is always loopback-only. Manual external-client tests are opt-in and require the SHA-pinned official wheel; see `docs/M5_PROGRESS.md`.

## Evidence and release

Latest **local Linux** M8 run: 289 pytest cases PASS (286 phase evidence plus 3 validator-mutation tests), 5 unittest subtests PASS; **178/199 unique P0 IDs observed PASS**, **21 NOT_RUN**, **0 attested**. All release gates remain **HOLD**; counts are not a proof of full compatibility. Public GitHub's active CI workflow is disabled; no automatic Actions and no main merge.

References: `docs/M8_PROGRESS.md`, `M8_REMAINING_P0.json`, `docs/SUPPORT_MATRIX.json`, `baseline_v1.1`, `suite/catalog/test_cases.jsonl`.

## M9 audit and verification (2026-10-20)

M8 original manifest **FAIL: 7/125 SHA-256 entries differ**. Seven files match remote Git blob hashes. See `docs/M9_PROGRESS.md` and `scripts/m9_audit_m8_zip.py`; never silently override the original manifest.

M9 local Linux baseline: **181/199 unique P0 CASE-IDs observed PASS**, **18 NOT_RUN**, **0 independently attested**; separate 100/1000-word benchmark and environment fingerprint available. Manufacturer error-code profile, actual pinned PyPI client wheel and Windows validation still missing. **Release remains HOLD.**

Run `python -m pytest tests/test_m9_platform_perf.py tests/test_m9_archive_audit.py tests/test_m9_gate.py -q`, then use `python -m scripts.m9_benchmark --out evidence/local/new_benchmark.json` in a new output path. See `docs/M9_WINDOWS_MANUAL_RUNBOOK.md` for Windows instructions.
