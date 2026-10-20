# M18 handoff — VirtualPLC

1. Verify latest main/PR HEAD/Actions for `greatgc-flow/VirtualPLC`, preserving Draft PR #1 and no automatic CI; do not merge without explicit request.
2. Verify M17 ZIP CRC and the **top-level full-file SHA-256 manifest**, including this handoff, before using artifacts.
3. M17 local tests: 466 PASS (core 122+81, evidence 218, TCP 45), 5 extra subtests; M17 preflight 26 are included in 218. Previous 183/199 P0 historic local observed, 16 external remain HOLD. All M17 Windows cases are synthetic: zero actual client/Windows attestations.
4. On isolated Windows PC use `RUN_M17_WINDOWS_ONE_SHOT.cmd "AUTO" "D:\\VPLC_M18_NEW" "<LATEST_PR_HEAD>"`; preflight verifies clean Git checkout/pytest/interpreter/wheel path. `AUTO` obtains wheel via PyPI only during explicit execution; full SHA-256 verification is mandatory. Offline wheel path is supported.
5. Keep Windows evidence ZIP private. Verify with `python -m scripts.m16_provenance_gate ...`, then have a human independently attest machine, actual wheel/provenance, logs, HEAD and no plant traffic. Do not count synthetic reports.
6. G0-E requires actual Mitsubishi model/CPU, module, firmware and cited official manual. G4 needs independent risk/licensing/failback acceptance; never self-approve.
7. Deliver changes only on Draft PR, with source/test/evidence and new reproducible handoff ZIP. Release stays HOLD unless ALL material gates independently close.
