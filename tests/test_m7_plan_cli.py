"""Fault selection/validation and CLI loading use one small JSON schema."""

from concurrent.futures import ThreadPoolExecutor
import json
from types import SimpleNamespace

import pytest


@pytest.fixture
def plan_file(tmp_path):
    return tmp_path / "faults.json"


def plan(steps):
    from virtual_plc.faults import FaultPlan

    return FaultPlan(steps)


def test_ordered_steps_match_command_request_and_connection_and_repeat():
    faults = plan([
        {"match": {"command": "0x0619", "nth": 2, "connection": 1}, "times": 2,
         "action": {"type": "drop"}},
        {"match": {"command": 0x0401}, "action": {"type": "truncate", "n": 1}},
    ])
    assert faults.select(0x0619, nth=1, connection=1) is None
    assert faults.select(0x0619, nth=2, connection=2) is None
    assert faults.select(0x0401, nth=1, connection=2) == {"type": "truncate", "n": 1}
    assert faults.select(0x0401, nth=3, connection=2) is None
    assert faults.select(0x0619, nth=2, connection=1) == {"type": "drop"}
    assert faults.select(0x0619, nth=2, connection=1) == {"type": "drop"}
    assert faults.select(0x0619, nth=2, connection=1) is None


def test_first_matching_step_has_priority_and_copies_configuration():
    steps = [{"action": {"type": "delay", "seconds": 0.01}}, {"action": {"type": "drop"}}]
    faults = plan(steps)
    steps[0]["action"]["seconds"] = 99
    chosen = faults.select(0x0619, nth=1, connection=1)
    assert chosen == {"type": "delay", "seconds": 0.01}
    chosen["type"] = "rst"
    assert faults.select(0x0619, nth=2, connection=1) == {"type": "drop"}
    assert faults.select(0x0619, nth=3, connection=1) is None


def test_atomic_step_reservation_across_threads():
    faults = plan([{"times": 7, "action": {"type": "drop"}}])
    with ThreadPoolExecutor(max_workers=12) as pool:
        choices = list(pool.map(lambda i: faults.select(0x0619, nth=1, connection=i + 1), range(100)))
    assert sum(choice is not None for choice in choices) == 7


def test_partial_send_honors_chunk_sizes_remainder_and_pauses():
    from virtual_plc.faults import send_fault

    pieces, pauses = [], []
    connection = SimpleNamespace(sendall=pieces.append)
    stopping = SimpleNamespace(wait=lambda seconds: pauses.append(seconds) or False)
    action = {"type": "partial_send", "chunks": [1, 2], "pause": 0.01}
    assert send_fault(connection, b"abcdef", SimpleNamespace(frame="3E", wire="binary"), action, stopping)
    assert pieces == [b"a", b"bc", b"def"]
    assert pauses == [0.01, 0.01]


@pytest.mark.parametrize("steps", [
    {}, [{"action": {"type": "unknown"}}], [{"action": {"type": "drop"}, "times": 0}],
    [{"match": {"nth": 0}, "action": {"type": "drop"}}],
    [{"match": {"connection": -1}, "action": {"type": "drop"}}],
    [{"match": {"command": "bogus"}, "action": {"type": "drop"}}],
    [{"match": {"frame": "3E"}, "action": {"type": "drop"}}],
    [{"action": {"type": "delay", "seconds": -1}}],
    [{"action": {"type": "delay", "seconds": float("nan")}}],
    [{"action": {"type": "truncate", "n": -1}}],
    [{"action": {"type": "bad_end_code", "code": 65536}}],
    [{"action": {"type": "corrupt_header", "xor": 0}}],
    [{"action": {"type": "corrupt_header", "offset": 9}}],
    [{"action": {"type": "partial_send", "chunks": [0], "pause": 0}}],
    [{"action": {"type": "partial_send", "chunks": [1], "pause": -1}}],
    [{"action": {"type": "drop", "seconds": 1}}],
    [{"action": {"type": "silent_hold"}, "unexpected": 1}],
])
def test_invalid_plan_fails_before_serving(steps):
    with pytest.raises(ValueError):
        plan(steps)


def test_json_file_and_cli_load_same_schema(plan_file, monkeypatch, capsys):
    from virtual_plc import __main__ as cli
    from virtual_plc.faults import FaultPlan

    path = plan_file
    path.write_text(json.dumps({"steps": [{"match": {"command": "0x0619"}, "action": {"type": "drop"}}]}))
    assert FaultPlan.from_file(path).select(0x0619, nth=1, connection=1) == {"type": "drop"}
    seen = []
    class FakeServer:
        def __init__(self, host, port, *, fault_plan=None, **options):
            self.address = (host, port)
            seen.append(fault_plan)
        def start(self):
            seen.append("start")
        def stop(self):
            seen.append("stop")
    def interrupt(timeout):
        assert timeout == 0.5
        raise KeyboardInterrupt
    monkeypatch.setattr(cli, "Server", FakeServer)
    monkeypatch.setattr(cli.threading, "Event", lambda: SimpleNamespace(wait=interrupt))
    cli.main(["--host", "127.0.0.1", "--port", "0", "--fault-plan", str(path)])
    assert seen[0].select(0x0619, nth=1, connection=1) == {"type": "drop"}
    assert seen[1:] == ["start", "stop"]
    assert "listening on 127.0.0.1:0" in capsys.readouterr().err


@pytest.mark.parametrize("text", ['{"steps":', '{}', '{"steps": [], "extra": true}'])
def test_invalid_cli_file_is_rejected_before_bind(plan_file, monkeypatch, text):
    from virtual_plc import __main__ as cli

    path = plan_file
    path.write_text(text)
    def forbidden(*args, **kwargs):
        pytest.fail("Invalid fault files must not construct a server")
    monkeypatch.setattr(cli, "Server", forbidden)
    with pytest.raises(SystemExit) as error:
        cli.main(["--fault-plan", str(path)])
    assert error.value.code == 2
