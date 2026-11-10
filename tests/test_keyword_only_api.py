"""#78 keyword-only public API, 0.11.0 step: positional use after `profile` is deprecated.

`Server(host, port, profile, ...)` and `Memory(profile, ...)` keep their leading
parameters positional; every later parameter warns (DeprecationWarning, attributed
to the caller) when passed positionally and becomes keyword-only in 1.0.
Constructors only: no test here binds a socket.
"""

import ast
import inspect
from pathlib import Path
import pydoc
import re
from unittest import mock
import warnings

import pytest

from virtual_plc import Memory, Server
from virtual_plc import __main__ as cli

ROOT = Path(__file__).resolve().parents[1]
HOST = "127.0.0.1"


def _no_warnings(call):
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        return call()


def _one_deprecation(call):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = call()
    assert [w.category for w in caught] == [DeprecationWarning], caught
    return result, caught[0]


# Server ---------------------------------------------------------------------

@pytest.mark.parametrize("args", [(), (HOST,), (HOST, 0), (HOST, 0, "Q")])
def test_server_host_port_profile_stay_positional_without_warning(args):
    server = _no_warnings(lambda: Server(*args))
    assert server.memory.profile.name == "Q"


def test_server_fourth_positional_argument_warns_at_the_caller():
    _, warning = _one_deprecation(lambda: Server(HOST, 0, "Q", None))
    message = str(warning.message)
    assert "Server()" in message and "memory" in message
    assert "keyword-only in 1.0" in message
    assert warning.filename == __file__


def test_server_warning_names_every_positional_extra_and_behaviour_is_unchanged():
    server, warning = _one_deprecation(lambda: Server(HOST, 0, "Q", None, None, 5))
    assert "memory, response_hook, max_points" in str(warning.message)
    assert "idle_timeout" not in str(warning.message)
    assert server._max_points == 5


def test_server_keyword_calls_never_warn():
    memory = Memory(profile="iQ-R")
    server = _no_warnings(lambda: Server(host=HOST, port=0, profile="iQ-R", memory=memory,
                                         max_points=5, initial_state="STOP", tcp_metrics=True))
    assert server.memory is memory and server.state == "STOP"
    _no_warnings(lambda: Server(HOST, 0, "Q", memory=None, max_points=5))


@pytest.mark.parametrize("call", [
    lambda: Server(HOST, 0, memory=None, port=1),
    lambda: Server(HOST, 0, "Q", None, memory=None),
    lambda: Server(HOST, 0, "Q", *([None] * 30)),
])
def test_server_argument_errors_still_raise_type_error_not_a_warning(call):
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        with pytest.raises(TypeError):
            call()


def test_server_duplicate_argument_message_is_unchanged():
    with pytest.raises(TypeError, match=r"Server\.__init__\(\) got multiple values for argument 'memory'"):
        Server(HOST, 0, "Q", None, memory=None)


def test_server_subclass_positional_super_call_warns_at_the_subclass_line():
    class Custom(Server):
        def __init__(self):
            super().__init__(HOST, 0, "Q", None)

    _, warning = _one_deprecation(Custom)
    assert warning.filename == __file__
    assert "memory" in str(warning.message)


# Memory ---------------------------------------------------------------------

def test_memory_profile_stays_positional_without_warning():
    assert _no_warnings(lambda: Memory("iQ-R")).profile.name == "iQ-R"
    assert _no_warnings(Memory).profile.name == "Q"


def test_memory_second_positional_argument_warns_at_the_caller():
    _, warning = _one_deprecation(lambda: Memory("Q", {}))
    message = str(warning.message)
    assert "Memory()" in message and "limits" in message and "max_cells" not in message
    assert "keyword-only in 1.0" in message
    assert warning.filename == __file__


