"""TCP/UDP server and request lifecycle for local simulation."""

import socket
import ipaddress
import logging
import sys
import threading

from . import faults
from .codec import decode_request, encode_response, frame_size
from .commands import CPU_STATES, dispatch
from .ethernet import EthernetSettings
from .memory import Memory, valid_span
from .one_e import frame_size_1e, dispatch_1e, _command_and_wire
from .udp_faults import UdpFaultPlan
from .udp_rate_limit import UdpRateLimiter, validate as _validate_udp_rate_limit
from .profiles import PROFILES

LOG = logging.getLogger(__name__)

ACCEPT_POLL = 0.1  # seconds between stop checks of the accept/receive loops
MAX_UDP_DATAGRAM = 8192  # one complete MC frame per datagram; bound allocation
IDLE_TIMEOUT = "idle timeout"  # TCP close reason counted as tcp_metrics idle_closed


def _bytes_like(value):
    """True when a response_hook result can be sent as-is (bytes-like)."""
    try:
        memoryview(value)
    except TypeError:
        return False
    return True


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


class NonLoopbackBindError(OSError):
    """A loopback-only Server resolved its host to a non-loopback address."""


class Server:
    """Local MC-protocol PLC simulator; use as a context manager or start()/stop().

    Keyword groups (all optional; bad values raise ValueError before binding):
      endpoints: host, port, listeners=[("tcp"|"udp", port), ...], allow_nonlocal,
        max_clients (concurrent TCP sessions), idle_timeout
      PLC: profile, memory, initial_state, password, latch_ranges, max_points
      wire: ascii_dword_order, ascii_numbering, text_pad, slmp_1e, slmp_1e_run_switch,
        ethernet_model, ethernet_overrides
      test hooks: fault_plan (TCP), udp_fault_plan, response_hook(bytes) -> bytes,
        udp_metrics, tcp_metrics, verbose
      protection: udp_rate_limit=(requests, per_seconds) per source IP
    Hooks must return: stop() joins the workers that run them.
    Usage and a pytest fixture: `virtual-plc guide embed`.
    """

    def __init__(self, host="127.0.0.1", port=0, profile="Q", memory=None,
                 response_hook=None, max_points=None, idle_timeout=None,
                 initial_state="RUN", latch_ranges=None, password=None, fault_plan=None,
                 ascii_dword_order="swapped", text_pad=0x00, ascii_numbering="compat", verbose=False,
                 allow_nonlocal=False, max_clients=64, listeners=None,
                 ethernet_model=None, ethernet_overrides=None, slmp_1e=False,
                 slmp_1e_run_switch="RUN", udp_fault_plan=None, udp_metrics=False,
                 tcp_metrics=False, udp_rate_limit=None):
        if type(port) is not int or not 0 <= port <= 65535:
            raise ValueError("port must be an integer 0..65535")
        if max_points is not None and (type(max_points) is not int or max_points < 1):
            raise ValueError("max_points must be None or an integer >= 1")
        # Range first (NaN fails it); math.isfinite() would overflow on huge ints.
        if idle_timeout is not None and (type(idle_timeout) not in (int, float)
                or not 0 < idle_timeout <= threading.TIMEOUT_MAX):
            raise ValueError("idle_timeout must be None or a number in (0, threading.TIMEOUT_MAX]")
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
        if type(slmp_1e) is not bool:
            raise ValueError("slmp_1e must be a boolean")
        if slmp_1e and (profile != "Q" or ethernet_model is not None or
                       ethernet_overrides is not None or fault_plan is not None):
            raise ValueError("slmp_1e requires synthetic Q profile, without model or TCP fault plan")
        if type(slmp_1e_run_switch) is not str or slmp_1e_run_switch not in ("RUN", "STOP"):
            raise ValueError("slmp_1e_run_switch must be RUN or STOP")
        if slmp_1e_run_switch != "RUN" and not slmp_1e:
            raise ValueError("nondefault 1E RUN switch requires slmp_1e=True")
        if slmp_1e_run_switch == "STOP" and initial_state != "STOP":
            raise ValueError("physical STOP requires initial_state=STOP")
        self.slmp_1e_run_switch = slmp_1e_run_switch
        self.slmp_1e = slmp_1e
        self._allow_nonlocal = allow_nonlocal
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
        if slmp_1e and ascii_numbering == "fx5-octal":
            raise ValueError("slmp_1e ASCII uses X,Y HEX numbering; ascii_numbering=fx5-octal is unsupported")
        self.ascii_numbering = ascii_numbering
        if fault_plan is not None and not isinstance(fault_plan, faults.FaultPlan):
            raise ValueError("fault_plan must be a FaultPlan or None")
        if udp_fault_plan is not None and not isinstance(udp_fault_plan, UdpFaultPlan):
            raise ValueError("udp_fault_plan must be a UdpFaultPlan or None")
        if udp_fault_plan is not None and not any(transport == "udp" for transport, _ in listen_specs):
            raise ValueError("UDP fault plan requires at least one UDP listener")
        if type(udp_metrics) is not bool:
            raise ValueError("udp_metrics must be a boolean")
        if type(tcp_metrics) is not bool:
            raise ValueError("tcp_metrics must be a boolean")
        # Type checks first: membership tests below would raise TypeError/AttributeError.
        if type(profile) is not str:
            raise ValueError("profile must be a string")
        if type(initial_state) is not str:
            raise ValueError("initial_state must be a string")
        if memory is not None and not isinstance(memory, Memory):
            raise ValueError("memory must be a Memory or None")
        if latch_ranges is not None and not isinstance(latch_ranges, dict):
            raise ValueError("latch_ranges must be a dict of device -> [(lo, hi), ...] or None")
        if response_hook is not None and not callable(response_hook):
            raise ValueError("response_hook must be callable or None")
        if udp_rate_limit is not None:
            udp_rate_limit = _validate_udp_rate_limit(udp_rate_limit)
            if not any(transport == "udp" for transport, _ in listen_specs):
                raise ValueError("udp_rate_limit requires at least one UDP listener")
        if udp_metrics and not any(transport == "udp" for transport, _ in listen_specs):
            raise ValueError("udp_metrics requires at least one UDP listener")
        if tcp_metrics and not any(transport == "tcp" for transport, _ in listen_specs):
            raise ValueError("tcp_metrics requires at least one TCP listener")
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
        self._udp_fault_plan = udp_fault_plan
        self._udp_metrics = ({"received": 0, "rejected": 0, "sent": 0,
                              "fault_dropped": 0, "send_errors": 0, "receive_resets": 0,
                              "rate_limited": 0}
                             if udp_metrics else None)
        self._udp_metrics_lock = threading.Lock()
        # Per-instance buckets shared by all UDP listeners, kept across stop/start.
        self._udp_rate_limiter = (UdpRateLimiter(*udp_rate_limit)
                                  if udp_rate_limit is not None else None)
        # Guarded by _clients_lock, the lock that already admits/removes sessions.
        self._tcp_metrics = ({"accepted": 0, "rejected": 0, "idle_closed": 0, "closed": 0}
                             if tcp_metrics else None)
        self._connection_number = 0  # never reset: unique 1E STOP-owner IDs across restarts
        self._fault_connection = 0   # FaultPlan match.connection: admitted TCP sessions since start()
        self._max_points = max_points
        self._max_clients = max_clients
        self._idle_timeout = idle_timeout
        self._lifecycle_lock = threading.RLock()  # serialize same-Server start/stop
        self._request_lock = threading.Lock()
        self._remote_stop_owner = None  # 1E connection ID; orphaned on disconnect
        self._remote_stop_owner_connected = False
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

    def get_1e_remote_control_status(self):
        """Return a request-consistent, read-only 1E STOP owner snapshot.

        Local Python API only, not network authentication. Worker cleanup
        may lag the peer closing its socket; orphaned reflects observed EOF.
        """
        if not self.slmp_1e:
            raise ValueError("get_1e_remote_control_status requires slmp_1e=True")
        with self._request_lock:
            owned = self._remote_stop_owner is not None
            connected = owned and self._remote_stop_owner_connected
            return {
                "cpu_state": self.state,
                "owned": owned,
                "owner_connected": connected,
                "orphaned": owned and not connected,
                "owner_connection_id": self._remote_stop_owner,
            }

    def reset_1e_remote_control(self):
        """Explicit local-only simulator reset of 1E remote STOP ownership.

        Holds the same request lock as all network operations. Deliberately
        leaves CPU in STOP, regardless of initial RUN setting: safe simulator
        policy, NOT a claim about FX5 physical power-cycle behavior. TCP
        disconnect, idle timeout and UDP packets never release ownership.
        """
        if not self.slmp_1e:
            raise ValueError("reset_1e_remote_control requires slmp_1e=True")
        with self._request_lock:
            self._remote_stop_owner = None
            self._remote_stop_owner_connected = False
            self.reset_count += 1
            self.set_state("STOP")

    def get_listener_health(self):
        """Return a read-only snapshot of registered TCP/UDP listener health.

        Local Python diagnostics only: started is True only after a successful
        start() and before stop(). Each listener is healthy when its socket
        file descriptor remains open and its accept/receive worker thread is
        alive; the top-level healthy flag requires started and every registered
        listener healthy. Does not start, rebind, or restart workers. If
        start() or stop() currently holds the lifecycle lock on another
        thread, returns an unstarted snapshot immediately rather than waiting
        behind worker joins.
        """
        if not self._lifecycle_lock.acquire(blocking=False):
            return {"started": False, "healthy": False, "listeners": []}
        try:
            started = (self._listener is not None
                       and not self._stopping.is_set()
                       and bool(self._listeners)
                       and len(self._listeners) == len(self._listener_threads))
            if not started:
                return {"started": False, "healthy": False, "listeners": []}
            entries = []
            for idx, (transport, sock) in enumerate(self._listeners):
                worker = self._listener_threads[idx]
                _, host, port = self.addresses[idx]
                socket_open = sock.fileno() != -1
                worker_alive = worker.is_alive()
                entries.append({
                    "transport": transport,
                    "host": host,
                    "port": port,
                    "socket_open": socket_open,
                    "worker_alive": worker_alive,
                    "healthy": socket_open and worker_alive,
                })
            return {
                "started": True,
                "healthy": all(item["healthy"] for item in entries),
                "listeners": entries,
            }
        finally:
            self._lifecycle_lock.release()

    def get_udp_metrics(self):
        """Return a copy of opt-in UDP datagram counters, or None if disabled.

        Local Python diagnostics only: never exposed over SLMP/MC frames.
        Counts aggregate all UDP listeners of this Server instance and persist
        across stop()/start() cycles so post-run assertions can inspect them.
        """
        if self._udp_metrics is None:
            return None
        with self._udp_metrics_lock:
            return dict(self._udp_metrics)

    def _count_udp(self, key):
        if self._udp_metrics is not None:
            with self._udp_metrics_lock:
                self._udp_metrics[key] += 1

    def get_tcp_metrics(self):
        """Return a copy of opt-in TCP session counters, or None if disabled.

        Local Python diagnostics only: never exposed over SLMP/MC frames.
        Counts aggregate all TCP listeners of this Server instance and persist
        across stop()/start() cycles so post-run assertions can inspect them.
        """
        if self._tcp_metrics is None:
            return None
        with self._clients_lock:
            return dict(self._tcp_metrics)

    def _count_tcp(self, *keys):
        """Caller holds _clients_lock, so snapshots match the session table."""
        if self._tcp_metrics is not None:
            for key in keys:
                self._tcp_metrics[key] += 1

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.stop()

    def _log(self, message, *args):
        if self.verbose:
            LOG.info(message, *args)

    def start(self):
        """Serialize overlapping start/stop calls for this Server instance."""
        with self._lifecycle_lock:
            return self._start_unlocked()

    def _start_unlocked(self):
        if self._listener is not None:
            return
        self._stopping.clear()
        self._fault_connection = 0
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
                # The socket is bound but not yet tracked in 'opened'.
                # A timeout-setup failure must close this socket too;
                # the outer rollback handles previously bound listeners.
                try:
                    listener.settimeout(ACCEPT_POLL)
                except BaseException:
                    listener.close()
                    raise
                opened.append((transport, listener))
                # A name such as "localhost" is resolved by the OS: verify the
                # actual bound address before any worker starts.
                if not self._allow_nonlocal:
                    bound = listener.getsockname()[0]
                    if not is_loopback_host(bound.split("%", 1)[0]):
                        raise NonLoopbackBindError(
                            f"{self._bind_address[0]!r} bound to non-loopback {bound}; "
                            "use a literal loopback host or allow_nonlocal=True")
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
        """Serialize shutdown with pending starts and other stop calls."""
        with self._lifecycle_lock:
            return self._stop_unlocked()

    def _stop_unlocked(self):
        """Close all endpoints and clients, then join listener and client workers."""
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

    def _udp_response(self, packet):
        """Process one complete UDP datagram without socket I/O.

        Returns None for an incomplete/concatenated frame, incompatible
        data-code, or oversized response. Malformed headers raise ValueError,
        which the caller drops. Both wire families retain their own framing
        and dispatcher, sharing one PLC Memory and request lock.

        The response hook runs once, outside the request lock, as before.
        UDP has no authenticated TCP requester/STOP ownership identity.
        """
        size = frame_size_1e(packet) if self.slmp_1e else frame_size(packet)
        if size != len(packet):
            self._log("UDP drop: incomplete or concatenated frame")
            return None

        if self.slmp_1e:
            with self._request_lock:
                # Parsing can overlap with stop(); do not begin a new command
                # after shutdown was signaled while parsing the datagram.
                if self._stopping.is_set():
                    return None
                response = dispatch_1e(packet, self.memory, self._max_points,
                                       control=self, requester=None)
        else:
            request = decode_request(packet)
            if (self.ethernet is not None and
                    request.wire != self.ethernet.values["communication_data_code"]):
                self._log("UDP drop: communication data code mismatch")
                return None
            with self._request_lock:
                if self._stopping.is_set():
                    return None
                end_code, data = dispatch(request, self.memory, self._max_points, self)
            self._log("UDP %s %s command=%04X sub=%04X end=%04X",
                      request.frame, request.wire, request.command,
                      request.subcommand, end_code)
            response = encode_response(request, end_code, data,
                                       ascii_dword_order=self.ascii_dword_order)

        if self._hook is not None:
            response = self._hook(response)
            if not _bytes_like(response):
                raise ValueError("UDP response_hook must return bytes-like data")
        if len(response) > MAX_UDP_DATAGRAM:
            self._log("UDP drop: oversized %sresponse", "1E " if self.slmp_1e else "")
            return None
        return response

    def _udp_loop(self, listener):
        """UDP socket lifecycle: receive, validate, respond, or drop one datagram."""
        resets_logged = False
        while not self._stopping.is_set():
            try:
                # Receive the full OS datagram before enforcing our smaller cap:
                # Winsock raises WSAEMSGSIZE on an undersized recvfrom buffer.
                packet, peer = listener.recvfrom(65535)
            except socket.timeout:
                continue
            except ConnectionResetError as error:
                # Windows reports an earlier reply's ICMP port-unreachable as
                # WSAECONNRESET (10054) on the next recvfrom; the socket stays
                # usable, so keep serving. Warn once per worker, count all.
                self._count_udp("receive_resets")
                if not resets_logged:
                    resets_logged = True
                    LOG.warning("UDP receive reset ignored (e.g. Windows ICMP port unreachable); "
                                "further resets are only counted: %s", error)
                continue
            except OSError as error:
                if not self._stopping.is_set():
                    LOG.warning("UDP receive failed; listener worker stopped: %s", error)
                return
            self._count_udp("received")
            # recvfrom may complete just as stop() closes the listener.
            # Do not dispatch even a fully valid late datagram.
            if self._stopping.is_set():
                return
            # Before any size check or parse: a flood never takes the request lock.
            if self._udp_rate_limiter is not None and not self._udp_rate_limiter.allow(peer[0]):
                self._count_udp("rate_limited")
                self._log("UDP drop: rate limit exceeded for %s", peer[0])
                continue
            if not packet or len(packet) > MAX_UDP_DATAGRAM:
                self._count_udp("rejected")
                self._log("UDP drop: empty or oversized datagram")
                continue
            try:
                response = self._udp_response(packet)
            except ValueError as error:
                self._count_udp("rejected")
                self._log("UDP drop: %s", error)
                continue
            except Exception as error:
                self._count_udp("rejected")  # no reply was produced for this datagram
                print(f"UDP worker: {type(error).__name__}: {error}", file=sys.stderr, flush=True)
                continue
            if self._stopping.is_set():
                continue
            if response is None:
                self._count_udp("rejected")
                continue
            try:
                if self._udp_fault_plan is not None:
                    # Datagram faults act after command dispatch and hook.
                    command = (_command_and_wire(packet)[0] if self.slmp_1e
                               else decode_request(packet).command)
                    action = self._udp_fault_plan.select(command, peer=peer[0])
                    if action is not None:
                        if action["type"] == "drop":
                            self._count_udp("fault_dropped")
                            continue
                        if self._stopping.wait(action["seconds"]):
                            continue  # stop() cancels an outstanding delay
                if not self._stopping.is_set():
                    try:
                        listener.sendto(response, peer)
                    except OSError as error:
                        self._count_udp("send_errors")
                        self._log("UDP drop: %s", error)
                    else:
                        self._count_udp("sent")
            except Exception as error:
                print(f"UDP worker: {type(error).__name__}: {error}", file=sys.stderr, flush=True)

    def _accept_loop(self, listener):
        while not self._stopping.is_set():
            try:
                connection, _ = listener.accept()
            except socket.timeout:
                continue
            except (ConnectionResetError, ConnectionAbortedError) as error:
                # A peer that vanished before accept completed affects only itself.
                self._log("close: TCP accept reset/aborted: %s", error)
                continue
            except OSError as error:
                if not self._stopping.is_set():
                    LOG.warning("TCP accept failed; listener worker stopped: %s", error)
                return
            # An accepted peer may fail socket configuration (e.g. Winsock
            # TCP_NODELAY/timeout errors). Close only that peer; keep this
            # port's accept worker alive for subsequent healthy clients.
            try:
                connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                connection.settimeout(self._idle_timeout)
            except OSError as error:
                try:
                    connection.close()
                except OSError:
                    pass
                self._log("close: accepted TCP socket setup failed: %s", error)
                continue
            with self._clients_lock:
                self._connection_number += 1  # unique for STOP owner, including cross-port TCP
                connection_id = self._connection_number
                rejected = self._stopping.is_set() or len(self._clients) >= self._max_clients
                self._count_tcp("rejected" if rejected else "accepted")
                if not rejected:
                    self._fault_connection += 1  # refused connections take no fault ordinal
                    worker = threading.Thread(target=self._serve, daemon=True,
                                              args=(connection, connection_id, self._fault_connection))
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
                    self._count_tcp("closed")
                connection.close()
                self._log("close: could not start client worker")

    def _serve(self, connection, connection_id, ordinal):
        with connection:
            try:
                reason = self._serve_frames(connection, connection_id, ordinal)
            except Exception as error:
                reason = f"unexpected {type(error).__name__}: {error}"
                print(f"connection worker: {type(error).__name__}: {error}", file=sys.stderr, flush=True)
            finally:
                self._log("close: %s", reason)
                # A disconnected STOP owner is NOT released: mark it orphaned.
                with self._request_lock:
                    if self._remote_stop_owner == connection_id:
                        self._remote_stop_owner_connected = False
                with self._clients_lock:
                    self._clients.pop(connection, None)
                    if reason == IDLE_TIMEOUT:
                        self._count_tcp("idle_closed")
                    self._count_tcp("closed")

    def _serve_frames(self, connection, connection_id, ordinal):
        """connection_id: unique 1E STOP-owner ID; ordinal: FaultPlan match.connection."""
        buffer = bytearray()
        nth = 0
        while not self._stopping.is_set():
            try:
                chunk = connection.recv(65536)
            except socket.timeout:
                return IDLE_TIMEOUT
            except OSError:
                return "receive error/reset"
            if not chunk:
                return "EOF"
            buffer += chunk
            while True:
                # A recv may contain multiple pipelined frames. Stop must
                # not begin dispatching the next frame after shutdown starts.
                # An already executing dispatch still finishes normally.
                if self._stopping.is_set():
                    return "server shutdown"
                try:
                    size = frame_size_1e(buffer) if self.slmp_1e else frame_size(buffer)
                    if size is None or len(buffer) < size:
                        break
                    if self.slmp_1e:
                        packet = bytes(buffer[:size])
                        with self._request_lock:
                            # Another connection may have held the lock while
                            # stop() was signalled: do not start this request.
                            if self._stopping.is_set():
                                return "server shutdown"
                            response = dispatch_1e(packet, self.memory, self._max_points,
                                                   control=self, requester=connection_id)
                    else:
                        request = decode_request(bytes(buffer[:size]))
                except ValueError:
                    return "malformed framing"
                del buffer[:size]
                if self.slmp_1e:
                    if self._hook is not None:
                        response = self._hook(response)
                        if not _bytes_like(response):
                            return "invalid response_hook result"
                    try:
                        connection.sendall(response)
                    except OSError:
                        return "send error/reset"
                    continue
                if self.ethernet is not None and request.wire != self.ethernet.values["communication_data_code"]:
                    return "communication data code mismatch"
                with self._request_lock:
                    if self._stopping.is_set():
                        return "server shutdown"
                    end_code, data = dispatch(request, self.memory, self._max_points, self)
                    action = None
                    if self._fault_plan is not None:
                        nth += 1
                        action = self._fault_plan.select(request.command, nth=nth, connection=ordinal)
                self._log("%s %s command=%04X sub=%04X end=%04X", request.frame, request.wire,
                          request.command, request.subcommand, end_code)
                response = encode_response(request, end_code, data, ascii_dword_order=self.ascii_dword_order)
                if self._hook is not None:
                    response = self._hook(response)
                    if not _bytes_like(response):
                        return "invalid response_hook result"
                try:
                    if action is None:
                        connection.sendall(response)
                    elif not faults.send_fault(connection, response, request, action, self._stopping):
                        return "fault close/shutdown"
                except OSError:
                    return "send error/reset"
        return "server shutdown"
