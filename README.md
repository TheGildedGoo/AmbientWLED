# AmbientWLED

Kodi / CoreELEC addon that samples video edges and drives a WLED controller (GLEDOPTO GL-C-017WL-D and similar) over DDP.

This is original software. It is not a ScreenGlow or SceneGlow clone.

## Repo layout

- `script.service.ambientwled/` addon source (install this on CoreELEC)
- `repository.ambientwled/` Kodi repository addon (install this zip once)
- `repo/` generated Kodi index and zips (created by `tools/build_repo.py` or the GitHub Action)
- `tools/build_repo.py` packs zips and writes `addons.xml` + `addons.xml.md5`

## Install on CoreELEC

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

## Configure

Add-ons → My add-ons → Services → AmbientWLED → Settings

- WLED IP from the WLED app
- LED count and color order matching the controller
- Enable only during video playback

Keep the Sonos Arc Ultra on the TV eARC port. This addon never touches HDMI.

## License

MIT
