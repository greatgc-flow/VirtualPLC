"""R04CPU opening-method source edition gate: CPU E -> I, source only.

Source: Mitsubishi official iQ-R R04CPU catalogue lists
SH-082488ENG-I (2026-08). The prior cited opening-method behavior
comes from SH-082488ENG-E pp.3, 684-685. No E/I clause comparison was
possible, so I cannot be treated as reviewed. Do not infer physical parity.
"""
import json
import socket

import pytest

from virtual_plc.ethernet import reference_catalog
from virtual_plc.rncpu_reference import inspect_reference_r04cpu_configuration


def test_cpu_manual_gate_is_in_manufacturer_reference_ssot():
    ref = reference_catalog()["rncpu_builtin"]["remote_opening_reference"]
    assert ref["source"]["manual"] == "SH-082488ENG-E"
    gate = ref["manual_revision_gate"]
    assert gate["validated_reference_revision"] == "E"
    assert gate["newer_catalog_revision"] == "I"
    assert gate["newer_catalog_published"] == "2026-08"
    assert gate["newer_revision_comparison"] == "NOT_VERIFIED"
    assert gate["catalog_url"].startswith("https://www.mitsubishielectric.com/")
    assert "manual_revision_gate" not in reference_catalog()["rncpu_builtin"]["data_timer_reference"]


def test_existing_ad_legacy_input_still_works_without_cpu_manual_revision():
    cfg = {"manual_revision": "AD", "opening_method": "do_not_open_by_program"}
    report = inspect_reference_r04cpu_configuration(cfg)
    assert report["overall_static_review"] == "REFERENCE_CHECKS_ONLY"
    assert report["checks"]["opening_method"]["source"]["manual"] == "SH-082488ENG-E"
    cpu = report["cpu_manual_revision_check"]
    assert cpu["requested_revision"] is None
    assert cpu["status"] == "UNKNOWN_REQUESTED_REVISION"
    assert cpu["affects_supplied_opening_method"] is True
    assert cpu["newer_revision_comparison"] == "NOT_VERIFIED"


@pytest.mark.parametrize("edition,state,overall", [
    ("E", "E_REFERENCE_ONLY", "REFERENCE_CHECKS_ONLY"),
    ("I", "UNVERIFIED_MANUAL_REVISION", "SOURCE_REVISION_NOT_VERIFIED"),
    ("F", "UNVERIFIED_MANUAL_REVISION", "SOURCE_REVISION_NOT_VERIFIED"),
    ("AD", "UNVERIFIED_MANUAL_REVISION", "SOURCE_REVISION_NOT_VERIFIED"),
])
def test_opening_method_source_revision_is_separate_from_ethernet_ad_ag(
        edition, state, overall):
    result = inspect_reference_r04cpu_configuration({
        "manual_revision": "AD", "cpu_manual_revision": edition,
        "opening_method": "do_not_open_by_program",
    })
    assert result["manual_revision_check"]["status"] == "AD_REFERENCE_ONLY"
    assert result["cpu_manual_revision_check"]["reference_revision"] == "E"
    assert result["cpu_manual_revision_check"]["listed_newer_revision"] == "I"
    assert result["cpu_manual_revision_check"]["status"] == state
    assert result["cpu_manual_revision_check"]["affects_supplied_opening_method"] is True
    assert result["overall_static_review"] == overall
    assert result["physical_hardware_certified"] is False


def test_ethernet_ag_is_unknown_even_with_confirmed_cpu_e():
    result = inspect_reference_r04cpu_configuration({
        "manual_revision": "AG",
        "cpu_manual_revision": "E",
        "opening_method": "do_not_open_by_program",
    })
    assert result["manual_revision_check"]["status"] == "UNVERIFIED_MANUAL_REVISION"
    assert result["cpu_manual_revision_check"]["status"] == "E_REFERENCE_ONLY"
    assert result["overall_static_review"] == "SOURCE_REVISION_NOT_VERIFIED"


