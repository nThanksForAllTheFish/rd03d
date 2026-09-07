# Stair Light Node-RED Flow

Turns the staircase light on when the rd03d radar sees a target inside a
zone, and off 60 s after the last in-zone activity. Built-in nodes only.

## Import

1. Open your Node-RED editor.
2. Menu (☰) → **Import** → select `flows-stair-light.json` (or paste its
   contents) → Import → **Deploy**.

## Configure (3 edit points)

1. **Broker** — the flow ships with an `iotstack` broker config node
   (`iotstack.local:1883`, anonymous). If your Node-RED already has a broker
   config for the same server, you can repoint the three MQTT nodes at it
   instead.
2. **Device topic** — double-click *"to Tasmota topic (EDIT DEVICE)"* and
   replace `stairlight` in `cmnd/stairlight/POWER` with your relay's topic.
3. **Zone** — double-click *"zone filter (EDIT ZONE)"* and set the four
   `ZONE` numbers (mm). Tune them with the walk test below.

## Zone tuning walk test

1. Open the radar chart (`http://rd03d.local`) next to the Node-RED debug
   sidebar.
2. Walk to each spot where the light SHOULD trigger (bottom approach, top
   landing) and read your x/y off the chart HUD.
3. Set `ZONE` so those spots are inside and pass-by areas are outside;
   Deploy; walk again and confirm *"in-zone events"* fires only where you
   want it.

## Test without walking

- The **force ON / force OFF** inject buttons drive the relay directly.
- `test_stair_flow.py` publishes synthetic radar events and watches the
  light topic (run it while the radar's view is quiet):

  `python3 test_stair_flow.py [broker] [light-topic] [--wait-off]`
  (arguments are positional; `--wait-off` may appear anywhere)

  Run it while the radar's view is quiet — real in-zone motion breaks the
  out-of-zone check and extends the hold.

## Behavior notes

- Any in-zone target (any of the 3 tracking slots) keeps the light on; the
  60 s hold restarts on each event.
- `{"gone":true}` and radar silence are both simply inactivity — the hold
  timer is the single source of truth for turning off.
- `rd03d/status` appears in the debug sidebar for sensor health but never
  drives the light: if the sensor dies while the light is on, the hold
  expires and the light turns off on its own.
- After a Deploy or Node-RED restart during an active hold, the timer is
  lost: a lit light stays lit until the next occupancy episode ends. If that
  bothers you, press **force OFF** after deploying.
- The force buttons are test aids, not overrides: **force OFF** during an
  active occupancy stays off until the current episode ends (radar activity
  only extends the running hold, it doesn't re-send ON), and a **force ON**
  is cancelled by the episode's eventual OFF.
- The *only changes* (rbe) node is belt-and-suspenders — the trigger already
  alternates ON/OFF strictly. Don't reconfigure it to "per topic" mode; that
  can swallow legitimate ONs.
