"""Schema-like predicates used to challenge evidence/incident/change claims.

This module never approves a release. It intentionally fails closed and is
fully offline. All inputs are synthetic examples until separately attested.
"""
from __future__ import annotations
from hashlib import sha256
import json
from pathlib import Path

REQUIRED_CHANGE = ('id','reason','owner','requirements','tests','risk','gate')
REQUIRED_INCIDENT = ('id','trigger','requirement_id','regression_case_id','metric','reviewer')

def valid_change(item):
    return (isinstance(item,dict) and all(item.get(k) for k in REQUIRED_CHANGE)
        and isinstance(item['requirements'],list) and isinstance(item['tests'],list)
        and len(set(item['tests']))==len(item['tests']))

def incident_can_close(item):
    return (isinstance(item,dict) and all(item.get(k) for k in REQUIRED_INCIDENT)
        and item.get('regression_pass') is True and item.get('metric_checked') is True
        and item.get('review_signed') is True)

def incident_reopened(original, observation):
    if not isinstance(original,dict) or not isinstance(observation,dict):
        raise ValueError('invalid incident')
    out=dict(original)
    if observation.get('regression_failed') is True:
        out.update(status='OPEN', review_signed=False, regression_pass=False,
                   new_reproduction=observation.get('evidence_hash'))
    return out

def verify_sources(sources):
    if not isinstance(sources,list):return False
    return all(isinstance(s,dict) and all(isinstance(s.get(k),str) and s[k].strip()
               for k in ('url','revision','license')) for s in sources)

def requires_client_replay(previous, current):
    def mm(s):
        try:
            a,b,*_=str(s).split('.')
            return int(a),int(b)
        except (TypeError,ValueError):
            raise ValueError('invalid version')
    return mm(previous)!=mm(current)

def record_failure(path, *, run_id, seed, failing_frame, case_id):
    if (not isinstance(run_id,str) or not run_id.isascii() or
        not run_id or not all(c.isalnum() or c in '-_' for c in run_id)):
        raise ValueError('invalid run id')
    if type(seed) is not int or type(failing_frame) is not bytes or not isinstance(case_id,str):
        raise ValueError('invalid evidence metadata')
    event={'run_id':run_id,'seed':seed,'case_id':case_id,
           'frame_sha256':sha256(failing_frame).hexdigest(),
           'redacted':True, 'case_result':'FAIL'}
    dst=Path(path)
    dst.write_text(json.dumps(event,sort_keys=True)+'\n',encoding='utf-8')
    return event
