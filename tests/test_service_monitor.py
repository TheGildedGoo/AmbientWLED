# -*- coding: utf-8 -*-
"""Load the real service module against a stub of xbmc and run the monitor loop."""
from __future__ import annotations

import importlib.util
import os
import sys
import time
import types
import unittest

LIB = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "script.module.ambientwled", "lib")
)
SERVICE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "script.service.ambientwled"))


class _Monitor(object):
    def __init__(self, *args, **kwargs):
        pass

    def abortRequested(self):
        return False

    def waitForAbort(self, timeout=0):
        return True


class _Player(object):
    def __init__(self, *args, **kwargs):
        pass

    def isPlayingVideo(self):
        return False


class _Addon(object):
    def __init__(self, addon_id=""):
        self.id = addon_id
        self.settings = {}

    def getSetting(self, key):
        return "" if key not in self.settings else str(self.settings[key])

    def getSettingBool(self, key):
        return str(self.settings.get(key, "")).lower() in ("true", "1")

    def getSettingInt(self, key):
        try:
            return int(self.settings.get(key) or 0)
        except (TypeError, ValueError):
            return 0

    def getLocalizedString(self, code):
        return "s%s" % code

    def setSetting(self, key, value):
        self.settings[key] = value

    def openSettings(self):
        self.opened = True


class _Dialog(object):
    def ok(self, *args, **kwargs):
        return True

    def notification(self, *args, **kwargs):
        return None

    def select(self, *args, **kwargs):
        return -1

    def yesno(self, *args, **kwargs):
        return False

    def numeric(self, *args, **kwargs):
        return ""

    def input(self, *args, **kwargs):
        return ""


def _install_stubs():
    xbmc = types.ModuleType("xbmc")
    xbmc.LOGINFO = 1
    xbmc.LOGWARNING = 2
    xbmc.LOGERROR = 3
    xbmc.Monitor = _Monitor
    xbmc.Player = _Player
    xbmc.log = lambda *args, **kwargs: None

    class _RenderCapture(object):
        def getAspectRatio(self):
            return 1.778

        def capture(self, width, height, flags=0):
            self.size = (int(width), int(height))

        def getImage(self, wait_ms=0):
            width, height = getattr(self, "size", (96, 54))
            return bytes((20, 80, 180, 255)) * (width * height)

    xbmc.RenderCapture = _RenderCapture

    xbmcgui = types.ModuleType("xbmcgui")
    xbmcgui.Dialog = _Dialog
    xbmcgui.NOTIFICATION_INFO = 1
    xbmcgui.INPUT_ALPHANUM = 0

    xbmcaddon = types.ModuleType("xbmcaddon")
    xbmcaddon.Addon = _Addon

    xbmcplugin = types.ModuleType("xbmcplugin")
    xbmcplugin.ended = []

    def end_of_directory(handle, succeeded=True):
        xbmcplugin.ended.append((handle, succeeded))

    xbmcplugin.endOfDirectory = end_of_directory

    sys.modules["xbmc"] = xbmc
    sys.modules["xbmcgui"] = xbmcgui
    sys.modules["xbmcaddon"] = xbmcaddon
    sys.modules["xbmcplugin"] = xbmcplugin
    if LIB not in sys.path:
        sys.path.insert(0, LIB)
    return xbmc


def _load_service():
    _install_stubs()
    path = os.path.join(SERVICE_DIR, "service.py")
    spec = importlib.util.spec_from_file_location("ambientwled_service", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestServiceMonitor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.svc = _load_service()

    def test_monitor_loop_exits_on_abort(self):
        xbmc = sys.modules["xbmc"]
        self.assertTrue(issubclass(self.svc.AmbientMonitor, xbmc.Monitor))
        self.assertTrue(issubclass(self.svc.PlayerHooks, xbmc.Player))
        self.svc.run_service()

    def test_stop_and_screensaver_are_safe_while_idle(self):
        app = self.svc.ServiceApp()
        player = self.svc.PlayerHooks(app)
        monitor = self.svc.AmbientMonitor(app)
        player.onPlayBackStopped()
        player.onPlayBackPaused()
        player.onPlayBackResumed()
        monitor.onScreensaverActivated()
        self.assertFalse(app.streaming)

    def test_video_start_runs_worker_until_stop(self):
        app = self.svc.ServiceApp()
        app.config.enabled = True
        app.config.configured = True
        app.config.video_only = True
        app.config.capture_mode = "native"
        app.config.wled_host = "127.0.0.1"
        app.config.sync_delay_ms = 0
        app.start_stream(True)
        deadline = time.time() + 3.0
        while time.time() < deadline and not app.streaming:
            time.sleep(0.05)
        self.assertTrue(app.streaming)
        # Cover the native probe and at least one map/DDP iteration.
        time.sleep(0.8)
        self.assertTrue(app.streaming)
        player = self.svc.PlayerHooks(app)
        player.onPlayBackStopped()
        self.assertFalse(app.streaming)

    def test_calibrate_script_arg_routes(self):
        _install_stubs()
        inserted = False
        if SERVICE_DIR not in sys.path:
            sys.path.insert(0, SERVICE_DIR)
            inserted = True
        sys.modules.pop("run", None)
        sys.modules.pop("service", None)
        try:
            import service as svc

            called = []
            svc.calibrate_sync = lambda: called.append("calibrate")
            import run

            argv = sys.argv
            sys.argv = ["run.py", "Calibrate_Sync"]
            try:
                run.main()
            finally:
                sys.argv = argv
            self.assertEqual(called, ["calibrate"])
        finally:
            sys.modules.pop("run", None)
            sys.modules.pop("service", None)
            if inserted and SERVICE_DIR in sys.path:
                sys.path.remove(SERVICE_DIR)

    def test_plugin_entry_is_stub_safe(self):
        _install_stubs()
        path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "plugin.program.ambientwled", "default.py")
        )
        spec = importlib.util.spec_from_file_location("ambientwled_plugin", path)
        plugin = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(plugin)
        argv = sys.argv
        sys.argv = ["plugin://plugin.program.ambientwled", "5", ""]
        try:
            plugin.run(5)
        finally:
            sys.argv = argv
        self.assertTrue(sys.modules["xbmcplugin"].ended)


if __name__ == "__main__":
    unittest.main()
