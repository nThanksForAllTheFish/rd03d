# Stair Light Node-RED Flow — Design

**Date:** 2026-09-06
**Runs on:** the user's Node-RED (IOTstack, same host as the MQTT broker `iotstack.local:1883`)
**Consumes:** rd03d MQTT topics (see `2026-09-06-rd03d-mqtt-design.md`)
**Controls:** a Tasmota-style MQTT relay/plug (`cmnd/<device>/POWER` → `ON`/`OFF`)

## Goal

Turn the staircase light on when a radar target is inside a configurable zone,
keep it on while anyone remains active there, and turn it off 60 s after the
last in-zone activity — using only built-in Node-RED nodes, delivered as an
importable flow JSON.

## Decisions Made

- Actuator: Tasmota/relay MQTT on/off. Placeholder command topic
  `cmnd/stairlight/POWER`; the user renames it to their device.
- Trigger: zone rectangle filter on target coordinates (bounds tuned after the
  physical placement test); approach-velocity refinement deferred (one extra
  condition in the filter when wanted).
- Off behavior: retriggerable 60 s hold via the built-in `trigger` node.
  `{"gone":true}` events and silence are treated identically (inactivity).
  No time-of-day gating.
- Sensor `rd03d/status` is surfaced for debugging but does NOT drive the
  light (a dead sensor resolves through the normal timeout).

## Flow Structure (built-in nodes only)

```
[mqtt in rd03d/target/+] → [zone filter (function)] → [trigger 60s] → [rbe] → [map payload] → [mqtt out cmnd/stairlight/POWER]
                                     ↓ (debug: in-zone events)
[inject "force ON"] ──────────────────────────────────────────────→ [map payload]
[inject "force OFF"] ─────────────────────────────────────────────→ [map payload]
[mqtt in rd03d/status] → [debug: sensor availability]
```

- **Zone filter** (function node, ~15 lines): config constants at the top —
  `ZONE = { xMin: -1500, xMax: 1500, yMin: 300, yMax: 3000 }` (placeholder;
  units mm, matching the radar payloads). Parses the JSON payload; drops
  `gone` events and anything outside the rectangle; forwards in-zone messages
  unchanged. Malformed payloads are dropped silently.
- **Trigger node**: on any incoming message send `ON`; after 60 s of quiet
  send `OFF`; each new message extends the delay. This is the entire on/off
  logic — one ON per occupancy episode, one OFF, self-healing.
- **rbe node** (report-by-exception): forwards only payload *changes*,
  guaranteeing the Tasmota topic never sees repeats.
- **Map payload** (change node): passes `ON`/`OFF` through as the message
  payload for the command topic (Tasmota accepts `ON`/`OFF` strings).
- **Inject buttons**: manual `ON` / `OFF` for testing the light path without
  motion; wired after the trigger logic (via the map node) so they don't
  disturb the timer state.
- **MQTT broker config node**: `iotstack.local:1883`, anonymous — reused for
  all three MQTT nodes.

## Multi-Target Semantics

All three `rd03d/target/+` topics feed the same filter; any in-zone target
extends the hold. The light goes off 60 s after the *last* in-zone activity,
regardless of which tracking slot produced it (slot numbers are not stable
identities and are deliberately ignored).

## Edge Behavior

- Broker or Node-RED restart: no stuck state — the light state re-derives
  from the next event or times out.
- Radar reboot (e.g. OTA): reconnect republish may re-light the stairs if
  someone is in zone — correct.
- Sensor offline while light is on: trigger's 60 s expiry turns it off.
- Two people: last one to leave starts the countdown.

## Deliverables

- `node-red/flows-stair-light.json` — importable flow (Menu → Import).
- `node-red/README.md` — import steps; the three edit points (broker config
  if theirs differs, Tasmota device topic, zone bounds); tuning procedure:
  walk the stairs watching the flow's debug output alongside the radar chart
  (`http://rd03d.local`), read your x/y from the chart HUD at the approach
  positions, set the rectangle, redeploy.

## Testing / Verification

1. Static: flow JSON imports cleanly into Node-RED (validated structurally
   before delivery; final import is on the user's instance).
2. From this Mac (no Node-RED needed): a python paho-mqtt harness plays the
   roles — subscribe to `cmnd/stairlight/POWER` while publishing synthetic
   `rd03d/target/1` messages (in-zone, out-of-zone, gone) — BUT this only
   works once the flow runs in the user's Node-RED; until then the harness
   serves as the acceptance script the user runs after import.
3. Real test: user walks the stairs; light on within a beat, off ~60 s after.

## Out of Scope

- Approach-direction filtering (noted one-liner for later).
- Dimming/effects (relay is on/off), multi-zone, second sensor node,
  time-of-day gating.
- Installing/configuring Node-RED or Tasmota themselves.
