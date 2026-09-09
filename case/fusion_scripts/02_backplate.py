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


def box(sk, x0, x1, y0, y1):
    """Axis-aligned rect from an X range and a Y range, either order (cm)."""
    sk.sketchCurves.sketchLines.addTwoPointRectangle(
        adsk.core.Point3D.create(min(x0, x1), min(y0, y1), 0),
        adsk.core.Point3D.create(max(x0, x1), max(y0, y1), 0))


def plane_at_z(comp, z):
    inp = comp.constructionPlanes.createInput()
    inp.setByOffset(comp.xYConstructionPlane,
                    adsk.core.ValueInput.createByReal(z))
    pl = comp.constructionPlanes.add(inp)
    pl.isLightBulbOn = False      # keep the user's viewport clean
    return pl


def ramp_loft(comp, z_lo, lo, z_hi, hi, participants):
    """Join a straight ruled ramp lofted between two axis-aligned rects.

    `lo`/`hi` are (x0, x1, y0, y1) tuples (cm) at z_lo / z_hi. A loft is used
    rather than a two-distance chamfer because the chamfer API's distance ->
    face assignment depends on the edge's internal face order, which is not
    predictable from a script; the loft states both end sections explicitly.
    """
    s_lo = comp.sketches.add(plane_at_z(comp, z_lo))
    box(s_lo, *lo)
    s_hi = comp.sketches.add(plane_at_z(comp, z_hi))
    box(s_hi, *hi)
    lofts = comp.features.loftFeatures
    li = lofts.createInput(adsk.fusion.FeatureOperations.JoinFeatureOperation)
    li.loftSections.add(s_lo.profiles.item(0))
    li.loftSections.add(s_hi.profiles.item(0))
    li.isSolid = True
    try:
        li.participantBodies = participants
    except Exception as exc:      # keep going: Join of an overlapping solid
        print("  (loft participantBodies unsupported: %s)" % exc)
    feat = lofts.add(li)
    # loftFeatures (unlike extrudeFeatures) leaves its profile sketches
    # visible; hide them so the user's viewport is not littered
    for s in (s_lo, s_hi):
        s.isVisible = False
    return feat


