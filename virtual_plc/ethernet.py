"""GX Works hardware-scoped Ethernet parameters (never a host TCP-stack emulator).

Every factory value carries an official manual/page; network-stack timers remain
reference-only. Selected deterministic MC policy is explicitly simulated.
"""

from copy import deepcopy
from types import MappingProxyType


_TIMER_DEFAULTS = {
    "tcp_ulp_ms": 30000,
    "tcp_zero_window_ms": 10000,
    "tcp_resend_ms": 10000,
    "tcp_end_ms": 20000,
    "ip_assembly_ms": 5000,
    "response_monitor_ms": 30000,
    "alive_start_ms": 600000,
    "alive_interval_ms": 10000,
    "alive_retries": 3,
}

_MODELS = {
    "qj71e71": {
        "profile": "Q",
        "editor": "GX Works2",
        "manual": "SH-080009ENG",
        "url": "https://www.mitsubishielectric.com/dl/fa/document/manual/plc/sh080009/sh080009x.pdf",
        "timer_pages": "38-39",
        "policy_pages": "39",
        "ports": {"auto_open_udp": 5000},
        "timer_step_ms": 500,
        "timer_max_ms": 32767 * 500,
        "retry_max": 32767,
    },
    "lj71e71": {
        "profile": "L",
        "editor": "GX Works2",
        "manual": "SH-081105ENG",
        "url": "https://dl.mitsubishielectric.com/dl/fa/document/manual/plc/sh081105eng/sh081105engg.pdf",
        "timer_pages": "35",
        "policy_pages": "36",
        "ports": {"auto_open_udp": 5000},
        "timer_step_ms": 500,
        "timer_max_ms": 32767 * 500,
        "retry_max": 32767,
    },
    "rj71en71": {
        "profile": "iQ-R",
        "editor": "GX Works3",
        "manual": "SH-081257ENG",
        "url": "https://dl.mitsubishielectric.com/dl/fa/document/manual/plc/sh081257eng/sh081257engad.pdf",
        "timer_pages": "396-397",
        "policy_pages": "322-323",
        "ports": {"auto_open_udp": 5000, "melsoft_udp": 5001, "melsoft_tcp": 5002},
        "timer_step_ms": 100,
        "timer_max_ms": 16383000,
        "retry_max": 99999,
    },
}

_POLICY_DEFAULTS = {"communication_data_code": "binary", "allow_write_during_run": False}


def _source(spec, page):
    return {"manual": spec["manual"], "page": page, "url": spec["url"]}


def _timer_bound(model, spec, name):
    if name == "alive_retries":
        return 1, spec["retry_max"], 1
    step = spec["timer_step_ms"]
    minimum = step if model == "rj71en71" or name in (
        "ip_assembly_ms", "alive_start_ms", "alive_interval_ms"
    ) else 2 * step
    maximum = spec["timer_max_ms"]
    if model in ("qj71e71", "lj71e71") and name == "ip_assembly_ms":
        maximum = 32766 * step
    return minimum, maximum, step


