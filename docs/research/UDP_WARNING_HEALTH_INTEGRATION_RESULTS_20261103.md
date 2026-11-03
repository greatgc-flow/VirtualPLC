# UDP receive-warning + listener-Health integration evidence — 2026-11-03

## Status and provenance

This source-controlled report documents the scope and verification boundary
of independent [PR #61](https://github.com/greatgc-flow/VirtualPLC/pull/61).
**The final exact-head 9-job CI result must be verified separately and
recorded in the PR / issues #13 and #25.** The dated file is not proof
that an as-yet-running workflow completed.

- Unchanged main base: `069af7aa5e192b3b3b0b2d5040a7d9061135a415`.
- [PR #58](https://github.com/greatgc-flow/VirtualPLC/pull/58):
  unexpected UDP terminal recvfrom WARNING, verified standalone head
  `8816d76e8c24cdedd377722aafb87c6e81fdb452`,
  [CI #41471970159](https://github.com/greatgc-flow/VirtualPLC/actions/runs/41471970159) 9/9.
- [PR #60](https://github.com/greatgc-flow/VirtualPLC/pull/60):
  Python-only, nonblocking `get_listener_health()`, verified standalone
  head `f7742a61fe641dbea162ab75136ecf51f49d82ca`,
  [CI #41586576010](https://github.com/greatgc-flow/VirtualPLC/actions/runs/41586576010) 9/9.
- [PR #59](https://github.com/greatgc-flow/VirtualPLC/pull/59):
  independently reproduced genuine native Windows localhost
  UDP `recvfrom` 10054, verified head
  `1f5f000d3dd331594d189e5fd646942e4f3055a8`,
  [CI #41475077193](https://github.com/greatgc-flow/VirtualPLC/actions/runs/41475077193) 9/9.
  This does **not** certify all Windows/endpoint security environments.
- PR #61 uses an isolated main-based test branch. Original PRs #56–#60,
  main and published PyPI package remain unchanged.

## Tests-first RED and minimal composition

Tests-only integration commit
`2f30399ca1f3d69fb6c3cb9737067b73fae3a4d7`,
[Actions #41589977921](https://github.com/greatgc-flow/VirtualPLC/actions/runs/41589977921)
**completed expected FAILURE**:
Ubuntu Python 3.11 prior **7,180 PASS +4 expected integration FAIL
+1 Windows-specific SKIP**. Windows Python 3.13 prior **7,184 PASS
+5 expected integration FAIL**. All new failed cases were consistent
with `get_listener_health()` absent on main and its worker-callback
contract missing. The existing suite remained PASS.

The composition source commit
`89c7d1b8ef147e2101f2e1978cbb3a81e0e405c2`
starts with exact PR #60 tree, includes #60's tests and Health implementation
with the earlier callback/stop deadlock correction,
adds only PR #58's small terminal UDP recvfrom warning hunk to
`virtual_plc/server.py`, and copies #58's independent regression file
unaltered. It also preserves PR #61's test-only integration file.
Overlapping README, BEHAVIOR, DESIGN, guide, HANDOFF, starter and design
plan are reconciled on this branch. No new runtime monitor thread,
lock, IOCTL, socket, retry/rebind, CLI flag or network health endpoint.

## Integration matrix tested on same runtime

`tests/test_udp_warning_health_integration.py` covers:

1. UDP-only registered worker: deterministic synthetic
   `OSError(10054)` yields exactly one server WARNING, no busy retry,
   one dead worker while the real registered UDP socket remains open;
   Health returns `started=True`, aggregate `healthy=False`,
   per-port `socket_open=True`, `worker_alive=False`.
2. Mixed TCP + UDP: the same terminal error makes aggregate unhealthy
   while the TCP sibling retains healthy socket and worker status.
3. Normal `stop()`: no spurious terminal-warning record;
   `get_listener_health()` returns false/false/empty.
4. Event-gated response_hook + concurrent stop: Health must
   return conservative false/false/empty during lifecycle lock
   contention; stop must complete without deadlock.
5. Explicit operator `stop(); start()` and a **real valid MC UDP read**
   on the new loopback ephemeral address restores response.
   Calling `start()` alone on a stale registered port is a no-op.
6. Windows native loopback 10054: a valid MC request from a real
   127.0.0.1 ephemeral UDP client, Event-held response, then closed
   client socket; the **registered Server worker** observes the OS
   socket's genuine `recvfrom` 10054 (no simulated exception),
   exactly one WARNING and unhealthy Health; explicit stop/start
   restores a real valid MC UDP reply. The Windows-only test
   explicitly SKIPs if the host suppresses ICMP; Ubuntu SKIPs
   this Windows-specific observation by design.

All events and joins are bounded. No nonloopback network traffic,
physical PLC, OS firewall manipulation or real production connection.

## Operator policy and limitations

- **WARNING** records the unexpected terminal socket receive error.
- **Health snapshot** is a local best-effort view of socket/thread
  registration and liveness, not a network service / MC reply guarantee.
  During concurrent start/stop, it conservatively reports unhealthy
  false/false/empty rather than block a UDP worker under shutdown.
- No automatic retry of a potentially unusable Winsock UDP socket,
  no response replay (writes could have executed), no dynamic port
  management or availability promise. An embedding operator may
  manually `server.stop(); server.start()` after diagnosis.
- Existing #54 branch protection and v* tag rulesets have not been
  activated (main.protected=false; rulesets=[] at last check).
- No main merge, release tag or PyPI upload, real PLC, factory
  network traffic or Mitsubishi firmware/manual compatibility claim.

References: [Issue #13](https://github.com/greatgc-flow/VirtualPLC/issues/13),
[Issue #25](https://github.com/greatgc-flow/VirtualPLC/issues/25),
and [Microsoft recvfrom](https://learn.microsoft.com/en-us/windows/win32/api/winsock/nf-winsock-recvfrom).
