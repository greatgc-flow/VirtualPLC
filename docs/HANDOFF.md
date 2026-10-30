# Handoff (2026-10-23)

State: virtual-plc 0.3.0 released (PyPI + GitHub), main clean, CI green, 5,891 local tests pass.
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
