"""P3/P5 round 2: dump preflight, empty paths, constructor types, hooks vs faults, nonlocal CLI."""

import os
from pathlib import Path
import stat
import socket
from types import SimpleNamespace

import pytest

import virtual_plc
from virtual_plc import FaultPlan, Server
from virtual_plc import __main__ as cli

from test_m1_server_raw import device_data, request

ROOT = Path(__file__).resolve().parents[1]


class FakeServer:
    """Records construction; never binds."""

    created = []

    def __init__(self, host, port, **kwargs):
        self.host, self.port, self.kwargs = host, port, kwargs
        self.address = (host, 54388)
        self.addresses = []
        self.memory = SimpleNamespace(dump=lambda: {})
        self.ethernet = None
        FakeServer.created.append(self)

    def start(self):
        pass

    def stop(self):
        pass


@pytest.fixture
def fake(monkeypatch):
    FakeServer.created = []

    def interrupt(timeout):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "Server", FakeServer)
    monkeypatch.setattr(cli.threading, "Event", lambda: SimpleNamespace(wait=interrupt))
    return FakeServer


def _exit_code(arguments):
    with pytest.raises(SystemExit) as error:
        cli.main(arguments)
    return error.value.code


# F1: a read-only existing dump target fails before binding (portable).
def test_dump_on_exit_read_only_existing_target_exits_2_before_bind(tmp_path, fake, capsys):
    target = tmp_path / "saved.json"
    target.write_text("previous", encoding="utf-8")
    os.chmod(target, stat.S_IREAD)
    try:
        assert _exit_code(["--port", "0", "--dump-on-exit", str(target)]) == 2
    finally:
        os.chmod(target, stat.S_IREAD | stat.S_IWRITE)
    assert fake.created == []
    err = capsys.readouterr().err.strip()
    assert "--dump-on-exit" in err and err.endswith("; see: virtual-plc guide memory")
    assert target.read_text(encoding="utf-8") == "previous"


# F1: an unwritable directory (e.g. a Windows deny-write ACL) is detected by a real probe.
def test_dump_on_exit_unwritable_directory_exits_2_before_bind(tmp_path, fake, monkeypatch, capsys):
    def denied(*args, **kwargs):
        raise PermissionError(13, "Access is denied")

    monkeypatch.setattr(cli.tempfile, "mkstemp", denied)
    assert _exit_code(["--port", "0", "--dump-on-exit", str(tmp_path / "saved.json")]) == 2
    assert fake.created == []
    assert capsys.readouterr().err.strip().endswith("; see: virtual-plc guide memory")


def test_dump_on_exit_probe_leaves_no_files(tmp_path, fake):
    target = tmp_path / "saved.json"
    assert cli.main(["--port", "0", "--dump-on-exit", str(target)]) == 0
    assert sorted(path.name for path in tmp_path.iterdir()) == ["saved.json"]


# F5: empty file paths are rejected, not silently ignored.
@pytest.mark.parametrize("flag, topic", [
    ("--dump-on-exit", "memory"), ("--init", "memory"), ("--fault-plan", "faults"),
    ("--udp-fault-plan", "faults"), ("--ethernet-config", "ethernet"),
])
def test_empty_file_path_options_exit_2(fake, capsys, flag, topic):
    assert _exit_code(["--port", "0", flag, ""]) == 2
    assert fake.created == []
    err = capsys.readouterr().err.strip()
    assert flag in err and err.endswith(f"; see: virtual-plc guide {topic}")


# F4: wrongly typed constructor values raise ValueError before binding.
@pytest.mark.parametrize("options", [
    {"latch_ranges": [1]}, {"latch_ranges": "D"}, {"memory": "x"}, {"profile": ["Q"]},
    {"initial_state": ["RUN"]}, {"response_hook": 5},
], ids=lambda options: f"{next(iter(options))}={next(iter(options.values()))!r}")
def test_server_constructor_type_errors_are_value_errors(options):
    with pytest.raises(ValueError):
        Server(**options)


def test_server_constructor_accepts_valid_optional_values():
    Server(latch_ranges=None, memory=None, response_hook=None)
    Server(latch_ranges={"D": [(0, 1)]}, response_hook=lambda data: data)


# F2: fault actions versus a response_hook that really changes bytes.
def _hooked(data):
    changed = bytearray(data)
    changed[2] = 0x77
    return bytes(changed)


def _read_all(connection):
    connection.settimeout(3)
    received = bytearray()
    while True:
        try:
            chunk = connection.recv(4096)
        except (ConnectionResetError, ConnectionAbortedError):
            break
        if not chunk:
            break
        received += chunk
    return bytes(received)


