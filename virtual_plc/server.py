"""Loopback-only, threaded 3E Binary TCP prototype server."""
from __future__ import annotations
import socket
import socketserver
import threading
import time
from .memory import Memory
from .protocol import REQUEST_HEADER,MAX_BODY,process,FrameError

MAX_SESSIONS=16
IDLE_TIMEOUT=1.1
DEFAULT_ROUTE=bytes.fromhex('00 FF FF 03 00')

def read_exact(sock,n,deadline):
    b=bytearray()
    while len(b)<n:
        remaining=deadline-time.monotonic()
        if remaining<=0:raise TimeoutError('frame deadline exceeded')
        sock.settimeout(remaining)
        part=sock.recv(n-len(b))
        if not part:raise EOFError('connection ended mid-frame')
        b.extend(part)
    return bytes(b)

class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        lock=self.server.limiter
        if not lock.acquire(blocking=False):return
        try:
            self.request.settimeout(IDLE_TIMEOUT)
            while True:
                try:
                    deadline=time.monotonic()+IDLE_TIMEOUT
                    first=read_exact(self.request,9,deadline)
                    if first[:2]!=REQUEST_HEADER:raise FrameError('invalid subheader')
                    if first[2:7]!=DEFAULT_ROUTE:raise FrameError('unconfigured station route')
                    body_len=int.from_bytes(first[7:9],'little')
                    if body_len<12 or body_len>MAX_BODY:raise FrameError('invalid body size')
                    body=read_exact(self.request,body_len,deadline)
                    response=process(first[2:7],body,self.server.memory)
                    self.request.sendall(response)
                except (EOFError,TimeoutError,ConnectionResetError,BrokenPipeError,FrameError,OSError):
                    break
        finally:
            lock.release()

class Server(socketserver.ThreadingMixIn,socketserver.TCPServer):
    allow_reuse_address=True
    daemon_threads=True
    block_on_close=False
    request_queue_size=32
    def __init__(self,address,*,memory=None):
        host,_=address
        # Strictly prevent accidental exposure on test or real PLC network.
        if host!='127.0.0.1':raise ValueError('this M1 build only binds 127.0.0.1')
        self.memory=memory or Memory()
        self.limiter=threading.BoundedSemaphore(MAX_SESSIONS)
        super().__init__(address,Handler)
