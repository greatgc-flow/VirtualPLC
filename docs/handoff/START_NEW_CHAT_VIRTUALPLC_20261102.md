# VirtualPLC — NEW CHAT START / 2026-11-02 (RUNTIME + GOVERNANCE)

> **Historical snapshot.** Superseded by the "Current state" section of [docs/HANDOFF.md](../HANDOFF.md)
> (for example, 11 required checks on Python 3.10–3.14 since 2026-11-09).

## Role, authorization and priority

You are continuing development of the GitHub repository
https://github.com/greatgc-flow/VirtualPLC. Use the **actual latest
remote main/PR/issues/CI** as SSOT: snapshots and hashes in this file
can become stale. User authorizes scoped branches, issues, commits,
PRs and squash merges **only after exact PR CI 9/9 PASS**; then verify
independent new-main push 9/9. This handoff is technical, contains no
personal memory/secrets and is safe to commit in a public repository.
Do NOT publish to PyPI, push a release `v*` tag, contact real PLCs
or production/factory networks, or claim official Mitsubishi parity.

## First-turn required verification

1. GET latest `main` branch full HEAD and protected flag. Check current
   open PRs, open issues, latest Actions runs and their nine jobs.
   Prefer newer HEAD to all hashes below.
2. Read in order: `AGENTS.md`, `docs/HANDOFF.md`, this file,
   `docs/governance/BRANCH_RELEASE_GATES_20261102.md`,
   `docs/DESIGN.md`, `docs/BEHAVIOR.md`, `docs/FAULTS.md`,
   `.github/workflows/ci.yml`, `.github/workflows/release.yml`.
3. Review issue #54 governance, #13 TCP/UDP, #25 handoff,
   #14 GX Ethernet manuals, #22 SLMP 1E and #2 vendor/physical gates.
4. Establish any latest PR and CI proof. Distinguish PR run from
   independent `push/main` run and distinguish a failed JOB from a
   cancelled/superseded WORKFLOW. Do not invent CI outcomes.
5. Pick one bounded, evidence-backed task: preferable next work is
   #54 enforce rulesets by owner/admin UI (if permission available),
   or #13 UDP client example / useful datagram-native coverage.
   Avoid implementing duplicate/reorder/corrupt faults without
   a documented bounded policy, deterministic tests and demand.
6. Leave a three-line Korean result, GitHub PR/CI links and handoff
   after the task. When chat grows, commit source-supported technical
   decisions/handoff and write a detailed next-chat starter prompt.

## Last VERIFIED remote state (before any newer change)

- main: `7ea3b718dd5aba848a9b9dc1e0b1642560e9b433`
- PR #52: squash merged; independent main CI run #41436034796
  `push` completed SUCCESS 9/9: wheel plus Ubuntu/Windows
  Python3.10–3.13, Ubuntu3.11 **7,159 PASS**.
- Exact PR #52 SHA `75a492b9a5306b138f871caa747dcf078a0d1f8d`,
  PR CI #41435360893 completed SUCCESS 9/9, Ubuntu3.11 7,159 PASS.
- PRs open: 0; issues open: #25, #22, #14, #13, #54, #5, #2.
- GitHub repo is public; `/branches/main` protected=false;
  `/rulesets` returned []; branch protection detail GET 403
  (integration cannot access that endpoint). No available
  connected GitHub admin *write* action to activate rulesets.

## Implementation chain, proof and limitations

- PR #48: listener bound+settimeout failure closes entire startup
  endpoint set; exact main CI #41396146386 9/9, 7,115 tests.
- PR #49: per-Server RLock start/stop lifecycle races; exact
  main CI #41405662272 9/9, 7,118 tests.
- PR #50: prevent queued, already-buffered TCP write from beginning
  after stop; in-flight execution may finish; exact main
  CI #41423539256 9/9, 7,120 tests.
- PR #51: check UDP receive return and pre-dispatch lock for
  1E/3E/4E during shutdown; exact main CI #41429231844 9/9,
  7,127 tests.
- PR #52: independent opt-in `UdpFaultPlan`, only post-dispatch
  UDP response `drop` and stop-cancellable `delay`; match command,
  global response nth, source IP; server Python option and
  `--udp-fault-plan FILE`. Preserves TCP FaultPlan and its
  UDP prohibition. Exact PR/main CI as listed above.
