# AmbientWLED — Capture Strategy (AM9 Pro / CE 22 Amlogic-NO)

**Target:** Ugoos AM9 Pro (S905X5-J) · CoreELEC 22 Amlogic-NO · Kodi 21/22  
**Decision date:** 2026-09-21 (CEST)  
**Owner:** Cap (Week-2)

## 1. Decision (one paragraph)

**Default path A:** try `xbmc.RenderCapture` at 20–30 fps, long edge 64–128 px.  
**If black/empty during HW video decode → path B:** do **not** invent a second Amlogic grabber. Install CoreELEC `service.hyperion.ng`, let Hyperion’s Amlogic grabber (`/dev/amvideocap0`) own frame capture, and Cap talks to Hyperion over JSON-RPC (thin client). Cap still owns the color pipeline → WLED DDP.  
**Honest prior:** RenderCapture has been broken/unreliable for fullscreen HW decode on CoreELEC Amlogic since CE20; treat A as a probe, expect B on AM9.

## 2. Decision tree

```
OnPlay(video):
  if capture_mode == auto:
      probe RenderCapture for N frames while video is HW-decoded
      if black_empty_detector(pass):
          mode = native_rc        # path A
      else:
          log once: "RenderCapture empty on HW decode → Hyperion bridge"
          mode = hyperion_bridge  # path B
  elif capture_mode == native:
      mode = native_rc
  elif capture_mode == hyperion:
      mode = hyperion_bridge

native_rc:
  Kodi: RenderCapture @ target fps → worker queue(depth=1)
  Cap: 4-edge + blackbar + gamma 2.2 + sat + EMA/flicker → WLED DDP

hyperion_bridge:
  Hyperion: Amlogic GRABBER on; LEDDEVICE off (Cap owns WLED)
  Cap: JSON/WS client → image or LED colors → Cap pipeline → WLED DDP
  Cap: playback hooks still Kodi-side (OnPlay/OnStop/Pause)
```

Manual override in settings: `auto` | `native` | `hyperion`. Persist last working mode.

## 3. Path A — `xbmc.RenderCapture`

### API (Kodi Python)

- `rc = xbmc.RenderCapture()`
- `rc.capture(w, h)` then `img = rc.getImage(msecs)` → BGRA, size `w*h*4`
- Docs: https://xbmc.github.io/docs.kodi.tv/master/kodi-base/dc/d6e/group__python__xbmc___render_capture.html

### Recommended sizes / fps

| Content            | Capture (long edge) | FPS | Notes |
|--------------------|---------------------|-----|-------|
| Default            | 96 px               | 25  | Aim capture+process &lt; 8 ms |
| Light / GUI bias   | 64 px               | 20  | |
| Heavy 4K remux CPU | 128 px              | 15  | If worker CPU &gt; ~15% |

Keep aspect from video (`getAspectRatio()`); never upscale beyond display. Prefer ~32 KB+ buffer history on CE (too-tiny captures sometimes never update — forum note for BlackBarsNever).

### Worker design (mandatory)

- Capture call may be issued from service timer; **never** process on Kodi render thread.
- Worker: single thread, **queue depth 1** (replace pending; drop old).
- Budget: capture + Cap pipeline **&lt; 8 ms avg**.
- OnStop / screensaver: stop timer, drain queue, release WLED live.

### Why A often fails on Amlogic

HW decode paints a **video plane** (zero-copy / DRM) that Kodi’s RenderCapture path does not composite into the captured buffer. GUI can look fine; fullscreen video returns black/empty. Reported CE19→CE20 regression with double-write still enabled (MoojMidge). Same class of problem as DRMPRIME/GBM “no fb for video” elsewhere (RPi5 feature request). Older Amlogic ambilight work used kernel `/dev/amvideocap*` / boblight-aml — not Python RenderCapture.

**S905X5-J flag:** No public evidence RenderCapture works for HW decode on AM9 Pro + CE 22 NO. Assume fail until probe proves otherwise.

## 4. Black/empty detector (reliable)

Run **only during OnPlay video** (not GUI-only), after ≥300 ms into playback (skip first frames / mode switch).

