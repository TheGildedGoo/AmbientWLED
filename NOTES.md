# AmbientWLED — Week 1 notes

**Date:** 2026-09-21 (Europe/Berlin)  
**Owner:** Dylan King · **PM:** Proxima  
**Scope:** local scaffold only under `/workspace/ambientwled`

## GitHub

`create-repo` returned **403**. Do **not** rely on GitHub API from this environment.  
When an **empty** repo exists, push locally:

```bash
cd /workspace/ambientwled
git init
git add .
git commit -m "Week 1: WLED JSON + DDP + fake cycle scaffold"
git remote add origin https://github.com/TheGildedGoo/AmbientWLED.git
git push -u origin main
```

Target: **https://github.com/TheGildedGoo/AmbientWLED**

## Hardware names (aligned with Dylan’s prompt)

- Addon: **AmbientWLED**
- Controller: **GLEDOPTO GL-C-017WL-D** (ESP32, 4 data outs, WLED)
- Strip: **SK6812 RGBW** (WS2812B RGB fallback)
- Box: **Ugoos AM9 Pro**, Amlogic **S905X5-J**, **CoreELEC 22 Amlogic-NO**
- TV: **LG C2** — never touch eARC / TrueHD / Sonos

## What works (Week 1)

- Installable addon tree for Kodi 21/22: module + service + program plugin
- Pure-Python lib: `wled_json.py`, `ddp.py`, `fake_cycle.py`, `colors/` stub
- `python -m pytest` without Kodi (ddp, wled_json, fake_cycle, colors stub)
- Service: if `xbmc` present and **Fake cycle** on → DDP rainbow/edge; playback hooks log stubs
- Settings: host, test connection, LED count, colour order, RGBW, enable on start, video-only, fake-cycle toggle
- README: wiring, WLED prefs, ~15 A / ~2.9 A limiter notes, LAN, CoreELEC zip install
- MIT license; couch-remote `en_gb` strings; no phone-home; no HDMI path

## Week 2 (next slice)

- `xbmc.RenderCapture` @ 20–30 fps, downsample ~64–128 px long edge
- Real **4-edge mapper** in `colors/` (mean/p75, gamma, sat, EMA) + fixture-frame tests
- Playback: OnPlay → stream DDP; OnStop → release live; Pause freeze/fade setting
- Wire **video-only** setting for real
- Optional: start Hyperion.ng Amlogic grabber research if RenderCapture is black on AM9 HW decode

## AM9 soak (later — Week 3/4)

- 4K HEVC remux + TrueHD: confirm Sonos Arc still TrueHD/Atmos; C2 DV untouched; lights update
- Capture+process &lt; 8 ms avg; CPU guard → drop to 15 fps
- Letterbox 2.39 blackbar detector
- 4-channel GL-C layout wizard; RGBW W=min(R,G,B) in live path
- Fail-soft when WLED unreachable; settings survive CE nightly
- Full ACCEPTANCE.md checklist on real AM9 + CE 22 NO + LG C2

## Blockers / caveats

1. **GitHub create-repo 403** — local scaffold only until empty remote exists.
2. **No hardware in CI** — pytest mocks HTTP/UDP; real DDP/JSON needs LAN + WLED.
3. **Icons** — placeholder 1×1 PNGs; replace with real art before release.
4. **Colour order** — addon setting is informational in Week 1; WLED firmware colour order must match strip. DDP payload is RGB(W) logical; WLED applies its configured order.
5. **settings.xml action** `RunScript(script.service.ambientwled,test_connection)` → `run.py` (script extension on the service addon). Confirm on CE 22.
6. **Adjacent docs** `CAPTURE.md` / `HYPERION_BRIDGE.md` are Week-2 planning (Cap); not required for Week-1 zip install.
7. **Service** hard-imports `xbmc` (normal for Kodi services). Shared lib remains pure-Python / pytest-able.
