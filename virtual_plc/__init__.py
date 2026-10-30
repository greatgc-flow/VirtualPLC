"""Local MC protocol simulator with optional response faults."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("virtual_plc")
except PackageNotFoundError:
    __version__ = "0.4.0"  # Source-tree use without an installed distribution.

from .faults import FaultPlan
from .memory import Memory
from .server import Server

__all__ = ["Server", "FaultPlan", "Memory", "__version__"]
