# AmbientWLED — Hyperion.ng JSON bridge (Cap client sketch)

**Mode:** path B when RenderCapture is black/empty on AM9 HW decode.  
**Transport:** HTTP POST `http://127.0.0.1:8090/json-rpc` for one-shots; WebSocket `ws://127.0.0.1:8090` for streams. LAN auth may be required — store token in addon settings if Hyperion demands it.  
**API ref:** https://api.hyperion-project.org/json-api-commands-overview-1023995m0.md

## 1. What Cap implements

Thin Python client inside `script.service.ambientwled`:

- Discover / health: `serverinfo` (+ `sysinfo` optional)
- Enable Amlogic capture path: `componentstate` GRABBER=true; LEDDEVICE=false; BLACKBORDER=false; SMOOTHING=false
- Pull pixels or LED colors for Cap pipeline (preferred: imagestream / getImageSnapshot)
- Optional runtime `adjustment` (brightness only as user mirror — Cap still does gamma/sat for WLED)
- Reconnect + fail-soft (never block Kodi; never spin)

Cap does **not** open `/dev/amvideocap0`. Cap does **not** configure Hyperion LED layout for v1.

## 2. Commands Cap will use

All bodies are JSON objects; responses include `success` bool and optional `tan`.

### 2.1 Health / inventory

```json
{"command":"serverinfo","subcommand":"getInfo","tan":1}
```

Use `info.components[]` (`name`/`enabled`) to confirm GRABBER / LEDDEVICE.  
Also acceptable: `{"command":"serverinfo","tan":1}` (legacy shape).

```json
{"command":"sysinfo","tan":2}
```

Optional: Hyperion version string for soak logs.

### 2.2 Component control

```json
{"command":"componentstate","componentstate":{"component":"LEDDEVICE","state":false},"tan":10}
{"command":"componentstate","componentstate":{"component":"BLACKBORDER","state":false},"tan":11}
{"command":"componentstate","componentstate":{"component":"SMOOTHING","state":false},"tan":12}
{"command":"componentstate","componentstate":{"component":"GRABBER","state":true},"tan":13}
```

Known component names: `ALL`, `SMOOTHING`, `BLACKBORDER`, `FORWARDER`, `BOBLIGHTSERVER`, `GRABBER`, `V4L`, `AUDIO`, `LEDDEVICE`.

On AmbientWLED stop / screensaver: `GRABBER` false (or leave on idle — prefer false to save VPU).

### 2.3 Frame / LED ingest (for Cap pipeline → WLED)

**Preferred (WS):**

```json
{"command":"ledcolors","subcommand":"imagestream-start","tan":20}
```

Subscribe updates: `ledcolors-imagestream-update` (binary/base64 image — decode → Cap edges).  
Stop: `{"command":"ledcolors","subcommand":"imagestream-stop","tan":21}`

**Alt (WS LED colors only):**

```json
{"command":"ledcolors","subcommand":"ledstream-start","tan":22}
```

Updates ~every 125 ms as RGB triplets. Use only if image stream unavailable; Cap then skips 4-edge remap (Hyperion already mapped) — acceptable fallback but weaker blackbar control.

**Alt (HTTP poll):**

```json
{"command":"instance-data","subcommand":"getImageSnapshot","instance":0,"tan":23}
{"command":"instance-data","subcommand":"getLedSnapshot","instance":0,"tan":24}
```

Poll ≤15–25 Hz; drop if slower than Cap budget.

### 2.4 Optional brightness mirror

```json
{"command":"adjustment","adjustment":{"brightness":80},"tan":30}
```

Runtime only (not persisted unless admin `config`/`setconfig` — Cap should not require admin). Cap’s WLED brightness remains authoritative for DDP output.

### 2.5 Explicitly out of scope for v1 client

- `color` / `clear` / `effect` as primary LED drive (Cap → WLED DDP instead)
- Admin `config` set/save
- Creating Hyperion instances
- Forwarder / boblight

## 3. Connection / reconnect

```
host default: 127.0.0.1
port: 8090 (http/ws), 8092 if TLS used (rare on CE)
timeout: connect 1.0 s, request 1.5 s
backoff: 0.5 s → 1 → 2 → 5 → 10 s cap; jitter ±20%
on success: reset backoff; re-assert componentstate (LEDDEVICE off, GRABBER on if playing)
auth: if authorize.tokenRequired → login/requestToken once; store bearer; 401 → clear token, backoff
```

Single outstanding WS session. If WS dies mid-stream, fall back to HTTP snapshot poll for up to 30 s, then mark bridge down.

## 4. Fail-soft

| Failure | Cap behavior |
|---------|----------------|
| Hyperion not installed / connection refused | Log once; bridge unavailable; if mode=auto and RC also failed → static bias/off per settings; no Kodi spin |
| GRABBER enables but snapshots black | Log once per session; treat like RC empty; disable send after 3 s; keep probing every 30 s |
| Slow frames (&gt;8 ms Cap process or &gt;80 ms e2e) | Drop to 15 fps / skip frames (queue depth 1) |
| Hyperion LEDDEVICE somehow on + Cap DDP | On each connect force LEDDEVICE=false; warn if still enabled |
| CE update breaks addon | Log version from sysinfo; user message in settings: “Update service.hyperion.ng from CE repo” |

Never raise uncaught exceptions into Kodi event loop. Never block render thread on socket I/O — dedicated bridge thread or async with timeouts.

## 5. Playback hook interaction

Kodi service still owns hooks:

- **OnPlay video:** ensure Hyperion running (addon enabled); GRABBER on; start imagestream; Cap pipeline → WLED live
- **Pause:** freeze last colors or fade (setting); optional imagestream pause
- **OnStop / screensaver:** GRABBER off; stop stream; release WLED live; clear Cap EMA state

## 6. Minimal client surface (symbols)

```
class HyperionClient:
  connect() -> bool
  close()
  server_info() -> dict | None
  set_component(name: str, enabled: bool) -> bool
  ensure_bridge_mode() -> bool   # LEDDEVICE/BLACKBORDER/SMOOTHING off, GRABBER on
  start_image_stream(on_frame: Callable[[bytes, w, h], None]) -> bool
  stop_image_stream()
  get_image_snapshot() -> tuple[bytes, int, int] | None
  set_brightness(pct: int) -> bool   # optional adjustment
  healthy: bool
  last_error: str
```

Unit-test with recorded JSON fixtures; integration test against local Hyperion on AM9 soak.

## 7. Sources

- Commands overview: https://api.hyperion-project.org/json-api-commands-overview-1023995m0.md  
- `color`: https://api.hyperion-project.org/setcolor-17009776e0  
- `componentstate` / adjustment / serverinfo: api.hyperion-project.org (same site)  
- Amlogic grabber: https://github.com/hyperion-project/hyperion.ng/blob/master/libsrc/grabber/amlogic/AmlogicGrabber.cpp  
- CE addon: https://relkai.coreelec.org/?dir=addons/Amlogic-no/22.0.12/aarch64 (service.hyperion.ng)  
- Strategy parent: `/workspace/ambientwled/CAPTURE.md`
