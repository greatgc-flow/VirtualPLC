# VirtualPLC — M1–M26 conversation-wide handoff (2026-10-22)

## 0. Scope, source of truth, and confidentiality
- This document preserves the substantive VirtualPLC project decisions, milestones, implementation constraints, evidence provenance, release gates, and continuation instructions from the long-running ChatGPT conversation. It is a curated project handoff, not a verbatim export of private chat history, hidden reasoning, account memory, or unrelated personal projects.
- The canonical public source repository is https://github.com/greatgc-flow/VirtualPLC ; the development target is the existing Draft PR #1 on branch feat/m1-3e-binary-tdd. The latest branch must ALWAYS be rechecked before edits. The verified pre-handoff parent HEAD was 289bb903b24ff3b4e531b161a151164f80e1a3f7 (M26); its parent was af73ff24f59e1d28f14a8f5a799e8ec303285612 (M25).
- The default main branch was 07189724a8b2473e54f5e7d74317d7f5d402b6e3 at the time of handoff. Keep PR Draft and DO NOT merge main, turn on automatic Actions, or modify high-risk repository policy without explicit user instruction.
- NEVER commit production network identifiers, real PLC traffic, machine data, Windows operator evidence (including hostnames, accounts or filesystem paths), private credentials, or materials from other projects to this PUBLIC repository. Do not attempt to publish the actual private transcript/memory.

## 1. User's durable engineering preferences
- Very Simple architecture, recursive MECE by component and phase, TDD, independent single-purpose functions, low coupling and extensibility.
- Option rather than hard-code ambiguous choices; all defaults safe; explicitly handle None/null and empty arrays; avoid forceful or irreversible operation.
- Every command-line test or script must preserve displayed console text exactly in a named evidence file, with source/JUnit/log hashes and clear exit status. Failed, timed-out, skipped and unexecuted tests are never PASS.
- Windows enterprise environment is important. If adding Java use JDK 1.8; C# Visual Studio 2015; PowerShell should work with 2.0 and Windows PowerShell 5.x. Current VirtualPLC project itself is Python >=3.11 because standard-library TOML support requires tomllib.
- User prefers carrying independent engineering work forward rather than stopping on blocked external approvals; keep owner, unblock trigger, acceptance and current status in backlog. Avoid unnecessary user questions.

## 2. Product definition and safety boundary
- Virtual PLC for CIM/EAS/EAP/MES interface integration testing; limited Mitsubishi MC/SLMP 3E Binary over TCP, using LOCAL LOOPBACK 127.0.0.1 only, D word and M bit devices, batch read/write commands 0x0401/0x1401.
- Atomic volatile D/M memory; batch read/write, device bounds, bit nibble packing, bounded frame bodies and concurrent sessions, configurable TOML, explicit allowed routing paths, deterministic in-process scenario seed/reset/snapshot.
- Bounded deterministic optional fault injection (delay and disconnect), recovery checks, workload generation, RSS and latency observation, offline evidence validation. Fault injection is disabled by default and cannot reach production hardware.
- No production PLC connection, no arbitrary remote binding, no 4E or ASCII or real scan/ladder support; no manufacturer-certified CPU-specific error-code fidelity. Simulator placeholder 0xC059 is NOT an attested vendor end code.
- Official pymcprotocol v0.3.0 wheel SHA-256 expected: 614217d43fbf8d9e409c1928993cbb4339d17828c1002c1766ce900aaee12dd6. Upstream GitHub source tag 0.3.0 was reviewed, but source inspection does NOT substitute actual SHA-verified wheel execution.

