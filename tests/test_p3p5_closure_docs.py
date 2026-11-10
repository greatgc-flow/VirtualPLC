"""P3/P5 closure: API docstrings and README/guide wording that must match code."""

import inspect
from pathlib import Path

from virtual_plc import Server, ethernet, guide
from virtual_plc.__main__ import build_parser

ROOT = Path(__file__).resolve().parents[1]


def test_readme_fx5_firmware_helper_uses_real_keyword():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    parameters = inspect.signature(ethernet.inspect_reference_fx5_simple_cpu_communication).parameters
    assert "firmware_version" in parameters
    assert "inspect_reference_fx5_simple_cpu_communication(model, firmware_version=None)" in readme
    assert "(model, firmware)" not in readme


def test_server_has_docstring_pointing_to_guide():
    doc = inspect.getdoc(Server)
    assert doc and "virtual-plc guide embed" in doc
    for keyword in ("listeners", "fault_plan", "udp_fault_plan", "response_hook", "max_clients"):
        assert keyword in doc


def test_blocking_hooks_are_documented():
    text = guide.render(build_parser(), "embed")
    assert "hooks must return" in text
    behavior = (ROOT / "docs/BEHAVIOR.md").read_text(encoding="utf-8")
    assert "hooks must return; stop() joins workers" in " ".join(behavior.split()).lower()


def test_behavior_exit_codes_include_dump_failure():
    behavior = " ".join((ROOT / "docs/BEHAVIOR.md").read_text(encoding="utf-8").split())
    assert "--dump-on-exit" in behavior and "write failures exit 1" in behavior
