# AmbientWLED — Acceptance checklist (AM9 Pro + CE 22 NO + LG C2)

Hardware under test: GLEDOPTO GL-C-017WL-D · SK6812 RGBW (or WS2812B) · LAN · Sonos Arc Ultra via eARC (must stay untouched).

- [ ] SDR 1080p: LEDs track L/R dominant colors ≤ ~80 ms perceived lag
- [ ] 4K HEVC remux + TrueHD: Sonos still TrueHD/Atmos; C2 still DV if title is DV; lights update
- [ ] Pause/stop: freeze or fade per setting; WLED live override released on stop
- [ ] Letterbox 2.39: blackbar samples picture box (bottom strip not all-black from bars)
- [ ] WLED unreachable: single log, send disabled, Kodi does not spin
- [ ] Settings persist across CE nightly update
- [ ] Capture+process < 8 ms avg; no GPU steal from 4K HEVC/DV FEL
- [ ] GUI-only mode respects static bias / off setting
