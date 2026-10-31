"""Usage guide: generated tables, size budgets, drift guards and teaching errors."""

import json
from pathlib import Path
import re
import subprocess
import sys

import pytest

from virtual_plc import __version__, guide
from virtual_plc import __main__ as cli
from virtual_plc.commands import COMMAND_NAMES, supported_commands
from virtual_plc.faults import ACTION_FIELDS, FaultPlan
from virtual_plc.memory import Memory
from virtual_plc.profiles import PROFILES

ROOT = Path(__file__).resolve().parents[1]
RAW = "https://raw.githubusercontent.com/greatgc-flow/VirtualPLC/main/"


@pytest.fixture
def parser():
    return cli.build_parser()


def every_text(parser):
    return {topic: guide.render(parser, topic) for topic in (None, *guide.TOPICS)}


def test_every_topic_renders_within_budget(parser):
    for topic, text in every_text(parser).items():
        assert text.isascii(), topic  # consoles with legacy code pages must not fail
        assert len(text.splitlines()) <= (45 if topic is None else 40), topic
        assert len(text) <= 4000, topic


def test_overview_has_the_required_parts(parser):
    text = guide.render(parser)
    for recipe in guide.RECIPES:
        assert recipe in text
    assert "from pymcprotocol import" in text
    assert "Pitfalls" in text
    assert all(topic in text for topic in guide.TOPICS)


def test_every_parser_option_is_in_options_topic_and_json(parser):
    text = guide.render(parser, "options")
    names = {action.option_strings[-1] for action in parser._actions}
    assert {"--port", "--fault-plan", "--help", "--version", "--verbose"} <= names
    assert all(name in text for name in names)
    rows = guide.data(parser, "options")["options"]
    assert {row["name"] for row in rows} == names
    by_name = {row["name"]: row for row in rows}
    assert by_name["--port"]["default"] == 5000
    assert by_name["--profile"]["choices"] == list(PROFILES)
    assert all(row["help"] for row in rows)


def test_overview_lists_every_user_option(parser):
    text = guide.render(parser)
    for action in parser._actions:
        if action.option_strings[-1] not in ("--help", "--version"):
            assert action.option_strings[-1] in text


def test_no_stale_option_names_in_any_text(parser):
    valid = {flag for action in parser._actions for flag in action.option_strings} | {"--json"}
    for topic, text in every_text(parser).items():
        assert set(re.findall(r"--[a-z][a-z0-9-]*", text)) <= valid, topic


def test_profiles_topic_covers_profiles_devices_and_commands(parser):
    text = guide.render(parser, "profiles")
    for profile in PROFILES.values():
        assert profile.name in text
        for device in profile.devices:
            assert re.search(rf"\b{device}\b", text), device
        assert supported_commands(profile)
    for command in {c for p in PROFILES.values() for c in supported_commands(p)}:
        assert f"{command:04X}" in text and command in COMMAND_NAMES
    assert set(COMMAND_NAMES) == {c for p in PROFILES.values() for c in supported_commands(p)}
    data = guide.data(parser, "profiles")
    assert [p["name"] for p in data["profiles"]] == list(PROFILES)
    for entry in data["profiles"]:
        profile = PROFILES[entry["name"]]
        assert entry["wire_class"] == profile.wire_class
        assert [d["name"] for d in entry["devices"]] == list(profile.devices)
        assert {d["kind"] for d in entry["devices"]} <= {"bit", "word", "dword"}


def test_embed_topic_lists_server_keywords(parser):
    import inspect
    from virtual_plc import Server

    text = guide.render(parser, "embed")
    assert all(name in text for name in inspect.signature(Server).parameters)


def test_faults_topic_covers_actions_and_examples_are_valid_plans(parser):
    text = guide.render(parser, "faults")
    assert all(kind in text for kind in ACTION_FIELDS)
    assert set(guide.EFFECTS) == set(ACTION_FIELDS)
    examples = [line for line in text.splitlines() if line.lstrip().startswith("{")]
    assert len(examples) == 3
    for line in examples:
        FaultPlan(json.loads(line)["steps"])


