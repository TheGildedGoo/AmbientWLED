"""Addon settings model. Pure data — no xbmc.

Kodi stores every setting as text. ``Config.from_mapping`` accepts that raw
dict plus real bools/ints from the wizard.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping


DEFAULTS: Dict[str, Any] = {
    "enabled": False,
    "configured": False,
    "video_only": True,
    "wled_host": "192.168.1.50",
    "wled_port": 80,
    "ddp_port": 4048,
    "rgbw": True,
    "white_extract": False,
    "color_order": "GRB",
    "led_count": 264,
    "leds_left": 47,
    "leds_top": 85,
    "leds_right": 47,
    "leds_bottom": 85,
    "start_corner": "bottom_left",
    "direction": "cw",
    "edge_depth_pct": 10,
    "black_threshold": 8,
    "white_suppression": 20,
    "saturation": 120,
    "contrast": 110,
    "gamma": 22,
    "brightness": 180,
    "smoothing": 40,
    "sync_delay_ms": 40,
    "capture_mode": "auto",
    "capture_fps": 25,
    "capture_long_edge": 96,
    "pause_mode": "freeze",
    "fail_soft": "off",
    "fake_cycle": False,
    "fake_cycle_mode": "rainbow",
    "hyperion_host": "127.0.0.1",
    "hyperion_port": 8090,
}

SETTING_KEYS = tuple(DEFAULTS.keys())

_BOOL_KEYS = {
    "enabled",
    "configured",
    "video_only",
    "rgbw",
    "white_extract",
    "fake_cycle",
}
_INT_KEYS = {
    "wled_port",
    "ddp_port",
    "led_count",
    "leds_left",
    "leds_top",
    "leds_right",
    "leds_bottom",
    "edge_depth_pct",
    "black_threshold",
    "white_suppression",
    "saturation",
    "contrast",
    "gamma",
    "brightness",
    "smoothing",
    "sync_delay_ms",
    "capture_fps",
    "capture_long_edge",
    "hyperion_port",
}


def _as_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None or value == "":
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in ("true", "1", "yes", "on")


def _as_int(value: Any, default: int) -> int:
    if value is None or value == "":
        return int(default)
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return int(default)


class Config:
    """Resolved AmbientWLED settings for one service generation."""

    def __init__(self, **values: Any):
        data = dict(DEFAULTS)
        data.update(values)
        self.enabled = _as_bool(data["enabled"], False)
        self.configured = _as_bool(data["configured"], False)
        self.video_only = _as_bool(data["video_only"], True)
        self.wled_host = str(data["wled_host"] or DEFAULTS["wled_host"]).strip()
        self.wled_port = _as_int(data["wled_port"], 80)
        self.ddp_port = _as_int(data["ddp_port"], 4048)
        self.rgbw = _as_bool(data["rgbw"], True)
        self.white_extract = _as_bool(data["white_extract"], False)
        self.color_order = str(data["color_order"] or "GRB").strip() or "GRB"
        self.led_count = max(1, _as_int(data["led_count"], 264))
        self.leds_left = max(0, _as_int(data["leds_left"], 47))
        self.leds_top = max(0, _as_int(data["leds_top"], 85))
        self.leds_right = max(0, _as_int(data["leds_right"], 47))
        self.leds_bottom = max(0, _as_int(data["leds_bottom"], 85))
        self.start_corner = str(data["start_corner"] or "bottom_left").strip().lower()
        self.direction = str(data["direction"] or "cw").strip().lower()
        self.edge_depth_pct = min(40, max(1, _as_int(data["edge_depth_pct"], 10)))
        self.black_threshold = min(64, max(0, _as_int(data["black_threshold"], 8)))
        self.white_suppression = min(100, max(0, _as_int(data["white_suppression"], 20)))
        self.saturation = min(200, max(0, _as_int(data["saturation"], 120)))
        self.contrast = min(200, max(0, _as_int(data["contrast"], 110)))
        self.gamma = min(35, max(10, _as_int(data["gamma"], 22)))
        self.brightness = min(255, max(1, _as_int(data["brightness"], 180)))
        self.smoothing = min(95, max(0, _as_int(data["smoothing"], 40)))
        delay = _as_int(data["sync_delay_ms"], 40)
        delay = max(0, min(200, delay))
        self.sync_delay_ms = delay - (delay % 10)
        self.capture_mode = str(data["capture_mode"] or "auto").strip().lower()
        if self.capture_mode not in ("auto", "native", "hyperion"):
            self.capture_mode = "auto"
        self.capture_fps = min(30, max(15, _as_int(data["capture_fps"], 25)))
        self.capture_long_edge = min(160, max(32, _as_int(data["capture_long_edge"], 96)))
        pause = str(data["pause_mode"] or "freeze").strip().lower()
        self.pause_mode = pause if pause in ("freeze", "fade") else "freeze"
        fail = str(data["fail_soft"] or "off").strip().lower()
        self.fail_soft = fail if fail in ("off", "dim", "hold") else "off"
        self.fake_cycle = _as_bool(data["fake_cycle"], False)
        mode = str(data["fake_cycle_mode"] or "rainbow").strip().lower()
        self.fake_cycle_mode = mode if mode in ("rainbow", "edge") else "rainbow"
        self.hyperion_host = str(data["hyperion_host"] or "127.0.0.1").strip()
        self.hyperion_port = _as_int(data["hyperion_port"], 8090)

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any] | None) -> "Config":
        merged: Dict[str, Any] = dict(DEFAULTS)
        if raw:
            for key in SETTING_KEYS:
                if key in raw and raw[key] not in (None, ""):
                    merged[key] = raw[key]
        return cls(**merged)

    def edge_sum(self) -> int:
        return self.leds_left + self.leds_top + self.leds_right + self.leds_bottom

    def output_count(self) -> int:
        total = self.edge_sum()
        return total if total > 0 else self.led_count

    def as_dict(self) -> Dict[str, Any]:
        return {key: getattr(self, key) for key in SETTING_KEYS}
