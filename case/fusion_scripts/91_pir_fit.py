"""Place the real EKMC1603111 in the back plate's PIR socket and check interference.

Run with:  python3 run_fusion.py script 91_pir_fit.py

Imports Panasonic's STEP of the sensor, drops it upright into the socket
exactly as 02_backplate.py step 14 defines it (axis at (pirCx, 0) along +Z,
lens ring top flush with the shell's face at z 16), snapshots the placement
and runs Fusion's interference analysis between the sensor, the plate, the
shell (its pod box) and the bezel parked on the face in its fitted (turned)
position. Expected (Task 9d): the bezel's lip against the dome - the
designed pirBezelPreload interference ring, bounded by the band volume -
and, since the measured fit allowances (rimGapY, wingGap negative), the
plate against the shell: the model's plate and wing sit into the shell's
long walls by what the print shrinks, bounded by those slabs. Anything
else (sensor against plate or shell, bezel against plate or shell) is a
failure. If it is not clean, fix
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

    # --- the dome where the bezel's lip meets it: the sphere R pirDomeR
    # centred on the axis at the face must be the STEP's dome. Probe 0.1
    # inside and outside the sphere at the lip radius, at four azimuths.
    domeR, lipR = p(des, "pirDomeR"), p(des, "pirBezelLipR")
    domeZ = zTop + math.sqrt(domeR * domeR - lipR * lipR)       # 18.888
    for ang in (0.0, 90.0, 180.0, 270.0):
        if not sensor_solid(domeZ - 0.01, lipR, ang):
            raise RuntimeError("no dome 0.1 mm under the sphere at r %.1f, %.0f deg (z %.3f): "
                               "pirDomeR is wrong" % (lipR * 10, ang, (domeZ - 0.01) * 10))
        if sensor_solid(domeZ + 0.01, lipR, ang):
            raise RuntimeError("dome 0.1 mm above the sphere at r %.1f, %.0f deg: pirDomeR is wrong"
                               % (lipR * 10, ang))
    print("dome surface at r %.1f is z %.3f (sphere R %.2f at the face) ok" % (lipR * 10, domeZ * 10, domeR * 10))

    # --- bezel fitted state (parked by 03_shell.py step 8 at (pirCx, 0,
    # zTop), lugs at the rest angles): flange on the face, lugs 0.3 under
    # the top's underside and clear of the box walls, probed in the case
    # frame through the occurrence's body proxies
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
    lugRo, skirtRo = p(des, "pirLugRo"), p(des, "pirBezelSkirtRo")
    lugT, skirtH = p(des, "pirLugT"), p(des, "pirBezelSkirtH")
    lugTop = zTop - skirtH + lugT                             # 13.7
    lugMid = zTop - skirtH + lugT / 2                         # 12.95
    rLug = (skirtRo + lugRo) / 2                              # 13.45
    REST = (90.0, 210.0, 330.0)
    probes = []
    for ang in REST:
        probes += [(bzb, True, rLug, ang, lugMid, "bezel lug at the rest angle %.0f" % ang),
                   (bzb, False, rLug, ang, lugTop + 0.015, "nothing of the bezel 0.15 above its lug top at %.0f" % ang),
                   (shb, False, rLug, ang, intD - 0.015, "shell void 0.15 under its top at the lug's rest position %.0f" % ang),
                   (shb, False, rLug, ang, lugMid, "shell void at the lug's rest position %.0f" % ang),
                   (shb, True, rLug, ang, intD + 0.02, "shell top solid over the parked lug at %.0f" % ang),
                   (shb, False, lugRo + 0.02, ang, lugMid, "box cavity open 0.2 past the lug's reach at %.0f" % ang)]
        probes += [(bzb, False, rLug, ang - 30.0, lugMid, "no bezel lug at the notch angle %.0f (turned away)" % (ang - 30.0))]
    probes += [(shb, True, 1.4, 0.0, zTop - 0.01, "shell face solid under the bezel flange (r 14)"),
               (bzb, True, 1.4, 0.0, zTop + 0.06, "bezel flange on the face (r 14, 0.6 up)"),
               (bzb, False, 1.4, 0.0, zTop - 0.01, "nothing of the bezel below the face at r 14"),
               (bzb, True, 1.2, 0.0, intD + 0.1, "bezel skirt inside the lens hole (r 12, z 15)"),
               (shb, False, 1.2, 0.0, intD + 0.1, "lens hole open round the skirt (r 12, z 15)")]
    for body, want, r, ang, z, label in probes:
        if solid_at(body, r, ang, z) != want:
            raise RuntimeError("bezel fit probe '%s' at (r %.2f, %.0f deg, z %.2f): expected %s"
                               % (label, r * 10, ang, z * 10, "solid" if want else "void"))
    print("bezel fitted: flange on the face, lugs at %s deg %.2f under the top, clear of the "
          "box walls ok" % ("/".join("%.0f" % a for a in REST), (intD - lugTop) * 10))

    # --- interference: sensor vs plate (the socket), shell (its pod box,
    # lens hole and notches) and the bezel parked on the face ---
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
    # Task 9d: the bezel's lip is built pirBezelPreload (0.2) into the dome
    # on purpose (03_shell.py step 8), so ONE pair is expected: bezel
    # against sensor, and only as big as that band can be. Bound: the
    # radial interference 0.2 on a ring of radius pirBezelLipR over a
    # contact height of about 2 sqrt(2 R d) (the chord of a sphere R at
    # depth d): 2 pi 10.5 x 0.2 x 4.2 = 55 mm^3. (The real lip is a cone
    # meeting the sphere at an angle, so the measured value is far
    # smaller; it is printed.) Any other pair is a failure.
    preload = p(des, "pirBezelPreload")
    band_max = 2 * math.pi * lipR * preload * 2 * math.sqrt(2 * domeR * preload)
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
        lip = (any(n.startswith("PirBezel") for n in names)
               and any(n.startswith(SENSOR_PREFIXES) for n in names))
        fit = (any(n.startswith("BackPlate") for n in names)
               and any(n.startswith("FrontShell") for n in names))
        if fit and 0 <= vol <= fit_max:
            print("fit allowance: %.2f mm^3 between %s and %s (designed plate/wing overlap "
                  "into the shell's walls, bound %.1f mm^3), expected" % (vol * 1000, c1, c2, fit_max * 1000))
            continue
        if lip and 0 <= vol <= band_max:
            line = ("lip preload: %.3f mm^3 between %s and %s (band bound %.1f mm^3), expected"
                    % (vol * 1000, c1, c2, band_max * 1000))
            if body:
                ib = body.boundingBox
                line += ("; z %.3f..%.3f, r to %.3f mm"
                         % (ib.minPoint.z * 10, ib.maxPoint.z * 10,
                            max(abs(ib.minPoint.x - pirCx), abs(ib.maxPoint.x - pirCx)) * 10))
            print(line)
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
