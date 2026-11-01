# PIR Companion Sensor — Design

**Date:** 2026-10-11
**Branch:** `feat/pir-companion` (off `main`)
**Firmware:** `rd03d_uart/` · **Case:** `case/fusion_scripts/` · **Flow:** `node-red/`

## Goal

Add a passive infrared sensor to the existing radar node so that both sensors
watch the same staircase from the same wall, and measure how a PIR compares with
the RD-03D at the one job that matters: turning the light on before a foot
reaches the first step, from either floor. The radar stays exactly as it is.
The PIR is an addition behind a Kconfig switch, publishes its own events, and the
Node-RED flow can run the light from the radar, the PIR, or either.

The second purpose is to prepare a battery version, where the XIAO and the radar
sleep until the PIR wakes them. That version is gated on a latency measurement
(see "Latency gate") and gets its own plan once the gate passes.

This is deliberately an exercise in letting the agent do the design, so the
geometry, the firmware and the case revision are all written as scripts and
specs, like the rest of the project.

## What the staircase scan established

The user scanned the staircase with LiDAR (Scaniverse, iPad Pro) on 2026-10-11 and a
separate session reduced it to dimensions. The ones the PIR design rests on:

- Switchback stair. The lower flight rises 1.44 m to a landing, turns 180°, and
  the upper flight rises a further 1.28 m alongside it behind a knee wall.
- The sensor wall is the wall behind the landing, about 1.0 m back from the top
  nosing of the lower flight. The node is mounted there at 2.24 m (88 in) above
  the landing floor, looking along both flights.
- Horizontal run of the lower flight 1.70 m, of the upper flight 1.54 m;
  stairwell 2.08 m wide, lower flight 1.06 m wide, upper flight 0.89 m.
- People mostly approach the foot and the top of the stairs from the side, not
  along the line of the flights. Nothing obstructs the view to the floor areas
  beyond either flight.

From the sensor, with the person's torso taken at 1.2 m above whichever floor
they stand on:

| target | distance | azimuth | elevation |
| --- | --- | --- | --- |
| foot of the lower flight | 3.7 m | 11° left | 43° down |
| 2 m beyond the foot (bottom floor) | 5.3 m | 6° left | 28° down |
| top of the upper flight | 2.6 m | 13° right | 6° up |
| 2 m beyond the top (top floor) | 4.6 m | 8° right | 3° up |

The ray to a torso 2 m past the top step clears the top-floor edge by about
0.9 m. Everything the light must react to lies in a wedge about 26° wide and
50° tall, from 6° above horizontal to 43° below. A stock wide-angle PIR lens
covers that; the design task is the aim angle, not the optics.

Side approaches are the strong case for a PIR (the person sweeps across several
zones). Motion on the flights is toward the sensor, the weak direction, but a
person climbs 0.18 m per step through the lens's stacked elevation tiers, which
registers.

## Decisions Made

- **Same node, not a second node.** One case, one jack, one OTA image, and both
  sensors' events come from one firmware, so timing comparisons need no clock
  reconciliation. A separate PIR node would be cleaner to isolate but doubles
  the hardware and complicates the comparison.
- **Panasonic EKMC1603111** (PaPIRs, wide-angle lens, 3.3 V, 100 µA, digital
  output, 12 m rated range). Low quiescent current matters for the battery
  version; the digital output goes straight into a XIAO pin. The HC-SR501 is the
  cheap alternative but wants 5 V and carries its own timer electronics.
- **PIR on D1 (GPIO1).** The ESP32-C6 can wake from deep sleep only on its
  low-power IOs, GPIO0 to 7. D1 is free, is an LP IO, and is not a strapping
  pin. The radar keeps D6/D7.
- **Radar power switch on D2 (GPIO2), for the battery version.** A boost
  converter with an enable pin makes the RD-03D's 5 V from the cell; enable low
  shuts both the radar and the boost down to microamps. In mains mode the pin is
  simply held high (or the boost is absent and the radar runs from the jack's
  5 V as today).
- **Kconfig switch, default off in the AP image.** `RD03D_ENABLE_PIR` keeps the
  work-site build unchanged.
- **Events, not polling.** A GPIO interrupt feeds a small gate (debounce + hold)
  and a publish; no task wakes up to poll the pin.
- **Mains mode first.** The battery mode is specified here so the pin choices
  and the power switch are right from the start, but it is implemented only
  after the latency gate passes.
- **No optics work.** No mirrors, no polyethylene window, no milled parts. The
  module's own lens is the window; the case only has to let it see out at the
  right angle.

## Hardware

Wiring, soldered to the top of the XIAO like the radar:

| EKMC pin | XIAO | note |
| --- | --- | --- |
| VDD | 3V3 | 0.1 µF ceramic across VDD/GND at the sensor; the element is sensitive to supply noise |
| OUT | D1 (GPIO1) | drives high on detection, floats otherwise: enable the C6's internal pull-down |
| GND | GND | |