@pytest.mark.parametrize("action, expect_hook_byte, expect_length", [
    ({"type": "truncate", "n": 4}, True, 4),
    ({"type": "close_after_response"}, True, 13),
    ({"type": "bad_end_code", "code": 0}, True, 13),
    ({"type": "bad_end_code", "code": 0xC059}, False, 20),
])
def test_fault_actions_and_hook_output(action, expect_hook_byte, expect_length):
    plan = FaultPlan([{"action": action}])
    with Server(port=0, fault_plan=plan, response_hook=_hooked) as server:
        with socket.create_connection(server.address, timeout=3) as connection:
            connection.sendall(request(data=device_data()))
            if action["type"] == "close_after_response":
                data = _read_all(connection)
            else:
                connection.settimeout(3)
                data = b""
                while len(data) < expect_length:
                    chunk = connection.recv(4096)
                    assert chunk
                    data += chunk
    assert len(data) == expect_length
    assert data[2] == (0x77 if expect_hook_byte else 0x00)
    if action.get("code"):
        assert data[9:11] == (0xC059).to_bytes(2, "little")


def test_faults_doc_states_bad_end_code_discards_hook_bytes():
    text = " ".join((ROOT / "docs/FAULTS.md").read_text(encoding="utf-8").split())
    assert "discard" in text and "bad_end_code" in text.split("discard", 1)[0][-300:]
    assert "connection/request counting" not in text


# F10: --allow-nonlocal succeeds via the CLI without binding a real socket.
def test_cli_allow_nonlocal_passes_flag_and_prints_warning(fake, capsys):
    assert cli.main(["--host", "0.0.0.0", "--allow-nonlocal", "--idle-timeout", "1"]) == 0
    (server,) = fake.created
    assert server.host == "0.0.0.0" and server.kwargs["allow_nonlocal"] is True
    assert server.kwargs["idle_timeout"] == 1.0
    err = capsys.readouterr().err
    assert "WARNING: localhost-only simulator" in err


# F7: restart is documented.
def test_behavior_doc_describes_restart():
    text = " ".join((ROOT / "docs/BEHAVIOR.md").read_text(encoding="utf-8").split())
    assert "one lifecycle per instance" not in text
    assert "start()/stop() may repeat" in text


# Closure (a): a connection accepted while stop() is signalled takes no ordinal.
def test_connection_accepted_during_shutdown_takes_no_ordinal():
    server = Server(port=0)
    ordinals = []

    class Connection:
        closed = False

        def setsockopt(self, *args):
            pass

        def settimeout(self, value):
            pass

        def close(self):
            self.closed = True

    admitted, late = Connection(), Connection()

    class ScriptedListener:
        accepted = 0

        def accept(self):
            self.accepted += 1
            if self.accepted == 1:
                return admitted, ("127.0.0.1", 50001)
            server._stopping.set()  # stop() signalled while this peer was being accepted
            return late, ("127.0.0.1", 50002)

    def serve_one(connection, connection_id, ordinal):
        ordinals.append(ordinal)
        with server._clients_lock:
            server._clients.pop(connection, None)

    server._serve = serve_one
    server._accept_loop(ScriptedListener())
    with server._clients_lock:
        assert server._clients == {}
    assert ordinals == [1]
    assert server._fault_connection == 1  # the late peer did not consume ordinal 2
    assert late.closed and not admitted.closed


# Closure (b): a blocking response_hook really blocks stop() until it returns.
def test_blocking_response_hook_delays_stop():
    import threading

    entered, release = threading.Event(), threading.Event()

    def hook(data):
        entered.set()
        release.wait(5)  # bounded so a failing test cannot hang the suite
        return data

    server = Server(port=0, response_hook=hook)
    server.start()
    stopper = threading.Thread(target=server.stop, daemon=True)
    try:
        with socket.create_connection(server.address, timeout=3) as connection:
            connection.sendall(request(data=device_data()))
            assert entered.wait(3)
            stopper.start()
            stopper.join(0.2)
            assert stopper.is_alive()  # stop() waits for the worker running the hook
            release.set()
            stopper.join(3)
            assert not stopper.is_alive()
    finally:
        release.set()
        if not stopper.is_alive() and not stopper.ident:
            server.stop()


# F14b: importlib.metadata helpers are not public package attributes.
def test_package_does_not_leak_metadata_helpers():
    assert not hasattr(virtual_plc, "version")
    assert not hasattr(virtual_plc, "PackageNotFoundError")
    assert isinstance(virtual_plc.__version__, str) and virtual_plc.__version__
    assert "__version__" in virtual_plc.__all__


def test_show_effective_ethernet_also_validates_init_and_dump_paths(tmp_path, capsys):
    """--init loads before Server(): the nonbinding inspection rejects bad inputs too (exit 2)."""
    from virtual_plc import __main__ as cli

    bad = tmp_path / "bad.json"
    bad.write_text('{"D": "bad"}', encoding="utf-8")
    with pytest.raises(SystemExit) as error:
        cli.main(["--ethernet-model", "qj71e71", "--show-effective-ethernet", "--init", str(bad)])
    assert error.value.code == 2
    with pytest.raises(SystemExit) as error:
        cli.main(["--ethernet-model", "qj71e71", "--show-effective-ethernet",
                  "--dump-on-exit", str(tmp_path / "missing" / "x.json")])
    assert error.value.code == 2
