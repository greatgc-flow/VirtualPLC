"""Start the experimental loopback-only virtual PLC (never a physical PLC)."""
import argparse
import signal
import threading
from .config import load_config, validate_options
from .memory import Memory
from .server import Server


def main(argv=None):
    parser = argparse.ArgumentParser(description='VirtualPLC MC 3E Binary, loopback only')
    parser.add_argument('--config', default=None, help='optional stdlib TOML configuration')
    parser.add_argument('--host', default=None, help='must be 127.0.0.1')
    parser.add_argument('--port', type=int, default=None, help='TCP port, 0 for auto-assigned test port')
    args = parser.parse_args(argv)
    try:
        cfg = load_config(args.config)
        overrides = {k: getattr(args, k) for k in ('host', 'port') if getattr(args, k) is not None}
        cfg = validate_options(dict(cfg, **overrides))
    except (OSError, ValueError) as exc:
        parser.error(f'configuration rejected before listening: {exc}')
    with Server((cfg['host'], cfg['port']),
                memory=Memory(d_size=cfg['d_size'], m_size=cfg['m_size']),
                max_body=cfg['max_body'],
                allowed_routes=[bytes.fromhex(x) for x in cfg['routes']]) as server:
        print(f"VirtualPLC M5 loopback-only: {server.server_address}", flush=True)
        # Signal handler cannot call shutdown() on the serve_forever thread.
        def terminate(signum, frame):
            threading.Thread(target=server.shutdown, daemon=True).start()
        for sig in ('SIGTERM', 'SIGINT'):
            signum = getattr(signal, sig, None)
            if signum is not None:
                try:
                    signal.signal(signum, terminate)
                except (OSError, ValueError):
                    pass
        try:
            server.serve_forever(poll_interval=0.05)
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
