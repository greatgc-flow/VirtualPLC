"""Local simulator CLI: python -m virtual_plc."""

import argparse
import json
import logging
from pathlib import Path
import re
import signal
import sys
import threading

from . import __version__, guide
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
    parser.add_argument("--port", type=int, default=5000, help="TCP port 0..65535; 0 chooses a free port")
    parser.add_argument("--profile", choices=PROFILES, default="Q", help="simulated CPU profile")
    parser.add_argument("--password", help="simulated lock password (not authentication)")
    parser.add_argument("--initial-state", choices=("RUN", "STOP", "PAUSE"), default="RUN", help="initial CPU state")
    parser.add_argument("--max-points", type=int, default=None, help="optional batch point cap below manual limit")
    parser.add_argument("--idle-timeout", type=float, default=None, help="seconds; default: no timeout")
    parser.add_argument("--ascii-dword-order", choices=("swapped", "client"), default="swapped",
                        help="ASCII dwords: low word first / client high word first")
    parser.add_argument("--ascii-numbering", choices=("compat", "manual"), default="compat",
                        help="ASCII device numbers: decimal compat / hex manual for X/Y/B/W")
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


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    parser = build_parser()
    if argv and argv[0] == "guide":
        return guide.main(argv[1:], parser)
    args = parser.parse_args(argv)
    topic = "faults"
    try:
        plan = FaultPlan.from_file(args.fault_plan) if args.fault_plan else None
        topic = "memory"
        options = dict(profile=args.profile, password=args.password, initial_state=args.initial_state,
                       max_points=args.max_points, idle_timeout=args.idle_timeout, fault_plan=plan,
                       max_clients=args.max_clients, allow_nonlocal=args.allow_nonlocal,
                       ascii_dword_order=args.ascii_dword_order, text_pad=args.text_pad,
                       ascii_numbering=args.ascii_numbering, verbose=args.verbose)
        if args.init or args.limit:
            options["memory"] = Memory(args.profile, dict(args.limit))
        if args.latch_range:
            ranges = {}
            for device, span in args.latch_range:
                ranges.setdefault(device, []).append(span)
            options["latch_ranges"] = ranges
        topic = "options"
        try:
            server = Server(args.host, args.port, **options)
        except ValueError as error:
            parser.error(str(error), "memory" if "latch" in str(error) else topic)
        topic = "memory"
        if args.init:
            options["memory"].load(json.loads(Path(args.init).read_text(encoding="utf-8")))
    except (OSError, ValueError) as error:
        parser.error(str(error), topic)
    try:
        server.start()
    except (OSError, OverflowError) as error:
        server.stop()
        print(f"cannot listen on {args.host}:{args.port}: {error}", file=sys.stderr)
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
        print("listening on %s:%d (%s, %s) idle_timeout=%s text_pad=0x%02X ascii_dword_order=%s ascii_numbering=%s fault_plan=%s%s" %
              (*server.address, args.profile, args.initial_state, args.idle_timeout, args.text_pad,
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
                Path(args.dump_on_exit).write_text(json.dumps(server.memory.dump(), indent=2) + "\n", encoding="utf-8")
            except OSError as error:
                print(f"cannot dump memory: {error}", file=sys.stderr)
                exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
