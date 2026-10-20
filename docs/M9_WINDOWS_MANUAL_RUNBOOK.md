# M9 Windows validation — pending operator run

**Not executed as part of the M9 Linux package.** All tests and app bind to `127.0.0.1`, with no production PLC access. Do not enable GitHub Actions without approval.

1. Use Windows PowerShell 5.x or PS2-compatible `cmd.exe`; install Python >=3.11 and local pytest. Do not place secrets or manufacturing topology in a public report.
2. On a clean checkout of the same Git SHA, in PowerShell run `$env:MC_SIM_ADAPTER_MODULE='virtual_plc.test_adapter'` and `py -3.11 -m pytest tests/test_virtual_plc.py tests/test_m9_platform_perf.py -q --junitxml=artifacts/windows.xml`.
3. Verify no bind outside loopback and record Python/OS, source SHA and exact wheel version (report `NOT_INSTALLED` if absent).
4. Upload JUnit and console logs to a controlled evidence location after reviewing for secrets. Cross-platform gate `CASE-0044`, Windows `CASE-0128` and G3 remain **NOT_RUN** until independent evidence is returned.
5. For genuine `pymcprotocol` 0.3.0 tests, first obtain the original PyPI wheel and verify SHA256 `614217d43fbf8d9e409c1928993cbb4339d17828c1002c1766ce900aaee12dd6`. Test only on 127.0.0.1. Never replace a missing wheel with an unofficial source copy while claiming the wheel version is attested.

Note: The M9 exact-181 CASE-ID merger is intentionally a **Linux-local snapshot**. Generate a distinct cross-platform release report, not a fake Linux result on Windows.
