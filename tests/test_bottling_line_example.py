"""Keep the bottling_line sample project working (it is the newcomer entry point)."""

import json
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

SAMPLE = Path(__file__).resolve().parents[1] / "examples" / "bottling_line"


def run_script(name, *args, timeout=60):
    # -W: the demos must stay free of deprecated positional calls (#78).
    return subprocess.run([sys.executable, "-W", "error::DeprecationWarning", str(SAMPLE / name), *args],
                          cwd=SAMPLE, capture_output=True, text=True, timeout=timeout)


def test_sample_files_exist_and_readme_references_every_script():
    readme = (SAMPLE / "README.md").read_text(encoding="utf-8")
    scripts = sorted(p.name for p in SAMPLE.iterdir() if p.suffix in (".py", ".json"))
    assert scripts, "sample is empty"
    for name in scripts:
        assert name in readme, name + " is not mentioned in the sample README"


@pytest.mark.parametrize("name,expected", [
    ("01_hello.py", ["D100..D101 = [123, -45]", "M0..M2     = [1, 0, 1]", "VirtualPLC"]),
    ("02_line_demo.py", ["run of 10 finished", "count=10/10", "alarm=True", "start refused"]),
    ("03_fault_injection.py", ["lost reply (drop)", "reconnects=1", "end_code=0xC051",
                                "end_code=0xC059", "outcome unknown, not re-sent"]),
])
def test_demo_scripts_run_and_print_documented_output(name, expected):
    result = run_script(name)
    assert result.returncode == 0, result.stderr
    for token in expected:
        assert token in result.stdout, (token, result.stdout)


def test_sample_pytest_suite_passes():
    result = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                             str(SAMPLE)], cwd=SAMPLE, capture_output=True, text=True,
                            timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr


def test_seed_and_fault_plan_files_are_valid_for_the_cli():
    json.loads((SAMPLE / "seed.json").read_text(encoding="utf-8"))
    from virtual_plc import FaultPlan, Memory

    memory = Memory()
    memory.load(json.loads((SAMPLE / "seed.json").read_text(encoding="utf-8")))
    FaultPlan.from_file(SAMPLE / "faults.json")


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start_cli(port, *extra):
    server = subprocess.Popen([sys.executable, "-m", "virtual_plc", "--port", str(port),
                               "--init", str(SAMPLE / "seed.json"), *extra],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                              env=dict(os.environ, PYTHONUNBUFFERED="1"))
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if server.poll() is not None:
            pytest.fail("simulator exited: " + server.communicate()[1])
        try:
            # A probe connection would consume fault-plan connection ordinals, so wait
            # for the startup banner on stderr instead.
            line = server.stderr.readline()
            if line.startswith("listening on"):
                return server
        except OSError:
            pass
    server.kill()
    pytest.fail("simulator did not start")


def stop_cli(server):
    server.terminate()
    server.communicate(timeout=15)


def test_external_server_step_works_against_the_cli(tmp_path):
    port = free_port()
    server = start_cli(port)
    try:
        result = run_script("04_external_server.py", str(port))
        assert result.returncode == 0, result.stderr
        assert re.search(r"LineStatus\(running=False, alarm=False, target=0, count=0, "
                         r"temperature_c=25\.0\)", result.stdout), result.stdout
        assert "reconnects: 0" in result.stdout
    finally:
        stop_cli(server)


def test_external_server_step_with_fault_plan_refuses_then_succeeds():
    """README step 4: run 1 drops then hits 0xC059 (exit 2); run 2 succeeds (exit 0)."""
    port = free_port()
    server = start_cli(port, "--fault-plan", str(SAMPLE / "faults.json"))
    try:
        first = run_script("04_external_server.py", str(port))
        assert first.returncode == 2, first.stdout + first.stderr
        assert "0xC059" in first.stderr
        second = run_script("04_external_server.py", str(port))
        assert second.returncode == 0, second.stdout + second.stderr
        assert "temperature_c=25.0" in second.stdout
    finally:
        stop_cli(server)


def test_external_server_step_reports_unreachable_plc():
    result = run_script("04_external_server.py", str(free_port()))
    assert result.returncode == 1
    assert "cannot reach the PLC" in result.stderr
