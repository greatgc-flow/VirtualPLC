# VirtualPLC — IPv6 transport & Windows UDP evidence consolidation (PR #63)

Date: 2026-11-04 KST | Issue #13 | Review branch only: **NO MAIN MERGE**

## Inputs checked directly

| Source | Exact head / test blob | What remains unique |
| --- | --- | --- |
| main | `069af7aa5e192b3b3b0b2d5040a7d9061135a415` | Baseline unchanged, protected=false, rulesets=[] (#54) |
| PR #56 | head `fbf83767eab72ffc94fe91dc7fd74e93e2a87aea`; IPv6 test blob `31c200baa38bf2a25cc0fabc97ef4dcb0b03b25a` | Real IPv6 TCP/UDP 3E/4E binary/ASCII; one memory; restart; malformed/oversized; peer-selected fault; wildcard rejection |
| PR #59 | head `1f5f000d3dd331594d189e5fd646942e4f3055a8`; native-test blob `3d35207ebd28729e67560fdfb930d91a03c9fb46` | Independent original Windows ICMP 10054 observation provenance, not needed as duplicated merged test |
| PR #61 | head `e2971a62dedf1171d853d5aaceb46b6816daee2c`; integration blob `01cd78796135aaf6aba6801ff1582ad194a43ddd` | Registered-worker **native Windows** 10054, exactly one WARNING, degraded Health and manual restart, among other cases |
| PR #62 | head `5b14a1987e58c2fb56bd15e7efa83718944cc205` | Five optional UDP counters + #61 Health/WARNING; exact-head CI #41779246404 completed 9/9 |
| PR #63 | branch `test/ipv6-udp-observability-consolidation-20261104` | Test-only additional IPv6 characterization, documentation, no runtime source delta |

All source PRs are historical independently successful candidates and remain OPEN/UNMERGED. The new branch derives from #62, **not a main push**.

## Coverage comparison and minimum addition

**Preserve #56 exactly** as `tests/test_ipv6_loopback_transport.py`, 15 cases.
It exercises a distinct address family with real IPv6 sockets on both
Ubuntu/Windows, and has no corresponding byte-identical test in #62.
The IPv6-only fixture checks actual loopback bind, skips when unsupported.

**Do not duplicate #59's whole test suite:** Its three cases are
(a) direct `_udp_loop` synthetic terminal error and manual restart,
(b) native Winsock 10054 from a standalone observer wrapper, and
(c) stale listener not revived by calling `start()` alone.
PR #62 already includes #60's stale-worker Health and restart
regression, plus PR #61's stronger **registered Server worker**
native 10054 + WARNING + degraded Health + stop/start test.
Source #59 is not byte-identical and is retained untouched as
independent OS observation provenance; omitting its duplicate test
does not mean deleting its original branch or Action result.

**Add exactly three new cases** in
`tests/test_ipv6_udp_observability.py`:
1. IPv6 `::1` mixed TCP+UDP Health and real 3E binary UDP read with
   opted-in `received/sent` counters; explicit two-cycle stop/start
   keeps cumulative counts and refreshes ephemeral addresses.
2. Same contract for 4E ASCII request/response/serial.
3. IPv6 `::1` fault-plan peer selector: first post-dispatch reply
   dropped (`fault_dropped=1`, not rejected), next request gets a
   real reply (`sent=1`); per-listener Health stays healthy.

Use bounded Event synchronization on counter updates, no arbitrary
sleep to assert sent-count delivery. Tests bind only IPv6 loopback
port zero. IPv6 may be OS-disabled: preserve reasoned SKIPs and do not
claim successful IPv6 execution on a skipped runner. No new threads,
locks, SDKs, CLI flags, IOCTL, automatic retry/rebind or write replay
in runtime; tests-only instrumentation tracks existing counters.
The `get_listener_health()` report is a best-effort snapshot, not
remote MC/PLC reachability.

## CI and evidence gate

PR #56 last standalone independent #41459979769 was 9/9. PR #59
#41475077193 separately demonstrated native hosted Windows 10054,
not all Windows installations. PR #62 combined-source
#41779246404 at exact head was 9/9 SUCCESS.

PR #63 **must** have its *own* exact-final-head completed 9/9:
wheel build plus Ubuntu and Windows Python3.10–3.13 tests.
Check executed case counts and any IPv6 skips separately.
This is additive characterization of existing behavior, not
a runtime behavior change requiring a fabricated RED state.
Keep any failed tests and changes traceable in PR #63 and issue #13.

## Governance, non-goals, ownership

main remains unmerged until the user explicitly authorizes it.
No tag `v*`, PyPI, physical PLC, real production/factory network
or unverified Mitsubishi hardware/firmware parity. Issue #54 requires
admin-applied main PR and immutable release tag rulesets; do not
claim they are active merely because green CI ran. Maintain the
original #56–#62 branches, tests, docs and historical CI evidence.

## 2026-11-04 final structural/SSOT audit addendum

Fresh review from source tree and exact original Git blobs confirms:
- #56 IPv6-only regression source is included **byte-identically**.
- #57 optional metrics tests are preserved in #63 through #62.
- #58 terminal WARNING and #60 nonblocking Health plus their exact
  source tests are preserved through #61, then #62 and #63.
- #59 standalone native Windows observation remains independent
  evidence; #61 already supplies registered-worker native Windows
  10054 + warning + unhealthy Health + manual recovery, so #59's
  overlapping suite is intentionally not imported.
- #63 is an **unmerged combined candidate**, not a command to close,
  merge or delete historical PR #56–#62.

The original #63 head
`759db62239badd6cad64d59cb3859d08ae2c4694`
has exact [CI #41785899899](https://github.com/greatgc-flow/VirtualPLC/actions/runs/41785899899)
COMPLETED SUCCESS 9/9 (Ubuntu each 7,238 PASS+1 Windows-only
SKIP; Windows each 7,243 PASS; build PASS).

One additional **distinct** cross-feature test was committed on
PR #63, `tests/test_udp_multi_listener_observability.py` at
`af48fa23728c07b2c971537ff6f0099367a0e684`.
It uses two real registered UDP sockets on 127.0.0.1 port 0:
a scripted terminal 10054 in one worker, exactly one WARNING,
no retry, surviving sibling UDP MC reply, aggregate Health false,
per-port worker liveness [false,true] with sockets still open,
per-Server metrics received/sent 1/1, no counter for failed recv,
no implicit repair on `start()`, then explicit `stop();start()`
and both UDP listeners responding (cumulative 3/3).
[Test-only CI #41804509573](https://github.com/greatgc-flow/VirtualPLC/actions/runs/41804509573)
was **COMPLETED SUCCESS 9/9**, Ubuntu each
7,239 PASS +1 Windows-only SKIP, Windows each 7,244 PASS,
wheel build PASS. This is **characterization of existing code**,
not a behavior change or fabricated RED. The only code delta
is the single new test file; documentation is reconciled here.

**Operational limitation observed from source:** `LOG.warning`
on terminal UDP receive errors does not include the affected local
bind address/port. Health identifies which listener is dead, but
metrics remain per-Server, not per-port. Treat this as deferred P2
diagnostic correlation scope, **not** permission to add a new
per-listener counter table, retry mechanism, logger thread, or
network diagnostic endpoint without a separately justified test-first
change. A callback may observe conservative false/false/[] during
lifecycle contention; snapshots are not atomic protocol checks.

No main merge, no release tag/PyPI, real PLC or production/factory
traffic, and no vendor hardware parity claim. Last observed main
`069af7aa5e192b3b3b0b2d5040a7d9061135a415`,
`protected=false`, rulesets `[]`; governance Issue #54 is open.
Verify the eventual documentation commit's own exact-HEAD 9/9
before claiming its final CI GREEN.
