"""TCP server and request lifecycle (M1)."""

import socket
import threading

from .codec import decode_request, encode_response, frame_size
from .commands import dispatch
from .memory import Memory

ACCEPT_POLL = 0.1  # seconds between stop checks of the accept loop


class Server:
    def __init__(self, host="127.0.0.1", port=0, profile="Q", memory=None,
                 response_hook=None, max_points=4096, idle_timeout=2.0):
        self.memory = Memory(profile) if memory is None else memory
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
                    end_code, data = dispatch(request, self.memory, self._max_points)
                response = encode_response(request, end_code, data)
                if self._hook is not None:
                    response = self._hook(response)
                connection.sendall(response)
