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

for n in nodes:
    if n["type"] in ("mqtt in", "mqtt out") and n.get("broker") not in by_id:
        fail(f"mqtt node {n['id']} references missing broker config")

tgt_in = one("mqtt in", lambda n: n.get("topic") == "rd03d/target/+", "(targets)")
status_in = one("mqtt in", lambda n: n.get("topic") == "rd03d/status", "(status)")

zone = one("function")
for needle in ("const ZONE", "JSON.parse", "gone", "xMin", "yMax"):
    if needle not in zone["func"]:
        fail(f"zone filter missing '{needle}'")

trig = one("trigger")
if not (trig["op1"] == "ON" and trig["op2"] == "OFF" and trig["extend"] is True
        and str(trig["duration"]) == "60" and trig["units"] == "s"
        and trig["bytopic"] == "all"):
    fail("trigger must be ON, then OFF after 60s, extend on retrigger, bytopic=all")

rbe = one("rbe")
if rbe.get("septopics") is not False:
    fail("rbe must have septopics=false (single stream across target topics)")

change = one("change")
rule = change["rules"][0]
if not (rule["t"] == "set" and rule["p"] == "topic"
        and rule["to"] == "cmnd/stairlight/POWER"):
    fail("change node must SET msg.topic to cmnd/stairlight/POWER")

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

spine = [tgt_in, zone, trig, rbe, change, out]
for a, b in zip(spine, spine[1:]):
    if not wired(a, b):
        fail(f"{a['type']} not wired to {b['type']}")
for inj in injects:
    if not wired(inj, change):
        fail("inject buttons must wire into the change node")

dbg_zone = next(n for n in debugs if n["name"] == "in-zone events")
dbg_stat = next(n for n in debugs if n["name"] == "sensor status")
if not wired(zone, dbg_zone):
    fail("zone filter must also wire to the in-zone debug tap")
if not wired(status_in, dbg_stat):
    fail("status mqtt in must wire to the sensor status debug")

print("flow validation passed")
