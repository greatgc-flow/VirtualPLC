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
    if model == "qj71e71" and name == "ip_assembly_ms":
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
        self.values = MappingProxyType(values)

    def report(self):
        """JSON-serializable factory/effective values and implemented-vs-reference scope."""
        spec = _MODELS[self.model]
        parameters = {}
        for name, factory in _TIMER_DEFAULTS.items():
            low, high, step = _timer_bound(self.model, spec, name)
            parameters[name] = {
                "value": self.values[name], "default": factory,
                "overridden": self.values[name] != factory,
                "unit": "count" if name == "alive_retries" else "ms",
                "min": low, "max": high, "step": step,
                "effect": "reference_only",
                "source": _source(spec, spec["timer_pages"]),
            }
        for name, factory in _POLICY_DEFAULTS.items():
            parameters[name] = {
                "value": self.values[name], "default": factory,
                "overridden": self.values[name] != factory,
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
