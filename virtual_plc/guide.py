"""Token-efficient usage guide for humans and AI agents: `virtual-plc guide [TOPIC] [--json]`.

Hand-written prose lives here. The option, profile, command, device and fault
tables are generated from the argparse parser and from the profile, command and
fault tables, so they cannot drift. Output is ASCII-only for legacy consoles.
"""

import argparse
import inspect
import json
import sys
import textwrap

from . import __version__
from .codec import FRAMES, WIRES
from .commands import COMMAND_NAMES, supported_commands
from .faults import ACTION_FIELDS
from .profiles import PROFILES
from .server import Server

TOPICS = ("run", "options", "client", "profiles", "embed", "faults", "memory", "troubleshoot", "divergences")

# Option -> topic named by error messages; every other option points to `options`.
OPTION_TOPICS = {"--profile": "profiles", "--fault-plan": "faults", "--init": "memory",
                 "--dump-on-exit": "memory", "--limit": "memory", "--latch-range": "memory"}

# Mirrored verbatim in the README quickstart (a test fails on drift).
RECIPES = (
    "virtual-plc --port 5000 --text-pad 0x20",
    "virtual-plc --profile iQ-R --port 0 --initial-state STOP",
    "virtual-plc --init seed.json --fault-plan faults.json --dump-on-exit saved.json",
)
RECIPE_LINES = "\n".join("  " + recipe for recipe in RECIPES)

EFFECTS = {
    "delay": "wait, then send the reply normally",
    "drop": "send nothing; the connection stays open",
    "truncate": "send only the first n bytes",
    "bad_end_code": "replace the end code (0..65535)",
    "close_before_response": "close without replying",
    "close_after_response": "reply, then close",
    "rst": "abortive close (TCP reset)",
    "silent_hold": "answer nothing on this connection until the server stops",
    "corrupt_header": "XOR one header byte (offset 0..8, xor 1..255)",
    "partial_send": "send in chunks of the given byte counts, pausing between",
}

RUN = f"""
Start the simulator (Python 3.10+, stdlib only). The banner and -v logs go to stderr; stdout stays empty.
  python -m pip install virtual-plc        (from a checkout: python -m pip install -e .)
{RECIPE_LINES}
Same program: python -m virtual_plc ...   Every option: virtual-plc guide options.
Banner: "listening on HOST:PORT (...)". With --port 0 parse the real port from it.
Stop: Ctrl+C or SIGTERM exits 0 and writes --dump-on-exit; Windows SIGBREAK needs a shared console.
Exit codes: 0 clean stop, 1 cannot bind, 2 bad configuration (message ends "see: virtual-plc guide TOPIC").
Default bind is 127.0.0.1. Other hosts print a WARNING: there is no authentication, so never expose it.
-v logs request summaries (no payloads or passwords) and why each connection closed.
Idle clients stay connected unless --idle-timeout SECONDS is set.
""".strip("\n")

CLIENT = """
Client: pymcprotocol 0.3.0 (python -m pip install pymcprotocol). Its plctype must match --profile.
  from pymcprotocol import Type3E               # Type4E for 4E frames
  c = Type3E(plctype="Q")                       # Q, L, QnA, iQ-L, iQ-R
  c.setaccessopt(commtype="ascii")              # default is "binary"
  c.connect("127.0.0.1", 5000)
  c.batchwrite_wordunits("D0", [123, -45]); c.batchread_wordunits("D0", 2)   # client signed, server unsigned
  c.batchwrite_bitunits("M0", [1, 0, 1]);   c.batchread_bitunits("M0", 3)
  c.randomwrite([], [], ["D0"], [0x12345678]); c.randomread([], ["D0"])      # returns (words, dwords)
  c.echo_test("ABC"); c.read_cputype()          # CPU name has NUL fill unless --text-pad 0x20
  c.remote_stop(); c.remote_run(0)              # remote_reset() needs STOP; remote_unlock(pw) needs --password
  c.close()
Hex-numbered devices (X Y B W SB SW DX DY ZR) take hex digits in the client: "X1F". Names are case-sensitive.
ASCII frames carry device numbers as decimal text (pymcprotocol "compat" numbering); the client handles it.
setaccessopt(timer_sec=2) sets the PLC monitoring timer (ignored here) and a 3 s client socket timeout.
""".strip("\n")

