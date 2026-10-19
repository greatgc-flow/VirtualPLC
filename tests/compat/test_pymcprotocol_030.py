"""Opt-in pinned real-client loopback test with transparent raw-request capture."""
import importlib.metadata
import os
import select
import socket
import struct
import threading
import pytest
from virtual_plc.server import Server

VERSION = '0.3.0'

class LocalRelay:
    def __init__(self, upstream_port):
        self.upstream_port = upstream_port
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener.bind(('127.0.0.1', 0))
        self.listener.listen(1)
        self.listener.settimeout(3)
        self.port = self.listener.getsockname()[1]
        self.client_bytes = bytearray()
        self.errors = []
        self.worker = threading.Thread(target=self._forward, daemon=True)

    def __enter__(self):
        self.worker.start()
        return self

    def _forward(self):
        try:
            with self.listener.accept()[0] as client:
                with socket.create_connection(('127.0.0.1', self.upstream_port), timeout=3) as upstream:
                    client.setblocking(False)
                    upstream.setblocking(False)
                    peers = (client, upstream)
                    while True:
                        ready, _, _ = select.select(peers, [], [], 3)
                        if not ready:
                            break
                        for side in ready:
                            try:
                                chunk = side.recv(8192)
                            except BlockingIOError:
                                continue
                            if not chunk:
                                return
                            if side is client:
                                self.client_bytes.extend(chunk)
                            (upstream if side is client else client).sendall(chunk)
        except Exception as exc:
            self.errors.append(repr(exc))

    def __exit__(self, *_):
        self.worker.join(timeout=4)
        self.listener.close()
        assert not self.worker.is_alive(), 'relay thread did not exit'
        assert not self.errors, f'local relay error: {self.errors}'

def commands_in_stream(raw):
    result = []
    offset = 0
    while offset < len(raw):
        assert len(raw) - offset >= 21
        assert raw[offset:offset+2] == b'\x50\x00'
        body_size = int.from_bytes(raw[offset+7:offset+9], 'little')
        assert 12 <= body_size <= 4096
        end = offset + 9 + body_size
        assert end <= len(raw), 'truncated real-client request'
        cmd, sub = struct.unpack_from('<HH', raw, offset+11)
        result.append((cmd, sub, raw[offset:end]))
        offset = end
    return result

@pytest.mark.parametrize('device', ['D_WORD', 'M_BIT'])
def test_pymcprotocol_030_roundtrip_with_raw_capture(device):
    if os.environ.get('VIRTUALPLC_RUN_PYMC') != '1':
        pytest.skip('opt in with VIRTUALPLC_RUN_PYMC=1')
    actual = importlib.metadata.version('pymcprotocol')
    assert actual == VERSION, f'expected pinned {VERSION}; found {actual}'
    import pymcprotocol
    with Server(('127.0.0.1', 0)) as server:
        thread = threading.Thread(target=server.serve_forever,
            kwargs={'poll_interval': 0.01}, daemon=True)
        thread.start()
        try:
            with LocalRelay(server.server_address[1]) as relay:
                client = pymcprotocol.Type3E()
                try:
                    client.connect('127.0.0.1', relay.port)
                    if device == 'D_WORD':
                        vals = [0, 0x1234, 0x7FFF]
                        client.batchwrite_wordunits('D100', vals)
                        result = client.batchread_wordunits('D100', 3)
                    else:
                        vals = [1, 0, 1, 1, 0]
                        client.batchwrite_bitunits('M10', vals)
                        result = client.batchread_bitunits('M10', 5)
                    assert result == vals
                finally:
                    client.close()
            frames = commands_in_stream(bytes(relay.client_bytes))
            assert [f[0] for f in frames] == [0x1401, 0x0401]
            assert [f[1] for f in frames] == ([0, 0] if device == 'D_WORD' else [1, 1])
        finally:
            server.shutdown()
            thread.join(timeout=3)
            assert not thread.is_alive()