## 3. Chronological milestone / evidence ledger
- M1–M3: base 3E Binary TCP simulator, code structure, 208-case test catalog and requirements model; 199 P0 cases, plus lower priorities. Original catalog SHA-256 reported 31415a1c0813aa28364883a24e006c5d8d4ff5ad8db171409ec4551a02f2fa7f; ALWAYS verify against current file rather than assume.
- M4: CASE-ID test expansion; M5: baseline 153/199 observed P0; M6: 173/199; M7: 176/199; M8: 178/199; M9: 181/199; M10: 183/199. The counts are historical local observations, not hardware/vendor certification.
- M11–M19: model-based D/M testing, independent evidence checks, wheel and packet provenance verification, native-Windows one-shot collection preparation, Windows ZIP path namespace defenses, and conservative fail-closed admission. P0 remained 183/199; the hardware/client/Windows tests were NOT done.
- M20: external 16 P0 moved into actionable backlog; bounded, opt-in deterministic fault injection. M21: one-command local smoke, exact stdout mirroring, JUnit manifests and failure-safe evidence. M22: bounded concurrency load with p50/p95/p99 and server-only RSS; 7,800 local loopback operations observed. M23: drop/reconnect and single-process time-series; M24: deterministic scenario matrix and conservative comparison, plus removal of 62 duplicate legacy CASE-ID annotations (tests retained). M25: independent review of sample integrity and 3-run summary, no confidence claims. M26: bounded 3..30 run orchestration, per-run logs and manifests, no evidence overwrite, preserved partial output on error.
- Archive ZIPs M1–M25 were delivered in the conversation and are NOT implicitly GitHub files. Do not fabricate a download URL or assume a new local working session has those bytes. For the next chat, the LIVE GitHub latest branch and THIS handoff are the first source of truth, and a ZIP is useful only after validating member hashes.

## 4. M26 VERIFIED SNAPSHOT, read with evidence limits
- The M26 GitHub commit message is 'M26: bounded repeat orchestration, fail-closed evidence, 1015-test audit'. Files added: scripts/m26_multi_run.py, tests/test_m26_multi_run.py, RUN_M26_LOCAL_REPEATS.cmd, docs/M26_PROGRESS.md, M26_GATES.json and M27_HANDOFF.md; README amended.
- The committed M26_GATES.json reports 1,015 unique locally observed pytest PASS, 5 separate unittest subtests PASS, 45/45 loopback TCP tests PASS, 11 original JUnit file groups, zero duplicate CASE-ID, 183/199 unique P0 observed, 16 external P0 blocked, no independent release approval. These are the recorded results; if raw JUnit originals are unavailable, DO NOT reconstruct their provenance by assertion.
- Local 3-run M26 observations were p95 613, 521, 521 microseconds (not independently verified; never an SLA). M26 evidence labels must remain OBSERVED_NOT_CERTIFIED, final release HOLD.
- Runner bounds in docs/M26_PROGRESS.md: 3..30 runs, 1..8 clients, 0.2..60 sec duration, 1..5000 cycles, fault delay 1..500ms, timeout 5..240s and at least duration+4s. Defaults: 3 runs, 2 clients, duration 0.5 s, up to 30 cycles, delay 20 ms, timeout 30 s. New external output directory required for each invocation, no symlinks or existing output, sources stay fixed, no auto-retry of uncertain writes.
- CLI: python -m scripts.m26_multi_run --out NEW_OUTPUT --runs 3 --clients 2 --duration 0.5 ; Windows wrapper: RUN_M26_LOCAL_REPEATS.cmd NEW_OUTPUT 3 2 0.5 30. Per-run JUnit, report, stdout, SHA-256 manifest and failure status stay distinct.

## 5. Open external gates: exact 16 case IDs
- G0-C real-client 6 cases: CASE-0027, CASE-0028, CASE-0029, CASE-0109, CASE-0110, CASE-0111. Need a real sha-verified official pymcprotocol 0.3.0 wheel, native clean Windows loopback execution, original packets/JUnit/logs/source HEAD and independent origin review. Owner roles: Windows operator and reviewer.
- G0-E vendor 6 cases: CASE-0018, CASE-0019, CASE-0020, CASE-0064, CASE-0088, CASE-0090. Need exact PLC CPU and Ethernet module, firmware, dated/revisioned manufacturer documentation, golden error frames. Never invent generic vendor mappings. Owner: PLC engineer/manual reviewer.
- G3 native Windows 2 cases: CASE-0044 and CASE-0128. Need Windows >=Python3.11 startup/shutdown/sockets and environment provenance. Owner: isolated Windows validation operator.
- G4 independent release 2 cases: CASE-0055 and CASE-0147. Independent signoff, licensing, source-evidence trace, failback/runbook and no real PLC traffic. Owner: independent reviewer/license owner.
- Authoritative backlog: backlog/M20_BACKLOG.json (BL-EXT-CLIENT, BL-EXT-VENDOR, BL-EXT-WINDOWS, BL-EXT-REVIEW). Keep BLOCKED until original evidence exists. BL-INT backlog statuses are historically from M20; do not assume its older internal next-step fields supersede newer milestones.

