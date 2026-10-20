# M14 — Real-client and manufacturer evidence readiness

**Date**: 2026-10-20  
**Repository**: https://github.com/greatgc-flow/VirtualPLC (PUBLIC)  
**PR**: https://github.com/greatgc-flow/VirtualPLC/pull/1 (Draft, keep unmerged)  
**Release**: HOLD. **P0 observed** 183/199 (historical local, not independently attested); **16 external P0 OPEN**.

## Provenance and real external dependency

1. M13 distribution ZIP CRC PASS and per-file SHA256 256/256 PASS. PR branch HEAD when checked at start: `e49e439c3674de90b6ac126e3d4cc588ab708ec2`.
2. PyPI official `pymcprotocol-0.3.0-py3-none-any.whl` checksum SHA256 is `614217d43fbf8d9e409c1928993cbb4339d17828c1002c1766ce900aaee12dd6` (https://pypi.org/project/pymcprotocol/). Python client not installed in this execution environment. The mirror/default pip attempted to download but did not supply the pinned release; direct official binary download also failed. **Real-client G0-C remains NOT_RUN 6/6.** Do not represent a GitHub source code inspection or reconstructed packet as a released wheel execution.
3. Manufacturer SLMP Reference Manual: https://dl.mitsubishielectric.com/dl/fa/document/manual/plc/sh080956eng/sh080956engm.pdf (4.2, device access). The manual states that unsuccessful replies include the responding station information and command/subcommand. **It does not establish which CPU+Ethernet-module+firmware profile applies without the exact target.** Provisional `0xC059` remains unverified. Model-specific G0-E remains OPEN 6/6.
4. No Windows native run and no independent review; G3 OPEN 2/2, G4 OPEN 2/2.

## Added reusable tools (no mandatory third-party dependencies)

- `scripts/m14_windows_evidence.py`: actual SHA-pinned wheel preflight, fixed Git HEAD comparison, clean checkout requirement, Windows-only guard; delegates all six REAL client tests to the existing `scripts/m10_wheel_gate.py` and verifies its output's sha/log/JUnit consistency. Creates a **new** evidence directory and compressed ZIP; refuses overwrite and refuses output inside the public repo. It labels all results **LOCAL_UNATTESTED** and release HOLD. No cloud upload. Public contribution must exclude downloaded/extracted client distribution and local evidence.
- `RUN_M14_ON_WINDOWS.cmd`: optional explicit entrypoint to run the above on an authorized Windows test PC. Requires Python >=3.11, pytest, Git and a SHA-verified *actual* wheel. Connects only to ephemeral 127.0.0.1 server, no real PLC.
- `scripts/m14_vendor_profile.py`: strict declarative 6-case end-code reference intake requiring exact model, firmware, Ethernet module, official manufacturer manual and specific page numbers. It **does not certify vendor fidelity** and never promotes P0. Console and evidence file are byte-identical. A pseudo-PLC profile is not substituted for the missing real profile.
- New regression tests: `tests/test_m14_windows_evidence.py`, `tests/test_m14_vendor_profile.py`. They verify fail-closed handling of mismatched hashes, invalid OS/HEAD, forged pass reports, skipped/duplicate cases, code/source mismatch, spoofed vendor URLs and output overwrite. **They do not count as six real-client P0 completions.**

## How to obtain the missing real-client evidence on Windows

1. Use a **new isolated directory** with this branch checked out; use `git status --short` to verify clean checkout. Do not use an operating PC connected to any PLC network.
2. Download the actual wheel from https://pypi.org/project/pymcprotocol/0.3.0/#files and check SHA256 `614217d43fbf8d9e409c1928993cbb4339d17828c1002c1766ce900aaee12dd6` (Windows `certutil -hashfile <wheel> SHA256`). Do **not** obtain substitutes from unrelated sites.
3. Install Python 3.11+ and `pytest` in a clean virtual environment. Run:

```bat
RUN_M14_ON_WINDOWS.cmd "C:\isolated\pymcprotocol-0.3.0-py3-none-any.whl" "D:\VirtualPLC_Evidence_M14_NEW" "<40-character expected head of the checkout>"
```

4. Review generated `M14_EVIDENCE.json`, real `pymc_junit.xml`, `console.log`, output ZIP and the raw client request capture. Share privately; exclude `_pinned_package`, hostnames/usernames and any proprietary data before public release.
5. Even if all six succeed, independent review is mandatory before G0-C or G3 promotion. A single Windows test does **not** prove Linux/Windows independently or safety of vendor PLC models.

## Information still needed for G0-E

Supply the **PLC CPU model**, **Ethernet module or built-in Ethernet**, **firmware version**, **SLMP 3E/4E setting** and **manufacturer manual revision**. The default simulator is *Q-compatible 3E Binary/TCP for local test*, not a field-certified FX/iQ-R/Q device.

## Gate discipline and feedback loop

`Target model/version -> official vendor reference -> expected per-case bytes/endcodes -> failing independent test -> minimal implementation -> regression -> real client run -> external evidence hash -> independent review -> approve/reopen`.

When a gate fails, report exact CASE-ID and its source/runtime/version; never edit historical JUnit or quietly reclassify skipped tests as PASS. No automatic Actions, main merge, or real PLC access under this phase.
