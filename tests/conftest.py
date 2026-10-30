"""M1 localhost fixtures; production imports stay lazy for the RED suite."""

import json
from pathlib import Path
import socket

import pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "unverified: manual-derived protocol claim awaiting manual cross-check")


@pytest.fixture
def scenarios():
    path = Path(__file__).parent / "data/scenarios.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


@pytest.fixture
def codec():
    from virtual_plc.codec import decode_request, encode_response, pack_bits, unpack_bits, pack_words, unpack_words
    from virtual_plc import codec

    return codec


@pytest.fixture
def memory_factory():
    from virtual_plc.memory import Memory

    return Memory


@pytest.fixture
def memory(memory_factory):
    # Synthetic test ranges, not authoritative Q PLC limits.
    return memory_factory(limits={name: (0, 8191) for name in (
        "D", "M", "X", "Y", "B", "W", "R", "ZR", "SM", "SD"
    )})


@pytest.fixture
def server_factory(memory):
    from virtual_plc.server import Server

    servers = []

    def create(**options):
        options.setdefault("memory", memory)
        instance = Server("127.0.0.1", port=0, profile="Q", **options)
        servers.append(instance)
        instance.start()
        assert instance.address[0] == "127.0.0.1"
        assert instance.address[1] > 0
        return instance

    yield create
    for instance in reversed(servers):
        instance.stop()


@pytest.fixture
def server(server_factory):
    return server_factory()


@pytest.fixture
def raw_socket(server):
    with socket.create_connection(server.address, timeout=2) as connection:
        connection.settimeout(2)
        yield connection


@pytest.fixture
def client(server):
    import pymcprotocol

    instance = pymcprotocol.Type3E(plctype="Q")
    instance.soc_timeout = 2
    try:
        instance.connect(*server.address)
        yield instance
    finally:
        if instance._is_connected:
            instance.close()
