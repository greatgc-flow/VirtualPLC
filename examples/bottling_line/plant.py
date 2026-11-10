"""PlantSimulator: stands in for the PLC's *ladder program* (the scan logic).

VirtualPLC simulates the PLC's protocol and memory, NOT a ladder program. A real
PLC would run logic such as "if M0 then set M10 and count bottles". For a demo
or a test that needs a living line, this class plays that role from outside:
it is just another MC protocol client that polls the request bits and writes
the status back, exactly like a program inside the PLC would.

(Why a client and not ``Memory`` directly? ``Memory`` must not be touched while
the server is serving; going through a client keeps every access serialized.)

Rules implemented, once per tick:
    start request         -> running = 1, count = 0 (refused while ALARM)
    stop request          -> running = 0 (wins over a simultaneous start)
    running               -> count += 1; target reached -> running = 0
    running / idle        -> temperature rises 0.5 degC / cools 0.5 degC (floor 25.0)
    temperature >= 80.0   -> ALARM = 1 and running = 0
"""

import threading

from pymcprotocol import Type3E

import plc_map as dev


class PlantSimulator:
    def __init__(self, host, port, plctype="Q", tick=0.01):
        self.host, self.port, self.plctype, self.tick = host, port, plctype, tick
        self.ticks = 0
        self.error = None  # set if the scan thread dies; re-raised on exit
        self._forced_temp = None  # see force_temperature_x10()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="plant", daemon=True)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc_info):
        self._stop.set()
        self._thread.join(timeout=5)
        if self.error is not None and exc_info[0] is None:
            raise RuntimeError("plant simulator stopped unexpectedly") from self.error

    def force_temperature_x10(self, value):
        """Set the tank temperature (0.1 degC units) from the test/demo side.

        The plant is the ONLY writer of D102. Writing D102 from a second client
        would race with the plant's read-modify-write scan and could be lost,
        so outside code asks the plant to do it on its next scan instead.
        """
        self._forced_temp = value

    def _run(self):
        client = Type3E(plctype=self.plctype)
        try:
            client.connect(self.host, self.port)
            while not self._stop.is_set():
                self._scan(client)
                self._stop.wait(self.tick)
        except Exception as error:  # do not die silently: report on __exit__
            if not self._stop.is_set():
                self.error = error
        finally:
            try:
                client.close()
            except Exception:
                pass

    def _scan(self, client):
        start, stop = client.batchread_bitunits(dev.START_REQUEST, 2)
        running, alarm = client.batchread_bitunits(dev.RUNNING, 2)
        target, count, temp = client.batchread_wordunits(dev.TARGET_COUNT, 3)

        if self._forced_temp is not None:
            temp, self._forced_temp = self._forced_temp, None
        if start and not alarm:
            running, count = 1, 0
        if stop:  # STOP always wins over START, as in real ladder logic
            running = 0
        if running:
            count += 1
            temp += 5
            if count >= target:
                running = 0
        else:
            temp = max(250, temp - 5)
        if temp >= dev.ALARM_TEMPERATURE_X10:
            alarm, running = 1, 0

        if start:  # consume each one-shot request (only the bit we actually saw)
            client.batchwrite_bitunits(dev.START_REQUEST, [0])
        if stop:
            client.batchwrite_bitunits(dev.STOP_REQUEST, [0])
        client.batchwrite_bitunits(dev.RUNNING, [running, alarm])
        client.batchwrite_wordunits(dev.BOTTLE_COUNT, [count, temp])
        self.ticks += 1
