# AmbientWLED

Bias lighting for **Kodi on CoreELEC** → **WLED** on the LAN.

A couch setup: install the repo, run the wizard with the remote, and the strip follows the picture while video plays. Original code. It does not touch HDMI, Dolby Vision, or audio.

## Hardware

| Role | Part |
|------|------|
| Box | **Ugoos AM9 Pro** — Amlogic S905X5-J · **CoreELEC 22 Amlogic-NO** · Kodi 21/22 |
| TV | **LG C2** |
| Audio | **Sonos Arc Ultra** on the TV **eARC** port |
| Controller | **GLEDOPTO GL-C-017WL-D** (WLED, Ethernet or Wi-Fi) |
| Strip | **SK6812 RGBW**, 264 LEDs. WS2812B RGB is a setting |

Leave the Arc Ultra on the TV eARC port. Do not change HDMI, audio passthrough, or Dolby Vision to make the lights work. AmbientWLED only reads a small picture and sends LAN packets.

## Install on the AM9 (do this first)

Install the **repository zip** before the service zip. Kodi then pulls the library, the service, and the wizard from that repo, and the zip URL stays valid when versions move.

1. Settings → System → Add-ons → Unknown sources: **On**
2. Download [repository.ambientwled-1.0.0.zip](https://raw.githubusercontent.com/TheGildedGoo/AmbientWLED/main/repo/zips/repository.ambientwled/repository.ambientwled-1.0.0.zip)
3. Add-ons → **Install from zip file** → that zip
4. Add-ons → **Install from repository** → **AmbientWLED Repo** → **Program add-ons** → **AmbientWLED Settings**

That program addon depends on the service, and the service depends on the library, so one install brings up all three. Open **AmbientWLED Settings**. The first time, the setup wizard runs.

The service starts with Kodi and stays idle until the wizard (or the Enable setting) turns it on.

### If you are copying zips by hand

Install in this order, or Kodi will refuse a dependency:

1. `script.module.ambientwled`
2. `script.service.ambientwled`
3. `plugin.program.ambientwled`

## Wizard

Seven steps, remote only:

1. Welcome
2. WLED IP, HTTP port, DDP port, **Test connection** (info dialog, then a short edge chase)
3. RGBW or RGB, LED count (264)
4. Left / top / right / bottom, with the live sum, start corner, direction, edge depth, and an edge chase
5. Picture sliders, **Calibrate sync**, plus a solid and a rainbow preview
6. Video only, capture mode, pause, and what to do if capture fails
7. Enable the service

You can run the chase in the wizard before capture has ever worked.

## Wizard defaults (this 264 SK6812 layout)

| Setting | Default |
|---------|---------|
| Strip | RGBW (SK6812). White extract **off** (W = min(R, G, B), RGB kept) |
| LEDs | 264 total · left **47** · top **85** · right **47** · bottom **85** |
| Order | Start **bottom left**, **clockwise** |
| Edge depth | 10% |
| Gamma | 2.2 (setting `22`) |
| Brightness cap | 180 (second cap; see WLED limiter below) |
| Sync delay | **40 ms** (0–200, step 10). Delays the DDP send, not capture. **Calibrate sync** matches it to the picture |
| Capture | **auto**, 25 fps, long edge 96 |
| Pause | freeze |
| Video only | on |
| If capture fails | off (release the strip, log once) |
| Fake colour cycle | **off** (debug only) |

Colour order **GRB** is a reminder for the WLED controller. DDP itself is sent as RGB / RGBW.

## WLED on the GL-C-017WL-D

In LED Preferences:

- **LED type:** SK6812 RGBW (or WS2812 if you turned RGBW off here)
- **Colour order:** GRB for a typical SK6812 — match the strip, not this addon
- **Length:** 264 on one output, or outputs that add up to 264. AmbientWLED sends one DDP stream in the wizard order
- **DDP:** on, UDP **4048**
- **Brightness limiter:** about **2900 mA**. That limiter is the current limit. The addon brightness slider is only a second cap and does not replace it
- 2.4 GHz Wi-Fi is enough for the controller. Ethernet on the AM9 is the better side of the link

Test connection reads `/json/info` and `/json/state`, shows a dialog, then runs a two-second edge chase. Stop, Home, and the screensaver POST `{"live": false}` so WLED can take the strip back.

## Sync calibration

Use this when the strip leads or lags the picture.

1. Open **AmbientWLED Settings** → **Picture** → **Calibrate sync**. The setup wizard's Picture step has the same item.
2. A white bar walks the edge of the screen, one lap about every 2.5 seconds, in the strip direction (clockwise by default). The same spot is sent to WLED through the sync-delay queue, on the DDP worker.
3. Press **Left** or **Right** until the white LED moves with the bar. Each click is 10 ms, from 0 to 200, and it is saved immediately. The number on screen is the current delay. A gauge under it shows the same value.
4. Press **OK** or **Back** when they match. The bar stops, the chase stops, and WLED live override is released.

If the controller does not answer, the bar and the delay control still run, and one notice says the LEDs are not connected. The fake colour cycle under Debug is a separate toggle and stays off.

## Capture

**Auto** (the default):

1. Kodi `RenderCapture`, about 96 px on the long edge, 20–25 fps, BGRA, on a worker (queue depth 1). If the colour pipe averages over 8 ms it drops to 15 fps.
2. After playback has been going ~300 ms, 12 frames are checked. If at least three quarters are near-black, native capture is treated as failed. That is the usual result for hardware-decoded video on this box.
3. **Hyperion.** Install CoreELEC **`service.hyperion.ng`** from the Amlogic-no repo that matches your nightly. AmbientWLED talks to `127.0.0.1:8090` (JSON, WebSocket if it answers). It turns the Hyperion **LED device off** and the **grabber on**, then maps those frames itself and sends DDP. It does not open the Amlogic grabber device.
4. If both fail, it logs once and stops. It does not spin or take Kodi down. Dim and Hold are optional in settings.

Do not also point Hyperion’s LED device at the same WLED. One sender.

The fake colour cycle is under Debug and stays off. It is not the live path.

## What it will not do

- No HDMI splitter, no capture card, no grabber of its own
- No change to eARC, TrueHD, Atmos, or Dolby Vision
- No phone-home. Traffic is the WLED on your LAN and, only if you use that path, Hyperion on localhost

## Develop

```bash
python3 -m pip install -r requirements-dev.txt
python3 -m pytest
python3 tools/build_repo.py
```

The library in `script.module.ambientwled/lib` does not import `xbmc`.

## Layout

- `script.module.ambientwled/` shared library (DDP, JSON, mapper, colour pipe, Hyperion client)
- `script.service.ambientwled/` background service
- `plugin.program.ambientwled/` wizard
- `repository.ambientwled/` the Kodi repository addon
- `repo/` index and zips from `tools/build_repo.py`
- `.github/workflows/kodi-repo.yml` rebuilds `repo/` on main

## License

MIT. See [LICENSE](LICENSE).

https://github.com/TheGildedGoo/AmbientWLED
