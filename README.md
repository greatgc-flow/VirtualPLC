# VirtualPLC — MC/SLMP simulator (experimental)

**M5 on Draft PR #1 — local-only, not a real Mitsubishi PLC.** Public repository; no production data or PLC IPs.

Supported test slice: 3E Binary/TCP, D word and M bit batch 0401/1401, 127.0.0.1 only. Atomic volatile memory, bounded frame and session handling, optional TOML config, in-process seed/reset/snapshot for isolated tests. 4E/ASCII, vendor error-code fidelity, scan/ladder, real hardware and remote bind are **NOT supported/verified**.

## Run

Requires **Python >=3.11** (stdlib `tomllib`).

```sh
python -m pip install 'pytest>=8,<10'
python -m virtual_plc --host 127.0.0.1 --port 5000
python scripts/run_m5.py --output evidence/m5_run
python scripts/run_m5.py --fast --output evidence/m5_fast
```

On Windows, use `py -3.11` or `python` consistently. The script mirrors the console output into evidence logs alongside JUnit. Test traffic is always loopback-only. Manual external-client tests are opt-in and require the SHA-pinned official wheel; see `docs/M5_PROGRESS.md`.

## Evidence and release

Latest **local Linux** run: 241 pytest cases PASS, 5 unittest subtests PASS; **153/199 unique P0 IDs observed PASS** via JUnit exact properties, **46 NOT_RUN**, **0 attested**. All release gates remain **HOLD**; counts are not a proof of full compatibility. Public GitHub's active CI workflow is disabled; no automatic Actions and no main merge.

References: `docs/M5_PROGRESS.md`, `docs/SUPPORT_MATRIX.json`, `baseline_v1.1`, `suite/catalog/test_cases.jsonl`.
