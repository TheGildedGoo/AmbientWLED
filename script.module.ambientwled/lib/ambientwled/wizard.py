"""Seven-step couch wizard. Dialogs are injected so tests can walk it.

Remote only: yes/no, select, numeric, and the on-screen text/IP dialog.
No mouse. Defaults match a 264-LED SK6812 around the LG C2
(left 47, top 85, right 47, bottom 85, bottom-left, clockwise).
"""

from __future__ import annotations

from typing import Any, Callable, List, Optional

from ambientwled.config import DEFAULTS, Config

STEP_NAMES = (
    "welcome",
    "wled",
    "strip",
    "geometry",
    "picture",
    "behavior",
    "done",
)


class WizardStore:
    """In-memory settings the wizard edits. ``export`` is a Config."""

    def __init__(self, initial: Optional[dict] = None) -> None:
        self.data = dict(DEFAULTS)
        if initial:
            for key, value in initial.items():
                if key in self.data and value not in (None, ""):
                    self.data[key] = value

    def get(self, key: str) -> Any:
        return self.data.get(key, DEFAULTS.get(key))

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value

    def export(self) -> Config:
        return Config.from_mapping(self.data)


class WizardActions:
    """Side effects (network). The default actions are safe no-ops."""

    def test_connection(self, store: WizardStore, ui: "WizardUI") -> None:
        ui.ok("AmbientWLED", "Test connection is not available in this session.")

    def edge_chase(self, store: WizardStore, ui: "WizardUI") -> None:
        ui.notify("AmbientWLED", "Edge chase skipped")

    def solid(self, store: WizardStore, ui: "WizardUI") -> None:
        ui.notify("AmbientWLED", "Solid preview skipped")

    def rainbow(self, store: WizardStore, ui: "WizardUI") -> None:
        ui.notify("AmbientWLED", "Rainbow preview skipped")

    def calibrate_sync(self, store: WizardStore, ui: "WizardUI") -> None:
        ui.notify("AmbientWLED", "Sync calibration skipped")


class WizardUI:
    def ok(self, title: str, message: str) -> None:
        return None

    def notify(self, title: str, message: str) -> None:
        return None

    def yesno(self, title: str, message: str, no: str, yes: str) -> bool:
        return False

    def select(self, title: str, options: List[str]) -> int:
        return -1

    def numeric(self, title: str, default: int) -> Optional[int]:
        return default

    def input_text(self, title: str, default: str) -> str:
        return default or ""


def run_wizard(ui: WizardUI, store: WizardStore, actions: Optional[WizardActions] = None) -> bool:
    """Walk the seven steps. Return True when the user enables the service."""
    actions = actions or WizardActions()
    steps: List[Callable] = [
        _step_welcome,
        _step_wled,
        _step_strip,
        _step_geometry,
        _step_picture,
        _step_behavior,
        _step_done,
    ]
    index = 0
    while 0 <= index < len(steps):
        try:
            action = steps[index](ui, store, actions)
        except Exception as exc:
            ui.ok("AmbientWLED", "Setup step failed: %s" % exc)
            return False
        if action == "next":
            index += 1
        elif action == "back":
            index -= 1
            if index < 0:
                return False
        else:
            return False
    return bool(store.get("enabled")) and bool(store.get("configured"))


def _step_welcome(ui: WizardUI, store: WizardStore, actions: WizardActions) -> str:
    message = (
        "AmbientWLED lights the strip around the TV while video plays.\n\n"
        "It only talks to WLED on your network. It does not change HDMI, "
        "Dolby Vision, or the Sonos Arc Ultra on eARC.\n\n"
        "Defaults: 264 SK6812 RGBW, left 47, top 85, right 47, bottom 85, "
        "starting bottom-left, clockwise."
    )
    if ui.yesno("AmbientWLED", message, "Cancel", "Next"):
        return "next"
    return "cancel"


def _step_wled(ui: WizardUI, store: WizardStore, actions: WizardActions) -> str:
    while True:
        host = ui.input_text("WLED IP address", str(store.get("wled_host")))
        if host:
            store.set("wled_host", host.strip())
        choice = ui.select(
            "WLED  %s" % store.get("wled_host"),
            [
                "Test connection",
                "HTTP port (%s)" % store.get("wled_port"),
                "DDP port (%s)" % store.get("ddp_port"),
                "Next",
                "Back",
            ],
        )
        if choice == 0:
            try:
                actions.test_connection(store, ui)
            except Exception as exc:
                ui.ok("AmbientWLED", "Test failed: %s" % exc)
        elif choice == 1:
            port = ui.numeric("WLED HTTP port", int(store.get("wled_port") or 80))
            if port is not None:
                store.set("wled_port", int(port))
        elif choice == 2:
            port = ui.numeric("DDP UDP port", int(store.get("ddp_port") or 4048))
            if port is not None:
                store.set("ddp_port", int(port))
        elif choice == 3:
            return "next"
        else:
            return "back"


