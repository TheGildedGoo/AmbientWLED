# -*- coding: utf-8 -*-
"""AmbientWLED background service.

xbmc.service entry. The monitor thread only watches playback, screensaver,
and abort. Capture, the colour pipe, the sync delay, and DDP run on workers.
"""
from __future__ import annotations

import threading
import time

import xbmc
import xbmcaddon
import xbmcgui

from ambientwled.calibrate import CALIBRATE_PROPERTY
from ambientwled.capture.black_detect import BlackDetector
from ambientwled.capture.hyperion import HyperionClient, HyperionError, HyperionSource
from ambientwled.capture.native import capture_size, recommend_fps
from ambientwled.colors.mapper import map_frame
from ambientwled.colors.pipeline import ColorPipeline
from ambientwled.config import SETTING_KEYS, Config
from ambientwled.ddp import DdpSender
from ambientwled.fake_cycle import run_cycle
from ambientwled.latest import LatestSlot
from ambientwled.preview import chase_frames, run_frames
from ambientwled.sync_delay import SyncDelay
from ambientwled.wled_json import WledClient, WledError

ADDON_ID = "script.service.ambientwled"
ADDON = xbmcaddon.Addon(ADDON_ID)


def _log(msg, level=None):
    if level is None:
        level = xbmc.LOGINFO
    xbmc.log("[AmbientWLED] %s" % msg, level)


def calibration_active():
    """True while the sync-calibration overlay owns the strip."""
    try:
        return xbmcgui.Window(10000).getProperty(CALIBRATE_PROPERTY) == "1"
    except Exception:
        return False


def load_config(addon=None):
    addon = addon or ADDON
    raw = {}
    for key in SETTING_KEYS:
        try:
            raw[key] = addon.getSetting(key)
        except Exception:
            raw[key] = ""
    return Config.from_mapping(raw)


def _capture_frame(rc, width, height, wait_ms):
    try:
        rc.capture(int(width), int(height))
    except TypeError:
        rc.capture(int(width), int(height), 0)
    image = rc.getImage(int(wait_ms))
    if not image:
        return None
    data = bytes(image)
    if len(data) < width * height * 4:
        return None
    return data


class NativeGrabber(object):
    """RenderCapture on the capture worker. One in-flight frame."""

    def __init__(self, rc, width, height, wait_ms=30):
        self.rc = rc
        self.width = int(width)
        self.height = int(height)
        self.wait_ms = int(wait_ms)

    def read(self):
        if self.rc is None:
            return None
        data = _capture_frame(self.rc, self.width, self.height, self.wait_ms)
        if data is None:
            return None
        return data, self.width, self.height

    def close(self):
        self.rc = None