TROUBLESHOOT = """
Symptom -> cause -> fix
"cannot listen on H:P" (exit 1): port busy or denied -> choose another --port, or --port 0 and read the banner.
Exit 2 and "see: virtual-plc guide TOPIC": bad option, JSON file or plan -> read that topic; nothing was bound.
Client times out: wrong host/port, a fault plan that holds or drops replies, or --idle-timeout closed the socket
  (reconnect). A silent_hold fault ends only when the server stops.
Large read fails: pymcprotocol reads once with recv(4096); keep batches under ~1000 words (ASCII is 4 chars/word).
  --max-points is a separate server-side limit (points per request).
CPU name has NUL bytes: the default fill is 0x00 and the client keeps NULs -> --text-pad 0x20.
Status 0 on a broken reply: the client never checks subheader or length, so a truncated or closed binary
  reply can look like success. It is not proof of success.
Run/stop/pause/latch-clear/reset fail: locked (unlock with the --password text; length per profile in
  guide profiles) or wrong state: latch clear and reset need STOP, pause needs RUN or PAUSE.
  A normal reset keeps the connection open.
iQ-R vs Q mismatch: addressed commands use different subcommands -> set --profile and plctype together.
Echo rejected: data must be ASCII letters/digits, 1..960 chars (an error end code, no disconnect).
Client device-name error: names are case-sensitive; hex devices need a digit first ("X0FFF", not "XFFF").
""".strip("\n")

DIVERGENCES = """
This is a simulator, not a PLC. These behaviors are synthetic or unverified; do not treat them as vendor facts.
- CPU identities (VirtualPLC-<profile>), device ranges and the SD203 state codes are synthetic.
- CPU-name fill defaults to NUL (--text-pad); the fill of a physical PLC is unverified.
- ASCII frames send device numbers as decimal text even for hex devices (X Y B W SB SW DX DY ZR), as
  pymcprotocol does ("compat"). The manual's hex policy is not implemented.
- ASCII dword word order: default swapped (low word first); --ascii-dword-order client keeps high first.
  The real order is unverified; round trips are symmetric but batch word views differ.
- The lock is server-wide, survives disconnects and gates only run/stop/pause/latch clear/reset. It is
  not authentication.
- iQ-R native dword devices (LTN LSTN LCN LZ) use one 32-bit point per address; word access streams the
  low/high halves. The stride is unverified.
- Timers and counters hold plain values; no PLC logic executes. The monitoring timer is parsed and ignored.
  Every network/PC/station route aliases one memory.
- Error codes are design values; C200 and C201 may be swapped. Z devices are unsupported.
- Faults act after execution: a faulted write or reset has already happened.
""".strip("\n")

PROSE = {"run": RUN, "client": CLIENT, "troubleshoot": TROUBLESHOOT, "divergences": DIVERGENCES}

CONNECT = """
Connect (python -m pip install pymcprotocol):
  from pymcprotocol import Type3E
  c = Type3E(plctype="Q"); c.connect("127.0.0.1", 5000)
  c.batchwrite_wordunits("D0", [123, -45]); print(c.batchread_wordunits("D0", 2)); c.close()
""".strip("\n")

PITFALLS = """
Pitfalls (fix):
  1. "cannot listen" (exit 1): port busy -> choose another --port, or --port 0 and read the stderr banner.
  2. iQ-R errors: the client plctype and --profile must both be iQ-R (Q-class names share one wire format).
  3. CPU name contains NUL bytes: the default fill is 0x00 -> start with --text-pad 0x20.
  4. Big reads fail in pymcprotocol (one recv of 4096 bytes) -> keep batches under ~1000 words.
  5. Reset or latch clear returns an error: both need STOP -> start with --initial-state STOP.
""".strip("\n")

OPTIONS_HEAD = "Options: flag, default ('-' = none), meaning. Bad values exit 2 with an error that ends in 'see: virtual-plc guide TOPIC'."
OPTIONS_TAIL = ("DEV:LO-HI repeats (--limit D:0-99 --limit M:0-15); its endpoints and --text-pad accept 0x notation.\n"
                "Same data for programs: virtual-plc guide options --json")

FAULTS_HEAD = """
Faults change how replies are delivered AFTER the command ran; writes are never rolled back. Opt in with
--fault-plan FILE or Server(fault_plan=FaultPlan(steps)); without a plan nothing is matched or delayed.
Schema: {"steps": [STEP, ...]} in a file (no other root keys); Python takes the list. A bad plan exits 2 before bind.
STEP = {"match": {...}, "times": N, "action": {"type": T, ...}}; match and times are optional (times defaults to 1).
match keys, ANDed: command (int or "0x0619"), connection (1 = first accepted), nth (1 = first request on it).
The first step that matches and has uses left wins; one step applies per request.
Actions (parameters; [optional]):
""".strip("\n")

