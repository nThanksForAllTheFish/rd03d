"""Place the real EKMC1603111 in the back plate's PIR socket and check interference.

Run with:  python3 run_fusion.py script 91_pir_fit.py

Imports Panasonic's STEP of the sensor, drops it upright into the socket
exactly as 02_backplate.py step 14 defines it (axis at (pirCx, 0) along +Z,
lens ring top flush with the shell's face at z 16), snapshots the placement
and runs Fusion's interference analysis between the sensor, the plate, the
shell (its pod box) and the plug. Expected: the plug's designed press-fit
annulus against the plate is the ONLY pair; anything involving the sensor
is a failure. If it is not clean, fix the SOCKET in 02_backplate.py or the
BOX in 03_shell.py, never the sensor.
"""
import math

import adsk.core
import adsk.fusion

# Local vendor download, gitignored (case/models/ is not redistributed).
SENSOR = "/path/to/rd03d/case/models/EKMC1603111.STEP"  # local vendor download, gitignored; run_fusion.py fills in the checkout root
SENSOR_PREFIXES = ("EKMC", "PaPIRs")

# Sensor native frame: Z is the lens axis, z = 0 the metal base. Its lens
# base ring top (z 8.4 mm) sits on the shell's front face plane (z 16), so
# the flange's underside (z 6.4) lands on the socket boss's top rim
# (pirSeatZ 14.0) and the can's underside (z -0.9) at the plug's rim (6.7).
RING_TOP_Z = 0.84   # cm, sensor frame


def p(des, name):
    return des.userParameters.itemByName(name).value  # cm


def all_bodies(occ):
    bodies = list(occ.bRepBodies)
    for child in occ.childOccurrences:
        bodies.extend(all_bodies(child))
    return bodies


def occ_bbox(occ):
    bb = None
    for body in all_bodies(occ):
        b = body.boundingBox
        if bb is None:
            bb = adsk.core.BoundingBox3D.create(b.minPoint.copy(),
                                                b.maxPoint.copy())
        else:
            bb.combine(b)
    return bb


def show_bbox(tag, bb):
    print("%s bbox(mm): x %.2f..%.2f  y %.2f..%.2f  z %.2f..%.2f" %
          (tag, bb.minPoint.x * 10, bb.maxPoint.x * 10, bb.minPoint.y * 10,
           bb.maxPoint.y * 10, bb.minPoint.z * 10, bb.maxPoint.z * 10))


def find_occ(root, prefixes):
    for occ in root.occurrences:
        if occ.component.name.startswith(prefixes):
            return occ
    return None