class EthernetSettings:
    """Immutable value snapshot with exact factory-default and fidelity metadata."""

    def __init__(self, model, overrides=None):
        if type(model) is not str or model not in _MODELS:
            raise ValueError("unknown ethernet_model")
        if overrides is None:
            overrides = {}
        if not isinstance(overrides, dict) or set(overrides) - {
            "timers", "communication_data_code", "allow_write_during_run"
        }:
            raise ValueError("ethernet overrides must be an object of supported settings")
        spec = _MODELS[model]
        values = {**_TIMER_DEFAULTS, **_POLICY_DEFAULTS}
        timers = overrides.get("timers", {})
        if not isinstance(timers, dict) or set(timers) - set(_TIMER_DEFAULTS):
            raise ValueError("unsupported ethernet timer")
        for name, value in timers.items():
            minimum, maximum, step = _timer_bound(model, spec, name)
            if type(value) is not int or not minimum <= value <= maximum or value % step:
                raise ValueError(f"{name} requires an integer {minimum}..{maximum}, step {step}")
            values[name] = value
        if "communication_data_code" in overrides:
            value = overrides["communication_data_code"]
            if value not in ("binary", "ascii"):
                raise ValueError("communication_data_code must be binary or ascii")
            values["communication_data_code"] = value
        if "allow_write_during_run" in overrides:
            value = overrides["allow_write_during_run"]
            if type(value) is not bool:
                raise ValueError("allow_write_during_run must be a boolean")
            values["allow_write_during_run"] = value

        if model == "rj71en71" and not (
            values["response_monitor_ms"] >= values["tcp_ulp_ms"]
            >= values["tcp_end_ms"] >= values["tcp_resend_ms"]
            > values["ip_assembly_ms"]
            and values["tcp_resend_ms"] == values["tcp_zero_window_ms"]
        ):
            raise ValueError("RJ71EN71 timer order/zero-window equality constraint violated")

        self.model = model
        self.profile = spec["profile"]
        # Preserve explicit intent even when an override equals the default.
        self._configured = frozenset(set(timers) | (set(overrides) & set(_POLICY_DEFAULTS)))
        self.values = MappingProxyType(values)

    def report(self):
        """JSON-serializable factory/effective values and implemented-vs-reference scope."""
        spec = _MODELS[self.model]
        parameters = {}
        for name, factory in _TIMER_DEFAULTS.items():
            low, high, step = _timer_bound(self.model, spec, name)
            parameters[name] = {
                "value": self.values[name], "default": factory,
                "overridden": name in self._configured,
                "unit": "count" if name == "alive_retries" else "ms",
                "min": low, "max": high, "step": step,
                "effect": "reference_only",
                "source": _source(spec, spec["timer_pages"]),
            }
        for name, factory in _POLICY_DEFAULTS.items():
            parameters[name] = {
                "value": self.values[name], "default": factory,
                "overridden": name in self._configured,
                "unit": "enum" if name == "communication_data_code" else "boolean",
                "choices": ["binary", "ascii"] if name == "communication_data_code"
                           else [False, True],
                "effect": "simulated",
                "source": _source(spec, spec["policy_pages"]),
            }
        return {
            "schema_version": 1,
            "model": self.model,
            "editor": spec["editor"],
            "profile": self.profile,
            "source": _source(spec, f"{spec['timer_pages']};{spec['policy_pages']}"),
            "parameters": parameters,
            "vendor_ports_reference_only": deepcopy(spec["ports"]),
            "simulation_notes": [
                "TCP retransmission, window, FIN and IP fragment timing are controlled by the OS.",
                "Manufacturer timer settings are recorded and validated, not applied to host sockets.",
                "Data-code mismatch is closed/dropped by the simulator; real-module error behavior is unverified.",
                "RUN write denial returns documented 0x0055; physical PLC parity is unverified.",
                "Vendor automatic/MELSOFT ports are not bound; use --listen explicitly.",
                "Simulator --idle-timeout is separate from all vendor timers.",
                "Each independent PLC runs in a separate OS process.",
            ],
        }


def model_catalog():
    """The SSOT for guide --json, CLI introspection and docs references."""
    return {model: EthernetSettings(model).report() for model in _MODELS}


# Vendor FX5 host SLMP port setting. Port 0 is a simulator-only ephemeral
# socket choice, NOT a GX Works3 setting. 1..1023 and 61440..65534 are
# permitted by these manual tables, but are NOT recommended for SLMP.
# SH-082625ENG-H p.100 (CPU); SH-082026ENG-H p.79 (ENET).
_FX5_SLMP_PORT_REFERENCE = {
    "vendor_port_ranges": [[1, 5548], [5570, 65534]],
    "vendor_port_recommended_ranges": [[1024, 5548], [5570, 61439]],
    "vendor_reserved_port_range": [5549, 5569],
}

# Model-specific FX5-ENET existence/alive-check parameters:
# official SH-082026ENG-H printed p.70 (PDF p.71).
# Timer selection is s OR ms; no additional 100-ms step is established
# by this manual page. Values are only reference data, not host socket knobs.
_FX5_ENET_ALIVE_TIMER_REFERENCE = {
    "start": {"default": 600, "unit": "s",
              "bounds": {"s": [1, 16383], "ms": [100, 16383000]}},
    "interval": {"default": 10, "unit": "s",
                 "bounds": {"s": [1, 16383], "ms": [100, 16383000]}},
    "retry": {"default": 3, "unit": "count", "bounds": [1, 32767]},
}