class ServiceApp(object):
    def __init__(self, addon=None):
        self.addon = addon or ADDON
        self.config = load_config(self.addon)
        self._stop = threading.Event()
        self._pause = threading.Event()
        self._fade = threading.Event()
        self._thread = None
        self._streaming = False
        self._is_video = False
        self._logged = set()
        self._wled = None
        self._sender = None
        self._lock = threading.Lock()
        self._drop_backlog = False

    @property
    def streaming(self):
        thread = self._thread
        return thread is not None and thread.is_alive()

    def _log_once(self, key, msg, level=None):
        if key in self._logged:
            return
        self._logged.add(key)
        if level is None:
            level = xbmc.LOGWARNING
        _log(msg, level)

    def reload(self):
        playing = self._is_video
        alive = self.streaming
        self.config = load_config(self.addon)
        if alive:
            self.stop_stream()
        if calibration_active():
            return
        self._maybe_start(playing)

    def _maybe_start(self, is_video):
        cfg = self.config
        if cfg.fake_cycle:
            if cfg.video_only and not is_video:
                return
            self.start_stream(is_video)
            return
        if not cfg.enabled:
            _log("idle until setup is enabled")
            return
        if cfg.video_only and not is_video:
            return
        self.start_stream(is_video)

    def start_stream(self, is_video):
        with self._lock:
            self._is_video = bool(is_video)
            if self.streaming:
                return
            cfg = self.config
            if not cfg.fake_cycle and not cfg.enabled:
                return
            if cfg.video_only and not is_video and not cfg.fake_cycle:
                return
            if cfg.video_only and not is_video and cfg.fake_cycle:
                return
            if calibration_active():
                return
            self._stop.clear()
            self._pause.clear()
            self._fade.clear()
            self._streaming = True
            self._thread = threading.Thread(target=self._run, name="AmbientWLED", daemon=True)
            self._thread.start()

    def pause(self):
        if not self.streaming:
            return
        if self.config.pause_mode == "fade" and not self.config.fake_cycle:
            self._fade.set()
        else:
            self._pause.set()

    def resume(self):
        self._drop_backlog = True
        self._pause.clear()
        self._fade.clear()
        if not self.streaming and (self.config.enabled or self.config.fake_cycle):
            self.start_stream(self._is_video)

    def stop_stream(self):
        """Stop workers, clear smoothing, release WLED live override."""
        self._stop.set()
        self._pause.clear()
        thread = self._thread
        self._thread = None
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=3.0)
        self._streaming = False
        self._release()

    def shutdown(self):
        self.stop_stream()

    def _release(self):
        wled = self._wled
        self._wled = None
        sender = self._sender
        self._sender = None
        if wled is not None:
            try:
                wled.set_live(False)
            except Exception as exc:
                _log("release live failed: %s" % exc, xbmc.LOGWARNING)
        if sender is not None:
            try:
                sender.close()
            except Exception:
                pass

    def _run(self):
        try:
            cfg = self.config
            if cfg.fake_cycle:
                _log("debug fake cycle (%s)" % cfg.fake_cycle_mode)
                self._run_fake(cfg)
            else:
                self._run_capture(cfg)
        except Exception as exc:
            _log("worker error: %s" % exc, xbmc.LOGERROR)
        finally:
            # Pause on the debug cycle ends the thread but must keep WLED live
            # so the last frame stays. Stop and screensaver clear that flag.
            paused = self._pause.is_set() and not self._stop.is_set()
            self._streaming = False
            if not paused:
                self._release()

    def _run_fake(self, cfg):
        self._wled = WledClient(cfg.wled_host, port=cfg.wled_port, timeout=2.0)
        try:
            info = self._wled.test_connection()
            self._wled.set_live(True)
            _log("fake cycle on %s leds=%s" % (info.get("name"), cfg.output_count()))
        except WledError as exc:
            self._log_once("wled", "WLED unreachable at %s: %s" % (cfg.wled_host, exc))
            return
        self._sender = DdpSender(cfg.wled_host, port=cfg.ddp_port, rgbw=cfg.rgbw)
        run_cycle(
            self._sender,
            cfg.output_count(),
            mode=cfg.fake_cycle_mode,
            fps=20.0,
            brightness=cfg.brightness / 255.0,
            should_stop=lambda: self._stop.is_set() or self._pause.is_set(),
        )

    def _run_capture(self, cfg):
        self._wled = WledClient(cfg.wled_host, port=cfg.wled_port, timeout=2.0)
        self._sender = DdpSender(cfg.wled_host, port=cfg.ddp_port, rgbw=cfg.rgbw)
        try:
            self._wled.set_live(True)
        except WledError as exc:
            self._log_once(
                "wled",
                "WLED HTTP unreachable at %s: %s — still sending DDP" % (cfg.wled_host, exc),
            )
        grabber = self._open_source(cfg)
        if grabber is None:
            self._fail_soft(cfg)
            return
        pipeline = ColorPipeline(
            black_threshold=cfg.black_threshold,
            white_suppression=cfg.white_suppression,
            saturation=cfg.saturation,
            contrast=cfg.contrast,
            gamma=cfg.gamma,
            brightness=cfg.brightness,
            smoothing=cfg.smoothing,
            rgbw=cfg.rgbw,
            white_extract=cfg.white_extract,
        )
        delay = SyncDelay()
        slot = LatestSlot()
        fps_box = [cfg.capture_fps]
        cap_stop = threading.Event()

        def capture_loop():
            while not self._stop.is_set() and not cap_stop.is_set():
                if self._pause.is_set() and not self._fade.is_set():
                    if self._stop.wait(0.1):
                        break
                    continue
                started = time.monotonic()
                try:
                    frame = grabber.read()
                except Exception as exc:
                    self._log_once("grab", "capture read failed: %s" % exc)
                    frame = None
                if frame is not None:
                    slot.put((frame, started))
                period = 1.0 / max(1, int(fps_box[0]))
                remaining = period - (time.monotonic() - started)
                if remaining > 0 and self._stop.wait(remaining):
                    break

        cap_thread = threading.Thread(target=capture_loop, name="AmbientWLED-capture", daemon=True)
        cap_thread.start()
        last = None
        proc_avg = 0.0
        try:
            while not self._stop.is_set():
                if self._drop_backlog:
                    delay.clear()
                    self._drop_backlog = False
                if self._fade.is_set():
                    self._do_fade(last)
                    self._fade.clear()
                    self._pause.set()
                if self._pause.is_set():
                    if self._stop.wait(0.1):
                        break
                    continue
                item = slot.get(0.1)
                now = time.monotonic()
                if item is not None:
                    (bgra, width, height), captured_at = item
                    t0 = time.perf_counter()
                    colours = map_frame(
                        bgra,
                        width,
                        height,
                        leds_left=cfg.leds_left,
                        leds_top=cfg.leds_top,
                        leds_right=cfg.leds_right,
                        leds_bottom=cfg.leds_bottom,
                        start_corner=cfg.start_corner,
                        direction=cfg.direction,
                        edge_depth_pct=cfg.edge_depth_pct,
                        black_threshold=cfg.black_threshold,
                    )
                    out = pipeline.process(colours)
                    elapsed_ms = (time.perf_counter() - t0) * 1000.0
                    proc_avg = elapsed_ms if proc_avg == 0.0 else (proc_avg * 0.8 + elapsed_ms * 0.2)
                    new_fps = recommend_fps(proc_avg, fps_box[0])
                    if new_fps != fps_box[0]:
                        fps_box[0] = new_fps
                        self._log_once(
                            "fps",
                            "colour pipe %.1f ms average, dropping capture to %s fps" % (proc_avg, new_fps),
                        )
                    delay.push(out, captured_at, cfg.sync_delay_ms / 1000.0)
                    last = out
                ready = delay.pop_ready(now)
                if ready is not None and not self._pause.is_set() and self._sender is not None:
                    self._sender.send(ready)
                    last = ready
        finally:
            cap_stop.set()
            slot.close()
            cap_thread.join(timeout=1.5)
            try:
                grabber.close()
            except Exception:
                pass
            pipeline.reset()
            delay.clear()

    def _open_source(self, cfg):
        mode = cfg.capture_mode
        if mode in ("auto", "native"):
            grab, det = self._probe_native(cfg)
            if self._stop.is_set():
                if grab is not None:
                    grab.close()
                return None
            if grab is not None and not det.failed():
                _log(
                    "capture native %sx%s meanY=%.1f empty=%s/%s"
                    % (grab.width, grab.height, det.mean_y, det.empty_count, det.count)
                )
                return grab
            if grab is not None:
                grab.close()
            self._log_once(
                "native-fail",
                "RenderCapture near-black (%s/%s empty, meanY %.1f)"
                % (det.empty_count, det.count, det.mean_y),
            )
            if mode == "native":
                return None
        if mode in ("auto", "hyperion"):
            source = self._open_hyperion(cfg)
            if source is not None:
                _log("capture hyperion %s:%s" % (cfg.hyperion_host, cfg.hyperion_port))
                return source
            self._log_once("hyperion-fail", "Hyperion capture unavailable")
        return None

    def _probe_native(self, cfg):
        try:
            rc = xbmc.RenderCapture()
        except Exception as exc:
            self._log_once("native-fail", "RenderCapture missing: %s" % exc)
            return None, BlackDetector()
        aspect = 16.0 / 9.0
        try:
            reported = float(rc.getAspectRatio() or 0)
            if reported > 0.05:
                aspect = reported
        except Exception:
            pass
        width, height = capture_size(aspect, cfg.capture_long_edge)
        if self._stop.wait(0.3):
            return None, BlackDetector()
        grab = NativeGrabber(rc, width, height, wait_ms=40)
        det = BlackDetector(frames=12, fail_ratio=0.75)
        for _ in range(12):
            if self._stop.is_set():
                break
            frame = grab.read()
            if frame is None:
                det.add(None, width, height)
            else:
                det.add(frame[0], frame[1], frame[2])
        return grab, det

    def _open_hyperion(self, cfg):
        client = HyperionClient(cfg.hyperion_host, cfg.hyperion_port, timeout=1.5)
        try:
            client.server_info()
        except HyperionError as exc:
            self._log_once("hyperion", "Hyperion not reachable: %s" % exc)
            return None
        if not client.ensure_bridge_mode():
            self._log_once("hyperion", "could not set Hyperion grabber mode (%s)" % client.last_error)
            return None
        source = HyperionSource(client, prefer_ws=True)
        frame = None
        for _ in range(10):
            if self._stop.is_set():
                source.close()
                return None
            try:
                frame = source.read(0.25)
            except Exception as exc:
                self._log_once("hyperion", "Hyperion read failed: %s" % exc)
                frame = None
            if frame:
                break
        if not frame:
            source.close()
            return None
        return source

    def _fail_soft(self, cfg):
        self._log_once("failsoft", "both captures failed; fail-soft=%s" % cfg.fail_soft)
        if cfg.fail_soft == "dim" and self._sender is not None:
            level = max(1, int(cfg.brightness * 0.12))
            colour = (level, int(level * 0.82), int(level * 0.55))
            count = cfg.output_count()
            pixels = [colour] * count
            if cfg.rgbw:
                pixels = [(c[0], c[1], c[2], min(c)) for c in pixels]
            try:
                self._sender.send(pixels)
            except Exception:
                pass
        elif cfg.fail_soft == "off":
            wled = self._wled
            if wled is not None:
                try:
                    wled.set_live(False)
                except Exception:
                    pass
        while not self._stop.is_set():
            if self._stop.wait(1.0):
                break

    def _do_fade(self, last):
        if not last or self._sender is None:
            return
        steps = 8
        for index in range(steps):
            if self._stop.is_set():
                return
            scale = 1.0 - (index + 1) / float(steps)
            faded = [tuple(int(channel * scale) for channel in pixel) for pixel in last]
            self._sender.send(faded)
            if self._stop.wait(0.08):
                return


