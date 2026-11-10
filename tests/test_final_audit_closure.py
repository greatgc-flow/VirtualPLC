"""Final whole-product audit of v0.11.1: six minor findings closed in 0.11.2."""

import json
import os
from pathlib import Path
import socket
import subprocess
import sys

import pytest

from virtual_plc import FaultPlan, Memory, Server, UdpFaultPlan, guide, oracle
from virtual_plc import __main__ as cli

from test_m1_server_raw import receive_exact
from test_m3_m4_raw import packet


ROOT = Path(__file__).resolve().parents[1]
DEEP = "[" * 200000  # parser stack overflow -> RecursionError in json.loads


# F1: stdout bytes are the report bytes (text-mode stdout would add CR on Windows).
def test_oracle_stdout_bytes_equal_report_bytes_in_a_subprocess(tmp_path):
    catalog = oracle.catalog()
    evidence = {
        "schema": "virtualplc.oracle.observations.v1", "origin": "simulator",
        "target": {"model": "VirtualPLC", "interface": "synthetic-1e", "firmware": "unverified"},
        "records": [{"case_id": item["id"], "request_hex": item["request_hex"],
                     "response_hex": item["expected_hex"]} for item in catalog["cases"]],
    }
    evidence_path = tmp_path / "observations.json"
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    report_path = tmp_path / "report.json"
    environment = dict(os.environ, PYTHONPATH=str(ROOT))
    completed = subprocess.run(
        [sys.executable, "-m", "virtual_plc.oracle", "compare", str(evidence_path), "--report", str(report_path)],
        capture_output=True, env=environment, cwd=str(tmp_path), timeout=60)
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == report_path.read_bytes()
    assert b"\r" not in completed.stdout


# F2: deeply nested JSON is invalid input, not an uncaught RecursionError.
@pytest.mark.parametrize("option, extra, topic", [
    ("--init", [], "memory"),
    ("--fault-plan", [], "faults"),
    ("--udp-fault-plan", ["--listen", "udp:0"], "faults"),
    ("--ethernet-config", ["--ethernet-model", "qj71e71"], "ethernet"),
])
def test_cli_deeply_nested_json_exits_2_with_one_line_hint(tmp_path, capsys, option, extra, topic):
    path = tmp_path / "deep.json"
    path.write_text(DEEP, encoding="utf-8")
    with pytest.raises(SystemExit) as error:
        cli.main([*extra, option, str(path)])
    assert error.value.code == 2
    lines = capsys.readouterr().err.strip().splitlines()
    assert len(lines) == 1
    assert "nesting" in lines[0]
    assert lines[0].endswith(f"; see: virtual-plc guide {topic}")


@pytest.mark.parametrize("plan_type", [FaultPlan, UdpFaultPlan])
def test_parseable_but_deep_plan_raises_value_error(tmp_path, plan_type):
    depth = 5000  # json parses it; copying the steps would overflow the stack
    with pytest.raises(ValueError, match="nesting"):
        plan_type([json.loads("[" * depth + "]" * depth)])
    path = tmp_path / "plan.json"
    path.write_text('{"steps": [' + "[" * depth + "]" * depth + "]}", encoding="utf-8")
    with pytest.raises(ValueError, match="nesting"):
        plan_type.from_file(path)


def test_oracle_deeply_nested_json_is_invalid_input_not_mismatch(tmp_path, capsys):
    path = tmp_path / "deep.json"
    path.write_text(DEEP, encoding="utf-8")
    report = tmp_path / "report.json"
    report.write_text('{"safe":true}\n', encoding="utf-8")
    assert oracle.main(["compare", str(path), "--report", str(report)]) == 2
    out = capsys.readouterr()
    assert not out.out
    assert out.err.startswith("physical-oracle: invalid evidence or report: ")
    assert "nesting" in out.err and len(out.err.strip().splitlines()) == 1
    assert report.read_text(encoding="utf-8") == '{"safe":true}\n'


# F3: bad Memory/Server values raise ValueError, as guide embed documents.
def test_memory_unknown_profile_is_value_error():
    with pytest.raises(ValueError, match="unknown profile"):
        Memory("bogus")
    with pytest.raises(ValueError, match="unknown profile"):
        Memory(profile=["Q"])


@pytest.mark.parametrize("limits", ["D", [("D", (0, 9))], 5])
def test_memory_limits_must_be_a_dict(limits):
    with pytest.raises(ValueError, match="limits must be a dict"):
        Memory(limits=limits)


@pytest.mark.parametrize("state", ["run", "", None, ["RUN"], 1])
def test_set_state_rejects_unknown_state_with_value_error(state):
    server = Server()
    with pytest.raises(ValueError, match="state must be RUN, STOP or PAUSE"):
        server.set_state(state)
    assert server.state == "RUN"
    server.set_state("STOP")
    assert server.state == "STOP"


# F4: UdpFaultPlan.from_file is documented like FaultPlan.from_file.
def test_udp_fault_plan_from_file_is_documented(parser):
    assert "UdpFaultPlan.from_file(path)" in (ROOT / "docs" / "FAULTS.md").read_text(encoding="utf-8")
    assert "UdpFaultPlan.from_file(path)" in guide.render(parser, "embed")


# F5: TCP corrupt_header past a short (hook-shortened) reply sends it unchanged.
def test_tcp_corrupt_header_offset_beyond_short_reply_sends_unchanged():
    plan = FaultPlan([{"action": {"type": "corrupt_header", "offset": 8}}])
    with Server(response_hook=lambda response: b"ab", fault_plan=plan) as server:
        with socket.create_connection(server.address, timeout=2) as connection:
            for _ in range(2):  # the connection survives the faulted reply
                connection.sendall(packet("3E", "binary"))
                assert receive_exact(connection, 2) == b"ab"


def test_faults_doc_states_tcp_short_reply_corrupt_header_rule():
    text = " ".join((ROOT / "docs" / "FAULTS.md").read_text(encoding="utf-8").split())
    assert "TCP response shorter than offset+1 bytes" in text


# F6 / troubleshoot: 1E orphaned STOP owner recovery is discoverable.
def test_troubleshoot_explains_orphaned_1e_stop_owner(parser):
    text = guide.render(parser, "troubleshoot")
    assert "orphaned" in text and "restart" in text


@pytest.fixture
def parser():
    return cli.build_parser()


@pytest.mark.parametrize("command", ["plan", "template"])
def test_oracle_main_works_under_redirect_stdout_string_io(command):
    import contextlib
    import io

    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        assert oracle.main([command]) == 0
    completed = subprocess.run([sys.executable, "-m", "virtual_plc.oracle", command], capture_output=True,
                               env=dict(os.environ, PYTHONPATH=str(ROOT)), timeout=60)
    assert completed.returncode == 0, completed.stderr
    assert captured.getvalue() == completed.stdout.decode("utf-8")
