"""The ONE place that knows which PLC device means what.

In a real project this table comes from the PLC program's device comment
list. Keeping it in a single module means a re-addressed PLC needs a one-file
change, and the simulator seed (``seed.json``) is the only other place to touch.

    Bits   (M)  HMI -> PLC : M0 start request, M1 stop request
                PLC -> HMI : M10 line running, M11 alarm
    Words  (D)  D100 target bottle count (set by the HMI)
                D101 bottles filled so far (counted by the PLC)
                D102 tank temperature in 0.1 degC units (e.g. 253 = 25.3 degC)
"""

# --- bit devices -------------------------------------------------------
START_REQUEST = "M0"
STOP_REQUEST = "M1"
RUNNING = "M10"
ALARM = "M11"

# --- word devices ------------------------------------------------------
TARGET_COUNT = "D100"
BOTTLE_COUNT = "D101"
TEMPERATURE_X10 = "D102"

# --- scale / limits ----------------------------------------------------
ALARM_TEMPERATURE_X10 = 800  # the PLC raises ALARM at 80.0 degC or above
