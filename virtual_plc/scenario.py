"""In-process test controls, deliberately NOT exposed on any network socket.

All validation precedes the shared-memory mutation. Seed and reset use the same
memory RLock as reads and writes, guaranteeing serialized snapshots under races.
"""
from __future__ import annotations
from .memory import Memory


def seed(memory: Memory, *, D=None, M=None, reset=False):
    """Atomically seed finite D/M maps; optionally zero both banks first.

    D and M are mappings of zero-based device numbers to 16-bit words / bits.
    None means no changes to that bank; {} means an empty update.
    Invalid values, types and indexes reject the *entire* proposed transition.
    """
    if not isinstance(memory, Memory) or type(reset) is not bool:
        raise ValueError('invalid seed target/options')
    d = {} if D is None else D
    m = {} if M is None else M
    if not isinstance(d, dict) or not isinstance(m, dict):
        raise ValueError('seed maps required')
    for updates, capacity, maximum in ((d, len(memory._d), 65535), (m, len(memory._m), 1)):
        for address, value in updates.items():
            if (type(address) is not int or type(value) is not int
                    or not 0 <= address < capacity or not 0 <= value <= maximum):
                raise ValueError('invalid seed address/value')
    with memory._lock:
        if reset:
            memory._d[:] = [0] * len(memory._d)
            memory._m[:] = [0] * len(memory._m)
        for address, value in d.items():
            memory._d[address] = value
        for address, value in m.items():
            memory._m[address] = value
        memory._version += 1
        return memory.snapshot()


def snapshot(memory: Memory):
    return memory.snapshot()


def reset(memory: Memory):
    memory.reset()
    return memory.snapshot()
