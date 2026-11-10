"""Step 2 - a living bottling line: HMI code + simulated PLC program.

    python 02_line_demo.py

Three actors, all in one process:
  * VirtualPLC     - the PLC's memory and MC protocol endpoint (virtual_plc.Server)
  * PlantSimulator - stands in for the PLC's ladder program (plant.py)
  * LineController - YOUR application, written with pymcprotocol (line_client.py)

Scenario: start a run of 10 bottles, watch it finish, then overheat the tank
and see the PLC raise the alarm and refuse the next start.
"""

import time

from virtual_plc import Memory, Server

from line_client import LineController
from plant import PlantSimulator


def started(hmi):
    """True once the run has begun (also true if it already finished: count > 0)."""
    status = hmi.status()
    return status.running or status.count > 0


def wait_for(condition, what, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = condition()
        if value:
            return value
        time.sleep(0.01)
    raise TimeoutError("timed out waiting for " + what)


def show(title, status):
    print("%-22s running=%-5s alarm=%-5s count=%2d/%-2d temp=%.1f C"
          % (title, status.running, status.alarm, status.count, status.target,
             status.temperature_c))


def main():
    memory = Memory()  # sparse: untouched devices read as 0
    memory.write_words("D", 102, [250])  # tank starts at 25.0 C (seed BEFORE start)

    with Server(memory=memory, port=0) as plc:
        host, port = plc.address
        with PlantSimulator(host, port) as plant, LineController(host, port) as hmi:
            show("idle", hmi.status())

            hmi.start(10)
            wait_for(lambda: started(hmi), "line to start")
            wait_for(lambda: not hmi.status().running, "line to finish")
            show("run of 10 finished", hmi.status())

            # Force an over-temperature condition: 79.5 C, so the next heating tick
            # crosses 80.0 C. We ask the plant (the only writer of D102) to do it.
            plant.force_temperature_x10(795)

            hmi.start(20)
            wait_for(lambda: hmi.status().alarm, "alarm")
            show("after overheating", hmi.status())

            # The alarm is latched: the PLC logic refuses to start until an operator
            # resets it (this demo's plant has no reset button on purpose).
            hmi.start(5)
            time.sleep(0.1)
            show("start refused (alarm)", hmi.status())


if __name__ == "__main__":
    main()