Battery version additions (not built in phase 1): single Li-ion cell on the
XIAO's BAT pads (its charger runs from the USB jack already in the plate), a boost
converter such as a TPS61023 module for the radar's 5 V with EN on D2, and a cell
holder. Idle draw is the PIR's 100 µA plus deep sleep, about 150 µA; a 3000 mAh
18650 lasts over a year at a few dozen wakes a day. The current case has no room
for a cell; a deeper back plate or an external pack is decided in the battery
plan.

## Firmware

### `pir.c` / `pir.h`

- `pir_init(gpio, cb)`: configures the pin as input with pull-down, installs a
  rising-edge ISR, starts a one-shot `esp_timer` used for the hold.
- The ISR only posts to a queue; a small task runs the gate and the callback.
- The gate (`pir_gate.c`, pure C, no IDF dependency, same pattern as
  `mqtt_throttle.c`): an edge while idle produces one event and starts a hold of
  `RD03D_PIR_HOLD_MS` (default 500 ms); edges during the hold extend it and
  produce nothing. The EKMC output already stays high for about 2 s per
  detection; the hold is there so bursts of edges from one pass become one
  event.
- On each event: `led_pulse()`, then the publisher callback with the event
  sequence number and timestamp.

### MQTT

New topic `rd03d/pir`, QoS 0, not retained:

```
{"n": 17, "t": 1760190000123, "radar": {"x": -420, "y": 2310, "v": 38}}
```

`n` is the event count since boot, `t` is epoch milliseconds (see time below),
`radar` is the radar's current nearest target or `null` when it has none. The
radar field is the comparison data: for every PIR event it records where the
radar had the person at that instant.

New retained topic `rd03d/pir/state`, `1` while the gate is in its hold, `0`
otherwise, so the flow and the chart can show the PIR as a lamp.

`rd03d/status` is unchanged.

### Time

Mains mode enables SNTP once WiFi is up so `t` is wall-clock milliseconds. With
the broker's host on the same LAN, Node-RED's arrival timestamp minus `t` is the
one-way latency directly, which is the measurement the battery gate needs.
Battery mode keeps time across deep sleep on the C6's RTC (drift of a few
milliseconds per minute of sleep is fine for this) and resyncs on each wake.

### Kconfig

```
RD03D_ENABLE_PIR       bool   default y (STA image), n in sdkconfig.ap
RD03D_PIR_GPIO         int    default 1
RD03D_PIR_HOLD_MS      int    default 500
RD03D_POWER_MODE       choice MAINS (default) / BATTERY
RD03D_RADAR_EN_GPIO    int    default 2        (BATTERY only)
RD03D_AWAKE_WINDOW_S   int    default 60       (BATTERY only)
```

### Battery mode (specified now, built after the gate)

- Deep sleep with EXT1 wake on the PIR pin, level high.
- On wake: raise `RADAR_EN`, start WiFi with the stored channel and BSSID and a
  static address (no scan, no DHCP), connect MQTT, publish the PIR event first,
  then run the radar as normal for `AWAKE_WINDOW_S`, extended by any further PIR
  event, then publish `rd03d/pir/state 0`, drop `RADAR_EN` and sleep.
- OTA: `/update` is reachable during the awake window; the rollback-cancel logic
  is unchanged (the IP event still fires in STA mode).
- The chart is live only during the awake window; that is the cost of the
  battery version and the reason the mains version stays the default.

## Latency gate

The battery version is worth building only if the wake path does not visibly
delay the light. The gate:

1. In the mains build, log the one-way latency of `rd03d/pir` events
   (Node-RED arrival minus `t`) over a few days of normal use. That is the
   baseline; expect tens of milliseconds.
2. Build a throwaway image that does nothing but sleep, wake on the PIR, join
   WiFi with the shortcuts above, publish one event, and sleep again. Walk the
   same route and log the same number. Expectation: 0.5 to 1 s.
3. Pass if the wake path adds no more than 0.5 s over the baseline. Then the
   battery plan goes ahead with deep sleep.
4. Fail: fall back to light sleep. The C6 stays associated and wakes in tens of
   milliseconds at roughly 1 to 2 mA, months on a cell instead of years, with
   no visible delay. The battery plan is written against whichever mode passed.

## Case

Final layout (2026-10-25, after one test print and three rounds with the user).
Three decisions drive it:

1. **The PIR looks where the radar looks** (`pirTilt` = 0): the user wants the
   two fields to overlap as much as possible. The case hangs on its ball joint
   aimed at the stairs; the PIR rides along. The lens's ±46° vertical field
   centred on the radar's boresight covers the stair wedge (6° up to 43° down)
   for any case tilt up to about 40°.
2. **The plate holds the sensor; the shell covers it.** All wiring stays on the
   plate and the shell lifts off over the sensor.
3. **Retention is simple:** a snug socket and a snug bezel ring, no clamp, no
   plug, no keeper. On a horizontal axis nothing pulls the sensor out.

Geometry (case frame, z −8 back plane .. 16 front face):

- **Wing.** The plate grows a 6 mm tab (z −8..−2) on its +X end, flush with
  the plate's back, y ±13.5 less the fit allowance, out to x 49 less the
  allowance. Two Technic holes through it at (24.95, ±4). Snap pockets in its
  ±Y faces.