def test_unrelated_cpu_manual_revision_does_not_block_ad_external_device():
    # CPU manual E/I is only the cited owner of Opening Method A031H.
    result = inspect_reference_r04cpu_configuration({
        "manual_revision": "AD", "cpu_manual_revision": "I",
        "external_devices": [{"connection_number": 1, "plc_port": 1024}],
        "data_timers": {},
    })
    assert result["cpu_manual_revision_check"]["affects_supplied_opening_method"] is False
    assert result["cpu_manual_revision_check"]["status"] == "UNVERIFIED_MANUAL_REVISION"
    assert result["overall_static_review"] == "REFERENCE_CHECKS_ONLY"


def test_explicit_cpu_manual_only_vs_null_or_missing_sections():
    unknown = inspect_reference_r04cpu_configuration({
        "manual_revision": "AD", "cpu_manual_revision": "I",
    })
    assert unknown["cpu_manual_revision_check"]["status"] == "UNVERIFIED_MANUAL_REVISION"
    assert unknown["cpu_manual_revision_check"]["affects_supplied_opening_method"] is False
    assert unknown["overall_static_review"] == "REFERENCE_CHECKS_ONLY"
    with_explicit_unknown_opening = inspect_reference_r04cpu_configuration({
        "manual_revision": "AD", "cpu_manual_revision": "I",
        "opening_method": None,
    })
    assert with_explicit_unknown_opening["cpu_manual_revision_check"][
        "affects_supplied_opening_method"] is True
    assert with_explicit_unknown_opening["overall_static_review"] == (
        "SOURCE_REVISION_NOT_VERIFIED"
    )


@pytest.mark.parametrize("invalid", [
    None, "", "i", "e", "A1", "AAA", " E", "E ", "E\n", 1, False,
    [], {}, 1.0,
])
def test_invalid_cpu_edition_is_never_silently_defaulted(invalid):
    with pytest.raises(ValueError, match="cpu_manual_revision"):
        inspect_reference_r04cpu_configuration({
            "manual_revision": "AD", "cpu_manual_revision": invalid,
            "opening_method": "do_not_open_by_program",
        })


def test_static_rejection_outweighs_both_source_edition_unknowns():
    r = inspect_reference_r04cpu_configuration({
        "manual_revision": "AG", "cpu_manual_revision": "I",
        "opening_method": "open_by_program",
        "external_devices": [{"connection_number": 1, "plc_port": 5005}],
    })
    assert r["overall_static_review"] == "REJECTED_STATIC_SETTINGS"
    assert r["cpu_manual_revision_check"]["status"] == "UNVERIFIED_MANUAL_REVISION"
    assert r["manual_revision_check"]["status"] == "UNVERIFIED_MANUAL_REVISION"


def test_catalog_copies_and_composite_sources_are_not_mutated():
    original = {"manual_revision": "AD", "cpu_manual_revision": "I",
                "opening_method": "open_by_program"}
    report = inspect_reference_r04cpu_configuration(original)
    assert json.loads(json.dumps(report)) == report
    report["cpu_manual_revision_check"]["source"]["manual"] = "FORGED"
    report["cpu_manual_revision_check"]["status"] = "E_REFERENCE_ONLY"
    again = inspect_reference_r04cpu_configuration(original)
    assert again["cpu_manual_revision_check"]["source"]["manual"] == "SH-082488ENG-E"
    assert again["cpu_manual_revision_check"]["status"] == "UNVERIFIED_MANUAL_REVISION"
    assert original["cpu_manual_revision"] == "I"
    ref = reference_catalog()
    ref["rncpu_builtin"]["remote_opening_reference"][
        "manual_revision_gate"]["newer_revision_comparison"] = "FORGED"
    assert reference_catalog()["rncpu_builtin"]["remote_opening_reference"][
        "manual_revision_gate"]["newer_revision_comparison"] == "NOT_VERIFIED"


def test_new_revision_gate_cannot_touch_sockets(monkeypatch):
    def reject(*args, **kwargs):
        raise AssertionError("offline source checks must not open a socket")
    monkeypatch.setattr(socket, "socket", reject)
    monkeypatch.setattr(socket, "create_connection", reject)
    r = inspect_reference_r04cpu_configuration({
        "manual_revision": "AD", "cpu_manual_revision": "I",
        "opening_method": "do_not_open_by_program",
    })
    assert r["simulator_network_affected"] is False
