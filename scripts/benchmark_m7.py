"""M7 deterministic loopback load measurements, NOT a latency SLA or release gate.

1000 aggregate points are split 960+40 to respect the M1 request cap;
they are NOT a single 1000-point MC request. Output is printed byte-for-byte
as written to an artifact. No raw PLC values or IP addresses are logged.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import platform
from pathlib import Path
import socket
import statistics
import sys
import threading
import time
from datetime import datetime, timezone
from virtual_plc.memory import Memory
from virtual_plc.server import Server
from suite.support.wire import request

ROOT=Path(__file__).resolve().parents[1]

def receive(sock,n):
    result=bytearray()
    while len(result)<n:
        part=sock.recv(n-len(result))
        if not part:raise EOFError('benchmark reply truncated')
        result.extend(part)
    return bytes(result)

def exchange(sock,points,head):
    start=time.perf_counter_ns()
    sock.sendall(request(head=head,points=points))
    header=receive(sock,9)
    length=int.from_bytes(header[7:9],'little')
    body=receive(sock,length)
    if header[:2]!=b'\xd0\x00' or body[:2]!=b'\0\0' or len(body)!=2+2*points:
        raise AssertionError('unexpected read reply: benchmark invalid')
    return time.perf_counter_ns()-start

def nearest_rank(values,percent):
    numbers=sorted(values)
    import math
    return numbers[max(0,math.ceil(percent*len(numbers))-1)]

def rss_kib():
    if sys.platform.startswith('linux'):
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return None

def run(iterations=40):
    if type(iterations) is not int or not 10<=iterations<=10000:
        raise ValueError('iterations must be 10..10000')
    memory=Memory()
    memory.write_words(0,[i&0xffff for i in range(1000)])
    result={'schema':'virtualplc-m7-benchmark-v1','timestamp_utc':datetime.now(timezone.utc).isoformat(),
            'platform':platform.platform(),'python':platform.python_version(),
            'iterations':iterations,'network':'127.0.0.1 ONLY',
            'catalog_sha256':hashlib.sha256((ROOT/'suite/catalog/test_cases.jsonl').read_bytes()).hexdigest(),
            'server_sha256':hashlib.sha256((ROOT/'virtual_plc/server.py').read_bytes()).hexdigest(),
            'method':'one persistent TCP connection, serialized read requests; nearest-rank percentiles',
            'platform_attestation':'LOCAL_ONLY_NOT_INDEPENDENT','release':'HOLD','samples':{}}
    with Server(('127.0.0.1',0),memory=memory) as server:
        thread=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':0.01},daemon=True)
        thread.start()
        try:
            with socket.create_connection(server.server_address,timeout=2) as sock:
                sock.settimeout(2)
                for label,chunks in [('100_words',[100]),('1000_words_aggregate',[960,40])]:
                    deltas=[]
                    for _ in range(iterations):
                        total=0
                        offset=0
                        for points in chunks:
                            total+=exchange(sock,points,offset)
                            offset+=points
                        deltas.append(total)
                    result['samples'][label]={'logical_words':sum(chunks),'wire_requests_per_sample':len(chunks),
                        'p50_ms':round(nearest_rank(deltas,0.50)/1e6,4),
                        'p95_ms':round(nearest_rank(deltas,0.95)/1e6,4),
                        'p99_ms':round(nearest_rank(deltas,0.99)/1e6,4),
                        'min_ms':round(min(deltas)/1e6,4),'max_ms':round(max(deltas)/1e6,4)}
                result['rss_peak_kib']=rss_kib()
        finally:
            server.shutdown()
            thread.join(timeout=3)
            if thread.is_alive():raise AssertionError('benchmark thread failed to shut down')
    return result

def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('--iterations',type=int,default=40)
    p.add_argument('--out',type=Path,default=ROOT/'evidence/m7_benchmark.json')
    a=p.parse_args(argv)
    result=run(a.iterations)
    out=a.out if a.out.is_absolute() else ROOT/a.out
    out.parent.mkdir(parents=True,exist_ok=True)
    rendered=json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+'\n'
    out.write_text(rendered,encoding='utf-8')
    print(rendered,end='')

if __name__=='__main__':main()