```
For each of N=12 consecutive captured frames (or ~500 ms @ 25 fps):
  Convert BGRA → luminance Y = 0.2126*R + 0.7152*G + 0.0722*B  (use B,G,R order)
  mean_Y = average over all pixels
  max_Y  = max over pixels (or p99)

Frame is EMPTY if:
  mean_Y < 4.0   AND  max_Y < 12.0     # near-black
  OR len(img) == 0 / getImage timeout / all zeros

Probe FAILS (→ Hyperion) if EMPTY_count / N >= 0.75
Probe PASSES if EMPTY_count / N <= 0.25 and mean_Y over window > 8

Re-probe once if user changes decoder / double-write / CE build.
Do not treat letterbox black bars as EMPTY: sample center 50% box only for detector
(edge blacks are fine; full-frame near-zero is the failure mode).
```

Log one line with mean_Y / max_Y / mode chosen. No toast spam.

## 5. Path B — Hyperion.ng Amlogic grabber + JSON bridge

### How the grabber works (S905X*)

Hyperion `AmlogicGrabber` (current master):

1. Opens `/dev/amvideo`, `ioctl(AMSTREAM_IOC_GET_VIDEO_DISABLE)` — skip if no video.
2. Opens `/dev/amvideocap0`, sets width/height/`CAP_FLAG_AT_END`/wait-max (~100 ms).
3. `pread` → BGR24; resamples into Hyperion image pipeline.
4. Default attempt rate ~**25 Hz**; if video FPS &gt; 30, hardware may deliver FPS/2.
5. GUI-only: falls back to framebuffer / DRM-GBM discovery path (not VPU).

Historical CoreELEC patches also exposed **ge2d** (`/dev/ge2d`, `amlogic_grabber` / `ge2d_mode`); current upstream Amlogic grabber path is **amvideocap0-centric**. Cap does **not** reopen these devices — Hyperion owns them.

Sources:  
https://github.com/hyperion-project/hyperion.ng/blob/master/libsrc/grabber/amlogic/AmlogicGrabber.cpp  
https://github.com/hyperion-project/hyperion.ng/pull/530  
https://github.com/CoreELEC/CoreELEC/commit/62346ccad544a73d61181e9a518b668983b880d2

### CoreELEC packaging

- Addon id: **`service.hyperion.ng`**
- Present on **Amlogic-no** repo for CE 22 (e.g. `addons/Amlogic-no/22.0.12/aarch64/service.hyperion.ng` on relkai.coreelec.org).
- Data: `/storage/.kodi/userdata/addon_data/service.hyperion.ng`
- **Match addon age to CE nightly** — Portisch has broken older addons against newer NO builds (e.g. post-20280816). Prefer repo addon for installed CE build, not random zip.
- Hyperion **does** run on Amlogic-NO / AM9 in the wild; AM9-specific color-channel bugs were reported and fixed in CE nightlies (forum thread Apr 2026).

### Ownership split (bridge mode)

| Piece | Owner |
|-------|--------|
| `xbmc.RenderCapture` usage | Kodi/AmbientWLED service (path A only) |
| Playback hooks OnPlay/OnStop/Pause/screensaver | Kodi/AmbientWLED service |
| Amlogic VPU frame grab (`amvideocap0`) | **Hyperion.ng** |
| Hyperion JSON/WS client, reconnect, fail-soft | **Cap** |
| 4-edge map, blackbar, gamma 2.2, sat, EMA+flicker | **Cap** |
| WLED DDP / DRGB / JSON brightness | **Cap** (Hyperion `LEDDEVICE` **off**) |
| Hyperion BLACKBORDER / SMOOTHING | Prefer **off** in bridge; Cap owns bars+EMA |

See `HYPERION_BRIDGE.md` for client surface.

### Bridge data path (preferred)

1. Cap `serverinfo` → confirm Hyperion up, GRABBER available.
2. `componentstate` LEDDEVICE=false, BLACKBORDER=false, SMOOTHING=false, GRABBER=true.
3. Consume frames via WebSocket `ledcolors` / `imagestream-start` **or** periodic `instance-data` `getImageSnapshot` (HTTP). Prefer imagestream if available; downsample already done by Hyperion (configure Hyperion capture ~80×45 or similar — Cap will edge-sample further).
4. Cap pipeline → WLED. Do **not** configure Hyperion LED layout for v1 WLED output.

Alternative (thinner, last resort): Hyperion LEDDEVICE = WLED UDP/JSON, Cap only toggles components + `adjustment` brightness. **Not preferred** — Cap loses RGBW / DDP / flicker control from PRD.

## 6. Risk flags (S905X5-J / AM9 Pro)

