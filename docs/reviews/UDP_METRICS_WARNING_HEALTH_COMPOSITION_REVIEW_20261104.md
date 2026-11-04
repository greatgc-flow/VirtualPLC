# VirtualPLC PR #62: #57 optional UDP metrics with #61 warning/Health
2026-11-04 | Issue #13 | REVIEW/TEST BRANCH ONLY — NO MAIN MERGE

## Proven inputs
- Main `069af7aa5e192b3b3b0b2d5040a7d9061135a415`, protected=false, rulesets=[] (#54).
- #57 HEAD `a593f3d76aed07bee622f3f8bef94cc34a263693`, prior independent 9/9 #41469614503.
- #61 HEAD `e2971a62dedf1171d853d5aaceb46b6816daee2c`, prior independent 9/9 #41602547921.
- Draft [#62](https://github.com/greatgc-flow/VirtualPLC/pull/62) based on #61, not main; all originals untouched.
- This public file records technical-only findings.

## Actual source overlap and composition
PR57 and PR61 both modify `Server._udp_loop`. Naively replacing #61
with #57 loses its terminal `recvfrom` OSError warning; retaining only
#61 loses opt-in received/rejected/sent/fault_dropped/send_errors
accounting and invalid hook-response handling.
Composition `ef2b4a8021b0afd4237feef7b768087d9c6ee66c`
reuses full #57 server source plus #61's unmodified nonblocking
`get_listener_health()` and its one-shot terminal recv WARNING
branch. Only one UDP worker loop, no new monitoring thread, rebind,
retry, replay, IOCTL, wire API, external dependency or CLI flag.
`udp_metrics=False` allocates no counter storage or lock. Opted-in
metrics lock is independent of lifecycle and request locks.

## TDD evidence and acceptance
- Tests-only HEAD `254c91902ab8a8cc850feb1a775370b71f0242e2`
  includes byte-identical original PR57 `tests/test_udp_metrics.py`
  blob `68484b2738bc045acb6f425474585aa3cdb3c4fd` (20 cases),
  plus two new tests in `tests/test_udp_metrics_warning_health_integration.py`.
- [RED CI #41778576988](https://github.com/greatgc-flow/VirtualPLC/actions/runs/41778576988)
  Ubuntu3.11 job log: 7,198 old PASS, 22 expected FAIL, 1 Windows-only SKIP.
  Every new failure arises from missing metrics API/option on #61;
  check overall workflow and other jobs separately.
- Test one: registered UDP worker handles one valid MC read,
  synthetic recvfrom OSError 10054 => exactly one WARNING, no retry,
  dead worker but open socket/Health unhealthy, metrics received=1/sent=1,
  explicit stop/start restores a real loopback UDP reply (cumulative 2/2).
- Test two: response hook queries counters and Health under concurrent
  stop/join; no lock inversion; canceled response not counted sent/rejected.
- Regression gates: original #57 UDP 20 cases; #61 warning/Health
  including native Windows 10054 where supported; all eight
  Python3.10–3.13 Ubuntu/Windows CI test jobs + wheel must finish
  SUCCESS at one final PR HEAD. Independent PR CI does NOT prove this.

## Invariants
Receive counter increments after *successful* recvfrom even if stop then
blocks dispatch. Timeout or terminal OSError does not count. Invalid
callback results count rejected without breaking later requests;
bytearray/memoryview remain supported. Explicit post-dispatch fault
drop increments fault_dropped, **not rejected**. Send exception/short
send increments send_errors. Counters need not sum to successful
transactions; writes may have committed despite a canceled/lost
response. Terminal receive error warns and terminates the UDP worker,
without a fabricated receive_errors metric or automatic recovery.
Nonblocking Health is a momentary local socket/thread snapshot,
not an MC reachability SLA.

## Status / safety
Documentation commit includes code under test, but final same-SHA
9/9 CI **PENDING**; require a fresh verification before promotion.
Keep original PRs #56–#61 OPEN and their evidence unchanged.
No main merge, tag v*, PyPI, real PLC, factory/nonloopback network,
or claim of Mitsubishi physical compatibility. #54 rules remain
owner/admin pending. 
