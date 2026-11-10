"""Opt-in per-source-IP UDP token bucket (local simulator protection, #13).

Each peer IP owns a bucket of `requests` tokens that refills continuously at
`requests / per_seconds`; a datagram that finds less than one token is dropped
by the UDP worker before size checks, parsing or the shared request lock.
Buckets are keyed by IP only (a host can open many source ports cheaply) and
shared by every UDP listener of one Server. At most `max_peers` buckets are
kept; the least recently seen peer is evicted and returns with a full bucket.

Drop notes for `-v` logging live in the same buckets (so the same LRU bounds
them): the first drop of a burst is reported, later drops are counted and
summarized at most once per DROP_LOG_INTERVAL seconds per IP.
"""

from collections import OrderedDict
import threading
import time

MAX_TRACKED_PEERS = 1024
MAX_REQUESTS = 1_000_000_000
DROP_LOG_INTERVAL = 10.0
FIRST_DROP = "UDP drop: rate limit exceeded for %s (further drops from this IP are summarized at most every %g s)"
DROP_SUMMARY = "UDP drop: rate limit: %d more datagrams dropped from %s in the last %.1f s"


def validate(value):
    """Return (requests, per_seconds) or raise ValueError naming udp_rate_limit."""
    if not isinstance(value, (tuple, list)) or len(value) != 2:
        raise ValueError("udp_rate_limit must be None or a (requests, per_seconds) pair")
    requests, per_seconds = value
    if type(requests) is not int or not 1 <= requests <= MAX_REQUESTS:
        raise ValueError(f"udp_rate_limit requests must be an integer 1..{MAX_REQUESTS}")
    # Range first (NaN fails it); math.isfinite() would overflow on huge ints.
    if type(per_seconds) not in (int, float) or not 0 < per_seconds <= threading.TIMEOUT_MAX:
        raise ValueError("udp_rate_limit per_seconds must be a number in (0, threading.TIMEOUT_MAX], "
                         f"which is {threading.TIMEOUT_MAX!r} seconds on this platform")
    return requests, float(per_seconds)


class UdpRateLimiter:
    """Thread-safe token buckets keyed by peer IP; its lock is never the request lock."""

    def __init__(self, requests, per_seconds, clock=time.monotonic, max_peers=MAX_TRACKED_PEERS):
        self.requests, self.per_seconds = validate((requests, per_seconds))
        self._clock = clock
        self._max_peers = max_peers
        # ip -> [tokens, last reading, last drop-log reading or None, suppressed drops]
        self._buckets = OrderedDict()
        self._lock = threading.Lock()

    def __len__(self):
        with self._lock:
            return len(self._buckets)

    def allow(self, ip):
        """Take one token for `ip`; False means drop the datagram."""
        return self.admit(ip)[0]

    def admit(self, ip):
        """Return (allowed, note): note is None or a (format, *args) log record to emit."""
        with self._lock:
            now = self._clock()
            bucket = self._buckets.get(ip)
            if bucket is None:
                if len(self._buckets) >= self._max_peers:
                    self._buckets.popitem(last=False)
                bucket = self._buckets[ip] = [float(self.requests), now, None, 0]
            else:
                self._buckets.move_to_end(ip)
                # The clock is read under this lock and is monotonic, so elapsed >= 0.
                # Multiply before dividing: tiny windows saturate, never NaN.
                refill = (now - bucket[1]) * self.requests / self.per_seconds
                bucket[0] = min(float(self.requests), bucket[0] + refill)
                bucket[1] = now
            allowed = bucket[0] >= 1
            if allowed:
                bucket[0] -= 1
            return allowed, self._note(ip, bucket, now, allowed)

    @staticmethod
    def _note(ip, bucket, now, allowed):
        """At most one log note per IP per DROP_LOG_INTERVAL; counts are never lost while tracked."""
        logged_at, suppressed = bucket[2], bucket[3]
        due = logged_at is None or now - logged_at >= DROP_LOG_INTERVAL
        if not allowed:
            suppressed += 1
            if logged_at is not None and suppressed == 1 and due:
                logged_at = None  # quiet for a whole interval: a new burst starts
        if not due or not suppressed:
            bucket[3] = suppressed
            return None
        bucket[2], bucket[3] = now, 0
        if logged_at is None:
            return FIRST_DROP, ip, DROP_LOG_INTERVAL
        return DROP_SUMMARY, suppressed, ip, now - logged_at
