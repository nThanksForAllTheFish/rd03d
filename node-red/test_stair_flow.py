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
