# RD-03D MQTT Publishing — Design

**Date:** 2026-09-06
**Target:** Seeed Studio XIAO ESP32-C6 (existing `rd03d_uart/` project)
**Framework:** ESP-IDF v5.5 (`~/esp/esp-idf-v5.5`), built-in `mqtt` (esp-mqtt) component
**Builds on:** WiFi/web UI and OTA designs (both done, merged, hardware-verified)
**Consumer:** Node-RED on the user's IOTstack (broker `iotstack.local:1883`, anonymous)

## Goal

The XIAO publishes radar detections over MQTT so LAN automations (Node-RED) can
react — but only when a target has actually moved a preset distance, so topics
carry events, not an 11 Hz firehose.

## Decisions Made

- Broker: `iotstack.local`, port 1883, **anonymous** (no credentials).
- **Per-target topics**: `rd03d/target/1` … `rd03d/target/3`.
- Movement payload: `{"x":-551,"y":550,"v":0}` (mm, mm, cm/s — same units as
  the WebSocket JSON).
- **Gone events**: when a previously-published target stops being reported,
  publish `{"gone":true}` once to its topic.
- Threshold: Euclidean distance vs the **last published** position, default
  **200 mm**, configurable via menuconfig.
- Availability: MQTT Last-Will on `rd03d/status` — retained `online` on
  connect; broker publishes retained `offline` when the device drops.
- QoS 0 everywhere; retain only on `rd03d/status`.
- Delivery of this feature to the device happens **via OTA** (no USB).

## Configuration (Kconfig, non-secret — defaults committed)

Added to the existing `RD03D Configuration` menu:

| Option | Default | Meaning |
| --- | --- | --- |
| `RD03D_MQTT_HOST` | `iotstack.local` | Broker hostname (`.local` resolved via mDNS) |
| `RD03D_MQTT_PORT` | `1883` | Broker TCP port |
| `RD03D_MQTT_MOVE_MM` | `200` | Minimum movement (mm) between publishes per target |

## New Module: `main/mqtt_pub.c/.h`

- `void mqtt_pub_start(void);` — spawns a connect task:
  1. Wait until `wifi_link_has_ip()`.
  2. Resolve the broker: if the host ends in `.local`, query it via
     `mdns_query_a()` (the firmware's mDNS stack is already running — esp-mqtt's
     own resolver uses plain DNS, which cannot see mDNS names); otherwise use
     the hostname as-is. On resolution failure, retry with a 30 s backoff
     (broker may be down/booting).
  3. Start `esp_mqtt_client` against `mqtt://<resolved>:<port>` with the
     Last-Will configured (`rd03d/status` → `offline`, retained). Publish
     retained `online` on `MQTT_EVENT_CONNECTED`. esp-mqtt's auto-reconnect
     handles broker restarts thereafter.
  4. On every `MQTT_EVENT_CONNECTED`, reset all per-target published state, so
     currently-present targets republish immediately — a consumer that
     (re)subscribes never waits indefinitely for state.
- `void mqtt_pub_frame(const rd03d_frame_t *f);` — called from the radar loop
  for every parsed frame:
  - Not connected → return immediately (no queuing, no blocking).
  - Per target i (1-based topic index): if present and (never published since
    connect OR `dx² + dy² ≥ threshold²` vs last published x/y) → publish the
    movement JSON, record the new position. If absent and previously
    published → publish `{"gone":true}` once, clear the state.
  - Publishes use QoS 0 / no retain and must never block the radar loop
    (esp-mqtt enqueues internally; on failure the event is simply dropped —
    the next movement retriggers).

## Wiring (`main/main.c`)

- `mqtt_pub_start();` after `web_server_start()` /
  `ota_update_register(...)`.
- `mqtt_pub_frame(&frame);` in the parse branch next to
  `web_server_send_frame(...)`.
- Everything else — parser, chart, WebSocket, OTA, validation — untouched.
  `main/rd03d.c/.h` untouched.

## Message Flow Examples

- Person walks through the zone: `rd03d/target/1` gets a message roughly every
  200 mm of travel; standing still (even for minutes) produces silence; leaving
  produces one `{"gone":true}`.
- Device power lost: broker publishes retained `offline` on `rd03d/status`.
- Broker restarts: esp-mqtt reconnects, `online` republished, current targets
  republish immediately.

## Error Handling

- Broker unresolvable/down at boot → resolve/connect retry loop (30 s), radar
  loop and all other features unaffected.
- Connection lost mid-run → esp-mqtt auto-reconnect; publishes silently skipped
  meanwhile; state resets on reconnect.
- The `gone` event for a target that disappears while disconnected is lost by
  design (QoS 0, no queue) — the reconnect-republish covers present targets,
  and an absent target's topic simply stops updating. Acceptable for this use.

## Testing / Verification

1. Host parser tests still pass (parser untouched).
2. Deliver via OTA; `/version` shows the new build.
3. Mac-side subscriber (python `paho-mqtt` in the scratchpad venv) on
   `rd03d/#`:
   - `rd03d/status` → `online` (and retained for late subscribers).
   - Walk test: movement messages with sane coordinates, cadence consistent
     with ~200 mm steps; stand-still silence; `{"gone":true}` after leaving.
   - Power-pull test: broker emits retained `offline` (LWT), then `online`
     after reboot.
4. Console log shows resolve → connect → publish lines; radar/chart unaffected.

## Out of Scope

- TLS, authentication (broker is anonymous by decision).
- QoS 1/2, message queuing while offline, retained target topics.
- Node-RED flow itself (consumer side is the user's).
- Home Assistant discovery (user runs Node-RED only).
