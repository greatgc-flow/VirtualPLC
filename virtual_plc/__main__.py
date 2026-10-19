"""Start the non-production, local-only simulator."""
import argparse
from .server import Server

def main():
    p = argparse.ArgumentParser(description="VirtualPLC 3E Binary loopback prototype")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=5000)
    args = p.parse_args()
    if args.host != "127.0.0.1":
        p.error("refusing to bind non-loopback address")
    with Server((args.host, args.port)) as server:
        print(f"VirtualPLC M1: {args.host}:{args.port}", flush=True)
        try:
            server.serve_forever(poll_interval=0.05)
        except KeyboardInterrupt:
            pass

if __name__ == "__main__":
    main()
