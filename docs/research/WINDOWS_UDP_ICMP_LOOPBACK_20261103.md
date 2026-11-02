# Windows UDP ICMP loopback evidence — 2026-11-03

## Scope, status, source of truth

Issue [#13](https://github.com/greatgc-flow/VirtualPLC/issues/13),
independent [PR #59](https://github.com/greatgc-flow/VirtualPLC/pull/59).
**Research/test only**; no new production retry policy, socket option,
runtime setting, security/network behavior, hardware or vendor claim.
All packets stay on the local IPv4 `127.0.0.1` interface, ephemeral
ports, with one MC 3E read frame and one reply. No raw ICMP socket,
admin firewall changes, SIO_UDP_CONNRESET manipulation or equipment.

Microsoft primary references:
- [recvfrom](https://learn.microsoft.com/en-us/windows/win32/api/winsock/nf-winsock-recvfrom):
  for UDP, WSAECONNRESET/10054 can signal that an earlier send
  produced an ICMP Port Unreachable; closing the socket is advised.
- [Winsock IOCTLs](https://learn.microsoft.com/en-us/windows/win32/winsock/winsock-ioctls):
  SIO_UDP_CONNRESET affects whether the UDP PORT_UNREACHABLE event is
  reported. **Not** set here: changing it would alter semantics and
  could hide useful failures.

## Actual Windows experiment, not injected errno

`tests/test_windows_udp_icmp_loopback.py` creates a real UDP listener
on loopback and calls existing `Server._udp_loop` with a thin forwarding
wrapper that *observes* exceptions thrown by the actual socket.
The response hook uses Event synchronization rather than sleeps:
a genuine client first sends an MC request, then closes its own bound
UDP port before the listener sends the encoded reply. The next native
`recvfrom` can raise 10054; the test asserts that actual code and a
terminated worker. It then calls an explicit `Server.start()` on a
fresh listener and performs a real MC read to confirm recovery.

- Observed [PR CI #41474184069](https://github.com/greatgc-flow/VirtualPLC/actions/runs/41474184069)
  on commit `c730b48db30925d783bbdf07c4b58c0888d7c814`:
  **9/9 completed SUCCESS**; Windows Python 3.10, 3.11, 3.12, 3.13 each
  **7,186 passed, zero skipped**. Thus all four Windows hosted CI
  environments really returned UDP 10054 during the test.
  Ubuntu Python 3.10–3.13 each **7,181 passed, 1 explicit Windows-only
  skip**, not a fake failure or claim that Linux delivers Winsock codes.
  The remaining test asserts explicit manual recovery with injected
  terminal error on both OS families.
- A further real-loopback lifecycle regression tests that a dead
  UDP worker cannot be resurrected merely by calling `start()`
  while its stale listener is still registered. It requires
  `stop()` then `start()`. Final candidate SHA and CI must be
  checked after this regression and documentation are committed.

This demonstrates one documented Windows outcome on the named hosted
CI environments, **not** a universal guarantee for all Windows builds,
Windows Server revisions, firewalls, VPNs or endpoint security tools.
If a runner suppresses ICMP, the Windows-only test marks the native
observation SKIPPED with a reason; it never fabricates an OS error.

## Minimal operational response (current policy)

1. An unexpected UDP receive error is terminal for that listener
   worker. Do not busy-retry an OS socket declared unusable.
2. The independent [PR #58](https://github.com/greatgc-flow/VirtualPLC/pull/58)
   adds a warning for that terminal error, without automatic rebind.
   **PR #58 is not merged to main**: do not claim that warning is
   present in currently shipped/default-main code.
3. For an embedding process, diagnose the warning and perform an
   explicit `server.stop()` followed by `server.start()`; a second
   `start()` alone may be a no-op if the stale listener remains.
4. UDP is connectionless; the write may have executed despite an
   absent reply. A client retry can duplicate a non-idempotent action;
   do not claim exactly-once semantics.

## Deferred alternatives — not implemented

- **Automatic listener rebinding:** would require a bounded attempt
  policy, health/status API, port-0 address refresh, rollback behavior,
  shutdown races, and cross-platform real-socket tests. Not justified
  merely by observing 10054. One independent PLC remains one process.
- **Disabling SIO_UDP_CONNRESET:** would silence an actionable network
  signal and is Windows-only; not enabled or recommended as a universal
  workaround.
- **Per-peer/packet history or automatic replay:** creates privacy,
  state and duplicate-write hazards; explicitly out of scope.
- **Hardware/vendor parity:** not investigated and remains NOT_VERIFIED.

## Non-merge and release boundary

This independent PR #59 builds on main
`069af7aa5e192b3b3b0b2d5040a7d9061135a415`. PRs #56 (IPv6),
#57 (UDP metrics), #58 (warning) and #59 remain OPEN and **UNMERGED**.
No main push for these feature changes, no v* tag or PyPI publish,
no physical PLC or production/factory network access.
Issue #54 GitHub protection rules remain not applied at last check.
