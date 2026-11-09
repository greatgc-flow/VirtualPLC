"""Post-0.6.0 correctness hardening (improvement ballot B1: I1, I2, I6, I9).

All sockets are ephemeral loopback; the cross-connection shutdown race is
driven deterministically with a signalling request lock.
"""

import threading

import pytest

from test_m1_server_raw import device_data, request
from test_slmp_1e import req
from virtual_plc import Memory, Server
from virtual_plc.faults import FaultPlan
from virtual_plc.udp_faults import UdpFaultPlan


class SignallingLock:
    """Wrap the request lock; announce each waiter before it blocks."""

    def __init__(self, inner):
        self.inner = inner
        self.waiting = threading.Event()

    def __enter__(self):
        self.waiting.set()
        self.inner.acquire()
        return self

    def __exit__(self, *exc):
        self.inner.release()


class OneShot:
    def __init__(self, payload):
        self.payload, self.sent = payload, []

    def recv(self, size):
        payload, self.payload = self.payload, b""
        return payload

    def sendall(self, data):
        self.sent.append(data)


@pytest.mark.parametrize("slmp_1e", [False, True])
def test_tcp_request_waiting_on_lock_is_not_dispatched_after_stop(slmp_1e):
    """I1: a decoded write blocked behind another request must not run once stop() is signalled."""
    server = Server(slmp_1e=slmp_1e)
    frame = (req(3, head=0, count=1, payload=b"\x34\x12") if slmp_1e
             else request(0x1401, data=device_data(payload=b"\x34\x12")))
    gate = SignallingLock(server._request_lock)
    server._request_lock = gate
    gate.inner.acquire()  # another connection is mid-dispatch
    worker = threading.Thread(target=server._serve_frames, args=(OneShot(frame), 7))
    try:
        worker.start()
        assert gate.waiting.wait(3), "write must reach the request lock"
        server._stopping.set()
    finally:
        gate.inner.release()
    worker.join(3)
    assert not worker.is_alive()
    assert server.memory.read_words("D", 0, 1) == [0]


@pytest.mark.parametrize("method,values", [
    ("write_words", [123, 1.5]),
    ("write_words", [1, "2"]),
    ("write_bits", [1, 1.0]),
    ("write_bits", [0, None]),
])
@pytest.mark.parametrize("device", ["D", "M", "LTN"])
def test_memory_rejects_non_int_values_without_partial_mutation(method, values, device):
    """I2: writes validate every value's type before storing anything."""
    memory = Memory("iQ-R")
    spec = memory.profile.devices[device]
    if method == "write_bits" and spec.kind != "bit":
        pytest.skip("bit write needs a bit device")
    before = memory.dump()
    with pytest.raises(ValueError):
        getattr(memory, method)(device, 0, values)
    assert memory.dump() == before


def test_memory_keeps_accepting_bools_as_plain_ints():
    memory = Memory("Q")
    memory.write_bits("M", 0, [True, False])
    memory.write_words("D", 0, [True])
    assert memory.dump() == {"M": {"0": [1, 0]}, "D": {"0": [1]}}
    assert all(type(v) is int for runs in memory.dump().values() for vs in runs.values() for v in vs)


@pytest.mark.parametrize("build", [
    lambda: Server(idle_timeout=1e10),
    lambda: Server(idle_timeout=10 ** 400),
    lambda: Server(idle_timeout=float("nan")),
    lambda: FaultPlan([{"action": {"type": "delay", "seconds": 10 ** 400}}]),
    lambda: FaultPlan([{"action": {"type": "delay", "seconds": float("nan")}}]),
    lambda: FaultPlan([{"action": {"type": "delay", "seconds": 1e10}}]),
    lambda: FaultPlan([{"action": {"type": "partial_send", "chunks": [2], "pause": 1e10}}]),
    lambda: UdpFaultPlan([{"action": {"type": "delay", "seconds": 1e10}}]),
])
def test_durations_beyond_platform_timeout_max_are_rejected_at_configuration(build):
    """I6: finite but unsupported waits fail early instead of killing a worker."""
    with pytest.raises(ValueError):
        build()


