"""In-memory, payload-free bounded observability; never logs device values or routes.

Records only fixed event names and validated numerical command/status metadata.
The ring is a diagnostic sample, not a full audit trail. Counters retain all events.
"""
from __future__ import annotations
from collections import Counter, deque
from threading import Lock

EVENTS = frozenset({'request_ok','request_error','framing_error','eof_mid_frame',
                    'idle_timeout','send_failure','connection_reset','session_refused'})

class Telemetry:
    def __init__(self, event_capacity=64):
        if type(event_capacity) is not int or not 1 <= event_capacity <= 256:
            raise ValueError('event capacity must be 1..256')
        self._lock=Lock()
        self._events=deque(maxlen=event_capacity)
        self._counts=Counter()
        self._total=0

    def record(self, event, *, command=None, status=None):
        # Never stringify or retain user-supplied objects/payloads/tags/addresses.
        if type(event) is not str or event not in EVENTS:
            raise ValueError('unrecognized event')
        if command is not None and (type(command) is not int or not 0 <= command <= 65535):
            raise ValueError('invalid command')
        if status is not None and (type(status) is not int or not 0 <= status <= 65535):
            raise ValueError('invalid status')
        sample={'event':event}
        if command is not None: sample['command']=command
        if status is not None: sample['status']=status
        with self._lock:
            self._counts[event]+=1
            self._total+=1
            self._events.append(sample)

    def snapshot(self):
        with self._lock:
            return {'total_events':self._total,'counters':dict(self._counts),
                    'sample':list(self._events),'sample_dropped':max(0,self._total-len(self._events))}