def run(_context: str):
    app = adsk.core.Application.get()
    des = adsk.fusion.Design.cast(app.activeProduct)
    root = des.rootComponent

    for occ in list(root.occurrences):
        if occ.component.name.startswith(SENSOR_PREFIXES):
            name = occ.name
            occ.deleteMe()
            print("removed prior import:", name)

    # --- socket frame, exactly as 02_backplate.py step 14 computes it: the
    # axis is upright (pirTilt 0) at (pirCx, 0); the sensor's ring top is
    # flush with the shell's face ---
    intD, wall = p(des, "intD"), p(des, "wall")
    pirCx = p(des, "pirCx")
    if abs(p(des, "pirTilt")) > 1e-9:
        raise RuntimeError("pirTilt is not 0; this script places the sensor upright")
    zTop = intD + wall                                       # 16
    origin_z = zTop - RING_TOP_Z                             # 7.6
    seatZ = p(des, "pirSeatZ")                               # 14.0: boss top
    front_pt = adsk.core.Point3D.create(pirCx, 0.0, zTop)

    imp = app.importManager
    before = root.occurrences.count
    imp.importToTarget(imp.createSTEPImportOptions(SENSOR), root)
    if root.occurrences.count != before + 1:
        raise RuntimeError("STEP import added %d occurrences, expected 1"
                           % (root.occurrences.count - before))
    sensor = root.occurrences.item(before)
    print("imported:", sensor.name, "| component:", sensor.component.name,
          "| bodies:", len(all_bodies(sensor)))
    if not sensor.component.name.startswith(SENSOR_PREFIXES):
        print("NOTE: component name does not match SENSOR_PREFIXES; "
              "02_backplate.py and this script will not auto-delete it")
    show_bbox("sensor native", occ_bbox(sensor))

    # No rotation: model +Z = case +Z. Translate the model's origin (the
    # metal base plane) to (pirCx, 0, zTop - RING_TOP_Z).
    m = adsk.core.Matrix3D.create()
    m.translation = adsk.core.Vector3D.create(pirCx, 0.0, origin_z)
    sensor.transform2 = m
    if des.snapshots.hasPendingSnapshot:
        des.snapshots.add()
    bb = occ_bbox(sensor)
    show_bbox("sensor placed", bb)
    print("axis at x %.2f; sensor origin z %.2f; ring top on the face z %.1f; "
          "lens apex should be ~%.1f mm proud (bbox top %.2f)"
          % (pirCx * 10, origin_z * 10, zTop * 10, (1.929 - RING_TOP_Z) * 10,
             bb.maxPoint.z * 10))

    sbody = all_bodies(sensor)[0]
    IN = adsk.fusion.PointContainment.PointInsidePointContainment

    def sensor_solid(z, r, ang=0.0):
        """Sensor material at case z, radius r from the axis, azimuth ang (deg)."""
        a = math.radians(ang)
        pt = adsk.core.Point3D.create(pirCx + r * math.cos(a), r * math.sin(a), z)
        return sbody.pointContainment(pt) == IN

    # --- flange on the boss rim: pirSeatZ must be the flange's underside.
    # Probe the sensor at the rim's bearing radius (between the bore and the
    # boss's outer radius) 0.3 mm above and below the seat, away from the
    # two latch tabs (45/225 deg).
    rimR = (p(des, "pirBoreR") + p(des, "pirSocketR")) / 2
    if not sensor_solid(seatZ + 0.03, rimR, 135.0):
        raise RuntimeError("no flange 0.3 mm above pirSeatZ (z %.2f) at r %.2f"
                           % (seatZ * 10, rimR * 10))
    if sensor_solid(seatZ - 0.03, rimR, 135.0):
        raise RuntimeError("sensor body 0.3 mm below pirSeatZ at r %.2f: it would not "
                           "seat on the boss rim" % (rimR * 10))
    print("flange underside at z %.1f bears on the boss rim (r %.2f) ok" % (seatZ * 10, rimR * 10))

    # --- plug seat: pirSeatD (shared with 02_backplate.py, which parks the
    # plug's front rim there) must be the base's underside. Probe the sensor
    # 0.5 mm either side of it, at a radius inside the rim's bearing annulus.
    seatD = p(des, "pirSeatD")
    plugZ = zTop - seatD
    plugRimR = (p(des, "pirPlugID") + p(des, "pirPlugOD")) / 4
    if not sensor_solid(plugZ + 0.05, plugRimR):
        raise RuntimeError("no sensor base 0.5 mm in front of pirSeatD (z %.2f) at r %.1f"
                           % (plugZ * 10, plugRimR * 10))
    if sensor_solid(plugZ - 0.05, plugRimR):
        raise RuntimeError("sensor body behind pirSeatD at r %.1f: the plug "
                           "rim would clash" % (plugRimR * 10))
    print("plug rim at z %.1f bears on the base underside (r %.1f) ok"
          % (plugZ * 10, plugRimR * 10))

    # --- keeper pin (2026-10-25): the cross-hole at pirPinZ crosses the bore
    # behind the plug; the sensor (pins end at case z 2.1) must not reach
    # it, or the filament stub would go through the sensor. Probed on the
    # axis and on the r 2.5 pin circle where the pin hole passes (y 0).
    pinZ = p(des, "pirPinZ")
    for r, ang in ((0.0, 0.0), (0.25, 0.0), (0.25, 180.0)):
        if sensor_solid(pinZ, r, ang):
            raise RuntimeError("sensor body at the keeper pin level z %.2f (r %.1f): "
                               "the pin would go through the sensor" % (pinZ * 10, r * 10))
    print("keeper pin at z %.2f clear of the sensor ok" % (pinZ * 10))

    # --- interference: sensor vs plate (the socket), shell (its pod box and
    # lens hole) and the plug parked in the bore ---
    plate = find_occ(root, ("BackPlate",))
    shell = find_occ(root, ("FrontShell",))
    plug = find_occ(root, ("PirPlug",))
    ents = adsk.core.ObjectCollection.create()
    for b in all_bodies(sensor):
        ents.add(b)
    for b in all_bodies(plate):
        ents.add(b)
    for b in all_bodies(shell):
        ents.add(b)
    if plug:
        for b in all_bodies(plug):
            ents.add(b)
    print("interference check over", ents.count, "bodies")
    # Since 2026-10-25 the plug's OD (12.1) is larger than the bore (11.8)
    # on purpose, to come out as a press fit on a printer whose outside
    # walls print 0.2 under. The parked plug therefore overlaps the PLATE
    # (which carries the bore) by a thin annulus: that one pair is
    # expected, and is only checked to be no bigger than the full annulus
    # (anything larger means the plug is hitting something other than the
    # bore wall). Any pair involving the sensor, or the plate against the
    # shell, is a failure.
    odR, boreR, plugL = p(des, "pirPlugOD") / 2, p(des, "pirBoreR"), p(des, "pirPlugL")
    press_max = math.pi * max(odR * odR - boreR * boreR, 0.0) * plugL   # cm^3, slot ignored
    inp = des.createInterferenceInput(ents)
    res = des.analyzeInterference(inp)
    total = 0.0
    bad = 0
    for i in range(res.count):
        r = res.item(i)
        c1 = r.entityOne.parentComponent.name
        c2 = r.entityTwo.parentComponent.name
        body = r.interferenceBody
        vol = body.volume if body else -1.0
        total += max(vol, 0.0)
        names = {c1, c2}
        press_fit = (any(n.startswith("PirPlug") for n in names)
                     and any(n.startswith("BackPlate") for n in names)
                     and not any(n.startswith(SENSOR_PREFIXES) for n in names))
        if press_fit and 0 <= vol <= press_max * 1.02:
            print("press fit: %.2f mm^3 between %s and %s (designed annulus "
                  "<= %.2f mm^3), expected" % (vol * 1000, c1, c2, press_max * 1000))
            continue
        bad += 1
        line = "INTERFERENCE: %.4f mm^3 between %s and %s" % (vol * 1000, c1, c2)
        if body:
            ib = body.boundingBox
            line += ("; world bbox x %.1f..%.1f y %.1f..%.1f z %.1f..%.1f mm"
                     % (ib.minPoint.x * 10, ib.maxPoint.x * 10,
                        ib.minPoint.y * 10, ib.maxPoint.y * 10,
                        ib.minPoint.z * 10, ib.maxPoint.z * 10))
            line += ("; sensor-frame z %.1f..%.1f mm"
                     % ((ib.minPoint.z - origin_z) * 10, (ib.maxPoint.z - origin_z) * 10))
        print(line)
    print("interference pairs: %d (%d unexpected), total volume %.4f mm^3"
          % (res.count, bad, total * 1000))
    if bad == 0:
        print("PIR FIT OK")
