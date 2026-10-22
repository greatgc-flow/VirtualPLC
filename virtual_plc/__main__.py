"""Local simulator CLI: python -m virtual_plc."""

import argparse
import sys
import threading

from .server import Server
from .faults import FaultPlan
from .profiles import PROFILES


def main(argv=None):
    parser = argparse.ArgumentParser(description="Virtual Mitsubishi MC protocol PLC (not for industrial use)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--profile", choices=PROFILES, default="Q")
    parser.add_argument("--password", help="simulated lock password (not authentication)")
    parser.add_argument("--initial-state", choices=("RUN", "STOP", "PAUSE"), default="RUN")
    parser.add_argument("--max-points", type=int, default=4096)
    parser.add_argument("--idle-timeout", type=float, default=None, help="seconds; default: no timeout")
    parser.add_argument("--fault-plan", metavar="FILE", help="load a declarative response fault plan from JSON")
    args = parser.parse_args(argv)
    try:
        plan = FaultPlan.from_file(args.fault_plan) if args.fault_plan else None
        server = Server(args.host, args.port, profile=args.profile, password=args.password,
                        initial_state=args.initial_state, max_points=args.max_points,
                        idle_timeout=args.idle_timeout, fault_plan=plan)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    server.start()
    warning = "; WARNING: localhost-only simulator; do not expose to production networks" if args.host != "127.0.0.1" else ""
    print("listening on %s:%d (%s, %s)%s" % (*server.address, args.profile, args.initial_state, warning),
          file=sys.stderr, flush=True)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()


if __name__ == "__main__":
    main()