def _step_strip(ui: WizardUI, store: WizardStore, actions: WizardActions) -> str:
    while True:
        kind = "RGBW (SK6812)" if store.get("rgbw") else "RGB (WS2812B)"
        extract = "on" if store.get("white_extract") else "off"
        choice = ui.select(
            "Strip  %s  %s LEDs" % (kind, store.get("led_count")),
            [
                "Use RGBW (SK6812)",
                "Use RGB (WS2812B)",
                "LED count (%s)" % store.get("led_count"),
                "White extract %s" % extract,
                "Next",
                "Back",
            ],
        )
        if choice == 0:
            store.set("rgbw", True)
        elif choice == 1:
            store.set("rgbw", False)
        elif choice == 2:
            count = ui.numeric("Total LEDs", int(store.get("led_count") or 264))
            if count is not None and int(count) > 0:
                store.set("led_count", int(count))
        elif choice == 3:
            store.set("white_extract", not bool(store.get("white_extract")))
        elif choice == 4:
            return "next"
        else:
            return "back"


def _geometry_message(store: WizardStore) -> str:
    left = int(store.get("leds_left") or 0)
    top = int(store.get("leds_top") or 0)
    right = int(store.get("leds_right") or 0)
    bottom = int(store.get("leds_bottom") or 0)
    total = left + top + right + bottom
    target = int(store.get("led_count") or 0)
    match = "matches" if total == target else "does not match"
    return "Left %s + Top %s + Right %s + Bottom %s = %s (%s LED count %s)" % (
        left,
        top,
        right,
        bottom,
        total,
        match,
        target,
    )


def _edit_count(ui: WizardUI, store: WizardStore, key: str, label: str) -> None:
    value = ui.numeric(label, int(store.get(key) or 0))
    if value is not None and int(value) >= 0:
        store.set(key, int(value))


def _step_geometry(ui: WizardUI, store: WizardStore, actions: WizardActions) -> str:
    while True:
        choice = ui.select(
            _geometry_message(store),
            [
                "Left (%s)" % store.get("leds_left"),
                "Top (%s)" % store.get("leds_top"),
                "Right (%s)" % store.get("leds_right"),
                "Bottom (%s)" % store.get("leds_bottom"),
                "Start corner (%s)" % store.get("start_corner"),
                "Direction (%s)" % store.get("direction"),
                "Edge depth %s%%" % store.get("edge_depth_pct"),
                "Preview edge chase",
                "Set LED count to the sum",
                "Next",
                "Back",
            ],
        )
        if choice == 0:
            _edit_count(ui, store, "leds_left", "LEDs on the left")
        elif choice == 1:
            _edit_count(ui, store, "leds_top", "LEDs on the top")
        elif choice == 2:
            _edit_count(ui, store, "leds_right", "LEDs on the right")
        elif choice == 3:
            _edit_count(ui, store, "leds_bottom", "LEDs on the bottom")
        elif choice == 4:
            picked = ui.select(
                "First LED corner",
                ["bottom_left", "bottom_right", "top_left", "top_right", "Back"],
            )
            if 0 <= picked <= 3:
                store.set("start_corner", ("bottom_left", "bottom_right", "top_left", "top_right")[picked])
        elif choice == 5:
            picked = ui.select("Direction", ["cw", "ccw", "Back"])
            if picked == 0:
                store.set("direction", "cw")
            elif picked == 1:
                store.set("direction", "ccw")
        elif choice == 6:
            depth = ui.numeric("Edge depth percent", int(store.get("edge_depth_pct") or 10))
            if depth is not None:
                store.set("edge_depth_pct", max(1, min(40, int(depth))))
        elif choice == 7:
            try:
                actions.edge_chase(store, ui)
            except Exception as exc:
                ui.ok("AmbientWLED", "Chase failed: %s" % exc)
        elif choice == 8:
            store.set(
                "led_count",
                int(store.get("leds_left"))
                + int(store.get("leds_top"))
                + int(store.get("leds_right"))
                + int(store.get("leds_bottom")),
            )
        elif choice == 9:
            if int(store.get("leds_left")) + int(store.get("leds_top")) + int(
                store.get("leds_right")
            ) + int(store.get("leds_bottom")) != int(store.get("led_count")):
                fix = ui.yesno(
                    "Geometry",
                    _geometry_message(store) + "\n\nUse the sum as the LED count?",
                    "Keep both",
                    "Use the sum",
                )
                if fix:
                    store.set(
                        "led_count",
                        int(store.get("leds_left"))
                        + int(store.get("leds_top"))
                        + int(store.get("leds_right"))
                        + int(store.get("leds_bottom")),
                    )
            return "next"
        else:
            return "back"


