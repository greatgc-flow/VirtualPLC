"""Fail-closed independent release policy, separate from unit-test success.

This is a local *policy precheck*, not cryptographic certification. No release
is authorised merely because a JSON report lists PASS. An independent
reviewer must confirm immutable CI artifacts, client captures, vendor profile,
manual OS/performance evidence, and license provenance out of band.
"""
from __future__ import annotations
import json
from pathlib import Path

REQUIRED_EXTERNAL = frozenset({'vendor_profile_approved', 'pinned_client_capture_verified',
    'windows_ci_reviewed', 'linux_ci_reviewed', 'performance_reviewed',
    'security_reviewed', 'independent_release_approval'})


def assess_release(evidence, *, total=199):
    errors = []
    if not isinstance(evidence, dict):
        return {'status': 'HOLD', 'errors': ['NO_VERIFIED_EVIDENCE']}
    if type(total) is not int or total != 199:
        errors.append('P0_TOTAL_MISMATCH')
    if evidence.get('p0_pass_count') != 199:
        errors.append('P0_NOT_ALL_ATTESTED')
    if evidence.get('observed_failures', 1) != 0:
        errors.append('FAILING_CASES')
    if evidence.get('unknown_or_duplicate_case_ids', True):
        errors.append('INVALID_CASE_IDENTITIES')
    # Deliberately not trusting a boolean flag: each evidence item needs a unique
    # review ID plus immutable SHA-256 reference, and approval is NEVER automatic.
    verified = evidence.get('externally_verified', {})
    if not isinstance(verified, dict):
        verified = {}
    for key in sorted(REQUIRED_EXTERNAL):
        value = verified.get(key)
        if not (isinstance(value, dict) and value.get('reviewer') and
                isinstance(value.get('artifact_sha256'), str) and
                len(value['artifact_sha256']) == 64 and
                all(x in '0123456789abcdef' for x in value['artifact_sha256'])):
            errors.append('MISSING_EXTERNAL_GATE:'+key)
    for src in evidence.get('third_party_sources', []):
        if not isinstance(src, dict) or not all(src.get(k) for k in ('url', 'license', 'revision')):
            errors.append('UNLICENSED_UPSTREAM_SOURCE')
    # This tool must NEVER issue APPROVED itself. Approval occurs in an
    # independent human release process, distinct from developer-provided JSON.
    errors.append('MANUAL_RELEASE_SIGNOFF_REQUIRED')
    return {'status': 'HOLD', 'errors': sorted(set(errors))}


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('evidence', type=Path, nargs='?')
    args = p.parse_args()
    doc = json.loads(args.evidence.read_text()) if args.evidence else None
    print(json.dumps(assess_release(doc), ensure_ascii=False, indent=2))
    return 1  # fail closed; never a deploy green check


if __name__ == '__main__':
    raise SystemExit(main())
