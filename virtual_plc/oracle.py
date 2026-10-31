"""Offline, read-only Mitsubishi SLMP 1E manufacturer-vector comparison.

Never opens network sockets, sends PLC commands or certifies hardware.
Manual source: Mitsubishi JY997D56001-K, printed pp.134-136.
Use: python -m virtual_plc.oracle plan|template|compare OBS.json [--report REPORT.json]
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile


MANUAL = "Mitsubishi JY997D56001-K (MELSEC iQ-F FX5 SLMP)"
MANUAL_URL = "https://dl.mitsubishielectric.com/dl/fa/document/manual/plcf/jy997d56001/jy997d56001k.pdf"
# Literal manual frames, not captured physical-PLC responses.
# ASCII fields are themselves bytes: e.g. b"15FF0000" -> hex 3135464630303030.
_CASES = (
    ("1e_binary_model", "15FF0000", "F3", "read_model", 134),
    ("1e_ascii_model", "3135464630303030", "4633", "read_model", 134),
    ("1e_binary_loopback", "16FF0000054142434445",
     "054142434445", "loopback", 136),
    ("1e_ascii_loopback", "3136464630303030303534313432343334343435",
     "303534313432343334343435", "loopback", 136),
)
MAX_INPUT_BYTES = 1024 * 1024
MAX_WIRE_BYTES = 8192


def catalog():
    """Fresh, canonical test-vector plan (no write/run/stop commands)."""
    return {
        "schema": "virtualplc.oracle.plan.v1",
        "status": "MANUAL_DERIVED_NOT_PHYSICAL",
        "manual": MANUAL,
        "manual_url": MANUAL_URL,
        "network_access": False,
        "physical_hardware_certified": False,
        "cases": [
            {"id": name, "request_hex": request, "expected_hex": expected,
             "operation": operation, "manual_reference": MANUAL,
             "manual_page": page, "provenance": "official_manual_example"}
            for name, request, expected, operation, page in _CASES
        ],
    }


def observation_template():
    """Intentionally incomplete template: never invent physical captures."""
    return {
        "schema": "virtualplc.oracle.observations.v1",
        "origin": "unspecified",
        "target": {"model": "", "interface": "", "firmware": ""},
        "records": [
            {"case_id": row["id"], "request_hex": row["request_hex"],
             "response_hex": None}
            for row in catalog()["cases"]
        ],
    }


def _wire(value, field):
    if not isinstance(value, str):
        raise ValueError("{} must be a hexadecimal string".format(field))
    compact = "".join(value.split())
    if len(compact) > MAX_WIRE_BYTES * 2 or len(compact) % 2:
        raise ValueError("{} has invalid or oversized length".format(field))
    try:
        return bytes.fromhex(compact)
    except ValueError:
        raise ValueError("{} is not hexadecimal".format(field))


def _digest(value):
    return hashlib.sha256(value).hexdigest()


def _check_target(target):
    if not isinstance(target, dict):
        raise ValueError("target must be a nonempty model/interface/firmware object")
    metadata = {}
    for name in ("model", "interface", "firmware"):
        value = target.get(name)
        if (not isinstance(value, str) or not value.strip() or
                len(value) > 256 or not value.isprintable()):
            raise ValueError("target.{} requires a printable nonempty string".format(name))
        metadata[name] = value
    # Raw device details stay in the local observation file, not the report.
    canonical = json.dumps(metadata, sort_keys=True, ensure_ascii=True,
                           separators=(",", ":")).encode("utf-8")
    return _digest(canonical)


def compare_observations(evidence):
    """Pure comparison: exact manual response bytes vs user-supplied bytes.

    A match only establishes equality with these narrow reference vectors.
    It does NOT certify a physical device or the user's stated capture origin.
    """
    if not isinstance(evidence, dict) or evidence.get("schema") != "virtualplc.oracle.observations.v1":
        raise ValueError("invalid observations schema")
    origin = evidence.get("origin")
    if origin not in ("simulator", "manual", "physical_plc"):
        raise ValueError("invalid origin; use simulator, manual, or physical_plc")
    target_sha256 = _check_target(evidence.get("target"))
    records = evidence.get("records")
    if not isinstance(records, list) or not 1 <= len(records) <= len(_CASES):
        raise ValueError("invalid records: require 1..{} observation items".format(len(_CASES)))

    known = {case[0]: case for case in _CASES}
    observations = {}
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("invalid record object")
        key = record.get("case_id")
        if not isinstance(key, str) or key not in known:
            raise ValueError("invalid or unsupported case_id")
        if key in observations:
            raise ValueError("duplicate case_id")
        reference = known[key]
        sent = _wire(record.get("request_hex"), "request_hex")
        if sent != bytes.fromhex(reference[1]):
            raise ValueError("request_hex differs from read-only reference vector")
        observations[key] = _wire(record.get("response_hex"), "response_hex")

    matched = mismatched = missing = 0
    results = []
    for key, request, expected, operation, page in _CASES:
        measured = observations.get(key)
        if measured is None:
            status = "missing"
            missing += 1
        elif measured == bytes.fromhex(expected):
            status = "match"
            matched += 1
        else:
            status = "mismatch"
            mismatched += 1
        results.append({
            "id": key,
            "status": status,
            "operation": operation,
            "request_sha256": _digest(bytes.fromhex(request)),
            "expected_sha256": _digest(bytes.fromhex(expected)),
            "observed_sha256": _digest(measured) if measured is not None else None,
            "observed_length": len(measured) if measured is not None else None,
            "manual_page": page,
        })
    return {
        "schema": "virtualplc.oracle.report.v1",
        "source": "self_reported_offline_observations",
        "origin": origin,
        "target_sha256": target_sha256,
        "manual": MANUAL,
        "matches": matched,
        "mismatches": mismatched,
        "missing": missing,
        "complete_manual_vector_match": matched == len(_CASES) and mismatched == 0 and missing == 0,
        "physical_hardware_certified": False,
        "network_access": False,
        "cases": results,
    }


def _read_json(path):
    with open(path, "rb") as stream:
        content = stream.read(MAX_INPUT_BYTES + 1)
    if len(content) > MAX_INPUT_BYTES:
        raise ValueError("invalid observations: input file exceeds 1 MiB")
    def no_duplicate_keys(pairs):
        result = {}
        for name, value in pairs:
            if name in result:
                raise ValueError("invalid observations: duplicate JSON key")
            result[name] = value
        return result
    return json.loads(content.decode("utf-8"), object_pairs_hook=no_duplicate_keys)


def _render(value):
    return json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True) + "\n"


def _write_report(path, content):
    """Atomic replacement; bytes exactly match what gets printed to console."""
    destination = Path(path)
    fd, temporary = tempfile.mkstemp(prefix="." + destination.name + ".",
                                      suffix=".tmp", dir=str(destination.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m virtual_plc.oracle",
        description="OFFLINE read-only 1E manual-vector comparison; never contacts PLC hardware",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("plan", help="print read-only manufacturer-derived vectors")
    commands.add_parser("template", help="print deliberately incomplete capture template")
    compare = commands.add_parser("compare", help="compare manually collected observations offline")
    compare.add_argument("observations", help="local JSON observations (no network collection)")
    compare.add_argument("--report", metavar="FILE",
                         help="atomically save the exact JSON printed to stdout")
    arguments = parser.parse_args(argv)
    if arguments.command == "plan":
        sys.stdout.write(_render(catalog()))
        return 0
    if arguments.command == "template":
        sys.stdout.write(_render(observation_template()))
        return 0
    try:
        if arguments.report and Path(arguments.report).resolve() == Path(arguments.observations).resolve():
            raise ValueError("invalid report: cannot overwrite the observations file")
        result = compare_observations(_read_json(arguments.observations))
        output = _render(result)
        if arguments.report:
            _write_report(arguments.report, output)
    except (ValueError, OSError, UnicodeError) as error:
        message = " ".join(str(error).split())
        print("physical-oracle: invalid evidence or report: " + message, file=sys.stderr)
        return 2
    sys.stdout.write(output)
    return 0 if result["complete_manual_vector_match"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
