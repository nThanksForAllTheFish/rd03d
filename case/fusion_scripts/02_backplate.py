import math

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
          An EMPTY list skips the slot cuts entirely, leaving the wall
          continuous - correct where the wall is tall enough to supply the
          needed flex on its own (see the radar clips in step 8a).
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

    # c) isolating slots (skipped entirely when `slots` is empty - an empty
    #    ObjectCollection is rejected by extrudeFeatures, and adding an
    #    empty sketch would litter the user's browser tree)
    if slots:
        sk = comp.sketches.add(comp.xYConstructionPlane)
        for v0, v1 in slots:
            mk(sk, wall_out - s * eps, wall_in + s * eps, v0, v1)
        profs = collection([sk.profiles.item(i)
                            for i in range(sk.profiles.count)])
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
             ([(round(a * 10, 2), round(b * 10, 2)) for a, b in slots]
              if slots else "NONE (continuous wall)")))


def ensure_params(des):
    """Create this plan's user parameters if the document lacks them.

    Deliberately NOT added to 01_setup.py: re-running that script resets
    every parameter the user has hand-tuned. Existing values are left alone
    so the user can edit them in Modify -> Change Parameters.
    """
    spec = [
        ("usbJackW", "9.08 mm", "USB-C jack widest section (its PCB)"),
        ("usbJackT", "3.17 mm", "USB-C jack thickness"),
        ("usbJackL", "14.42 mm", "USB-C jack overall length"),
        ("usbShellL", "10.58 mm", "USB-C jack metal shell length"),
        ("usbJackClear", "0.25 mm", "total jack slot clearance"),
        ("capDia", "8.2 mm", "bulk capacitor diameter"),
        ("capLen", "12 mm", "bulk capacitor body length"),
        ("capClear", "0.4 mm", "total capacitor cradle clearance"),
    ]
    ups = des.userParameters
    for name, expr, comment in spec:
        if ups.itemByName(name) is None:
            ups.add(name, adsk.core.ValueInput.createByString(expr),
                    "mm", comment)
            print("added param", name, "=", expr)


