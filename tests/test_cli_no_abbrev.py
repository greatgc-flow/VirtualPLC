"""Regression tests for CLI option abbreviation prohibition and help text."""

import pytest

from virtual_plc import __main__ as cli


def test_abbreviated_option_rejected_ethernet_model_prof():
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["--ethernet-model", "rj71en71", "--prof", "Q", "--show-effective-ethernet"])
    assert exc_info.value.code == 2


def test_abbreviated_option_rejected_listen_por(monkeypatch):
    monkeypatch.setattr(cli.Server, "start", lambda self: pytest.fail("should not reach Server.start"))
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["--listen", "udp:0", "--por", "6000"])
    assert exc_info.value.code == 2


def test_full_spellings_work(capsys):
    assert cli.main(["--ethernet-model", "qj71e71", "--profile", "Q", "--show-effective-ethernet"]) == 0
    out = capsys.readouterr().out
    assert "qj71e71" in out


def test_show_effective_ethernet_help_mentions_host_safety():
    parser = cli.build_parser()
    action = next(a for a in parser._actions if "--show-effective-ethernet" in a.option_strings)
    assert "host safety" in action.help


def test_show_effective_ethernet_non_loopback_host_rejected():
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["--host", "192.168.1.100", "--ethernet-model", "qj71e71", "--show-effective-ethernet"])
    assert exc_info.value.code == 2
