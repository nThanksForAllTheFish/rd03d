# Stair Light Node-RED Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** An importable Node-RED flow that lights the staircase relay (`cmnd/stairlight/POWER`) when a radar target is inside a configurable zone and turns it off 60 s after the last in-zone activity, plus a validator, an acceptance harness, and a README.

**Architecture:** Built-in nodes only: `mqtt in rd03d/target/+` → zone-filter function node (editable ZONE constants) → `trigger` (ON now, OFF after 60 s, extend on retrigger) → `rbe` (dedupe) → `change` (sets the Tasmota command topic — the single edit point for the device name) → `mqtt out`. Plus force-ON/OFF inject buttons, debug taps, and an `rd03d/status` monitor that deliberately does not drive the light.

**Tech Stack:** Node-RED built-ins (flow JSON, no palette dependencies), Python (json validation + paho-mqtt acceptance harness in the scratchpad venv).

**Spec:** `docs/superpowers/specs/2026-09-06-stair-light-flow-design.md`

**Environment:** No firmware work; the device (rd03d.local) and broker (iotstack.local:1883 / 192.168.1.243) are live. The scratchpad venv (/private/tmp/claude-501/-path-to-rd03d/1a58ef3a-b659-4aae-a07a-3f6d1a6f573b/scratchpad/venv) has paho-mqtt. Nothing here can be fully end-to-end verified until the user imports the flow into their Node-RED — the plan's verification is: structural validation now, harness plumbing now, real walk test by the user after import.

---

### Task 1: The flow JSON + structural validator

**Files:**
- Create: `node-red/validate_flow.py`
- Create: `node-red/flows-stair-light.json`

- [ ] **Step 1: Write the validator first**

`node-red/validate_flow.py`:

```python
#!/usr/bin/env python3
"""Structural validation for flows-stair-light.json (no Node-RED needed)."""
import json
import sys
from pathlib import Path

FLOW = Path(__file__).parent / "flows-stair-light.json"

def fail(msg):
    print(f"FAIL: {msg}")
    sys.exit(1)

nodes = json.loads(FLOW.read_text())
if not isinstance(nodes, list):
    fail("top level must be a list")

by_id = {n["id"]: n for n in nodes}
if len(by_id) != len(nodes):
    fail("duplicate node ids")

tabs = [n for n in nodes if n["type"] == "tab"]
if len(tabs) != 1:
    fail(f"expected exactly 1 tab, got {len(tabs)}")
tab_id = tabs[0]["id"]

configs = {"tab", "mqtt-broker"}
for n in nodes:
    if n["type"] in configs:
        continue
    if n.get("z") != tab_id:
        fail(f"node {n['id']} ({n['type']}) not on the tab")
    for out in n.get("wires", []):
        for target in out:
            if target not in by_id:
                fail(f"node {n['id']} wires to missing node {target}")

def one(type_, pred=lambda n: True, what=""):
    found = [n for n in nodes if n["type"] == type_ and pred(n)]
    if len(found) != 1:
        fail(f"expected exactly one {type_} {what}, got {len(found)}")
    return found[0]

broker = one("mqtt-broker")
if broker["broker"] != "iotstack.local" or str(broker["port"]) != "1883":
    fail("broker must be iotstack.local:1883")

tgt_in = one("mqtt in", lambda n: n.get("topic") == "rd03d/target/+", "(targets)")
one("mqtt in", lambda n: n.get("topic") == "rd03d/status", "(status)")

zone = one("function")
for needle in ("const ZONE", "JSON.parse", "gone", "xMin", "yMax"):
    if needle not in zone["func"]:
        fail(f"zone filter missing '{needle}'")

trig = one("trigger")
if not (trig["op1"] == "ON" and trig["op2"] == "OFF" and trig["extend"] is True
        and str(trig["duration"]) == "60" and trig["units"] == "s"):
    fail("trigger must be ON, then OFF after 60s, extend on retrigger")

one("rbe")
change = one("change")
if change["rules"][0]["to"] != "cmnd/stairlight/POWER":
    fail("change node must set topic cmnd/stairlight/POWER")

out = one("mqtt out")
if out.get("topic", "") != "":
    fail("mqtt out topic must be empty (msg.topic from the change node)")

injects = [n for n in nodes if n["type"] == "inject"]
if sorted(n["payload"] for n in injects) != ["OFF", "ON"]:
    fail("expected force ON and force OFF inject buttons")

debugs = [n for n in nodes if n["type"] == "debug"]
if len(debugs) != 2:
    fail(f"expected 2 debug nodes, got {len(debugs)}")

# Wiring spine: targets -> zone -> trigger -> rbe -> change -> mqtt out
def wired(a, b):
    return any(b["id"] in out for out in a.get("wires", []))

spine = [tgt_in, zone, trig, one("rbe"), change, out]
for a, b in zip(spine, spine[1:]):
    if not wired(a, b):
        fail(f"{a['type']} not wired to {b['type']}")
for inj in injects:
    if not wired(inj, change):
        fail("inject buttons must wire into the change node")

print("flow validation passed")
```

