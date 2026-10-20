"""Fail-closed, minimal TOML server configuration; Python >=3.11 stdlib only.

No dynamic Python, arbitrary imports or network contact is allowed in config.
No config file means defaults. Never allows bind beyond loopback.
"""
from __future__ import annotations
from pathlib import Path
import tomllib

DEFAULTS = {'host': '127.0.0.1', 'port': 5000, 'd_size': 10000, 'm_size': 10000, 'max_body': 4096, 'routes': ['00FFFF0300']}
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
    routes = result['routes']
    if not isinstance(routes, list) or not 1 <= len(routes) <= 16:
        raise ValueError('routes must be a list of 1..16 10-character hex strings')
    if any(type(x) is not str or len(x) != 10 or
           any(c not in '0123456789abcdefABCDEF' for c in x) for x in routes):
        raise ValueError('routes must contain exact hexadecimal byte strings')
    normalized = [x.upper() for x in routes]
    if normalized[0] != '00FFFF0300' or len(set(normalized)) != len(normalized):
        raise ValueError('routes must start with default and be unique')
    if 'FFFFFFFFFF' in normalized:
        raise ValueError('wildcard route prohibited')
    result['routes'] = normalized
    return result


def load_config(path=None):
    if path is None:
        return validate_options({})
    with Path(path).open('rb') as stream:
        data = tomllib.load(stream)
    if set(data) != {'server'} or not isinstance(data['server'], dict):
        raise ValueError('TOML requires one [server] table only')
    return validate_options(data['server'])
