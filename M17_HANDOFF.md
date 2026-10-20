# M17 continuation — VirtualPLC

1. Verify GitHub `greatgc-flow/VirtualPLC` main and Draft PR #1 HEAD, Actions; preserve Draft and DO NOT merge/re-enable CI without explicit instruction.
2. First validate the M16 ZIP CRC + top-level `FILE_SHA256_MANIFEST.json`; only then use `project/docs/M16_PROGRESS.md`, `project/M16_GATES.json`, `project/scripts/m16_provenance_gate.py` and `project/scripts/m16_windows_one_shot.py` as the working handoff.
3. Prior P0 baseline is 183/199 observed locally; **16 external remains HOLD**. Official SHA-verified wheel (`614217...2dd6`) was NOT available in Linux build environment. GitHub upstream source `0.3.0` static review is not wheel execution.
4. M16 local verified groups: 203 tests+5 subtests, 191 evidence tests, 45 live loopback TCP tests. Synthetic M14 ZIP fixture passes integrity but MUST NEVER be used as Windows attestation.
5. To close G0-C and G3, have isolated Windows operator run `RUN_M16_WINDOWS_ONE_SHOT.cmd "AUTO" "D:\\VPLC_M16_NEW" "<PR_SHA>"` (or offline wheel). Privately upload `M14_CLIENT_RUN.zip`; verify ZIP with `python -m scripts.m16_provenance_gate --zip ... --result ...`; independent reviewer verifies origin, OS, logs, source HEAD.
6. G0-E additionally needs a concrete Mitsubishi CPU/model, Ethernet module, firmware and manual revision/page; no assumed generic end code.
7. G4 requires independent acceptance, license decision, failback/runbook and proof of no production PLC traffic. No self-certification. Keep all stored evidence and changed source in one new ZIP + updated GitHub Draft PR.