- Test-first evidence exists in linked PRs and issue #13; some
  earlier RED workflow runs are cancelled after their individual
  Ubuntu jobs recorded expected failures. Test-fixture 4E ASCII
  expected-zero-word correction is recorded; don't present it
  as a production bug.

## Invariants / architecture / security

- One independent PLC is one OS process. One Server may bind
  multiple TCP/UDP ports sharing one PLC Memory, CPU and request lock.
- Default loopback binding only; explicit allow_nonlocal and
  idle_timeout needed for nonlocal binds. Not authenticated.
- UDP accepts one complete <=8192-byte 1E or MC3E/4E datagram,
  no sessions/retry/stream semantics. Malformed frames drop silently.
- Standard-library runtime; maintain pinned pymcprotocol==0.3.0
  offline client-compat tests. No unsupported protocol defaults.
- Runtime `ethernet.py` vs reference-only `ethernet_reference.py`
  are independently owned; no reverse import. GX CPU/module scope
  must remain explicit, and reference UNKNOWNs remain UNKNOWN.
- Mitsubishi original manual SH-081257ENG AD vs AG, and
  SH-082488ENG E vs I source clause comparisons NOT_VERIFIED;
  issue #14/#22/#2 remain open. No real hardware validation.
- `AGENTS.md` has a test-enforced 40-line ceiling.
- No secrets, personal memory, internal business identifiers,
  licensed manufacturer PDF bytes or credentials in public repo.

## Release/governance risk needing owner/admin action

- Rule set is currently EMPTY and main unprotected. CI success is
  voluntary until enforced. The linked GitHub app cannot perform
  admin ruleset changes; seek owner to use Settings > Rulesets.
- Suggest main branch rule: PR required (0 approval acceptable
  for solo workflow), **all 9 named build/test checks**, block
  force-push and deletion. Separate v* tag rule: block update/delete
  but permit deliberate creation with explicit release approval.
- `.github/workflows/release.yml` automatically publishes to PyPI
  on v* tag push after its workflow gates. Do not push tags;
  a tag alone is a release-triggering action, not a harmless marker.
- GitHub official Rulesets docs and exact check names are in
  `docs/governance/BRANCH_RELEASE_GATES_20261102.md`.

## Preferred next steps and completion gate

(A) Verify the latest main and issues, then owner-applied
    `main-ci-pr-gate` and `v*` tag rulesets; record actual ID,
    active policy and merge-blocked test in #54. If settings are
    not writable, leave #54 OPEN and do not claim completion.
(B) Next independent engineering slice: evaluate demand for an
    optional raw UDP client example and/or IPv6 loopback tests.
    Avoid new UDP packet scheduler and costly duplicated logic.
(C) For behavior change: first tests-only commit and observed
    real RED; minimal GREEN; docs parity; exact PR SHA full
    build+Ubuntu/Windows 3.10-3.13 9/9; squash; new independent
    main push at exact merged SHA 9/9; issue #13/#25 handoff.
(D) Do not release, publish, use production networks or assert
    real PLC compliance. Keep secrets and personal user data out.

## What to report in Korean

3-line completed-vs-unfinished summary; source/PR/CI URLs;
exact commit and test count where verified; current protections
with any admin blocker, no real PLC/PyPI. Continue without
re-asking already documented approvals.

## 2026-11-02 later session continuation (PR #55)

- Later verified baseline before branch: main `caa4dc2a34da7a819809a607eb13ba335dc03946`, main push CI #41448900230 9/9.
- PR #55 adds a standalone IPv4 loopback-only, standard-library MC3E binary D0 UDP reader, strict response source/length/end-code validation and executable tests. RED test-only `fc8b399529a5273c190773e36edd648e2bc0b607` (CI #41453639346); verify actual final HEAD and CI/merge outcome before acting.
- Governance #7 broad audit was CLOSED during PR #53; #54 is the OPEN owner/admin-only follow-up for unapplied main and v* tag rulesets. The connection has no ruleset write ability. Do not push release tags or claim protection active.
- Read `docs/HANDOFF.md` and #25/#54 for the most recent checkpoint after PR #55; do not assume this starter's commit remains current.
