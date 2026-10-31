# Handoff (historical baseline 2026-10-23)

## Current-source checkpoint (2026-10-31)

**Use remote `main` and GitHub CI as the current source of truth.** The
contents below are historical and can include outdated release/backlog claims.
Published PyPI v0.5.0 predates the 2026-10-31 multi-TCP/UDP and GX Works
Ethernet model changes. One independent PLC runs in **one OS process**; all
listeners of that process share its state. The currently implemented model
keys are `qj71e71` (Q), `lj71e71` (L) and `rj71en71` (iQ-R).
Review [Ethernet settings](ETHERNET_MODEL_SETTINGS.md),
[FX5 1E/3E protocol gates](research/FX5_SLMP_FRAME_SCOPE_20261031.md), and
[manufacturer research matrix](research/GXWORKS_ETHERNET_PARAMETERS_20261031.md),
[remaining hardware gaps](research/ETHERNET_HARDWARE_NEXT_20261031.md) and
[issue #14](https://github.com/greatgc-flow/VirtualPLC/issues/14) for
accuracy and future changes. Reference-only GX Works3 FX5 CPU/FX5-ENET/
RnCPU hardware metadata is available under `virtual-plc guide ethernet --json`
without promoting these interfaces to runnable profiles. CLI model selection
infers the wire profile; explicit JSON overrides are tracked even if equal to
the factory default. Review changes against
[VerySimpleGuide](https://github.com/greatgc-flow/VerySimpleGuide). Vendor TCP/IP timers are *reference-only*;
physical PLC equivalence is not claimed. The source checkout also supports
opt-in `--ascii-numbering fx5-octal` for X/Y octal on the generic 3E/4E
simulator. The new explicit `--slmp-1e` mode implements a bounded
**1E 00..03 batch-only** binary/ASCII adapter using synthetic Q memory;
this is **not** a complete FX5-ENET/RnCPU hardware profile. See
[issue #22](https://github.com/greatgc-flow/VirtualPLC/issues/22)
for remaining remote operations, unsupported devices, firmware-specific
policies and physical PLC acceptance. Do not mark hardware parity.

---


State: virtual-plc 0.5.0 released (PyPI + GitHub), main clean, CI green, 6,320 local tests pass.
Design: docs/DESIGN.md. Unverified-vs-real-PLC backlog: issue #2.

## Open items
1. (done 2026-10-30, user-confirmed) PyPI trusted publishers registered and chat-pasted token revoked; first tag push should verify auto-publish.
3. Gemini review done 2026-10-30 (see below); triage pending peer consensus.
4. oracle-watch.yml and the release publish path are unexercised on GitHub.
5. Verify unverified behaviors against manuals (end codes C200/C201, ASCII hex numbering, dword order, etc.).
6. Fork greatgc-flow/pymcprotocol (D:\Engram1\workspace\pymcprotocol; origin=fork, upstream=senrust): feature work not started.

## Working setup
- peerhub store: `D:\Engram1\.peerhub\core.db` (use `--db`); peers cc, cx, ag. Run `peerhub guide` first.
- cx sandbox has no network/pip; run installs/builds yourself (`.venv` in repo; build with `python -m build --no-isolation`).

## Standing rules (from user memory)
- Reuse peerhub sessions (`--stream`/`--request-id`); unanimous peer consensus for material decisions; "끝장토론" before implementation (TDD/SDD-ready).
- Minimize this terminal's tokens; delegate even small edits. Do NOT fall back to cc when cx/ag are quota-blocked; wait for reset (cc only for short reviews/ballots).
- AI-to-AI/code/docs in English; Korean to the user. Terse terminal output.
- Keep branches/workspace clean; update deps before release; remove over-engineering (github.com/greatgc-flow/VerySimpleGuide); log lessons as GitHub issues.
- Near limits: write handoff + print ONE-line continuation prompt. Never assume unverified facts; ask ambiguities in batches.

## Update 2026-10-23 (markitdown fork)
- Fork greatgc-flow/markitdown (upstream=microsoft; local clone D:\Engram1\workspace\markitdown deleted 2026-10-30, re-clone from origin when needed). Our PyPI dist is `markitdown-gc` (0.2.0, packages/markitdown). `markitdown-mcp`/`markitdown-ocr`/sample-plugin are upstream-owned; do not publish.
- PR #9 (ci/release-workflow: tag-triggered release.yml + tests on push to main) MERGED 2026-10-23. GitHub env `pypi` created.
- Existing `tests` workflow has a Windows-ARM job that queues for hours (runner unavailable); PR #9 had no checks run.
- PyPI trusted publishers still to register by user: virtual-plc (VirtualPLC/release.yml/pypi) and markitdown-gc (markitdown/release.yml/pypi).
- Git identity in repos: greatgc-flow <greatgc@gmail.com>.

## Update 2026-10-30 (Gemini review, ag.effort via G pool; stream vplc-gemini-review)
ag needs read-only-tools instruction (shell denied headless) plus `--writable`. Raw findings triaged by cc (verified only where noted):
- Valid, low: server.py start() does not clear `_stopping` (restart unsupported); stop() leaks listener if acceptor never started; Server latch check uses isinstance (bool accepted) vs type() in Memory.
- Wrong/unsupported: MAX_POINT is used (profiles.py:39, tests) so "dead code" is false; echo alnum check likely matches spec (echo data are 0-9/A-F chars), remote STOP mode (1,) likely spec-fixed 0001H. Verify vs manuals (issue #2) before changing.
- Needs manual check: ASCII hex addressing for X/Y/B/W (item 5), bad_end_code frame shape (error frame should carry no data), 0xC061 vs 0xC05C on length mismatch, zero-point random ops, 960-word batch limit.
- Simplification candidates (need consensus): guide.py (343 lines) and GuideParser in __main__.py.
Next: peer ballot (cx/cc) on triage, then TDD fixes for confirmed items.

## Update 2026-10-30 (ballot + fixes)
Unanimous ballot (ag, cx, cc): fix 3 low-risk server items, defer MC-spec items to issue #2, keep guide.py. Implemented via ag.effort (stream vplc-impl-ag): Server restart/idempotent start/stop, shared `valid_span` (memory.py) for latch ranges, tests/test_server_lifecycle.py. 5,900 tests pass.
Open follow-ups from ballot: pin echo-alnum and STOP mode (1,) with tests; list deferred unverified items in docs/DESIGN.md; document restart semantics (port 0 rebinds a new port).
ag tip: first turn of a fresh ag session returns empty (shell denied); resend with "ONLY file read/edit tools" on the same stream. cx X-7D was 88% on 2026-10-30; avoid until reset.

## Update 2026-10-30 (manual cross-check applied)
Sources (kept local in git-ignored `.manual/`; see docs/manual/PROVENANCE.md): SH-080008 rev AB, SH-081257 rev AD. Unanimous ballot (ag, cx, cc) applied via ag: DATA_LENGTH_MISMATCH 0xC061 -> 0xC057; echo payload 0-9/A-F (both cases, case unverified); C200/C201/C202 documented as manual-unsupported. 5,903 tests pass.
Open: #5 remap password end codes to C203/C204; #6 hex ASCII numbering policy for X/Y/B/W; #2 remaining unverified (zero-point random ops, bad_end_code frame shape, batch limits per module); #4 handoff issue; pymcprotocol fork work not started; PyPI auto-publish unexercised (next tag push).
Gotcha: repeated full pytest runs exhaust Windows ephemeral ports (WinError 10048 in client.connect); wait ~2-3 min for TIME_WAIT to drain, then rerun.

## Update 2026-10-30 (late): #6 and error information
- #6 closed: `--ascii-numbering manual` (hex X/Y/B/W/SB/SW/DX/DY/ZR), default compat.
- Error responses now carry error information (route + command + subcommand) per SH-080008 5.2/5.3; bad_end_code injection strips data and appends it (unanimous ballot). 5,937 tests pass.
- Still open: #5 (blocked: manual does not define locked-gate end code), #2 (zero-point random ops, per-module batch limits unverified), pymcprotocol fork work (needs user scope), PyPI auto-publish (next tag push).

## Update 2026-10-30 (final of session)
Zero-point random ops now return C053 (bit) / C054 (word,dword) (unanimous ballot; path-to-code assignment unverified). 5,977 tests pass.
Remaining: #5 blocked on evidence (locked-gate end code); weighted random upper bounds (1920/960) and per-module batch caps deferred (formula symbols unreadable in extraction; read the PDF page visually if needed); pymcprotocol fork work needs user scope; PyPI auto-publish unverified until next tag push (consider releasing 0.4.0 with these behavior changes).
CI: Windows runners hit WinError 10048 (ephemeral port exhaustion); fixed by a `netsh ... dynamicport` step in ci.yml (run 41029671000 green on all 8 jobs). Verbose-close test idle timeout widened to 0.3 s.
Random-access upper bounds (read 192/96, write weighted 1920/960, bit 188/94) enforced by wire class; 6,202 tests pass. Review follow-ups (low): parametrize write over-limit tests for all Q-class profiles, fix extra=67 case to reach 255 on iQ-R, add docstring line on limits.

## Release v0.4.0 (2026-10-30)
Tag v0.4.0 pushed; build job green, `publish` failed with PyPI `invalid-publisher` (no matching trusted publisher for repo greatgc-flow/VirtualPLC, workflow release.yml, environment pypi). github-release skipped. After the user fixes the PyPI publisher: `gh run rerun 41032569882 --failed -R greatgc-flow/VirtualPLC` (skip-existing is on, so reruns are safe), then verify PyPI shows 0.4.0 and the GitHub release has assets.

## pymcprotocol fork assessment (2026-10-30, ag.deepthink, read-only, claims not yet verified by tests)
Full report: docs/manual/pymcprotocol-assessment-2026-10-30.md. Top items: (1) ASCII hex device numbers written back as decimal for X/Y/B/W (t3e:339-345); (2) parse error responses incl. error information into MCProtocolError; (3) empty/short reply treated as success; (4) client-side random-access limits; (5) framed receive; (6) setaccessopt zero values; (7) exception hygiene; (8) LSTC/LTN constants and unsigned word writes. Needs user scope decision before implementation (work happens in D:\Engram1\workspace\pymcprotocol, origin=greatgc-flow fork).

## v0.4.0 published (2026-10-30)
Trusted publisher fixed by the user; rerun (attempt 3) of run 41032569882 succeeded: PyPI shows 0.3.0 and 0.4.0, GitHub release has wheel+sdist. Open: #2 (batch caps, real-PLC verification), #5 (needs evidence); pymcprotocol PRs #1/#2 awaiting merge decision (cx quota exhausted until ~2026-11-04).

## pymcprotocol fork merged (2026-10-30)
User instructed the merge. PR #1 (hex ASCII numbers, error information, short replies) and PR #3 (random-access limits, framed receive, setaccessopt zeros, LSTC/LTN; re-opened because deleting #1's base branch closed #2) are merged into greatgc-flow/pymcprotocol main; 52 tests pass (the real-PLC test is deselected). cx never voted (quota exhausted until ~2026-11-04): record this deviation. Open: VirtualPLC #2, #5. Optionally bump the oracle pin in requirements-dev.txt only after a fork release exists.

## Batch caps (2026-10-30, post-0.4.0, unreleased)
Per-profile batch caps (Ethernet E71 column, SH-080008 p.87/91/96): word 960, bit 7168 binary / 3584 ASCII (QnA 480/3584/1792); over-limit -> C051 (word) / C052 (bit), assignment unverified; --max-points default is now None (optional extra cap). 6,320 tests pass. Not yet released (next version would be 0.5.0 given the CLI default change). Remaining in #2: real-PLC verification only.

## v0.5.0 published (2026-10-30)
Release run green (build, publish, github-release); PyPI shows 0.5.0 wheel+sdist. Includes per-profile batch caps (C051/C052), --max-points default None. Open: #2 (real-PLC verification of code/path assignments), #5 (needs evidence for locked-state end code). pymcprotocol fork main has the client fixes (hex ASCII numbers, error info, limits, framing); no fork release yet.
