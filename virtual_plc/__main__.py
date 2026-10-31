"""Local simulator CLI: python -m virtual_plc."""

import argparse
import json
import logging
import os
from pathlib import Path
import re
import signal
import sys
import threading
import tempfile

from . import __version__, guide
from .ethernet import EthernetSettings, model_catalog
from .server import Server, is_loopback_host
from .faults import FaultPlan
from .memory import Memory
from .profiles import PROFILES


def text_pad(value):
    try:
        number = int(value, 0)
        if 0 <= number <= 255:
            return number
    except ValueError:
        pass
    raise argparse.ArgumentTypeError("text pad must be an integer 0..255 (e.g. 0x00 or 0x20)")


def listener_spec(value):
    """CLI listener syntax: tcp:PORT or udp:PORT (each port 0..65535)."""
    try:
        transport, separator, number = value.partition(":")
        if separator == ":" and transport in ("tcp", "udp") and number.isascii() and number.isdecimal():
            port = int(number, 10)
            if 0 <= port <= 65535:
                return transport, port
    except (TypeError, ValueError):
        pass
    raise argparse.ArgumentTypeError("listener must be tcp:PORT or udp:PORT with port 0..65535")


def device_range(value):
    try:
        device, span = value.split(":")
        low, high = (int(part, 0) for part in span.split("-"))
        if device and 0 <= low <= high:
            return device, (low, high)
    except ValueError:
        pass
    raise argparse.ArgumentTypeError("range must be DEV:LO-HI with 0 <= LO <= HI")


def local_host(host):
    return is_loopback_host(host)


class GuideParser(argparse.ArgumentParser):
    def error(self, message, topic=None):
        if topic is None:
            flags = re.findall(r"--[a-z][a-z-]*", message)
            topic = guide.option_topic("/".join(flags))
        # JSON errors and filenames can contain newlines; diagnostics stay one line.
        self.exit(2, f"{self.prog}: error: {' '.join(message.split())}; see: virtual-plc guide {topic}\n")


def build_parser():
    parser = GuideParser(prog="virtual-plc", description="Virtual Mitsubishi MC protocol PLC (not for industrial use)")
    parser.add_argument("--version", action="version", version=__version__, help="show installed version")
    parser.add_argument("--host", default="127.0.0.1", help="bind address (loopback by default)")
    parser.add_argument("--allow-nonlocal", action="store_true", help="explicitly permit non-loopback binding (unsafe; requires --idle-timeout)")
    parser.add_argument("--max-clients", type=int, default=64, help="maximum concurrent connections; default: 64")
    parser.add_argument("--port", type=int, default=5000, help="legacy single TCP port 0..65535; 0 chooses a free port")
    parser.add_argument("--listen", action="append", type=listener_spec, default=[], metavar="PROTO:PORT",
                        help="repeatable tcp:PORT or udp:PORT; shares one PLC state, overrides default --port")
    parser.add_argument("--profile", choices=PROFILES, default="Q", help="simulated CPU profile (inferred from --ethernet-model unless explicitly specified)")
    parser.add_argument("--ethernet-model", choices=tuple(model_catalog()), help="optional GX Works CPU/module Ethernet model (legacy defaults unchanged)")
    parser.add_argument("--slmp-1e", action="store_true", help="opt-in 1E batch frame server (Q synthetic memory; not an FX5 hardware preset)")
    parser.add_argument("--ethernet-config", metavar="FILE", help="JSON Ethernet timer/policy overrides (requires --ethernet-model)")
    parser.add_argument("--show-effective-ethernet", action="store_true", help="print model defaults/overrides and fidelity as JSON without binding")
    parser.add_argument("--password", help="simulated lock password (not authentication)")
    parser.add_argument("--initial-state", choices=("RUN", "STOP", "PAUSE"), default="RUN", help="initial CPU state")
    parser.add_argument("--max-points", type=int, default=None, help="optional batch point cap below manual limit")
    parser.add_argument("--idle-timeout", type=float, default=None, help="seconds; default: no timeout")
    parser.add_argument("--ascii-dword-order", choices=("swapped", "client"), default="swapped",
                        help="ASCII dwords: low word first / client high word first")
    parser.add_argument("--ascii-numbering", choices=("compat", "manual", "fx5-octal"), default="compat",
                        help="ASCII addresses: decimal compat, hex manual, or FX5 X/Y octal (others use device base)")
    parser.add_argument("--text-pad", type=text_pad, default=0x00, help="CPU name fill byte 0..255; 0x20 = space")
    parser.add_argument("--fault-plan", metavar="FILE", help="response fault JSON")
    parser.add_argument("--init", metavar="FILE", help="load memory JSON before listening")
    parser.add_argument("--dump-on-exit", metavar="FILE", help="save memory JSON after shutdown")
    parser.add_argument("--latch-range", action="append", type=device_range, default=[], metavar="DEV:LO-HI",
                        help="retained span; repeatable; default all L")
    parser.add_argument("--limit", action="append", type=device_range, default=[], metavar="DEV:LO-HI",
                        help="inclusive device limit; repeatable; default profile ceiling")
    parser.add_argument("-v", "--verbose", action="store_true", help="log requests and connection close reasons")
    return parser


