"""AmbientWLED shared library — pure Python, no xbmc imports.

Week 1: WLED JSON helpers, DDP UDP sender, fake color cycle.
Week 2+: 4-edge color mapper (see colors/).
"""

__version__ = "0.1.0"

from ambientwled.wled_json import WledClient, WledError
from ambientwled.ddp import DdpSender

__all__ = ["WledClient", "WledError", "DdpSender", "__version__"]
