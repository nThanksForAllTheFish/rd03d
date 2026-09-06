# RD-03D WiFi Streaming — Design

**Date:** 2026-09-06
**Target:** Seeed Studio XIAO ESP32-C6 (existing `rd03d_uart/` project)
**Framework:** ESP-IDF v5.5 (`~/esp/esp-idf-v5.5`)
**Builds on:** `2026-08-31-rd03d-uart-design.md` (UART reader, done and hardware-verified)

## Goal

Run the XIAO untethered (USB power only, no data cable) at the radar's intended
mounting location and stream RD-03D data over the home WiFi network to the
Processing visualizer `RD03D_RadarChart`, which gains a network mode.

## Architecture

- **Transport:** TCP. The XIAO runs a server on port **3333**; the sketch
  connects as a client using Processing's built-in `processing.net.Client`.
- **Discovery:** mDNS — the XIAO advertises itself as **`rd03d.local`** so the
  sketch never needs a hardcoded IP.
- **Payload:** the raw UART byte stream from the radar, forwarded **verbatim**
  (30-byte `AA FF 03 00 … 55 CC` frames plus any line noise). No framing layer:
  the sketch's existing parser already resynchronizes on the header, so byte
  alignment over the wire doesn't matter.
- **Direction:** one-way (radar → sketch). The firmware itself puts the radar
  in multi-target mode at boot; the sketch's network mode sends nothing.

## Firmware Changes (`rd03d_uart/`)

New modules, keeping `main.c` lean:

- `main/wifi_link.c/.h` — WiFi station bring-up + mDNS.
  - Joins the home 2.4 GHz network. Credentials come from **menuconfig**
    (`CONFIG_RD03D_WIFI_SSID` / `CONFIG_RD03D_WIFI_PASSWORD` via a `Kconfig.projbuild`),
    so they live in the untracked generated `sdkconfig`, never in committed source.
  - Auto-reconnects on disconnect (ESP-IDF event handler loop), logging state
    changes to the console.
  - Advertises `rd03d.local` via the `espressif/mdns` managed component.
- `main/stream_server.c/.h` — TCP listener on port 3333.
  - One client at a time; a new connection replaces the old one.
  - `stream_server_send(buf, len)`: forwards bytes to the connected client if
    any; non-blocking with a short send timeout — on backpressure or error the
    data is dropped and the client closed, never stalling the radar loop.

Changes to existing code:

- `main/main.c` — after UART init: send the multi-target command
  `FD FC FB FA 02 00 90 00 04 03 02 01` once (with a short settle delay);
  start `wifi_link` and `stream_server`; in the read loop, pass each chunk
  from `uart_read_bytes` to `stream_server_send` before parsing it locally.
- `main/rd03d.c/.h` — **untouched.**
- USB console behavior unchanged: parsed text lines + link stats still print
  (free diagnostics when attached; harmless when untethered).
- `sdkconfig.defaults` gains the WiFi/lwIP/mDNS options the feature needs
  (WiFi enabled; NVS for PHY calibration data is on by default).

## Processing Sketch Changes (`RD03D_RadarChart/`)

Config flags at the top of the sketch:

```java
boolean useNetwork = true;          // false = original serial mode
String networkHost = "rd03d.local";
int networkPort = 3333;
```

- Network mode: open `processing.net.Client`; skip `readFirmwareVersion()` and
  the multi-target write (firmware handles radar config). Poll
  `client.available()` in `draw()` and feed bytes into the **same**
  `inputBuffer`/`parsePacket` path serial mode uses.
- Serial mode: unchanged, still the fallback when `useNetwork = false`.
- Status line shows mode, host, and connection state; on connection loss the
  sketch keeps running and retries every ~2 s instead of freezing.

## Error Handling

- WiFi down / router restart → firmware reconnect loop; radar reading and USB
  console continue regardless.
- No TCP client connected → `stream_server_send` is a cheap no-op.
- Client stalls (backpressure) → drop + disconnect that client; radar loop
  never blocks. The sketch reconnects and resyncs mid-stream.
- Sketch cannot resolve/connect → visible "connecting…" status + periodic
  retry; no crash.

## Data Rate Sanity

~10 frames/s × 30 bytes = ~300 B/s — negligible for WiFi and TCP.

## Testing / Verification

1. Host parser tests still pass (regression; parser untouched).
2. Firmware alone: `nc rd03d.local 3333 | xxd | head` on the Mac shows live
   `aaff 0300 … 55cc` frames — verifies WiFi, mDNS, and streaming with no
   Processing involved.
3. Reconnect drill: kill and rerun `nc`; power-cycle the XIAO mid-connection;
   confirm the stream resumes both times.
4. Sketch network mode against the live XIAO: targets plot; pull XIAO power and
   confirm the sketch shows disconnected then recovers on reboot.
5. Untethered test: XIAO on a USB power bank at the mounting spot, sketch
   plotting on the Mac.

## Out of Scope

- Bidirectional command tunnel (sketch → radar commands over WiFi).
- Multiple simultaneous viewer clients.
- WiFi provisioning UI (credentials are set at build time via menuconfig).
- AP mode, TLS/auth, OTA updates.
