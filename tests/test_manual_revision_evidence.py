"""Offline manual comparison evidence kit: fail-closed, no PDF redistribution.

Test against synthetic PDF headers/text only. The real AG/I original manuals
are NOT bundled, downloaded, or assumed equivalent to AD/E.
"""
import hashlib
import importlib
import json
from pathlib import Path

import pytest


@pytest.fixture
def kit():
    # Tests-first RED: absent until implementation, no import-time collection error.
    return importlib.import_module("tools.manual_revision_evidence")


@pytest.fixture
def pdfs(tmp_path):
    result = {}
    for name in ("ethernet_ad", "ethernet_ag", "cpu_e", "cpu_i"):
        path = tmp_path / (name + ".pdf")
        path.write_bytes(b"%PDF-1.7\n" + name.encode("ascii") + b"\n%%EOF\n")
        result[name] = path
    return result


def test_pdf_fingerprint_real_bytes_and_rejects_nonpdf(kit, pdfs, tmp_path):
    path = pdfs["ethernet_ad"]
    info = kit.fingerprint_pdf(path)
    assert info["bytes"] == path.stat().st_size
    assert info["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert info["file"] == str(path)
    bogus = tmp_path / "bogus.pdf"
    bogus.write_bytes(b"not a PDF")
    with pytest.raises(ValueError, match="PDF"):
        kit.fingerprint_pdf(bogus)
    with pytest.raises((OSError, ValueError)):
        kit.fingerprint_pdf(tmp_path / "missing.pdf")


def test_pdf_fingerprint_rejects_oversized_and_directory(kit, pdfs, tmp_path):
    with pytest.raises(ValueError, match="size"):
        kit.fingerprint_pdf(pdfs["ethernet_ad"], max_bytes=4)
    with pytest.raises((OSError, ValueError)):
        kit.fingerprint_pdf(tmp_path)


def test_pages_preserve_pdf_page_numbers_even_if_empty(kit):
    pages = kit.split_pages("cover\f\fOpening Method A031H\f")
    assert pages == ["cover", "", "Opening Method A031H"]


def test_topic_finder_page_indices_and_bounded_samples(kit):
    pages = kit.split_pages(
        "Cover\fTable of contents External Device Configuration\f"
        "R04CPU External Device Configuration port 5005\f"
        "Data Communication Timer " + "x" * 500 + "\f"
    )
    topics = kit.find_topics(pages, "ethernet", max_hits=2)
    assert topics["external_device_configuration"]["pages"] == [2, 3]
    assert topics["external_device_configuration"]["occurrences"] == 2
    assert len(topics["data_communication_timer"]["examples"][0]) <= 180
    assert all(x >= 1 for x in topics["r04cpu"]["pages"])


def test_generate_evidence_two_source_gates_remain_not_verified(kit, pdfs):
    text = {
        "ethernet_ad": "SH-081257ENG-AD\fExternal Device Configuration R04CPU\fA038H Timer",
        "ethernet_ag": "SH-081257ENG-AG\fExternal Device Configuration R04CPU\fA038H Timer",
        "cpu_e": "SH-082488ENG-E\fOpening Method A031H Remote STOP",
        "cpu_i": "SH-082488ENG-I\fOpening Method A031H Remote RUN",
    }
    def extract(path):
        return text[path.stem]
    report = kit.generate_report({
        "ethernet": (pdfs["ethernet_ad"], pdfs["ethernet_ag"]),
        "cpu": (pdfs["cpu_e"], pdfs["cpu_i"]),
    }, extract=extract)
    assert report["status"] == "SOURCE_CLAUSE_REVIEW_REQUIRED"
    assert report["manual_revision_equivalence"] == "NOT_VERIFIED"
    assert report["physical_hardware_certified"] is False
    assert report["simulator_network_affected"] is False
    assert set(report["pairs"]) == {"ethernet", "cpu"}
    ethernet = report["pairs"]["ethernet"]
    cpu = report["pairs"]["cpu"]
    assert ethernet["older"]["declared_edition"] == "AD"
    assert ethernet["newer"]["declared_edition"] == "AG"
    assert ethernet["older"]["front_matter_edition_candidate"] is True
    assert ethernet["newer"]["front_matter_edition_candidate"] is True
    assert ethernet["topics"]["external_device_configuration"]["older_pages"] == [2]
    assert cpu["older"]["declared_edition"] == "E"
    assert cpu["newer"]["declared_edition"] == "I"
    assert cpu["topics"]["remote_run"]["older_pages"] == []
    assert cpu["topics"]["remote_run"]["newer_pages"] == [2]
    assert cpu["topics"]["remote_run"]["hint"] == "MATCH_COUNT_CHANGED"
    assert cpu["manual_revision_equivalence"] == "NOT_VERIFIED"
    assert json.loads(json.dumps(report)) == report


def test_equal_text_is_not_automatic_source_edition_certification(kit, pdfs):
    def extract(_):
        return "Opening Method A031H Remote STOP"
    report = kit.generate_report({"cpu": (pdfs["cpu_e"], pdfs["cpu_i"])},
                                 extract=extract)
    assert report["manual_revision_equivalence"] == "NOT_VERIFIED"
    assert report["pairs"]["cpu"]["manual_revision_equivalence"] == "NOT_VERIFIED"
    assert report["pairs"]["cpu"]["older"]["front_matter_edition_candidate"] is False
    assert report["pairs"]["cpu"]["newer"]["front_matter_edition_candidate"] is False


@pytest.mark.parametrize("pairs", [{}, {"ethernet": (None, None)},
                                   {"other": ("a", "b")}, {"cpu": ("a",)},
                                   {"cpu": ["a", "b", "c"]}])
def test_malformed_or_missing_pair_fails_closed(kit, pairs):
    with pytest.raises((ValueError, TypeError)):
        kit.generate_report(pairs, extract=lambda _: "text")


def test_extract_pdf_uses_local_subprocess_list_no_shell_and_timeout(kit, pdfs,
                                                                    monkeypatch):
    recorded = {}
    class Completed:
        returncode = 0
        stdout = b"SH-082488ENG-E\fOpening Method"
        stderr = b""
    def fake_run(args, **kwargs):
        recorded["args"] = args
        recorded["kwargs"] = kwargs
        return Completed()
    monkeypatch.setattr(kit.subprocess, "run", fake_run)
    text = kit.extract_pdf_text(pdfs["cpu_e"], executable="pdftotext")
    assert text.endswith("Opening Method")
    assert recorded["args"] == ["pdftotext", "-layout", "-enc", "UTF-8",
                                 str(pdfs["cpu_e"]), "-"]
    assert recorded["kwargs"]["timeout"] >= 5
    assert recorded["kwargs"].get("shell") is not True


def test_extract_pdf_errors_remain_errors(kit, pdfs, monkeypatch):
    class Bad:
        returncode = 1
        stdout = b""
        stderr = b"bad PDF"
    monkeypatch.setattr(kit.subprocess, "run", lambda *a, **kw: Bad())
    with pytest.raises(ValueError, match="pdftotext"):
        kit.extract_pdf_text(pdfs["cpu_i"])


def test_cli_requires_complete_pair_and_does_not_use_network(kit, pdfs,
                                                             monkeypatch, capsys,
                                                             tmp_path):
    monkeypatch.setattr(kit, "extract_pdf_text",
                        lambda path, executable="pdftotext":
                        "SH-082488ENG-" + ("E" if path.stem == "cpu_e" else "I")
                        + "\fOpening Method A031H")
    output = tmp_path / "evidence.json"
    assert kit.main(["--cpu-e", str(pdfs["cpu_e"]), "--cpu-i", str(pdfs["cpu_i"]),
                     "--output", str(output)]) == 0
    shown = capsys.readouterr().out
    assert shown == output.read_text(encoding="utf-8")
    assert json.loads(shown)["manual_revision_equivalence"] == "NOT_VERIFIED"
    with pytest.raises(SystemExit) as error:
        kit.main(["--cpu-e", str(pdfs["cpu_e"])])
    assert error.value.code == 2


def test_no_pdf_bytes_or_full_text_exported_in_report(kit, pdfs):
    source = "SH-081257ENG-AG\fExternal Device Configuration " + "SECRET" * 150
    report = kit.generate_report({"ethernet": (pdfs["ethernet_ad"],
                                               pdfs["ethernet_ag"])},
                                 extract=lambda _: source)
    payload = json.dumps(report)
    assert "%PDF" not in payload
    assert "SECRET" * 50 not in payload
    assert len(report["pairs"]["ethernet"]["topics"][
        "external_device_configuration"]["older_examples"][0]) <= 180
