# UDP terminal warning + Health API — integration test plan (2026-11-03)

## Status and decision

**Original preflight (retained as design evidence).** After this plan was
written, the user authorized its next step with `ㄱㄱㄱ`. The separate
[PR #61](https://github.com/greatgc-flow/VirtualPLC/pull/61)
combines #58/#60 source behavior only inside its own reviewable
test branch based on main; neither original PR nor main is merged,
rebased, or altered. This is not permission to merge main or publish. Both
[PR #58](https://github.com/greatgc-flow/VirtualPLC/pull/58) and
[PR #60](https://github.com/greatgc-flow/VirtualPLC/pull/60) are
independent OPEN/UNMERGED proposals from the same main snapshot:
`069af7aa5e192b3b0b2d5040a7d9061135a415`.
Other OPEN/UNMERGED PRs #56, #57 and #59 are not prerequisites to
a synthetic warning/health test. The user currently forbids merging
into `main`, and the branch protection ruleset (#54) remains absent.
The existing PRs each had independent exact-head 9/9 CI; **that is
NOT a combined-code test**.

## Verified source change compatibility

- PR #58 changes only `virtual_plc/server.py` around the UDP
  `recvfrom` `except OSError` near main line 361: unexpected errors
  emit one WARNING with the error, stop-triggered errors remain quiet.
  The worker exits; no automatic retry/rebind.
- PR #60 adds the Python-only
  `Server.get_listener_health()` method near main line 219. It
  uses existing socket/thread registrations, and a nonblocking
  lifecycle-RLock snapshot (after the additional deadlock regression).
  A dead UDP worker with its listener still registered can report
  `started=True`, `healthy=False`,
  `socket_open=True`, `worker_alive=False`.
- Those *runtime hunks* are disjoint. Do not assume the Git merges
  cleanly without checking. Both PRs edit README, BEHAVIOR, DESIGN,
  HANDOFF and dated starter; PR #60 also edits guide.py. Treat these
  as intentional **documentation conflict/reconciliation candidates**,
  preserve both policies, avoid duplicated or contradictory wording.
- No new thread, socket, timer, retry, Windows IOCTL, wire command,
  Network endpoint, CLI setting, or external dependency is proposed.

## Integration test matrix — only after explicit owner authorization

| Scenario | Trigger / synchronization | Required observation |
| --- | --- | --- |
| Unexpected terminal recvfrom (portable) | Inject one `OSError(10054)` into the UDP receive boundary with an actual registered socket/worker and a bounded Event gate | Exactly one warning including 10054; worker terminates; no retry; health eventually `started=True, healthy=False`, per-port `socket_open=True, worker_alive=False` |
| Intentional shutdown | Signal `stop()` while UDP worker is polling/returning from `recvfrom` | No spurious warning; after stop health false/false/empty; no late MC dispatch or reply |
| Mixed transport | One UDP listener fails; TCP sibling remains active | Aggregate health False, affected UDP health False, TCP health True; no automatic socket reopen or sibling client close |
| Nonblocking health during stop | Hold UDP response hook; launch stop; after stop flag set, resume hook which calls `get_listener_health()` | No stop/join/health deadlock; contended snapshot returns false/false/[] immediately; stop completes |
| Manual recovery | Explicit `server.stop(); server.start()`, then send a valid MC UDP read on refreshed address | New socket/worker healthy; complete MC reply. If bound to port 0, actual bound port may change |
| Native Windows 10054 | Reuse #59's actual 127.0.0.1 closed-port / Event-gated response, but execute from the *normal registered Server worker*, not only a standalone observer | Real socket error 10054 on supported Windows; one warning; unhealthy health snapshot; explicit recovery. SKIP with reason if OS suppresses ICMP; never claim simulated errnos are native proof |

### Determinism and no-hang rules

Use `threading.Event` handshakes and bounded `join()`/wait, not sleeps
or unbounded retries. Port 0 and loopback only. Do not access
`Memory` directly concurrently with wire requests. For the portable
terminal-path test, the mocked receive must be attached to a
**registered** UDP worker; a standalone call to `_udp_loop(fake_socket)`
without updating Server registration is **not** proof that
`get_listener_health()` reports the failure. Native Windows test
must observe actual Winsock 10054, not monkeypatched `OSError`.
On a runner that suppresses ICMP, declare this *specific observation*
SKIPPED with reason, never a reproduced behavior.

A health snapshot is not atomic with worker death; retry briefly with
bounded synchronization when observing transitions. The API is a local
best-effort status, not remote MC-response proof or hardware parity.

### Previously discovered critical concurrency issue

On the initial PR #60, `get_listener_health()` used a blocking
`with self._lifecycle_lock`. Existing `stop()` holds that lock
while joining workers. If a response_hook on a worker calls health
after stop begins, both wait forever (lock inversion).
The Event-synchronized test on PR #60 reproduced this in
[RED CI #41586012373](https://github.com/greatgc-flow/VirtualPLC/actions/runs/41586012373):
Ubuntu3.11 7,189 old PASS + 1 expected FAIL and Windows3.13
7,193 PASS + 1 expected FAIL (individual job logs).
The minimal PR #60 fix makes lifecycle lock acquisition nonblocking
and returns conservative unhealthy/empty while another thread
owns that lock. Once the lock is available the normal defensive
snapshot is returned. This is a **best-effort status**; false/empty
during transition does not assert that shutdown completed. Check
exact final PR #60 CI before accepting the correction.

## Release / authorization gate

1. Obtain a new **explicit user instruction** before combining
   unmerged branches, merging anything into `main`, or publishing.
   The current instruction explicitly prohibits merging.
2. After authorization, integrate source changes in a reviewable,
   separately named test branch; resolve docs overlapping changes
   without silently dropping either behavior. Preserve original PR
   evidence, verify base/target SHAs and record a combined diff.
3. Add tests-first on that combined branch; intentionally observe
   RED for any discovered integration contract defect, fix minimally,
   run full exact-head GitHub CI build + 8 OS/Python tests 9/9.
   Separate historical PR CI from actual **combined-head** CI.
4. Do not create `v*` tags or publish to PyPI without separate
   explicit release approval. Never involve real PLCs, factory
   or production networks. Official Mitsubishi manual equivalence
   remains NOT_VERIFIED.
5. GitHub #54 branch/tag rulesets must be applied and verified by
   owner/admin; current `main.protected=false`, rulesets=`[]`.

References: Issue [#13](https://github.com/greatgc-flow/VirtualPLC/issues/13),
[#25](https://github.com/greatgc-flow/VirtualPLC/issues/25)
and [#54](https://github.com/greatgc-flow/VirtualPLC/issues/54).
