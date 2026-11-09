"""Local MC protocol simulator with optional response faults."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("virtual_plc")
except PackageNotFoundError:
    __version__ = "0.6.0"  # Source-tree use without an installed distribution.

from .ethernet import EthernetSettings
from .faults import FaultPlan
from .udp_faults import UdpFaultPlan
from .memory import Memory, OutOfRange
from .server import Server

__all__ = ["Server", "FaultPlan", "UdpFaultPlan", "Memory", "OutOfRange", "EthernetSettings", "__version__"]
