"""Step 5 - test your client against VirtualPLC with pytest.

    pip install virtual-plc pymcprotocol==0.3.0 pytest
    python -m pytest -q          # run from examples/bottling_line

Each test gets its own fresh simulator on a free port, so tests are isolated,
fast, and need no hardware. The fixture pattern below is the one to copy.
"""

import time

import pytest
from pymcprotocol import Type3E
from virtual_plc import FaultPlan, Memory, Server

import plc_map as dev
from line_client import LineController, LineError, LineUnreachable
from plant import PlantSimulator


@pytest.fixture
def memory():
    mem = Memory()
    mem.write_words("D", 100, [10, 3, 253])  # target 10, count 3, 25.3 C
    mem.write_bits("M", 10, [1, 0])  # running, no alarm
    return mem


@pytest.fixture
def plc(memory):
    with Server(memory=memory, port=0) as server:
        yield server


def raw_client(plc):
    client = Type3E(plctype="Q")
    client.connect(*plc.address)
    return client


def test_status_decodes_raw_device_values(plc):
    with LineController(*plc.address) as hmi:
        status = hmi.status()
    assert (status.running, status.alarm) == (True, False)
    assert (status.target, status.count) == (10, 3)
    assert status.temperature_c == pytest.approx(25.3)


def test_start_writes_target_and_request_bit(plc):
    with LineController(*plc.address) as hmi:
        hmi.start(42)
    client = raw_client(plc)
    try:
        assert client.batchread_wordunits(dev.TARGET_COUNT, 1) == [42]
        assert client.batchread_bitunits(dev.START_REQUEST, 1) == [1]
    finally:
        client.close()


def test_start_rejects_bad_target_before_touching_the_plc(plc):
    with LineController(*plc.address) as hmi:
        with pytest.raises(ValueError):
            hmi.start(0)


def test_full_run_with_simulated_ladder_program(plc):
    host, port = plc.address
    with PlantSimulator(host, port), LineController(host, port) as hmi:
        hmi.start(5)
        for _ in range(500):  # poll up to ~5 s
            status = hmi.status()
            if status.count == 5 and not status.running:
                break
            time.sleep(0.01)
        assert (status.count, status.running, status.alarm) == (5, False, False)


def test_lost_reply_is_recovered_by_reconnecting(memory):
    plan = FaultPlan([{"match": {"command": "0x0401"}, "action": {"type": "drop"}}])
    with Server(memory=memory, port=0, fault_plan=plan) as plc:
        with LineController(*plc.address, timeout=0.3) as hmi:
            assert hmi.status().count == 3
            assert hmi.reconnects == 1


def test_plc_error_code_is_reported_not_retried(memory):
    plan = FaultPlan([{"match": {"command": "0x0401"}, "times": 99,
                       "action": {"type": "bad_end_code", "code": 0xC051}}])
    with Server(memory=memory, port=0, fault_plan=plan) as plc:
        with LineController(*plc.address) as hmi:
            with pytest.raises(LineError) as info:
                hmi.status()
            assert info.value.end_code == "0xC051"
            assert hmi.reconnects == 0


def test_unreachable_plc_gives_up_after_the_retry_budget(memory):
    plan = FaultPlan([{"match": {"command": "0x0401"}, "times": 99,
                       "action": {"type": "drop"}}])
    with Server(memory=memory, port=0, fault_plan=plan) as plc:
        with LineController(*plc.address, retries=1, timeout=0.2) as hmi:
            with pytest.raises(LineUnreachable):
                hmi.status()
            assert hmi.reconnects == 2


def test_overheating_raises_a_latched_alarm_and_blocks_new_runs(plc):
    host, port = plc.address
    with PlantSimulator(host, port) as plant, LineController(host, port) as hmi:
        plant.force_temperature_x10(795)  # the plant is the only writer of D102
        hmi.start(20)
        for _ in range(500):
            if hmi.status().alarm:
                break
            time.sleep(0.01)
        assert hmi.status().alarm
        hmi.start(5)  # refused while the alarm is latched
        time.sleep(0.2)
        status = hmi.status()
        assert status.alarm and not status.running


def test_one_shot_start_request_is_not_resent_after_a_lost_reply():
    # Request 1 writes D100 (safe to retry); request 2 writes the one-shot M0 bit.
    # Its reply is lost: the PLC DID receive it, so re-sending could restart a run.
    plan = FaultPlan([{"match": {"connection": 1, "nth": 2}, "action": {"type": "drop"}}])
    with Server(memory=Memory(), port=0, fault_plan=plan) as server:
        with LineController(*server.address, timeout=0.3) as hmi:
            with pytest.raises(LineUnreachable, match="outcome unknown"):
                hmi.start(5)
            assert hmi.reconnects == 0  # no blind retry of the request bit
            assert hmi.status().target == 5  # the caller checks status instead
