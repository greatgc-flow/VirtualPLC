"""Composite offline R04CPU CPU-built-in Ethernet configuration preflight.

This module is deliberately an *orchestrator*, not a second vendor fact
table. All documented port/slot and timer validation is delegated to the
independent source-scoped inspectors in ethernet.py. The returned checks are
neither a GX Works3 native-project parser nor physical hardware evidence.
"""

import re

from .ethernet import (
    inspect_reference_rncpu_data_timers,
    inspect_reference_rncpu_external_device_batch,
    inspect_reference_rncpu_remote_opening,
    reference_catalog,
)


def inspect_reference_r04cpu_configuration(
        configuration=None, model="R04CPU", report_slot_gaps=True):
    """Validate manually transcribed GX Works3 R04CPU settings *offline*.

    Parameters
    ----------
    configuration : dict or None, optional
        None means no configuration was supplied; an empty object is an
        explicitly empty selection. Supported optional keys:
          manual_revision: Ethernet manual "AD" or "AG"; AG unverified.
          cpu_manual_revision: CPU module "E" or "I"; I unverified.
            Only gates the supplied opening_method section (A031H).
          opening_method: None, "open_by_program" or "do_not_open_by_program".
          data_timers: A038H override dict; explicit None is INVALID.
          external_devices: None (unknown), [] (empty), or strict rows of
            {"connection_number": int, "plc_port": int or None}.
        Missing sections are never populated from presumed physical PLC
        defaults. Explicit timer {} means use documented reference defaults.
    model : str
        Only the independently sourced R04CPU built-in Ethernet example.
        RJ71EN71 and all other RnCPU models are intentionally rejected.
    report_slot_gaps : bool
        Preserve the underlying independent batch lint's optional advisory.

    Returns
    -------
    dict
        Source-only revision gate and independent diagnostic reports. The
        highest-level state never represents GX Works3 acceptance, active
        service capacity, a network listener or physical device parity.
    """
    if type(model) is not str or model != "R04CPU":
        raise ValueError("only the R04CPU CPU-built-in example is supported")
    if type(report_slot_gaps) is not bool:
        raise ValueError("report_slot_gaps must be a boolean")

    if configuration is None:
        input_state, supplied = "NOT_PROVIDED", {}
    elif type(configuration) is dict:
        input_state = "EMPTY" if not configuration else "PROVIDED"
        supplied = configuration
    else:
        raise ValueError("configuration must be an object or omitted")

    supported = {
        "manual_revision", "cpu_manual_revision", "opening_method",
        "data_timers", "external_devices",
    }
    if set(supplied) - supported:
        raise ValueError("unsupported R04CPU configuration key")

    # The Ethernet Application manual and CPU Module manual are separate
    # source contracts. Validate their edition strings independently.
    for name in ("manual_revision", "cpu_manual_revision"):
        if name in supplied and (
                type(supplied[name]) is not str or
                re.fullmatch(r"[A-Z]{1,2}", supplied[name]) is None):
            raise ValueError(
                "{} requires one or two uppercase ASCII letters".format(name)
            )
    requested_revision = supplied.get("manual_revision")
    requested_cpu_revision = supplied.get("cpu_manual_revision")
    if "data_timers" in supplied and type(supplied["data_timers"]) is not dict:
        raise ValueError("explicit data_timers must be an object, not null")

    # Derived from the existing SSOT: never duplicate edition labels or
    # elevate manufacturer-listed AG to equivalent-to-AD without a clause diff.
    catalog = reference_catalog()["rncpu_builtin"]
    spec = catalog["external_device_configuration_reference"]
    cpu_spec = catalog["remote_opening_reference"]
    revision_gate = spec["manual_revision_gate"]
    cpu_revision_gate = cpu_spec["manual_revision_gate"]
    reference_revision = revision_gate["validated_reference_revision"]
    cpu_reference_revision = cpu_revision_gate["validated_reference_revision"]
    if requested_revision is None:
        revision_state = "UNKNOWN_REQUESTED_REVISION"
    elif requested_revision == reference_revision:
        revision_state = "AD_REFERENCE_ONLY"
    else:
        revision_state = "UNVERIFIED_MANUAL_REVISION"
    if requested_cpu_revision is None:
        cpu_revision_state = "UNKNOWN_REQUESTED_REVISION"
    elif requested_cpu_revision == cpu_reference_revision:
        cpu_revision_state = "E_REFERENCE_ONLY"
    else:
        cpu_revision_state = "UNVERIFIED_MANUAL_REVISION"

    checks = {
        "opening_method": (
            inspect_reference_rncpu_remote_opening(supplied["opening_method"])
            if "opening_method" in supplied else None
        ),
        "data_timers": (
            inspect_reference_rncpu_data_timers(model, supplied["data_timers"])
            if "data_timers" in supplied else None
        ),
        "external_devices": (
            inspect_reference_rncpu_external_device_batch(
                supplied["external_devices"],
                model=model, report_slot_gaps=report_slot_gaps,
            )
            if "external_devices" in supplied else None
        ),
    }

    batch = checks["external_devices"]
    opening = checks["opening_method"]
    batch_state = batch["static_preflight_state"] if batch is not None else None
    opening_state = opening["reconnect_risk_status"] if opening is not None else None

    # Relative priorities preserve an invalid input diagnosis even if the
    # supplied document edition is also unknown. Individual reports always
    # retain their detailed independent findings.
    if input_state in ("NOT_PROVIDED", "EMPTY"):
        overall = input_state
    elif batch_state == "REJECTED_STATIC_SETTINGS":
        overall = "REJECTED_STATIC_SETTINGS"
    elif (revision_state != "AD_REFERENCE_ONLY" or
          ("opening_method" in supplied and requested_cpu_revision is not None and
           cpu_revision_state != "E_REFERENCE_ONLY")):
        overall = "SOURCE_REVISION_NOT_VERIFIED"
    elif (batch_state == "REVIEW_REQUIRED" or
          opening_state in ("UNKNOWN", "DOCUMENTED_REMOTE_RUN_RECONNECT_FAILURE")):
        overall = "REVIEW_REQUIRED"
    else:
        overall = "REFERENCE_CHECKS_ONLY"

    return {
        "model": model,
        "interface": "rncpu_builtin",
        "input_state": input_state,
        "manual_revision_check": {
            "requested_revision": requested_revision,
            "reference_revision": reference_revision,
            "listed_newer_revision": revision_gate["newer_catalog_revision"],
            "newer_revision_comparison": revision_gate["newer_revision_comparison"],
            "status": revision_state,
            "source": spec["source"],
            "catalog_url": revision_gate["catalog_url"],
        },
        "cpu_manual_revision_check": {
            "requested_revision": requested_cpu_revision,
            "reference_revision": cpu_reference_revision,
            "listed_newer_revision": cpu_revision_gate["newer_catalog_revision"],
            "newer_revision_comparison": cpu_revision_gate["newer_revision_comparison"],
            "affects_supplied_opening_method": "opening_method" in supplied,
            "status": cpu_revision_state,
            "source": cpu_spec["source"],
            "catalog_url": cpu_revision_gate["catalog_url"],
        },
        "checks": checks,
        "overall_static_review": overall,
        "status": "OFFLINE_SOURCE_SCOPED_COMPOSITION_NOT_VENDOR_CERTIFIED",
        "not_a_simultaneous_tcp_socket_limit": True,
        "physical_hardware_certified": False,
        "simulator_network_affected": False,
        "notes": [
            "AD facts are scoped to the R04CPU CPU built-in manual example.",
            "Manufacturer AG edition has not been clause-compared with AD.",
            "CPU Module I edition has not been clause-compared with E.",
            "Missing sections do not describe real PLC factory/active settings.",
            "Only existing offline inspectors own vendor tables and diagnostics.",
            "No runtime TCP/UDP, GX Works3 native-project validation, "
            "physical device, or PyPI behavior is changed.",
        ],
    }
