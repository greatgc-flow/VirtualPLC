"""Bounded, in-memory replay metadata. No IP address or PLC value is retained.

The seed token is never stored; only its SHA-256 digest is retained. Event
samples are diagnostic and truncated, while aggregate counters are complete.
The request's memory version is a scalar and cannot reconstruct PLC values.
"""
from __future__ import annotations
from collections import Counter, deque
from hashlib import sha256
from threading import Lock
from . import __version__

EVENTS = frozenset({'request_ok','request_error','framing_error','eof_mid_frame',
                    'idle_timeout','send_failure','connection_reset','session_refused'})

class Telemetry:
    def __init__(self, event_capacity=64, *, seed_token=None):
        if type(event_capacity) is not int or not 1 <= event_capacity <= 256:
            raise ValueError('event capacity must be 1..256')
        if seed_token is not None and (type(seed_token) is not bytes or not 1 <= len(seed_token) <= 256):
            raise ValueError('seed token must be 1..256 bytes')
        self._lock = Lock()
        self._events = deque(maxlen=event_capacity)
        self._counts = Counter()
        self._total = 0
        self._next_session = 0
        self._seed_digest = sha256(seed_token).hexdigest() if seed_token is not None else None

    def new_session(self):
        """Return a monotone in-process session ID (not a remote IP/client ID)."""
        with self._lock:
            self._next_session += 1
            return self._next_session

    def record(self, event, *, command=None, status=None, session_id=None, memory_version=None):
        if type(event) is not str or event not in EVENTS:
            raise ValueError('unrecognized event')
        for name, value, maximum in (('command', command, 65535),
                                     ('status', status, 65535),
                                     ('session_id', session_id, 2**63-1),
                                     ('memory_version', memory_version, 2**63-1)):
            if value is not None and (type(value) is not int or not 0 <= value <= maximum):
                raise ValueError('invalid ' + name)
        sample = {'event': event, 'release_version': __version__}
        for name, value in (('command', command), ('status', status),
                            ('session_id', session_id), ('memory_version', memory_version)):
            if value is not None:
                sample[name] = value
        if self._seed_digest is not None:
            sample['seed_sha256'] = self._seed_digest
        with self._lock:
            self._counts[event] += 1
            self._total += 1
            self._events.append(sample)

    def snapshot(self):
        with self._lock:
            return {'total_events': self._total, 'counters': dict(self._counts),
                    'sample': [dict(e) for e in self._events],
                    'sample_dropped': max(0, self._total-len(self._events))}