- [ ] **Step 2: Run it to verify it fails (no flow yet)**

```bash
cd node-red && python3 validate_flow.py
```

Expected: FAIL — `FileNotFoundError` (flows-stair-light.json missing).

- [ ] **Step 3: Write the flow**

`node-red/flows-stair-light.json`:

```json
[
    {
        "id": "stairtab1",
        "type": "tab",
        "label": "Stair Light",
        "disabled": false,
        "info": "Radar-driven stair lighting: rd03d MQTT events -> zone filter -> 60s hold -> Tasmota relay.\nEdit points: ZONE constants in the zone filter node; device topic in the change node."
    },
    {
        "id": "stairbroker1",
        "type": "mqtt-broker",
        "name": "iotstack",
        "broker": "iotstack.local",
        "port": "1883",
        "clientid": "",
        "autoConnect": true,
        "usetls": false,
        "protocolVersion": "4",
        "keepalive": "60",
        "cleansession": true,
        "autoUnsubscribe": true,
        "birthTopic": "",
        "birthQos": "0",
        "birthPayload": "",
        "birthMsg": {},
        "closeTopic": "",
        "closeQos": "0",
        "closePayload": "",
        "closeMsg": {},
        "willTopic": "",
        "willQos": "0",
        "willPayload": "",
        "willMsg": {},
        "userProps": "",
        "sessionExpiry": ""
    },
    {
        "id": "stairin1",
        "type": "mqtt in",
        "z": "stairtab1",
        "name": "radar targets",
        "topic": "rd03d/target/+",
        "qos": "0",
        "datatype": "utf8",
        "broker": "stairbroker1",
        "nl": false,
        "rap": true,
        "rh": 0,
        "inputs": 0,
        "x": 130,
        "y": 120,
        "wires": [["stairzone1"]]
    },
    {
        "id": "stairzone1",
        "type": "function",
        "z": "stairtab1",
        "name": "zone filter (EDIT ZONE)",
        "func": "// Zone bounds in mm, radar frame: x lateral (+/-), y forward from sensor.\n// EDIT these four numbers after the placement walk test.\nconst ZONE = { xMin: -1500, xMax: 1500, yMin: 300, yMax: 3000 };\n\nlet d;\ntry {\n    d = JSON.parse(msg.payload);\n} catch (e) {\n    return null; // malformed payload\n}\nif (d.gone) {\n    return null; // disappearance = inactivity; the trigger timeout handles it\n}\nif (typeof d.x !== \"number\" || typeof d.y !== \"number\") {\n    return null;\n}\nif (d.x < ZONE.xMin || d.x > ZONE.xMax || d.y < ZONE.yMin || d.y > ZONE.yMax) {\n    return null; // outside the zone\n}\nreturn msg; // in-zone activity\n",
        "outputs": 1,
        "timeout": "",
        "noerr": 0,
        "initialize": "",
        "finalize": "",
        "libs": [],
        "x": 330,
        "y": 120,
        "wires": [["stairtrig1", "stairdbg1"]]
    },
    {
        "id": "stairdbg1",
        "type": "debug",
        "z": "stairtab1",
        "name": "in-zone events",
        "active": true,
        "tosidebar": true,
        "console": false,
        "tostatus": false,
        "complete": "payload",
        "targetType": "msg",
        "statusVal": "",
        "statusType": "auto",
        "x": 560,
        "y": 180,
        "wires": []
    },
    {
        "id": "stairtrig1",
        "type": "trigger",
        "z": "stairtab1",
        "name": "ON, hold 60s",
        "op1": "ON",
        "op2": "OFF",
        "op1type": "str",
        "op2type": "str",
        "duration": "60",
        "extend": true,
        "overrideDelay": false,
        "units": "s",
        "reset": "",
        "bytopic": "all",
        "topic": "topic",
        "outputs": 1,
        "x": 550,
        "y": 120,
        "wires": [["stairrbe1"]]
    },
    {
        "id": "stairrbe1",
        "type": "rbe",
        "z": "stairtab1",
        "name": "only changes",
        "func": "rbe",
        "gap": "",
        "start": "",
        "inout": "out",
        "septopics": false,
        "property": "payload",
        "topi": "topic",
        "x": 730,
        "y": 120,
        "wires": [["stairmap1"]]
    },
    {
        "id": "stairmap1",
        "type": "change",
        "z": "stairtab1",
        "name": "to Tasmota topic (EDIT DEVICE)",
        "rules": [
            {
                "t": "set",
                "p": "topic",
                "pt": "msg",
                "to": "cmnd/stairlight/POWER",
                "tot": "str"
            }
        ],
        "action": "",
        "property": "",
        "from": "",
        "to": "",
        "reg": false,
        "x": 950,
        "y": 120,
        "wires": [["stairout1"]]
    },
    {
        "id": "stairout1",
        "type": "mqtt out",
        "z": "stairtab1",
        "name": "stair light relay",
        "topic": "",
        "qos": "0",
        "retain": "false",
        "respTopic": "",
        "contentType": "",
        "userProps": "",
        "correl": "",
        "expiry": "",
        "broker": "stairbroker1",
        "x": 1170,
        "y": 120,
        "wires": []
    },
    {
        "id": "stairinjon1",
        "type": "inject",
        "z": "stairtab1",
        "name": "force ON",
        "props": [{"p": "payload"}],
        "repeat": "",
        "crontab": "",
        "once": false,
        "onceDelay": 0.1,
        "topic": "",
        "payload": "ON",
        "payloadType": "str",
        "x": 720,
        "y": 220,
        "wires": [["stairmap1"]]
    },
    {
        "id": "stairinjoff1",
        "type": "inject",
        "z": "stairtab1",
        "name": "force OFF",
        "props": [{"p": "payload"}],
        "repeat": "",
        "crontab": "",
        "once": false,
        "onceDelay": 0.1,
        "topic": "",
        "payload": "OFF",
        "payloadType": "str",
        "x": 720,
        "y": 260,
        "wires": [["stairmap1"]]
    },
    {
        "id": "stairstat1",
        "type": "mqtt in",
        "z": "stairtab1",
        "name": "sensor status",
        "topic": "rd03d/status",
        "qos": "0",
        "datatype": "utf8",
        "broker": "stairbroker1",
        "nl": false,
        "rap": true,
        "rh": 0,
        "inputs": 0,
        "x": 130,
        "y": 320,
        "wires": [["stairdbg2"]]
    },
    {
        "id": "stairdbg2",
        "type": "debug",
        "z": "stairtab1",
        "name": "sensor status",
        "active": true,
        "tosidebar": true,
        "console": false,
        "tostatus": false,
        "complete": "payload",
        "targetType": "msg",
        "statusVal": "",
        "statusType": "auto",
        "x": 330,
        "y": 320,
        "wires": []
    }
]
```