def _adjust(ui: WizardUI, store: WizardStore, key: str, label: str, step: int, low: int, high: int) -> None:
    while True:
        value = int(store.get(key))
        choice = ui.select(
            "%s: %s" % (label, value),
            ["Decrease", "Increase", "OK"],
        )
        if choice == 0:
            store.set(key, max(low, value - step))
        elif choice == 1:
            store.set(key, min(high, value + step))
        else:
            return


def _step_picture(ui: WizardUI, store: WizardStore, actions: WizardActions) -> str:
    knobs = [
        ("black_threshold", "Black threshold", 1, 0, 64),
        ("white_suppression", "White suppression", 5, 0, 100),
        ("saturation", "Saturation", 5, 0, 200),
        ("contrast", "Contrast", 5, 0, 200),
        ("gamma", "Gamma (22 = 2.2)", 1, 10, 35),
        ("brightness", "Brightness cap", 5, 1, 255),
        ("smoothing", "Smoothing", 5, 0, 95),
        ("sync_delay_ms", "Sync delay ms", 10, 0, 200),
    ]
    while True:
        options = ["%s (%s)" % (label, store.get(key)) for key, label, _s, _a, _b in knobs]
        options.extend(["Calibrate sync", "Solid preview", "Rainbow preview", "Next", "Back"])
        choice = ui.select("Picture", options)
        if choice is None or choice < 0:
            return "back"
        if 0 <= choice < len(knobs):
            key, label, step, low, high = knobs[choice]
            _adjust(ui, store, key, label, step, low, high)
        elif choice == len(knobs):
            try:
                actions.calibrate_sync(store, ui)
            except Exception as exc:
                ui.ok("AmbientWLED", "Calibrate sync failed: %s" % exc)
        elif choice == len(knobs) + 1:
            try:
                actions.solid(store, ui)
            except Exception as exc:
                ui.ok("AmbientWLED", "Solid preview failed: %s" % exc)
        elif choice == len(knobs) + 2:
            try:
                actions.rainbow(store, ui)
            except Exception as exc:
                ui.ok("AmbientWLED", "Rainbow failed: %s" % exc)
        elif choice == len(knobs) + 3:
            delay = int(store.get("sync_delay_ms") or 0)
            store.set("sync_delay_ms", max(0, min(200, delay - (delay % 10))))
            return "next"
        else:
            return "back"


def _step_behavior(ui: WizardUI, store: WizardStore, actions: WizardActions) -> str:
    while True:
        choice = ui.select(
            "Behaviour",
            [
                "Video only: %s" % ("on" if store.get("video_only") else "off"),
                "Capture: %s" % store.get("capture_mode"),
                "Pause: %s" % store.get("pause_mode"),
                "If capture fails: %s" % store.get("fail_soft"),
                "Hyperion %s:%s" % (store.get("hyperion_host"), store.get("hyperion_port")),
                "Next",
                "Back",
            ],
        )
        if choice == 0:
            store.set("video_only", not bool(store.get("video_only")))
        elif choice == 1:
            picked = ui.select("Capture", ["auto", "native", "hyperion", "Back"])
            if 0 <= picked <= 2:
                store.set("capture_mode", ("auto", "native", "hyperion")[picked])
        elif choice == 2:
            picked = ui.select("Pause", ["freeze", "fade", "Back"])
            if picked == 0:
                store.set("pause_mode", "freeze")
            elif picked == 1:
                store.set("pause_mode", "fade")
        elif choice == 3:
            picked = ui.select("If both captures fail", ["off", "dim", "hold", "Back"])
            if 0 <= picked <= 2:
                store.set("fail_soft", ("off", "dim", "hold")[picked])
        elif choice == 4:
            host = ui.input_text("Hyperion host", str(store.get("hyperion_host")))
            if host:
                store.set("hyperion_host", host.strip())
            port = ui.numeric("Hyperion port", int(store.get("hyperion_port") or 8090))
            if port is not None:
                store.set("hyperion_port", int(port))
        elif choice == 5:
            return "next"
        else:
            return "back"


def _step_done(ui: WizardUI, store: WizardStore, actions: WizardActions) -> str:
    cfg = store.export()
    message = (
        "WLED %s\n"
        "%s LEDs, %s, %s/%s/%s/%s, %s %s\n"
        "Capture %s, video only %s, pause %s, sync %s ms\n\n"
        "Enable AmbientWLED now? It starts with Kodi and waits for video."
    ) % (
        cfg.wled_host,
        cfg.led_count,
        "RGBW" if cfg.rgbw else "RGB",
        cfg.leds_left,
        cfg.leds_top,
        cfg.leds_right,
        cfg.leds_bottom,
        cfg.start_corner,
        cfg.direction,
        cfg.capture_mode,
        "on" if cfg.video_only else "off",
        cfg.pause_mode,
        cfg.sync_delay_ms,
    )
    if not ui.yesno("AmbientWLED", message, "Back", "Enable"):
        return "back"
    store.set("enabled", True)
    store.set("configured", True)
    store.set("fake_cycle", False)
    return "next"
