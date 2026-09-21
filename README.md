# AmbientWLED

Bias lighting for **Kodi on CoreELEC** → **WLED** on the LAN.  
Working title: **AmbientWLED**. Original code — not a ScreenGlow/SceneGlow clone.

**Week 1:** WLED JSON discover + DDP sender + fake colour cycle (no screen capture yet).

Kodi / CoreELEC addon that will sample video edges (later weeks) and drive a WLED controller (GLEDOPTO GL-C-017WL-D and similar) over DDP.

## Hardware (Dylan’s rig)

| Role | Part |
|------|------|
| Box | **Ugoos AM9 Pro** — Amlogic S905X5-J · **CoreELEC 22 Amlogic-NO** |
| TV | **LG C2** — do **not** touch eARC / TrueHD / Sonos path |
| Controller | **GLEDOPTO GL-C-017WL-D** (ESP32, 4 data outs, WLED firmware) |
| Strip | **SK6812 RGBW** (fallback: WS2812B RGB) |

No HDMI splitter, no capture card, no phone-home. Ethernet on the AM9 preferred; WLED may use Wi‑Fi.

## Wiring the GL-C-017WL-D

1. Power the controller from a suitable 5 V supply. The board is rated around **15 A** total — size the PSU for your LED count and brightness.
2. Data outs are typically GPIOs **16 / 4 / 2 / 1** (confirm silkscreen / WLED LED Preferences). Week 1 treats the strip as **one logical loop** over DDP; 4-channel layout wizard is later.
3. Connect SK6812 (or WS2812B) data + 5 V + GND. Common ground with the PSU.
4. For long runs, inject 5 V at the far end; keep voltage drop in mind.

### WLED LED Preferences (suggested Week 1)

- **LED type:** SK6812 RGBW (or WS2812 for RGB fallback)
- **Colour order:** usually **GRB** for SK6812 — match the addon setting
- **Length:** total LED count (same as addon “LED count”)
- **DDP:** enabled (UDP **4048**) — AmbientWLED’s primary path  
  *(DRGB/DRGBW on 21324 is stubbed for later)*
- **Current / brightness limiter:** stay well under **15 A**. Many living-room setups use a software limiter around **~2.9 A** — start conservative; the addon brightness cap defaults mid-range.

## Network

1. Put the GLEDOPTO on the same LAN as the AM9 (2.4 GHz Wi‑Fi is fine for WLED).
2. Note the controller IP (router DHCP list or WLED AP setup).
3. In AmbientWLED settings: set **WLED address**, **Test connection**, set LED count / colour order / RGBW.
4. Enable **Fake cycle (Week 1)** to verify DDP without video capture.

## Repo layout

- `script.module.ambientwled/` shared pure-Python lib (WLED JSON, DDP, fake cycle)
- `script.service.ambientwled/` background service (install this on CoreELEC)
- `plugin.program.ambientwled/` Program add-ons → opens settings
- `repository.ambientwled/` Kodi repository addon (install this zip once)
- `repo/` generated Kodi index and zips (created by `tools/build_repo.py` or the GitHub Action)
- `tools/build_repo.py` packs zips and writes `addons.xml` + `addons.xml.md5`

## Install on CoreELEC (repository zip)

1. Settings → System → Add-ons → Unknown sources: On
2. Download [repository.ambientwled-1.0.0.zip](https://raw.githubusercontent.com/TheGildedGoo/AmbientWLED/main/repo/zips/repository.ambientwled/repository.ambientwled-1.0.0.zip)
3. Add-ons → Install from zip file → that zip
4. Add-ons → Install from repository → AmbientWLED Repo → AmbientWLED

If the zip link 404s, the GitHub Action has not published `repo/` yet. Run:

```bash
python3 tools/build_repo.py
git add repo && git commit -m "Build Kodi repo" && git push
```

The repository must be **public** (or you host `repo/` on GitHub Pages) or CoreELEC cannot fetch raw GitHub URLs.

## Install from this repo (local scaffold)

Kodi 21/22 compatible addon tree:

```
script.module.ambientwled/     # shared pure-Python lib
script.service.ambientwled/    # background service
plugin.program.ambientwled/    # Program add-ons → opens settings
```

**From this repo (local scaffold):**

```bash
cd /path/to/AmbientWLED
zip -r ambientwled-week1.zip \
  script.module.ambientwled \
  script.service.ambientwled \
  plugin.program.ambientwled \
  -x '*/__pycache__/*' '*.pyc'
```

On the AM9 (CoreELEC):

1. Copy the zip to the box (SMB, USB, or `scp`).
2. Kodi → **Add-ons** → **Install from zip file** → install **module**, then **service**, then **plugin** (or one multi-addon zip if you packaged that way).
3. Enable the service if prompted. Open **Program add-ons → AmbientWLED Settings**.

Settings live on `script.service.ambientwled`. The program plugin only opens that page (couch remote).

## Configure

Add-ons → My add-ons → Services → AmbientWLED → Settings  
(or Program add-ons → AmbientWLED Settings)

- WLED IP from the WLED app
- LED count and colour order matching the controller
- Enable **Fake cycle (Week 1)** to verify DDP without video capture
- Enable only during video playback (video-only)

Keep the Sonos Arc Ultra on the TV eARC port. This addon never touches HDMI.

## Develop / test without Kodi

```bash
cd /path/to/AmbientWLED
python -m pip install pytest
python -m pytest
```

The library under `script.module.ambientwled/lib` has **no `xbmc` imports**.

## What Week 1 does / does not do

| Does | Does not |
|------|----------|
| GET `/json/info`, brightness / on / live helpers | Screen capture (`RenderCapture`) |
| DDP UDP 4048 RGB + RGBW | Hyperion bridge |
| Fake rainbow / edge chase | Blackbar detect, 4-edge mapper |
| Service + settings + playback **log stubs** | Touch HDMI / eARC / TrueHD / Sonos |

## License

MIT — see [LICENSE](LICENSE).

## Repo

https://github.com/TheGildedGoo/AmbientWLED
