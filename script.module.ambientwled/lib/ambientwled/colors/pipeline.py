"""Per-LED colour pipe. Runs on the worker, never the render thread.

Order: black threshold → white suppression → saturation → contrast →
gamma → brightness cap → EMA smoothing.

RGBW packing happens after smoothing. Default W = min(R, G, B) with RGB
left intact. ``white_extract`` subtracts that white from RGB.

``sync_delay_ms`` is not applied here — see ``ambientwled.sync_delay``.
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple, Union

RGB = Tuple[int, int, int]
RGBW = Tuple[int, int, int, int]
Pixel = Union[RGB, RGBW]


def gamma_value(gamma: float) -> float:
    """Settings store gamma in tenths (22 → 2.2). Floats below 10 pass through."""
    g = float(gamma)
    if g >= 10.0:
        return g / 10.0
    return g


def _clamp(value: float) -> int:
    if value <= 0:
        return 0
    if value >= 255:
        return 255
    return int(round(value))


def _luma(r: int, g: int, b: int) -> float:
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def pack_rgbw(r: int, g: int, b: int, white_extract: bool = False) -> RGBW:
    """R,G,B,W with W = min(R,G,B). Extract subtracts W from the RGB channels."""
    r = _clamp(r)
    g = _clamp(g)
    b = _clamp(b)
    w = min(r, g, b)
    if white_extract:
        return (r - w, g - w, b - w, w)
    return (r, g, b, w)


class ColorPipeline:
    def __init__(
        self,
        *,
        black_threshold: int = 8,
        white_suppression: int = 20,
        saturation: int = 120,
        contrast: int = 110,
        gamma: float = 22,
        brightness: int = 180,
        smoothing: int = 40,
        rgbw: bool = True,
        white_extract: bool = False,
    ) -> None:
        self.black_threshold = int(black_threshold)
        self.white_suppression = max(0, min(100, int(white_suppression))) / 100.0
        self.saturation = max(0, min(200, int(saturation))) / 100.0
        self.contrast = max(0, min(200, int(contrast))) / 100.0
        self.gamma = max(0.1, gamma_value(gamma))
        self.brightness = max(0, min(255, int(brightness))) / 255.0
        self.smoothing = max(0, min(95, int(smoothing))) / 100.0
        self.rgbw = bool(rgbw)
        self.white_extract = bool(white_extract)
        self._ema: Optional[List[List[float]]] = None

    def reset(self) -> None:
        self._ema = None

    def process_pixel(self, r: int, g: int, b: int, previous: Optional[Sequence[float]] = None):
        if _luma(r, g, b) < self.black_threshold:
            r = g = b = 0
        if self.white_suppression:
            white = min(r, g, b) * self.white_suppression
            r -= white
            g -= white
            b -= white
        if self.saturation != 1.0:
            avg = (r + g + b) / 3.0
            r = avg + (r - avg) * self.saturation
            g = avg + (g - avg) * self.saturation
            b = avg + (b - avg) * self.saturation
        if self.contrast != 1.0:
            r = (r - 128.0) * self.contrast + 128.0
            g = (g - 128.0) * self.contrast + 128.0
            b = (b - 128.0) * self.contrast + 128.0
        if self.gamma != 1.0:
            r = 255.0 * ((max(0.0, r) / 255.0) ** self.gamma)
            g = 255.0 * ((max(0.0, g) / 255.0) ** self.gamma)
            b = 255.0 * ((max(0.0, b) / 255.0) ** self.gamma)
        if self.brightness != 1.0:
            r *= self.brightness
            g *= self.brightness
            b *= self.brightness
        r = max(0.0, min(255.0, r))
        g = max(0.0, min(255.0, g))
        b = max(0.0, min(255.0, b))
        if previous is not None and self.smoothing:
            keep = self.smoothing
            fresh = 1.0 - keep
            r = previous[0] * keep + r * fresh
            g = previous[1] * keep + g * fresh
            b = previous[2] * keep + b * fresh
        return r, g, b

    def process(self, pixels: Sequence[RGB]) -> List[Pixel]:
        if self._ema is None or len(self._ema) != len(pixels):
            self._ema = [[0.0, 0.0, 0.0] for _ in pixels]
            fresh_ema = True
        else:
            fresh_ema = False
        out: List[Pixel] = []
        for i, pixel in enumerate(pixels):
            prev = None if fresh_ema else self._ema[i]
            r, g, b = self.process_pixel(int(pixel[0]), int(pixel[1]), int(pixel[2]), prev)
            self._ema[i][0] = r
            self._ema[i][1] = g
            self._ema[i][2] = b
            ri, gi, bi = _clamp(r), _clamp(g), _clamp(b)
            if self.rgbw:
                out.append(pack_rgbw(ri, gi, bi, self.white_extract))
            else:
                out.append((ri, gi, bi))
        return out
