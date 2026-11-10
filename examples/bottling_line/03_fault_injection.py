"""Step 3 - break the PLC on purpose: response faults and client resilience.

    python 03_fault_injection.py

A fault plan makes VirtualPLC misbehave in a controlled, repeatable way. The
request itself still runs; only the *reply* is damaged. Here we ask: does
LineController survive a slow PLC, a lost reply, a PLC error code and a dropped
connection? (Real PLCs do all of these in the field; this is how you test it
without waiting for one to.)
"""

from virtual_plc import FaultPlan, Memory, Server

from line_client import LineController, LineError, LineUnreachable

READ_ONE_SHOT = {"match": {"command": "0x0401"}, "times": 1}  # command 0x0401 = batch read


def scenario(title, action, expect):
    """Run one scenario: a fresh PLC whose first status read is sabotaged."""
    plan = FaultPlan([dict(READ_ONE_SHOT, action=action)])
    memory = Memory()
    memory.write_words("D", 100, [10, 3, 253])
    with Server(memory=memory, port=0, fault_plan=plan) as plc:
        with LineController(*plc.address, retries=2, timeout=0.4) as hmi:
            try:
                status = hmi.status()
                outcome = "OK count=%d temp=%.1f (reconnects=%d)" % (
                    status.count, status.temperature_c, hmi.reconnects)
            except LineError as error:
                outcome = "LineError end_code=%s (not retried)" % error.end_code
            except LineUnreachable as error:
                outcome = "LineUnreachable (%s)" % error
    print("%-34s -> %s" % (title, outcome))
    assert outcome.startswith(expect), outcome


def lost_start_reply():
    """The reply to the one-shot START bit is lost: report it, never re-send it."""
    plan = FaultPlan([{"match": {"connection": 1, "nth": 2}, "action": {"type": "drop"}}])
    with Server(port=0, fault_plan=plan) as plc:
        with LineController(*plc.address, timeout=0.4) as hmi:
            try:
                hmi.start(5)
                outcome = "OK (unexpected)"
            except LineUnreachable:
                outcome = "LineUnreachable: outcome unknown, not re-sent (reconnects=%d)" % (
                    hmi.reconnects)
    print("%-34s -> %s" % ("lost START reply (drop)", outcome))
    assert outcome.startswith("LineUnreachable"), outcome


def main():
    scenario("slow PLC (delay 0.1 s)", {"type": "delay", "seconds": 0.1}, "OK")
    scenario("lost reply (drop)", {"type": "drop"}, "OK")
    scenario("connection closed (close_before_response)",
             {"type": "close_before_response"}, "OK")
    scenario("PLC error (end code 0xC051)", {"type": "bad_end_code", "code": 0xC051},
             "LineError")
    scenario("unsupported command (0xC059)", {"type": "bad_end_code", "code": 0xC059},
             "LineError")
    lost_start_reply()


if __name__ == "__main__":
    main()