class PlayerHooks(xbmc.Player):
    def __init__(self, app):
        xbmc.Player.__init__(self)
        self.app = app

    def _video(self):
        try:
            return bool(self.isPlayingVideo())
        except Exception:
            return False

    def onAVStarted(self):
        self.app.start_stream(self._video())

    def onPlayBackStarted(self):
        return None

    def onPlayBackPaused(self):
        self.app.pause()

    def onPlayBackResumed(self):
        self.app.resume()

    def onPlayBackStopped(self):
        self.app._is_video = False
        self.app.stop_stream()

    def onPlayBackEnded(self):
        self.onPlayBackStopped()

    def onPlayBackError(self):
        self.onPlayBackStopped()


class AmbientMonitor(xbmc.Monitor):
    def __init__(self, app):
        xbmc.Monitor.__init__(self)
        self.app = app

    def onScreensaverActivated(self):
        self.app.stop_stream()

    def onSettingsChanged(self):
        self.app.reload()


def run_service():
    _log("service starting")
    app = ServiceApp()
    player = PlayerHooks(app)
    monitor = AmbientMonitor(app)
    try:
        playing = bool(player.isPlayingVideo())
    except Exception:
        playing = False
    app._is_video = playing
    app._maybe_start(playing)
    was_calibrating = False
    while not monitor.abortRequested():
        active = calibration_active()
        if active:
            was_calibrating = True
            if app.streaming:
                app.stop_stream()
        elif was_calibrating:
            was_calibrating = False
            app.config = load_config(app.addon)
            app._maybe_start(app._is_video)
        if monitor.waitForAbort(0.2):
            break
    app.shutdown()
    _log("service stopped")
    del player


