"""Step 4 - talk to a simulator started from the command line.

Terminal A (the "PLC"):
    virtual-plc --port 5000 --init seed.json

Terminal B (your application):
    python 04_external_server.py 5000

Same LineController as before - only the PLC now lives in another process, so
you can also point GX Works-style tools or your own services at it. To rehearse
failures, restart terminal A with the fault plan:

    virtual-plc --port 5000 --init seed.json --fault-plan faults.json

(faults.json drops the first read, then answers the next read with an error
code; run this script twice to see the retry and the error path.)
"""

import argparse
import sys

from line_client import LineController, LineError, LineUnreachable


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read the line status from a running simulator")
    parser.add_argument("port", type=int)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args(argv)
    try:
        with LineController(args.host, args.port) as hmi:
            print(hmi.status())
            print("reconnects:", hmi.reconnects)
    except LineError as error:
        print("PLC refused the request:", error, file=sys.stderr)
        return 2
    except (LineUnreachable, OSError) as error:
        print("cannot reach the PLC:", error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