- [ ] **Step 4: Run the validator to verify it passes**

```bash
cd node-red && python3 validate_flow.py
```

Expected: `flow validation passed`

Additionally, if `node` is available (`node -v`), syntax-check the function body:

```bash
cd node-red && python3 -c "
import json, pathlib, subprocess, tempfile, shutil, sys
if shutil.which('node') is None:
    print('node not installed - skipping JS syntax check'); sys.exit(0)
nodes = json.loads(pathlib.Path('flows-stair-light.json').read_text())
func = next(n for n in nodes if n['type'] == 'function')['func']
with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False) as f:
    f.write('function nodefn(msg){' + func + '}')
    path = f.name
r = subprocess.run(['node', '--check', path], capture_output=True, text=True)
print(r.stderr if r.returncode else 'JS syntax OK')
sys.exit(r.returncode)
"
```

Expected: `JS syntax OK` (or the skip message).

- [ ] **Step 5: Commit**

```bash
git add node-red/validate_flow.py node-red/flows-stair-light.json
git commit -m "feat(stair-light): importable Node-RED flow with structural validator"
```

End every commit message in this plan with:
`Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`

---

### Task 2: Acceptance harness

**Files:**
- Create: `node-red/test_stair_flow.py`

- [ ] **Step 1: Write the harness**

`node-red/test_stair_flow.py`:

