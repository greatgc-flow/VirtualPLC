# VirtualPLC — NEW CHAT HANDOFF / PR #56–#61 consolidation review
Date: 2026-11-03 (KST) | Repo: https://github.com/greatgc-flow/VirtualPLC

## Paste this as the next chat's first instruction

You are a development/review agent for `greatgc-flow/VirtualPLC`.
Continue from **the latest actual remote GitHub state**. All SHAs
below are dated evidence, not a reason to override a newer main.
The user's latest authorization: commit on separate branches, open
PRs/issues and keep technical evidence, but **DO NOT MERGE ANY PR
INTO MAIN** without a new explicit user instruction. Do not publish
PyPI, create `v*` release tags, connect to a real PLC, or access
production/factory networks.

### Restoration checklist — required first

1. Fetch main HEAD, protected flag, repository rulesets, open PRs,
   issues, Actions and exact nine job results. Last observed main:
   `069af7aa5e192b3b3b0b2d5040a7d9061135a415`,
   protected=false, rulesets=[]; #54 is not applied.
2. Read repository `AGENTS.md`, `docs/HANDOFF.md`,
   `docs/handoff/START_NEW_CHAT_VIRTUALPLC_20261102.md`,
   this file, `docs/reviews/UDP_PR56_61_CONSOLIDATION_REVIEW_20261103.md`,
   `README.md`, `docs/BEHAVIOR.md`, `docs/DESIGN.md`,
   `docs/FAULTS.md`, `docs/CLIENT_COMPATIBILITY.md`,
   governance #54 and both CI/release workflow files. For PR-specific
   files read each source branch, not only main.
3. Read the latest issue #13 and #25 comments and PR #56–#61
   descriptions/patches. Check fresh SHA and 9/9 CI before claiming
   any new completion. Compare PR #57 vs #61 `server.py` UDP loop
   carefully; do NOT silently stack changes.
4. Respect no-main-merge and no-release constraints even if dated
   handoff docs contain older permission to merge. Do not access
   physical PLCs or infer verified Mitsubishi firmware behavior.

### Last verified work (before this review-only commit)

- #56 IPv6 tests, head
  `fbf83767eab72ffc94fe91dc7fd74e93e2a87aea`;
  Actions #41459979769 9/9 SUCCESS.
- #57 opt-in UDP metrics, head
  `a593f3d76aed07bee622f3f8bef94cc34a263693`;
  Actions #41469614503 9/9 SUCCESS.
- #58 UDP terminal `recvfrom` WARNING, head
  `8816d76e8c24cdedd377722aafb87c6e81fdb452`;
  Actions #41471970159 9/9 SUCCESS.
- #59 native Windows UDP ICMP 10054 loopback,
  head `1f5f000d3dd331594d189e5fd646942e4f3055a8`;
  Actions #41475077193 9/9 SUCCESS, Windows native
  observation, Linux Windows-only SKIP.
- #60 local TCP/UDP Health API, nonblocking lifecycle RLock
  after a stop/join/response_hook deadlock RED,
  head `f7742a61fe641dbea162ab75136ecf51f49d82ca`;
  Actions #41586576010 9/9 SUCCESS.
- #61 independent combination #58+#60 + new integration tests,
  HEAD *before this doc-only review commit*
  `0a7d797937892add1039a4be1ed6282f2dc5d541`;
  [Actions #41590981213](https://github.com/greatgc-flow/VirtualPLC/actions/runs/41590981213)
  COMPLETED SUCCESS 9/9. Ubuntu Python3.10–3.13:
  7,198 PASS+1 intended Windows-only SKIP each.
  Windows Python3.10–3.13: 7,203 PASS, zero skips each.
  Same combined CI tested **native** Windows 10054 from real
  registered UDP worker, exactly one warning, degraded Health,
  explicit stop/start and valid MC read. No main merge.
- All six PRs OPEN and not merged at this review. No new main push.
  New doc-only commit on #61 requires **a fresh final-head 9/9
  result**, which must be checked before claiming it passed.

### Consolidation findings / next recommended work

- #61 already contains warning+Health and both original tests.
  PR #58 terminal regression file SHA
  `147b25f58b32193e1e877e492f12efbcd9773276`
  is identical in #61. PR #60 Health tests blob SHA
  `0e504376e61d286df683878c591bff07a4373bf9`
  is identical in #61. Do not separately merge #58/#60
  if #61 is ultimately chosen. Keep original historical PR
  evidence/branches until explicitly directed to close them.
- #56 and #59 are tests/docs evidence; #57 is NOT included
  in #61, and its accounting/callback validation overlaps the
  UDP loop modified in #58/#61. A later #57+#61 combination
  requires independently reviewed acceptance tests and exact
  combined-head 9/9; do not assume a clean merge.
- Read all detail/risk priorities in
  `docs/reviews/UDP_PR56_61_CONSOLIDATION_REVIEW_20261103.md`.
  Prefer a brief, independent test-first next slice over feature
  accretion. Do not introduce monitoring daemons, automatic
  replay/rebinding or unnecessary CLI options.
- #54 owner/admin must implement main branch + immutable v* tag
  rulesets; connected GitHub integration currently cannot apply.
  There are still #22 FX5 1E, #14 Ethernet module defaults,
  #5 password end codes, #2 vendor parity research backlog items.
  Never label unverified vendor/document/hardware behavior proven.

### Engineering style / final report

Use Python 3.10–3.13, stdlib runtime, simple independent functions,
nullable/empty cases, local loopback ephemeral ports, explicit
opts only when justified, rich usage docs and tests-first RED
evidence. All change commits belong to scoped branches.
Every final source candidate needs exact-head GitHub Actions
build+Ubuntu/Windows Python3.10–3.13 9/9 PASS; no claims for
queued or cancelled runs. Always give 3 Korean summary lines
and GitHub links. Do not create local worktree artifacts unless
needed; clean them after committing. Keep any private human context
out of this public repo and use only technical handoff details.

### End of handoff

No release tag, PyPI publication, or main merge was done.
Source, decisions, CI and next-step technical context are preserved
on the PR #61 branch and linked GitHub issues.
