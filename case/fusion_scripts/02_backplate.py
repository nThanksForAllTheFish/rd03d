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
        if occ.component.name.startswith("BackPlate"):
            # rename before deleting: the dead component keeps its name
            # reserved in the document's name registry (until save), which
            # would force the rebuilt component to "BackPlate (1)"
            occ.component.name = "BackPlate_deleted"
            occ.deleteMe()
            print("removed existing BackPlate")

    occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    comp = occ.component
    comp.name = "BackPlate"

    intW, intH = p(des, "intW"), p(des, "intH")
    backT, rimGap = p(des, "backT"), p(des, "rimGap")
    rW, rH, rT = p(des, "radarW"), p(des, "radarH"), p(des, "radarT")
    rCx = p(des, "radarCx")
    xW, xH, xCx = p(des, "xiaoW"), p(des, "xiaoH"), p(des, "xiaoCx")
    postH, clear = p(des, "postH"), p(des, "boardClear")
    intD, wall, winT = p(des, "intD"), p(des, "wall"), p(des, "windowT")
    MM = 0.1

    # 1. plate
    sk = comp.sketches.add(comp.xYConstructionPlane)
    rect(sk, 0, 0, intW - 2 * rimGap, intH - 2 * rimGap)
    plate = extrude(comp, sk.profiles.item(0), -backT, 0,
                    adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    plate_body = plate.bodies.item(0)
    print("plate ok")

    # 2. (deleted 2026-09-07) tape recess: with the LEGO Technic holes as
    # the primary mount, the 34x38x0.6 rear pocket only hurt printability -
    # back-face-down the first layer touched just the outer rim and then
    # bridged the whole recess (user print report). The rear face is now
    # fully flat; adhesive tape sticks directly to it. The rear Technic
    # counterbores (0.9 deep, step 7) are unchanged.

    # 3. snap pockets at plate +/-X edges, y=+/-12 (BLIND: z -1.7..-0.3,
    # leaving material ledges at both z ends so the shell's bumps
    # (z -1.6..-0.4) are retained axially with 0.1mm slop per side)
    sk = comp.sketches.add(comp.xYConstructionPlane)
    for sx in (-1, 1):
        edge = sx * (intW / 2 - rimGap)
        for sy in (-1, 1):
            # rect centered on the edge, 1.2 wide -> cuts 0.6 deep into plate
            rect(sk, edge, sy * 12 * MM, 0.12, 6.2 * MM)
    profs = collection([sk.profiles.item(i) for i in range(sk.profiles.count)])
    extrude(comp, profs, -1.7 * MM, -0.3 * MM,
            adsk.fusion.FeatureOperations.CutFeatureOperation,
            participants=[plate_body])
    print("snap pockets ok")

    # 4. radar bay: two +/-X side walls + crossbars. (Thin-wall fix
    # 2026-09-07: the old full perimeter fence ring left 0.6 mm +/-Y wall
    # segments after the plate-outline trim - unprintable on a 0.6 mm
    # nozzle. The +/-Y restraint is now two retention ribs inside the
    # FrontShell (03_shell.py); the plate keeps only the 1.5 mm-thick
    # +/-X walls, spanning the full old ring extent in Y and still
    # trimmed by the plate outline in step 6.)
    bayW, bayH = rW + 2 * clear, rH + 2 * clear
    t = 1.5 * MM
    sk = comp.sketches.add(comp.xYConstructionPlane)
    rect(sk, rCx - bayW / 2 - t / 2, 0, t, bayH + 2 * t)   # -X wall
    rect(sk, rCx + bayW / 2 + t / 2, 0, t, bayH + 2 * t)   # +X wall
    profs = collection([sk.profiles.item(i) for i in range(sk.profiles.count)])
    extrude(comp, profs, 0, 11 * MM,
            adsk.fusion.FeatureOperations.JoinFeatureOperation,
            participants=[plate_body])
    # Board-seating fix 2026-09-07: the crossbars now bear on the RD-03D's
    # BARE PCB, not on its rear connector.
    #   Was: two 4 mm-wide bars at y = +/-18 with tops at z = intD - 1 - radarT
    #   = 6.65 mm (the board's TOTAL thickness incl. the rear connector). That
    #   was wrong in both places: probing the live vendor model showed the
    #   board's rear profile is a bare PCB face at z = 10.50 mm, with only the
    #   5-pin connector reaching back to z = 6.70 over y -20..-13.5. So the
    #   +18 bar stopped 3.85 mm short of the board (no contact at all) and the
    #   -18 bar was the sole support, loading the connector - the board could
    #   rock on it.
    #   Now: tops at the measured PCB rear face, placed in the two
    #   full-board-width bands measured clear of every rear component
    #   (probed at x -18.6, -17, -14, -11.5, -9, -6, -4.4):
    #       band y -13.0..-11.0  -> crossbar A, y -12.8..-11.2 (1.6 wide)
    #       band y +17.5..+20.0  -> crossbar B, y +17.7..+19.8 (2.1 wide)
    #   The connector now hangs free in the open space below the bars.
    #   The board's resting position is UNCHANGED: PCB rear + the 2.54 mm
    #   PCB/patch stack = patch face at z = 13.0, i.e. 1 mm behind the shell's
    #   front inner wall exactly as before, so the RF geometry is unaffected.
    #   (rT / radarT is now only descriptive of the board's total thickness;
    #   the support height is the measured PCB rear face, a local constant.)
    #   Height provenance: the change request quoted a coarse probe reading of
    #   10.50 mm. Bisecting the vendor solid's underside on a 21 x 9 grid over
    #   both bar footprints put the rear face uniformly at 10.4600 mm, so a
    #   10.50 top left a 0.04 mm nominal overlap (2.235 mm^3 = 15.1 x 3.7 x
    #   0.04, exactly the board-width x total-bar-width slab) and a nonzero
    #   plate<->radar interference pair. 10.46 restores exact face contact and
    #   the zero-interference invariant; functionally identical either way,
    #   since the board simply rests on whatever height the bars are.
    PCB_REAR_Z = 10.46 * MM      # measured bare-PCB rear face of the RD-03D
    XBARS = ((-12.0 * MM, 1.6 * MM),    # A: y -12.8..-11.2
             (18.75 * MM, 2.1 * MM))    # B: y +17.7..+19.8
    sk = comp.sketches.add(comp.xYConstructionPlane)
    for cy, w in XBARS:
        rect(sk, rCx, cy, bayW, w)
    profs = collection([sk.profiles.item(i) for i in range(sk.profiles.count)])
    extrude(comp, profs, 0, PCB_REAR_Z,
            adsk.fusion.FeatureOperations.JoinFeatureOperation,
            participants=[plate_body])
    print("radar bay ok (X walls + crossbars bearing on the PCB; "
          "Y-restraint is the shell's job), crossbar top z(mm)=",
          round(PCB_REAR_Z * 10, 3), "board total thickness radarT(mm)=",
          round(rT * 10, 2))

    # 4b. notch the radar fence +X wall where the XIAO board crosses it
    # (as-built correction found in Task 5: the bay centers put the radar
    # fence's +X wall at x -3.7..-2.2mm while the XIAO board's -X edge
    # reaches x -3.23mm, so the full-height wall would pass through the
    # board. Remove the wall above the post height over the XIAO footprint
    # +0.5mm clearance; the stub below z=postH stays and is co-planar with
    # the posts, and the wall segments beyond y=+/-9.4mm still retain the
    # radar board laterally.)
    nx0 = rCx + bayW / 2 - 0.01
    nx1 = rCx + bayW / 2 + 1.5 * MM + 0.01
    ny = xH / 2 + clear + 0.25 * MM
    sk = comp.sketches.add(comp.xYConstructionPlane)
    rect(sk, (nx0 + nx1) / 2, 0, nx1 - nx0, 2 * ny)
    extrude(comp, sk.profiles.item(0), postH, 11 * MM + 0.01,
            adsk.fusion.FeatureOperations.CutFeatureOperation,
            participants=[plate_body])
    print("radar fence notched for xiao board")

    # 5. xiao bay: 4 posts + 3-sided fence (open toward +X)
    sk = comp.sketches.add(comp.xYConstructionPlane)
    for sx in (-1, 1):
        for sy in (-1, 1):
            rect(sk, xCx + sx * (xW / 2 - 1.5 * MM),
                 sy * (xH / 2 - 1.5 * MM), 3 * MM, 3 * MM)
    profs = collection([sk.profiles.item(i) for i in range(sk.profiles.count)])
    extrude(comp, profs, 0, postH,
            adsk.fusion.FeatureOperations.JoinFeatureOperation,
            participants=[plate_body])
    fW, fH = xW + 2 * clear, xH + 2 * clear
    t = 1.5 * MM
    sk = comp.sketches.add(comp.xYConstructionPlane)
    rect(sk, xCx - fW / 2 - t / 2, 0, t, fH + 2 * t)          # -X side
    rect(sk, xCx, fH / 2 + t / 2, fW + 2 * t, t)              # +Y side
    rect(sk, xCx, -(fH / 2 + t / 2), fW + 2 * t, t)           # -Y side
    profs = collection([sk.profiles.item(i) for i in range(sk.profiles.count)])
    extrude(comp, profs, 0, 5 * MM,
            adsk.fusion.FeatureOperations.JoinFeatureOperation,
            participants=[plate_body])
    print("xiao bay ok")

    # 6. trim everything to the plate outline (the radar fence and the xiao
    # fence ±Y bars as drawn overhang the 41.7 x 45.7 plate; the shell's
    # interior walls occupy that space, so intersect with the plate footprint)
    sk = comp.sketches.add(comp.xYConstructionPlane)
    rect(sk, 0, 0, intW - 2 * rimGap, intH - 2 * rimGap)
    extrude(comp, sk.profiles.item(0), -backT, 11 * MM,
            adsk.fusion.FeatureOperations.IntersectFeatureOperation,
            participants=[plate_body])
    print("trimmed to plate outline")

    # 7. LEGO Technic mounting holes (change request 2026-09-07): six
    # through-holes on the 8mm LEGO pitch — a 1x4 column at x=0.95mm
    # (y=-12,-4,+4,+12) and a 1x2 column one pitch over at x=8.95mm
    # (y=-4,+4). Each: legoHole dia through bore (z -backT..0) with a
    # legoCbDia x legoCbDepth counterbore on BOTH faces so Technic
    # pin collars/tips seat flush, plus a 0.3mm 45 deg entry chamfer
    # on the rear opening.
    pitch = p(des, "legoPitch")
    holeD = p(des, "legoHole")
    cbD = p(des, "legoCbDia")
    cbZ = p(des, "legoCbDepth")
    x1 = 0.95 * MM               # 1x4 column
    x2 = x1 + pitch              # 1x2 column (8.95mm)
    centers = ([(x1, s * pitch / 2) for s in (-3, -1, 1, 3)] +
               [(x2, s * pitch / 2) for s in (-1, 1)])

    def circles(radius):
        sk = comp.sketches.add(comp.xYConstructionPlane)
        for cx, cy in centers:
            sk.sketchCurves.sketchCircles.addByCenterRadius(
                adsk.core.Point3D.create(cx, cy, 0), radius)
        return collection([sk.profiles.item(i)
                           for i in range(sk.profiles.count)])

    extrude(comp, circles(holeD / 2), -backT, 0,
            adsk.fusion.FeatureOperations.CutFeatureOperation,
            participants=[plate_body])
    extrude(comp, circles(cbD / 2), -backT, -backT + cbZ,
            adsk.fusion.FeatureOperations.CutFeatureOperation,
            participants=[plate_body])
    extrude(comp, circles(cbD / 2), -cbZ, 0,
            adsk.fusion.FeatureOperations.CutFeatureOperation,
            participants=[plate_body])
    print("technic holes ok:",
          [(round(cx / MM, 2), round(cy / MM, 2)) for cx, cy in centers])

    # rear entry chamfer: the bore's rear opening edge sits at the rear
    # counterbore floor, z = -backT + cbZ (circle radius holeD/2)
    try:
        edges = adsk.core.ObjectCollection.create()
        for e in plate_body.edges:
            g = e.geometry
            if (isinstance(g, adsk.core.Circle3D)
                    and abs(g.radius - holeD / 2) < 0.005
                    and abs(g.center.z - (-backT + cbZ)) < 0.005):
                edges.add(e)
        if edges.count != 6:
            raise RuntimeError("expected 6 rear bore edges, found %d"
                               % edges.count)
        ch = comp.features.chamferFeatures
        chi = ch.createInput(edges, False)
        chi.setToEqualDistance(adsk.core.ValueInput.createByReal(0.3 * MM))
        ch.add(chi)
        print("rear entry chamfers ok (0.3mm x 45deg on 6 edges)")
    except Exception as exc:  # counterbore alone is acceptable
        print("CHAMFER SKIPPED:", exc)

    print("BackPlate bodies:", comp.bRepBodies.count)
