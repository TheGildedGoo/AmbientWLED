# -*- coding: utf-8 -*-
"""Couch-remote entry: setup wizard, then settings.

First open (not configured) runs the wizard. Later opens offer the wizard
again or the settings categories.
"""
from __future__ import annotations

import sys

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin

from ambientwled.config import SETTING_KEYS
from ambientwled.preview import chase_frames, rainbow_frames, run_frames, solid_frame
from ambientwled.wled_json import WledClient, WledError
from ambientwled.wizard import WizardActions, WizardStore, WizardUI, run_wizard

SERVICE_ID = "script.service.ambientwled"
PLUGIN_ID = "plugin.program.ambientwled"


def _log(msg, level=None):
    xbmc.log("[AmbientWLED] %s" % msg, level if level is not None else xbmc.LOGINFO)


def _setting_bool(addon, key):
    try:
        return bool(addon.getSettingBool(key))
    except Exception:
        return str(addon.getSetting(key)).lower() in ("true", "1", "yes")


class KodiStore(WizardStore):
    def __init__(self, addon):
        raw = {}
        for key in SETTING_KEYS:
            try:
                raw[key] = addon.getSetting(key)
            except Exception:
                raw[key] = ""
        WizardStore.__init__(self, raw)
        self.addon = addon

    def save(self):
        cfg = self.export()
        for key, value in cfg.as_dict().items():
            _write_setting(self.addon, key, value)


def _write_setting(addon, key, value):
    if isinstance(value, bool):
        try:
            addon.setSettingBool(key, value)
            return
        except Exception:
            addon.setSetting(key, "true" if value else "false")
            return
    if isinstance(value, int) and not isinstance(value, bool):
        try:
            addon.setSettingInt(key, int(value))
            return
        except Exception:
            addon.setSetting(key, str(int(value)))
            return
    try:
        addon.setSettingString(key, str(value))
    except Exception:
        addon.setSetting(key, str(value))


class KodiUI(WizardUI):
    def __init__(self):
        self.dialog = xbmcgui.Dialog()

    def ok(self, title, message):
        self.dialog.ok(title, message)

    def notify(self, title, message):
        try:
            self.dialog.notification(title, message, xbmcgui.NOTIFICATION_INFO, 3000)
        except Exception:
            _log(message)

    def yesno(self, title, message, no, yes):
        try:
            return bool(self.dialog.yesno(title, message, nolabel=no, yeslabel=yes))
        except TypeError:
            return bool(self.dialog.yesno(title, message))

    def select(self, title, options):
        try:
            return int(self.dialog.select(title, options))
        except Exception:
            return -1

    def numeric(self, title, default):
        try:
            raw = self.dialog.numeric(0, title, str(int(default)))
        except Exception:
            return default
        if raw in (None, ""):
            return default
        try:
            return int(raw)
        except (TypeError, ValueError):
            return default

    def input_text(self, title, default):
        kind = getattr(xbmcgui, "INPUT_ALPHANUM", 0)
        try:
            value = self.dialog.input(title, default or "", type=kind)
        except TypeError:
            try:
                value = self.dialog.input(title, default or "")
            except Exception:
                return default or ""
        except Exception:
            return default or ""
        if not value:
            return default or ""
        return value


def _geometry(cfg):
    return {
        "leds_left": cfg.leds_left,
        "leds_top": cfg.leds_top,
        "leds_right": cfg.leds_right,
        "leds_bottom": cfg.leds_bottom,
        "start_corner": cfg.start_corner,
        "direction": cfg.direction,
    }


class LiveActions(WizardActions):
    def test_connection(self, store, ui):
        cfg = store.export()
        try:
            summary = WledClient(cfg.wled_host, port=cfg.wled_port, timeout=2.0).test_connection()
        except WledError as exc:
            ui.ok("AmbientWLED", "Cannot reach WLED at %s\n%s" % (cfg.wled_host, exc))
            return
        count = summary.get("led_count")
        ui.ok(
            "AmbientWLED",
            "Connected to %s (%s LEDs).\nBrightness %s.\n\nA short edge chase follows."
            % (
                summary.get("name") or cfg.wled_host,
                "?" if count is None else count,
                "?" if summary.get("bri") is None else summary.get("bri"),
            ),
        )
        self.edge_chase(store, ui)

    def edge_chase(self, store, ui):
        cfg = store.export()
        ui.notify("AmbientWLED", "Edge chase")
        frames = chase_frames(_geometry(cfg), seconds=2.0, fps=20.0)
        error = run_frames(
            cfg.wled_host,
            frames,
            port=cfg.wled_port,
            ddp_port=cfg.ddp_port,
            rgbw=cfg.rgbw,
        )
        if error:
            ui.notify("AmbientWLED", "Chase sent (HTTP: %s)" % error)

    def solid(self, store, ui):
        cfg = store.export()
        level = max(1, min(255, cfg.brightness))
        colour = (level, int(level * 0.78), int(level * 0.45))
        frames = [solid_frame(cfg.output_count(), colour) for _ in range(20)]
        ui.notify("AmbientWLED", "Solid preview")
        run_frames(cfg.wled_host, frames, port=cfg.wled_port, ddp_port=cfg.ddp_port, rgbw=cfg.rgbw, fps=20.0)

    def rainbow(self, store, ui):
        cfg = store.export()
        ui.notify("AmbientWLED", "Rainbow")
        frames = rainbow_frames(cfg.output_count(), seconds=2.0, fps=20.0, brightness=cfg.brightness / 255.0)
        run_frames(cfg.wled_host, frames, port=cfg.wled_port, ddp_port=cfg.ddp_port, rgbw=cfg.rgbw)

    def calibrate_sync(self, store, ui):
        cfg = store.export()

        def on_delay(delay_ms):
            store.set("sync_delay_ms", int(delay_ms))
            addon = getattr(store, "addon", None)
            if addon is not None:
                _write_setting(addon, "sync_delay_ms", int(delay_ms))

        try:
            ui_mod = _load_calibrate_ui()
        except Exception as exc:
            ui.ok("AmbientWLED", "Calibrate sync is not available (%s)" % exc)
            return
        ui_mod.run_calibration(cfg, on_delay=on_delay, notify=ui.notify)


def _load_calibrate_ui():
    path = xbmcaddon.Addon(SERVICE_ID).getAddonInfo("path")
    if path and path not in sys.path:
        sys.path.insert(0, path)
    import calibrate_ui

    return calibrate_ui


def open_wizard(addon):
    store = KodiStore(addon)
    finished = run_wizard(KodiUI(), store, LiveActions())
    if finished:
        store.save()
        _log("wizard enabled the service")
    return finished


def run(handle):
    query = sys.argv[2] if len(sys.argv) > 2 else ""
    addon = xbmcaddon.Addon(SERVICE_ID)
    force_wizard = "wizard=1" in query
    configured = _setting_bool(addon, "configured")
    if force_wizard or not configured:
        open_wizard(addon)
    else:
        choice = xbmcgui.Dialog().select("AmbientWLED", ["Setup wizard", "Settings"])
        if choice == 0:
            open_wizard(addon)
        elif choice == 1:
            addon.openSettings()
    if handle >= 0:
        xbmcplugin.endOfDirectory(handle, succeeded=True)


if __name__ == "__main__":
    handle = int(sys.argv[1]) if len(sys.argv) > 1 else -1
    try:
        run(handle)
    except Exception as exc:
        xbmc.log("[AmbientWLED] plugin failed: %s" % exc, xbmc.LOGERROR)
        if handle >= 0:
            try:
                xbmcplugin.endOfDirectory(handle, succeeded=False)
            except Exception:
                pass
