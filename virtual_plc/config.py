"""Fail-closed, minimal TOML server configuration; Python >=3.11 stdlib only.

No dynamic Python, arbitrary imports or network contact is allowed in config.
No config file means defaults. Never allows bind beyond loopback.
"""
from __future__ import annotations
from pathlib import Path
import tomllib

DEFAULTS = {'host': '127.0.0.1', 'port': 5000, 'd_size': 10000, 'm_size': 10000, 'max_body': 4096}
_ALLOWED = frozenset(DEFAULTS)


def validate_options(options):
    if not isinstance(options, dict) or set(options) - _ALLOWED:
        raise ValueError('unknown server configuration key')
    result = dict(DEFAULTS)
    result.update(options)
    if result['host'] != '127.0.0.1' or type(result['host']) is not str:
        raise ValueError('only IPv4 loopback 127.0.0.1 is permitted')
    if type(result['port']) is not int or not 0 <= result['port'] <= 65535:
        raise ValueError('port must be an integer 0..65535')
    for key in ('d_size', 'm_size'):
        n = result[key]
        if type(n) is not int or not 1 <= n <= 1_000_000:
            raise ValueError(f'{key} must be in 1..1,000,000')
    if type(result['max_body']) is not int or not 12 <= result['max_body'] <= 4096:
        raise ValueError('max_body must be 12..4096')
    return result


def load_config(path=None):
    if path is None:
        return validate_options({})
    with Path(path).open('rb') as stream:
        data = tomllib.load(stream)
    if set(data) != {'server'} or not isinstance(data['server'], dict):
        raise ValueError('TOML requires one [server] table only')
    return validate_options(data['server'])
