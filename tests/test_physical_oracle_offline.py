"""Physical-oracle preparation: strictly OFFLINE manual-vector comparison.

There must be no network access or PLC command execution in the tool.
These manual-derived examples are NOT measured physical PLC responses.
"""
import importlib
import json
import socket

import pytest


EXPECTED = {
    "1e_binary_model": ("15FF0000", "F3"),
    "1e_ascii_model": ("3135464630303030", "4633"),
    "1e_binary_loopback": ("16FF0000054142434445", "054142434445"),
    "1e_ascii_loopback": ("3136464630303030303534313432343334343435",
                          "303534313432343334343435"),
}
ORIGIN = "simulator"
TARGET = {"model": "VirtualPLC", "interface": "synthetic-1e", "firmware": "unverified"}


@pytest.fixture
def api():
    # Deferred import enables a tests-first RED without stopping legacy collection.
    return importlib.import_module("virtual_plc.oracle")


def recorded(api, overrides=None):
    catalog = api.catalog()
    data = {
        "schema": "virtualplc.oracle.observations.v1",
        "origin": ORIGIN,
        "target": TARGET.copy(),
        "records": [
            {"case_id": item["id"], "request_hex": item["request_hex"],
             "response_hex": item["expected_hex"]}
            for item in catalog["cases"]
        ],
    }
    if overrides:
        overrides(data)
    return data


def test_manual_vectors_are_literal_readonly_model_and_loopback(api):
    catalog = api.catalog()
    assert catalog["schema"] == "virtualplc.oracle.plan.v1"
    assert catalog["status"] == "MANUAL_DERIVED_NOT_PHYSICAL"
    assert {row["id"]: (row["request_hex"], row["expected_hex"])
            for row in catalog["cases"]} == EXPECTED
    assert all(row["operation"] in ("read_model", "loopback") for row in catalog["cases"])
    assert all(row["manual_reference"] and row["manual_page"] for row in catalog["cases"])
    assert all(row["id"].startswith("1e_") for row in catalog["cases"])


def test_template_must_not_claim_observed_hardware_or_contain_fake_capture(api):
    template = api.observation_template()
    assert template["origin"] == "unspecified"
    assert template["target"]["model"] == ""
    assert template["target"]["interface"] == ""
    assert template["target"]["firmware"] == ""
    assert all(x["response_hex"] is None for x in template["records"])
    with pytest.raises(ValueError):
        api.compare_observations(template)


def test_offline_comparison_matches_manual_but_never_certifies_physical_plc(api, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("offline oracle must never create network connections")
    monkeypatch.setattr(socket, "create_connection", forbidden)
    data = recorded(api)
    report = api.compare_observations(data)
    assert report["schema"] == "virtualplc.oracle.report.v1"
    assert report["origin"] == "simulator"
    assert report["matches"] == 4
    assert report["mismatches"] == 0
    assert report["missing"] == 0
    assert report["complete_manual_vector_match"] is True
    assert report["physical_hardware_certified"] is False
    assert {item["status"] for item in report["cases"]} == {"match"}
    assert all("observed_sha256" in item for item in report["cases"])
    assert "response_hex" not in json.dumps(report)


def test_single_byte_mismatch_is_detected_and_no_raw_payload_is_reported(api):
    data = recorded(api)
    data["records"][0]["response_hex"] = "DEADBEEF"
    report = api.compare_observations(data)
    assert report["matches"] == 3
    assert report["mismatches"] == 1
    assert report["complete_manual_vector_match"] is False
    assert next(item for item in report["cases"] if item["id"] == "1e_binary_model")["status"] == "mismatch"
    assert "DEADBEEF" not in json.dumps(report)


def test_missing_observations_are_not_false_pass(api):
    data = recorded(api)
    data["records"].pop()
    report = api.compare_observations(data)
    assert report["matches"] == 3
    assert report["missing"] == 1
    assert report["complete_manual_vector_match"] is False
    assert {row["status"] for row in report["cases"]} == {"match", "missing"}


@pytest.mark.parametrize("mutate", [
    lambda d: d.update(records=None),
    lambda d: d.update(records=[]),  # no evidence is not an accepted oracle
    lambda d: d.update(origin="certified"),
    lambda d: d.update(schema="wrong"),
    lambda d: d["target"].update(model=""),
    lambda d: d["target"].update(firmware=None),
    lambda d: d["records"].append(d["records"][0].copy()),
    lambda d: d["records"][0].update(case_id="1e_binary_write"),
    lambda d: d["records"][0].update(request_hex="14FF0000"),
    lambda d: d["records"][0].update(response_hex="XYZ"),
    lambda d: d["records"][0].update(response_hex=None),
])
def test_fail_closed_on_invalid_evidence(api, mutate):
    data = recorded(api)
    mutate(data)
    with pytest.raises(ValueError):
        api.compare_observations(data)


def test_self_attested_physical_origin_is_not_hardware_certification(api):
    data = recorded(api)
    data["origin"] = "physical_plc"
    data["target"] = {"model": "FX5U", "interface": "cpu_builtin",
                      "firmware": "user-supplied-version"}
    report = api.compare_observations(data)
    assert report["origin"] == "physical_plc"
    assert report["physical_hardware_certified"] is False
    assert report["complete_manual_vector_match"] is True


def test_cli_plan_and_template_json_never_contact_hardware(api, capsys, monkeypatch):
    monkeypatch.setattr(socket, "create_connection", lambda *x, **y: pytest.fail("no network"))
    assert api.main(["plan"]) == 0
    assert json.loads(capsys.readouterr().out)["schema"] == "virtualplc.oracle.plan.v1"
    assert api.main(["template"]) == 0
    assert json.loads(capsys.readouterr().out)["origin"] == "unspecified"


def test_cli_report_file_equals_screen_output_byte_for_byte(api, tmp_path, capsys):
    evidence_path = tmp_path / "observations.json"
    evidence_path.write_text(json.dumps(recorded(api)), encoding="utf-8")
    report_path = tmp_path / "report.json"
    assert api.main(["compare", str(evidence_path), "--report", str(report_path)]) == 0
    screen = capsys.readouterr().out
    assert screen == report_path.read_text(encoding="utf-8")
    assert json.loads(screen)["physical_hardware_certified"] is False


def test_bad_input_cannot_overwrite_existing_report(api, tmp_path, capsys):
    evidence_path = tmp_path / "invalid.json"
    evidence_path.write_text('{"records":null}', encoding="utf-8")
    report_path = tmp_path / "previous.json"
    report_path.write_text('{"safe":true}\n', encoding="utf-8")
    assert api.main(["compare", str(evidence_path), "--report", str(report_path)]) == 2
    assert report_path.read_text(encoding="utf-8") == '{"safe":true}\n'
    out = capsys.readouterr()
    assert not out.out
    assert "invalid" in out.err.lower() or "error" in out.err.lower()


def test_cli_exit_one_for_mismatch_or_missing(api, tmp_path, capsys):
    evidence_path = tmp_path / "observations.json"
    data = recorded(api)
    data["records"] = data["records"][:1]
    evidence_path.write_text(json.dumps(data), encoding="utf-8")
    assert api.main(["compare", str(evidence_path)]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["matches"] == 1 and result["missing"] == 3


def test_observation_size_bound_and_hex_validation(api):
    data = recorded(api)
    data["records"][0]["response_hex"] = "AA" * 9000
    with pytest.raises(ValueError):
        api.compare_observations(data)
