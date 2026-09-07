import math

import adsk.core
import adsk.fusion

RADAR = "/Users/me/Downloads/rd-03d-sensor-1/RD-03D.step"
XIAO = ("/Users/me/Downloads/seeed-studio-xiao-esp32-c6-1/"
        "Seeed Studio XIAO ESP32-C6.step")

# --- Orientation config (iterated visually; see plan Task 5 Step 2) ---
# Radar native frame: X = board width (15.1), Y = thickness (patch on a +/-Y
# face), Z = stick long axis (44.0).  A +/-90 deg rotation about X maps the
# long axis onto case Y and the thickness onto case Z:
#   +90 about X: (x,y,z) -> (x,-z,y)   native +Y face ends up facing +Z
#   -90 about X: (x,y,z) -> (x,z,-y)   native -Y face ends up facing +Z
# An optional extra 180 about Z keeps the same face up but swaps which stick
# end points to case +Y (and mirrors X, which is fine - we recenter X anyway).
RADAR_XROT_DEG = 90       # +90 or -90: which native Y face becomes +Z
# Verified by face probing: with +90 the PCB sits at the top of the
# thickness (patch pads at z=13.0, connector hanging down to z=6.65), so
# the patch side faces +Z.  The 5-pin connector footprint landed at the
# +Y end, i.e. the antenna end was at -Y, so flip the stick 180 about Z
# to put the antenna end under the window at y 1..25.
RADAR_FLIP180 = True      # True: also rotate 180 about Z (swap stick ends)

# XIAO native frame: X = long axis w/ USB overhang at +X, Y = thickness
# (components/USB on +Y side), Z = board short axis.  Rotation about X keeps
# USB pointing +X; +90 puts native +Y (component side) up.
XIAO_XROT_DEG = 90


def p(des, name):
    return des.userParameters.itemByName(name).value  # cm


def all_bodies(occ):
    """All body proxies under an occurrence, recursing into sub-assemblies."""
    bodies = list(occ.bRepBodies)
    for child in occ.childOccurrences:
        bodies.extend(all_bodies(child))
    return bodies


def occ_bbox(occ):
    """Bounding box of all of an occurrence's body proxies (root coords)."""
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
    print("%s bbox(cm): x %.3f..%.3f  y %.3f..%.3f  z %.3f..%.3f" %
          (tag, bb.minPoint.x, bb.maxPoint.x, bb.minPoint.y, bb.maxPoint.y,
           bb.minPoint.z, bb.maxPoint.z))


def rot_matrix(xrot_deg, flip180):
    m = adsk.core.Matrix3D.create()
    origin = adsk.core.Point3D.create(0, 0, 0)
    m.setToRotation(math.radians(xrot_deg),
                    adsk.core.Vector3D.create(1, 0, 0), origin)
    if flip180:
        mz = adsk.core.Matrix3D.create()
        mz.setToRotation(math.pi, adsk.core.Vector3D.create(0, 0, 1), origin)
        m.transformBy(mz)  # m = rotZ(180) * rotX(...)
    return m


def place(occ, rot, target_cx, target_cy, target_zmin):
    """Set rotation, then translate so the rotated bbox lands on target."""
    occ.transform2 = rot
    bb = occ_bbox(occ)
    dx = target_cx - (bb.minPoint.x + bb.maxPoint.x) / 2
    dy = target_cy - (bb.minPoint.y + bb.maxPoint.y) / 2
    dz = target_zmin - bb.minPoint.z
    m = rot.copy()
    m.translation = adsk.core.Vector3D.create(dx, dy, dz)
    occ.transform2 = m


def run(_context: str):
    app = adsk.core.Application.get()
    des = adsk.fusion.Design.cast(app.activeProduct)
    root = des.rootComponent

    for occ in list(root.occurrences):
        if occ.component.name.startswith(("RD-03D", "Seeed", "XIAO")):
            name = occ.name
            occ.deleteMe()
            print("removed prior import:", name)

    imp = app.importManager
    before = root.occurrences.count
    imp.importToTarget(imp.createSTEPImportOptions(RADAR), root)
    radar_occ = root.occurrences.item(before)
    imp.importToTarget(imp.createSTEPImportOptions(XIAO), root)
    xiao_occ = root.occurrences.item(before + 1)
    print("imported:", radar_occ.name, "|", xiao_occ.name)

    show_bbox("radar native", occ_bbox(radar_occ))
    show_bbox("xiao native", occ_bbox(xiao_occ))

    intD, rT = p(des, "intD"), p(des, "radarT")
    rCx, xCx, postH = p(des, "radarCx"), p(des, "xiaoCx"), p(des, "postH")

    # Radar: back face on crossbars at z = intD - 1mm - radarT (= 6.65 mm)
    place(radar_occ, rot_matrix(RADAR_XROT_DEG, RADAR_FLIP180),
          rCx, 0.0, intD - 0.1 - rT)
    # XIAO: bottom on posts at z = postH (= 3 mm)
    place(xiao_occ, rot_matrix(XIAO_XROT_DEG, False), xCx, 0.0, postH)

    # Parametric designs revert occurrence moves unless snapshotted.
    if des.snapshots.hasPendingSnapshot:
        des.snapshots.add()

    show_bbox("radar placed", occ_bbox(radar_occ))
    show_bbox("xiao placed", occ_bbox(xiao_occ))

    # Interference: all bodies of all top-level occurrences
    ents = adsk.core.ObjectCollection.create()
    for occ in root.occurrences:
        for b in all_bodies(occ):
            ents.add(b)
    print("interference check over", ents.count, "bodies")
    inp = des.createInterferenceInput(ents)
    res = des.analyzeInterference(inp)
    print("interference pairs:", res.count)
    if res.count == 0:
        print("INTERFERENCE: none")
    for i in range(res.count):
        r = res.item(i)
        c1 = r.entityOne.parentComponent.name
        c2 = r.entityTwo.parentComponent.name
        # API adaptation: InterferenceResult has no interferenceVolume
        # property; measure the transient interference body instead.
        vol = r.interferenceBody.volume if r.interferenceBody else -1.0
        print("INTERFERENCE: %.6f cm^3 between %s and %s" % (vol, c1, c2))
