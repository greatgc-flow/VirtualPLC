"""R04CPU CPU-built-in *offline* full-configuration reference preflight.

Manufacturer facts are scoped to SH-081257ENG-AD; October 2026 AG is
not clause-verified. Cross-checks only reuse independent existing inspectors.
No real PLC, network listener, runtime defaults or certification.
"""
import importlib
import json
import socket

import pytest

from virtual_plc.ethernet import (
    inspect_reference_rncpu_external_device_batch,
    inspect_reference_rncpu_remote_opening,
    inspect_reference_rncpu_data_timers,
    reference_catalog,
)


@pytest.fixture
def inspect():
    # Lazy resolution lets tests actually run RED before feature implementation.
    return getattr(importlib.import_module("virtual_plc.rncpu_reference"),
                   "inspect_reference_r04cpu_configuration")


def test_missing_root_and_empty_object_are_not_the_same(inspect):
    missing = inspect()
    empty = inspect({})
    assert missing["input_state"] == "NOT_PROVIDED"
    assert empty["input_state"] == "EMPTY"
    for report in (missing, empty):
        assert report["checks"] == {
            "opening_method": None,
            "data_timers": None,
            "external_devices": None,
        }
        assert report["manual_revision_check"]["status"] == "UNKNOWN_REQUESTED_REVISION"
        assert report["physical_hardware_certified"] is False
        assert report["simulator_network_affected"] is False
        assert json.loads(json.dumps(report)) == report


def test_ad_manual_composes_existing_offline_inspectors_without_new_defaults(inspect):
    cfg = {
        "manual_revision": "AD",
        "opening_method": "do_not_open_by_program",
        "data_timers": {},
        "external_devices": [
            {"connection_number": 1, "plc_port": 1024},
            {"connection_number": 2, "plc_port": None},
        ],
    }
    report = inspect(cfg)
    assert report["model"] == "R04CPU"
    assert report["interface"] == "rncpu_builtin"
    assert report["input_state"] == "PROVIDED"
    assert report["manual_revision_check"]["status"] == "AD_REFERENCE_ONLY"
    assert report["checks"]["opening_method"] == inspect_reference_rncpu_remote_opening(
        "do_not_open_by_program"
    )
    assert report["checks"]["data_timers"] == inspect_reference_rncpu_data_timers(
        "R04CPU", {}
    )
    assert report["checks"]["external_devices"] == inspect_reference_rncpu_external_device_batch(
        cfg["external_devices"], model="R04CPU"
    )
    assert report["overall_static_review"] == "REFERENCE_CHECKS_ONLY"
    assert cfg["external_devices"][1]["plc_port"] is None


def test_ag_and_other_revisions_cannot_be_silently_declared_compatible(inspect):
    catalog_gate = reference_catalog()["rncpu_builtin"][
        "external_device_configuration_reference"
    ]["manual_revision_gate"]
    ag = inspect({"manual_revision": "AG", "external_devices": []})
    assert ag["manual_revision_check"]["status"] == "UNVERIFIED_MANUAL_REVISION"
    assert ag["manual_revision_check"]["reference_revision"] == catalog_gate[
        "validated_reference_revision"
    ]
    assert ag["manual_revision_check"]["listed_newer_revision"] == catalog_gate[
        "newer_catalog_revision"
    ]
    assert ag["manual_revision_check"]["newer_revision_comparison"] == "NOT_VERIFIED"
    assert ag["overall_static_review"] == "SOURCE_REVISION_NOT_VERIFIED"
    ae = inspect({"manual_revision": "AE"})
    assert ae["manual_revision_check"]["status"] == "UNVERIFIED_MANUAL_REVISION"
    assert ae["overall_static_review"] == "SOURCE_REVISION_NOT_VERIFIED"
    assert inspect({"external_devices": []})["overall_static_review"] == (
        "SOURCE_REVISION_NOT_VERIFIED"
    )


