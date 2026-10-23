"""Declarative, post-dispatch response faults; no effects until explicitly selected."""

from copy import deepcopy
import json
import math
import os
from pathlib import Path
import socket
import struct
import threading

from .codec import Layout


def _integer(value, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"expected integer in {minimum}..{maximum}")


def _seconds(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError("seconds must be finite and nonnegative")


# Action type -> (required, optional) parameter names; also drives `virtual-plc guide faults`.
ACTION_FIELDS = {
    "delay": ({"seconds"}, set()), "drop": (set(), set()),
    "truncate": ({"n"}, set()), "bad_end_code": ({"code"}, set()),
    "close_before_response": (set(), set()), "close_after_response": (set(), set()),
    "rst": (set(), set()), "silent_hold": (set(), set()),
    "corrupt_header": (set(), {"offset", "xor"}),
    "partial_send": ({"chunks"}, {"pause"}),
}


def _validate(step):
    if not isinstance(step, dict) or set(step) - {"match", "times", "action"} or "action" not in step:
        raise ValueError("a fault step requires action and optional match/times")
    match = step.setdefault("match", {})
    if not isinstance(match, dict) or set(match) - {"command", "nth", "connection"}:
        raise ValueError("unknown match fields")
    for key, value in match.items():
        if key == "command" and isinstance(value, str):
            value = match[key] = int(value, 0)
        _integer(value, 0 if key == "command" else 1, 0xFFFF if key == "command" else 2**63 - 1)
    _integer(step.setdefault("times", 1), 1, 2**63 - 1)
    action = step["action"]
    if not isinstance(action, dict):
        raise ValueError("action must be an object")
    kind = action.get("type")
    if not isinstance(kind, str) or kind not in ACTION_FIELDS:
        raise ValueError("unknown fault action")
    required, optional = ACTION_FIELDS[kind]
    if not required <= set(action) or set(action) - required - optional - {"type"}:
        raise ValueError(f"invalid fields for {kind}")
    if kind == "delay":
        _seconds(action["seconds"])
    elif kind == "truncate":
        _integer(action["n"], 0, 2**63 - 1)
    elif kind == "bad_end_code":
        _integer(action["code"], 0, 0xFFFF)
    elif kind == "corrupt_header":
        # Common to every response header, including the shortest 3E binary header.
        _integer(action.setdefault("offset", 0), 0, 8)
        _integer(action.setdefault("xor", 1), 1, 255)
    elif kind == "partial_send":
        if not isinstance(action["chunks"], list) or not action["chunks"]:
            raise ValueError("chunks must be a nonempty list of positive byte counts")
        for size in action["chunks"]:
            _integer(size, 1, 2**63 - 1)
        _seconds(action.setdefault("pause", 0))


class FaultPlan:
    """First eligible step wins; counts are reserved atomically, never rolled back."""

    def __init__(self, steps):
        if not isinstance(steps, list):
            raise ValueError("steps must be a list")
        self._steps = deepcopy(steps)
        for step in self._steps:
            _validate(step)
        self._lock = threading.Lock()

    @classmethod
    def from_file(cls, path):
        document = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(document, dict) or set(document) != {"steps"}:
            raise ValueError("fault file must contain only a steps array")
        return cls(document["steps"])

    def select(self, command, *, nth, connection):
        context = {"command": command, "nth": nth, "connection": connection}
        with self._lock:
            for step in self._steps:
                if step["times"] and all(context[key] == value for key, value in step["match"].items()):
                    step["times"] -= 1
                    return deepcopy(step["action"])
        return None


def send_fault(connection, response, request, action, stopping):
    """Apply one reserved action. Return False to close; waits cancel on server stop."""
    kind = action["type"]
    if kind == "drop":
        return True
    if kind == "silent_hold":
        stopping.wait()
        return False
    if kind == "close_before_response":
        return False
    if kind == "rst":
        connection.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("hh" if os.name == "nt" else "ii", 1, 0))
        return False  # The worker closes without shutdown, preserving abortive-close semantics.
    if kind == "delay" and stopping.wait(action["seconds"]):
        return False
    if kind == "truncate":
        response = response[:action["n"]]
    elif kind == "bad_end_code":
        layout = Layout(request.frame, request.wire)
        offset = layout.header_size
        response = response[:offset] + layout.number(action["code"], 2) + response[offset + 2 * layout.scale:]
    elif kind == "corrupt_header":
        changed = bytearray(response)
        changed[action["offset"]] ^= action["xor"]
        response = bytes(changed)
    elif kind == "partial_send":
        offset = 0
        for size in action["chunks"] + [len(response)]:
            chunk = response[offset:offset + size]
            if not chunk:
                break
            connection.sendall(chunk)
            offset += len(chunk)
            if offset < len(response) and stopping.wait(action["pause"]):
                return False
        return True
    connection.sendall(response)
    return kind != "close_after_response"