def run(_context: str):
    app = adsk.core.Application.get()
    des = adsk.fusion.Design.cast(app.activeProduct)
    root = des.rootComponent
    ensure_params(des)

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
    # legoCbDia x legoCbDepth counterbore on the REAR face only, so pin
    # collars seat flush, plus a 0.3mm 45 deg entry chamfer on the rear
    # opening. (2026-09-09: the interior counterbores were deleted - a
    # Technic pin only ever goes in from the back, and their 0.9 mm
    # recesses fell where printed features want flat interior floor.)
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
    # boards now press in under snap lips carried on the fence walls they
    # already sit against, so a bare plate holds its boards. (As of
    # 2026-09-10 none of the five is a slot-isolated finger any more: every
    # one is a lip on a continuous wall - see 8a and 8b.)
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

    # 8a. RADAR clips - THREE, and NO relief slots (change request
    # 2026-09-09, user design review; supersedes the two slotted radar
    # clips of 2026-09-08).
    #
    # Why the slots go away: the lip underside sits 11.80 mm above the
    # plate, so the fence wall itself is an 11.8 mm cantilever of 1.5 mm
    # PETG. Deflecting its tip the 0.60 mm needed to clear the board edge
    # puts the peak surface strain at ~3*t*d/(2*L^2) = 3*1.5*0.60/
    # (2*11.8^2) ~= 1% - a quarter of PETG's ~4-5% yield - and needs of
    # order 12 N at the lip. A 1.5 x 7 mm section at that length simply
    # does not need to be isolated from its neighbours to flex, and the
    # slots cost stiffness where the wall's real job is holding the radar
    # laterally. So all three radar clips pass an EMPTY slot list; the
    # local wall raise and the lip/ramp are unchanged.
    #
    # Bonus effect of dropping the +X clip's inboard slot: the 1.7 x 1.25
    # x 3 mm nick it used to take out of the XIAO's +Y fence bar (recorded
    # as cosmetic on 2026-09-08) is gone, and the +X wall is continuous
    # from the step-4b notch edge (y=9.4) to the plate outline.
    #
    # (2026-09-10: the XIAO clips in 8b are now slot-free too, but for the
    # opposite reason - see 8b. Here the wall is long enough to flex; there
    # the user wanted it NOT to flex.)
    RADAR_PCB_FRONT_Z = 11.70 * MM
    R_LIP_Z = RADAR_PCB_FRONT_Z + LIP_FLOAT      # 11.80
    R_TOP_Z = 12.50 * MM
    R_LIP = 0.85 * MM
    R_SLOT_Z0 = 2.0 * MM                         # unused: slots are []
    R_RAISE_Z0 = 10.5 * MM                       # inside the 11 mm wall
    # Both +X clips sit under a radome step at 12.90 rather than the 14.0
    # wall, so they get their own lower top for lid clearance: 0.60 mm of
    # headroom instead of 0.40. Trade: a slightly steeper insertion cam
    # (0.85 over 0.50 instead of 0.70), i.e. a firmer snap. Both parts are
    # separate prints, so nominal clearance absorbs their stacked tolerance.
    R_TOP_Z_PX = 12.30 * MM
    NO_SLOTS = []

    # A - LEFT wall, finger centred on y=0. This is the radar IC's y band,
    # which is exactly why it is free: the shell keeps its front inner face
    # at 14.0 over y -4..+4 (the radome step in 03_shell.py skips that band
    # for the IC), so a 12.50 clip top has 1.50 mm of headroom.
    clip(comp, plate_body, "x", -20.8 * MM, -19.3 * MM,
         -3.5 * MM, 3.5 * MM,
         NO_SLOTS,
         R_SLOT_Z0, R_RAISE_Z0, R_TOP_Z, R_LIP_Z, R_LIP, label="radar A -X")

    # The +X wall cannot carry a clip at y=0: step 4b notches it down to
    # z=postH (3 mm) over y +/-9.4 because the XIAO board (x -3.23..19.23)
    # crosses the wall's x -3.7..-2.2 footprint. So the two +X clips take
    # the two full-height stretches of that wall, one under each radome
    # zone, each placed to sit CLEAR of a crossbar - a crossbar runs the
    # full bay width (x -19.3..-3.7) and butts into both walls, so a lip
    # band on top of one would be locally braced and would not flex.
    #
    # B - +X wall under the TX radome. Crossbar A occupies y -12.8..-11.2,
    # so the band stops at -13.5 (0.70 mm clear) and runs down to -20.5
    # (1.51 mm inside the board's -22.01 edge).
    clip(comp, plate_body, "x", -2.2 * MM, -3.7 * MM,
         -20.5 * MM, -13.5 * MM,
         NO_SLOTS,
         R_SLOT_Z0, R_RAISE_Z0, R_TOP_Z_PX, R_LIP_Z, R_LIP,
         label="radar B +X")

    # C - +X wall under the RX radome, in the free stretch between the
    # step-4b notch edge (y=9.4) and crossbar B (y +17.7..+19.8):
    # y +10.0..+17.0 leaves 0.60 mm to the notch and 0.70 mm to the bar.
    clip(comp, plate_body, "x", -2.2 * MM, -3.7 * MM,
         10.0 * MM, 17.0 * MM,
         NO_SLOTS,
         R_SLOT_Z0, R_RAISE_Z0, R_TOP_Z_PX, R_LIP_Z, R_LIP,
         label="radar C +X")

    # 8b. XIAO clips - one per +/-Y fence wall, 7 mm lip band at x 4.5..11.5.
    #
    # NO SLOTS, NO TRENCHES (2026-09-10, user instruction after printing and
    # handling the part; supersedes the slotted-and-trenched design of
    # 2026-09-09 and its 8c trench block, both now deleted).
    #
    # The user's report: the clips as printed were "very wimpy - barely
    # holding it in". That is physical evidence against the calculation the
    # earlier design optimised for, and it wins. The old design isolated a
    # 1.5 mm blade with 0.7 mm slots at each end and dropped its root 1.5 mm
    # below the floor with a trench either side, all to keep BENDING STRAIN
    # low on a lever only ~5.8 mm long. It succeeded at that and failed at
    # the actual job, which is holding the board down.
    #
    # What the clip is NOW: a 7 mm stretch (x 4.5..11.5) of the continuous
    # 1.5 mm fence wall, locally raised from 5.0 to 5.60 mm and carrying a
    # 0.60 mm lip whose flat underside sits at z 4.30 - 0.10 mm above the
    # XIAO's 4.20 mm top face - for 0.34 mm of grab per side against the
    # board edges at y +/-8.89. Lip, grab and float are all UNCHANGED; the
    # user did not ask for a lip change and explicitly declined one.
    #
    # It is no longer a cantilever in any useful sense: the wall is anchored
    # along its whole base to the plate floor and is continuous with its
    # neighbours in x out to the plate edge. Deliberately NO strain or force
    # figure is quoted here. The old 2.3% / 1.4x arithmetic modelled an
    # isolated end-loaded blade and does not describe this at all; a
    # base-anchored, laterally-continuous wall loaded near its top is a
    # different problem, and any number written down for it would be false
    # precision. Qualitatively: far stiffer, so much higher retention.
    #
    # THE TRADE IS INSERTION FORCE. Getting the board past the lip now takes
    # a firmer push, and removing it takes a firmer fingernail. That is the
    # cost the user accepted in exchange for a board that stays put. The
    # 0.85 mm-rise lead-in ramp (clip() step d) still cams the board in, and
    # the README's "rock one edge in first" tip matters more than it did.
    XIAO_PCB_TOP_Z = 4.20 * MM
    X_LIP_Z = XIAO_PCB_TOP_Z + LIP_FLOAT         # 4.30
    X_TOP_Z = 5.60 * MM
    X_LIP = 0.60 * MM
    X_RAISE_Z0 = 4.5 * MM                        # inside the 5 mm wall
    X_THIN = 0.0
    # NO_SLOTS (defined in 8a) makes clip() skip its slot cut entirely; with
    # X_THIN = 0 the thinning cut is skipped too, so slot_z0 is never read
    # and the old X_SLOT_Z0 / X_TRENCH_Z0 constants are gone rather than
    # left behind to imply geometry that no longer exists. 0.0 is passed for
    # slot_z0 to make that unusedness explicit.
    for sy in (-1, 1):
        clip(comp, plate_body, "y", sy * 10.65 * MM, sy * 9.15 * MM,
             4.5 * MM, 11.5 * MM,
             NO_SLOTS,
             0.0, X_RAISE_Z0, X_TOP_Z, X_LIP_Z, X_LIP, thin=X_THIN,
             label="xiao %sY" % ("+" if sy > 0 else "-"))

    # 9. USB-C base jack (2026-09-09). The user powers the node through a
    # jack in the LEGO-mount face instead of the XIAO's own connector.
    # Measured part: 14.42 long overall, 10.58 of that metal shell, 9.08
    # wide (its PCB, the widest section), 3.17 thick. Mouth flush with the
    # back face at z=-8, so 6.42 protrudes into the free -Y band beside the
    # XIAO and the PCB tail starts at z=+0.92 - above the floor, which is
    # why the plate's slot only ever contains the metal shell.
    #
    # The shell's rear edge lands at z = usbShellL - backT = 2.58, where a
    # 45 deg ramp on each +/-Y collar wall rises 0.8 mm inward and wedges it
    # to a stop. Ramps rather than a flat ledge: they self-centre, they
    # print with no unsupported horizontal overhang, and since USB-C is
    # reversible they work whichever face the jack's PCB tail is flush with
    # (a dimension we never measured and do not need).
    #
    # PULL-OUT RETENTION IS EPOXY. The part presents no rearward-facing
    # surface to catch, so no printed feature can resist it; the collar
    # gives ~40 mm2 of glue wall against a plug latch force of order 10 N.
    jW = p(des, "usbJackW") + p(des, "usbJackClear")      # 9.33
    jT = p(des, "usbJackT") + p(des, "usbJackClear")      # 3.42
    JCX, JCY = 13.6 * MM, -19.0 * MM
    COLLAR_T = 1.5 * MM
    COLLAR_TOP = 4.5 * MM
    RAMP_Z0 = p(des, "usbShellL") - backT                 # 2.58
    RAMP_RISE = 0.8 * MM
    RAMP_Z1 = RAMP_Z0 + RAMP_RISE                         # 3.38
    ANCHOR = 0.3 * MM            # loft sections start inside the wall
    sx0, sx1 = JCX - jW / 2, JCX + jW / 2                 # 8.935 .. 18.265
    sy0, sy1 = JCY - jT / 2, JCY + jT / 2                 # -20.71 .. -17.29

    # 9a. collar box, then one cut for the slot AND the collar bore
    sk = comp.sketches.add(comp.xYConstructionPlane)
    box(sk, sx0 - COLLAR_T, sx1 + COLLAR_T,
        sy0 - COLLAR_T, sy1 + COLLAR_T)
    extrude(comp, sk.profiles.item(0), 0, COLLAR_TOP,
            adsk.fusion.FeatureOperations.JoinFeatureOperation,
            participants=[plate_body])
    sk = comp.sketches.add(comp.xYConstructionPlane)
    box(sk, sx0, sx1, sy0, sy1)
    extrude(comp, sk.profiles.item(0), -backT, COLLAR_TOP,
            adsk.fusion.FeatureOperations.CutFeatureOperation,
            participants=[plate_body])

    # 9b. seating ramps on both +/-Y collar walls, plus the narrowed wall
    # they lead into (z RAMP_Z1..COLLAR_TOP), leaving a 1.82 mm tail channel
    for s in (-1, 1):
        # s = -1 is the -Y wall, whose material lies at more negative y and
        # whose channel is toward +y; "inward" is therefore -s.
        face = sy0 if s < 0 else sy1          # the wall's inner face
        back_y = face + s * ANCHOR            # 0.3 mm INTO the wall
        tip_y = face - s * RAMP_RISE          # 0.8 mm INTO the channel
        ramp_loft(comp, RAMP_Z0,
                  (sx0, sx1, back_y, face),
                  RAMP_Z1,
                  (sx0, sx1, back_y, tip_y),
                  [plate_body])
        sk = comp.sketches.add(comp.xYConstructionPlane)
        box(sk, sx0, sx1, back_y, tip_y)
        extrude(comp, sk.profiles.item(0), RAMP_Z1, COLLAR_TOP,
                adsk.fusion.FeatureOperations.JoinFeatureOperation,
                participants=[plate_body])

    # 9c. 0.5 mm entry chamfer on the slot's back-face opening, so the plug
    # finds the mouth. Comfort feature: report and continue if refused.
    try:
        edges = adsk.core.ObjectCollection.create()
        for e in plate_body.edges:
            g = e.geometry
            if not isinstance(g, adsk.core.Line3D):
                continue
            mz = (g.startPoint.z + g.endPoint.z) / 2
            mx = (g.startPoint.x + g.endPoint.x) / 2
            my = (g.startPoint.y + g.endPoint.y) / 2
            if abs(mz + backT) > 0.005:
                continue
            on_x = (abs(abs(mx - JCX) - jW / 2) < 0.005
                    and abs(my - JCY) < jT / 2 + 0.005)
            on_y = (abs(abs(my - JCY) - jT / 2) < 0.005
                    and abs(mx - JCX) < jW / 2 + 0.005)
            if on_x or on_y:
                edges.add(e)
        if edges.count != 4:
            raise RuntimeError("expected 4 slot mouth edges, found %d"
                               % edges.count)
        ch = comp.features.chamferFeatures
        chi = ch.createInput(edges, False)
        chi.setToEqualDistance(adsk.core.ValueInput.createByReal(0.5 * MM))
        ch.add(chi)
        print("usb slot mouth chamfer ok (0.5mm x 45deg on 4 edges)")
    except Exception as exc:
        print("USB MOUTH CHAMFER SKIPPED:", exc)

    if comp.bRepBodies.count != 1:
        raise RuntimeError("usb jack step split the plate: %d bodies"
                           % comp.bRepBodies.count)
    print("usb jack ok: slot %.2f x %.2f at (%.2f, %.2f), collar to %.2f, "
          "ramp %.2f->%.2f, tail channel %.2f"
          % (jW * 10, jT * 10, JCX * 10, JCY * 10, COLLAR_TOP * 10,
             RAMP_Z0 * 10, RAMP_Z1 * 10, (jT - 2 * RAMP_RISE) * 10))

    # 10. Bulk capacitor cradle (2026-09-09). The user's 100 uF electrolytic
    # (12 x 8.2 dia) sits across the incoming 5 V. It lies on its SIDE in the
    # +Y band, which is otherwise empty: standing it would put 12 mm into a
    # 14 mm cavity with the leads pointing at the lid, and its footprint only
    # fits the -Y band alongside the jack by about 0.1 mm.
    #
    # Two rib blocks with the cap's cylinder bored through them: 1.2 mm of
    # arm at the equator (two clean extrusions on the 0.6 mm nozzle),
    # thicker below, and a 7.0 mm opening at the rib top (z=8.0) so the cap
    # snaps down past its widest point.
    #
    # RIB X POSITIONS - what they must clear, in priority order:
    #
    #   1. THE LEGO TECHNIC BORES (2026-09-09 fix, final review). The ribs
    #      run y 11.25..22.25 at z 0..8, which crosses the y band of the
    #      through-bores at (0.95, +/-12): radius 2.45 puts that bore at
    #      x -1.50..3.40, y 9.55..14.45. The ribs were at x 3.0 and 12.8;
    #      the x=3.0 rib's footprint (x 2.40..3.60) therefore overlapped
    #      that bore by 1.00 mm in x over 3.20 mm in y and ROOFED about 11%
    #      of the bore's interior mouth for the rib's full 8 mm height. A
    #      Technic pin pushed in from the back would have bottomed out on
    #      the rib - one of the six mount holes silently unusable, and only
    #      discoverable after printing. Moved to x 5.0 and 14.8: same 9.8 mm
    #      rib span (the cap sits identically, just centred at x 9.9 instead
    #      of 7.9), and the -X rib's left edge is now x 4.40, a full 1.00 mm
    #      clear of the bore edge at x 3.40. 90_verify.check_lego_bores_clear
    #      now asserts this for all six bores so it cannot regress.
    #
    #   2. (Historical, 2026-09-09 - 2026-09-10.) The -X rib used to overlap
    #      the +Y clip's outboard trench (x 4.4..11.6, y 10.65..11.85,
    #      z -1.5..0) in plan, over y 11.25..11.85. That was harmless (rib
    #      z 0..8, trench z -1.5..0 - never the same space) and it is now
    #      moot: the clip trenches were deleted with the XIAO clip slots on
    #      2026-09-10, so the floor under the rib is plain solid plate.
    #      Constraint 1 is the only thing pinning RIB_X now, and it still
    #      pins it - do not move the ribs back toward x 3.0.
    #
    # Lead end faces +X. There is NO through-channel past the XIAO fence
    # there - the +/-Y fence bars run the full plate width to x 20.85 (only
    # the BOARD stops at x 19.23). The cap's leads reach the -Y band either
    # over the top of a fence bar (5 mm tall in a 14 mm cavity, so ~9 mm of
    # headroom) or through the +/-Y wire notches and across the bay above
    # the XIAO.
    capR = p(des, "capDia") / 2 + p(des, "capClear") / 2   # 4.3
    CAP_Y, CAP_Z = 16.75 * MM, 5.5 * MM
    RIB_T = 1.2 * MM
    RIB_R = capR + RIB_T                                   # 5.5
    RIB_TOP = CAP_Z + 2.5 * MM                             # 8.0 -> 7.0 mouth
    RIB_X = (5.0 * MM, 14.8 * MM)

    sk = comp.sketches.add(comp.xYConstructionPlane)
    for rx in RIB_X:
        box(sk, rx - RIB_T / 2, rx + RIB_T / 2,
            CAP_Y - RIB_R, CAP_Y + RIB_R)
    profs = collection([sk.profiles.item(i) for i in range(sk.profiles.count)])
    if profs.count != len(RIB_X):
        raise RuntimeError("expected %d cradle rib profiles, found %d"
                           % (len(RIB_X), profs.count))
    extrude(comp, profs, 0, RIB_TOP,
            adsk.fusion.FeatureOperations.JoinFeatureOperation,
            participants=[plate_body])

    # bore the cap's cylinder along X through both ribs. This is the ONLY
    # feature in this script that does not sketch on XY: the sketch sits on
    # a YZ-parallel plane offset to x = BORE_X0, whose normal is +X, so the
    # extrude sweeps along world X and the circle appears in section.
    #
    # Do NOT hand-map the circle's centre into sketch axes. Probed on the
    # live document: this plane's own geometry reports uDirection = world +Y
    # and vDirection = world +Z, but the SKETCH Fusion creates on it picks a
    # different basis - u = world -Z, v = world +Y. Writing the centre as
    # (CAP_Y, CAP_Z) therefore put it at world (y 5.5, z -16.75), in fresh
    # air below the plate, and the Cut silently removed nothing (the plate's
    # volume rose by exactly the two rib blocks). modelToSketchSpace asks
    # the sketch for its own mapping instead of assuming one.
    BORE_X0 = 1.0 * MM           # plane offset; ribs live at x 4.4..15.4
    BORE_LEN = 16.0 * MM         # sweep +X clear through both ribs (to 17.0;
    #                              was 14.0, which stopped at x 15.0 and would
    #                              have left 0.4 mm of the +X rib unbored once
    #                              the ribs moved +2 mm - the want_cut guard
    #                              below would have caught it, loudly)
    pl_inp = comp.constructionPlanes.createInput()
    pl_inp.setByOffset(comp.yZConstructionPlane,
                       adsk.core.ValueInput.createByReal(BORE_X0))
    pl = comp.constructionPlanes.add(pl_inp)
    pl.isLightBulbOn = False
    sk = comp.sketches.add(pl)
    want = adsk.core.Point3D.create(BORE_X0, CAP_Y, CAP_Z)
    circ = sk.sketchCurves.sketchCircles.addByCenterRadius(
        sk.modelToSketchSpace(want), capR)
    got = circ.worldGeometry.center
    if max(abs(got.x - want.x), abs(got.y - want.y),
           abs(got.z - want.z)) > 1e-6:
        raise RuntimeError(
            "cap bore circle landed at (%.3f, %.3f, %.3f) mm, wanted "
            "(%.3f, %.3f, %.3f) mm"
            % (got.x * 10, got.y * 10, got.z * 10,
               want.x * 10, want.y * 10, want.z * 10))

    # A cut that sweeps the wrong way, or lands off the ribs, removes nothing
    # and raises no error - the failure mode above. Check the volume actually
    # removed against the closed form: per rib, RIB_T times the part of the
    # bore circle below the rib top, i.e. the full circle less the segment
    # standing proud of RIB_TOP. (The circle's bottom, CAP_Z - capR = 1.2, is
    # above the plate floor, so nothing else limits it.)
    d = RIB_TOP - CAP_Z                                   # 2.5
    seg = capR ** 2 * math.acos(d / capR) - d * math.sqrt(capR ** 2 - d ** 2)
    want_cut = len(RIB_X) * RIB_T * (math.pi * capR ** 2 - seg)
    vol_before = plate_body.volume
    extrude(comp, sk.profiles.item(0), 0, BORE_LEN,
            adsk.fusion.FeatureOperations.CutFeatureOperation,
            participants=[plate_body])
    sk.isVisible = False
    cut = vol_before - plate_body.volume
    if abs(cut - want_cut) > 5e-4:      # 0.5 mm3
        raise RuntimeError("cap bore removed %.4f mm3, expected %.4f mm3"
                           % (cut * 1000, want_cut * 1000))

    if comp.bRepBodies.count != 1:
        raise RuntimeError("cap cradle split the plate: %d bodies"
                           % comp.bRepBodies.count)
    mouth = 2 * math.sqrt(capR ** 2 - d ** 2)
    print("cap cradle ok: ribs at x %s, bore r=%.2f at (y %.2f, z %.2f), "
          "arm %.2f, mouth %.2f at z %.2f (bore removed %.2f mm3)"
          % ([round(v * 10, 2) for v in RIB_X], capR * 10, CAP_Y * 10,
             CAP_Z * 10, RIB_T * 10, mouth * 10, RIB_TOP * 10, cut * 1000))

    # 11. Wire notches (2026-09-09). The jack's 5V/GND pair reaches the
    # XIAO's pads - user-confirmed on the long edge shared with D7, at the
    # end nearest the XIAO's own USB-C, i.e. x 14..18 - in about 10 mm
    # within the -Y band. This notch lets the pair drop straight down
    # instead of being pinched between the board edge and the fence wall.
    # Cut in BOTH walls: the standard pinout puts those pads on -Y, and
    # mirroring costs nothing if the board reads the other way round. Clear
    # of the clip fingers at x 4.5..11.5.
    NOTCH_X0, NOTCH_X1 = 14.5 * MM, 18.0 * MM
    NOTCH_Z0 = 2.5 * MM
    sk = comp.sketches.add(comp.xYConstructionPlane)
    for sy in (-1, 1):
        box(sk, NOTCH_X0, NOTCH_X1, sy * 9.05 * MM, sy * 10.75 * MM)
    profs = collection([sk.profiles.item(i) for i in range(sk.profiles.count)])
    if profs.count != 2:
        raise RuntimeError("expected 2 wire-notch profiles, found %d"
                           % profs.count)
    extrude(comp, profs, NOTCH_Z0, 5.1 * MM,
            adsk.fusion.FeatureOperations.CutFeatureOperation,
            participants=[plate_body])
    print("wire notches ok (x %.2f..%.2f, z %.2f..5.00, both fence walls)"
          % (NOTCH_X0 * 10, NOTCH_X1 * 10, NOTCH_Z0 * 10))

    print("BackPlate bodies:", comp.bRepBodies.count)
