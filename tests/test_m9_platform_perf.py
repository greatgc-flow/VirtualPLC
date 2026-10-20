"""M9 local-only P0: platform fingerprint and deterministic benchmark, no SLA.

Windows gate CASE-0128 and cross-OS CASE-0044 remain NOT_RUN on Linux.
Neither client compatibility nor vendor error-code fidelity is claimed.
"""
from __future__ import annotations
import platform
import sys
import pytest
from scripts.m9_benchmark import (measure, percentile, read_words,
                                  logical_read, environment)

@pytest.fixture(scope='module')
def report():
    return measure(rounds=12)


def test_case_0129_linux_python_and_fingerprint(record_property, report):
    if sys.platform != 'linux':
        pytest.skip('CASE-0129 requires a Linux runner')
    record_property('case_id', 'CASE-0129')
    assert sys.version_info >= (3, 11)
    assert report['environment']['platform'] == 'linux'
    assert report['environment']['python'] == platform.python_version()
    assert report['environment']['pytest']
    assert report['environment']['process_rss_peak_kib'] is not None
    assert report['measurements'][0]['rounds'] == 12


def test_case_0047_percentiles_and_rss_baseline(record_property, report):
    record_property('case_id', 'CASE-0047')
    assert report['no_performance_sla'] and report['release'] == 'HOLD'
    assert report['environment']['os']
    for x in report['measurements']:
        assert 0 <= x['min_ms'] <= x['p50_ms'] <= x['p95_ms'] <= x['p99_ms'] <= x['max_ms']
        assert x['rounds'] == 12
        assert len(x['result_checksum_sha256']) == 64
    if sys.platform == 'linux':
        assert report['environment']['process_rss_peak_kib'] > 0


def test_case_0132_deterministic_100_1000_chunks(record_property, report):
    record_property('case_id', 'CASE-0132')
    samples = report['measurements']
    assert [m['words'] for m in samples] == [100, 1000]
    assert [m['requests_per_logical_read'] for m in samples] == [1, 2]
    assert all(m['rounds'] == 12 for m in samples)
    assert all(m['p99_ms'] >= m['p50_ms'] for m in samples)


@pytest.mark.parametrize('sample,p',[([],0.5),([1,2],-0.1),([1,2],1.1)])
def test_percentile_rejects_bad_input(sample,p):
    with pytest.raises(ValueError):
        percentile(sample,p)


def test_percentile_interpolation():
    assert percentile([1,3,5],0.5) == 3
    assert percentile([1,3,5],0.95) == 4.8


def test_out_of_range_wire_rejected_before_send():
    with pytest.raises(ValueError):
        read_words(None,0,1000)


def test_benchmark_invalid_settings_rejected():
    with pytest.raises(ValueError):
        measure(rounds=1)
    with pytest.raises(ValueError):
        measure(rounds=2, sizes=(100,2000))
