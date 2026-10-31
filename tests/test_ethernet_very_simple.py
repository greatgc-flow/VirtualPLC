"""Small GX Works configuration contracts guided by VerySimpleGuide.

A research-only hardware reference is NOT a runnable VirtualPLC profile.
Explicit overrides are distinct from inherited factory defaults.
"""

import json

import pytest

from virtual_plc.__main__ import main
from virtual_plc import __main__ as cli
from virtual_plc.ethernet import EthernetSettings, model_catalog, reference_catalog
from virtual_plc.guide import data


@pytest.mark.parametrize("model,profile", [
    ("qj71e71", "Q"), ("lj71e71", "L"), ("rj71en71", "iQ-R")
])
def test_cli_infers_profile_from_explicit_hardware_model(model, profile, capsys):
    assert main(["--ethernet-model", model, "--show-effective-ethernet"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["model"] == model
    assert result["profile"] == profile
    # Explicit profile remains valid and deterministic.
    assert main(["--profile", profile, "--ethernet-model", model,
                 "--show-effective-ethernet"]) == 0


def test_cli_conflicting_explicit_profile_is_not_silently_overridden(capsys):
    with pytest.raises(SystemExit) as error:
        main(["--profile=Q", "--ethernet-model", "rj71en71", "--show-effective-ethernet"])
    assert error.value.code == 2
    assert "guide ethernet" in capsys.readouterr().err


@pytest.mark.parametrize("value", ["null", "[]", "true", "7", '""'])
def test_cli_json_config_rejects_nonobject_before_binding(tmp_path, capsys, value):
    config = tmp_path / "ethernet.json"
    config.write_text(value, encoding="utf-8")
    with pytest.raises(SystemExit) as error:
        main(["--ethernet-model", "qj71e71", "--ethernet-config", str(config),
              "--show-effective-ethernet"])
    assert error.value.code == 2
    assert "guide ethernet" in capsys.readouterr().err


def test_config_explicit_default_is_still_override():
    config = EthernetSettings("qj71e71", {
        "timers": {"tcp_ulp_ms": 30000},
        "communication_data_code": "binary",
        "allow_write_during_run": False,
    })
    report = config.report()
    for key in ("tcp_ulp_ms", "communication_data_code", "allow_write_during_run"):
        field = report["parameters"][key]
        assert field["value"] == field["default"]
        assert field["overridden"] is True
    assert report["parameters"]["tcp_resend_ms"]["overridden"] is False
    assert EthernetSettings("qj71e71").report()["parameters"]["tcp_ulp_ms"]["overridden"] is False


def test_explicit_overrides_snapshot_does_not_follow_mutated_input():
    original = {"timers": {"tcp_ulp_ms": 30000}}
    config = EthernetSettings("qj71e71", original)
    original["timers"].clear()
    assert config.report()["parameters"]["tcp_ulp_ms"]["overridden"] is True


def test_reference_catalog_never_promotes_unimplemented_models():
    research = reference_catalog()
    assert set(research) == {"fx5_cpu_builtin", "fx5_enet", "rncpu_builtin"}
    assert set(research).isdisjoint(model_catalog())
    for identifier, item in research.items():
        assert item["implementation"] == "research_only"
        assert item["source"]["url"].startswith("https://")
        assert "unverified" in item
        with pytest.raises(ValueError, match="ethernet_model"):
            EthernetSettings(identifier)
    assert research["fx5_cpu_builtin"]["reference"]["connection_limit"] == 8
    assert research["fx5_enet"]["reference"]["vendor_port_ranges"] == [[1, 5548], [5570, 65534]]
    assert research["fx5_enet"]["reference"]["default_slmp_host_port"] == "blank"
    assert research["fx5_enet"]["reference"]["alive_start_ms"] == 600000
    assert research["fx5_enet"]["reference"]["alive_retries"] == 3
    assert research["rncpu_builtin"]["reference"]["auto_open_udp"] == 5005
    assert "tcp_ulp_ms" in research["fx5_enet"]["unverified"]


def test_guide_json_is_single_registry_projection_not_runtime_model_claim():
    doc = data(cli.build_parser(), "ethernet")
    assert doc["models"] == model_catalog()
    assert doc["reference_only_models"] == reference_catalog()
    assert set(cli.build_parser()._option_string_actions["--ethernet-model"].choices) == set(doc["models"])
    assert set(doc["models"]).isdisjoint(doc["reference_only_models"])
    assert json.loads(json.dumps(doc)) == doc
