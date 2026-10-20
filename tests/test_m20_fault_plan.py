"""M20 internal backlog BL-I001. Not an external P0 attestation."""
from __future__ import annotations
import json
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

import pytest

from virtual_plc.faults import FaultPlan
from virtual_plc.memory import Memory
from virtual_plc.server import Server
from suite.support.wire import request, recv_response


@contextmanager
def running_server(**kwargs):
    with Server(('127.0.0.1', 0), **kwargs) as server:
        worker = threading.Thread(target=server.serve_forever,
                                  kwargs={'poll_interval': 0.01}, daemon=True)
        worker.start()
        try:
            yield server
        finally:
            server.shutdown()
            worker.join(timeout=3)
            assert not worker.is_alive()


def exchange(server, data=None, expect_drop=False):
    with socket.create_connection(('127.0.0.1', server.server_address[1]), timeout=2) as sock:
        sock.settimeout(2)
        sock.sendall(request() if data is None else data)
        if expect_drop:
            try:
                assert sock.recv(1) == b''
            except ConnectionResetError:
                pass
            return
        return recv_response(sock)


@pytest.mark.parametrize('bad', [None, 'disconnect', {}, True,
    [{'action': 'delay'}], [{'action':'delay','delay_ms': 0}],
    [{'action':'delay','delay_ms':501}], [{'action':'delay','delay_ms': True}],
    [{'action':'disconnect','delay_ms':1}], [{'action':'pass','unexpected':1}],
    [{'action':'unknown'}], [None], [{'action':'PASS'}],
    [{'action':'delay','delay_ms':1.1}],
    [{'action':'pass'}]*257])
def test_invalid_plan_fails_before_listening(bad):
    with pytest.raises(ValueError):
        FaultPlan(bad)


def test_empty_steps_and_immutability():
    plan = FaultPlan([])
    assert plan.snapshot() == {'configured':0,'consumed':0,'remaining':0}
    assert plan.consume() == ('pass', 0)
    source = [{'action':'delay','delay_ms':5}, {'action':'disconnect'}]
    plan = FaultPlan(source)
    source[0]['delay_ms'] = 500
    source.clear()
    assert plan.consume() == ('delay',5)
    assert plan.consume() == ('disconnect',0)
    assert plan.consume() == ('pass',0)
    assert plan.snapshot() == {'configured':2,'consumed':2,'remaining':0}


def test_server_default_does_not_inject():
    with running_server() as server:
        assert server.fault_plan is None
        assert exchange(server)['endcode'] == 0
        assert not any(k.startswith('fault_') for k in server.telemetry.snapshot()['counters'])


def test_server_rejects_untyped_plan():
    with pytest.raises(TypeError):
        Server(('127.0.0.1', 0), fault_plan=['disconnect'])


def test_fault_drop_is_pre_mutation_and_following_request_normal():
    memory = Memory()
    plan = FaultPlan([{'action':'disconnect'}])
    # The first command attempts to write word 0: the injected drop wins.
    write = request(cmd=0x1401, head=0, payload=b'\x34\x12')
    with running_server(memory=memory, fault_plan=plan) as server:
        exchange(server, write, expect_drop=True)
        assert memory.read_words(0, 1) == [0]
        assert memory.version == 0
        assert exchange(server)['data'] == b'\x00\x00'
        assert server.telemetry.snapshot()['counters']['fault_disconnect'] == 1
        assert plan.snapshot()['consumed'] == 1


def test_delay_blocks_only_one_worker_and_records_no_payload():
    plan = FaultPlan([{'action':'delay','delay_ms':80}])
    with running_server(fault_plan=plan) as server:
        begin=time.monotonic()
        assert exchange(server)['endcode'] == 0
        elapsed=time.monotonic()-begin
        assert elapsed >= 0.060
        assert elapsed < 1.6
        assert exchange(server)['endcode'] == 0
        record=server.telemetry.snapshot()
        assert record['counters']['fault_delay'] == 1
        assert 'ip' not in json.dumps(record).lower()
        assert 'payload' not in json.dumps(record).lower()


def test_bad_route_does_not_consume_fault_step():
    plan = FaultPlan([{'action':'disconnect'}])
    with running_server(fault_plan=plan) as server:
        alien=request(route=bytes.fromhex('02FFFF0300'))
        exchange(server, alien, expect_drop=True)
        assert plan.snapshot()['consumed'] == 0
        exchange(server, expect_drop=True)
        assert plan.snapshot()['consumed'] == 1


def test_global_step_sequence_race_safe():
    steps=[{'action':'disconnect'}]*10 + [{'action':'delay','delay_ms':1}]*20
    plan=FaultPlan(steps)
    with ThreadPoolExecutor(max_workers=18) as pool:
        actual=list(pool.map(lambda _: plan.consume(), range(200)))
    assert actual.count(('disconnect',0)) == 10
    assert actual.count(('delay',1)) == 20
    assert actual.count(('pass',0)) == 170
    assert plan.snapshot()['consumed'] == 30


def test_config_has_no_remotely_exposed_fault_keys():
    from virtual_plc.config import validate_options
    with pytest.raises(ValueError):
        validate_options({'fault_plan': [{'action':'disconnect'}]})
    with pytest.raises(ValueError):
        Server(('0.0.0.0', 0), fault_plan=FaultPlan([]))


def test_nondefault_route_keeps_fault_plan_semantics():
    from virtual_plc.server import DEFAULT_ROUTE
    other=bytes.fromhex('02FFFF0300')
    plan=FaultPlan([{'action':'disconnect'}])
    with running_server(fault_plan=plan,allowed_routes=[DEFAULT_ROUTE, other]) as server:
        exchange(server, request(route=other), expect_drop=True)
        assert exchange(server, request(route=other))['endcode'] == 0
