"""AmbientWLED shared library — pure Python, no xbmc imports."""

__version__ = "0.2.0"

from ambientwled.config import Config, DEFAULTS
from ambientwled.ddp import DdpSender
from ambientwled.wled_json import WledClient, WledError

__all__ = [
    "Config",
    "DEFAULTS",
    "DdpSender",
    "WledClient",
    "WledError",
    "__version__",
]
