"""Place the real EKMC1603111 in the back plate's PIR pod and check interference.

Run with:  python3 run_fusion.py script 91_pir_fit.py

Imports Panasonic's STEP of the sensor, seats it in the pod exactly as
02_backplate.py step 14 defines the pod tower (recomputed from the same
parameters), snapshots the placement and runs Fusion's interference analysis
between the sensor, the plate, the shell and the plug. Expected: the plug's
designed press-fit annulus against the plate is the ONLY pair; anything
involving the sensor is a failure. If it is not clean, fix the POD in
02_backplate.py, never the sensor.
"""
import math

import adsk.core
import adsk.fusion

# Local vendor download, gitignored (case/models/ is not redistributed).
SENSOR = "/path/to/rd03d/case/models/EKMC1603111.STEP"  # local vendor download, gitignored; run_fusion.py fills in the checkout root
SENSOR_PREFIXES = ("EKMC", "PaPIRs")

# Sensor native frame: Z is the lens axis, z = 0 the metal base. Its lens
# base ring top (z 8.4 mm) sits on the pod's front face plane.
SEAT_Z = 0.84   # cm


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

    # --- pod frame, exactly as 02_backplate.py step 14 computes it: the
    # tower stands on the plate's wing 0.3 mm outside the shell's +X wall,
    # its top face flush with the shell's front face ---
    intW, intD = p(des, "intW"), p(des, "intD")
    wall, backT = p(des, "wall"), p(des, "backT")
    recessR, podWall = p(des, "pirRecessR"), p(des, "pirPodWall")
    tilt = p(des, "pirTilt") if p(des, "pirTilt") < 1.6 else math.radians(p(des, "pirTilt"))
    sgn = 1.0 if p(des, "pirTiltSign") >= 0 else -1.0
    POD_GAP = 0.03                      # cm, tower to shell wall (02 step 14)
    xTow0 = intW / 2 + wall + POD_GAP   # tower's -X face, 23.3
    zTop = intD + wall
    depth = zTop + backT
    podW = 2 * (recessR + podWall) + depth * math.tan(tilt)
    podCx = xTow0 + podW / 2
    front_pt = adsk.core.Point3D.create(podCx, 0.0, zTop)

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
              "03_shell.py and this script will not auto-delete it")
    show_bbox("sensor native", occ_bbox(sensor))

    # Rotation about Y so the model's +Z (lens axis) tips toward +X by tilt
    # (sgn = +1). The sign of Fusion's rotation is checked numerically
    # rather than assumed: whichever sign sends (0,0,1) to +x*sgn wins.
    yaxis = adsk.core.Vector3D.create(0, 1, 0)
    origin = adsk.core.Point3D.create(0, 0, 0)
    rot = None
    for ang in (sgn * tilt, -sgn * tilt):
        m = adsk.core.Matrix3D.create()
        m.setToRotation(ang, yaxis, origin)
        v = adsk.core.Vector3D.create(0, 0, 1)
        v.transformBy(m)
        if v.x * sgn > 0:
            rot = m
            print("rotation about Y by %+.1f deg tips +Z toward %s"
                  % (math.degrees(ang), "+X" if sgn > 0 else "-X"))
            break
    if rot is None:
        raise RuntimeError("neither rotation sign about Y tips the sensor's "
                           "+Z toward %+.0fX; check pirTilt/pirTiltSign"
                           % sgn)
    # translate so the model's (0, 0, SEAT_Z) lands on the front-face axis point
    seat = adsk.core.Point3D.create(0, 0, SEAT_Z)
    seat.transformBy(rot)
    rot.translation = adsk.core.Vector3D.create(front_pt.x - seat.x,
                                                front_pt.y - seat.y,
                                                front_pt.z - seat.z)
    sensor.transform2 = rot
    if des.snapshots.hasPendingSnapshot:
        des.snapshots.add()
    bb = occ_bbox(sensor)
    show_bbox("sensor placed", bb)
    print("front-face axis point (mm): x %.2f z %.2f; lens apex should be "
          "~%.1f mm proud of z=%.1f" % (front_pt.x * 10, front_pt.z * 10,
                                        (1.929 - SEAT_Z) * 10 * math.cos(tilt),
                                        zTop * 10))

    # --- plug seat: pirSeatD (shared with 02_backplate.py, which parks the plug's
    # front rim there) must be the base's underside. Probe the sensor body
    # 0.5 mm either side of it, at a radius inside the rim's bearing annulus.
    seatD = p(des, "pirSeatD")
    ax = adsk.core.Vector3D.create(sgn * math.sin(tilt), 0, math.cos(tilt))
    rimR = (p(des, "pirPlugID") + p(des, "pirPlugOD")) / 4
    sbody = all_bodies(sensor)[0]
    IN = adsk.fusion.PointContainment.PointInsidePointContainment
    def sensor_solid(d, side):
        pt = adsk.core.Point3D.create(front_pt.x - ax.x * d, side,
                                      front_pt.z - ax.z * d)
        return sbody.pointContainment(pt) == IN
    if not sensor_solid(seatD - 0.05, rimR):
        raise RuntimeError("no sensor base 0.5 mm in front of pirSeatD at r %.1f"
                           % (rimR * 10))
    if sensor_solid(seatD + 0.05, rimR):
        raise RuntimeError("sensor body behind pirSeatD at r %.1f: the plug "
                           "rim would clash" % (rimR * 10))
    print("plug rim at d %.1f bears on the base underside (r %.1f) ok"
          % (seatD * 10, rimR * 10))

    # --- keeper pin (2026-10-25): the cross-hole at pirPinD crosses the bore
    # behind the plug; the sensor (pins end at d 13.9) must not reach it, or
    # the filament stub would go through the sensor. Probed on the axis and
    # on the r 2.5 pin circle, where the pin hole passes at y 0.
    pinD = p(des, "pirPinD")
    for side in (0.0, 0.25, -0.25):
        if sensor_solid(pinD, side):
            raise RuntimeError("sensor body at the keeper pin axis point d %.2f "
                               "(y %.1f): the pin would go through the sensor"
                               % (pinD * 10, side * 10))
    print("keeper pin at d %.2f clear of the sensor ok" % (pinD * 10))

    # --- interference: sensor vs plate (the pod), shell (its notched +X
    # wall is 0.3 mm from the tower) and the plug parked in the bore ---
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
    # (which carries the bore since the pod moved to its wing) by a thin
    # annulus: that one pair is expected, and is only checked to be no
    # bigger than the full annulus (anything larger means the plug is
    # hitting something other than the bore wall). Any pair involving the
    # sensor, or the plate against the shell, is a failure.
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
            # approximate sensor-frame z range: bbox corners projected on
            # the bore axis (d), then z = SEAT_Z - d
            ax = adsk.core.Vector3D.create(sgn * math.sin(tilt), 0, math.cos(tilt))
            zs = []
            for cx in (ib.minPoint.x, ib.maxPoint.x):
                for cz in (ib.minPoint.z, ib.maxPoint.z):
                    d = (front_pt.x - cx) * ax.x + (front_pt.z - cz) * ax.z
                    zs.append((SEAT_Z - d) * 10)
            line += "; approx sensor-frame z %.1f..%.1f mm" % (min(zs), max(zs))
        print(line)
    print("interference pairs: %d (%d unexpected), total volume %.4f mm^3"
          % (res.count, bad, total * 1000))
    if bad == 0:
        print("PIR FIT OK")
