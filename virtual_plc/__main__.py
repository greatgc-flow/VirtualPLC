"""Local server entry point (M1): python -m virtual_plc --host H --port P."""

import argparse
import threading

from .server import Server


def main():
    parser = argparse.ArgumentParser(description="Virtual Mitsubishi MC protocol PLC (not for industrial use)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()
    server = Server(args.host, args.port)
    server.start()
    print("listening on %s:%d" % server.address)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()


if __name__ == "__main__":
    main()