FAULTS_TAIL = """
Examples (each line is a complete valid file):
  {"steps": [{"match": {"command": "0x0619"}, "action": {"type": "delay", "seconds": 0.5}}]}
  {"steps": [{"match": {"command": "0x0401"}, "times": 2, "action": {"type": "bad_end_code", "code": 49241}}]}
  {"steps": [{"match": {"connection": 1, "nth": 1}, "action": {"type": "truncate", "n": 1}}]}
Reset test: --initial-state STOP plus {"steps": [{"match": {"command": "0x1006"}, "action": {"type": "rst"}}]}
makes the client reconnect after about 1 s. Give silent_hold its own connection.
""".strip("\n")

MEMORY_HEAD = """
Memory JSON: --init FILE loads it before listening; --dump-on-exit FILE saves it after a graceful stop.
Schema: {"DEVICE": {"HEAD": [values, ...]}}; HEAD is a decimal string and values fill consecutive points.
  {"D": {"100": [1, 2, 3]}, "M": {"0": [1, 0, 1]}}
  {"LTN": {"7": [305419896]}}
Values are unsigned native points: bit 0/1, word 0..65535, dword 0..4294967295 (never signed numbers).
The whole snapshot is validated before anything is applied; an invalid file exits 2.
Dumps use the same schema: contiguous runs, explicit zeros kept, plus SD203 (CPU state: STOP=0 RUN=1 PAUSE=2).
Device names by kind (Q-class profiles lack LT*/LST*/LC*/LZ/RD; see guide profiles):
""".strip("\n")

MEMORY_TAIL = """
--limit DEV:LO-HI (repeatable) sets the inclusive valid points of a device; requests outside get an error.
--latch-range DEV:LO-HI (repeatable) lists the points latch clear preserves; default: all of L. SM and SD are never cleared.
Example: virtual-plc --init seed.json --limit D:0-102 --latch-range D:100-101 --dump-on-exit saved.json
Word access to a bit device needs a head divisible by 16 (a word read of M16 returns M16..M31).
Bit access to a word device is rejected. Python: Memory.load(dict) and Memory.dump(); see guide embed.
""".strip("\n")


def option_topic(names):
    """Topic for an argparse argument name such as '--limit' or '-v/--verbose'."""
    return next((OPTION_TOPICS[name] for name in names.split("/") if name in OPTION_TOPICS), "options")


def _option_rows(parser):
    return [{
        "name": action.option_strings[-1],
        "flags": action.option_strings,
        "metavar": (action.metavar or action.dest.upper()) if action.nargs != 0 else None,
        "default": None if action.default is argparse.SUPPRESS else action.default,
        "choices": list(action.choices) if action.choices else None,
        "help": action.help,
    } for action in parser._actions]


def _default_text(row):
    default = row["default"]
    if default is None or default == []:
        return "-"
    return "off" if default is False else str(default)


def _option_line(row):
    label = ", ".join(row["flags"]) + (" " + row["metavar"] if row["metavar"] else "")
    choices = " [" + "|".join(row["choices"]) + "]" if row["choices"] else ""
    return f"  {label} | {_default_text(row)} | {row['help']}{choices}"


def _options(parser):
    return "\n".join([OPTIONS_HEAD, *map(_option_line, _option_rows(parser)), OPTIONS_TAIL])


def _overview(parser):
    return "\n".join([
        f"virtual-plc: local Mitsubishi MC-protocol PLC simulator (3E/4E, binary/ASCII; profiles {', '.join(PROFILES)})"
        " for client tests. Localhost only.",
        "Run:", RECIPE_LINES,
        "Options (flag | default | meaning; details: virtual-plc guide options):",
        *map(_option_line, _option_rows(parser)), CONNECT,
        f"Topics (virtual-plc guide TOPIC [--json]): {' '.join(TOPICS)}", PITFALLS,
    ])


def _profile_commands():
    return {profile.name: supported_commands(profile) for profile in PROFILES.values()}


def _profiles(parser):
    commands = _profile_commands()
    lines = [f"Frames {' '.join(FRAMES)} x encodings {' '.join(WIRES)}: every command works on all four pairs, "
             "even mixed on one connection.", f"Code  {'Command':<30}Profiles"]
    for code in sorted({code for codes in commands.values() for code in codes}):
        names = [name for name, codes in commands.items() if code in codes]
        where = "all" if len(names) == len(PROFILES) else " ".join(names)
        lines.append(f"{code:04X}  {COMMAND_NAMES[code]:<30}{where}")
    groups = {}
    for profile in PROFILES.values():
        groups.setdefault((profile.wire_class, tuple(profile.devices)), []).append(profile)
    for (wire_class, devices), members in groups.items():
        wire = members[0].wire
        size = str(wire.password_min) if wire.password_min == wire.password_max else f"{wire.password_min}-{wire.password_max}"
        lines.append(f"{', '.join(profile.name for profile in members)}: {wire_class} wire, password {size} chars, devices:")
        lines.append(textwrap.fill(" ".join(devices), 100, initial_indent="  ", subsequent_indent="  "))
    lines.append("Client plctype must equal --profile for iQ-R; Q-class profiles differ only in CPU identity and code.")
    return "\n".join(lines)