def test_connection():
    cfg = load_config()
    title = "AmbientWLED"
    try:
        summary = WledClient(cfg.wled_host, port=cfg.wled_port, timeout=2.0).test_connection()
    except WledError:
        xbmcgui.Dialog().ok(title, "Cannot reach WLED at %s" % cfg.wled_host)
        return
    name = summary.get("name") or cfg.wled_host
    count = summary.get("led_count")
    count_s = "?" if count is None else str(count)
    bri = summary.get("bri")
    bri_s = "?" if bri is None else str(bri)
    xbmcgui.Dialog().ok(
        title,
        "Connected to %s (%s LEDs).\nBrightness %s.\n\nA short edge chase follows."
        % (name, count_s, bri_s),
    )
    frames = chase_frames(
        {
            "leds_left": cfg.leds_left,
            "leds_top": cfg.leds_top,
            "leds_right": cfg.leds_right,
            "leds_bottom": cfg.leds_bottom,
            "start_corner": cfg.start_corner,
            "direction": cfg.direction,
        },
        seconds=2.0,
        fps=20.0,
    )
    error = run_frames(
        cfg.wled_host,
        frames,
        port=cfg.wled_port,
        ddp_port=cfg.ddp_port,
        rgbw=cfg.rgbw,
    )
    note = "Edge chase finished"
    if error:
        note = "Chase sent (WLED HTTP: %s)" % error
    try:
        xbmcgui.Dialog().notification(title, note, xbmcgui.NOTIFICATION_INFO, 4000)
    except Exception:
        _log(note)


def _write_delay(addon, delay_ms):
    delay_ms = int(delay_ms)
    try:
        addon.setSettingInt("sync_delay_ms", delay_ms)
    except Exception:
        addon.setSetting("sync_delay_ms", str(delay_ms))


def calibrate_sync():
    """Settings action: white perimeter bar + delayed LED hotspot."""
    import os
    import sys

    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    import calibrate_ui

    cfg = load_config()

    def on_delay(delay_ms):
        _write_delay(ADDON, delay_ms)

    calibrate_ui.run_calibration(cfg, on_delay=on_delay)


if __name__ == "__main__":
    run_service()
