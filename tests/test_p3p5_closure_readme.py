"""Execute every README ```python block and parse every ```json block.

Convention: a block that is not self-contained carries `<!-- test:skip REASON -->`
on the line directly above its opening fence. Recipe blocks that connect to the
quickstart ports 5000 (Q, --text-pad 0x20) and 5001 (iQ-R, STOP) run against a
matching Server bound to a free port; the literal port is rewritten.
"""

import json
from pathlib import Path
import re
from unittest import mock

import pytest

from virtual_plc import FaultPlan, Memory, Server, guide
from virtual_plc import __main__ as cli

ROOT = Path(__file__).resolve().parents[1]
FENCE = re.compile(r"^```(\w+)\n(.*?)^```$", re.M | re.S)
SKIP = re.compile(r"<!-- test:skip (\S.*?) -->\n\Z")


class _Captured(Exception):
    pass


def _recipe_server(recipe):
    """(host, port, Server kwargs) exactly as the CLI maps the recipe's flags; never binds."""
    def capture(host, port, **options):
        raise _Captured(host, port, options)
    with mock.patch.object(cli, "Server", capture):
        try:
            cli.main(recipe.split()[1:])
        except _Captured as captured:
            return captured.args
    raise AssertionError(f"recipe did not construct a Server: {recipe}")


def _recipe_servers():
    servers = {}
    for recipe in guide.RECIPES:
        if any(argument.endswith(".json") for argument in recipe.split()):
            continue  # file-based recipe; its files are not part of the README blocks
        host, port, options = _recipe_server(recipe)
        servers[port] = lambda host=host, options=options: Server(host, 0, **options)
    return servers


# Derived from guide.RECIPES: dropping e.g. `--initial-state STOP` there is caught here.
RECIPE_SERVERS = _recipe_servers()


def test_recipe_servers_cover_quickstart_ports():
    assert set(RECIPE_SERVERS) == {5000, 5001}


def _blocks(language):
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    found = []
    for match in FENCE.finditer(text):
        if match.group(1) != language:
            continue
        line = text.count("\n", 0, match.start()) + 1
        skip = SKIP.search(text[:match.start()].rsplit("\n", 2)[-2] + "\n")
        found.append(pytest.param(match.group(2), skip and skip.group(1), id=f"README.md:{line}"))
    return found


def test_readme_has_python_and_json_blocks():
    assert len(_blocks("python")) >= 5 and len(_blocks("json")) >= 2


@pytest.mark.parametrize("source, skip", _blocks("python"))
def test_readme_python_block_runs(source, skip):
    if skip:
        pytest.skip(skip)
    ports = [int(port) for port in re.findall(r'connect\("127\.0\.0\.1", (\d+)\)', source)]
    assert set(ports) <= set(RECIPE_SERVERS), f"untagged block needs an unknown server: {ports}"
    if not ports:
        exec(compile(source, "README.md", "exec"), {"__name__": "readme_block"})
        return
    (port,) = set(ports)
    with RECIPE_SERVERS[port]() as server:
        source = source.replace(f'"127.0.0.1", {port})', f'"127.0.0.1", {server.address[1]})')
        exec(compile(source, "README.md", "exec"), {"__name__": "readme_block"})


@pytest.mark.parametrize("source, skip", _blocks("json"))
def test_readme_json_block_is_valid(source, skip):
    document = json.loads(source)
    if "steps" in document:
        FaultPlan(document["steps"])
    else:
        Memory().load(document)
