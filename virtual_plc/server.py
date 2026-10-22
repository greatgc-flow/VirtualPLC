"""TCP server and request lifecycle (M1)."""

import socket
import threading

from .codec import decode_request, encode_response, frame_size
from .commands import CPU_STATES, dispatch
from .memory import Memory
from .profiles import PROFILES

ACCEPT_POLL = 0.1  # seconds between stop checks of the accept loop


class Server:
    def __init__(self, host="127.0.0.1", port=0, profile="Q", memory=None,
                 response_hook=None, max_points=4096, idle_timeout=2.0,
                 initial_state="RUN", latch_ranges=None, password=None):
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
            spans = tuple(tuple(span) for span in spans)
            if any(len(span) != 2 or not all(isinstance(point, int) for point in span)
                   or not device.minimum <= span[0] <= span[1] <= device.maximum for span in spans):
                raise ValueError("invalid latch range")
            self.latch_ranges[name] = spans
        self._password = password
        self.locked = False
        self.last_force = False
        self.reset_count = 0
        self._set_state(initial_state)
        self.address = (host, port)
        self._hook = response_hook
        self._max_points = max_points
        self._idle_timeout = idle_timeout
        self._request_lock = threading.Lock()
        self._clients_lock = threading.Lock()
        self._clients = {}  # connection -> worker thread
        self._stopping = threading.Event()
        self._listener = None
        self._acceptor = None

    def _set_state(self, state):
        self.memory.write_words("SD", 203, [CPU_STATES[state]])
        self.state = state

    def start(self):
        self._listener = socket.create_server(self.address)
        self._listener.settimeout(ACCEPT_POLL)
        self.address = self._listener.getsockname()[:2]
        self._acceptor = threading.Thread(target=self._accept_loop, daemon=True)
        self._acceptor.start()

    def stop(self):
        """Close the listener and every client, then join all workers."""
        self._stopping.set()
        if self._acceptor is None:
            return
        self._acceptor.join()
        self._listener.close()
        with self._clients_lock:
            clients = list(self._clients.items())
        for connection, worker in clients:
            try:
                connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass  # already closed by its worker
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
            worker = threading.Thread(target=self._serve, args=(connection,), daemon=True)
            with self._clients_lock:
                self._clients[connection] = worker
            worker.start()

    def _serve(self, connection):
        with connection:
            try:
                self._serve_frames(connection)
            except (OSError, ValueError):
                pass  # timeout, reset, or malformed framing: drop this client only
            finally:
                with self._clients_lock:
                    del self._clients[connection]

    def _serve_frames(self, connection):
        buffer = bytearray()
        while True:
            chunk = connection.recv(65536)
            if not chunk:
                return
            buffer += chunk
            while (size := frame_size(buffer)) is not None and len(buffer) >= size:
                request = decode_request(bytes(buffer[:size]))
                del buffer[:size]
                with self._request_lock:
                    end_code, data = dispatch(request, self.memory, self._max_points, self)
                response = encode_response(request, end_code, data)
                if self._hook is not None:
                    response = self._hook(response)
                connection.sendall(response)
