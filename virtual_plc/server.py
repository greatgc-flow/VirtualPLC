"""Bounded threaded loopback TCP server for 3E Binary/MC protocol."""
from __future__ import annotations
import socketserver
import threading
from .memory import Memory
from .protocol import REQUEST_HEADER, MAX_BODY, process, FrameError

MAX_SESSIONS = 24
IDLE_TIMEOUT = 1.1

def read_exact(sock, size):
    data = bytearray()
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise EOFError("connection ended in frame")
        data.extend(chunk)
    return bytes(data)

class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        limiter = self.server.limiter
        if not limiter.acquire(blocking=False):
            return
        try:
            self.request.settimeout(IDLE_TIMEOUT)
            while True:
                try:
                    header = read_exact(self.request, 9)
                    if header[:2] != REQUEST_HEADER:
                        raise FrameError("invalid 3E subheader")
                    body_size = int.from_bytes(header[7:9], "little")
                    if not 12 <= body_size <= MAX_BODY:
                        raise FrameError("invalid frame body size")
                    body = read_exact(self.request, body_size)
                    response = process(header[2:7], body, self.server.memory)
                    self.request.sendall(response)
                except (EOFError, TimeoutError, ConnectionResetError,
                        BrokenPipeError, FrameError, OSError):
                    break
        finally:
            limiter.release()

class Server(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True
    block_on_close = False
    request_queue_size = 32

    def __init__(self, address, *, memory=None):
        host, _ = address
        if host != "127.0.0.1":
            raise ValueError("M1 is local-only: host must be 127.0.0.1")
        self.memory = memory if memory is not None else Memory()
        self.limiter = threading.BoundedSemaphore(MAX_SESSIONS)
        super().__init__(address, Handler)