# Reference-only hardware facts. Unsupported models never enter _MODELS, and
# unknown module timers must never be borrowed from Q/L or RJ71EN71.
_REFERENCE_HARDWARE = {
    "fx5_cpu_builtin": {
        "implementation": "research_only",
        "source": {
            "manual": "Mitsubishi FAQ #22320 (FX5 built-in Ethernet)",
            "page": "FAQ #22320, updated 2023-07-04",
            "url": "https://fa-faq.mitsubishielectric.com/faq/show/22320",
        },
        "reference": {
            "connection_limit": 8,
            "connection_limit_scope": "SLMP/MELSOFT/MODBUS-TCP/socket/predefined-protocol combined; documented exclusions apply",
            "slmp_server_frames": ["1E", "3E"],
            **deepcopy(_FX5_SLMP_PORT_REFERENCE),
        },
        "port_source": {
            "manual": "SH-082625ENG-H (FX5 CPU communication)",
            "page": "100",
            "url": "https://dl.mitsubishielectric.com/dl/fa/document/manual/plcf/sh082625eng/sh082625engh.pdf",
        },
        # A target count for one *feature* is not an aggregate count of
        # simultaneously open SLMP/server socket connections.
        "service_specific_connection_reference": {
            "feature": "simple_cpu_communication",
            "target_limits": {
                "FX5U": 16, "FX5UC": 16, "FX5UJ": 8, "FX5S": 8,
            },
            "scope": "not the total Ethernet SLMP/socket connection limit; simple CPU communication target count only",
            "status": "OFFICIAL_MANUAL_REFERENCE_ONLY",
            "source": {
                "manual": "Mitsubishi FAQ #40032",
                "page": "FAQ #40032, 2023-08-24",
                "url": "https://fa-faq.mitsubishielectric.com/faq/show/40032",
            },
        },
        "unverified": [
            "tcp_ulp_ms", "tcp_resend_ms", "response_monitor_ms",
            "model/firmware-specific SLMP default host port", "RUN-write behavior",
        ],
    },
    "fx5_enet": {
        "implementation": "research_only",
        "source": {
            "manual": "SH-082026ENG-H (FX5-ENET)",
            "page": "70, 79",
            "url": "https://dl.mitsubishielectric.com/dl/fa/document/manual/plcf/sh082026eng/sh082026engh.pdf",
        },
        "reference": {
            "communication_data_code_default": "binary",
            "communication_data_code_choices": ["binary", "ascii_x_y_octal", "ascii_x_y_hexadecimal"],
            "opening_method_default": "do_not_open_by_program",
            "default_slmp_host_port": "blank",
            **deepcopy(_FX5_SLMP_PORT_REFERENCE),
            "alive_start_ms": _FX5_ENET_ALIVE_TIMER_REFERENCE["start"]["default"] * 1000,
            "alive_interval_ms": _FX5_ENET_ALIVE_TIMER_REFERENCE["interval"]["default"] * 1000,
            "alive_retries": _FX5_ENET_ALIVE_TIMER_REFERENCE["retry"]["default"],
            "slmp_server_frames": ["1E", "3E"],
            "connection_limit": 32,
            "ascii_xy_numbering_choices": ["octal", "hexadecimal"],
        },
        "protocol_source": {
            "manual": "JY997D56001-K (FX5 SLMP)",
            "page": "41-45, 66-67, 119-122",
            "url": "https://dl.mitsubishielectric.com/dl/fa/document/manual/plcf/jy997d56001/jy997d56001k.pdf",
        },
        "port_source": {
            "manual": "SH-082026ENG-H (FX5-ENET)",
            "page": "79",
            "url": "https://dl.mitsubishielectric.com/dl/fa/document/manual/plcf/sh082026eng/sh082026engh.pdf",
        },
        "alive_timer_source": {
            "manual": "SH-082026ENG-H (FX5-ENET)",
            "page": "70",
            "url": "https://dl.mitsubishielectric.com/dl/fa/document/manual/plcf/sh082026eng/sh082026engh.pdf",
        },
        "alive_timer_reference": deepcopy(_FX5_ENET_ALIVE_TIMER_REFERENCE),
        "unverified": [
            "tcp_ulp_ms", "tcp_zero_window_ms", "tcp_resend_ms",
            "tcp_end_ms", "ip_assembly_ms", "response_monitor_ms",
            "RUN-write behavior", "MC device and frame compatibility",
        ],
    },
    "rncpu_builtin": {
        "implementation": "research_only",
        "source": {
            "manual": "SH-081257ENG-AD (iQ-R built-in Ethernet, system ports)",
            "page": "Appendix 10",
            "url": "https://dl.mitsubishielectric.com/dl/fa/document/manual/plc/sh081257eng/sh081257engad.pdf",
        },
        "reference": {
            "auto_open_udp": 5005,
            "melsoft_udp": 5006,
            "melsoft_tcp": 5007,
        },
        "unverified": [
            "tcp_ulp_ms", "tcp_resend_ms", "response_monitor_ms",
            "per-CPU/firmware editable timer ranges", "RUN-write behavior",
            "MC service parity and MELSOFT handshake",
        ],
    },
}


def reference_catalog():
    """Read-only discovery; these hardware IDs are NOT runnable models."""
    return deepcopy(_REFERENCE_HARDWARE)


