"""Local server entry point (M1): python -m virtual_plc --host H --port P."""

import argparse
import threading

from .server import Server
from .faults import FaultPlan


def main(argv=None):
    parser = argparse.ArgumentParser(description="Virtual Mitsubishi MC protocol PLC (not for industrial use)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--fault-plan", metavar="FILE", help="load a declarative response fault plan from JSON")
    args = parser.parse_args(argv)
    try:
        plan = FaultPlan.from_file(args.fault_plan) if args.fault_plan else None
    except (OSError, ValueError) as error:
        parser.error(str(error))
    server = Server(args.host, args.port, fault_plan=plan)
    server.start()
    print("listening on %s:%d" % server.address, flush=True)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()


if __name__ == "__main__":
    main()
