"""Capture helpers: native sizing, black probe, Hyperion bridge."""

from ambientwled.capture.black_detect import BlackDetector, center_luma
from ambientwled.capture.hyperion import HyperionClient, HyperionError, HyperionSource
from ambientwled.capture.native import capture_size, recommend_fps

__all__ = [
    "BlackDetector",
    "HyperionClient",
    "HyperionError",
    "HyperionSource",
    "capture_size",
    "center_luma",
    "recommend_fps",
]
