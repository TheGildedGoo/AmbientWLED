# -*- coding: utf-8 -*-
"""AmbientWLED background service (Week 1).

Playback hooks + optional fake DDP colour cycle. Capture arrives Week 2+.
Never blocks the render thread: cycle runs on a worker; queue depth is 1 later.
"""
from __future__ import annotations

import sys
from typing import Optional
import threading
import time

import xbmc
import xbmcaddon
import xbmcgui

ADDON_ID = "script.service.ambientwled"
ADDON = xbmcaddon.Addon(ADDON_ID)


def _log(msg, level=xbmc.LOGINFO):
    xbmc.log("[AmbientWLED] %s" % msg, level)


def _setting_bool(key, default=False):
    try:
        return ADDON.getSettingBool(key)
    except Exception:
        v = ADDON.getSetting(key)
        if v == "":
            return default
        return v.lower() in ("true", "1", "yes")


def _setting_int(key, default=0):
    try:
        return ADDON.getSettingInt(key)
    except Exception:
        try:
            return int(ADDON.getSetting(key) or default)
        except (TypeError, ValueError):
            return default


def _setting_str(key, default=""):
    try:
        v = ADDON.getSettingString(key)
    except Exception:
        v = ADDON.getSetting(key)
    return v if v not in (None, "") else default


class CycleWorker(object):
    """Runs fake_cycle on a daemon thread; stop via Event."""

    def __init__(self):
        self._stop = threading.Event()
        self._thread = None
        self._sender = None
        self._wled = None
        self._unreachable_logged = False

    @property
    def running(self):
        return self._thread is not None and self._thread.is_alive()

    def start(self):
        if self.running:
            return
        if not _setting_bool("enable_on_start", True):
            _log("enable_on_start=false; service idle")
            return
        if not _setting_bool("fake_cycle", False):
            _log("fake_cycle off; waiting for Week 2 capture")
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="AmbientWLED-cycle", daemon=True)
        self._thread.start()

    def stop(self, release_live=True):
        self._stop.set()
        t = self._thread
        if t is not None:
            t.join(timeout=3.0)
        self._thread = None
        if release_live and self._wled is not None:
            try:
                self._wled.set_live(False)
            except Exception as e:
                _log("release live failed: %s" % e, xbmc.LOGWARNING)
        if self._sender is not None:
            try:
                self._sender.close()
            except Exception:
                pass
            self._sender = None

    def _run(self):
        try:
            from ambientwled.ddp import DdpSender
            from ambientwled.fake_cycle import run_cycle
            from ambientwled.wled_json import WledClient, WledError
        except ImportError as e:
            _log("library import failed: %s" % e, xbmc.LOGERROR)
            return

        host = _setting_str("wled_host", "192.168.1.50")
        led_count = max(1, _setting_int("led_count", 120))
        rgbw = _setting_bool("rgbw", True)
        mode = _setting_str("fake_cycle_mode", "rainbow") or "rainbow"
        bri_cap = max(1, min(255, _setting_int("brightness_cap", 128)))
        brightness = bri_cap / 255.0

        self._wled = WledClient(host)
        try:
            info = self._wled.test_connection()
            count = info.get("led_count")
            if count:
                led_count = int(count)
            self._wled.set_live(True)
            self._unreachable_logged = False
            _log("WLED ok: %s leds=%s" % (info.get("name"), led_count))
        except WledError as e:
            if not self._unreachable_logged:
                _log("WLED unreachable at %s: %s — send disabled" % (host, e), xbmc.LOGWARNING)
                self._unreachable_logged = True
            return

        self._sender = DdpSender(host, rgbw=rgbw)
        try:
            run_cycle(
                self._sender,
                led_count,
                mode=mode,
                fps=20.0,
                brightness=brightness,
                should_stop=self._stop.is_set,
            )
        except Exception as e:
            _log("cycle error: %s" % e, xbmc.LOGERROR)
        finally:
            try:
                self._wled.set_live(False)
            except Exception:
                pass


class PlayerHooks(xbmc.Player):
    """OnPlay / OnStop / pause — Week 1 only gates the fake cycle."""

    def __init__(self, worker):
        xbmc.Player.__init__(self)
        self.worker = worker
        self._paused = False

    def onAVStarted(self):
        if _setting_bool("video_only", True) and not self.isPlayingVideo():
            return
        if _setting_bool("fake_cycle", False):
            self.worker.start()

    def onPlayBackStarted(self):
        # Some builds fire this before AV; prefer onAVStarted for video.
        pass

    def onPlayBackStopped(self):
        self._paused = False
        self.worker.stop(release_live=True)

    def onPlayBackEnded(self):
        self.onPlayBackStopped()

    def onPlayBackPaused(self):
        # Week 1: freeze = stop sending (last frame remains on strip via live).
        self._paused = True
        self.worker.stop(release_live=False)

    def onPlayBackResumed(self):
        if self._paused and _setting_bool("fake_cycle", False):
            self.worker.start()
        self._paused = False


class ScreensaverMonitor(xbmc.Monitor):
    def __init__(self, worker):
        xbmc.Monitor.__init__(self)
        self.worker = worker

    def onScreensaverActivated(self):
        self.worker.stop(release_live=True)

    def onSettingsChanged(self):
        # Restart cycle if settings flipped while idle/playing.
        self.worker.stop(release_live=True)
        if _setting_bool("fake_cycle", False) and (
            not _setting_bool("video_only", True) or xbmc.Player().isPlayingVideo()
        ):
            self.worker.start()


def run_service():
    _log("service starting")
    worker = CycleWorker()
    player = PlayerHooks(worker)
    monitor = ScreensaverMonitor(worker)

    # GUI-only / always-on demo when video_only is off
    if _setting_bool("fake_cycle", False) and not _setting_bool("video_only", True):
        worker.start()

    while not monitor.abortRequested():
        if monitor.waitForAbort(1.0):
            break

    worker.stop(release_live=True)
    _log("service stopped")
    del player


def test_connection():
    host = _setting_str("wled_host", "192.168.1.50")
    try:
        from ambientwled.wled_json import WledClient, WledError
    except ImportError as e:
        xbmcgui.Dialog().ok(ADDON.getLocalizedString(30100), "Library missing: %s" % e)
        return
    try:
        summary = WledClient(host).test_connection()
        msg = ADDON.getLocalizedString(30101).format(
            summary.get("name") or host,
            summary.get("led_count") or "?",
        )
        xbmcgui.Dialog().ok(ADDON.getLocalizedString(30100), msg)
    except WledError:
        xbmcgui.Dialog().ok(
            ADDON.getLocalizedString(30100),
            ADDON.getLocalizedString(30102).format(host),
        )


if __name__ == "__main__":
    # xbmc.service entry always loads service.py as __main__ without argv modes.
    # Script entry (run.py) handles test_connection.
    run_service()
