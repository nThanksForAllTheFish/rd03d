import adsk.core
import adsk.fusion


def p(des, name):
    return des.userParameters.itemByName(name).value  # cm


def rect(sk, cx, cy, w, h):
    sk.sketchCurves.sketchLines.addTwoPointRectangle(
        adsk.core.Point3D.create(cx - w / 2, cy - h / 2, 0),
        adsk.core.Point3D.create(cx + w / 2, cy + h / 2, 0))


def extrude(comp, profiles, z0, z1, op, participants=None):
    ext = comp.features.extrudeFeatures
    inp = ext.createInput(profiles, op)
    start = adsk.fusion.OffsetStartDefinition.create(
        adsk.core.ValueInput.createByReal(z0))
    inp.startExtent = start
    inp.setOneSideExtent(
        adsk.fusion.DistanceExtentDefinition.create(
            adsk.core.ValueInput.createByReal(z1 - z0)),
        adsk.fusion.ExtentDirections.PositiveExtentDirection)
    if participants is not None:
        # Restrict which bodies this feature can modify; without this a
        # Cut/Intersect eats every intersecting body in the design (e.g.
        # the other component's body).
        inp.participantBodies = participants
    return ext.add(inp)


def collection(items):
    coll = adsk.core.ObjectCollection.create()
    for i in items:
        coll.add(i)
    return coll


def run(_context: str):
    app = adsk.core.Application.get()
    des = adsk.fusion.Design.cast(app.activeProduct)
    root = des.rootComponent

    for occ in list(root.occurrences):
        if occ.component.name == "FrontShell":
            occ.deleteMe()
            print("removed existing FrontShell")

    occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    comp = occ.component
    comp.name = "FrontShell"

    intW, intH, intD = p(des, "intW"), p(des, "intH"), p(des, "intD")
    wall, backT = p(des, "wall"), p(des, "backT")
    winT, rCx = p(des, "windowT"), p(des, "radarCx")
    MM = 0.1

    # 1+2: outer box then cavity (cavity cut MUST be restricted to the shell
    # body: unrestricted it also hollows out the BackPlate body to nothing)
    sk = comp.sketches.add(comp.xYConstructionPlane)
    rect(sk, 0, 0, intW + 2 * wall, intH + 2 * wall)
    box = extrude(comp, sk.profiles.item(0), -backT, intD + wall,
                  adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    shell_body = box.bodies.item(0)
    sk = comp.sketches.add(comp.xYConstructionPlane)
    rect(sk, 0, 0, intW, intH)
    extrude(comp, sk.profiles.item(0), -backT, intD,
            adsk.fusion.FeatureOperations.CutFeatureOperation,
            participants=[shell_body])
    print("shell box ok")

    # 3: radar window pocket on the outer front face over the patch end
    # rect x in [rCx-9.5mm, rCx+9.5mm], y in [1mm, 25mm]
    sk = comp.sketches.add(comp.xYConstructionPlane)
    rect(sk, rCx, 13 * MM, 19 * MM, 24 * MM)
    extrude(comp, sk.profiles.item(0), intD + winT, intD + wall,
            adsk.fusion.FeatureOperations.CutFeatureOperation,
            participants=[shell_body])
    print("window ok")

    # 4: usb notch through +X wall, back rim z=-backT up to z=8mm
    sk = comp.sketches.add(comp.xYConstructionPlane)
    rect(sk, intW / 2 + wall / 2, 0, wall + 0.02, 11.3 * MM)
    extrude(comp, sk.profiles.item(0), -backT, 8 * MM,
            adsk.fusion.FeatureOperations.CutFeatureOperation,
            participants=[shell_body])
    print("usb notch ok")

    # 5: snap bumps on inner +/-X walls at y=+/-12, z centered -1mm
    # (rects extend into the wall so the Join reliably merges with the
    # shell body; proud amount into the cavity is snapBump)
    snap = p(des, "snapBump")
    sk = comp.sketches.add(comp.xYConstructionPlane)
    for sx in (-1, 1):
        cx = sx * (intW / 2 + (wall - snap) / 2)  # spans intW/2-snap .. intW/2+wall
        for sy in (-1, 1):
            rect(sk, cx, sy * 12 * MM, snap + wall, 6 * MM)
    profs = collection([sk.profiles.item(i) for i in range(sk.profiles.count)])
    extrude(comp, profs, -1.6 * MM, -0.4 * MM,
            adsk.fusion.FeatureOperations.JoinFeatureOperation,
            participants=[shell_body])
    print("snap bumps ok")
    print("FrontShell bodies:", comp.bRepBodies.count)
