# VirtualPLC — Project Handoff

## Current state
- Released version: v0.9.0 (2026-11-10); previous v0.8.0 (2026-11-10).
- Upstream client oracle pin: `pymcprotocol==0.3.0` (`requirements-dev.txt`).
- Governance tracker #54 closed (rulesets active: branch 26796594, tag 26796603; see [gates](governance/BRANCH_RELEASE_GATES_20261102.md)); #7 closed. Rebase each PR onto main and get fresh required checks before merging (strict=false).
- Open issues: #2, #5, #68, #69 (blocked on vendor/physical evidence), #13 (narrowed hardware-free scope), #25 (handoff), #78 (keyword-only API, 1.0).
- Ruleset 26796594 requires 11 checks (build + Ubuntu/Windows 3.10–3.14) since 2026-11-09; `test-macos` is informational.
- Release gate: tag only a main commit whose `ci.yml` push run succeeded (release.yml enforces it).
- Active documentation SSOT: see [AGENTS.md](../AGENTS.md) and [README.md](../README.md).

## 2026-11-10 release 0.9.0 — release-note source

Two opt-in additions; default behaviour is unchanged (no breaking changes).

- #79: opt-in stored-cell cap `Memory(max_cells=N)` / CLI `--max-cells N` (default unchanged: uncapped). Only new points count (overwrites always allowed; SD203 counts); a write past the cap answers C056 on 3E/4E and 1E and changes nothing (whole-request check; 3E/4E random writes now commit via `write_atomic`); an over-cap `--init`/`Memory.load` raises ValueError / exits 2. New `memory.CellCapExceeded` (subclass of `OutOfRange`) and `Memory.stored_cells`.
- #13 (narrowed scope, point 3): opt-in TCP session counters, `Server(tcp_metrics=True)` + `server.get_tcp_metrics()` (`accepted`, `rejected` at `max_clients`, `idle_closed`, `closed`), mirroring the UDP counters: `None` when disabled, requires a TCP listener, cumulative across stop/start, no CLI flag. Semantics: [BEHAVIOR.md](BEHAVIOR.md#tcp-session-counters-opt-in).

## 2026-11-10 release 0.8.0 — release-note source