def test_memory_warning_names_both_extras_and_behaviour_is_unchanged():
    memory, warning = _one_deprecation(lambda: Memory("Q", {"D": (0, 9)}, 10))
    assert "limits, max_cells" in str(warning.message)
    assert memory.max_cells == 10 and memory._limits["D"] == (0, 9)


def test_memory_keyword_calls_never_warn():
    memory = _no_warnings(lambda: Memory(profile="Q", limits={"D": (0, 9)}, max_cells=3))
    assert memory.max_cells == 3
    _no_warnings(lambda: Memory("Q", limits={"D": (0, 9)}, max_cells=3))
    _no_warnings(lambda: Memory(max_cells=3))


@pytest.mark.parametrize("call", [
    lambda: Memory("Q", {}, limits={}),
    lambda: Memory("Q", None, None, None),
    lambda: Memory("Q", profile="Q"),
])
def test_memory_argument_errors_still_raise_type_error_not_a_warning(call):
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        with pytest.raises(TypeError):
            call()


# Internal callers emit nothing -----------------------------------------------

def test_memory_load_does_not_warn():
    memory = Memory("Q", limits={"D": (0, 99)}, max_cells=50)
    _no_warnings(lambda: memory.load({"D": {"0": [1, 2]}}))
    assert memory.read_words("D", 0, 2) == [1, 2]


def test_cli_memory_construction_does_not_warn(tmp_path):
    snapshot = tmp_path / "seed.json"
    snapshot.write_text('{"D": {"0": [7]}}', encoding="utf-8")
    captured = {}

    def capture(host, port, **options):
        captured.update(options)
        raise SystemExit(0)

    with mock.patch.object(cli, "Server", capture), pytest.raises(SystemExit):
        _no_warnings(lambda: cli.main(["--init", str(snapshot), "--limit", "D:0-99", "--max-cells", "50"]))
    assert captured["memory"].max_cells == 50
    assert captured["memory"].read_words("D", 0, 1) == [7]


# Introspection stays intact ---------------------------------------------------

def test_signatures_and_help_are_unchanged():
    server = inspect.signature(Server).parameters
    assert list(server)[:4] == ["host", "port", "profile", "memory"]
    assert "udp_rate_limit" in server and server["max_points"].default is None
    assert all(p.kind is p.POSITIONAL_OR_KEYWORD for p in server.values())  # `*` lands in 1.0
    assert list(inspect.signature(Memory).parameters) == ["profile", "limits", "max_cells"]
    assert "udp_rate_limit" in pydoc.render_doc(Server)
    assert "max_cells" in pydoc.render_doc(Memory)


def test_repository_tests_treat_deprecation_warnings_as_errors(pytestconfig):
    filters = pytestconfig.getini("filterwarnings")
    assert "error::DeprecationWarning" in filters
    assert "error::PendingDeprecationWarning" in filters


# Static guard: no positional extras anywhere in the repository ---------------

KEEP = {"Server": 3, "Memory": 1}


def _python_sources():
    for folder in ("virtual_plc", "examples", "tests", "tools"):
        for path in sorted((ROOT / folder).rglob("*.py")):
            if path.resolve() != Path(__file__).resolve():
                yield str(path.relative_to(ROOT)), path.read_text(encoding="utf-8")
    for path in [ROOT / "README.md", *sorted((ROOT / "docs").rglob("*.md")), *sorted((ROOT / "examples").rglob("*.md"))]:
        for number, block in enumerate(re.findall(r"^```python\n(.*?)^```$", path.read_text(encoding="utf-8"), re.M | re.S)):
            yield f"{path.relative_to(ROOT)} block {number}", block


def _positional_extras(source):
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
        if name in KEEP and (len(node.args) > KEEP[name] or any(isinstance(a, ast.Starred) for a in node.args)):
            yield f"{name}() line {node.lineno}"


def test_repository_code_and_documented_snippets_use_keywords_after_profile():
    offenders = [f"{where}: {call}" for where, source in _python_sources() for call in _positional_extras(source)]
    assert offenders == []
