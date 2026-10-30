"""Pinned-client error handling, labelled client-misbehaviour, real reset retries."""

import time

from pymcprotocol.mcprotocolerror import MCProtocolError, UnsupportedComandError
import pytest

from test_m3_m4_client import TRANSPORTS, connected
from test_m7_faults_raw import start_fault_server


@pytest.mark.client_misbehaviour
@pytest.mark.parametrize("frame", ["3E", "4E"])
def test_client_misbehaviour_binary_truncation_decodes_as_success(server_factory, frame):
    """client-misbehaviour: missing binary status/data silently decode as zero."""
    server = start_fault_server(server_factory, {"type": "truncate", "n": 1}, match={"command": 0x0401})
    server.memory.write_words("D", 0, [0x1234])
    with connected(server, frame, "binary") as client:
        assert client.batchread_wordunits("D0", 1) == [0]  # Not the stored value.
        assert client.batchread_wordunits("D0", 1) == [0x1234]


@pytest.mark.client_misbehaviour
@pytest.mark.parametrize("frame", ["3E", "4E"])
def test_truncated_ascii_status_raises_instead_of_binary_false_success(server_factory, frame):
    server = start_fault_server(server_factory, {"type": "truncate", "n": 1}, match={"command": 0x0401})
    with connected(server, frame, "ascii") as client:
        with pytest.raises(ValueError):
            client.batchread_wordunits("D0", 1)
        assert client.batchread_wordunits("D0", 1) == [0]


@pytest.mark.client_misbehaviour
@pytest.mark.parametrize("frame,wire", TRANSPORTS)
def test_client_misbehaviour_corrupt_subheader_is_not_validated(server_factory, frame, wire):
    """client-misbehaviour: real client accepts a flipped response subheader."""
    server = start_fault_server(server_factory, {"type": "corrupt_header"})
    with connected(server, frame, wire) as client:
        assert client.echo_test("0A") == (2, "0A")


@pytest.mark.parametrize("frame,wire", TRANSPORTS)
@pytest.mark.parametrize("code,error", [(0xC059, UnsupportedComandError), (0xC05C, MCProtocolError)])
def test_injected_end_codes_raise_real_client_errors(server_factory, frame, wire, code, error):
    server = start_fault_server(server_factory, {"type": "bad_end_code", "code": code})
    with connected(server, frame, wire) as client:
        with pytest.raises(error):
            client.echo_test("0A")
        assert client.echo_test("0A") == (2, "0A")


@pytest.mark.slow
@pytest.mark.parametrize("frame,wire", [("3E", "binary"), ("4E", "ascii")])
@pytest.mark.parametrize("kind", ["silent_hold", "rst"])
def test_real_remote_reset_sleeps_reconnects_same_address_and_stays_usable(server_factory, monkeypatch, frame, wire, kind):
    # Dedicated server/connection; never patch the client's real sleep or receive timeout.
    server = start_fault_server(server_factory, {"type": kind}, match={"command": 0x1006, "connection": 1, "nth": 1},
                                initial_state="STOP")
    with connected(server, frame, wire) as client:
        original_socket = client._sock
        original_connect = client.connect
        targets = []
        def reconnect(host, port):
            targets.append((host, port))
            return original_connect(host, port)
        monkeypatch.setattr(client, "connect", reconnect)
        started = time.monotonic()
        try:
            client.remote_reset()
            elapsed = time.monotonic() - started
            assert elapsed >= (1.8 if kind == "silent_hold" else 0.8)
            assert targets == [server.address]
            assert client._sock is not original_socket
            assert client._sock.gettimeout() == client.soc_timeout
            assert client.echo_test("0A") == (2, "0A")
            assert server.reset_count == 1 and server.state == "STOP"
        finally:
            original_socket.close()
