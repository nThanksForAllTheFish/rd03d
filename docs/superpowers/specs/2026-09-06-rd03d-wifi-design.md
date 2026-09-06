# RD-03D WiFi Streaming — Design

**Date:** 2026-09-06 (revised same day: browser UI served from the XIAO replaces
the Processing network mode — user pivot after Task 2 landed)
**Target:** Seeed Studio XIAO ESP32-C6 (existing `rd03d_uart/` project)
**Framework:** ESP-IDF v5.5 (`~/esp/esp-idf-v5.5`)
**Builds on:** `2026-08-31-rd03d-uart-design.md` (UART reader, done and hardware-verified)

## Goal

Run the XIAO untethered (USB power only) at the radar's intended mounting
location and view live radar targets from any browser on the home network —
Mac or phone — at `http://rd03d.local`, with no Processing sketch and no
installed software.

## Architecture

- **WiFi:** station on the home 2.4 GHz network; credentials via menuconfig
  (`CONFIG_RD03D_WIFI_SSID`/`_PASSWORD`), stored only in the untracked
  `sdkconfig`. Auto-reconnect on drop. *(Implemented — Task 2.)*
- **Radar config:** firmware sends the multi-target command at boot and flushes
  the ACK; viewers never send radar commands. *(Implemented — Task 1.)*
- **Discovery:** mDNS hostname **`rd03d.local`**.
- **UI transport:** ESP-IDF `esp_http_server` with WebSocket support
  (`CONFIG_HTTPD_WS_SUPPORT=y`):
  - `GET /` → a single self-contained embedded HTML page (baked into the
    firmware image via CMake `EMBED_FILES`; no filesystem, no external assets).
  - `GET /ws` → WebSocket pushing one JSON text message per parsed radar frame
    (~10/s).
- **Payload (parsed JSON, not raw bytes):** the firmware reuses the tested
  `rd03d` parser and sends decoded targets:

  ```json
  {"t":[{"x":-551,"y":550,"v":0},null,null],"dropped":0,"bad":0}
  ```

  `t` always has 3 entries; absent targets are `null`. `x`/`y` in mm, `v` in
  cm/s; `dropped`/`bad` are the parser's cumulative link counters.

## Firmware Changes (`rd03d_uart/`)

- `main/wifi_link.c/.h` — as implemented, plus two hardening amendments from
  code review: WPA2 auth-mode threshold (refuse open-network SSID spoofs) and
  compile-time asserts on credential lengths. mDNS init (hostname `rd03d`)
  added here after WiFi start, via the `espressif/mdns` managed component.
- `main/web_server.c/.h` — new module:
  - `web_server_start(void)` — starts `esp_http_server`, registers `/` and
    `/ws` handlers.
  - `web_server_send_frame(const rd03d_frame_t *f, uint32_t dropped, uint32_t bad)`
    — formats the JSON message and sends it asynchronously to every connected
    WebSocket client. Bounded work: a client whose send fails or backs up is
    closed; the radar loop is never blocked. No client connected → no-op.
  - A small number of simultaneous clients supported (HTTP server default
    socket limit; at least Mac + phone together).
- `main/index.html` — the embedded page (see UI section), registered via
  `EMBED_FILES` in `main/CMakeLists.txt`.
- `main/main.c` — after each parsed frame: `print_frame` (unchanged) and
  `web_server_send_frame(...)`. `web_server_start()` called after
  `wifi_link_start()`.
- `sdkconfig.defaults` gains `CONFIG_HTTPD_WS_SUPPORT=y`.
- `main/rd03d.c/.h` — **untouched.**
- USB console output unchanged (free diagnostics when attached).

## Web UI (embedded `index.html`)

Single dark-theme page, no external resources, mobile-friendly viewport:

- Canvas XY chart echoing the Processing sketch: radar at bottom-center
  origin, +Y forward (up), grid with range rings/labels, fixed plot range
  (default ±3 m X, 6 m Y).
- One color per target (T1/T2/T3), current position dot plus a fading trail
  (recent history kept client-side).
- HUD: connection state, per-target `x / y / v` readout, frames-received
  counter, and the firmware's `dropped`/`bad` link counters.
- WebSocket auto-reconnects every ~2 s when closed (XIAO reboot, WiFi blip)
  without freezing the page.

## Processing Sketch

Untouched. It continues to work in its original direct-USB serial mode; the
web page replaces its role for WiFi viewing.

## Error Handling

- WiFi down → firmware reconnect loop; radar reading and console continue.
- No WS clients → sends are no-ops.
- Slow/stalled WS client → that client is dropped; others unaffected.
- Browser side: on WS close, HUD shows "disconnected — retrying" and the page
  keeps retrying.

## Data Rate Sanity

~10 frames/s × ~120-byte JSON ≈ 1.2 KB/s per client — negligible.

## Testing / Verification

1. Host parser tests still pass (parser untouched).
2. `ping rd03d.local` resolves (mDNS).
3. `curl -s http://rd03d.local/ | head` returns the page HTML.
4. Browser on the Mac: live dots track motion; kill/restore XIAO power →
   page shows disconnected, then recovers.
5. Phone browser: same page works simultaneously with the Mac.
6. Untethered: XIAO on a USB power bank at the mounting spot.

## Out of Scope

- Raw TCP byte stream (dropped in the revision; the Processing sketch keeps
  its USB serial mode instead).
- Radar commands from the browser; authentication/TLS; OTA updates; HTTPS.
- WiFi provisioning UI (credentials remain build-time menuconfig).
