# VirtualPLC M20 — START HERE

- **Release: HOLD.** Virtual loopback-only simulator, no hardware use.
- GitHub Draft PR #1: https://github.com/greatgc-flow/VirtualPLC/pull/1
- `docs/M20_BACKLOG.md` / `backlog/M20_BACKLOG.json`: 16 external cases moved to deferred, **nonblocking** backlog with dependencies and triggers.
- `docs/M20_PROGRESS.md`: new in-process deterministic disconnect/delay fault injection design and validation.
- `tests/test_m20_fault_plan.py` and `tests/test_m20_backlog.py`: new negative/positive tests.
- `M20_GATES.json`: P0 accounting and HOLD.
- `M20_RUN_SUMMARY.json`: actual local JUnit evidence and file hash list.
- `M21_HANDOFF.md`: next internal objective: reproducible smoke/evidence runner.

No official verified pymcprotocol wheel, native Windows operator run or exact Mitsubishi model manual certification was executed in M20. They stay in backlog and must not obstruct safe internal development.
