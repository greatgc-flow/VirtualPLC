"""Pinned pymcprotocol cross-process interoperability (G0-C, G2).
This test is opt-in via `--run-pymc`: pure-Python server implementation is NOT shipped.
"""
from __future__ import annotations
import importlib.metadata,os
import pytest

@pytest.mark.compat
@pytest.mark.parametrize('mode',['D_WORD','M_BIT'])
def test_pymcprotocol_roundtrip(request,mode):
    if not request.config.getoption('--run-pymc'):
        pytest.skip('separate external compatibility gate; run with --run-pymc and MC_PINNED_PYMC_VERSION')
    pin=os.environ.get('MC_PINNED_PYMC_VERSION','')
    if not pin:pytest.fail('G0-C OPEN: set audited MC_PINNED_PYMC_VERSION',pytrace=False)
    try:installed=importlib.metadata.version('pymcprotocol')
    except importlib.metadata.PackageNotFoundError:pytest.fail('pymcprotocol not installed',pytrace=False)
    assert installed==pin,f'actual pymcprotocol {installed} differs from pinned {pin}'
    import pymcprotocol
    # Skip/fail and verify version BEFORE opening a server subprocess.
    server=request.getfixturevalue('server')
    plc=pymcprotocol.Type3E()
    try:
        plc.connect('127.0.0.1',server['port'])
        if mode=='D_WORD':
            vals=[0,0x1234,0x7FFF]
            plc.batchwrite_wordunits(headdevice='D100',values=vals)
            assert plc.batchread_wordunits(headdevice='D100',readsize=3)==vals
        else:
            vals=[1,0,1,1,0]
            plc.batchwrite_bitunits(headdevice='M10',values=vals)
            assert plc.batchread_bitunits(headdevice='M10',readsize=5)==vals
    finally:plc.close()
