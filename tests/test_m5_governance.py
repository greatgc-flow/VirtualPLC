"""Exact CASE-ID policy tests. Passing here never means release approved."""
from __future__ import annotations
import ast
from copy import deepcopy
import json
from pathlib import Path
import sys
import pytest
from scripts.validate_suite import audit, readcases
from scripts.release_gate import assess_release

ROOT = Path(__file__).resolve().parents[1]
CATALOG = {c['id']:c for c in readcases()}
SELECTED = ['CASE-0046', 'CASE-0057', 'CASE-0131', 'CASE-0133',
            'CASE-0150', 'CASE-0152', 'CASE-0153', 'CASE-0154']
assert all(CATALOG[x]['runner']=='static_validator' and CATALOG[x]['phase']=='P0' for x in SELECTED)

@pytest.mark.parametrize('case_id', SELECTED, ids=SELECTED)
def test_governance_case(case_id, record_property):
    record_property('case_id', case_id)
    cases = readcases()
    if case_id == 'CASE-0046':
        result = audit(cases)
        assert not result['errors']
        assert result['p0_requirements_linked']==34 and result['risks_linked']==15
    elif case_id == 'CASE-0057':
        matrix=json.loads((ROOT/'docs/SUPPORT_MATRIX.json').read_text())
        assert matrix['P0']=={'frame':'3E', 'wire':'binary', 'transport':'TCP',
                              'device_memory':['D_word','M_bit'], 'bind':'127.0.0.1'}
        assert {'4E','ASCII','REST'}.issubset(matrix['unsupported_or_future'])
        assert all(not any(x in c['title'].lower() for x in ['4e frame required', 'ascii required', 'rest endpoint required']) for c in cases if c['phase']=='P0')
    elif case_id == 'CASE-0131':
        requirements = {row.split(',')[0] for row in (ROOT/'baseline_v1.1/machine/requirements.csv').read_text().splitlines()[1:]}
        forward = {req for c in cases for req in c['req_ids']}
        assert requirements == forward
        assert all(c['req_ids'] and set(c['req_ids']) <= requirements for c in cases)
    elif case_id == 'CASE-0133':
        # Approved code is Python 3.11+ stdlib only; tests may depend on pytest.
        roots=set(sys.stdlib_module_names) | {'virtual_plc','__future__'}
        for path in (ROOT/'virtual_plc').glob('*.py'):
            parsed=ast.parse(path.read_text())
            for node in ast.walk(parsed):
                if isinstance(node,ast.Import):
                    names=[alias.name for alias in node.names]
                elif isinstance(node,ast.ImportFrom) and node.level==0:
                    names=[node.module or '']
                else:
                    names=[]
                assert all(name.split('.')[0] in roots for name in names),(path,names)
    elif case_id == 'CASE-0150':
        altered=deepcopy(cases)
        candidate=next(c for c in altered if c['phase']=='P2')
        candidate['phase']='P0'
        # A scope/requirement/runner mismatch MUST reject the mutation.
        assert any('SCOPE_LEAK' in e or 'REQUIREMENT_PHASE_LEAK' in e for e in audit(altered)['errors'])
    elif case_id == 'CASE-0152':
        matrix=json.loads((ROOT/'docs/SUPPORT_MATRIX.json').read_text())
        assert matrix['release_gate']=='HOLD'
        assert matrix['P0']['frame']=='3E' and matrix['P0']['wire']=='binary'
        assert '4E' in matrix['unsupported_or_future'] and 'ASCII' in matrix['unsupported_or_future']
    elif case_id == 'CASE-0153':
        # A fully green but static-only report must not be approved.
        report=assess_release({'p0_pass_count': 199, 'observed_failures':0,
                               'unknown_or_duplicate_case_ids':False})
        assert report['status']=='HOLD' and any('MISSING_EXTERNAL_GATE' in e for e in report['errors'])
    elif case_id == 'CASE-0154':
        source={'url':'https://invalid.example/upstream.py','revision':'unverified'}
        report=assess_release({'p0_pass_count':199, 'observed_failures':0,
                               'unknown_or_duplicate_case_ids':False,
                               'third_party_sources':[source]})
        assert report['status']=='HOLD' and 'UNLICENSED_UPSTREAM_SOURCE' in report['errors']
    else:
        raise AssertionError('missing mapping: '+case_id)
