"""Place the real EKMC1603111 in the back plate's PIR socket and check interference.

Run with:  python3 run_fusion.py script 91_pir_fit.py

Imports Panasonic's STEP of the sensor, drops it upright into the socket
exactly as 02_backplate.py step 14 defines it (axis at (pirCx, 0) along +Z,
lens ring top flush with the shell's face at z 16), snapshots the placement
and runs Fusion's interference analysis between the sensor, the plate, the
shell (its pod box) and the bezel ring parked in the lens gap clocked to
the lens tabs. Expected (Task 9e): ONE pair, the plate against the shell,
because the measured fit allowances (rimGapY, wingGap) are negative: the
model's plate and wing sit into the shell's long walls by what the print
shrinks, bounded by those slabs. Anything else (sensor against anything,
bezel against anything) is a failure. If it is not clean, fix
the SOCKET in 02_backplate.py or the BOX / BEZEL in 03_shell.py, never the
sensor.
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
# (pirSeatZ 14.0); the pins (to z -5.5) and the cap on them (to about
# -8.5) hang in the blind bore above its floor (case z -2).
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

    # --- bore floor: the blind bore ends at the wing top (z -2); nothing
    # of the sensor may reach it (the pins end at z 2.1, the cap on them
    # at about -0.9, which is not in the STEP). Probed on the axis and on
    # the r 2.5 pin circle 0.3 above the floor.
    floorZ = -p(des, "backT") + 0.6
    for r, ang in ((0.0, 0.0), (0.25, 0.0), (0.25, 180.0)):
        if sensor_solid(floorZ + 0.03, r, ang):
            raise RuntimeError("sensor body 0.3 mm above the bore floor z %.1f (r %.1f): it "
                               "would stand on the floor, not seat on the rim" % (floorZ * 10, r * 10))
    print("bore floor at z %.1f clear of the sensor ok" % (floorZ * 10))

    # --- bezel ring fitted state (parked by 03_shell.py step 8 at (pirCx,
    # 0, zTop) turned to the lens tabs): flange on the face, skirt in the
    # hole round the lens ring, the tabs in its notches, probed in the
    # case frame through the occurrence's body proxies; then the ring's
    # clearance to the lens ring / dome flank by bisection at eight
    # azimuths away from the tabs
    plate = find_occ(root, ("BackPlate",))
    shell = find_occ(root, ("FrontShell",))
    bezel = find_occ(root, ("PirBezel",))
    if bezel is None:
        raise RuntimeError("no PirBezel occurrence: run 03_shell.py first")
    bzb, shb = all_bodies(bezel)[0], all_bodies(shell)[0]

    def solid_at(body, r, ang, z):
        a = math.radians(ang)
        return body.pointContainment(adsk.core.Point3D.create(
            pirCx + r * math.cos(a), r * math.sin(a), z)) == IN

    intD = p(des, "intD")
    flangeR, flangeT = p(des, "pirBezelFlangeR"), p(des, "pirBezelFlangeT")
    innerR, skirtH, lensR = p(des, "pirBezelInnerR"), p(des, "pirBezelSkirtH"), p(des, "pirHoleR")
    TAB = (45.0, 225.0)                                        # the tabs (STEP probe; sensor unrotated)
    AWAY = (0.0, 90.0, 135.0, 180.0, 270.0, 315.0)
    rs = (innerR + lensR) / 2
    probes = []
    for ang in TAB:
        probes += [(sbody, True, 1.08, ang, zTop - 0.1, "lens tab at %.0f deg (r 10.8, z 15.9)" % ang),
                   (bzb, False, rs, ang, zTop - skirtH / 2, "bezel skirt notch over the tab at %.0f" % ang),
                   (bzb, False, rs, ang, zTop + flangeT / 2, "bezel flange notch over the tab at %.0f" % ang),
                   (bzb, True, (lensR - 0.02 + flangeR) / 2, ang, zTop + flangeT / 2, "bezel flange bridge over the notch at %.0f" % ang)]
    for ang in AWAY:
        probes += [(bzb, True, rs, ang, zTop - skirtH / 2, "bezel skirt in the hole at %.0f" % ang),
                   (shb, False, rs, ang, zTop - skirtH / 2, "hole open round the skirt at %.0f" % ang),
                   (shb, True, lensR + 0.02, ang, zTop - skirtH / 2, "hole wall outside the skirt at %.0f" % ang),
                   (bzb, True, (lensR + flangeR) / 2, ang, zTop + flangeT / 2, "bezel flange on the face at %.0f" % ang),
                   (shb, True, (lensR + flangeR) / 2, ang, zTop - 0.01, "shell face under the flange at %.0f" % ang),
                   (sbody, False, innerR - 0.003, ang, zTop - skirtH / 2, "sensor clear of the skirt's ID at %.0f (z 15)" % ang),
                   (sbody, False, innerR - 0.003, ang, zTop + flangeT / 2, "sensor clear of the flange's ID at %.0f (z 16.4)" % ang)]
    for body, want, r, ang, z, label in probes:
        if solid_at(body, r, ang, z) != want:
            raise RuntimeError("bezel fit probe '%s' at (r %.2f, %.0f deg, z %.2f): expected %s"
                               % (label, r * 10, ang, z * 10, "solid" if want else "void"))
    # minimum radial clearance between the sensor (lens ring, dome flank)
    # and the bezel's bore, by bisection of the sensor's outer radius
    min_clear, where = 9.9, None
    for ang in AWAY:
        for z in (zTop - skirtH + 0.05, zTop - skirtH / 2, zTop - 0.05, zTop + 0.05, zTop + flangeT / 2, zTop + flangeT - 0.05):
            lo, hi = 0.9, innerR + 0.1
            if not sensor_solid(z, lo, ang):
                raise RuntimeError("no sensor at r 9 at %.0f deg z %.2f" % (ang, z * 10))
            for _ in range(24):
                mid = (lo + hi) / 2
                if sensor_solid(z, mid, ang):
                    lo = mid
                else:
                    hi = mid
            c = innerR - lo
            if c < min_clear:
                min_clear, where = c, (ang, z)
    print("bezel fitted: flange on the face, skirt in the hole, tabs at %s deg in the notches; "
          "sensor-to-bezel bore minimum clearance %.3f mm (at %.0f deg, z %.2f)"
          % ("/".join("%.0f" % a for a in TAB), min_clear * 10, where[0], where[1] * 10))
    # (0.05 designed at the dome flank just above the ring, pirBezelInnerR)
    if min_clear < 0.003:
        raise RuntimeError("bezel bore under 0.03 mm from the sensor")

    # --- interference: sensor vs plate (the socket), shell (its pod box
    # and lens hole) and the bezel ring in the gap ---
    ents = adsk.core.ObjectCollection.create()
    for b in all_bodies(sensor):
        ents.add(b)
    for b in all_bodies(plate):
        ents.add(b)
    for b in all_bodies(shell):
        ents.add(b)
    for b in all_bodies(bezel):
        ents.add(b)
    print("interference check over", ents.count, "bodies")
    # Task 9e: the bezel ring touches neither the sensor nor the shell in
    # the model (0.10 to the lens ring, 0.05 to the dome flank, the skirt's
    # OD exactly the hole's radius: the print's shrink makes the push
    # fit). Any pair involving the bezel is a failure.
    # Fit allowances (02 ensure_params, calipers 2026-10-25): rimGapY and
    # wingGap are NEGATIVE, so in the MODEL the plate's +/-Y edges sit
    # 0.2 a side into the shell's long walls and the wing 0.12 a side
    # into the box walls (the print's measured shrink takes it back to
    # 0.1 a side of gap). That plate/shell pair is therefore expected
    # too, bounded by those slabs: the plate (z -8..0) and the two radar
    # fence walls that reach the outline (1.5 thick, z 0..11) along both
    # +/-Y edges, and the wing (z -8..-2) along both its faces; +5% for
    # the probe's own tolerance. Anything bigger means the parts meet
    # somewhere they should not.
    intW, intH, backT = p(des, "intW"), p(des, "intH"), p(des, "backT")
    gX, gY, gW = p(des, "rimGapX"), p(des, "rimGapY"), p(des, "wingGap")
    boxHalfX = p(des, "pirBoxHalfX")
    fit_max = 0.0
    if gY < 0:
        fit_max += 2 * (-gY) * ((intW - 2 * gX) * backT + 2 * 0.15 * 1.1)
    if gW < 0:
        fit_max += 2 * (-gW) * ((pirCx + boxHalfX - gX) - (intW / 2 - gX)) * 0.6
    if gX < 0:
        fit_max += 2 * (-gX) * (intH - 2 * gY) * backT
    fit_max *= 1.05
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
        fit = (any(n.startswith("BackPlate") for n in names)
               and any(n.startswith("FrontShell") for n in names))
        if fit and 0 <= vol <= fit_max:
            print("fit allowance: %.2f mm^3 between %s and %s (designed plate/wing overlap "
                  "into the shell's walls, bound %.1f mm^3), expected" % (vol * 1000, c1, c2, fit_max * 1000))
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
