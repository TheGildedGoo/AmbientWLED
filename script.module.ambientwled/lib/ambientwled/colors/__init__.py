"""Colour sampling and the worker colour pipe."""

from ambientwled.colors.mapper import detect_content_rect, edge_sequence, map_frame
from ambientwled.colors.pipeline import ColorPipeline, pack_rgbw

__all__ = [
    "ColorPipeline",
    "detect_content_rect",
    "edge_sequence",
    "map_frame",
    "pack_rgbw",
    "trivial_mean_rgb",
]


def trivial_mean_rgb(pixels):
    """Mean of (r, g, b) tuples. Kept for the original fixture test."""
    if not pixels:
        return (0, 0, 0)
    n = len(pixels)
    r = sum(p[0] for p in pixels) // n
    g = sum(p[1] for p in pixels) // n
    b = sum(p[2] for p in pixels) // n
    return (r, g, b)