def write_snapshot_atomic(path, snapshot):
    """Write a complete JSON snapshot before replacing the target on the same filesystem."""
    destination = Path(path)
    content = json.dumps(snapshot, indent=2) + "\n"
    fd, temporary = tempfile.mkstemp(prefix=f".{destination.name}.",
                                      suffix=".tmp", dir=destination.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    parser = build_parser()
    if argv and argv[0] == "guide":
        return guide.main(argv[1:], parser)
    args = parser.parse_args(argv)
    if args.listen and any(argument == "--port" or argument.startswith("--port=") for argument in argv):
        parser.error("--port cannot be combined with --listen")
    if (args.ethernet_config or args.show_effective_ethernet) and not args.ethernet_model:
        parser.error("--ethernet-model is required for ethernet configuration/inspection", "ethernet")
    if args.slmp_1e and (args.profile != "Q" or args.ethernet_model or args.fault_plan):
        parser.error("--slmp-1e requires the synthetic Q profile, no --ethernet-model or --fault-plan")
    if args.ethernet_model:
        required_profile = EthernetSettings(args.ethernet_model).profile
        specified_profile = any(value == "--profile" or value.startswith("--profile=") for value in argv)
        if specified_profile and args.profile != required_profile:
            parser.error("--profile conflicts with the selected ethernet hardware model", "ethernet")
        if not specified_profile:
            args.profile = required_profile
    topic = "faults"
    try:
        plan = FaultPlan.from_file(args.fault_plan) if args.fault_plan else None
        topic = "memory"
        overrides = json.loads(Path(args.ethernet_config).read_text(encoding="utf-8")) if args.ethernet_config else None
        if args.ethernet_config and not isinstance(overrides, dict):
            parser.error("ethernet configuration root must be a JSON object", "ethernet")
        options = dict(profile=args.profile, password=args.password, initial_state=args.initial_state,
                       max_points=args.max_points, idle_timeout=args.idle_timeout, fault_plan=plan,
                       max_clients=args.max_clients, allow_nonlocal=args.allow_nonlocal,
                       ascii_dword_order=args.ascii_dword_order, text_pad=args.text_pad,
                       ascii_numbering=args.ascii_numbering, verbose=args.verbose,
                       slmp_1e=args.slmp_1e)
        if args.listen:
            options["listeners"] = args.listen
        if args.ethernet_model:
            options["ethernet_model"] = args.ethernet_model
            options["ethernet_overrides"] = overrides
        if args.init or args.limit:
            options["memory"] = Memory(args.profile, dict(args.limit))
        if args.latch_range:
            ranges = {}
            for device, span in args.latch_range:
                ranges.setdefault(device, []).append(span)
            options["latch_ranges"] = ranges
        topic = "options"
        try:
            server = Server(args.host, 0 if args.listen else args.port, **options)
        except ValueError as error:
            hint = ("ethernet" if args.ethernet_model and (args.ethernet_config or
                    "ethernet" in str(error) or "profile" in str(error))
                    else ("memory" if "latch" in str(error) else topic))
            parser.error(str(error), hint)
        if args.show_effective_ethernet:
            print(json.dumps(server.ethernet.report(), indent=2))
            return 0
        topic = "memory"
        if args.init:
            options["memory"].load(json.loads(Path(args.init).read_text(encoding="utf-8")))
    except (OSError, ValueError) as error:
        parser.error(str(error), "ethernet" if args.ethernet_config else topic)
    try:
        server.start()
    except (OSError, OverflowError) as error:
        server.stop()
        destination = (", ".join(f"{protocol}:{args.host}:{port}" for protocol, port in args.listen)
                       if args.listen else f"{args.host}:{args.port}")
        print(f"cannot listen on {destination}: {error}", file=sys.stderr)
        return 1
    warning = "; WARNING: localhost-only simulator; do not expose to production networks" if not local_host(args.host) else ""
    exit_code = 0
    previous = {}
    def terminate(signum, frame):
        raise KeyboardInterrupt  # finally stops workers and writes the snapshot, then exits 0
    handler = logging.StreamHandler(sys.stderr)
    logger = logging.getLogger("virtual_plc")
    old_level = logger.level
    if args.verbose:
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    try:
        for name in ("SIGTERM", "SIGBREAK"):
            if hasattr(signal, name):
                number = getattr(signal, name)
                previous[number] = signal.signal(number, terminate)
        destination = (", ".join(f"{protocol}:{host}:{port}" for protocol, host, port in server.addresses)
                       if args.listen else f"{server.address[0]}:{server.address[1]}")
        print("listening on %s (%s, %s) idle_timeout=%s text_pad=0x%02X ascii_dword_order=%s ascii_numbering=%s fault_plan=%s%s" %
              (destination, args.profile, args.initial_state, args.idle_timeout, args.text_pad,
               args.ascii_dword_order, args.ascii_numbering, args.fault_plan, warning), file=sys.stderr, flush=True)
        event = threading.Event()
        while not event.wait(0.5):
            pass
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()
        for number, old in previous.items():
            signal.signal(number, old)
        if args.verbose:
            logger.removeHandler(handler)
            logger.setLevel(old_level)
        if args.dump_on_exit:
            try:
                write_snapshot_atomic(args.dump_on_exit, server.memory.dump())
            except OSError as error:
                print(f"cannot dump memory: {error}", file=sys.stderr)
                exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
