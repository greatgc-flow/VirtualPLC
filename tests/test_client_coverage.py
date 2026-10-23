"""Closed-loop inventory: new client public methods/device constants need tests."""

import ast
import inspect
from pathlib import Path
import textwrap

import pymcprotocol
from pymcprotocol.mcprotocolconst import DeviceConstants
import pytest

# Explicit inventories, independent of introspection. Each value names actual tests.
COVERED = {
    "methods": {
        "connect": ("test_m1_client.py", "test_hardening_api_cli.py"),
        "close": ("test_m1_server_raw.py", "test_hardening_api_cli.py"),
        "setaccessopt": ("test_hardening_protocol.py",),
        "set_subheaderserial": ("test_m6_wire.py", "test_hardening_protocol.py"),
        "batchread_wordunits": ("test_m6_client.py",),
        "batchwrite_wordunits": ("test_m6_client.py",),
        "batchread_bitunits": ("test_m6_client.py",),
        "batchwrite_bitunits": ("test_m6_client.py",),
        "randomread": ("test_hardening_protocol.py",),
        "randomwrite": ("test_hardening_protocol.py",),
        "randomwrite_bitunits": ("test_hardening_protocol.py",),
        "echo_test": ("test_m6_client.py", "test_hardening_protocol.py"),
        "read_cputype": ("test_text_pad.py",),
        "remote_run": ("test_m5_control.py", "test_m6_client.py"),
        "remote_stop": ("test_m5_control.py", "test_m6_client.py"),
        "remote_pause": ("test_m5_control.py", "test_m6_client.py"),
        "remote_latchclear": ("test_m5_memory_lock.py", "test_m6_client.py"),
        "remote_reset": ("test_m5_control.py", "test_m7_client.py"),
        "remote_lock": ("test_m5_memory_lock.py", "test_m6_client.py"),
        "remote_unlock": ("test_m5_memory_lock.py", "test_m6_client.py"),
    },
    "devices": {
        **dict.fromkeys(("SM", "SD", "X", "Y", "M", "B", "D", "W", "R", "ZR"), ("test_m1_client.py", "test_m6_client.py")),
        **dict.fromkeys(("L", "F", "V", "TS", "TC", "TN", "SS", "SC", "SN", "CS", "CC", "CN", "SB", "SW", "DX", "DY"),
                        ("test_m2b_devices.py", "test_m6_client.py")),
        **dict.fromkeys(("LTS", "LTC", "LTN", "LSTS", "LSTN", "LCS", "LCC", "LCN", "LZ", "RD"), ("test_m6_client.py",)),
        "LSTC": ("test_m6_wire.py",),  # constant exists, client lookup does not
        **dict.fromkeys(("STS", "STC", "STN"), ("test_m6_client.py",)),  # client aliases for SS/SC/SN
        "BIT": ("test_client_coverage.py",),
        "WORD": ("test_client_coverage.py",),
        "DWORD": ("test_client_coverage.py",),
    },
}


def assert_covered(actual, category):
    missing = set(actual) - COVERED[category].keys()
    assert not missing, f"Uncovered pymcprotocol {category}: {sorted(missing)}. Add tests and update COVERED."


def lookup_device_names():
    """Read the actual name->code/type branches, including names without constants."""
    names = set()
    for method in (DeviceConstants.get_binary_devicecode,
                   DeviceConstants.get_ascii_devicecode, DeviceConstants.get_devicetype):
        tree = ast.parse(textwrap.dedent(inspect.getsource(method)))
        found = {value.value for node in ast.walk(tree) if isinstance(node, ast.Compare)
                 and isinstance(node.left, ast.Name) and node.left.id == "devicename"
                 for value in node.comparators if isinstance(value, ast.Constant)
                 and isinstance(value.value, str)}
        assert found, ("pymcprotocol lookup source changed: review name->code/type lookup "
                       "and update lookup_device_names plus COVERED before accepting the oracle bump.")
        names.update(found)
    return names


def test_lookup_only_names_are_covered():
    names = lookup_device_names()
    assert {"STS", "STC", "STN"} <= names
    assert_covered(names, "devices")


def test_guard_rejects_lookup_only_addition(monkeypatch):
    original = DeviceConstants.get_binary_devicecode

    def expanded(plctype, devicename):
        if devicename == "FUTURE_LOOKUP_ONLY":
            return 0xFE, 10
        return original(plctype, devicename)

    monkeypatch.setattr(DeviceConstants, "get_binary_devicecode", staticmethod(expanded))
    with pytest.raises(AssertionError, match="Uncovered pymcprotocol devices.*FUTURE_LOOKUP_ONLY"):
        assert_covered(lookup_device_names(), "devices")


@pytest.mark.parametrize("client_class", [pymcprotocol.Type3E, pymcprotocol.Type4E])
def test_every_public_client_method_is_covered(client_class):
    assert_covered([name for name, method in inspect.getmembers(client_class, callable)
                    if not name.startswith("_")], "methods")


def test_every_device_constant_is_covered_and_references_exist():
    assert_covered([name.removesuffix("_DEVICE") for name, value in inspect.getmembers(DeviceConstants) if name.endswith("_DEVICE")], "devices")
    assert (DeviceConstants.BIT_DEVICE, DeviceConstants.WORD_DEVICE, DeviceConstants.DWORD_DEVICE) == ("bit", "word", "dword")
    for inventory in COVERED.values():
        for modules in inventory.values():
            assert modules
            for module in modules:
                assert Path(__file__).with_name(module).is_file(), module


def test_guard_rejects_a_new_public_method_and_device():
    for category in ("methods", "devices"):
        with pytest.raises(AssertionError, match="Uncovered pymcprotocol"):
            assert_covered(["new_future_feature"], category)
