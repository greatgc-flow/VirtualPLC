"""TCP server and request lifecycle for local simulation."""

import socket
import logging
import math
import sys
import threading

from . import faults
from .codec import decode_request, encode_response, frame_size
from .commands import CPU_STATES, dispatch
from .memory import Memory, valid_span
from .profiles import PROFILES

LOG = logging.getLogger(__name__)

ACCEPT_POLL = 0.1  # seconds between stop checks of the accept loop


class Server:
    def __init__(self, host="127.0.0.1", port=0, profile="Q", memory=None,
                 response_hook=None, max_points=4096, idle_timeout=None,
                 initial_state="RUN", latch_ranges=None, password=None, fault_plan=None,
                 ascii_dword_order="swapped", text_pad=0x00, verbose=False):
        if type(port) is not int or not 0 <= port <= 65535:
            raise ValueError("port must be an integer 0..65535")
        if type(max_points) is not int or max_points < 1:
            raise ValueError("max_points must be an integer >= 1")
        if idle_timeout is not None and (type(idle_timeout) not in (int, float)
                or not math.isfinite(idle_timeout) or idle_timeout <= 0):
            raise ValueError("idle_timeout must be None or a finite number > 0")
        self.verbose = verbose
        if isinstance(text_pad, str) and len(text_pad) == 1:
            text_pad = ord(text_pad)
        if isinstance(text_pad, bool) or not isinstance(text_pad, int) or not 0 <= text_pad <= 255:
            raise ValueError("text_pad must be an integer 0..255 or a single byte-valued character")
        self.text_pad = text_pad
        if ascii_dword_order not in ("swapped", "client"):
            raise ValueError("ascii_dword_order must be swapped or client")
        self.ascii_dword_order = ascii_dword_order
        if fault_plan is not None and not isinstance(fault_plan, faults.FaultPlan):
            raise ValueError("fault_plan must be a FaultPlan or None")
        if initial_state not in CPU_STATES:
            raise ValueError("initial_state must be RUN, STOP or PAUSE")
        if profile not in PROFILES:
            raise ValueError("unknown profile")
        wire = PROFILES[profile].wire
        if password is not None and (not isinstance(password, str) or not wire.password_min <= len(password) <= wire.password_max
                                     or not password.isascii()):
            raise ValueError("password must be ASCII and within the profile length limits")
        self.memory = Memory(profile) if memory is None else memory
        if self.memory.profile.name != profile:
            raise ValueError("memory profile does not match server profile")
        ranges = self.memory.profile.latch_ranges if latch_ranges is None else latch_ranges
        self.latch_ranges = {}
        for name, spans in ranges.items():
            device = self.memory.profile.devices.get(name)
            if device is None:
                raise ValueError("unknown latch device")
            try:
                spans = tuple(tuple(span) for span in spans)
            except TypeError:
                raise ValueError("invalid latch range")
            if any(not valid_span(device, span) for span in spans):
                raise ValueError("invalid latch range")
            self.latch_ranges[name] = spans
        self.password = password
        self.locked = False
        self.reset_count = 0
        self.set_state(initial_state)
        self._bind_address = (host, port)
        self.address = (host, port)
        self._hook = response_hook
        self._fault_plan = fault_plan
        self._connection_number = 0
        self._max_points = max_points
        self._idle_timeout = idle_timeout
        self._request_lock = threading.Lock()
        self._clients_lock = threading.Lock()
        self._clients = {}  # connection -> worker thread
        self._stopping = threading.Event()
        self._listener = None
        self._acceptor = None

    def set_state(self, state):
        self.memory.write_words("SD", 203, [CPU_STATES[state]])
        self.state = state

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.stop()

    def _log(self, message, *args):
        if self.verbose:
            LOG.info(message, *args)

    def start(self):
        if self._listener is not None:
            return
        self._stopping.clear()
        family = socket.AF_INET6 if ":" in self._bind_address[0] else socket.AF_INET
        self._listener = socket.create_server(self._bind_address, family=family)
        self._listener.settimeout(ACCEPT_POLL)
        self.address = self._listener.getsockname()[:2]
        self._acceptor = threading.Thread(target=self._accept_loop, daemon=True)
        self._acceptor.start()

    def stop(self):
        """Close the listener and every client, then join all workers."""
        self._stopping.set()
        if self._listener is not None:
            self._listener.close()
        if self._acceptor is not None:
            self._acceptor.join()
            self._acceptor = None
        self._listener = None
        with self._clients_lock:
            clients = list(self._clients.items())
        for connection, worker in clients:
            try:
                connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass  # already closed by its worker
            connection.close()
            worker.join()

    def _accept_loop(self):
        while not self._stopping.is_set():
            try:
                connection, _ = self._listener.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            connection.settimeout(self._idle_timeout)
            if self._fault_plan is not None:
                self._connection_number += 1
            worker = threading.Thread(target=self._serve, args=(connection, self._connection_number), daemon=True)
            with self._clients_lock:
                self._clients[connection] = worker
            worker.start()

    def _serve(self, connection, connection_id):
        with connection:
            try:
                reason = self._serve_frames(connection, connection_id)
            except Exception as error:
                reason = f"unexpected {type(error).__name__}: {error}"
                print(f"connection worker: {type(error).__name__}: {error}", file=sys.stderr, flush=True)
            finally:
                self._log("close: %s", reason)
                with self._clients_lock:
                    del self._clients[connection]

    def _serve_frames(self, connection, connection_id):
        buffer = bytearray()
        nth = 0
        while not self._stopping.is_set():
            try:
                chunk = connection.recv(65536)
            except socket.timeout:
                return "idle timeout"
            except OSError:
                return "receive error/reset"
            if not chunk:
                return "EOF"
            buffer += chunk
            while True:
                try:
                    size = frame_size(buffer)
                    if size is None or len(buffer) < size:
                        break
                    request = decode_request(bytes(buffer[:size]))
                except ValueError:
                    return "malformed framing"
                del buffer[:size]
                with self._request_lock:
                    end_code, data = dispatch(request, self.memory, self._max_points, self)
                    action = None
                    if self._fault_plan is not None:
                        nth += 1
                        action = self._fault_plan.select(request.command, nth=nth, connection=connection_id)
                self._log("%s %s command=%04X sub=%04X end=%04X", request.frame, request.wire,
                          request.command, request.subcommand, end_code)
                response = encode_response(request, end_code, data, ascii_dword_order=self.ascii_dword_order)
                if self._hook is not None:
                    response = self._hook(response)
                try:
                    if action is None:
                        connection.sendall(response)
                    elif not faults.send_fault(connection, response, request, action, self._stopping):
                        return "fault close/shutdown"
                except OSError:
                    return "send error/reset"
        return "server shutdown"