MECE completeness review (7 product areas x 6 quality dimensions + 8 cross-closure checks), two rounds of independent scoring with fixes in between, plus a newcomer sample project. Behaviour changes to list first in release notes:
- Echo (0619) length errors return C057 on ASCII as on binary (was C05C on ASCII).
- An odd-word batch write to LCN returns C051 before anything is written (SH-081257 3.5, p.453); other dword devices keep the half-word policy.
- 1E: a binary/ASCII device code with a byte >= 80H, or a leading-space/byte-swapped name, returns C05B (was a closed connection or a silent match). Once the frame size is valid, non-hex 1E device codes, heads and data return C05C and write nothing; header/framing fields still close.
- `Server(slmp_1e=True, ascii_numbering="fx5-octal")` raises ValueError (1E ASCII uses X,Y HEX numbering). Wrong-typed `profile`, `initial_state`, `memory`, `latch_ranges` or `response_hook` raise ValueError before binding.
- `Memory` heads and counts must be `int` (bools/floats raise ValueError).
- CLI `--init` loads before the server is built, so `--initial-state` sets SD203 (a snapshot's SD203 is overwritten), and `--show-effective-ethernet` now also validates `--init` and `--dump-on-exit` (exit 2).
- CLI `--dump-on-exit` is checked for writability before binding (exit 2); empty path arguments exit 2; JSON inputs (`--init`, fault plans, `--ethernet-config`, oracle observations) accept a UTF-8 BOM, and oracle observations also UTF-16.
- Fault-plan `match.connection` counts only admitted TCP sessions and restarts at 1 on each `start()`.
- `guide` and the offline oracle/manual-evidence CLIs reject abbreviated options; `--help` names `virtual-plc guide`; the startup banner shows `udp_fault_plan` and `max_clients` and brackets IPv6 hosts.
Minor: the private `virtual_plc.version` / `PackageNotFoundError` re-exports were removed; Server fault-plan errors hint `guide faults`; the qj71e71 manual URL uses dl.mitsubishielectric.com.
Additions: `examples/bottling_line` sample project (5 runnable steps, CI-tested); `Server` docstring; README Safety and "Other options" sections; documented manual divergences (1E two-byte error code, C05C vs C050/C05A/C05B, 1E indirect device paths).
Docs/tests: README links absolute (PyPI-safe) with link/anchor closure over every Markdown file; README python blocks executed in CI; SH-081257 citations corrected to printed p.453; ERROR_CODES sources C056/C057/C059/C05C marked manual.
Delivery: release tooling pinned in `requirements-release.txt`; the CI sdist run uses `python -I` so it tests the installed package; GitHub `pypi` environment restricted to `v*` tags.

## 2026-11-09 session close

v0.7.0 is published and verified: PyPI and GitHub assets match, and a clean install from PyPI passed smoke. Independent review scored 100/100. The session records (ballots, consensus, reviews, process lessons) are archived on #25. Next candidates: #13 optional hardware-free scope, #78, #79, and promoting `test-macos` to a required check once it is stably green. #2, #5, #68 and #69 stay blocked on vendor or physical evidence.

## 2026-11-09 release 0.7.0 — release-note source

Post-0.6.0 improvement round (unanimous ballot ag/cc/cx + independent Fable review; #75 #76 #77 #80 #81 #82 #83). Behaviour changes to list first in release notes:
- `Memory.write_words/write_bits` reject non-integer values (floats, strings) with ValueError before storing anything; bools still stored as 0/1.
- `Memory.load` address keys must be plain ASCII decimal digits.
- `idle_timeout`, fault `seconds`/`pause` and UDP delay above `threading.TIMEOUT_MAX` are rejected at configuration (CLI exits 2).
- CLI no longer accepts abbreviated long options (exit 2).
- ASCII requests use the binary end-code order: truncated/extra ASCII payloads now C057 (was C05C); over-limit counts win over bad payloads. `0101` with a payload returns C057 (binary answered OK).
- Windows UDP 10054 no longer stops the UDP worker (user-approved); new `receive_resets` metric key.
- TCP `response_hook` must return bytes-like data (else that connection closes); `start()` refuses a host name that binds off-loopback (`NonLoopbackBindError`, an OSError).
Fixes: cross-connection TCP stop race, UDP `rejected` count on unexpected errors, TCP accept warning/recovery. Additions: `OutOfRange` export, IPv6 UDP example. Packaging: the sdist now ships examples/ and tools/. CI: SHA-pinned actions, Python 3.14, sdist test run, per-SHA main concurrency, release CI gate, informational macOS job.

## 2026-11-08 release 0.6.0

Since 0.5.0: multi-listener TCP/UDP, SLMP 1E, UDP faults and observability, Ethernet models and offline references; non-loopback host needs `--allow-nonlocal` and `--idle-timeout`, and `--max-clients` defaults to 64.

## 2026-11-08 #13 observability rebuild

#13 observability rebuilt from #63 onto main; #56-#62 superseded (see PR).

## 2026-11-02 #13 UDP client example and governance #54 (PR #55)

New bounded source-only UDP client example for one MC3E binary D0 read:
`examples/udp_read_d0.py` is standard-library-only, validates full
response header/length/end code/source and refuses non-loopback hosts.
No runtime Server/CLI behavior change; pinned pymcprotocol==0.3.0 remains
the TCP client oracle. Tests-first RED SHA
`fc8b399529a5273c190773e36edd648e2bc0b607`,
[CI #41453639346](https://github.com/greatgc-flow/VirtualPLC/actions/runs/41453639346)
Ubuntu Python3.11 job prior 7,159 PASS + 21 expected FAIL on absent
example script; new script/tests/README/CLIENT_COMPATIBILITY prepared.
Final candidate PR/main CI must be independently verified before
declaring completion (9/9 build + Ubuntu/Windows Python3.10-3.13).
Current remote baseline at start caa4dc2a34da7a819809a607eb13ba335dc03946
(PR #53 docs-only merged, main CI #41448900230 9/9 PASS).
Important governance correction: the broad review #7 was closed,
but no main rulesets are actually active; owner/admin action is
tracked by OPEN issue #54 (not #7). `main` protected=false; rulesets=[];
this integration cannot activate rulesets. DO NOT create v* tags
(release workflow may publish to PyPI). No actual PLC/vendor parity.

## 2026-11-02 #54 (formerly #7) repository rulesets / release gate verification and new-chat handoff

At review baseline main `7ea3b718dd5aba848a9b9dc1e0b1642560e9b433`,
branch API `protected=false` and rulesets API `[]`; legacy protection
detail GET 403 for connected GitHub integration. **No actual ruleset
was activated in this session.** GitHub actions available here do not
permit repository admin ruleset writes. Last independent main push CI run #41436034796
COMPLETED SUCCESS 9/9, Ubuntu Python3.11 7,159 PASS.
Release v0.5.0 only; no tag, PyPI or physical PLC action.

Scope of this docs-only PR: owner-action checklist
`docs/governance/BRANCH_RELEASE_GATES_20261102.md` documents the
nine exact required checks, main PR/force-push/delete restrictions,
separate v* tag immutability gate and explicit release approvals.
Source-owned next-chat handoff
`docs/handoff/START_NEW_CHAT_VIRTUALPLC_20261102.md` supersedes the
dated 2026-11-01 starter; README links it. Corrected DESIGN's
contradiction about UDP-specific response faults and PR #52's
already completed PR/main CI evidence here. No behavior, tests,
CLI, dependencies or workflow action changed. Broad review #7 was closed;
ruleset activation remains tracked by OPEN issue #54 until an administrator
**actually applies and verifies** rulesets.
## 2026-11-02 #13 UDP response-native fault plan (PR #52)

First opt-in drop/delay datagram response fault slice. Independent
UdpFaultPlan/--udp-fault-plan: command, global UDP response nth,
numeric peer IP; after dispatch and response_hook. Distinct from
TCP FaultPlan; no plan means normal unchanged behavior. No
duplicate/corruption/reorder or physical PLC semantics.

Tests-only RED f134073253278a9cc90ef5b8766ad25dd351cace
(CI #41434118229): Ubuntu Python3.11 7,127 old PASS, 26 expected
FAIL on absent virtual_plc.udp_faults and CLI option. Implementation
7124389d787beaadd19e75dcf849f6993fa08d1c. Final PR
75a492b9a5306b138f871caa747dcf078a0d1f8d CI #41435360893
**COMPLETED SUCCESS 9/9**, Ubuntu Python3.11 **7,159 PASS**.
PR #52 squash merged main 7ea3b718dd5aba848a9b9dc1e0b1642560e9b433;
independent exact-main push CI #41436034796 **SUCCESS 9/9**,
Ubuntu Python3.11 **7,159 PASS**, 0 open PRs at checkpoint.
Vendor AD/AG E/I source comparison remains NOT_VERIFIED.
No real PLC, production network, new dependencies or PyPI release.
## 2026-11-02 #13 UDP receive/parse vs shutdown dispatch guard (PR #51)

`_udp_loop` previously checked `_stopping` at the top of the recv loop
and prior to send, but a datagram returned while stop began could still
execute a write and silently change PLC Memory. It now drops datagrams
when `_stopping` is already set on receive return. `_udp_response` also
checks the stop event **under the existing shared request lock** before
executing 3E/4E or opt-in 1E dispatch, covering stop during decoding.
Already executing dispatch may still finish; no transaction rollback
or physical PLC parity claim.

**Genuine tests-only RED** `3ace67f6b092023119d22b6870e49a61975bce43`,
[CI #41428081297](https://github.com/greatgc-flow/VirtualPLC/actions/runs/41428081297):
Ubuntu Python3.11 job **7,120 PASS and 7 expected FAIL**. Five
3E/4E binary/ASCII + 1E synthetic datagram cases mutated D0=0x1234
after stop; two real-loopback UDP tests held 3E/4E decode or 1E framing
while stop began and mutated D0=0x5678. Response was suppressed but
memory was not protected. Other jobs also failed on these expected tests.
Tests use fake recvfrom for exact receive boundary and actual loopback
UDP + thread Events for parse boundary, no external PLC.

**Minimal implementation** `a8f21d50842bb8522821c032fa463ba4648afe70`:
only `virtual_plc/server.py`, adding receive-return stop check and
request-lock-local stop checks for both 1E and 3E/4E. No new
dependencies, CLI flags, default values, remote network access or
extra dispatch lock. Full cross-OS CI must be verified on the exact
final PR candidate before merging; then independently verify main
push CI on the squash SHA.

**Remaining #13:** UDP-native faults, optional client examples and
nonlocal metrics/rate limits, IPv6/Windows edge coverage. This does
not claim race-free global linearizability at every OS event, cancellation
of already-dispatched work, or physical PLC parity. Manufacturer
SH-081257ENG AD↔AG and SH-082488ENG E↔I clauses NOT_VERIFIED;
no production network/real PLC/PyPI.

## 2026-11-02 #13 in-flight stop and pipelined TCP dispatch guard (PR #50)

On the shared Server, TCP `_serve_frames` previously checked shutdown
only at the outer recv loop. One recv containing read+write could process
the later write even after stop began during the first in-flight read.
Now the inner buffered-frame loop checks `_stopping` before starting each
next frame. This preserves the current already-executing dispatch; it does
not promise rollback of an in-flight PLC request. UDP keeps existing
post-dispatch send suppression during shutdown.

**Tests-first RED with realistic worker cleanup**
`1fb52da0d1a957b307939b7d3eb0d2b8851ff702`,
[CI #41422322631](https://github.com/greatgc-flow/VirtualPLC/actions/runs/41422322631)
Ubuntu Python3.11 **7,119 PASS and 1 expected FAIL**:
after stop, queued TCP write changed D0 to 0x1234, instead of remaining 0.
Initial tests-only `da59dd26856266cabae5b0c5cf865f673f0b2325`
[CI #41421921593](https://github.com/greatgc-flow/VirtualPLC/actions/runs/41421921593)
also failed, but first at missing cleanup in a scripted test connection;
that fixture issue was corrected before using the observed RED evidence.
Actual correction `7d225ebcb440d426fa45e27c07fd21f46ef16e67`.

Companion test covers in-flight UDP response hook, stop before send, and
restart with a successful actual loopback datagram. The TCP test also
verifies cleanup of both endpoints and normal TCP/UDP operation after
restart. Validate exact final PR SHA 9/9 on build + Ubuntu/Windows
Python3.10–3.13, then independent postmerge main push CI before GREEN.

No new CLI flags, protocol/default values, dependencies, physical PLC,
production network or PyPI action. Mitsubishi AD↔AG and E↔I revisions
remain NOT_VERIFIED; future UDP receive-vs-stop dispatch race is a
separate #13 issue, not part of this TCP fix.

## 2026-11-02 #13 concurrent start/stop and TCP/UDP request lock (PR #49)

Concurrent external starts and stops on the same Server are now serialized
by a per-instance reentrant lifecycle lock. A stop racing a blocked bind
waits for the starting listener pack to finish, then closes all endpoints.
A second concurrent start does not bind a duplicate TCP/UDP pack.
Separate Server instances have separate locks; this is **not** multi-PLC
or physical-PLC behavior. Existing command dispatch and request lock remain
unchanged; a real TCP write/UDP read test pins serialization on shared
Memory under the existing request lock.

**Genuine tests-only RED** `7ce94d2e6ff1f568f31e23461b780eac35d53d4b`,
[CI #41404589397](https://github.com/greatgc-flow/VirtualPLC/actions/runs/41404589397)
Ubuntu3.11 job **7,115 PASS + 2 expected FAIL**:
stop returned while start was blocked in create_server, and a second start
bound before the first completed. Deterministic bound localhost socket
barriers, cleanup checks and cross-OS matrix; no real PLC.

**Implementation** `21ac34bc50615b6c17fb9e608d8e9f12c8bd797e`.
**Additional request-lock regression** `c3079945c07e7d34a8d6eea0be890358dbb09e12`.
Check the exact final candidate CI (build + Ubuntu/Windows Python3.10–3.13),
then squash merge and independent main push CI before claiming GREEN.
No default/CLI/SLMP/PyPI/manufacturer parameter changes. Mitsubishi
AD↔AG and E↔I clause comparisons remain NOT_VERIFIED.

## 2026-11-02 #13 late listener-timeout setup rollback (PR #48)

When the second TCP or UDP socket has been created/bound but its listener
`settimeout` fails, `Server.start()` now closes the newly created socket
*before* propagating the original exception. Existing outer rollback still
closes all earlier bound sockets, with no worker started. An unchanged Server
instance can then bind, serve and stop/restart with real loopback TCP/UDP.

Observed tests-only RED `ca81f2c981f5be8b2c988d0c865b6bf2a2990d27`
([CI #41395382427](https://github.com/greatgc-flow/VirtualPLC/actions/runs/41395382427)):
Ubuntu Python3.11 job **7,111 PASS / 4 expected FAIL**, all four
TCP→TCP, TCP→UDP, UDP→TCP, UDP→UDP combinations failed on an unclosed
second listener. Code fix `27ee55925a6aa433b0428fc76d1a65e8964eb1c9`.
Gate: exact PR head CI (build + Ubuntu/Windows Python3.10–3.13) 9/9,
then squash and independent exact new-main push CI 9/9.

No PLC wire, memory, CPU state, manufacturer defaults, dependencies,
real PLC, production network or PyPI changes. All tests are loopback-only;
manual AD↔AG/E↔I source clauses remain NOT_VERIFIED.

## 2026-11-02 #13 TCP accepted-socket setup failure isolation (PR #47)

The per-port TCP accept worker now catches `OSError` while configuring a
newly accepted socket's `TCP_NODELAY` or `idle_timeout`. It closes only
that peer and continues accepting; no client worker/slot is allocated for
failed setup. UDP, protocol commands, PLC state, network safety guards,
configuration defaults and PyPI remain unchanged.

Observed tests-first RED `59bb621f609074d8cb119db3bf879e90441a638b`:
[CI #41381290013](https://github.com/greatgc-flow/VirtualPLC/actions/runs/41381290013)
Ubuntu Python 3.11 **7,109 old PASS and 2 expected FAIL** (injected
`setsockopt` / `settimeout` exceptions killed accept loop). Small fix
`df2fac400b59105fdbd7e3b3ae7b74138bb1ff3f`. Gate: exact final PR
9/9 build + Ubuntu/Windows Python 3.10–3.13, then independently verify
post-merge main 9/9 before final GREEN claim. No physical PLC / production
networks or vendor AG/I clause claims.

## 2026-11-02 complete-pack PDF preflight (PR #46)

The developer-only local manual PDF evidence utility now checks **all** supplied
edition roles (pair shape, existing PDF header/size, SHA-256 uniqueness across
families) **before** invoking any text extractor. A malformed, absent or
byte-duplicate later edition no longer causes unnecessary earlier `pdftotext`
work. Extraction order and existing per-file post-extraction and whole-pack
final fingerprints remain unchanged; valid report JSON schema unchanged.

Observed tests-only RED `5443ae7657533f77d7f1440d634af7a653751a9e`:
[CI #41374056432](https://github.com/greatgc-flow/VirtualPLC/actions/runs/41374056432),
Ubuntu Python3.11 **7,106 PASS + 3 expected FAIL** (invalid pack called
extractor). Implementation `d485e7640e9cc0f374900cbd2f5969e289f489b1`.
Before declaring GREEN or merging, check exact final candidate PR CI
and independent postmerge main CI (build + 8 OS/Python jobs).

No vendor PDF bytes, authenticity or AD/AG / E/I clause parity were
verified; `NOT_VERIFIED` remains. No simulator network/CLI/PyPI changes.

## 2026-11-01 PDF full-pack source stability across editions (PR #45)

Starting verified remote main: `42e52fd5d9781f4c44aad5ab15c3eae19221c49b`;
[main CI #41282564326](https://github.com/greatgc-flow/VirtualPLC/actions/runs/41282564326)
completed 9/9, Ubuntu Python3.11 7,102 PASS.
New [PR #45](https://github.com/greatgc-flow/VirtualPLC/pull/45) tests-only
commit `d2d89f3725b4eb23020701b74a43cb93528b9dfc`:
[RED CI #41301971183](https://github.com/greatgc-flow/VirtualPLC/actions/runs/41301971183),
Ubuntu3.11 **7,103 PASS, 2 expected FAIL** and Windows3.13
**7,107 PASS, 2 expected FAIL** — late source mutation not rejected.
The implementation `90e1ed5e354f562e0dea1cc5ba2d78f079d178ca`
stores each pre-extraction source fingerprint, retains the post-extract
check and checks every input PDF once again after *all* editions/families
have finished extraction, before reporting. No reported schema change,
runtime code, vendor value, dependencies, physical PLC or PyPI changed.
This is not protection against every TOCTOU race nor vendor authentication.

Official fresh R04CPU manufacturer page lists Ethernet AG (2026-10)
and CPU I (2026-08); some stale crawled snapshots list AF (2026-04).
Research-only catalogue note: [issue #14](https://github.com/greatgc-flow/VirtualPLC/issues/14#issuecomment-6557323167).
Do not infer a scope difference from mixed-age snapshots.
Authentic AD+AG and E+I original PDFs still unavailable; actual
clause parity remains `NOT_VERIFIED`.
**Before calling GREEN or merging:** verify final exact PR head
CI completed 9/9 (build plus Ubuntu/Windows Python3.10–3.13),
squash merge and verify independent exact-sha main push CI 9/9.

## 2026-11-01 developer-only manual evidence atomic JSON output (PR #44)

Session starting main: `4a3e4083584136e27e0fe1aaa063cfae2fb1f438`,
[main CI #41277321048](https://github.com/greatgc-flow/VirtualPLC/actions/runs/41277321048)
9/9 PASS, Ubuntu3.11 7,099 PASS.
Tests-first RED commit `d3719c1aaf7c001f64897b02f9ddabe878cdbf70`
in [PR #44](https://github.com/greatgc-flow/VirtualPLC/pull/44);
[RED CI #41282058680](https://github.com/greatgc-flow/VirtualPLC/actions/runs/41282058680)
Windows Python3.13: **7,103 PASS, 3 expected FAIL** for direct
overwrite, missing atomic publication and no-overwrite race.
Implementation `c99d9bd6316b488bedfafb41e6b360bf5e716e41`
stages a same-directory tempfile, flushes/fsyncs it, atomically
replaces with explicit --overwrite or exclusively links without it.
On publication failure the old report remains and temporary file is
removed. Unsupported hard-link filesystems fail closed.
No runtime/socket/CLI schema changes, dependencies, manufacturer PDF
redistribution, real PLC or PyPI. Official AG/I catalogue publication
still does not establish AD↔AG or E↔I clause equivalence: NOT_VERIFIED.
Before claiming GREEN, verify final candidate PR CI exactly 9/9,
then squash merge and verify independent main push CI exactly 9/9.

## 2026-11-01 local Mitsubishi PDF evidence integrity and next-chat continuity (PR #43)

Latest verified starting main: `54e65cb3074187cd1adb2e006d28aeaf58948a2e`
([CI #41271965936](https://github.com/greatgc-flow/VirtualPLC/actions/runs/41271965936)
9/9 PASS, Ubuntu3.11 7,094 tests; only open PR was Dependabot #11). New focused
[PR #43](https://github.com/greatgc-flow/VirtualPLC/pull/43),
branch `fix/manual-evidence-source-integrity-20261101`, validates
source chain of custody for the optional local manual PDF kit:
duplicate source SHA-256 is rejected across PDF edition roles even
when filenames differ, and each PDF is rehashed after extraction
to detect same-length or length-changing in-place modifications.
No new dependencies, API/report schema changes for valid inputs,
runtime PLC/network changes, or source-SSOT promotion.

Tests-only RED `7aab81d3d9c018f97f7cc82603b389b755d4d0ed`,
[CI #41276732098](https://github.com/greatgc-flow/VirtualPLC/actions/runs/41276732098):
Ubuntu Py3.11 logged **7,095 pass and 4 expected fails** (no
ValueError for duplicate PDF and mutation), genuine RED. Code
implementation `8a545eb0eaeb94ec0de7e648cc9640be294a64fd`.
Final PR and merged-main CI exact HEAD 9/9 must be checked
**after** the latest change; never claim GREEN from earlier CI.
[Runbook](research/RNCPU_MANUAL_PDF_EVIDENCE_KIT_20261101.md).

Manufacturer current catalogue confirms Ethernet Application
SH-081257ENG-AG (2026-10) and CPU Module SH-082488ENG-I
(2026-08). Actual authentic PDF bytes were unavailable in
this environment again (official reader/host failures); no
AG-vs-AD or I-vs-E clause equality was established.
Both `newer_revision_comparison` remain **NOT_VERIFIED**.
Human next action: acquire authentic AD+AG and E+I PDF pairs,
run the kit locally, retain PDF SHA/source URL, then inspect
true manufacturer clause/tables and review with #14 and #2.

For seamless continuity, read
[dedicated next-chat prompt](handoff/START_NEW_CHAT_VIRTUALPLC_20261102.md)
and fetch latest main/CI before modifying anything.

## 2026-11-01 offline Mitsubishi AD/AG and E/I manual PDF evidence kit (PR #42)

Official [Mitsubishi R04CPU manual catalogue](https://www.mitsubishielectric.com/fa/products/faspec/download.page?category=ex&formNm=RnCPU_R04CPU_3322&id=spec&kisyu=%2Fplcr&lang=2)
confirms Ethernet `SH-081257ENG-AG` 2026-10 (19.23MB) and CPU
`SH-082488ENG-I` 2026-08 (18.39MB). **Real original PDF source
clauses were still inaccessible in this execution environment**:
AG URL unavailable; I/AD/E too large for web extraction, and local
manufacturer host DNS failed. No SHA or original source PDFs were
obtained; **AD→AG and E→I clause parity remains NOT_VERIFIED**.

New developer-only `tools/manual_revision_evidence.py` with
`tools/__init__.py` provides a reproducible local workflow when
genuine edition pairs are downloaded. Its report screens PDF magic,
computes SHA256 over original local bytes, checks weak first-page
edition hints and gathers limited page/term candidates. It explicitly
does **not** claim real PDF authentication, unchanged clauses or
physical PLC parity. All outputs keep `NOT_VERIFIED` and require
human review; none of this changes `virtual_plc/ethernet_reference.py`,
runnable `Server`, network/CLI runtime, PyPI or production equipment.
Instructions, optional local Poppler dependency, correct Windows
CMD/PowerShell 2.x command and acceptance guide:
[offline runbook](research/RNCPU_MANUAL_PDF_EVIDENCE_KIT_20261101.md).

Tests-first RED commit
`67aff10a7fa177b62ba96f6a8eb4d238def9cd75` on
[CI #41271434991](https://github.com/greatgc-flow/VirtualPLC/actions/runs/41271434991)
Ubuntu Python3.11: **7,079 preexisting PASS; 15 expected new fixture
errors** because the tools module was absent. Implementation
commit `b8a3975a44b810c3dc1153ff998d06a6d698b05e`,
and explicit developer tools package and doc/runbook follow.
**Check exact PR #42 and independent postmerge main 9/9 before
reporting GREEN.** Do not create manufacturer parity results without
the authentic PDF source evidence.

## 2026-11-01 R04CPU independent Ethernet AD/AG and CPU E/I revision gates (PR #41)

Live manufacturer catalogue independently confirms Ethernet
`SH-081257ENG-AG` **2026-10** and CPU `SH-082488ENG-I`
**2026-08**. Actual large PDF clauses could not be retrieved:
**AD→AG and E→I clause parity both NOT_VERIFIED**. Existing
reference-only AD slots/own-ports/A038H timers and CPU E A031H
opening-method warning remain unchanged. New opt-in
`cpu_manual_revision` and separate `cpu_manual_revision_check`
prevent an explicit newer CPU I source from being silently treated
as reviewed E when `opening_method` is supplied. Missing CPU
revision keeps legacy overall report semantics. CPU E/I source
uncertainty does not block an unrelated AD-only external-port/timer
preflight; static invalid slots/ports still take priority.

New `remote_opening_reference.manual_revision_gate` shares the
existing `reference_catalog()` single manufacturer metadata SSOT
with the separate Ethernet AD/AG gate. Tests-first RED branch
`feat/r04cpu-cpu-manual-revision-gate-20261101`,
test-only SHA `2f3e2928dcb24c327ab95979849ca7af142cfe0d`:
[CI #41265169171](https://github.com/greatgc-flow/VirtualPLC/actions/runs/41265169171)
Windows Python3.11 job independently logged **7,053 prior tests PASS**,
4 new validation cases PASS and **26 expected new cases FAIL** because
source CPU revision key/result were not implemented. Implementation:
`77047e7c8fdfb1ca7fffb8d5082c1b6bc109da86` (registry) and
`de42a86f07c1adc319285187df36307f8d0de928` (composite).

**Verify current PR #41 exact candidate CI then independent merged main
CI 9/9 before claiming GREEN.** No runtime sockets, CLI, SLMP network
semantics, physical equipment or PyPI changed.
[Source matrix and examples](research/RNCPU_R04CPU_DUAL_MANUAL_REVISION_GATES_20261101.md),
[official evidence/limits in issue #14](https://github.com/greatgc-flow/VirtualPLC/issues/14#issuecomment-6552328065),
[PR #41](https://github.com/greatgc-flow/VirtualPLC/pull/41).
Pending authenticated vendor PDFs and manual clause diff; never
auto-promote AG/I parity based on catalogue publication.

## 2026-11-01 VerySimpleGuide Ethernet reference-ownership refactor (PR #40)

Separated two non-overlapping scopes from former `ethernet.py`:
runnable Q/L/iQ-R EthernetSettings, timer/model defaults and CLI catalogue
remain in `virtual_plc/ethernet.py` (now ~198 lines); the manufacturer
FX5/FX5-ENET/RnCPU reference-only registry and its 8 discovery/inspection
functions live in `virtual_plc/ethernet_reference.py` (~900 lines).
Manufacturer fact block moved **unchanged**; legacy `ethernet` module
re-exports same functions and private registries, with no wrappers,
duplicated tables, runtime reverse imports or new dependencies.
`virtual_plc/rncpu_reference.py` and `virtual_plc/guide.py` use their
existing imports, so CLI/JSON and source revision gates remain stable.

Observed tests-first RED: `e5d7ad9b336c173487f393dad591e4700b298338`,
[CI #41263480811](https://github.com/greatgc-flow/VirtualPLC/actions/runs/41263480811):
on Ubuntu Python3.11 **7,031 pre-existing PASS; 22 new expected
ModuleNotFoundError setup errors** because `ethernet_reference` was
deliberately absent. This is an architecture characterization test,
not a report of a runtime defect. Implementation extracted in
`62223551b838d7136fb2165e2ddf06fc988b83ba`; legacy facade
applied in `fca962e8c8dd3c65daa7b4bc3adda9d093756516`.

**After this handoff check exact HEAD candidate PR CI and postmerge main
CI before claiming GREEN**: build plus Ubuntu/Windows Python3.10–3.13,
9/9 jobs, and no client/guide/oracle regression. No real PLC/production
network, PyPI, physical-vendor acceptance, SLMP wire or simulator
socket behavior was changed. Vendor SH-081257ENG-AG vs AD clauses
remain **NOT_VERIFIED**, not inferred from this refactor.
Related [PR #40](https://github.com/greatgc-flow/VirtualPLC/pull/40),
[issue #7](https://github.com/greatgc-flow/VirtualPLC/issues/7) (now closed; see #54),
[issue #14](https://github.com/greatgc-flow/VirtualPLC/issues/14).

## 2026-11-01 VerySimpleGuide refactor: UDP dispatch boundary (PR #39)

Introduced private `Server._udp_response(packet)` to separate UDP
datagram transport I/O and shutdown from 1E/3E/4E complete-frame parsing,
shared-lock command dispatch, single post-dispatch response hook and 8KB
response cap. The UDP loop still rejects empty/oversized input before
dispatch and keeps existing drop/log/exception policy. Source-backed
manufacturer settings, public CLI, TCP/UDP ports, one-PLC-per-process
ownership and PyPI are unchanged.

Test-only RED [PR #39](https://github.com/greatgc-flow/VirtualPLC/pull/39):
first tests-only build had a pytest reserved-argument collection error
(corrected before claiming RED). Corrected tests-only SHA
`8be7fd351d871550b1a811b2e73a507fbb8dfd2f` showed
**7,007 existing PASS + 24 expected missing-method failures** on
Ubuntu Python3.11. Implementation SHA `523c85f3e4fa5c4abc5d28bc4116d55696f0084d`.
Read current exact PR candidate CI and main after any eventual merge;
do not claim GREEN until 9/9 and independent postmerge main CI.

Next maintainability review and deferred high-risk splitting are tracked
in [issue #7](https://github.com/greatgc-flow/VirtualPLC/issues/7) (now closed; see #54);
in particular, do not split `ethernet.py` source metadata or mix
1E and 3E/4E parsers without a measured coupling/compatibility benefit.

## 2026-11-01 R04CPU CPU built-in composite offline preflight (PR #38)

`virtual_plc.rncpu_reference.inspect_reference_r04cpu_configuration`
composes the three already independent reference-only inspectors:
CPU built-in Opening Method (remote STOP/RUN reconnect risk), R04CPU
A038H timer settings and GX Works3 external-device user slots/ports.
No duplicated Mitsubishi lookup tables, new network listeners, real
PLC calls or PyPI release. Missing vs empty vs explicit null, strict
keys/models, invalid own-port rows and source revision provenance are
tested. Manufacturer current catalogue lists SH-081257ENG-AG
(2026-10), but **AG-vs-AD clauses are NOT_VERIFIED**; results only
reference sourced SH-081257ENG-AD R04CPU examples. See
[implementation and negative contracts](research/RNCPU_R04CPU_COMPOSITE_PREFLIGHT_20261101.md)
and [PR #38](https://github.com/greatgc-flow/VirtualPLC/pull/38).
Read the PR and exact CI before declaring complete; all outputs are
offline synthetic diagnostics and **not** GX Works3 or hardware certification.

## 2026-11-01 R04CPU CPU built-in multi-entry configuration lint and AG source gate (PR #37)

Newest manufacturer catalogue lists SH-081257ENG-AG
(**2026-10**), but direct PDF contents were NOT accessible for
an AG-vs-AD clause diff. Existing facts remain explicitly
SH-081257ENG-AD pp.324-326 and Appendix 10 p.554, restricted
to R04CPU CPU built-in (not RJ71EN71 network part).
New offline `inspect_reference_rncpu_external_device_batch`
reuses the independent scalar reference checker and adds
developer-authored static diagnostics for duplicate configured
user slot numbers, optional holes, potentially reused PLC own
ports (review, not guaranteed conflict) and vendor-reserved
port violations. Strict root/input/row validation; None versus
[] is distinct; no vendor end codes, live TCP connection budget,
new network listeners, physical PLC or PyPI changes.
The SSOT carries `manual_revision_gate` with
`newer_revision_comparison=NOT_VERIFIED`.
See [research](research/RNCPU_R04CPU_BATCH_LINT_20261101.md),
[PR #37](https://github.com/greatgc-flow/VirtualPLC/pull/37),
and issue #14. Check actual CI/merge before assuming success.

## 2026-11-01 R04CPU CPU built-in external-device slot and own-port preflight (PR #36)

Mitsubishi official SH-081257ENG-AD pp.324–326 distinguishes the
**CPU built-in** GX Works3 configured user connection slots **1–16**
from RJ71EN71 network-part **1–64**; these are NOT live simultaneous
TCP socket limits. User-configurable PLC own ports: 1–4999 and
5010–65534, with the default Blank and recommended 1024–4999 or
5010–61439. Appendix 10 p.554 reserves several ports/ranges *inside*
those broad bounds (including 5001, 5005–5009, 61441, 61696–65534),
so system reservation overrides numeric range classification.

New standalone, no-network `inspect_reference_rncpu_external_device`
is restricted to the R04CPU example and reports source, unknown slot,
GUI blank port, recommended/discouraged/system-reserved classifications;
it never changes sockets or total client limits. All values in
`virtual_plc/ethernet.py` source registry, projected by
`guide ethernet --json`. See
[research](research/RNCPU_R04CPU_EXTERNAL_DEVICE_PORTS_20261101.md)
and [PR #36](https://github.com/greatgc-flow/VirtualPLC/pull/36).
Keep other RnCPU firmwares/models and physical parity UNKNOWN.
Verify actual latest PR and postmerge main CI before declaring complete.

## 2026-11-01 R04CPU built-in A038H timers, independent manual scope (PR #35)

Official SH-081257ENG-AD **R04CPU CPU built-in** parameter screen
pp.329-330 directly refers to timer table pp.396-397; separate CPU
SH-082488ENG-E p.685 identifies the CPU A038H parameter group.
New offline-only `inspect_reference_rncpu_data_timers("R04CPU", overrides)`
validates documented nine reference defaults, seconds/milliseconds
ranges, 100ms increments, Change/Set Timer Value flag, and printed
timer inequalities without borrowing RJ71EN71 source/default policy.
Other RnCPU models/firmware and physical timing remain UNKNOWN.
See [research](research/RNCPU_R04CPU_A038H_DATA_TIMER_REFERENCE_20261101.md)
and [PR #35](https://github.com/greatgc-flow/VirtualPLC/pull/35).
No actual PLC/port/OS timer changes or PyPI release. Verify exact CI.

## 2026-11-01 RnCPU CPU built-in remote opening safety preflight (PR #34)

Mitsubishi official CPU manual SH-082488ENG-E printed p.3 warns that
`Open by Program` can close the line on remote STOP and block a
subsequent external remote RUN. Appendix 8 pp.684–685 maps CPU built-in
`Opening Method` to A031H; `Timer Settings for Data Communication`
is A038H (not proof of matching RJ71EN71 timer defaults).
`inspect_reference_rncpu_remote_opening(None | "open_by_program" |
"do_not_open_by_program")` is offline/reference-only and keeps missing
configuration UNKNOWN. TDD and CI: [PR #34](https://github.com/greatgc-flow/VirtualPLC/pull/34);
[research/validation](research/RNCPU_REMOTE_OPENING_SAFETY_20261101.md).
No real CPU connection, automated RUN/STOP, socket changes or PyPI release.
Check current exact PR/main CI before assuming gate completion.

## 2026-11-01 RnCPU built-in service connection reference (PR #33)

Mitsubishi official FAQs [#20230](https://fa-faq.mitsubishielectric.co.jp/faq/show/20230)
and [#45267](https://fa-faq.mitsubishielectric.com/faq/show/45267)
document *different* RnCPU built-in Ethernet service requirements:
simple CPU communication receiving partner via auto-open UDP needs no
extra opening setting, while multiple GOTs using TCP need a per-GOT
GX Works3 External Device Configuration (GOT UDP does not).
The `reference_catalog()` SSOT and `guide ethernet --json` project
these separately without enabling network services. See
[service-specific matrix](research/RNCPU_BUILTIN_SERVICE_CONNECTIONS_20261101.md)
and [PR #33](https://github.com/greatgc-flow/VirtualPLC/pull/33).
Check live HEAD and exact PR/head CI; no physical PLC verification.

## 2026-11-01 FX5 CPU simple communication firmware gate (PR #32)

The offline, reference-only API
`inspect_reference_fx5_simple_cpu_communication(model, firmware_version)`
uses Mitsubishi FAQs #39316/#44329: FX5U/FX5UC require firmware >=1.110
for the *simple CPU communication* feature, FX5UJ/FX5S support it
from first release. Only documented U/UC mixed-firmware GX Works3
interop route is mapped; early UJ/S route remains unknown. No SLMP
socket/CPU behavior changes, physical captures or PyPI releases.
See [firmware matrix](research/FX5_CPU_FIRMWARE_SIMPLE_COMM_20261101.md)
and [PR #32](https://github.com/greatgc-flow/VirtualPLC/pull/32).
PR #32 was squash-merged into main
`42d1a19b1258c3dd0157f280049db7144992e7bc`; independent post-merge
[CI #41216086296](https://github.com/greatgc-flow/VirtualPLC/actions/runs/41216086296)
COMPLETED SUCCESS 9/9. Check for later remote changes.

## 2026-11-01 FX5-ENET alive-check reference timer validation (PR #31)

The new `inspect_reference_fx5_enet_alive_timers` API validates the
FX5-ENET module's SH-082026ENG-H p.70 existence-check start/interval/retry
factory values, supported units and ranges under an explicit Change/Set
Timer Value flag. Reference-only, no socket effects, runtime hardware
activation or physical PLC parity. See
[FX5-ENET alive reference](research/FX5_ENET_ALIVE_REFERENCE_20261101.md).
PR #31 was merged into main SHA
`fa8c71e469607eb88a2816e0ce4e424e73c1d9b1` with independent
post-merge [CI #41214550025](https://github.com/greatgc-flow/VirtualPLC/actions/runs/41214550025)
9/9 SUCCESS. Check for newer remote changes.

## 2026-10-31 FX5 reference-only port/connection preflight (PR #30 merged)

New `inspect_reference_slmp_port` in `virtual_plc/ethernet.py` exposes
manual-scoped FX5 CPU/ENET SLMP vendor port classification without socket
binding, runtime hardware activation, or changing `Server(port=0)` and
`max_clients=64`. Separates 8 aggregate Ethernet connections from
16/8 *simple CPU communication target* counts by CPU family. See
[FX5 port and connection scope](research/FX5_SLMP_PORT_SCOPE_20261031.md),
[PR #30](https://github.com/greatgc-flow/VirtualPLC/pull/30),
[#14](https://github.com/greatgc-flow/VirtualPLC/issues/14).
**PR #30 was squash-merged** into main SHA
`cf41bf1961d69ad85411f942fbc2c81cea748bcb`; post-merge main CI
[#41213732838](https://github.com/greatgc-flow/VirtualPLC/actions/runs/41213732838)
was independently verified 9/9 SUCCESS. Check for later main changes.

## 2026-10-31 offline reference oracle checkpoint

`python -m virtual_plc.oracle plan|template|compare` implements an
**offline, read-only** manual-vector comparison workflow for 1E 15/16
binary/ASCII. Strict self-reported origin/target provenance, SHA-256-only
reporting and no socket operations; never physical-certification evidence.
[Procedure](PHYSICAL_ORACLE.md). Always check live main/PRs/CI before
assuming this dated status is current.

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
**1E 00..03 batch, 04/05 random writes, 13/14 owner-scoped remote control, 15/16 diagnostics** binary/ASCII adapter
using synthetic Q memory;
this is **not** a complete FX5-ENET/RnCPU hardware profile. See
[issue #22](https://github.com/greatgc-flow/VirtualPLC/issues/22)
for unsupported device/firmware combinations, UDP control identity, physical error-code
fidelity and PLC acceptance. TCP STOP ownership persists across disconnect until local reset. Do not mark hardware parity.

## 2026-10-30 v0.5.0 published

Release run green (build, publish, github-release); PyPI shows 0.5.0 wheel+sdist. Includes per-profile batch caps (C051/C052), --max-points default None. Open: #2 (real-PLC verification of code/path assignments), #5 (needs evidence for locked-state end code). pymcprotocol fork main has the client fixes (hex ASCII numbers, error info, limits, framing); no fork release yet.

## 2026-10-30 Batch caps (post-0.4.0, unreleased)

Per-profile batch caps (Ethernet E71 column, SH-080008 p.87/91/96): word 960, bit 7168 binary / 3584 ASCII (QnA 480/3584/1792); over-limit -> C051 (word) / C052 (bit), assignment unverified; --max-points default is now None (optional extra cap). 6,320 tests pass. Not yet released (next version would be 0.5.0 given the CLI default change). Remaining in #2: real-PLC verification only.

## 2026-10-30 pymcprotocol fork merged

User instructed the merge. PR #1 (hex ASCII numbers, error information, short replies) and PR #3 (random-access limits, framed receive, setaccessopt zeros, LSTC/LTN; re-opened because deleting #1's base branch closed #2) are merged into greatgc-flow/pymcprotocol main; 52 tests pass (the real-PLC test is deselected). cx never voted (quota exhausted until ~2026-11-04): record this deviation. Open: VirtualPLC #2, #5. Optionally bump the oracle pin in requirements-dev.txt only after a fork release exists.

## 2026-10-30 v0.4.0 published

Trusted publisher fixed by the user; rerun (attempt 3) of run 41032569882 succeeded: PyPI shows 0.3.0 and 0.4.0, GitHub release has wheel+sdist. Open: #2 (batch caps, real-PLC verification), #5 (needs evidence); pymcprotocol PRs #1/#2 awaiting merge decision (cx quota exhausted until ~2026-11-04).

## 2026-10-30 pymcprotocol fork assessment (ag.deepthink, read-only, claims not yet verified by tests)

Full report: docs/manual/pymcprotocol-assessment-2026-10-30.md. Top items: (1) ASCII hex device numbers written back as decimal for X/Y/B/W (t3e:339-345); (2) parse error responses incl. error information into MCProtocolError; (3) empty/short reply treated as success; (4) client-side random-access limits; (5) framed receive; (6) setaccessopt zero values; (7) exception hygiene; (8) LSTC/LTN constants and unsigned word writes. Needs user scope decision before implementation (work happens in D:\Engram1\workspace\pymcprotocol, origin=greatgc-flow fork).

## 2026-10-30 Release v0.4.0

Tag v0.4.0 pushed; build job green, `publish` failed with PyPI `invalid-publisher` (no matching trusted publisher for repo greatgc-flow/VirtualPLC, workflow release.yml, environment pypi). github-release skipped. After the user fixes the PyPI publisher: `gh run rerun 41032569882 --failed -R greatgc-flow/VirtualPLC` (skip-existing is on, so reruns are safe), then verify PyPI shows 0.4.0 and the GitHub release has assets.

## 2026-10-30 Update (final of session)

Zero-point random ops now return C053 (bit) / C054 (word,dword) (unanimous ballot; path-to-code assignment unverified). 5,977 tests pass.
Remaining: #5 blocked on evidence (locked-gate end code); weighted random upper bounds (1920/960) and per-module batch caps deferred (formula symbols unreadable in extraction; read the PDF page visually if needed); pymcprotocol fork work needs user scope; PyPI auto-publish unverified until next tag push (consider releasing 0.4.0 with these behavior changes).
CI: Windows runners hit WinError 10048 (ephemeral port exhaustion); fixed by a `netsh ... dynamicport` step in ci.yml (run 41029671000 green on all 8 jobs). Verbose-close test idle timeout widened to 0.3 s.
Random-access upper bounds (read 192/96, write weighted 1920/960, bit 188/94) enforced by wire class; 6,202 tests pass. Review follow-ups (low): parametrize write over-limit tests for all Q-class profiles, fix extra=67 case to reach 255 on iQ-R, add docstring line on limits.

## 2026-10-30 Update (late): #6 and error information

- #6 closed: `--ascii-numbering manual` (hex X/Y/B/W/SB/SW/DX/DY/ZR), default compat.
- Error responses now carry error information (route + command + subcommand) per SH-080008 5.2/5.3; bad_end_code injection strips data and appends it (unanimous ballot). 5,937 tests pass.
- Still open: #5 (blocked: manual does not define locked-gate end code), #2 (zero-point random ops, per-module batch limits unverified), pymcprotocol fork work (needs user scope), PyPI auto-publish (next tag push).

## 2026-10-30 Update (manual cross-check applied)

Sources (kept local in git-ignored `.manual/`; see docs/manual/PROVENANCE.md): SH-080008 rev AB, SH-081257 rev AD. Unanimous ballot (ag, cx, cc) applied via ag: DATA_LENGTH_MISMATCH 0xC061 -> 0xC057; echo payload 0-9/A-F (both cases, case unverified); C200/C201/C202 documented as manual-unsupported. 5,903 tests pass.
Open: #5 remap password end codes to C203/C204; #6 hex ASCII numbering policy for X/Y/B/W; #2 remaining unverified (zero-point random ops, bad_end_code frame shape, batch limits per module); #4 handoff issue; pymcprotocol fork work not started; PyPI auto-publish unexercised (next tag push).
Gotcha: repeated full pytest runs exhaust Windows ephemeral ports (WinError 10048 in client.connect); wait ~2-3 min for TIME_WAIT to drain, then rerun.

## 2026-10-30 Update (ballot + fixes)

Unanimous ballot (ag, cx, cc): fix 3 low-risk server items, defer MC-spec items to issue #2, keep guide.py. Implemented via ag.effort (stream vplc-impl-ag): Server restart/idempotent start/stop, shared `valid_span` (memory.py) for latch ranges, tests/test_server_lifecycle.py. 5,900 tests pass.
Open follow-ups from ballot: pin echo-alnum and STOP mode (1,) with tests; list deferred unverified items in docs/DESIGN.md; document restart semantics (port 0 rebinds a new port).
ag tip: first turn of a fresh ag session returns empty (shell denied); resend with "ONLY file read/edit tools" on the same stream. cx X-7D was 88% on 2026-10-30; avoid until reset.

## 2026-10-30 Update (Gemini review, ag.effort via G pool; stream vplc-gemini-review)

ag needs read-only-tools instruction (shell denied headless) plus `--writable`. Raw findings triaged by cc (verified only where noted):
- Valid, low: server.py start() does not clear `_stopping` (restart unsupported); stop() leaks listener if acceptor never started; Server latch check uses isinstance (bool accepted) vs type() in Memory.
- Wrong/unsupported: MAX_POINT is used (profiles.py:39, tests) so "dead code" is false; echo alnum check likely matches spec (echo data are 0-9/A-F chars), remote STOP mode (1,) likely spec-fixed 0001H. Verify vs manuals (issue #2) before changing.
- Needs manual check: ASCII hex addressing for X/Y/B/W (item 5), bad_end_code frame shape (error frame should carry no data), 0xC061 vs 0xC05C on length mismatch, zero-point random ops, 960-word batch limit.
- Simplification candidates (need consensus): guide.py (343 lines) and GuideParser in __main__.py.
Next: peer ballot (cx/cc) on triage, then TDD fixes for confirmed items.

## 2026-10-23 Update (markitdown fork)

- Fork greatgc-flow/markitdown (upstream=microsoft; local clone D:\Engram1\workspace\markitdown deleted 2026-10-30, re-clone from origin when needed). Our PyPI dist is `markitdown-gc` (0.2.0, packages/markitdown). `markitdown-mcp`/`markitdown-ocr`/sample-plugin are upstream-owned; do not publish.
- PR #9 (ci/release-workflow: tag-triggered release.yml + tests on push to main) MERGED 2026-10-23. GitHub env `pypi` created.
- Existing `tests` workflow has a Windows-ARM job that queues for hours (runner unavailable); PR #9 had no checks run.
- PyPI trusted publishers still to register by user: virtual-plc (VirtualPLC/release.yml/pypi) and markitdown-gc (markitdown/release.yml/pypi).
- Git identity in repos: greatgc-flow <greatgc@gmail.com>.

## Historical baseline (2026-10-23, last edited 2026-10-30)

State: virtual-plc 0.5.0 released (PyPI + GitHub), main clean, CI green, 6,320 local tests pass.
Design: docs/DESIGN.md. Unverified-vs-real-PLC backlog: issue #2.

### Open items (historical)
1. (done 2026-10-30, user-confirmed) PyPI trusted publishers registered and chat-pasted token revoked; first tag push should verify auto-publish.
3. Gemini review done 2026-10-30 (see above); triage pending peer consensus.
4. oracle-watch.yml and the release publish path are unexercised on GitHub.
5. Verify unverified behaviors against manuals (end codes C200/C201, ASCII hex numbering, dword order, etc.).
6. Fork greatgc-flow/pymcprotocol (D:\Engram1\workspace\pymcprotocol; origin=fork, upstream=senrust): feature work not started.

### Working setup (historical)
- peerhub store: `D:\Engram1\.peerhub\core.db` (use `--db`); peers cc, cx, ag. Run `peerhub guide` first.
- cx sandbox has no network/pip; run installs/builds yourself (`.venv` in repo; build with `python -m build --no-isolation`).

### Standing rules (from user memory)
- Reuse peerhub sessions (`--stream`/`--request-id`); unanimous peer consensus for material decisions; "끝장토론" before implementation (TDD/SDD-ready).
- Minimize this terminal's tokens; delegate even small edits. Do NOT fall back to cc when cx/ag are quota-blocked; wait for reset (cc only for short reviews/ballots).
- AI-to-AI/code/docs in English; Korean to the user. Terse terminal output.
- Keep branches/workspace clean; update deps before release; remove over-engineering (github.com/greatgc-flow/VerySimpleGuide); log lessons as GitHub issues.
- Near limits: write handoff + print ONE-line continuation prompt. Never assume unverified facts; ask ambiguities in batches.
