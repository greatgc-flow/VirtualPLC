"""Local MC protocol simulator with optional response faults."""

from importlib.metadata import PackageNotFoundError as _PackageNotFoundError, version as _version

try:
    __version__ = _version("virtual_plc")
except _PackageNotFoundError:
    __version__ = "0.11.0"  # Source-tree use without an installed distribution.

from .ethernet import EthernetSettings
from .faults import FaultPlan
from .udp_faults import UdpFaultPlan
from .memory import Memory, OutOfRange
from .server import Server

__all__ = ["Server", "FaultPlan", "UdpFaultPlan", "Memory", "OutOfRange", "EthernetSettings", "__version__"]