| # | Risk | Severity | Mitigation |
|---|------|----------|------------|
| 1 | RenderCapture black on HW decode (expected) | High for path A | Auto-fallback to Hyperion; keep A as probe only |
| 2 | `/dev/amvideocap0` missing or ioctl mismatch on young NO/S905X5 kernel | High for path B | Week-2: `ls -l /dev/amvideo /dev/amvideocap0` under play; if absent, Hyperion screen grab falls to FB (GUI only) — document failure, do not ship custom ioctl grabber |
| 3 | CE NO nightly ↔ `service.hyperion.ng` version skew (service won’t start / blank capture) | Medium | Install matching repo addon; pin after soak; retest after CE update |
| 4 | AM9 grabber color channel / green-cast regressions (seen Apr 2026, fixed) | Medium | Soak HEVC/HDR/IPTV; Cap gamma/sat can mask mild casts but not R↔B swaps |
| 5 | Capture CPU vs 4K HEVC / DV FEL | Medium | Cap budget 8 ms; drop to 15 fps; Hyperion at ≤25 Hz; never block render thread |
| 6 | Double Hyperion+Cap both writing WLED | Low | Explicit LEDDEVICE=off in bridge; single DDP owner |

**Tone:** Prefer Hyperion bridge over reinventing amvideocap on this SoC. If both A and B fail, fail-soft (static bias / off) — no HDMI splitter in v1.

## 7. Week-2 checklist (Cap drives)

- [ ] Implement RenderCapture worker: 96 px long edge @ 25 fps, queue depth 1, timing log (p50/p95 ms).
- [ ] Implement black/empty detector (center-box mean/max Y, N=12); unit-test with black + real fixture frames.
- [ ] OnPlay probe → set `capture_mode` auto result; settings override.
- [ ] SSH soak on AM9: during 4K HEVC play, confirm `/dev/amvideocap0` exists; install `service.hyperion.ng` from Amlogic-no repo matching CE build.
- [ ] Hyperion WebUI: enable Amlogic screen capture ~25 Hz; verify live preview during remux (not only GUI).
- [ ] Cap Hyperion client: `serverinfo`, `componentstate`, imagestream/snapshot; LEDDEVICE off; reconnect + fail-soft (see HYPERION_BRIDGE.md).
- [ ] Cap pipeline on both sources: 4-edge mean/p75, blackbar, gamma 2.2, sat, EMA+flicker → DDP.
- [ ] Acceptance: SDR 1080p ≤~80 ms perceived lag; 4K remux + TrueHD/DV path untouched; pause/stop release live.
- [ ] If A always fails on AM9: default settings to `hyperion`, keep A behind “experimental”.
- [ ] Doc in README: Hyperion required for AM9 until/unless RenderCapture probe passes.

## 8. Sources

1. Kodi RenderCapture Python API — https://xbmc.github.io/docs.kodi.tv/master/kodi-base/dc/d6e/group__python__xbmc___render_capture.html  
2. CE20 RenderCapture broken (MoojMidge) — https://discourse.coreelec.org/t/coreelec-20-0-nexus-rc2-discussion/19879/53  
3. BlackBarsNever / CE capture tips (resolution, wait, double-write) — https://discourse.coreelec.org/t/blackbarsnever-add-on/19369  
4. Historic Amlogic HW decode vs RenderCapture / amvideocap — https://forum.kodi.tv/showthread.php?tid=219563  
5. DRMPRIME/GBM video not in FB (class of problem) — https://github.com/xbmc/xbmc/issues/26790  
6. Hyperion AmlogicGrabber.cpp — https://github.com/hyperion-project/hyperion.ng/blob/master/libsrc/grabber/amlogic/AmlogicGrabber.cpp  
7. Hyperion ge2d / amvideocap PR — https://github.com/hyperion-project/hyperion.ng/pull/530  
8. CoreELEC ge2d/amvideocap kernel patch — https://github.com/CoreELEC/CoreELEC/commit/62346ccad544a73d61181e9a518b668983b880d2  
9. Hyperion.NG Amlogic improvements (incl. AM9 / NO notes) — https://discourse.coreelec.org/t/hyperion-ng-amlogic-improvements/5476  
10. CoreELEC Amlogic-no addons (`service.hyperion.ng`) — https://relkai.coreelec.org/?dir=addons/Amlogic-no/22.0.12/aarch64  
11. Hyperion JSON-API commands overview — https://api.hyperion-project.org/json-api-commands-overview-1023995m0.md  
12. Hyperion `color` command — https://api.hyperion-project.org/setcolor-17009776e0  
13. AmbientWLED PRD — `/workspace/ambientwled/PRD.md`
