# VirtualPLC — Open PR #56–#61 consolidation review
Date: 2026-11-03 (KST) | Issue: #13 | Outcome: REVIEW ONLY / NO MAIN MERGE

## Verified source of truth

Actual remote GitHub main HEAD at review:
`069af7aa5e192b3b0b2d5040a7d9061135a415`.
Main branch `protected=false` and repository rulesets API `[]`:
**issue #54 is NOT enforced**. All PRs #56–#61 were OPEN, ready for
review, NOT MERGED, and target the same main HEAD. Last published
PyPI release must not be inferred from any of these branch tests.
This document contains engineering-only context; no personal data or secrets.

| PR | Responsibility | Exact HEAD | Verified CI | Assessment |
|---|---|---|---|---|
| #56 | IPv6 ::1 TCP/UDP loopback tests | `fbf83767eab72ffc94fe91dc7fd74e93e2a87aea` | [#41459979769](https://github.com/greatgc-flow/VirtualPLC/actions/runs/41459979769), 9/9 | Independently useful test-only evidence, no server runtime delta |
| #57 | Optional per-Server UDP diagnostic counters and callback validation | `a593f3d76aed07bee622f3f8bef94cc34a263693` | [#41469614503](https://github.com/greatgc-flow/VirtualPLC/actions/runs/41469614503), 9/9 | Separate opt-in feature; requires rebasing/explicit combined checks with #61 |
| #58 | Unexpected terminal UDP `recvfrom` WARNING | `8816d76e8c24cdedd377722aafb87c6e81fdb452` | [#41471970159](https://github.com/greatgc-flow/VirtualPLC/actions/runs/41471970159), 9/9 | Runtime and regression suite INCLUDED in #61 |
| #59 | Real Windows loopback ICMP / Winsock UDP 10054 evidence | `1f5f000d3dd331594d189e5fd646942e4f3055a8` | [#41475077193](https://github.com/greatgc-flow/VirtualPLC/actions/runs/41475077193), 9/9 | Independent native-OS observation, some behavioral overlap with #61 |
| #60 | Read-only Python listener Health with nonblocking lifecycle lock | `f7742a61fe641dbea162ab75136ecf51f49d82ca` | [#41586576010](https://github.com/greatgc-flow/VirtualPLC/actions/runs/41586576010), 9/9 | Runtime and regression suite INCLUDED in #61 |
| #61 | Combined #58 WARNING + #60 Health plus integrated tests | `0a7d797937892add1039a4be1ed6282f2dc5d541` *before this review-only commit* | [#41590981213](https://github.com/greatgc-flow/VirtualPLC/actions/runs/41590981213), exact-head 9/9 | Recommended canonical **review candidate**, not yet a main integration decision |

Old CI results pertain to their exact listed SHAs only. A new
documentation-only review commit must receive its *own* final-head 9/9
before it is considered green. A superseded/cancelled intermediate CI
run is not evidence of success or a regression.

## Evidence of redundancy and preservation

- PR #58 `tests/test_udp_receive_terminal_diagnostics.py` Git blob
  `147b25f58b32193e1e877e492f12efbcd9773276` is **exactly the
  same SHA** in PR #61 (83 source lines).
- PR #60 `tests/test_listener_health.py` Git blob
  `0e504376e61d286df683878c591bff07a4373bf9` is **exactly the
  same SHA** in PR #61 (186 source lines). Includes the bounded
  response_hook/stop deadlock regression.
- PR #61 adds `tests/test_udp_warning_health_integration.py` blob
  `01cd78796135aaf6aba6801ff1582ad194a43ddd`:
  five integrated pytest cases on Windows (four on Ubuntu with the
  native Winsock case deliberately skipped). It exercises *registered*
  worker / warning + health state + explicit manual recovery, not just
  standalone method mocks.
- PR #61 runtime diff versus main contains only (1) the
  `get_listener_health()` method from #60 (using nonblocking
  `_lifecycle_lock.acquire(False)`, false/false/[] on contention),
  and (2) terminal UDP `recvfrom` WARNING from #58. No new monitor
  thread, lock, hardware access, automatic retry, socket rebind or
  protocol behavior. Both original PRs remain untouched.
- PR #59's native Windows evidence is **not byte-for-byte identical**
  to PR #61's integration test, though it tests the same OS error:
  #59 also documents native observation and manual lifecycle tests.
  Keep both provenance trails until a later deduplication decision.
- README, BEHAVIOR, DESIGN, guide, HANDOFF, dated restart document
  were edited by multiple PRs; PR #61 reconciles #58/#60 wording
  but this does not preempt future concurrent #57 or #56 docs edits.

