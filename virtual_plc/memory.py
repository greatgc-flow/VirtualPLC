"""Small, atomic and intentionally volatile D/M word/bit memory model."""
from __future__ import annotations
from threading import RLock

class Memory:
    def __init__(self, *, d_size=10000, m_size=10000):
        if any(type(v) is not int or v < 1 or v > 1_000_000 for v in (d_size,m_size)):
            raise ValueError('invalid memory capacity')
        self._d = [0]*d_size
        self._m = [0]*m_size
        self._version = 0
        self._lock = RLock()

    @staticmethod
    def _range(head, n, size):
        if type(head) is not int or type(n) is not int or head < 0 or n < 1 or head > size or n > size - head:
            raise ValueError('invalid memory span')

    def _read(self, kind, head, count):
        with self._lock:
            data = self._d if kind=='D' else self._m
            self._range(head,count,len(data))
            return data[head:head+count]

    def _write(self, kind, head, values):
        if not isinstance(values,(list,tuple)):
            raise ValueError('values must be a sequence')
        maximum = 65535 if kind=='D' else 1
        if not values or any(type(v) is not int or v < 0 or v > maximum for v in values):
            raise ValueError('invalid word/bit')
        with self._lock:
            data = self._d if kind=='D' else self._m
            self._range(head,len(values),len(data))
            data[head:head+len(values)] = values
            self._version += 1

    def read_words(self,head,count):return self._read('D',head,count)
    def write_words(self,head,values):self._write('D',head,values)
    def read_bits(self,head,count):return self._read('M',head,count)
    def write_bits(self,head,values):self._write('M',head,values)

    def reset(self):
        with self._lock:
            self._d[:] = [0]*len(self._d)
            self._m[:] = [0]*len(self._m)
            self._version += 1

    def snapshot(self):
        with self._lock:
            return {'D':tuple(self._d),'M':tuple(self._m),'version':self._version}
