"""CLI lifecycle and embedding contracts introduced by the hardening audit."""

import json
import logging
from pathlib import Path
import queue
import signal
import socket
import subprocess
import sys
import threading
from types import SimpleNamespace

import pytest
import pymcprotocol

from test_m1_server_raw import device_data, exchange, request


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("options", [
    {"max_points": 0}, {"max_points": -1}, {"max_points": 1.5},
    {"idle_timeout": 0}, {"idle_timeout": -1}, {"idle_timeout": float("nan")},
    {"idle_timeout": float("inf")}, {"port": -1}, {"port": 65536}, {"port": 1.5},
])
def test_invalid_server_configuration(options):
    from virtual_plc.server import Server
    with pytest.raises(ValueError):
        Server(**options)


def test_public_exports_context_and_version():
    import re
    from virtual_plc import Server, Memory, FaultPlan, __version__
    assert __version__ == re.search(r'version = "([^"]+)"', (ROOT / "pyproject.toml").read_text()).group(1)
    memory = Memory()
    memory.write_words("D", 0, [123])
    with Server(memory=memory, fault_plan=FaultPlan([])) as server:
        with socket.create_connection(server.address, timeout=1) as connection:
            assert exchange(connection, request(data=device_data())) == (0, b"{\x00")
    assert server._stopping.is_set()


def test_memory_json_roundtrip_and_invalid_load_is_atomic():
    from virtual_plc.memory import Memory
    memory = Memory("iQ-R")
    data = {"D": {"100": [1, 2, 3]}, "M": {"0": [1, 0, 1]}, "LTN": {"7": [0x12345678, 0xFFFFFFFF]}}
    memory.load(data)
    assert memory.dump() == data
    assert memory.read_words("LTN", 7, 4) == [0x5678, 0x1234, 65535, 65535]
    for invalid in [{"D": {"100": [9]}, "M": {"0": [2]}}, {"BAD": {"0": [1]}}, {"D": {"-1": [1]}}]:
        with pytest.raises(ValueError):
            memory.load(invalid)
        assert memory.dump() == data
    copy = Memory("iQ-R")
    copy.load(json.loads(json.dumps(memory.dump())))
    assert copy.dump() == data


@pytest.mark.parametrize("verbose", [False, True])
def test_verbose_requests_and_close_reasons(server_factory, caplog, verbose):
    with caplog.at_level(logging.INFO, logger="virtual_plc.server"):
        server = server_factory(verbose=verbose, idle_timeout=0.3)
        with socket.create_connection(server.address, timeout=1) as connection:
            assert exchange(connection, request(data=device_data()))[0] == 0
            assert connection.recv(1) == b""
        server.stop()
    assert ("command=0401" in caplog.text) == verbose
    assert ("close: idle timeout" in caplog.text) == verbose


@pytest.mark.parametrize("signal_name", [name for name in ("SIGTERM", "SIGBREAK") if hasattr(signal, name)])
@pytest.mark.parametrize("host", ["127.0.0.2", "localhost", "::1", "0.0.0.0"])
def test_cli_signal_polling_banner_and_local_warning(monkeypatch, capsys, host, signal_name):
    from virtual_plc import __main__ as cli
    stopped = []
    def create(host, port, **options):
        return SimpleNamespace(address=(host, 1234), memory=options.get("memory"),
                               start=lambda: None, stop=lambda: stopped.append(True))
    def wait(timeout):
        assert timeout == 0.5
        number = getattr(signal, signal_name)
        signal.getsignal(number)(number, None)
        return True
    monkeypatch.setattr(cli, "Server", create)
    monkeypatch.setattr(cli.threading, "Event", lambda: SimpleNamespace(wait=wait, set=lambda: None))
    assert cli.main(["--host", host, "--port", "0", "--idle-timeout", "3"]) == 0
    output = capsys.readouterr().err
    assert stopped
    assert ("WARNING" in output) == (host == "0.0.0.0")
    assert "idle_timeout=3" in output and "text_pad=0x00" in output
    assert "ascii_dword_order=swapped" in output and "fault_plan=None" in output


