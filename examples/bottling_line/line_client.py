"""LineController: the application code that talks to the PLC with pymcprotocol.

This is the "code under test". It is deliberately small, but it shows the three
things every real PLC client needs:

1. one place that turns raw device values into meaningful fields,
2. ``MCProtocolError`` (the PLC said "no") handled differently from a
   socket failure (the PLC said nothing),
3. reconnect-and-retry for transient failures. After a timeout a
   pymcprotocol socket may hold a stale half-reply, so the safe recovery is to
   close the connection and open a new one rather than reuse it.

Only idempotent requests are retried (reads, and writes of absolute values
such as a target count). Never blindly retry an increment, a toggle, or a
one-shot *request bit* like START: if its reply was lost the PLC may already
have acted, so re-sending could start a second run. Those calls raise
LineUnreachable("... outcome unknown ...") and the caller checks status().
"""

from dataclasses import dataclass

from pymcprotocol import Type3E
from pymcprotocol.mcprotocolerror import MCProtocolError, UnsupportedComandError

import plc_map as dev


class LineError(Exception):
    """The PLC rejected a request (carries the MC protocol end code)."""

    def __init__(self, end_code):
        super().__init__("PLC returned end code %s" % end_code)
        self.end_code = end_code


class LineUnreachable(Exception):
    """The PLC could not be reached even after the allowed retries."""


@dataclass(frozen=True)
class LineStatus:
    running: bool
    alarm: bool
    target: int
    count: int
    temperature_c: float


class LineController:
    def __init__(self, host, port, plctype="Q", retries=2, timeout=0.5):
        self.host, self.port, self.plctype = host, port, plctype
        self.retries, self.timeout = retries, timeout
        self.reconnects = 0  # how many times a failure forced a new connection
        self._client = None

    # -- connection handling ------------------------------------------
    def connect(self):
        client = Type3E(plctype=self.plctype)
        client.soc_timeout = self.timeout  # socket timeout in seconds
        client.connect(self.host, self.port)
        self._client = client

    def close(self):
        if self._client is not None:
            try:
                self._client.close()
            finally:
                self._client = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *exc_info):
        self.close()

    def _call(self, name, *args, idempotent=True):
        """Run one client method; reconnect-and-retry socket failures if idempotent."""
        attempts = self.retries + 1 if idempotent else 1
        last_error = None
        for _attempt in range(attempts):
            try:
                if self._client is None:
                    self.connect()
                return getattr(self._client, name)(*args)
            except MCProtocolError as error:
                # The PLC answered with an error: retrying would not help.
                raise LineError(error.errorcode) from error
            except UnsupportedComandError as error:
                # pymcprotocol maps end code 0xC059 to its own exception type.
                raise LineError("0xC059") from error
            except OSError as error:  # includes socket.timeout / TimeoutError
                last_error = error
                self.close()  # drop the possibly desynchronised socket
                if not idempotent:
                    raise LineUnreachable(
                        "%s outcome unknown (the PLC may have acted); check status(): %s"
                        % (name, error)) from error
                self.reconnects += 1
        raise LineUnreachable("PLC unreachable after %d attempts: %s"
                              % (self.retries + 1, last_error))

    # -- application operations ---------------------------------------
    def status(self):
        running, alarm = self._call("batchread_bitunits", dev.RUNNING, 2)
        target, count, temp_x10 = self._call("batchread_wordunits", dev.TARGET_COUNT, 3)
        return LineStatus(bool(running), bool(alarm), target, count, temp_x10 / 10)

    def start(self, target):
        """Set the target (retried if needed), then send the one-shot START request."""
        if not 1 <= target <= 32767:
            raise ValueError("target must be 1..32767")
        self._call("batchwrite_wordunits", dev.TARGET_COUNT, [target])
        self._call("batchwrite_bitunits", dev.START_REQUEST, [1], idempotent=False)

    def stop(self):
        self._call("batchwrite_bitunits", dev.STOP_REQUEST, [1], idempotent=False)
