"""Local MC protocol simulator with optional response faults."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("virtual_plc")
except PackageNotFoundError:
    __version__ = "0.5.0"  # Source-tree use without an installed distribution.

from .ethernet import EthernetSettings
from .faults import FaultPlan
from .memory import Memory
from .server import Server

__all__ = ["Server", "FaultPlan", "Memory", "EthernetSettings", "__version__"]
