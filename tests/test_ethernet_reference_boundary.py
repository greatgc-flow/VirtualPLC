"""Architectural characterization of runnable vs offline-only Ethernet ownership.

Reference facts may move, but the legacy import API and the source-scoped
JSON contracts must not drift. No physical PLC, external network, or socket
is used in these tests.
"""

from copy import deepcopy
import importlib
import inspect
import json

import pytest

from virtual_plc.ethernet import EthernetSettings, model_catalog, reference_catalog

REFERENCE_EXPORTS = (
    "reference_catalog",
    "inspect_reference_slmp_port",
    "inspect_reference_fx5_enet_alive_timers",
    "inspect_reference_fx5_simple_cpu_communication",
    "inspect_reference_rncpu_remote_opening",
    "inspect_reference_rncpu_data_timers",
    "inspect_reference_rncpu_external_device",
    "inspect_reference_rncpu_external_device_batch",
)


@pytest.fixture
def separated_modules():
    """This intentionally fails RED until the offline module is extracted."""
    return (importlib.import_module("virtual_plc.ethernet"),
            importlib.import_module("virtual_plc.ethernet_reference"))


@pytest.mark.parametrize("name", REFERENCE_EXPORTS)
def test_legacy_import_and_new_reference_import_are_identical(separated_modules, name):
    legacy, offline = separated_modules
    assert getattr(legacy, name) is getattr(offline, name)
    assert getattr(offline, name).__module__ == "virtual_plc.ethernet_reference"


def test_offline_reference_registry_is_owned_only_once(separated_modules):
    legacy, offline = separated_modules
    assert legacy._REFERENCE_HARDWARE is offline._REFERENCE_HARDWARE
    assert legacy._FX5_SLMP_PORT_REFERENCE is offline._FX5_SLMP_PORT_REFERENCE
    assert legacy._R04CPU_BUILTIN_DATA_TIMERS is offline._R04CPU_BUILTIN_DATA_TIMERS
    assert set(offline.reference_catalog()) == {
        "fx5_cpu_builtin", "fx5_enet", "rncpu_builtin",
    }


def test_offline_reference_module_does_not_import_runtime_settings(separated_modules):
    legacy, offline = separated_modules
    source = inspect.getsource(offline)
    assert "from .ethernet import" not in source
    assert "class EthernetSettings" not in source
    assert not hasattr(offline, "EthernetSettings")
    assert not hasattr(offline, "_MODELS")
    assert EthernetSettings is legacy.EthernetSettings


def test_runnable_models_do_not_absorb_reference_only_hardware(separated_modules):
    _, offline = separated_modules
    runnable = model_catalog()
    reference = offline.reference_catalog()
    assert set(runnable) == {"qj71e71", "lj71e71", "rj71en71"}
    assert not set(runnable).intersection(reference)
    assert all(value["implementation"] == "research_only" for value in reference.values())


@pytest.mark.parametrize("model", ["fx5_cpu_builtin", "fx5_enet", "rncpu_builtin"])
def test_reference_catalog_remains_json_serializable_and_defensively_copied(
        separated_modules, model):
    legacy, offline = separated_modules
    first = offline.reference_catalog()
    initial = deepcopy(first[model])
    first[model]["implementation"] = "mutated"
    second = legacy.reference_catalog()
    assert second[model] == initial
    assert json.loads(json.dumps(second)) == second


@pytest.mark.parametrize("name,args,kwargs", [
    ("inspect_reference_slmp_port", ("fx5_enet", 5000), {}),
    ("inspect_reference_fx5_enet_alive_timers", (), {}),
    ("inspect_reference_fx5_simple_cpu_communication", ("FX5U", "1.110"), {}),
    ("inspect_reference_rncpu_remote_opening", ("do_not_open_by_program",), {}),
    ("inspect_reference_rncpu_data_timers", (), {}),
    ("inspect_reference_rncpu_external_device", (), {"plc_port": 1024}),
    ("inspect_reference_rncpu_external_device_batch", (), {"entries": []}),
])
def test_old_and_new_reference_entry_points_return_the_same_report(
        separated_modules, name, args, kwargs):
    legacy, offline = separated_modules
    from_old = getattr(legacy, name)(*args, **kwargs)
    from_new = getattr(offline, name)(*args, **kwargs)
    assert from_old == from_new
    assert json.loads(json.dumps(from_old)) == from_old


def test_r04cpu_composite_continues_to_use_the_same_offline_single_source(separated_modules):
    _, offline = separated_modules
    from virtual_plc.rncpu_reference import inspect_reference_r04cpu_configuration
    report = inspect_reference_r04cpu_configuration({
        "manual_revision": "AD",
        "opening_method": "do_not_open_by_program",
        "external_devices": [],
        "data_timers": {},
    })
    assert report["checks"]["data_timers"] == offline.inspect_reference_rncpu_data_timers()
    assert report["checks"]["external_devices"] == offline.inspect_reference_rncpu_external_device_batch([])
    assert report["manual_revision_check"]["newer_revision_comparison"] == "NOT_VERIFIED"
    assert report["simulator_network_affected"] is False