def clip(comp, body, axis, wall_out, wall_in, f0, f1, slots, slot_z0,
         raise_z0, top_z, lip_z, lip_proj, thin=0.0, label=""):
    """Build ONE cantilever retention clip on a straight fence wall.

    axis  'x' -> the wall's thickness runs along X (wall_out / wall_in are X
                 coordinates of its outer / inner faces) and the finger spans
                 f0..f1 in Y.  'y' -> the transpose.
    slots list of (v0, v1) spans in the finger-span axis, cut through the full
          wall thickness from slot_z0 up past the clip top; they isolate the
          finger so it can flex.  The finger stays anchored below slot_z0.
    thin  material removed from the wall's OUTER face over the finger width
          (0 = keep the wall at full thickness).  Lowers the spring rate.
    lip   flat underside at lip_z projecting lip_proj past the wall's inner
          face, ramping back flush with the wall by top_z.  The ramp doubles
          as the insertion lead-in (the board's edge cams the finger open on
          the way in); the flat underside is the retaining face.
    Every feature is restricted to `body`.  All lengths in cm.
    """
    MM = 0.1
    s = 1.0 if wall_in > wall_out else -1.0      # sign of "inward"
    eps = 0.1 * MM
    z_over = top_z + 1.0 * MM

    def mk(sk, u0, u1, v0, v1):
        if axis == "x":
            box(sk, u0, u1, v0, v1)
        else:
            box(sk, v0, v1, u0, u1)

    # a) raise the wall locally over the finger width (overlaps the existing
    #    wall so the Join merges by volume, not by coplanar faces)
    sk = comp.sketches.add(comp.xYConstructionPlane)
    mk(sk, wall_out, wall_in, f0, f1)
    extrude(comp, sk.profiles.item(0), raise_z0, top_z,
            adsk.fusion.FeatureOperations.JoinFeatureOperation,
            participants=[body])

    # b) thin the finger from the OUTER face
    if thin > 0:
        sk = comp.sketches.add(comp.xYConstructionPlane)
        mk(sk, wall_out - s * eps, wall_out + s * thin, f0, f1)
        extrude(comp, sk.profiles.item(0), slot_z0, z_over,
                adsk.fusion.FeatureOperations.CutFeatureOperation,
                participants=[body])

    # c) isolating slots
    sk = comp.sketches.add(comp.xYConstructionPlane)
    for v0, v1 in slots:
        mk(sk, wall_out - s * eps, wall_in + s * eps, v0, v1)
    profs = collection([sk.profiles.item(i) for i in range(sk.profiles.count)])
    if profs.count != len(slots):
        raise RuntimeError("%s: expected %d slot profiles, found %d"
                           % (label, len(slots), profs.count))
    extrude(comp, profs, slot_z0, z_over,
            adsk.fusion.FeatureOperations.CutFeatureOperation,
            participants=[body])

    # d) lip + lead-in ramp
    back = wall_in - s * 0.3 * MM        # anchor the loft inside the wall
    if axis == "x":
        lo = (back, wall_in + s * lip_proj, f0, f1)
        hi = (back, wall_in, f0, f1)
    else:
        lo = (f0, f1, back, wall_in + s * lip_proj)
        hi = (f0, f1, back, wall_in)
    ramp_loft(comp, lip_z, lo, top_z, hi, [body])

    if comp.bRepBodies.count != 1:
        raise RuntimeError("%s: clip did not merge, %d bodies"
                           % (label, comp.bRepBodies.count))
    print("  clip %-14s axis=%s wall %.2f..%.2f  finger %.2f..%.2f  "
          "top %.2f  lip %.2f +%.2f  slots %s"
          % (label, axis, wall_out * 10, wall_in * 10, f0 * 10, f1 * 10,
             top_z * 10, lip_z * 10, lip_proj * 10,
             [(round(a * 10, 2), round(b * 10, 2)) for a, b in slots]))


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

    # 8. BOARD RETENTION CLIPS (change request 2026-09-08). Until now nothing
    # held either board down on the plate: the radar was captured only when
    # the lid closed, and the XIAO only by the shell's hold-down boss. Both
    # boards now press into cantilever snap fingers cut into the fence walls
    # they already sit against, so a bare plate holds its boards.
    #
    # MUST come after step 6 (the plate-outline Intersect is limited to
    # z <= 11 mm and would decapitate anything taller) and after step 7 (the
    # LEGO bore chamfer selects edges by circle radius; extra clip edges are
    # harmless but the ordering keeps that selection on virgin topology).
    #
    # Measurement provenance (probed on the live vendor solids, not derived):
    #   RD-03D  PCB rear face z = 10.46 (rests on the crossbars); PCB FRONT
    #           face - the antenna/patch plane - z = 11.70, flat across both
    #           board edges over the whole clip range; board x -19.05..-3.95,
    #           y +/-22.01. Its 45-degree IC protrudes to 12.95, but only over
    #           about x -15..-5, y -3..+3, i.e. nowhere near either edge.
    #   XIAO    PCB top z = 4.20, flat along both long edges (the header
    #           holes are further in at y ~ +/-7.5); board x -3.23..19.23,
    #           y +/-8.89. Edge castellations bite ~0.24 mm in at a ~2.54 mm
    #           pitch, so a lip reaching 0.34 mm past the edge still lands on
    #           solid board (0.10 mm) even where it crosses a castellation.
    #   Fence walls as built: radar +/-X walls x -20.8..-19.3 (inner face
    #           -19.3) and x -3.7..-2.2 (inner face -3.7); XIAO +/-Y walls
    #           y +/-9.15..+/-10.65 (inner faces +/-9.15), 1.5 thick.
    #
    # Each lip's flat underside sits 0.10 mm above its board's front/top face,
    # so the clips CLEAR the boards at rest (no press, no interference) and
    # only bear if a board tries to lift. That 0.10 mm float is deliberate:
    # a preloaded clip would creep in PETG.
    print("retention clips:")
    LIP_FLOAT = 0.10 * MM

    # 8a. RADAR clips - one per +/-X fence wall, 7 mm finger, slots from
    # z=2.0 to the top (~10 mm of lever below the lip), wall raised locally
    # to 12.5, lip underside at 11.80 = PCB front 11.70 + float, projecting
    # 0.85 past the wall's inner face -> lip inner edges at x -18.45 / -4.55
    # against board edges -19.05 / -3.95 = 0.60 mm of grab per side.
    RADAR_PCB_FRONT_Z = 11.70 * MM
    R_LIP_Z = RADAR_PCB_FRONT_Z + LIP_FLOAT      # 11.80
    R_TOP_Z = 12.50 * MM
    R_LIP = 0.85 * MM
    R_SLOT_Z0 = 2.0 * MM
    R_RAISE_Z0 = 10.5 * MM                       # inside the 11 mm wall
    # The +X clip (below) sits under the RX radome step at 12.90 rather than
    # the 14.0 wall, so it gets its own lower top for lid clearance: 0.60 mm
    # instead of 0.40. Trade: a slightly steeper insertion cam (0.85 over
    # 0.50 instead of 0.70), i.e. a firmer snap. Both parts are separate
    # prints, so nominal clearance absorbs their stacked tolerance.
    R_TOP_Z_PX = 12.30 * MM

    # LEFT wall: finger centred on y=0 as designed. This is the radar IC's
    # y band, which is exactly why it is free: the shell keeps its front
    # inner face at 14.0 over y -4..+4 (the radome step in 03_shell.py skips
    # that band for the IC), so a 12.5 clip top has 1.5 mm of headroom.
    clip(comp, plate_body, "x", -20.8 * MM, -19.3 * MM,
         -3.5 * MM, 3.5 * MM,
         [(-4.5 * MM, -3.5 * MM), (3.5 * MM, 4.5 * MM)],
         R_SLOT_Z0, R_RAISE_Z0, R_TOP_Z, R_LIP_Z, R_LIP, label="radar -X")

    # RIGHT wall: DEVIATION, recorded. The change request asked for this clip
    # at y=0 too, but the +X radar fence wall does not exist there: step 4b
    # notches it down to z=postH (3 mm) over y +/-9.4 because the XIAO board
    # (x -3.23..19.23) crosses the wall's x -3.7..-2.2 footprint. Verified on
    # the live model - wall top is 2.95 at y=0, 10.95 only outside y +/-9.4.
    # A finger there would run straight through the XIAO board, and even a
    # finger thinned to miss it would have only 0.27 mm of flex room before
    # hitting the XIAO. So this clip moves +Y to the nearest full-height
    # stretch of the same wall: finger y +12.0..+19.0 (still well inside the
    # board's +/-22.01 and clear of the XIAO fence bars, which end at
    # y=10.65). Its inboard slot is widened to start at the step-4b notch
    # edge (y=9.4) instead of 11.0 so it swallows the 1.6 mm orphan stub of
    # wall that would otherwise be left standing between notch and slot.
    # Cost of the move: the clip top now sits under the RX radome step
    # (shell inner face 12.90 there, not 14.00), so headroom is 0.60 mm
    # instead of 1.50. Static clearance - the finger flexes in X, not Z.
    clip(comp, plate_body, "x", -2.2 * MM, -3.7 * MM,
         12.0 * MM, 19.0 * MM,
         [(9.4 * MM, 12.0 * MM), (19.0 * MM, 20.0 * MM)],
         R_SLOT_Z0, R_RAISE_Z0, R_TOP_Z_PX, R_LIP_Z, R_LIP, label="radar +X")

    # 8b. XIAO clips - one per +/-Y fence wall, 7 mm finger at x 4.5..11.5.
    # The XIAO's top face is only 4.2 mm above the plate, so the lever is
    # short; the finger is therefore THINNED to 1.0 mm (0.5 mm off the wall's
    # OUTER face, inner face stays at +/-9.15) and the grab is smaller, to
    # keep bending strain away from PETG's yield. Slots run to the plate
    # floor (z=0) so the finger gets its full 4.3 mm of lever - at a
    # 0.34 mm deflection that is ~2.5% strain vs PETG's ~4-5% yield. Wall
    # raised locally to 5.6, lip underside 4.30 = PCB top 4.20 + float,
    # projecting 0.60 -> lip inner edges y +/-8.55 vs board edges +/-8.89 =
    # 0.34 mm of grab per side.
    XIAO_PCB_TOP_Z = 4.20 * MM
    X_LIP_Z = XIAO_PCB_TOP_Z + LIP_FLOAT         # 4.30
    X_TOP_Z = 5.60 * MM
    X_LIP = 0.60 * MM
    X_SLOT_Z0 = 0.0
    X_RAISE_Z0 = 4.5 * MM                        # inside the 5 mm wall
    X_THIN = 0.5 * MM
    for sy in (-1, 1):
        clip(comp, plate_body, "y", sy * 10.65 * MM, sy * 9.15 * MM,
             4.5 * MM, 11.5 * MM,
             [(3.5 * MM, 4.5 * MM), (11.5 * MM, 12.5 * MM)],
             X_SLOT_Z0, X_RAISE_Z0, X_TOP_Z, X_LIP_Z, X_LIP, thin=X_THIN,
             label="xiao %sY" % ("+" if sy > 0 else "-"))

    print("BackPlate bodies:", comp.bRepBodies.count)
