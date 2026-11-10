"""UDP-only post-dispatch datagram faults for isolated client tests.

Separate from TCP FaultPlan: no close/reset/partial_send/stream semantics.
The command has run before the reply is dropped or delayed.
"""
from copy import deepcopy
import ipaddress
import threading

from .faults import _integer, _load_steps, _seconds


def _validate(step):
    if not isinstance(step, dict) or set(step) - {"match", "times", "action"} or "action" not in step:
        raise ValueError("UDP step requires action and optional match/times")
    match = step.setdefault("match", {})
    if not isinstance(match, dict) or set(match) - {"command", "nth", "peer"}:
        raise ValueError("unknown UDP match fields")
    for key, value in match.items():
        if key == "command":
            if isinstance(value, str):
                value = match[key] = int(value, 0)
            _integer(value, 0, 0xFFFF)
        elif key == "nth":
            _integer(value, 1, 2**63 - 1)
        else:
            if not isinstance(value, str):
                raise ValueError("UDP peer must be a numeric IP address")
            match[key] = str(ipaddress.ip_address(value))
    _integer(step.setdefault("times", 1), 1, 2**63 - 1)
    action = step["action"]
    if not isinstance(action, dict) or action.get("type") not in ("drop", "delay"):
        raise ValueError("UDP action must be drop or delay")
    kind = action["type"]
    if set(action) != ({"type", "seconds"} if kind == "delay" else {"type"}):
        raise ValueError("invalid UDP action fields")
    if kind == "delay":
        _seconds(action["seconds"])


class UdpFaultPlan:
    """Atomic post-dispatch selection across all UDP listeners of a Server.

    Global nth advances only for valid UDP responses when a plan exists.
    Concurrent UDP listener reservations follow acquisition order of this
    plan's lock; times and nth survive restart when the plan is reused.
    """

    def __init__(self, steps):
        if not isinstance(steps, list):
            raise ValueError("UDP fault steps must be a list")
        self._steps = deepcopy(steps)
        for step in self._steps:
            _validate(step)
        self._lock = threading.Lock()
        self._nth = 0

    @classmethod
    def from_file(cls, path):
        return cls(_load_steps(path, "UDP fault file must contain only a steps array"))

    def select(self, command, *, peer):
        """Atomically reserve at most one action per completed UDP response."""
        with self._lock:
            self._nth += 1
            context = {"command": command, "nth": self._nth, "peer": peer}
            for step in self._steps:
                if step["times"] and all(context[key] == value for key, value in step["match"].items()):
                    step["times"] -= 1
                    return deepcopy(step["action"])
        return None
