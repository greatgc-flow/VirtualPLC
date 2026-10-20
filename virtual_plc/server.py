"""Local-only, capacity-limited TCP 3E Binary simulator; never routes to real PLCs."""
from __future__ import annotations
import socket
import socketserver
import struct
import threading
import time
from .memory import Memory
from .protocol import REQUEST_HEADER,MAX_BODY,process,FrameError
from .telemetry import Telemetry

MAX_SESSIONS=16
IDLE_TIMEOUT=1.1
DEFAULT_ROUTE=bytes.fromhex('00 FF FF 03 00')

class CleanEOF(EOFError):
    """Client closed cleanly at a frame boundary."""

def read_exact(sock,n,deadline):
    b=bytearray()
    while len(b)<n:
        remaining=deadline-time.monotonic()
        if remaining<=0:raise TimeoutError('frame deadline exceeded')
        sock.settimeout(remaining)
        part=sock.recv(n-len(b))
        if not part:
            if n==9 and not b:
                raise CleanEOF('closed at next header boundary')
            raise EOFError('connection ended mid-frame')
        b.extend(part)
    return bytes(b)

class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        lock=self.server.limiter
        telemetry=self.server.telemetry
        if not lock.acquire(blocking=False):
            telemetry.record('session_refused')
            return
        session_id = telemetry.new_session()
        try:
            while True:
                try:
                    deadline=time.monotonic()+IDLE_TIMEOUT
                    first=read_exact(self.request,9,deadline)
                    if first[:2]!=REQUEST_HEADER:raise FrameError('invalid subheader')
                    if first[2:7]!=DEFAULT_ROUTE:raise FrameError('unconfigured station route')
                    body_len=int.from_bytes(first[7:9],'little')
                    if body_len<12 or body_len>self.server.max_body:raise FrameError('invalid body size')
                    body=read_exact(self.request,body_len,deadline)
                    response=process(first[2:7],body,self.server.memory)
                    # Fixed, numeric-only metadata. Count only fully decoded requests.
                    cmd=struct.unpack_from('<H',body,2)[0]
                    endcode=struct.unpack_from('<H',response,9)[0]
                    telemetry.record('request_ok' if endcode==0 else 'request_error',
                                     command=cmd, status=endcode, session_id=session_id,
                                     memory_version=self.server.memory.version)
                    self.request.settimeout(IDLE_TIMEOUT)
                    try:
                        self.request.sendall(response)
                    except (TimeoutError, BrokenPipeError, ConnectionResetError, OSError):
                        telemetry.record('send_failure', session_id=session_id)
                        break
                except FrameError:
                    telemetry.record('framing_error')
                    break
                except CleanEOF:
                    break
                except EOFError:
                    telemetry.record('eof_mid_frame')
                    break
                except TimeoutError:
                    telemetry.record('idle_timeout')
                    break
                except (BrokenPipeError,ConnectionResetError):
                    telemetry.record('connection_reset')
                    break
                except OSError:
                    telemetry.record('send_failure', session_id=session_id)
                    break
        finally:
            lock.release()

class Server(socketserver.ThreadingMixIn,socketserver.TCPServer):
    allow_reuse_address=True
    daemon_threads=True
    block_on_close=False
    request_queue_size=32
    def __init__(self,address,*,memory=None,max_body=MAX_BODY,telemetry=None):
        host,_=address
        if host!='127.0.0.1':raise ValueError('this prototype only binds 127.0.0.1')
        if type(max_body) is not int or not 12 <= max_body <= MAX_BODY:
            raise ValueError('invalid max_body setting')
        self.max_body=max_body
        self.memory=memory if memory is not None else Memory()
        if telemetry is not None and not isinstance(telemetry,Telemetry):
            raise TypeError('telemetry must be a Telemetry instance')
        self.telemetry=telemetry if telemetry is not None else Telemetry()
        self.limiter=threading.BoundedSemaphore(MAX_SESSIONS)
        super().__init__(address,Handler)
