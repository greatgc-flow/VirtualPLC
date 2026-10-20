"""Optional deterministic, in-process fault injection for local CIM/EAP tests.

NOT a PLC feature. No socket command, TOML option, remote control, or outbound
connection can configure faults. A plan is supplied explicitly by Python tests
or a local test harness. The default server runs without fault injection.

The plan is consumed, globally, once per *complete routed request frame*, before
MC command processing. Invalid transport headers do not consume a step. Steps
are finite and never repeat; after the last step all requests pass normally.
"""
from __future__ import annotations
from threading import Lock

MAX_STEPS = 256
MAX_DELAY_MS = 500


class FaultPlan:
    """Finite, thread-safe deterministic request sequence, no payload capture.

    Steps: {'action': 'pass'}, {'action': 'disconnect'}, or
           {'action': 'delay', 'delay_ms': 1..500}.
    ``disconnect`` closes before executing any PLC operation. ``delay`` holds
    only the current worker for the requested milliseconds before processing.
    Every input object is copied and validated before use.
    """
    def __init__(self, steps):
        if not isinstance(steps, (tuple, list)) or len(steps) > MAX_STEPS:
            raise ValueError('fault steps must be a bounded list/tuple')
        compiled = []
        for step in steps:
            if not isinstance(step, dict):
                raise ValueError('fault step must be a mapping')
            action = step.get('action')
            if action in ('pass', 'disconnect') and set(step) == {'action'}:
                compiled.append((action, 0))
            elif (action == 'delay' and set(step) == {'action', 'delay_ms'}
                  and type(step['delay_ms']) is int and 1 <= step['delay_ms'] <= MAX_DELAY_MS):
                compiled.append(('delay', step['delay_ms']))
            else:
                raise ValueError('invalid fault action or delay')
        self._steps = tuple(compiled)
        self._cursor = 0
        self._lock = Lock()

    def consume(self):
        """Return (action, delay_ms) atomically; exhausted plans return pass."""
        with self._lock:
            if self._cursor >= len(self._steps):
                return 'pass', 0
            step = self._steps[self._cursor]
            self._cursor += 1
            return step

    def snapshot(self):
        """Non-sensitive structural counters, no packet bytes or client IPs."""
        with self._lock:
            return {'configured': len(self._steps), 'consumed': self._cursor,
                    'remaining': len(self._steps) - self._cursor}
