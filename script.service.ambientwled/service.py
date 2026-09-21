import json
import time

import xbmc
import xbmcaddon

from resources.lib.mapper import map_edges, rgb_to_rgbw
from resources.lib.wled import WledClient

ADDON = xbmcaddon.Addon()
MONITOR = xbmc.Monitor()
PLAYER = xbmc.Player()


def _setting(key, default=""):
    value = ADDON.getSetting(key)
    return value if value not in (None, "") else default


def _setting_bool(key):
    return ADDON.getSettingBool(key)


def _setting_int(key, default=0):
    try:
        return ADDON.getSettingInt(key)
    except Exception:
        try:
            return int(_setting(key, str(default)))
        except Exception:
            return default


def _should_run():
    if not _setting_bool("enabled"):
        return False
    if _setting_bool("video_only") and not PLAYER.isPlayingVideo():
        return False
    return True


def _capture_frame(width, height):
    cap = xbmc.RenderCapture()
    cap.capture(width, height)
    deadline = time.time() + 0.25
    while time.time() < deadline:
        if MONITOR.abortRequested():
            return None
        data = cap.getImage(20)
        if data:
            return bytes(data)
    return None


def run():
    xbmc.log("[AmbientWLED] service started", xbmc.LOGINFO)
    last_error = 0.0
    client = None
    live = False

    while not MONITOR.abortRequested():
        host = _setting("wled_host", "192.168.1.50")
        port = _setting_int("wled_port", 80)
        led_count = max(1, _setting_int("led_count", 264))
        fps = max(5, min(30, _setting_int("capture_fps", 20)))
        cap_w = max(32, _setting_int("capture_width", 96))
        cap_h = max(18, _setting_int("capture_height", 54))
        rgbw = _setting_bool("rgbw")
        brightness = max(1, min(255, _setting_int("brightness", 128)))

        if client is None or client.host != host:
            client = WledClient(host, port)

        if not _should_run():
            if live:
                client.release_live()
                live = False
            MONITOR.waitForAbort(0.5)
            continue

        frame = _capture_frame(cap_w, cap_h)
        if not frame:
            now = time.time()
            if now - last_error > 10:
                xbmc.log("[AmbientWLED] no RenderCapture frame", xbmc.LOGWARNING)
                last_error = now
            MONITOR.waitForAbort(1.0 / fps)
            continue

        pixels = map_edges(frame, cap_w, cap_h, led_count)
        if rgbw:
            pixels = [rgb_to_rgbw(r, g, b) for r, g, b in pixels]
        try:
            client.send_ddp(pixels, rgbw=rgbw, brightness=brightness)
            live = True
        except Exception as exc:
            now = time.time()
            if now - last_error > 10:
                xbmc.log("[AmbientWLED] send failed: %s" % exc, xbmc.LOGERROR)
                last_error = now
            live = False

        MONITOR.waitForAbort(1.0 / fps)

    if client and live:
        client.release_live()
    xbmc.log("[AmbientWLED] service stopped", xbmc.LOGINFO)


if __name__ == "__main__":
    run()