## Consolidation choice: minimal, traceable and non-destructive

**Recommended after future explicit user authorization:** treat PR #61
as the candidate single change set for WARNING + Health. Do **not**
merge #58, #60 and #61 separately: that risks duplicate artifacts and
confusing commit/feature provenance. Keep #58/#60 OPEN as verified
historical source inputs until the owner decides whether to close them
as superseded. A historical PR does **not** need a separate main
merge to preserve its branch, SHA, CI and issue links. No PR is closed
or merged as part of this review.

#56 is tests-only, independent of this runtime feature. It can be
assessed separately, although docs/HANDOFF edits may need resolving.
#59 is likewise tests/docs-only and records independent genuine
Windows observations; avoid accidentally running overlapping
loopback tests twice merely to inflate the suite. Do not delete
evidence or tests without confirming unique scenarios are retained.

#57 is **not** subsumed. It adds `udp_metrics=False` configuration,
`get_udp_metrics()`, an opt-in counter lock, metrics accounting and a
UDP response_hook result check. Its `_udp_loop` rewrites the same
`recvfrom`-to-`sendto` block touched by PR #58/#61. A naive merge
could overwrite `except OSError as error` + WARNING, lose `_count_udp`
calls, or change shutdown/response semantics. Treat this as a
**real overlapping change region**, NOT a proven unresolvable Git
conflict. It needs a separately scoped branch + combined regressions.
Keep opt-in metrics disabled by default. Do not add `receive_errors`
or other counters without deciding their exact semantics and testing
that a terminated UDP worker does not continue counting.

## Risk and review checklist, by priority

| Priority | Risk | Gate / expected evidence |
|---|---|---|
| P0 | main currently unprotected; `v*` tag release may publish | Owner/admin activates and verifies #54 branch/immutable tag rulesets. No tags until explicit release authorization |
| P1 | #57 UDP metrics loop overlaps #61 WARNING logic | No silent overwritten branches; choose preservation rules for warnings, metrics, timeout, stop, late packet, invalid hook, fault drop, send errors. TDD + exact combined CI 9/9 before *any* later main merge |
| P1 | Stop holds lifecycle lock while joining workers; callback Health can deadlock | Preserve PR #60's nonblocking lock and Event-gated test. Under contention report conservative false/false/[]; never auto-restart on a single false snapshot |
| P1 | UDP send may have executed a non-idempotent command before reply loss | No blind replay, retry or automatic rebind; manual operator-directed stop/start only; ports bound to zero may change |
| P2 | Different PRs modify the same docs and handoff | Reconcile SSOT README/BEHAVIOR/DESIGN/guide/HANDOFF once, keep issue links for historical provenance. Avoid copying entire handoff history into runtime docs |
| P2 | CI proof can be overstated | Require GitHub Actions `head_sha` == final PR HEAD and completed success all 9 jobs, inspect every OS test summary, distinguish intentional Windows-only skip |
| P2 | Native Windows `10054` is host-policy-dependent | Native test must observe real Winsock errno; if not delivered, SKIP with reason, never claim universal Windows behavior or hardware parity |
| P3 | Health `healthy=True` may be stale and false/empty during lock contention | Document transient local snapshot, not remote MC-response guarantee. Do not connect metrics or operator automation to health without an explicit policy |

**Very Simple judgement:** do not add new abstractions, duplicate
runtime services, restart supervisors or CLI flags now. The present
minimal method + warning are adequate for a local embedding process.
New functionality must justify a separate independently testable
slice and minimize instructions/token cost.

## Reproducible acceptance and release boundaries

1. Retrieve live remote main, PR heads/mergeability, issues, branch
   rulesets and Actions; do not trust these dated hashes over GitHub.
2. Read `AGENTS.md`, `docs/HANDOFF.md`, dated starter, governance and
   release workflows, and all PR diffs. Confirm that #61 already
   includes the original regression suites via exact blob SHAs.
3. Do not modify or merge main without a **new explicit instruction**.
   Creating/reviewing side branches and issue comments is allowed.
4. Before any future combined #57+#61 work: define expected exact
   behavior tests first, observe RED, implement minimally, then
   document and obtain 9/9 exact-head CI. Do not claim combining
   distinct independently green PRs is automatically safe.
5. Preserve release boundaries: no `v*` tags, PyPI, physical PLC,
   production/factory network or unverified Mitsubishi revision parity.

Related: [#13](https://github.com/greatgc-flow/VirtualPLC/issues/13),
[#25](https://github.com/greatgc-flow/VirtualPLC/issues/25),
[#54](https://github.com/greatgc-flow/VirtualPLC/issues/54).