def test_memory_topic_examples_load_and_devices_are_listed(parser):
    text = guide.render(parser, "memory")
    examples = [line for line in text.splitlines() if line.lstrip().startswith("{")]
    assert examples
    for line in examples:
        Memory("iQ-R").load(json.loads(line))
    assert all(re.search(rf"\b{name}\b", text) for name in PROFILES["iQ-R"].devices)


def test_json_output_shapes(parser, capsys):
    for topic, key in [(None, "text"), ("run", "text"), ("options", "options"), ("profiles", "profiles")]:
        assert guide.main([*([topic] if topic else []), "--json"], parser) == 0
        document = json.loads(capsys.readouterr().out)
        assert set(document) >= {"version", "topic", key} and document["version"] == __version__
        assert document["topic"] == (topic or "overview")
        assert ("text" in document) == (key == "text")
    assert document["frames"] == ["3E", "4E"] and document["encodings"] == ["binary", "ascii"]


def test_plain_output_matches_render(parser, capsys):
    assert guide.main(["run"], parser) == 0
    assert capsys.readouterr().out == guide.render(parser, "run") + "\n"


def test_unknown_topic_lists_topics_and_exits_2(parser, capsys):
    assert guide.main(["nope"], parser) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert all(topic in captured.err for topic in guide.TOPICS)


