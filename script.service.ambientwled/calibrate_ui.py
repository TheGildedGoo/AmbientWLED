# -*- coding: utf-8 -*-
"""On-screen sync calibration. Remote only.

The white bar is moved on this thread. DDP and the WLED HTTP probe run on a
worker, and the hotspot waits in the same sync-delay queue as live video.
"""
from __future__ import annotations

import os
import threading
import time

import xbmc
import xbmcgui

from ambientwled.calibrate import (
    CALIBRATE_PROPERTY,
    REVOLUTION_S,
    CalibrateClock,
    bar_rect,
    classify_remote_action,
    step_delay_ms,
)
from ambientwled.ddp import DdpSender
from ambientwled.wled_json import WledClient, WledError

_MEDIA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources", "media", "white.png")
_GUI_W = 1920
_GUI_H = 1080


def _log(msg):
    xbmc.log("[AmbientWLED] %s" % msg, xbmc.LOGINFO)


def _geometry(cfg):
    return {
        "leds_left": cfg.leds_left,
        "leds_top": cfg.leds_top,
        "leds_right": cfg.leds_right,
        "leds_bottom": cfg.leds_bottom,
        "start_corner": cfg.start_corner,
        "direction": cfg.direction,
    }


def _set_flag(active):
    try:
        xbmcgui.Window(10000).setProperty(CALIBRATE_PROPERTY, "1" if active else "")
    except Exception as exc:
        _log("calibrate flag failed: %s" % exc)


class _ChaseWorker(threading.Thread):
    """Probe WLED, then send delayed hotspots. Sockets stay off the UI thread."""

    def __init__(self, cfg, clock, stop):
        threading.Thread.__init__(self, name="AmbientWLED-calibrate", daemon=True)
        self.cfg = cfg
        self.clock = clock
        self.stop = stop
        self.unreachable = threading.Event()

    def run(self):
        cfg = self.cfg
        host = (cfg.wled_host or "").strip()
        client = None
        sender = None
        try:
            if not host:
                self.unreachable.set()
                self.stop.wait(0.2)
                return
            client = WledClient(host, port=cfg.wled_port, timeout=2.0)
            reachable = True
            try:
                client.test_connection()
            except WledError as exc:
                reachable = False
                self.unreachable.set()
                _log("calibrate: WLED unreachable at %s: %s" % (host, exc))
            # Let the service release the strip before we take live override.
            if self.stop.wait(0.45):
                return
            if reachable:
                try:
                    client.set_live(True)
                except WledError as exc:
                    self.unreachable.set()
                    _log("calibrate: live override failed: %s" % exc)
            sender = DdpSender(host, port=cfg.ddp_port, rgbw=cfg.rgbw)
            period = 1.0 / 30.0
            while not self.stop.is_set():
                started = time.monotonic()
                frame = self.clock.tick(started)
                if frame:
                    try:
                        sender.send(frame)
                    except Exception as exc:
                        self.unreachable.set()
                        _log("calibrate send failed: %s" % exc)
                remaining = period - (time.monotonic() - started)
                if remaining > 0 and self.stop.wait(remaining):
                    break
        finally:
            if client is not None:
                try:
                    client.set_live(False)
                except Exception:
                    pass
            if sender is not None:
                try:
                    sender.close()
                except Exception:
                    pass


