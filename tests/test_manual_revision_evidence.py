"""Offline manual comparison evidence kit: fail-closed, no PDF redistribution.

Test against synthetic PDF headers/text only. The real AG/I original manuals
are NOT bundled, downloaded, or assumed equivalent to AD/E.
"""
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path

import pytest


@pytest.fixture
def kit():
    # Load the dev-only tool by path: `tools` is not an installed package, and the
    # sdist CI run uses `python -I`, which keeps the source tree off sys.path.
    path = Path(__file__).resolve().parents[1] / "tools" / "manual_revision_evidence.py"
    spec = importlib.util.spec_from_file_location("tools.manual_revision_evidence", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def test_same_pdf_path_cannot_masquerade_as_both_editions(kit, pdfs):
    """Even if text extraction differs, a single source cannot be AD and AG."""
    one = pdfs["ethernet_ad"]
    with pytest.raises(ValueError, match="duplicate.*PDF"):
        kit.generate_report(
            {"ethernet": (one, one)},
            extract=lambda path: "SH-081257ENG-AD\fExternal Device Configuration",
        )


def test_byte_identical_distinct_files_rejected_across_edition_pair(kit, pdfs):
    """Two different names are not independent evidence when bytes match."""
    pdfs["cpu_i"].write_bytes(pdfs["cpu_e"].read_bytes())
    with pytest.raises(ValueError, match="duplicate.*PDF"):
        kit.generate_report(
            {"cpu": (pdfs["cpu_e"], pdfs["cpu_i"])},
            extract=lambda path: "Opening Method A031H",
        )


def test_duplicate_evidence_rejected_even_when_manual_family_differs(kit, pdfs):
    """An incorrectly reused source across manual families is not a valid pack."""
    pdfs["cpu_e"].write_bytes(pdfs["ethernet_ad"].read_bytes())
    with pytest.raises(ValueError, match="duplicate.*PDF"):
        kit.generate_report({
            "ethernet": (pdfs["ethernet_ad"], pdfs["ethernet_ag"]),
            "cpu": (pdfs["cpu_e"], pdfs["cpu_i"]),
        }, extract=lambda path: "Opening Method A031H")


def test_pdf_replaced_during_extraction_rejects_even_equal_size(kit, pdfs):
    """Recorded SHA must refer to the exact bytes used for extraction."""
    source = pdfs["cpu_i"]
    before = source.read_bytes()

    def unsafe_extract(path):
        if path == source:
            payload = bytearray(before)
            payload[-6] ^= 1  # Same byte length, different SHA-256
            path.write_bytes(bytes(payload))
        return "Opening Method A031H"

    with pytest.raises(ValueError, match="changed during extraction"):
        kit.generate_report(
            {"cpu": (pdfs["cpu_e"], source)},
            extract=unsafe_extract,
        )
    assert source.stat().st_size == len(before)


def test_stable_sources_remain_read_only_and_not_verified(kit, pdfs):
    """New checks must not mutate input or accidentally certify parity."""
    original = {k: p.read_bytes() for k, p in pdfs.items()}
    report = kit.generate_report({
        "ethernet": (pdfs["ethernet_ad"], pdfs["ethernet_ag"]),
        "cpu": (pdfs["cpu_e"], pdfs["cpu_i"]),
    }, extract=lambda path: "Opening Method A031H")
    assert report["manual_revision_equivalence"] == "NOT_VERIFIED"
    assert report["physical_hardware_certified"] is False
    assert set(report["pairs"]) == {"cpu", "ethernet"}
    assert {k: p.read_bytes() for k, p in pdfs.items()} == original


def _mock_pdf_extract_for_atomic_output(kit, monkeypatch):
    """Local-only fixture; never touches network, real manuals or a PLC."""
    monkeypatch.setattr(
        kit, "extract_pdf_text",
        lambda path, executable="pdftotext": "SH-082488ENG-"
        + ("E" if path.stem == "cpu_e" else "I")
        + "\fOpening Method A031H",
    )


def test_atomic_output_preserves_prior_evidence_if_publish_fails(
        kit, pdfs, tmp_path, monkeypatch, capsys):
    """A failing atomic replacement must not truncate an existing report."""
    import os
    _mock_pdf_extract_for_atomic_output(kit, monkeypatch)
    output = tmp_path / "evidence.json"
    output.write_text("previous verified evidence\n", encoding="utf-8")

    def deny_replace(source, destination):
        raise OSError("simulated replace failure")

    monkeypatch.setattr(os, "replace", deny_replace)
    with pytest.raises(SystemExit) as exc:
        kit.main(["--cpu-e", str(pdfs["cpu_e"]), "--cpu-i", str(pdfs["cpu_i"]),
                  "--output", str(output), "--overwrite"])
    assert exc.value.code == 2
    assert output.read_text(encoding="utf-8") == "previous verified evidence\n"
    assert capsys.readouterr().out == ""
    assert list(tmp_path.glob(".evidence.json.*.tmp")) == []


def test_atomic_success_commits_complete_stdout_identical_json(
        kit, pdfs, tmp_path, monkeypatch, capsys):
    """Report becomes visible in one replacement, identical to console proof."""
    import os
    _mock_pdf_extract_for_atomic_output(kit, monkeypatch)
    output = tmp_path / "evidence.json"
    output.write_text("old report\n", encoding="utf-8")
    real_replace = os.replace
    calls = []

    def record_replace(source, destination):
        calls.append((Path(source), Path(destination)))
        return real_replace(source, destination)

    monkeypatch.setattr(os, "replace", record_replace)
    assert kit.main(["--cpu-e", str(pdfs["cpu_e"]), "--cpu-i", str(pdfs["cpu_i"]),
                     "--output", str(output), "--overwrite"]) == 0
    shown = capsys.readouterr().out
    assert shown == output.read_text(encoding="utf-8")
    assert json.loads(shown)["manual_revision_equivalence"] == "NOT_VERIFIED"
    assert len(calls) == 1
    assert calls[0][1] == output
    assert calls[0][0].parent == tmp_path
    assert list(tmp_path.glob(".evidence.json.*.tmp")) == []


def test_atomic_new_report_refuses_concurrent_destination_creation(
        kit, pdfs, tmp_path, monkeypatch, capsys):
    """No --overwrite must never replace a concurrent writer's report."""
    import os
    _mock_pdf_extract_for_atomic_output(kit, monkeypatch)
    output = tmp_path / "evidence.json"

    def concurrent_create(source, destination):
        output.write_text("another writer\n", encoding="utf-8")
        raise FileExistsError("destination created concurrently")

    monkeypatch.setattr(os, "link", concurrent_create)
    with pytest.raises(SystemExit) as exc:
        kit.main(["--cpu-e", str(pdfs["cpu_e"]), "--cpu-i", str(pdfs["cpu_i"]),
                  "--output", str(output)])
    assert exc.value.code == 2
    assert output.read_text(encoding="utf-8") == "another writer\n"
    assert capsys.readouterr().out == ""
    assert list(tmp_path.glob(".evidence.json.*.tmp")) == []



def test_cross_source_late_mutation_invalidates_earlier_pdf(kit, pdfs):
    """Later edition extraction must not invalidate an earlier hashed source."""
    older, newer = pdfs["cpu_e"], pdfs["cpu_i"]

    def extract(path):
        if path == newer:
            older.write_bytes(older.read_bytes() + b"changed after prior extraction")
        return "SH-082488ENG-E Opening Method A031H"

    with pytest.raises(ValueError, match="PDF changed"):
        kit.generate_report({"cpu": (older, newer)}, extract=extract)


def test_cross_family_late_mutation_invalidates_prior_pdf(kit, pdfs):
    """The final audit also spans both separate manual families."""
    earlier, later = pdfs["cpu_e"], pdfs["ethernet_ag"]

    def extract(path):
        if path == later:
            earlier.write_bytes(earlier.read_bytes() + b"late cross-family mutation")
        return "R04CPU External Device Configuration"

    with pytest.raises(ValueError, match="PDF changed"):
        kit.generate_report({
            "cpu": (pdfs["cpu_e"], pdfs["cpu_i"]),
            "ethernet": (pdfs["ethernet_ad"], pdfs["ethernet_ag"]),
        }, extract=extract)


def test_cross_source_final_audit_keeps_stable_json_and_originals(kit, pdfs):
    """The new audit must not alter the report schema or original PDFs."""
    original = {key: path.read_bytes() for key, path in pdfs.items()}
    report = kit.generate_report({
        "cpu": (pdfs["cpu_e"], pdfs["cpu_i"]),
        "ethernet": (pdfs["ethernet_ad"], pdfs["ethernet_ag"]),
    }, extract=lambda _: "Opening Method A031H R04CPU")
    assert report["manual_revision_equivalence"] == "NOT_VERIFIED"
    assert set(report["pairs"]) == {"cpu", "ethernet"}
    assert {key: path.read_bytes() for key, path in pdfs.items()} == original


@pytest.mark.parametrize("invalid_role", ("duplicate_bytes", "missing_file", "malformed_pair"))
def test_pack_preflight_fails_before_extraction_for_invalid_later_source(
        kit, pdfs, invalid_role):
    """All source roles must be safe before any expensive pdftotext call."""
    if invalid_role == "duplicate_bytes":
        pdfs["ethernet_ag"].write_bytes(pdfs["ethernet_ad"].read_bytes())
    elif invalid_role == "missing_file":
        pdfs["ethernet_ag"].unlink()

    ethernet = (pdfs["ethernet_ad"], pdfs["ethernet_ag"])
    if invalid_role == "malformed_pair":
        ethernet = (pdfs["ethernet_ad"],)
    calls = []

    def extract(path):
        calls.append(path.stem)
        return "R04CPU Opening Method A031H"

    with pytest.raises(ValueError):
        kit.generate_report({
            "cpu": (pdfs["cpu_e"], pdfs["cpu_i"]),
            "ethernet": ethernet,
        }, extract=extract)
    assert calls == [], "invalid evidence packs must never invoke the extractor"


def test_pack_preflight_keeps_one_extraction_per_valid_role(kit, pdfs):
    calls = []

    def extract(path):
        calls.append(path.stem)
        return "R04CPU Opening Method A031H"

    report = kit.generate_report({
        "ethernet": (pdfs["ethernet_ad"], pdfs["ethernet_ag"]),
        "cpu": (pdfs["cpu_e"], pdfs["cpu_i"]),
    }, extract=extract)
    assert calls == ["cpu_e", "cpu_i", "ethernet_ad", "ethernet_ag"]
    assert report["manual_revision_equivalence"] == "NOT_VERIFIED"
