"""Standalone loopback-only UDP 3E binary client example contract (#13).

The example is deliberately independent of pymcprotocol and reuses
neither server codec nor raw-request test helper implementation.
"""
import importlib.util
from pathlib import Path
import socket
import subprocess
import sys

import pytest

from virtual_plc import Server, Memory


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "udp_read_d0.py"


def example():
    spec = importlib.util.spec_from_file_location("udp_read_d0_example", EXAMPLE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_udp_example_reads_actual_loopback_word():
    sample = example()
    memory = Memory()
    memory.write_words("D", 0, [0x1234])
    with Server(listeners=[("udp", 0)], memory=memory) as plc:
        assert sample.read_d0(plc.address[1]) == 0x1234


def test_udp_example_reports_actual_port_from_cli():
    memory = Memory()
    memory.write_words("D", 0, [0xABCD])
    with Server(listeners=[("udp", 0)], memory=memory) as plc:
        completed = subprocess.run(
            [sys.executable, str(EXAMPLE), str(plc.address[1])],
            capture_output=True, text=True, timeout=8)
        assert completed.returncode == 0, completed.stderr
        assert completed.stdout.strip() == "D0 = 43981 (0xABCD)"


@pytest.mark.parametrize("response", [
    b"",
    b"\xd0\x00",
    b"\xd4\x00" + b"\x00\xff\xff\x03\x00\x04\x00\x00\x00\x34\x12",
    b"\xd0\x00" + b"\x00\xff\xff\x03\x00\x05\x00\x00\x00\x34\x12",
    b"\xd0\x00" + b"\x00\xff\xff\x03\x00\x04\x00\x00\x00\x34",
    b"\xd0\x00" + b"\x00\xff\xff\x03\x00\x04\x00\x00\x00\x34\x12\x99",
    b"\xd0\x00" + b"\x00\xff\xff\x03\x00\x04\x00\x01\x00\x34\x12",
])
def test_udp_example_rejects_wrong_frame_length_header_and_status(monkeypatch, response):
    sample = example()
    class ScriptedSocket:
        def __enter__(self):
            return self
        def __exit__(self, *_):
            return None
        def settimeout(self, timeout):
            assert timeout > 0
        def sendto(self, request, target):
            assert target[0] == "127.0.0.1"
            assert request.startswith(b"\x50\x00")
        def recvfrom(self, n):
            assert n == 8192
            return response, ("127.0.0.1", 5000)
    monkeypatch.setattr(sample.socket, "socket", lambda *a: ScriptedSocket())
    with pytest.raises(ValueError):
        sample.read_d0(5000)


def test_udp_example_rejects_reply_from_unrelated_sender(monkeypatch):
    sample = example()
    valid = b"\xd0\x00\x00\xff\xff\x03\x00\x04\x00\x00\x00\x34\x12"
    class FakeSocket:
        def __enter__(self): return self
        def __exit__(self, *_): return None
        def settimeout(self, timeout): pass
        def sendto(self, frame, target): pass
        def recvfrom(self, n): return valid, ("127.0.0.2", 5000)
    monkeypatch.setattr(sample.socket, "socket", lambda *a: FakeSocket())
    with pytest.raises(ValueError, match="source"):
        sample.read_d0(5000)


@pytest.mark.parametrize("kwargs", [
    {"port": 0}, {"port": -1}, {"port": True}, {"port": 65536},
    {"port": "5000"}, {"port": 5000, "host": "0.0.0.0"},
    {"port": 5000, "host": "192.168.1.2"},
    {"port": 5000, "host": "localhost"},
    {"port": 5000, "timeout": 0},
    {"port": 5000, "timeout": float("inf")},
    {"port": 5000, "timeout": True},
])
def test_udp_example_is_fail_closed_loopback_only(kwargs):
    sample = example()
    with pytest.raises(ValueError):
        sample.read_d0(**kwargs)
