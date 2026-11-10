"""UDP-only post-dispatch datagram faults for isolated client tests.

Separate from TCP FaultPlan: no close/reset/partial_send/stream semantics.
The command has run before the reply is dropped, delayed, duplicated,
truncated or corrupted; every action affects delivery of one reply only.
"""
from copy import deepcopy
import ipaddress
import threading

from .faults import _integer, _load_steps, _seconds

# Action type -> (required, optional) parameter names; also drives `virtual-plc guide faults`.
UDP_ACTION_FIELDS = {
    "drop": (set(), set()), "delay": ({"seconds"}, set()),
    "duplicate": (set(), set()), "truncate": ({"n"}, set()),
    "corrupt_header": (set(), {"offset", "xor"}),
}


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
    kind = action.get("type") if isinstance(action, dict) else None
    if not isinstance(kind, str) or kind not in UDP_ACTION_FIELDS:
        raise ValueError("UDP action must be one of: " + ", ".join(UDP_ACTION_FIELDS))
    required, optional = UDP_ACTION_FIELDS[kind]
    if not required <= set(action) or set(action) - required - optional - {"type"}:
        raise ValueError(f"invalid UDP action fields for {kind}")
    if kind == "delay":
        _seconds(action["seconds"])
    elif kind == "truncate":
        _integer(action["n"], 1, 2**63 - 1)  # n=0 would be `drop`; no empty datagrams
    elif kind == "corrupt_header":
        # Same bounds as the TCP action (offsets shared by every 3E/4E response header).
        _integer(action.setdefault("offset", 0), 0, 8)
        _integer(action.setdefault("xor", 1), 1, 255)


def datagrams(response, action):
    """Reply datagrams to send, in order, for one reserved non-drop action (or None)."""
    kind = action["type"] if action is not None else None
    if kind == "duplicate":
        return [response, response]
    if kind == "truncate":
        return [response[:action["n"]]]
    if kind == "corrupt_header" and action["offset"] < len(response):
        changed = bytearray(response)
        changed[action["offset"]] ^= action["xor"]
        return [bytes(changed)]
    return [response]  # delay, no action, or an offset past a short (e.g. 1E) reply


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
