"""Manufacturer-metadata validation; never substitute for official vendor testing."""
import copy
import json
import pytest
from scripts.m14_vendor_profile import G0E_IDS, check_profile, main


def valid():
    return {'model':'FX5U-32MR/ES', 'ethernet_module':'BUILT_IN_ETHERNET',
            'firmware':'example-version-MUST-REPLACE',
            'manual_url':'https://www.mitsubishielectric.com/dl/fa/document/manual/plcf/example.pdf',
            'manual_revision':'example-rev-MUST-REPLACE',
            'behavior':[{'case_id':i,'trigger':'case '+i,
                         'end_code_hex':None,'manual_page':None,'comments':'unverified'}
                        for i in G0E_IDS]}


def test_no_codes_cannot_be_vendor_verified():
    report=check_profile(valid())
    assert report['codes_with_citations']==0
    assert report['missing_code_sources']==6
    assert not report['manufacturer_certified']
    assert report['release']=='HOLD'


@pytest.mark.parametrize('variant', ['missing_model','unknown','extra','duplicate','missing','invalid_hex',
    'page_missing','bad_page','bad_domain','spoof_domain','insecure_url','bad_code_case','empty_comment','missing_firmware'])
def test_forged_or_incomplete_profile_rejected(variant):
    p=valid()
    if variant=='missing_model':p.pop('model')
    if variant=='unknown':p['model']='UNKNOWN'
    if variant=='extra':p['surplus']='extra'
    if variant=='duplicate':p['behavior'][1]['case_id']=p['behavior'][0]['case_id']
    if variant=='missing':p['behavior'].pop()
    if variant=='invalid_hex':p['behavior'][0].update(end_code_hex='C05Z',manual_page=278)
    if variant=='page_missing':p['behavior'][0]['end_code_hex']='C059'
    if variant=='bad_page':p['behavior'][0].update(end_code_hex='C059',manual_page='29')
    if variant=='bad_domain':p['manual_url']='https://evil.example/path'
    if variant=='spoof_domain':p['manual_url']='https://fakemitsubishielectric.com/x'
    if variant=='insecure_url':p['manual_url']='http://www.mitsubishielectric.com/x'
    if variant=='bad_code_case':p['behavior'][0].update(end_code_hex='c059',manual_page=278)
    if variant=='empty_comment':p['behavior'][0]['comments']=''
    if variant=='missing_firmware':p['firmware']='TODO'
    with pytest.raises((ValueError,KeyError)):
        check_profile(p)


def test_code_with_page_still_unattested():
    p=valid();p['behavior'][0].update(end_code_hex='C059',manual_page=90)
    res=check_profile(p)
    assert res['codes_with_citations']==1 and not res['manufacturer_certified']


def test_stdout_matches_local_evidence(capsysbinary,tmp_path):
    p=tmp_path/'v.json';p.write_text(json.dumps(valid()))
    out=tmp_path/'evidence'
    assert main([str(p),'--out',str(out)])==2
    assert capsysbinary.readouterr().out==(out/'console.txt').read_bytes()==(out/'result.json').read_bytes()


def test_manifest_does_not_get_overwritten(capsys,tmp_path):
    p=tmp_path/'v.json';p.write_text(json.dumps(valid()))
    out=tmp_path/'exists';out.mkdir();(out/'keep').write_text('yes')
    assert main([str(p),'--out',str(out)])==2
    assert (out/'keep').read_text()=='yes'
