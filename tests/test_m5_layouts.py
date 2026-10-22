"""Pinned client encoders versus manual-derived M5 payload literals."""

from types import SimpleNamespace

import pymcprotocol
import pytest

from test_m3_m4_client import TRANSPORTS
from test_m3_m4_raw import packet


pytestmark = pytest.mark.unverified
LAYOUTS = [
    ("run", {"clear_mode": 2, "force_exec": True}, 0x1001, "03 00 02 00", b"00030200"),
    ("stop", {}, 0x1002, "01 00", b"0001"),
    ("pause", {"force_exec": True}, 0x1003, "03 00", b"0003"),
    ("latchclear", {}, 0x1005, "01 00", b"0001"),
    ("reset", {}, 0x1006, "01 00", b"0001"),
    ("unlock", {"password": "A1b2"}, 0x1630, "04 00 41 31 62 32", b"0004A1b2"),
    ("lock", {"password": "A1b2"}, 0x1631, "04 00 41 31 62 32", b"0004A1b2"),
]


@pytest.mark.parametrize("frame,wire", TRANSPORTS)
@pytest.mark.parametrize("method,options,command,binary,ascii_payload", LAYOUTS)
def test_actual_client_control_layout(monkeypatch, frame, wire, method, options, command, binary, ascii_payload):
    client = (pymcprotocol.Type4E if frame == "4E" else pymcprotocol.Type3E)()
    client.setaccessopt(commtype=wire)
    if frame == "4E":
        client.set_subheaderserial(0xBEEF)
    sent, timeouts = [], []
    monkeypatch.setattr(client, "_send", sent.append)
    monkeypatch.setattr(client, "_sock", SimpleNamespace(settimeout=timeouts.append), raising=False)
    status_offset = (13 if frame == "4E" else 9) * (2 if wire == "ascii" else 1)
    reply = b"0" * (status_offset + 4) if wire == "ascii" else bytes(status_offset + 2)
    monkeypatch.setattr(client, "_recv", lambda: reply)
    assert getattr(client, f"remote_{method}")(**options) is None
    assert sent == [packet(frame, wire, command, 0, ascii_payload if wire == "ascii" else bytes.fromhex(binary))]
    assert timeouts == ([1] if method == "reset" else [])