## 6. Evidence/quality policy; how to avoid false PASS
- Distinguish (A) direct completed test in current environment, (B) previously recorded local observation, (C) externally independently attested, (D) unexecuted SKIP/HOLD. Do not sum these as if equivalent.
- Earlier failures discovered and corrected: M8 manifest 7 mismatched hashes though actual files matched GitHub blobs; M9 extra internal manifest; M24 62 duplicate CASE-ID owner annotations; occasional combined network tests timed out and must be rerun in independent groups. Preserve original failed evidence and corrections, not rewrite history.
- Validate ZIP CRC AND all listed member SHA-256 AND completeness including unregistered members. JUnit parser must check failure/error/skip, unique test node and case_id, exact catalog membership. Exclude timed-out/partial runs from PASS.
- For performance use descriptive p50/p95/p99, server-only RSS (not client+server), source/environment/config fingerprint and repeatability. A handful of short local runs cannot establish memory-leak absence or SLA approval. Only apply opt-in user-defined bounds; unmatched environment is not comparable by default.
- All stdout mirrored byte-for-byte to evidence file. Hashes are tamper-evidence and do not independently prove operator identity, execution origin, Windows authenticity or signing.

## 7. Required next-chat reading sequence
1. Confirm latest main, Draft PR #1 HEAD, branch, open PRs and Actions/workflow triggers via connected GitHub, NEVER trust this stored SHA over newer changes.
2. Read docs/handoff/START_NEW_CHAT_M27_20261022.md (new chat prompt).
3. Read THIS document: docs/handoff/2026-10-22_M26_COMPLETE_CHAT_HANDOFF.md.
4. Read README.md, M27_HANDOFF.md, docs/M26_PROGRESS.md, M26_GATES.json and backlog/M20_BACKLOG.json.
5. Inspect scripts/m26_multi_run.py, tests/test_m26_multi_run.py, RUN_M26_LOCAL_REPEATS.cmd and M25/m24 comparison tools before changing implementation.
6. Read suite/catalog/test_cases.jsonl, governance/test owner mappings, current gate_report scripts as needed to ensure exact P0 counting.
7. If original M26 ZIP or JUnit originals are available, validate their SHA/CRC before interpreting them. Otherwise state they were not independently inspected in the new session.

## 8. M27 nonblocking priorities (proposal, not a completed milestone)
- Create deterministic, MECE cross-run anomaly/diff report for 3..30 bounded M26 runs. Separate environment comparability, success/error/timeout, latency distribution, RSS trend, abnormal connection/recovery cases, evidence provenance.
- Keep zero arbitrary SLA thresholds and zero automatic release approval; anomaly thresholds optional with documented assumptions. Feature flags and modular unit functions, null/empty input, replay with fixed seed, no production traffic.
- Provide unit/negative tests, full regression grouped to avoid timeout, exact stdout file, JUnit SHA/manifest and detailed docs. Verify all artifacts, commit portable sources/docs to existing Draft PR only, package local evidence separately, update handoff. Do not block M27 on the 16 external gates.

## 9. Handoff completeness and limitations
- The GitHub repo is PUBLIC. This handoff includes the full relevant project trajectory and file paths, not user secrets or unrelated saved memory. Conversation-local noncommitted historical ZIP/JUnit bytes are not embedded in GitHub due to privacy, size, and original provenance concerns.
- The authoritative implementation at handoff is GitHub's branch HEAD, not any incomplete container filesystem or conversation prose. Preserve approved main/CI policies, source, tests and release HOLD. Disclose any artifact you cannot access rather than claiming it is committed.
