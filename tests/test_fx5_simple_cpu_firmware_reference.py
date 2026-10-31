"""Manual/FAQ-scoped FX5 simple CPU communication firmware gate.

Authoritative Mitsubishi English FAQs:
- #39316: FX5U/FX5UC >=1.110; FX5UJ/FX5S from first revision.
- #44329: for new/legacy CPU *connection example*, GX Works3 path and
  QnA-compatible 3E peer device selection differ at version 1.110.

This is REFERENCE ONLY. It must never enable SLMP, bind sockets,
substitute simple CPU target counts for SLMP connection caps, or claim
any vendor firmware has been observed.
"""

import importlib
import json
import socket

import pytest

from virtual_plc.ethernet import EthernetSettings, model_catalog, reference_catalog
from virtual_plc.__main__ import build_parser
from virtual_plc.guide import data


@pytest.fixture
def inspect():
    # Missing API is an observed TDD RED without breaking test collection.
    return getattr(importlib.import_module("virtual_plc.ethernet"),
                   "inspect_reference_fx5_simple_cpu_communication")


@pytest.mark.parametrize("model,firmware,support,path,destination", [
    ("FX5U", "1.000", "NOT_SUPPORTED", "External device configuration", None),
    ("FX5U", "1.109", "NOT_SUPPORTED", "External device configuration", None),
    ("FX5U", "1.110", "SUPPORTED", "Simple CPU communication settings",
     "SLMP-compatible device (QnA-compatible 3E frame)"),
    ("FX5U", "1.111", "SUPPORTED", "Simple CPU communication settings",
     "SLMP-compatible device (QnA-compatible 3E frame)"),
    ("FX5UC", "1.099", "NOT_SUPPORTED", "External device configuration", None),
    ("FX5UC", "1.110", "SUPPORTED", "Simple CPU communication settings",
     "SLMP-compatible device (QnA-compatible 3E frame)"),
    ("FX5UC", "1.220", "SUPPORTED", "Simple CPU communication settings",
     "SLMP-compatible device (QnA-compatible 3E frame)"),
    ("FX5UJ", None, "SUPPORTED", None, None),
    ("FX5UJ", "1.010", "SUPPORTED", None, None),
    ("FX5S", None, "SUPPORTED", None, None),
    ("FX5S", "1.010", "SUPPORTED", None, None),
])
def test_model_specific_firmware_and_legacy_configuration(
        inspect, model, firmware, support, path, destination):
    report = inspect(model, firmware)
    assert report["model"] == model
    assert report["firmware_version"] == firmware
    assert report["support_status"] == support
    if path is None:
        assert report["gxworks3_configuration_path"] is None
    else:
        assert report["gxworks3_configuration_path"][-1] == path
    assert report["destination_device_type"] == destination
    assert report["status"] == "OFFICIAL_FAQ_REFERENCE_ONLY"
    assert report["physical_hardware_certified"] is False
    assert report["simulator_network_affected"] is False
    assert len(report["sources"]) == 2
    assert all(entry["url"].startswith("https://fa-faq.mitsubishielectric.com/faq/show/")
               for entry in report["sources"])
    assert json.loads(json.dumps(report)) == report


@pytest.mark.parametrize("model", ["FX5U", "FX5UC"])
def test_unknown_firmware_not_equated_with_unsupported(inspect, model):
    report = inspect(model)
    assert report["support_status"] == "UNKNOWN_FIRMWARE"
    assert report["firmware_version"] is None
    assert report["gxworks3_configuration_path"] is None
    assert report["destination_device_type"] is None
    assert report["target_limit"] == 16


@pytest.mark.parametrize("model,limit", [
    ("FX5U", 16), ("FX5UC", 16), ("FX5UJ", 8), ("FX5S", 8),
])
def test_target_limit_is_distinct_from_total_ethernet_sockets(inspect, model, limit):
    result = inspect(model, "1.110")
    assert result["target_limit"] == limit
    assert result["external_ethernet_connection_limit"] == 8
    assert result["target_limit_scope"] == "simple_cpu_communication_targets_not_slmp_sockets"
    assert result["physical_hardware_certified"] is False
    assert result["support_status"] == "SUPPORTED"


@pytest.mark.parametrize("model", [
    "", "fx5u", "FX5", "FX5-ENET", "fx5_cpu_builtin",
    "qj71e71", "rncpu_builtin", None, False, True, [], {},
])
def test_wrong_family_never_inherits_firmware_gate(inspect, model):
    with pytest.raises(ValueError):
        inspect(model, "1.110")


@pytest.mark.parametrize("firmware", [
    "", "1.11", "1.1100", "1.1.10", "v1.110", "1.110 ", " 1.110",
    "1,110", "1.x10", "1.١١٠", "01.110", "1.١10", "2",
    -1, 1.110, False, True, [], {},
])
def test_version_is_exact_vendor_string_not_float(inspect, firmware):
    with pytest.raises(ValueError):
        inspect("FX5U", firmware)


def test_faq_metadata_is_single_ssot_and_defensively_copied(inspect):
    c = reference_catalog()
    spec = c["fx5_cpu_builtin"]
    support = spec["simple_cpu_firmware_reference"]
    assert support["models"]["FX5U"]["minimum_version"] == "1.110"
    assert support["models"]["FX5UC"]["minimum_version"] == "1.110"
    assert support["models"]["FX5UJ"]["from_first"] is True
    assert support["models"]["FX5S"]["from_first"] is True
    assert support["source"]["url"].endswith("/39316")
    assert spec["simple_cpu_interop_reference"]["source"]["url"].endswith("/44329")
    assert "simple_cpu_firmware_reference" not in c["fx5_enet"]
    assert "simple_cpu_firmware_reference" not in c["rncpu_builtin"]
    assert "fx5_cpu_builtin" not in model_catalog()
    assert "fx5_enet" not in model_catalog()
    assert data(build_parser(), "ethernet")["reference_only_models"] == c
    spec["simple_cpu_firmware_reference"]["models"]["FX5U"]["minimum_version"] = "9.999"
    assert inspect("FX5U", "1.109")["support_status"] == "NOT_SUPPORTED"
    assert reference_catalog()["fx5_cpu_builtin"]["simple_cpu_firmware_reference"][
        "models"]["FX5U"]["minimum_version"] == "1.110"
    with pytest.raises(ValueError):
        EthernetSettings("fx5_cpu_builtin")


def test_no_socket_calls_or_runtime_profile_changes(inspect, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("no network allowed in offline firmware reference")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    for model in ("FX5U", "FX5UC", "FX5UJ", "FX5S"):
        assert inspect(model)["simulator_network_affected"] is False
    assert build_parser().get_default("max_clients") == 64
    assert set(model_catalog()) == {"qj71e71", "lj71e71", "rj71en71"}


def test_uj_and_s_early_firmware_are_never_incorrectly_rejected(inspect):
    for model in ("FX5UJ", "FX5S"):
        # Official FAQ #39316: these families support feature from first
        # revision, rather than only firmware >= 1.110.
        result = inspect(model, "1.010")
        assert result["support_status"] == "SUPPORTED"
        # FAQ #44329 does not separately establish the GX Works3 path
        # for every UJ/S early release; leave it unknown.
        assert result["gxworks3_configuration_path"] is None