class SyncCalibrateWindow(xbmcgui.Window):
    """Fullscreen Estuary window. Left/Right moves the delay. OK/Back closes."""

    def __init__(self, clock, on_delay):
        xbmcgui.Window.__init__(self)
        self.clock = clock
        self.on_delay = on_delay
        self.closed = False
        self._width = _GUI_W
        self._height = _GUI_H
        self._built = False
        self.bar = None
        self.value = None
        self.fill = None
        self._gauge_x = 0
        self._gauge_y = 0
        self._gauge_w = 1
        self._gauge_h = 8

    def onInit(self):
        if self._built:
            return
        try:
            width = int(self.getWidth() or 0)
            height = int(self.getHeight() or 0)
        except Exception:
            width = height = 0
        if width >= 640 and height >= 480:
            self._width = width
            self._height = height
        self._build(self._width, self._height)

    def _build(self, width, height):
        media = _MEDIA
        self.addControl(xbmcgui.ControlImage(0, 0, width, height, media, 0, "0xFF000000"))
        self.bar = xbmcgui.ControlImage(0, 0, 32, 64, media, 0, "0xFFFFFFFF")
        self.addControl(self.bar)
        self.value = xbmcgui.ControlLabel(
            0,
            height // 2 - 110,
            width,
            120,
            "",
            "font_MainMenu",
            "0xFFFFFFFF",
            alignment=6,
        )
        self.addControl(self.value)
        hint = xbmcgui.ControlLabel(
            int(width * 0.08),
            height // 2 + 20,
            int(width * 0.84),
            90,
            "Left / Right changes delay\nOK or Back when the strip matches",
            "font13",
            "0xFFDDDDDD",
            alignment=6,
        )
        self.addControl(hint)
        self._gauge_w = int(width * 0.46)
        self._gauge_h = max(10, int(min(width, height) * 0.012))
        self._gauge_x = (width - self._gauge_w) // 2
        self._gauge_y = int(height * 0.64)
        self.addControl(
            xbmcgui.ControlImage(
                self._gauge_x,
                self._gauge_y,
                self._gauge_w,
                self._gauge_h,
                media,
                0,
                "0xFF333333",
            )
        )
        self.fill = xbmcgui.ControlImage(
            self._gauge_x,
            self._gauge_y,
            1,
            self._gauge_h,
            media,
            0,
            "0xFFFFFFFF",
        )
        self.addControl(self.fill)
        # Off-screen focus target so Left/Right reach the window, not a button.
        focus = xbmcgui.ControlButton(-20, -20, 1, 1, "")
        self.addControl(focus)
        try:
            self.setFocus(focus)
        except Exception:
            _log("calibrate window has no focus target")
        self._built = True
        self._draw_readout()
        self.update_bar(time.monotonic())

    def onAction(self, action):
        try:
            aid = action.getId()
        except Exception:
            return
        kind = classify_remote_action(aid)
        if kind == "close":
            self.closed = True
            self.close()
        elif kind == "decrease":
            self._nudge(-1)
        elif kind == "increase":
            self._nudge(1)

    def _nudge(self, steps):
        previous = int(self.clock.delay_ms)
        new = step_delay_ms(previous, steps)
        self.clock.set_delay_ms(new)
        if new != previous and self.on_delay is not None:
            try:
                self.on_delay(new)
            except Exception as exc:
                _log("calibrate persist failed: %s" % exc)
        self._draw_readout()

    def _draw_readout(self):
        delay = int(self.clock.delay_ms)
        if self.value is not None:
            self.value.setLabel("%s ms" % delay)
        if self.fill is None:
            return
        span = int(round(self._gauge_w * delay / 200.0))
        if span < 1:
            self.fill.setWidth(1)
            if hasattr(self.fill, "setVisible"):
                self.fill.setVisible(False)
        else:
            if hasattr(self.fill, "setVisible"):
                self.fill.setVisible(True)
            self.fill.setWidth(span)
            self.fill.setPosition(self._gauge_x, self._gauge_y)

    def update_bar(self, now):
        if self.bar is None:
            return
        loc = self.clock.location(now)
        x, y, w, h = bar_rect(loc, self._width, self._height)
        self.bar.setPosition(x, y)
        self.bar.setWidth(w)
        self.bar.setHeight(h)


def run_calibration(cfg, on_delay=None, notify=None):
    """Block until the user presses OK or Back. Safe to call off the render thread's sockets."""
    clock = CalibrateClock(_geometry(cfg), delay_ms=cfg.sync_delay_ms, period_s=REVOLUTION_S)
    clock.started = time.monotonic()
    stop = threading.Event()
    worker = _ChaseWorker(cfg, clock, stop)
    _set_flag(True)
    worker.start()
    window = SyncCalibrateWindow(clock, on_delay)
    toasted = False
    monitor = xbmc.Monitor()
    try:
        window.show()
        if not window._built:
            window.onInit()
        while not window.closed and not monitor.abortRequested():
            window.update_bar(time.monotonic())
            if worker.unreachable.is_set() and not toasted:
                toasted = True
                message = "LEDs aren't connected"
                if notify is not None:
                    try:
                        notify("AmbientWLED", message)
                    except Exception:
                        _log(message)
                else:
                    try:
                        xbmcgui.Dialog().notification(
                            "AmbientWLED",
                            message,
                            xbmcgui.NOTIFICATION_WARNING,
                            4000,
                        )
                    except Exception:
                        _log(message)
            xbmc.sleep(33)
    finally:
        window.closed = True
        stop.set()
        try:
            window.close()
        except Exception:
            pass
        worker.join(timeout=2.5)
        _set_flag(False)
        _log("calibrate sync stopped at %s ms" % clock.delay_ms)
