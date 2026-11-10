"""Documentation closure and SSOT alignment checks (stdlib only)."""

from pathlib import Path
import re

import virtual_plc
from virtual_plc import commands, guide, one_e
from virtual_plc.server import is_loopback_host

ROOT = Path(__file__).resolve().parents[1]


def test_design_points_to_safety_predicate_and_cli_ssot():
    design = (ROOT / "docs/DESIGN.md").read_text(encoding="utf-8")
    assert is_loopback_host.__name__ in design
    assert "build_parser is the SSOT" in design
    assert "virtual-plc guide options" in design


def _supported_1e_commands():
    supported = []
    for byte in range(256):
        try:
            parsed = one_e._command_and_wire(bytes([byte]))
        except ValueError:
            continue
        if parsed == (byte, "binary"):
            supported.append(byte)
    return tuple(supported)


def _wire_end_codes():
    codes = {int(code) for code in commands.EndCode} | set(one_e.ERROR.values())
    return tuple(sorted(codes))


def test_readme_guide_table_covers_all_topics():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    table_lines = [
        line for line in readme.splitlines()
        if line.startswith("| `virtual-plc guide ")
    ]
    table_text = "\n".join(table_lines)
    missing = [
        topic for topic in guide.TOPICS
        if f"`virtual-plc guide {topic}`" not in table_text
    ]
    assert not missing, f"README guide table missing topics: {missing}"


def test_one_e_commands_documented_in_llms_and_behavior():
    commands_1e = _supported_1e_commands()
    assert commands_1e, "expected supported 1E command bytes from one_e"
    for rel_path in ("llms.txt", "docs/BEHAVIOR.md"):
        text = (ROOT / rel_path).read_text(encoding="utf-8")
        missing = [
            f"0x{cmd:02X}" for cmd in commands_1e
            if not re.search(rf"\b{cmd:02X}H\b", text)
        ]
        assert not missing, f"{rel_path} missing 1E command codes: {missing}"


def test_public_exports_documented_in_behavior_and_design():
    assert virtual_plc.__all__, "expected non-empty virtual_plc.__all__"
    for rel_path in ("docs/BEHAVIOR.md", "docs/DESIGN.md"):
        text = (ROOT / rel_path).read_text(encoding="utf-8")
        missing = [
            name for name in virtual_plc.__all__
            if not re.search(rf"\b{re.escape(name)}\b", text)
        ]
        assert not missing, f"{rel_path} missing public exports: {missing}"


def test_wire_end_codes_documented_in_behavior():
    behavior = (ROOT / "docs/BEHAVIOR.md").read_text(encoding="utf-8")
    missing = [
        f"0x{code:04X}" for code in _wire_end_codes()
        if not re.search(rf"\b(?:0x)?{code:04X}H?\b", behavior)
    ]
    assert not missing, f"docs/BEHAVIOR.md missing wire end codes: {missing}"


def test_no_stale_policy_phrases_in_behavior_and_design():
    stale_phrases = (
        "only supported numbering policy",
        "1E are still unsupported",
    )
    for rel_path in ("docs/BEHAVIOR.md", "docs/DESIGN.md"):
        text = (ROOT / rel_path).read_text(encoding="utf-8")
        found = [phrase for phrase in stale_phrases if phrase in text]
        assert not found, f"{rel_path} contains stale phrases: {found}"


def test_guide_divergences_1e_points_to_behavior_without_command_enumeration():
    text = guide.DIVERGENCES
    assert "--slmp-1e" in text
    assert "docs/BEHAVIOR.md#slmp-1e-transport-opt-in" in text
    leaked = [
        f"{cmd:02X}" for cmd in _supported_1e_commands()
        if re.search(rf"\b{cmd:02X}H?\b", text)
    ]
    assert not leaked, f"guide.DIVERGENCES enumerates 1E command bytes: {leaked}"


def test_behavior_export_sentence_matches_package_all():
    text = (ROOT / "docs/BEHAVIOR.md").read_text(encoding="utf-8")
    names = [f"`{name}`" for name in virtual_plc.__all__]
    sentence = "The package exports " + ", ".join(names[:-1]) + " and " + names[-1] + "."
    assert sentence in " ".join(text.split())
