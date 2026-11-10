"""P1/P2 review closure: CLI --init snapshots do not override the SD203 CPU state mirror."""

import json
from types import SimpleNamespace

import pytest

from virtual_plc import __main__ as cli


@pytest.mark.parametrize("state, mirror", [("STOP", 0), ("PAUSE", 2), ("RUN", 1)])
def test_init_snapshot_sd203_is_replaced_by_initial_state(tmp_path, monkeypatch, state, mirror):
    snapshot, dump = tmp_path / "snap.json", tmp_path / "dump.json"
    # A dump taken from a RUN server always carries SD203=1.
    snapshot.write_text(json.dumps({"SD": {"203": [1]}, "D": {"0": [5]}}), encoding="utf-8")

    def interrupt(timeout):
        raise KeyboardInterrupt

    # Patch only the CLI's module binding; the real Server's workers keep threading.Event.
    monkeypatch.setattr(cli, "threading", SimpleNamespace(Event=lambda: SimpleNamespace(wait=interrupt)))
    assert cli.main(["--port", "0", "--initial-state", state, "--init", str(snapshot),
                     "--dump-on-exit", str(dump)]) == 0
    result = json.loads(dump.read_text(encoding="utf-8"))
    assert result["SD"]["203"] == [mirror]
    assert result["D"]["0"] == [5]