def test_guide_is_dispatched_before_server_options(monkeypatch, capsys):
    monkeypatch.setattr(cli, "Server", lambda *a, **k: pytest.fail("guide must not build a server"))
    assert cli.main(["guide", "options", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["topic"] == "options"


def run_cli(*arguments):
    return subprocess.run([sys.executable, "-m", "virtual_plc", *arguments], cwd=ROOT,
                          capture_output=True, text=True, timeout=20)


def test_subprocess_guide_and_unknown_topic(parser):
    result = run_cli("guide")
    assert result.returncode == 0 and result.stdout == guide.render(parser) + "\n"
    result = run_cli("guide", "nope")
    assert result.returncode == 2 and "troubleshoot" in result.stderr


def test_readme_run_block_matches_guide_recipes(parser):
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    block = re.search(r"<!-- guide:run -->\n```text\n(.*?)\n```\n<!-- /guide:run -->", readme, re.S)
    assert block and block.group(1) == "\n".join(guide.RECIPES)
    assert all(recipe in guide.render(parser, "run") for recipe in guide.RECIPES)
    assert "AI agents: run `virtual-plc guide`" in "\n".join(readme.splitlines()[:12])


def test_readme_option_table_has_every_option(parser):
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "virtual-plc guide options" in readme
    assert "| Option | Default | Meaning |" not in readme  # generated at runtime instead


def test_console_entry_point_dispatches_guide(monkeypatch, capsys):
    from importlib.metadata import entry_points

    entry = next(e for e in entry_points(group="console_scripts") if e.name == "virtual-plc")
    monkeypatch.setattr(sys, "argv", ["virtual-plc", "guide", "client", "--json"])
    assert entry.load()() == 0
    assert json.loads(capsys.readouterr().out)["topic"] == "client"


@pytest.mark.parametrize("topic", guide.TOPICS)
def test_each_topic_through_cli(topic, parser, capsys):
    assert cli.main(["guide", topic]) == 0
    assert capsys.readouterr().out == guide.render(parser, topic) + "\n"


@pytest.mark.parametrize("arguments, topic", [
    (["--profile", "X"], "profiles"),
    (["--port", "abc"], "options"),
    (["--text-pad", "300"], "options"),
    (["--limit", "D:1"], "memory"),
    (["--latch-range", "D:2-1"], "memory"),
    (["--max-points", "0"], "options"),
    (["--password", "x"], "options"),
    (["--bogus"], "options"),
    (["--idle-timeout", "nan"], "options"),
    (["--initial-state", "broken"], "options"),
    (["--ascii-dword-order", "broken"], "options"),
    (["--ascii-numbering", "broken"], "options"),
    (["--limit", "NOPE:0-1"], "memory"),
    (["--latch-range", "NOPE:0-1"], "memory"),
])
def test_invalid_options_end_with_guide_hint(capsys, arguments, topic):
    with pytest.raises(SystemExit) as error:
        cli.main(arguments)
    assert error.value.code == 2
    lines = capsys.readouterr().err.strip().splitlines()
    assert len(lines) == 1
    assert lines[0].endswith(f"; see: virtual-plc guide {topic}")


@pytest.mark.parametrize("content, option, topic", [
    ('{"D": {"0": [70000]}}', "--init", "memory"),
    ("not json", "--init", "memory"),
    (None, "--init", "memory"),
    ('{"steps": [{"action": {"type": "nope"}}]}', "--fault-plan", "faults"),
    ('{"steps":', "--fault-plan", "faults"),
    (None, "--fault-plan", "faults"),
    ('[]', "--init", "memory"),
    ('{"Z": {"0": [1]}}', "--init", "memory"),
    ('{"steps": [null]}', "--fault-plan", "faults"),
])
def test_bad_files_end_with_guide_hint(tmp_path, capsys, content, option, topic):
    path = tmp_path / "input.json"
    if content is not None:
        path.write_text(content, encoding="utf-8")
    with pytest.raises(SystemExit) as error:
        cli.main([option, str(path)])
    assert error.value.code == 2
    lines = capsys.readouterr().err.strip().splitlines()
    assert len(lines) == 1
    assert lines[0].endswith(f"; see: virtual-plc guide {topic}")


def test_agent_files_exist_within_budget_and_are_packaged():
    llms = (ROOT / "llms.txt").read_text(encoding="utf-8")
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert len(llms.splitlines()) <= 30 and len(agents.splitlines()) <= 40
    assert "pip install virtual-plc" in llms and "virtual-plc guide" in llms
    assert " ".join(guide.TOPICS) in llms
    links = re.findall(re.escape(RAW) + r"(\S+?)\)", llms)
    assert links and all((ROOT / link).exists() for link in links)
    assert ".venv" in agents and "pytest" in agents and "guide.py" in agents
    manifest = (ROOT / "MANIFEST.in").read_text(encoding="utf-8")
    assert "llms.txt" in manifest and "AGENTS.md" in manifest


def test_latch_semantics_in_all_usage_docs(parser):
    phrase = "Latch ranges are cleared by latchclear and preserved by remote_run(clear_mode=1)."
    for text in (guide.render(parser, "memory"),
                 (ROOT / "README.md").read_text(encoding="utf-8"),
                 (ROOT / "docs/BEHAVIOR.md").read_text(encoding="utf-8")):
        assert phrase in text
        assert "points latch clear preserves" not in text


def test_client_guidance_is_self_contained(parser):
    client = guide.render(parser, "client")
    assert "pymcprotocol 0.3.0" not in client
    for text in (client, (ROOT / "README.md").read_text(encoding="utf-8")):
        assert 'Type3E(plctype="iQ-R")' in text
        assert "--profile iQ-R --port 5001" in text
        assert 'connect("127.0.0.1", 5001)' in text
    llms = (ROOT / "llms.txt").read_text(encoding="utf-8")
    assert "pip install pymcprotocol" in llms
    assert 'Type3E(plctype="Q")' in llms and 'connect("127.0.0.1", 5000)' in llms
    assert "batches under ~1000 words" in llms


def test_embed_pytest_example_runs(parser):
    text = guide.render(parser, "embed")
    example = text.split("pytest fixture:\n", 1)[1]
    namespace = {}
    exec(__import__("textwrap").dedent(example), namespace)
    fixture = namespace["plc"].__wrapped__()
    server = next(fixture)
    try:
        namespace["test_seeded"](server)
    finally:
        with pytest.raises(StopIteration):
            next(fixture)
