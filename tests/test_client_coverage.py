"""Closed-loop inventory: new client public methods/device constants need tests."""

import inspect
from pathlib import Path

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
        "BIT": ("test_client_coverage.py",),
        "WORD": ("test_client_coverage.py",),
        "DWORD": ("test_client_coverage.py",),
    },
}


def assert_covered(actual, category):
    missing = set(actual) - COVERED[category].keys()
    assert not missing, f"Uncovered pymcprotocol {category}: {sorted(missing)}. Add tests and update COVERED."


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