```python
#!/usr/bin/env python3
"""Acceptance harness for the stair-light flow. Run AFTER importing the flow
into Node-RED. Publishes synthetic radar events and watches the light topic.

Usage: python3 test_stair_flow.py [broker-host] [light-topic]
Defaults: iotstack.local, cmnd/stairlight/POWER

CAUTION: the real radar publishes to the same topics — run this while the
radar's view is quiet (or unplugged), otherwise real motion can produce
extra ONs. The definitive test is walking the stairs.
"""
import json
import sys
import time

import paho.mqtt.client as mqtt

BROKER = sys.argv[1] if len(sys.argv) > 1 else "iotstack.local"
LIGHT_TOPIC = sys.argv[2] if len(sys.argv) > 2 else "cmnd/stairlight/POWER"
TARGET_TOPIC = "rd03d/target/1"

seen = []

def on_message(c, u, m):
    line = (time.strftime("%H:%M:%S"), m.payload.decode())
    seen.append(line)
    print(f"{line[0]} {LIGHT_TOPIC} -> {line[1]}", flush=True)

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.on_message = on_message
client.connect(BROKER, 1883, 30)
client.subscribe(LIGHT_TOPIC)
client.loop_start()
time.sleep(1)

def publish(payload):
    print(f"publishing {TARGET_TOPIC} {payload}")
    client.publish(TARGET_TOPIC, json.dumps(payload))

def wait_for(value, timeout):
    deadline = time.time() + timeout
    start = len(seen)
    while time.time() < deadline:
        if any(p == value for _, p in seen[start:]):
            return True
        time.sleep(0.2)
    return False

failures = 0

# 1. In-zone target -> ON
publish({"x": 0, "y": 1000, "v": -10})
if wait_for("ON", 5):
    print("PASS: in-zone event turned the light ON")
else:
    print("FAIL: no ON within 5s - is the flow deployed and the broker right?")
    failures += 1

# 2. Out-of-zone target -> no new command (rbe also swallows repeat ONs,
#    so we verify no OFF arrives, i.e. nothing unexpected)
before = len(seen)
publish({"x": 6000, "y": 7500, "v": 0})
time.sleep(5)
if len(seen) == before:
    print("PASS: out-of-zone event produced no light command")
else:
    print("FAIL: out-of-zone event produced a command")
    failures += 1

# 3. Optional: wait out the hold for OFF
if "--wait-off" in sys.argv:
    print("waiting up to 75s for the hold to expire...")
    if wait_for("OFF", 75):
        print("PASS: light turned OFF after the hold")
    else:
        print("FAIL: no OFF within 75s")
        failures += 1
else:
    print("skipped OFF-timeout check (add --wait-off to include it)")

client.loop_stop()
print(f"{'ALL CHECKS PASSED' if failures == 0 else f'{failures} FAILURE(S)'}")
sys.exit(1 if failures else 0)
```

- [ ] **Step 2: Plumbing test against the live broker (flow NOT yet deployed)**

```bash
SP=/private/tmp/claude-501/-path-to-rd03d/1a58ef3a-b659-4aae-a07a-3f6d1a6f573b/scratchpad
cd node-red && $SP/venv/bin/python test_stair_flow.py 192.168.1.243
```

Expected (this is the correct pre-import outcome): connects, publishes, then `FAIL: no ON within 5s - is the flow deployed...`, exit code 1. That failure proves the harness's broker connectivity, publish path, and reporting all work; the PASS outcomes become reachable only after the user imports the flow.

- [ ] **Step 3: Commit**

```bash
git add node-red/test_stair_flow.py
git commit -m "feat(stair-light): acceptance harness for the Node-RED flow"
```

---

### Task 3: README + user handoff

**Files:**
- Create: `node-red/README.md`

- [ ] **Step 1: Write the README**

`node-red/README.md`:

```markdown
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

## Behavior notes

- Any in-zone target (any of the 3 tracking slots) keeps the light on; the
  60 s hold restarts on each event.
- `{"gone":true}` and radar silence are both simply inactivity — the hold
  timer is the single source of truth for turning off.
- `rd03d/status` appears in the debug sidebar for sensor health but never
  drives the light: if the sensor dies while the light is on, the hold
  expires and the light turns off on its own.
```

- [ ] **Step 2: Commit**

```bash
git add node-red/README.md
git commit -m "docs(stair-light): import, configure, and tuning instructions"
```

- [ ] **Step 3: User handoff (user-owned, report as pending)**

The user imports the flow, renames the device topic, runs the harness (expect
ALL CHECKS PASSED with `--wait-off`), then does the zone-tuning walk test.
The plan is complete when the code/docs land; the import + walk test remain
with the user.