def inspect_reference_slmp_port(model, port):
    """Classify one *vendor* FX5 SLMP host port without opening a socket.

    This is an OFFLINE and reference-only GX Works3 preflight for either
    FX5 CPU builtin or FX5-ENET. It never configures Server listeners.
    A positive result is a documented setting-range check, NOT an
    assertion that the real module/firmware will accept connections.
    """
    if type(model) is not str or model not in ("fx5_cpu_builtin", "fx5_enet"):
        raise ValueError("FX5 SLMP reference check requires fx5_cpu_builtin or fx5_enet")
    if type(port) is not int or not 0 <= port <= 65535:
        raise ValueError("vendor SLMP port must be an integer 0..65535")
    entry = _REFERENCE_HARDWARE[model]
    reference = entry["reference"]

    def contains(ranges):
        return any(start <= port <= end for start, end in ranges)

    if port == 0:
        classification = "simulator_only_ephemeral"
    elif contains([reference["vendor_reserved_port_range"]]):
        classification = "vendor_system_reserved"
    elif contains(reference["vendor_port_recommended_ranges"]):
        classification = "recommended"
    elif contains(reference["vendor_port_ranges"]):
        classification = "permitted_not_recommended"
    else:
        classification = "outside_vendor_range"
    return {
        "model": model,
        "port": port,
        "classification": classification,
        "permitted": classification in ("recommended", "permitted_not_recommended"),
        "recommended": classification == "recommended",
        "status": "OFFICIAL_MANUAL_REFERENCE_ONLY",
        "source": deepcopy(entry["port_source"]),
        "physical_hardware_certified": False,
        "simulator_bind_affected": False,
        "note": ("Vendor reference only; 5549..5569 are system-reserved. "
                 "Port 0 is solely VirtualPLC ephemeral binding; "
                 "1..1023 and 61440..65534 are permitted but not recommended. "
                 "Does not inspect firmware or host operating-system port conflicts."),
    }


def inspect_reference_fx5_enet_alive_timers(overrides=None):
    """Validate *reference-only* FX5-ENET existence-check timer settings.

    Does not configure Server, host TCP timers or real Mitsubishi equipment.
    Source: SH-082026ENG-H printed p.70. "Change/Set Timer Value" defaults
    to No; explicit values require the caller to set the flag True.
    """
    allowed = {"change_set_timer_value", "start", "interval", "retry"}
    if overrides is None:
        overrides = {}
    if type(overrides) is not dict or set(overrides) - allowed:
        raise ValueError("FX5-ENET alive timer overrides must be a supported object")
    change = overrides.get("change_set_timer_value", False)
    if type(change) is not bool:
        raise ValueError("change_set_timer_value requires a boolean")
    if not change and any(name in overrides for name in ("start", "interval", "retry")):
        raise ValueError("explicit alive timers require change_set_timer_value=True")

    reference = _REFERENCE_HARDWARE["fx5_enet"]["alive_timer_reference"]
    parameters = {}
    for name in ("start", "interval", "retry"):
        spec = reference[name]
        overridden = name in overrides
        if name == "retry":
            value = overrides[name] if overridden else spec["default"]
            low, high = spec["bounds"]
            if type(value) is not int or not low <= value <= high:
                raise ValueError("retry must be an integer 1..32767")
            parameters[name] = {
                "value": value, "unit": "count",
                "default": spec["default"], "overridden": overridden,
                "min": low, "max": high,
            }
            continue

        option = overrides[name] if overridden else {
            "value": spec["default"], "unit": spec["unit"],
        }
        if type(option) is not dict or set(option) != {"value", "unit"}:
            raise ValueError("{} requires a value and a unit (s or ms)".format(name))
        value = option["value"]
        unit = option["unit"]
        if type(unit) is not str or unit not in spec["bounds"]:
            raise ValueError("{} unit must be s or ms".format(name))
        low, high = spec["bounds"][unit]
        if type(value) is not int or not low <= value <= high:
            raise ValueError("{} {} must be an integer {}..{}".format(name, unit, low, high))
        parameters[name] = {
            "value": value, "unit": unit,
            "milliseconds": value * 1000 if unit == "s" else value,
            "default_milliseconds": spec["default"] * 1000,
            "overridden": overridden, "min": low, "max": high,
        }
    return {
        "model": "fx5_enet",
        "status": "OFFICIAL_MANUAL_REFERENCE_ONLY",
        "source": deepcopy(_REFERENCE_HARDWARE["fx5_enet"]["alive_timer_source"]),
        "change_set_timer_value": change,
        "physical_hardware_certified": False,
        "simulator_network_affected": False,
        "parameters": parameters,
    }
