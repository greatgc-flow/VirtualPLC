"""TCP/UDP server and request lifecycle for local simulation."""

import socket
import ipaddress
import logging
import math
import sys
import threading

from . import faults
from .codec import decode_request, encode_response, frame_size
from .commands import CPU_STATES, dispatch
from .ethernet import EthernetSettings
from .memory import Memory, valid_span
from .profiles import PROFILES

LOG = logging.getLogger(__name__)

ACCEPT_POLL = 0.1  # seconds between stop checks of the accept/receive loops
MAX_UDP_DATAGRAM = 8192  # one complete MC frame per datagram; bound allocation


def is_loopback_host(host):
    """Only literal loopback IPs or localhost are approved for default binds."""
    if not isinstance(host, str):
        return False
    if host.casefold() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


class Server:
    def __init__(self, host="127.0.0.1", port=0, profile="Q", memory=None,
                 response_hook=None, max_points=None, idle_timeout=None,
                 initial_state="RUN", latch_ranges=None, password=None, fault_plan=None,
                 ascii_dword_order="swapped", text_pad=0x00, ascii_numbering="compat", verbose=False,
                 allow_nonlocal=False, max_clients=64, listeners=None,
                 ethernet_model=None, ethernet_overrides=None):
        if type(port) is not int or not 0 <= port <= 65535:
            raise ValueError("port must be an integer 0..65535")
        if max_points is not None and (type(max_points) is not int or max_points < 1):
            raise ValueError("max_points must be None or an integer >= 1")
        if idle_timeout is not None and (type(idle_timeout) not in (int, float)
                or not math.isfinite(idle_timeout) or idle_timeout <= 0):
            raise ValueError("idle_timeout must be None or a finite number > 0")
        if type(allow_nonlocal) is not bool:
            raise ValueError("allow_nonlocal must be a boolean")
        if type(max_clients) is not int or max_clients < 1:
            raise ValueError("max_clients must be a positive integer")
        if listeners is None:
            listen_specs = (("tcp", port),)
        else:
            if not isinstance(listeners, (list, tuple)) or not listeners:
                raise ValueError("listeners must be a nonempty sequence of (tcp|udp, port) pairs")
            if port != 0:
                raise ValueError("port must be 0 when explicit listeners are provided")
            listen_specs = []
            used = set()
            for entry in listeners:
                if not isinstance(entry, (tuple, list)) or len(entry) != 2:
                    raise ValueError("invalid listener: expected (tcp|udp, port)")
                transport, bind_port = entry
                if transport not in ("tcp", "udp") or type(bind_port) is not int or not 0 <= bind_port <= 65535:
                    raise ValueError("invalid listener transport or port")
                key = (transport, bind_port)
                if bind_port and key in used:
                    raise ValueError("duplicate listener transport and port")
                used.add(key)
                listen_specs.append(key)
            listen_specs = tuple(listen_specs)
        if any(transport == "udp" for transport, _ in listen_specs) and fault_plan is not None:
            raise ValueError("UDP listeners do not support TCP fault plans")
        if not is_loopback_host(host):
            if not allow_nonlocal:
                raise ValueError("non-loopback host requires allow_nonlocal=True (CLI: --allow-nonlocal)")
            if idle_timeout is None:
                raise ValueError("non-loopback bind requires an explicit positive idle_timeout")
        self.verbose = verbose
        if isinstance(text_pad, str) and len(text_pad) == 1:
            text_pad = ord(text_pad)
        if isinstance(text_pad, bool) or not isinstance(text_pad, int) or not 0 <= text_pad <= 255:
            raise ValueError("text_pad must be an integer 0..255 or a single byte-valued character")
        self.text_pad = text_pad
        if ascii_dword_order not in ("swapped", "client"):
            raise ValueError("ascii_dword_order must be swapped or client")
        self.ascii_dword_order = ascii_dword_order
        if ascii_numbering not in ("compat", "manual", "fx5-octal"):
            raise ValueError("ascii_numbering must be compat, manual or fx5-octal")
        self.ascii_numbering = ascii_numbering
        if fault_plan is not None and not isinstance(fault_plan, faults.FaultPlan):
            raise ValueError("fault_plan must be a FaultPlan or None")
        if initial_state not in CPU_STATES:
            raise ValueError("initial_state must be RUN, STOP or PAUSE")
        if profile not in PROFILES:
            raise ValueError("unknown profile")
        if ethernet_model is None and ethernet_overrides is not None:
            raise ValueError("ethernet_model required for ethernet_overrides")
        self.ethernet = (EthernetSettings(ethernet_model, ethernet_overrides)
                         if ethernet_model is not None else None)
        if self.ethernet is not None and self.ethernet.profile != profile:
            raise ValueError("ethernet_model profile does not match selected PLC profile")
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
        self._listen_specs = tuple(listen_specs)
        self.addresses = [(transport, host, bind_port) for transport, bind_port in self._listen_specs]
        self.address = (host, self._listen_specs[0][1])
        self._hook = response_hook
        self._fault_plan = fault_plan
        self._connection_number = 0
        self._max_points = max_points
        self._max_clients = max_clients
        self._idle_timeout = idle_timeout
        self._request_lock = threading.Lock()
        self._clients_lock = threading.Lock()
        self._clients = {}  # connection -> worker thread
        self._stopping = threading.Event()
        self._listener = None   # legacy first endpoint, including UDP-only instances
        self._acceptor = None   # legacy first listener thread
        self._listeners = []    # (transport, socket) pairs for every endpoint
        self._listener_threads = []

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
        opened = []
        try:
            # Bind every endpoint before starting any workers (all-or-nothing startup).
            for transport, port in self._listen_specs:
                address = (self._bind_address[0], port)
                if transport == "tcp":
                    listener = socket.create_server(address, family=family)
                else:
                    listener = socket.socket(family, socket.SOCK_DGRAM)
                    try:
                        listener.bind(address)
                    except BaseException:
                        listener.close()
                        raise
                listener.settimeout(ACCEPT_POLL)
                opened.append((transport, listener))
        except BaseException:
            for _, listener in opened:
                listener.close()
            raise

        self._listeners = opened
        self.addresses = [(transport, *listener.getsockname()[:2])
                          for transport, listener in opened]
        self.address = self.addresses[0][1:]
        self._listener = opened[0][1]
        try:
            for transport, listener in opened:
                target = self._accept_loop if transport == "tcp" else self._udp_loop
                worker = threading.Thread(target=target, args=(listener,), daemon=True)
                worker.start()
                self._listener_threads.append(worker)
            self._acceptor = self._listener_threads[0]
        except BaseException:
            self.stop()
            raise

    def stop(self):
        """Close all endpoints and clients, then join every listener and client worker."""
        self._stopping.set()
        listeners = [listener for _, listener in self._listeners]
        if self._listener is not None and self._listener not in listeners:
            listeners.append(self._listener)
        for listener in listeners:
            listener.close()
        threads = list(self._listener_threads)
        if self._acceptor is not None and self._acceptor not in threads:
            threads.append(self._acceptor)
        for worker in threads:
            worker.join()
        self._listener_threads = []
        self._listeners = []
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

    def _udp_loop(self, listener):
        """One exact 3E/4E binary/ASCII request per datagram, sharing the TCP lock."""
        while not self._stopping.is_set():
            try:
                # Receive the full OS datagram before enforcing our smaller cap:
                # Winsock raises WSAEMSGSIZE on an undersized recvfrom buffer.
                packet, peer = listener.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                return
            if not packet or len(packet) > MAX_UDP_DATAGRAM:
                self._log("UDP drop: empty or oversized datagram")
                continue
            try:
                if frame_size(packet) != len(packet):
                    self._log("UDP drop: incomplete or concatenated frame")
                    continue
                request = decode_request(packet)
                if self.ethernet is not None and request.wire != self.ethernet.values["communication_data_code"]:
                    self._log("UDP drop: communication data code mismatch")
                    continue
                with self._request_lock:
                    end_code, data = dispatch(request, self.memory, self._max_points, self)
                self._log("UDP %s %s command=%04X sub=%04X end=%04X",
                          request.frame, request.wire, request.command, request.subcommand, end_code)
                response = encode_response(request, end_code, data,
                                           ascii_dword_order=self.ascii_dword_order)
                if self._hook is not None:
                    response = self._hook(response)
                if len(response) > MAX_UDP_DATAGRAM:
                    self._log("UDP drop: oversized response")
                    continue
                if not self._stopping.is_set():
                    listener.sendto(response, peer)
            except (ValueError, OSError) as error:
                self._log("UDP drop: %s", error)
            except Exception as error:
                print(f"UDP worker: {type(error).__name__}: {error}", file=sys.stderr, flush=True)

    def _accept_loop(self, listener):
        while not self._stopping.is_set():
            try:
                connection, _ = listener.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            connection.settimeout(self._idle_timeout)
            with self._clients_lock:
                if self._fault_plan is not None:
                    self._connection_number += 1
                connection_id = self._connection_number
                rejected = self._stopping.is_set() or len(self._clients) >= self._max_clients
                worker = threading.Thread(target=self._serve, args=(connection, connection_id), daemon=True)
                if not rejected:
                    self._clients[connection] = worker
            if rejected:
                connection.close()
                self._log("close: client limit reached or server stopping")
                continue
            try:
                worker.start()
            except RuntimeError:
                with self._clients_lock:
                    self._clients.pop(connection, None)
                connection.close()
                self._log("close: could not start client worker")

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
                    self._clients.pop(connection, None)

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
                if self.ethernet is not None and request.wire != self.ethernet.values["communication_data_code"]:
                    return "communication data code mismatch"
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
