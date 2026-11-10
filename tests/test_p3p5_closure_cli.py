"""P3/P5 closure: CLI preflight, BOM JSON, help/guide parsing, banner and pass-through."""

import json
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from virtual_plc import __main__ as cli
from virtual_plc import guide

ROOT = Path(__file__).resolve().parents[1]
BOM = "﻿"


class FakeServer:
    """Stands in for Server; records construction kwargs and inspects the logger mid-run."""

    created = []

    def __init__(self, host, port, **kwargs):
        self.host, self.port, self.kwargs = host, port, kwargs
        self.address = (host, 54388)
        self.addresses = [(transport, host, 5000 + index)
                          for index, (transport, _) in enumerate(kwargs.get("listeners", []))]
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
    seen = {}

    def interrupt(timeout):
        seen["handlers"] = list(logging.getLogger("virtual_plc").handlers)
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "Server", FakeServer)
    monkeypatch.setattr(cli.threading, "Event", lambda: SimpleNamespace(wait=interrupt))
    return seen


def _exit_code(arguments):
    with pytest.raises(SystemExit) as error:
        cli.main(arguments)
    return error.value.code


# F1: --dump-on-exit is preflighted before binding.
@pytest.mark.parametrize("relative", ["nodir/x.json", "afile.txt/x.json", "adir"])
def test_dump_on_exit_destination_is_checked_before_binding(tmp_path, monkeypatch, capsys, relative):
    (tmp_path / "afile.txt").write_text("x", encoding="utf-8")
    (tmp_path / "adir").mkdir()
    monkeypatch.setattr(cli.Server, "start", lambda self: pytest.fail("must not bind"))
    assert _exit_code(["--port", "0", "--dump-on-exit", str(tmp_path / relative)]) == 2
    err = capsys.readouterr().err.strip()
    assert len(err.splitlines()) == 1 and "--dump-on-exit" in err
    assert err.endswith("; see: virtual-plc guide memory")
    assert ".tmp" not in err


def test_dump_on_exit_existing_directory_ok(tmp_path, fake):
    target = tmp_path / "saved.json"
    assert cli.main(["--port", "0", "--dump-on-exit", str(target)]) == 0
    assert json.loads(target.read_text(encoding="utf-8")) == {}


# F2: UTF-8 BOM JSON (Windows PowerShell 5.1 Out-File/Set-Content) is accepted everywhere.
def test_bom_fault_plan_and_udp_plan_files_load(tmp_path):
    from virtual_plc import FaultPlan, UdpFaultPlan
    path = tmp_path / "plan.json"
    path.write_text(BOM + '{"steps": [{"action": {"type": "drop"}}]}', encoding="utf-8")
    assert FaultPlan.from_file(path).select(1, nth=1, connection=1) == {"type": "drop"}
    assert UdpFaultPlan.from_file(path).select(1, peer="127.0.0.1") == {"type": "drop"}


def test_bom_init_and_ethernet_config_load(tmp_path, fake):
    seed = tmp_path / "seed.json"
    seed.write_text(BOM + '{"D": {"0": [7]}}', encoding="utf-8")
    config = tmp_path / "eth.json"
    config.write_text(BOM + "{}", encoding="utf-8")
    assert cli.main(["--port", "0", "--init", str(seed)]) == 0
    assert FakeServer.created[-1].kwargs["memory"].read_words("D", 0, 1) == [7]
    assert cli.main(["--port", "0", "--ethernet-model", "qj71e71", "--ethernet-config", str(config)]) == 0
    assert FakeServer.created[-1].kwargs["ethernet_overrides"] == {}


# F4: --help points to the guide.
def test_help_mentions_guide(capsys):
    assert _exit_code(["--help"]) == 0
    assert "virtual-plc guide [TOPIC] [--json]" in capsys.readouterr().out


# F5: guide options are never abbreviated.
def test_guide_rejects_abbreviated_json(capsys):
    assert _exit_code(["guide", "--js"]) == 2


# F7: exit-code line covers dump failures.
def test_run_guide_exit_codes_include_dump_failure():
    assert "1 cannot bind or cannot write --dump-on-exit" in guide.RUN


# F12b/F12c: --max-clients passes through; -v handler attached only while running.
def test_max_clients_passthrough_and_verbose_handler_lifecycle(fake):
    logger = logging.getLogger("virtual_plc")
    before = list(logger.handlers)
    assert cli.main(["--port", "0", "--max-clients", "2", "-v"]) == 0
    assert FakeServer.created[-1].kwargs["max_clients"] == 2
    added = [handler for handler in fake["handlers"] if handler not in before]
    assert len(added) == 1
    assert logger.handlers == before


# F14: banner shows udp_fault_plan/max_clients and brackets IPv6 hosts.
def test_banner_brackets_ipv6_and_shows_plans_and_limits(fake, capsys):
    assert cli.main(["--host", "::1", "--port", "0", "--max-clients", "3"]) == 0
    banner = capsys.readouterr().err.strip()
    assert banner.startswith("listening on [::1]:54388 (")
    assert "max_clients=3" in banner and "udp_fault_plan=None" in banner


def test_listen_banner_brackets_ipv6(fake, capsys, tmp_path):
    plan = tmp_path / "udp.json"
    plan.write_text('{"steps": []}', encoding="utf-8")
    assert cli.main(["--host", "::1", "--listen", "tcp:0", "--listen", "udp:0",
                     "--udp-fault-plan", str(plan)]) == 0
    banner = capsys.readouterr().err.strip()
    assert banner.startswith("listening on tcp:[::1]:5000, udp:[::1]:5001 (")
    assert f"udp_fault_plan={plan}" in banner


def test_guide_documents_listen_banner():
    assert "PROTO:HOST:PORT" in guide.RUN and "[::1]" in guide.RUN


# C1: every long option of build_parser is named in README or docs.
def test_every_cli_flag_is_documented_outside_the_generated_guide():
    texts = [(ROOT / "README.md").read_text(encoding="utf-8")]
    texts += [path.read_text(encoding="utf-8") for path in (ROOT / "docs").glob("*.md")]
    corpus = "\n".join(texts)
    readme = texts[0]
    flags = [flag for action in cli.build_parser()._actions for flag in action.option_strings
             if flag.startswith("--")]
    missing = [flag for flag in flags if flag not in corpus]
    assert not missing
    assert [flag for flag in flags if flag not in readme] == []
