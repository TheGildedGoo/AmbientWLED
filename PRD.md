# AmbientWLED — Product Brief (v1)

**Owner:** Dylan King (Kaiserslautern) · **PM:** Proxima  
**Working title:** AmbientWLED · **Platform:** Kodi addon on CoreELEC 22 Amlogic-NO  
**Hardware:** Ugoos AM9 Pro (S905X5-J) → LG C2 · WLED GLEDOPTO GL-C-017WL-D · SK6812 RGBW (WS2812B fallback)

## Vision
Recreate the ScreenGlow / SceneGlow *workflow* as a first-party Kodi addon. Original implementation — no ScreenGlow UI, assets, package name, or code. Couch remote, one settings page.

## Why not Android ScreenGlow
ScreenGlow uses MediaProjection. CoreELEC is Linux + Kodi. Capture via `xbmc.RenderCapture` and/or Hyperion.ng Amlogic grabber.

## Hard constraints
- LAN only (prefer AM9 Ethernet; WLED Wi‑Fi OK). No cloud, accounts, phone-home.
- Do **not** touch HDMI / eARC / TrueHD / Dolby Vision / Sonos path. No splitter, no capture card in v1.
- No root beyond normal CoreELEC addon privileges.
- Do not ship copyrighted ScreenGlow/SceneGlow resources.
- GPL-2.0-or-later or MIT.

## Architecture (v1)
1. `script.service.ambientwled` (background) + `plugin.program.ambientwled` (settings UI).
2. **Capture preference:**  
   A. `xbmc.RenderCapture` @ 20–30 fps, downsample ~64–128 px long edge.  
   B. If black/empty on AM9 HW decode → Hyperion.ng Amlogic grabber + Hyperion JSON API (thin wrapper), not a second grabber.
3. **Color pipeline:** 4 edges (+ optional corner weights); mean or p75; blackbar detect; gamma 2.2; sat boost; brightness cap; EMA + flicker clamp; RGBW: W = min(R,G,B), send RGBW over DDP (no WLED auto-white double-compute).
4. **Output:** Primary WLED DDP UDP 4048; fallback DRGB/DRGBW UDP 21324; JSON HTTP for discover / brightness / on-off / live override.
5. **Playback hooks:** OnPlay video → stream; OnStop/screensaver → dim/stop + release live; Pause → freeze or fade (setting); GUI-only → optional 6500K @ 10% or off.

## Hardware mapping
- GL-C-017WL-D 4 data channels (GPIOs typically 16 / 4 / 2 / 1).
- Layout wizard: TV size preset, clockwise start corner, corner gap LEDs, 1-loop vs 4-channel.
- Current: do not exceed controller 15A; default brightness limiter note ~2.9A (YouTube setup).

## Performance (AM9 Pro)
- Capture + process < 8 ms avg. Do not steal GPU from 4K HEVC / DV FEL.
- If CPU > 15% during remux → 15 fps + larger downsample.
- Never block render thread: worker + queue depth 1 (drop old).

## Non-goals
HDMI intercept, eARC, DV metadata, paid cloud, cloning ScreenGlow.

## Implementation order
- **Week 1:** WLED JSON discover + DDP sender + fake color cycle.
- **Week 2:** RenderCapture + 4-edge mapper + playback service.
- **Week 3:** blackbars, RGBW, 4-channel layout, settings, AM9 soak.
- **Week 4:** fail-soft + docs.

## Acceptance (AM9 + CE 22 NO + LG C2)
1. SDR 1080p: LEDs track L/R dominant colors ≤ ~80 ms perceived lag.
2. 4K HEVC remux + TrueHD: Sonos still TrueHD/Atmos; C2 still DV if title is DV; lights update.
3. Pause/stop: freeze or fade; WLED live override released on stop.
4. Letterbox 2.39: blackbar detector samples picture box, not whole bottom strip black.
5. WLED unreachable: log once, disable send, no Kodi spin.
6. Settings survive CE nightly update.

## Deliverables
- addon.xml (Kodi 21/22), license, README (wire GL-C-017WL-D, LED prefs, current limit, network).
- settings.xml + strings.po.
- Unit-testable pure-Python color mapper + fixture frames.
- Optional Hyperion-bridge mode.

## Tone
Couch remote, not lab UI. If Hyperion already solves ~90%, thin wrapper first.

## Credit discipline
One solid vertical slice per week. Prefer Hyperion bridge over reinventing grabber on this SoC.
