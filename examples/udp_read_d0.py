"""Standalone MC 3E binary UDP client: read D0 on IPv4 loopback only.

Run a *source checkout* simulator in another terminal:
    python -m virtual_plc --listen udp:5000
Then:
    python examples/udp_read_d0.py 5000

Unlike pymcprotocol's TCP client, this is a raw UDP datagram sample.
Not for physical PLCs or production networks; no authentication or retries.
"""

import argparse
import ipaddress
import math
import socket
import sys


# Complete 3E binary MC request: local route, 0x0401 batch word read,
# D0 (device 0xA8), count 1. Exactly one request per datagram.
READ_D0 = bytes.fromhex(
    "5000 00FFFF0300 0C00 0400 0104 0000 000000 A8 0100"
)
RESPONSE_PREFIX = bytes.fromhex("D000 00FFFF0300")


def read_d0(port, host="127.0.0.1", timeout=1.0):
    """Read one D0 word, validate sender and the *entire* binary response.

    This deliberately refuses non-loopback endpoints, DNS names, invalid
    timeouts and malformed MC frames. A timeout raises socket.timeout;
    invalid replies raise ValueError. It does not implement retries.
    """
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("port must be an integer 1..65535")
    if not isinstance(host, str):
        raise ValueError("host must be a literal IPv4 loopback address")
    try:
        target_ip = ipaddress.IPv4Address(host)
    except ipaddress.AddressValueError as error:
        raise ValueError("host must be a literal IPv4 loopback address") from error
    if not target_ip.is_loopback:
        raise ValueError("example permits IPv4 loopback only")
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be a finite positive number")

    target = (str(target_ip), port)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as connection:
        connection.settimeout(timeout)
        connection.sendto(READ_D0, target)
        reply, sender = connection.recvfrom(8192)

    if sender != target:
        raise ValueError("UDP response source does not match the requested endpoint")
    if len(reply) != 13 or reply[:7] != RESPONSE_PREFIX:
        raise ValueError("invalid 3E binary response header or size")
    if reply[7:9] != b"\x04\x00" or reply[9:11] != b"\x00\x00":
        raise ValueError("invalid 3E response length or nonzero end code")
    return int.from_bytes(reply[11:13], "little")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Loopback-only 3E UDP D0 reader")
    parser.add_argument("port", type=int, help="local simulator UDP listener port")
    args = parser.parse_args(argv)
    try:
        value = read_d0(args.port)
    except (OSError, ValueError) as error:
        print("UDP read failed: %s" % error, file=sys.stderr)
        return 1
    print("D0 = %d (0x%04X)" % (value, value))
    return 0


if __name__ == "__main__":
    sys.exit(main())