def test_udp_unexpected_hook_error_counts_rejected():
    """I9: a datagram that gets no reply because of an unexpected error is 'rejected'."""
    import socket
    from test_m3_m4_raw import packet

    calls = []

    def hook(response):
        calls.append(response)
        if len(calls) == 1:
            raise RuntimeError("boom")
        return response

    with Server(listeners=[("udp", 0)], udp_metrics=True, response_hook=hook) as plc:
        _, host, port = plc.addresses[0]
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
            udp.settimeout(2)
            udp.sendto(packet("3E", "binary"), (host, port))
            udp.sendto(packet("3E", "binary"), (host, port))
            udp.recvfrom(8192)
    metrics = plc.get_udp_metrics()  # after stop(): the worker has finished counting
    assert metrics["received"] == 2
    assert metrics["rejected"] == 1
    assert metrics["sent"] == 1


@pytest.mark.parametrize("key", ["+1", " 1", "1 ", "1_0", "\u0661", "-0"])
def test_memory_load_requires_plain_ascii_decimal_addresses(key):
    """M2: snapshot address keys are plain ASCII decimal digits."""
    memory = Memory("Q")
    with pytest.raises(ValueError):
        memory.load({"D": {key: [1]}})
    assert memory.dump() == {}


@pytest.mark.parametrize("device", ["LZ", "LTN"])
def test_native_dword_high_bit_round_trips(device):
    """F10: 0x80000000 native dword survives load/dump and word reads."""
    memory = Memory("iQ-R")
    memory.load({device: {"0": [0x80000000]}})
    assert memory.dump() == {device: {"0": [0x80000000]}}
    assert memory.read_words(device, 0, 2) == [0x0000, 0x8000]


def test_out_of_range_is_exported():
    """F05: README names OutOfRange; it is part of the public package API."""
    import virtual_plc
    from virtual_plc.memory import OutOfRange
    assert "OutOfRange" in virtual_plc.__all__
    assert virtual_plc.OutOfRange is OutOfRange


@pytest.mark.parametrize("slmp_1e", [False, True])
def test_tcp_response_hook_must_return_bytes_like(slmp_1e):
    """M3: TCP validates the hook result like UDP; the bad connection closes cleanly."""
    import socket
    frame = req(1, head=0, count=1) if slmp_1e else request(data=device_data())
    calls = []

    def first_call_invalid(response):
        calls.append(response)
        return 123 if len(calls) == 1 else response

    with Server(slmp_1e=slmp_1e, response_hook=first_call_invalid) as plc:
        with socket.create_connection(plc.address, timeout=2) as client:
            client.settimeout(2)
            client.sendall(frame)
            assert client.recv(64) == b""
        # The same listener keeps serving the next client (public API only).
        with socket.create_connection(plc.address, timeout=2) as client:
            client.settimeout(2)
            client.sendall(frame)
            assert client.recv(64)[:2] in (b"\x81\x00", b"\xd0\x00")  # 1E / 3E normal response
        assert plc.get_listener_health()["healthy"]


def test_1e_ascii_loopback_non_hex_closes_connection():
    """F14: characterization - a non-hex 1E ASCII loopback payload closes the connection."""
    import socket
    with Server(slmp_1e=True) as plc:
        with socket.create_connection(plc.address, timeout=2) as client:
            client.settimeout(2)
            client.sendall(b"16FF000002ZZZZ")
            assert client.recv(64) == b""
        assert plc.get_listener_health()["healthy"]


def test_udp_data_code_mismatch_counts_rejected():
    """F11: characterization - a wrong data code yields no reply and counts as rejected."""
    import socket
    from test_m3_m4_raw import packet
    with Server(listeners=[("udp", 0)], udp_metrics=True, ethernet_model="qj71e71") as plc:
        _, host, port = plc.addresses[0]
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
            udp.settimeout(0.3)
            udp.sendto(packet("3E", "ascii"), (host, port))
            with pytest.raises(socket.timeout):
                udp.recvfrom(8192)
    metrics = plc.get_udp_metrics()
    assert (metrics["received"], metrics["rejected"], metrics["sent"]) == (1, 1, 0)