def test_composition_retains_diagnostics_and_independent_gap_policy(inspect):
    cfg = {
        "manual_revision": "AD",
        "opening_method": "open_by_program",
        "external_devices": [
            {"connection_number": 2, "plc_port": 5005},
            {"connection_number": 3, "plc_port": 5005},
        ],
    }
    result = inspect(cfg)
    assert result["overall_static_review"] == "REJECTED_STATIC_SETTINGS"
    assert [x["code"] for x in result["checks"]["external_devices"]["diagnostics"]] == [
        "VENDOR_PORT_NOT_CONFIGURABLE", "VENDOR_PORT_NOT_CONFIGURABLE",
        "POTENTIAL_OWN_PORT_REUSE", "SLOT_GAP_REVIEW",
    ]
    assert result["checks"]["opening_method"]["reconnect_risk_status"] == (
        "DOCUMENTED_REMOTE_RUN_RECONNECT_FAILURE"
    )
    without_gaps = inspect(cfg, report_slot_gaps=False)
    assert [x["code"] for x in without_gaps["checks"]["external_devices"]["diagnostics"]] == [
        "VENDOR_PORT_NOT_CONFIGURABLE", "VENDOR_PORT_NOT_CONFIGURABLE",
        "POTENTIAL_OWN_PORT_REUSE",
    ]


def test_review_required_with_ad_source_even_without_invalid_port(inspect):
    result = inspect({
        "manual_revision": "AD",
        "opening_method": "open_by_program",
        "external_devices": [{"connection_number": 1, "plc_port": 1024}],
    })
    assert result["overall_static_review"] == "REVIEW_REQUIRED"


@pytest.mark.parametrize("root", [[], (), "", "None", 0, True, 1.2, {0: "a"},
                                   {"unexpected": 1}, {"manual_revision": None},
                                   {"manual_revision": "ad"},
                                   {"manual_revision": "A1"},
                                   {"data_timers": None}])
def test_invalid_root_and_field_values_fail_closed(inspect, root):
    with pytest.raises(ValueError):
        inspect(root)


@pytest.mark.parametrize("model", ["RJ71EN71", "R08CPU", "r04cpu", None, True, {}])
def test_other_cpu_and_module_models_are_never_promoted(inspect, model):
    with pytest.raises(ValueError):
        inspect({"manual_revision": "AD"}, model=model)


@pytest.mark.parametrize("bad", [None, 1, 0, [], "false"])
def test_gap_option_requires_bool_even_with_missing_rows(inspect, bad):
    with pytest.raises(ValueError):
        inspect({}, report_slot_gaps=bad)


def test_delegated_invalid_values_fail_atomically(inspect):
    with pytest.raises(ValueError):
        inspect({"opening_method": "open_by_program", "data_timers": {
            "timers": {"tcp_ulp_ms": {"value": 1, "unit": "s"}}
        }})
    with pytest.raises(ValueError):
        inspect({"external_devices": [{"connection_number": 1, "plc_port": True}]})


def test_unprovided_fields_are_not_implied_actual_plc_settings(inspect):
    report = inspect({"manual_revision": "AD"})
    assert report["checks"]["opening_method"] is None
    assert report["checks"]["data_timers"] is None
    assert report["checks"]["external_devices"] is None
    explicit_unknown = inspect({"manual_revision": "AD", "opening_method": None,
                                "external_devices": None})
    assert explicit_unknown["checks"]["opening_method"]["reconnect_risk_status"] == "UNKNOWN"
    assert explicit_unknown["checks"]["external_devices"]["input_state"] == "NOT_PROVIDED"
    assert explicit_unknown["overall_static_review"] == "REVIEW_REQUIRED"


def test_no_sockets_or_mutation_and_defensive_source_copy(inspect, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("offline reference preflight must never open sockets")
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    original = {"manual_revision": "AD", "external_devices": [
        {"connection_number": 1, "plc_port": 1024}
    ]}
    report = inspect(original)
    report["manual_revision_check"]["source"]["manual"] = "FORGED"
    report["checks"]["external_devices"]["rows"][0]["plc_port"] = 999
    again = inspect(original)
    assert again["manual_revision_check"]["source"]["manual"] == "SH-081257ENG-AD"
    assert again["checks"]["external_devices"]["rows"][0]["plc_port"] == 1024
    assert original["external_devices"][0]["plc_port"] == 1024
