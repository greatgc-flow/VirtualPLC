"""Independent domain Red-phase contract; explicitly fails until real implementation adapter exists."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
import importlib,os
import pytest

@pytest.fixture
def memory():
    path=os.environ.get('MC_SIM_ADAPTER_MODULE','')
    if not path:
        pytest.fail('RED/NOT_RUN: implement domain adapter, then set MC_SIM_ADAPTER_MODULE=your_package.test_adapter',pytrace=False)
    module=importlib.import_module(path)
    return module.create_memory(d_size=10000,m_size=10000)

def test_new_memory_zeros(memory):
    assert memory.read_words(0,3)==[0,0,0]
    assert memory.read_bits(0,5)==[0]*5

def test_word_boundaries(memory):
    memory.write_words(0,[0,65535]);memory.write_words(9999,[0x1234])
    assert memory.read_words(0,2)==[0,65535]
    assert memory.read_words(9999,1)==[0x1234]

def test_bit_boundaries(memory):
    memory.write_bits(0,[1,0,1]);memory.write_bits(9999,[1])
    assert memory.read_bits(0,3)==[1,0,1]
    assert memory.read_bits(9999,1)==[1]

@pytest.mark.parametrize('head,values',[(9999,[1,2]),(-1,[1]),(10000,[1]),(0,[65536]),(0,[-1]),(0,[])])
def test_invalid_write_never_partially_commits(memory,head,values):
    before=memory.snapshot()
    with pytest.raises((ValueError,IndexError)):
        memory.write_words(head,values)
    assert memory.snapshot()==before

@pytest.mark.parametrize('head,values',[(9999,[1,0]),(-1,[0]),(10000,[1]),(0,[2]),(0,[-1]),(0,[])])
def test_invalid_bit_write_never_partially_commits(memory,head,values):
    before=memory.snapshot()
    with pytest.raises((ValueError,IndexError)):
        memory.write_bits(head,values)
    assert memory.snapshot()==before

def test_reset_clear(memory):
    memory.write_words(100,[10,11]);memory.write_bits(10,[1,1,0]);memory.reset()
    assert memory.read_words(100,2)==[0,0]
    assert memory.read_bits(10,3)==[0,0,0]

def test_snapshot_is_immutable_snapshot(memory):
    memory.write_words(100,[1,2,3]);s=memory.snapshot()
    memory.write_words(100,[4,5,6]);assert list(s['D'][100:103])==[1,2,3]

def test_overlapping_vectors_atomic(memory):
    va=[111]*16;vb=[222]*16
    def op(vals):
        for i in range(50):memory.write_words(500,vals)
    with ThreadPoolExecutor(max_workers=2) as pool:
        f1=pool.submit(op,va);f2=pool.submit(op,vb)
        f1.result(timeout=4);f2.result(timeout=4)
    assert memory.read_words(500,16) in (va,vb)

def test_read_during_overlapping_write_no_torn_vector(memory):
    va=[111]*16;vb=[222]*16
    memory.write_words(500,va)
    def writer():
        for i in range(250):memory.write_words(500,vb if i%2 else va)
    with ThreadPoolExecutor(max_workers=2) as pool:
        f=pool.submit(writer)
        for _ in range(250):assert memory.read_words(500,16) in (va,vb)
        f.result(timeout=5)