def _profile_data():
    commands = _profile_commands()
    return {"frames": list(FRAMES), "encodings": list(WIRES), "profiles": [{
        "name": profile.name, "wire_class": profile.wire_class, "cpu_name": profile.cpu_name,
        "devices": [{"name": device.name, "kind": device.kind} for device in profile.devices.values()],
        "commands": [f"{code:04X}" for code in commands[profile.name]],
    } for profile in PROFILES.values()]}


def _embed(parser):
    keywords = ", ".join(inspect.signature(Server).parameters)
    return f"""
Embed in Python (stdlib only). Leaving the with-block stops the server and joins its workers.
  from virtual_plc import Server, Memory, FaultPlan
  memory = Memory()                     # Memory("iQ-R"); Memory(limits=dict(D=(0, 99)))
  memory.write_words("D", 0, [123])     # seed BEFORE start
  with Server(memory=memory, port=0) as server:   # port 0 = free port
      host, port = server.address       # connect clients here
  snapshot = memory.dump()              # AFTER stop; same JSON schema as --init
Server keywords: {keywords}.
Bad values raise ValueError before binding; Server(profile=...) and Memory(profile) must match.
Memory API: read_words/write_words/read_bits/write_bits(device, head, ...), load(dict), dump().
Live state: server.state ("RUN"/"STOP"/"PAUSE"), server.set_state(s), server.reset_count, server.locked.
Memory calls are not synchronized with wire requests: never load, mutate or dump while serving; use a client.
FaultPlan(steps) or FaultPlan.from_file(path) -> Server(fault_plan=...); schema: virtual-plc guide faults.
response_hook(bytes) -> bytes transforms every complete reply before it is sent.
pytest fixture:
  import pytest
  from virtual_plc import Server, Memory

  @pytest.fixture
  def plc():
      with Server(memory=Memory()) as server:
          yield server
  # test body: Type3E(plctype="Q").connect(*plc.address)
""".strip("\n")


def _faults(parser):
    actions = []
    for kind, (required, optional) in ACTION_FIELDS.items():
        parts = sorted(required) + [f"[{name}]" for name in sorted(optional)]
        signature = f"{kind}({', '.join(parts)})" if parts else kind
        actions.append(f"  {signature:<34}{EFFECTS[kind]}")
    return "\n".join([FAULTS_HEAD, *actions, FAULTS_TAIL])


def _memory(parser):
    largest = max(PROFILES.values(), key=lambda profile: len(profile.devices))
    kinds = {}
    for device in largest.devices.values():
        kinds.setdefault(device.kind, []).append(device.name)
    return "\n".join([MEMORY_HEAD, *(f"  {kind}: {' '.join(names)}" for kind, names in kinds.items()), MEMORY_TAIL])


GENERATED = {None: _overview, "options": _options, "profiles": _profiles, "embed": _embed,
             "faults": _faults, "memory": _memory}


def render(parser, topic=None):
    """Text of one topic (None = overview); `parser` supplies the option table."""
    return PROSE[topic] if topic in PROSE else GENERATED[topic](parser)


def data(parser, topic=None):
    """JSON-ready document: text, or structured rows for the options and profiles topics."""
    document = {"version": __version__, "topic": topic or "overview"}
    if topic == "options":
        document["options"] = _option_rows(parser)
    elif topic == "profiles":
        document.update(_profile_data())
    else:
        document["text"] = render(parser, topic)
    return document


def main(argv, parser):
    """Print one guide topic and return the exit status (2 for an unknown topic)."""
    arguments = argparse.ArgumentParser(prog="virtual-plc guide", description="Usage guide for humans and AI agents.")
    arguments.add_argument("topic", nargs="?", help="one of: " + " ".join(TOPICS))
    arguments.add_argument("--json", action="store_true", help="print JSON instead of text")
    args = arguments.parse_args(argv)
    if args.topic is not None and args.topic not in TOPICS:
        print(f"unknown topic {args.topic!r}; topics: {', '.join(TOPICS)}", file=sys.stderr)
        return 2
    print(json.dumps(data(parser, args.topic)) if args.json else render(parser, args.topic))
    return 0
