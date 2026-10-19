from .memory import Memory

def create_memory(*,d_size=10000,m_size=10000):
    return Memory(d_size=d_size,m_size=m_size)