def test_cli_init_limits_latch_and_dump(tmp_path, monkeypatch):
    from virtual_plc import __main__ as cli
    seed, dump = tmp_path / "seed.json", tmp_path / "dump.json"
    seed.write_text('{"D":{"100":[1,2,3]},"M":{"0":[1,0,1]}}')
    seen = []
    def create(host, port, **options):
        seen.append(options)
        return SimpleNamespace(address=(host, port), memory=options["memory"], start=lambda: None, stop=lambda: None)
    def interrupt(timeout):
        assert timeout == 0.5
        raise KeyboardInterrupt
    monkeypatch.setattr(cli, "Server", create)
    monkeypatch.setattr(cli.threading, "Event", lambda: SimpleNamespace(wait=interrupt))
    cli.main(["--init", str(seed), "--dump-on-exit", str(dump), "--limit", "D:0-102",
              "--latch-range", "D:100-101", "--latch-range", "M:0-1"])
    assert json.loads(dump.read_text()) == json.loads(seed.read_text())
    assert seen[0]["latch_ranges"] == {"D": [(100, 101)], "M": [(0, 1)]}
    with pytest.raises(ValueError):
        seen[0]["memory"].write_words("D", 103, [1])


def test_text_pad_converter_has_clear_error(capsys):
    from virtual_plc.__main__ import main
    with pytest.raises(SystemExit) as error:
        main(["--text-pad", "not-a-byte"])
    assert error.value.code == 2
    assert "text pad must be" in capsys.readouterr().err.lower()


def run_cli(*arguments):
    return subprocess.run([sys.executable, "-m", "virtual_plc", *arguments], cwd=ROOT,
                          capture_output=True, text=True, timeout=10)


def test_subprocess_help_version_and_port_in_use():
    from virtual_plc import __version__
    assert run_cli("--help").returncode == 0
    result = run_cli("--version")
    assert result.returncode == 0 and __version__ in result.stdout
    with socket.create_server(("127.0.0.1", 0)) as listener:
        result = run_cli("--port", str(listener.getsockname()[1]))
    assert result.returncode == 1
    assert "cannot listen on 127.0.0.1:" in result.stderr
    assert "Traceback" not in result.stderr


def test_subprocess_live_client_and_termination():
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
    process = subprocess.Popen([sys.executable, "-m", "virtual_plc", "--port", "0"], cwd=ROOT,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=flags)
    lines = queue.Queue()
    reader = threading.Thread(target=lambda: [lines.put(line) for line in process.stderr], daemon=True)
    reader.start()
    client = pymcprotocol.Type3E()
    try:
        banner = lines.get(timeout=8)
        assert banner.startswith("listening on 127.0.0.1:")
        port = int(banner.split(":", 1)[1].split()[0])
        client.connect("127.0.0.1", port)
        client.batchwrite_wordunits("D0", [123, -1])
        assert client.batchread_wordunits("D0", 2) == [123, -1]
        client.close()
        if sys.platform == "win32":
            # TerminateProcess bypasses Python handlers; SIGBREAK needs a console.
            try:
                process.send_signal(signal.CTRL_BREAK_EVENT)
                process.wait(timeout=3)
            except (OSError, subprocess.TimeoutExpired):
                process.terminate()
        else:
            process.terminate()
        process.wait(timeout=5)
        if sys.platform != "win32":
            assert process.returncode == 0
    finally:
        if client._is_connected:
            client.close()
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=5)
        reader.join(timeout=1)


@pytest.mark.parametrize("limits", [{"BAD": (0, 10)}, {"D": None}, {"D": (10, 0)}, {"D": (-1, 3)}])
def test_invalid_memory_limits_are_value_errors(limits):
    from virtual_plc import Memory
    with pytest.raises(ValueError):
        Memory(limits=limits)


@pytest.mark.parametrize("arguments", [["--max-points", "0"], ["--idle-timeout", "0"],
                                      ["--idle-timeout", "nan"], ["--port", "65536"],
                                      ["--limit", "BAD:0-10"], ["--latch-range", "D:2-1"]])
def test_invalid_cli_configuration_is_parser_error_before_start(arguments, monkeypatch):
    from virtual_plc import __main__ as cli
    monkeypatch.setattr(cli.Server, "start", lambda self: pytest.fail("must validate before bind"))
    with pytest.raises(SystemExit) as error:
        cli.main(arguments)
    assert error.value.code == 2



def test_banner_readiness_includes_installed_signal_handlers(monkeypatch):
    from virtual_plc import __main__ as cli
    previous = signal.getsignal(signal.SIGTERM)
    seen = []
    def announce(*args, **kwargs):
        assert signal.getsignal(signal.SIGTERM) is not previous
        seen.append(True)
    def interrupt(timeout):
        raise KeyboardInterrupt
    monkeypatch.setattr(cli, "Server", lambda *a, **kw: SimpleNamespace(
        address=("127.0.0.1", 1234), start=lambda: None, stop=lambda: None))
    monkeypatch.setattr(cli, "print", announce, raising=False)
    monkeypatch.setattr(cli.threading, "Event", lambda: SimpleNamespace(wait=interrupt))
    assert cli.main([]) == 0
    assert seen == [True]
    assert signal.getsignal(signal.SIGTERM) is previous
