"""Launch one isolated test server per case. Not part of PLC implementation."""
from __future__ import annotations
import os, socket, shlex, subprocess, time
from pathlib import Path
import pytest


def pytest_addoption(parser):
    group=parser.getgroup('MC 3E virtual PLC')
    group.addoption('--server-cmd',action='store',default=os.environ.get('MC_SIM_SERVER_CMD',''),
                    help='Program command, not shell. Must accept --host {host} --port {port} or equivalent placeholders.')
    group.addoption('--run-pymc',action='store_true',default=False,
                    help='Opt-in to pinned pymcprotocol compatibility tests')

@pytest.fixture
def server(request, tmp_path):
    cmdtemplate=request.config.getoption('--server-cmd')
    if not cmdtemplate:
        pytest.fail('RED/NOT_RUN: no implementation command configured. Run --server-cmd "python -m virtual_plc --host {host} --port {port}"',pytrace=False)
    if '{host}' not in cmdtemplate or '{port}' not in cmdtemplate:
        pytest.fail('server command must explicitly use {host} and {port} to prevent remote targeting',pytrace=False)
    with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    command=shlex.split(cmdtemplate.format(host='127.0.0.1',port=port))
    if not command:pytest.fail('empty server command',pytrace=False)
    out=(tmp_path/'server.stdout.log').open('wb')
    err=(tmp_path/'server.stderr.log').open('wb')
    proc=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=out,stderr=err,cwd=Path.cwd())
    try:
        deadline=time.monotonic()+6
        while time.monotonic()<deadline:
            if proc.poll() is not None:
                pytest.fail(f'server exited early: {err.name}, exit {proc.returncode}',pytrace=False)
            try:
                with socket.create_connection(('127.0.0.1',port),timeout=0.2):pass
                break
            except (OSError,TimeoutError):time.sleep(0.04)
        else:pytest.fail(f'server never listened on 127.0.0.1:{port}; see {err.name}',pytrace=False)
        yield {'port':port,'proc':proc,'stdout':out.name,'stderr':err.name}
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:proc.wait(timeout=4)
            except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=3)
        out.close();err.close()
