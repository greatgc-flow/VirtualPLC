"""Atomic snapshot replacement and failure recovery (#7)."""

import json
import os

import pytest

from virtual_plc import __main__ as cli


def test_snapshot_replaces_existing_json_without_temp_files(tmp_path):
    target = tmp_path / "state.json"
    target.write_text("old snapshot", encoding="utf-8")
    snapshot = {"D": {"100": [1, 2, 3]}, "M": {"0": [0, 1]}}
    cli.write_snapshot_atomic(target, snapshot)
    assert json.loads(target.read_text(encoding="utf-8")) == snapshot
    assert target.read_text(encoding="utf-8").endswith("\n")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["state.json"]


@pytest.mark.parametrize("failure", ["fsync", "replace"])
def test_snapshot_failed_commit_preserves_old_content_and_cleans_up(tmp_path, monkeypatch, failure):
    target = tmp_path / "state.json"
    original = '{"D":{"0":[42]}}\n'
    target.write_text(original, encoding="utf-8")

    def fail(*args, **kwargs):
        raise OSError(f"simulated {failure} failure")

    monkeypatch.setattr(cli.os, failure, fail)
    with pytest.raises(OSError, match=failure):
        cli.write_snapshot_atomic(target, {"D": {"0": [100]}})
    assert target.read_text(encoding="utf-8") == original
    assert sorted(p.name for p in tmp_path.iterdir()) == ["state.json"]


def test_snapshot_unserializable_data_never_touches_existing_file(tmp_path):
    target = tmp_path / "state.json"
    target.write_text("known-good", encoding="utf-8")
    with pytest.raises(TypeError):
        cli.write_snapshot_atomic(target, {"unsupported": object()})
    assert target.read_text(encoding="utf-8") == "known-good"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["state.json"]


def test_cli_dump_error_reports_exit_code_and_preserves_old_snapshot(tmp_path, monkeypatch, capsys):
    target = tmp_path / "state.json"
    target.write_text("previous", encoding="utf-8")
    from types import SimpleNamespace

    class DummyServer:
        def __init__(self, host, port, **kwargs):
            self.address = (host, 2222)
            self.memory = SimpleNamespace(dump=lambda: {"D": {"0": [99]}})
        def start(self):
            pass
        def stop(self):
            pass

    def interrupt(_):
        raise KeyboardInterrupt

    def fail(*args, **kwargs):
        raise OSError("simulated disk failure")

    monkeypatch.setattr(cli, "Server", DummyServer)
    monkeypatch.setattr(cli.threading, "Event", lambda: SimpleNamespace(wait=interrupt))
    monkeypatch.setattr(cli.os, "replace", fail)
    assert cli.main(["--dump-on-exit", str(target)]) == 1
    assert "cannot dump memory" in capsys.readouterr().err
    assert target.read_text(encoding="utf-8") == "previous"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["state.json"]