- **Socket.** A straight boss on the wing at (35.5, 0): outer Ø15.4, bore
  Ø11.1 (0.15 per side on the measured Ø10.8 base; holes print true), from the
  wing top to z 14.0 where the sensor's flange underside seats; 1 mm foot
  fillet. The bore is blind at the wing top. A Ø3 wire hole leaves the boss's
  −X side at z 4 (pin level) into the pod cavity; the wires run over the wing
  into the XIAO bay.
- **Pod box on the shell.** The shell's +X wall over |y| ≤ 13.5 is replaced by
  a hollow box, walls 2 mm, inner y ±13.5, x 21..49, full height, open to the
  shell cavity. Its flat top carries a Ø23.3 hole: the lens ring (Ø20.6) and
  its two latch tabs (Ø22) pass, the ring's top sits flush with the face, the
  dome stands 11 mm proud. Snap bumps on the box's inner ±Y walls engage the
  wing's pockets; the shell's −X snap pair is unchanged; the old +X pair is
  gone.
- **Bezel.** A one-piece ring dropped into the gap from the front: flange
  r 10.4..12.5 × 0.8 mm on the face, two skirt arcs r 10.4..11.65 × 2 mm in
  the hole, two 6 mm notches 180° apart (through the skirt, and through the
  flange out to r 11.4, leaving a bridge) that sit over the lens's tabs, which
  are at 45°/225° on the sensor and 5 mm wide. Light push fit in the hole
  (outside walls print 0.2 under, holes true) and 0.1 around the lens ring.
  Clocked to wherever the tabs ended up; the sensor itself is placed at any
  rotation.
- **Fit allowances from calipers (2026-10-25):** plate outside prints 0.17
  (X) and 0.27 (Y) under, the shell cavity true in X and 0.34 over in Y, the
  wing 0.24 under, the box cavity 0.2 over. `rimGapX` 0.03, `rimGapY` −0.20,
  `wingGap` −0.12 give about 0.1 mm per side everywhere.
- Printable without supports: plate back-down, shell face-down, bezel
  flange-down.
- Verification: `90_verify.py` probes socket, bore, wing, Technic holes, box,
  hole, snaps and the bezel in its own frame; `91_pir_fit.py` places the
  sensor STEP and the bezel and checks interference (the plate/shell fit
  overlap is the only expected pair; sensor-to-bezel clearances are printed).

Earlier layouts (shell pod with supports; plate tower with a canted top; bayonet
bezel) are in the branch history and the plan's Tasks 9, 9b, 9c, 9d.

## Chart page

The WebSocket frame gains a `pir` field (the gate state). The chart flashes its
outer ring and logs a line for each PIR event so a walk can be watched with both
sensors reacting on one screen.

## Node-RED

- New MQTT-in node on `rd03d/pir`, feeding the existing hold through a source
  switch: `radar`, `pir`, `either` (default `either` once the PIR has a day of
  clean data; `radar` until then).
- A logging branch writes one CSV line per trigger episode: timestamp, which
  sensor fired first, the delay to the other, and the radar position at the PIR
  event. Read it after a few days to decide what the PIR is good for.
- The latency measurement is the same branch: arrival time minus `t`.

## Verification

- `tests/test_pir_gate.c`: host unit test for the gate (single edge → one event;
  burst within the hold → one event; edge after the hold → a second event; hold
  extension).
- Bench: PIR taped to the outside of the case, dome 18° down, before any case
  work. Hand wave at 1 m, 3 m, 5 m; confirm one event per pass and the LED pulse.
- Walk test, same route as the radar one (approach from downstairs on the left,
  up, out the top on the right, back, down, out the left), with the CSV branch
  running. Success: the PIR fires before the first step on both approaches, and
  the first-fire delay against the radar is reported per approach.
- Case: probe harness passes; both parts print without supports anywhere; the
  dome sees the
  whole wedge when the case is on the wall (check with the chart's PIR lamp while
  walking the extremes).

## Deliverables

1. `rd03d_uart/main/pir.c`, `pir.h`, `pir_gate.c`, `pir_gate.h`, Kconfig
   entries, SNTP enable, the `rd03d/pir` and `rd03d/pir/state` topics, the chart
   `pir` field.
2. `tests/test_pir_gate.c` and its Makefile entry.
3. `case/fusion_scripts/02_backplate.py` wing/pod (parameters in its
   `ensure_params`), `03_shell.py` notch, `90_verify.py` checks,
   `91_pir_fit.py` fit check.
4. `node-red/flows-stair-light.json` with the source switch and the CSV branch.
5. A short note in `docs/` with the walk-test and latency numbers once measured.

## Out of scope

- The battery build itself (cell, boost, holder, deep-sleep firmware): its own
  plan after the latency gate.
- Any change to the radar parser, throttle, or the existing MQTT topics.
- Custom PIR optics. The mirror and polyethylene-window options discussed before
  the scan are documented here only as not needed for this geometry.
- Replacing the radar. The point is to run both and compare.
