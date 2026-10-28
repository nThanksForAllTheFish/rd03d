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
        # Radar bay side clearance (2026-10-26, from the user's print): the
        # fence walls' inner faces measured 15.68 apart for 15.60 modelled
        # (radarW 15.1 + 2 x boardClear 0.25; this cavity printed +0.08)
        # while the RD-03D PCB is 15.09 wide, so the board had 0.6 of side
        # play and the clip lips (0.85 projecting, printing about 0.65)
        # barely overlapped its edge. The radar bay uses this instead of
        # boardClear (the XIAO bay keeps boardClear): 0.10 a side -> 15.30
        # modelled, about 15.38 printed, 0.15 a side on the 15.09 board,
        # and the lips overlap the board edge by about 0.75 nominal.
        ("radarClear", "0.10 mm", "radar bay side clearance per side (X): fence inner faces at radarCx +/- (radarW/2 + this). Print 2026-10-26: 15.68 measured for 15.60 modelled with boardClear 0.25, PCB 15.09 -> 0.6 of play; 0.10 gives 0.15 a side printed. The XIAO bay keeps boardClear"),
        # Fit allowances from caliper measurements of the 9c print
        # (2026-10-25), replacing the single rimGap (0.15 a side, still in
        # the document, no longer read). Measured: plate outside X 41.53
        # for 41.7 modelled (0.17 under), plate outside Y 45.43 for 45.7
        # (0.27 under), shell cavity inside X 41.98 for 42.0 (true),
        # cavity inside Y 46.34 for 46.0 (0.34 OVER), wing width 26.46
        # for 26.7 (0.24 under), box cavity width 27.2 for 27.0 (0.2
        # over). So the gaps came out 0.45 total in X, 0.91 in Y, 0.74
        # wing-to-box; the target is 0.2 total (0.1 a side, a light push
        # fit). Rule on this printer: outside walls print 0.17..0.27
        # under, cavities true in X but 0.2..0.34 over in Y. Each
        # allowance is the per-side model gap that lands the printed gap
        # at 0.1 a side: (target total - (cavity over + outside under)) /
        # 2, and may be NEGATIVE (the model overlaps, the print does not).
        ("rimGapX", "0.03 mm", "plate half-width = intW/2 - this. X: cavity prints true (41.98 for 42), plate 0.17 under (41.53 for 41.7): (0.2 - 0.17 - 0) / 2 = 0.015 -> 0.03 (rounded up: 0.19 printed gap, light push)"),
        ("rimGapY", "-0.05 mm", "plate half-length = intH/2 - this. Reprint 2026-10-26: the plate printed 46.10 for 46.40 modelled (0.30 under) and the shell cavity measures 46.00 on this shell (the earlier 46.34 was another shell or spot), so at -0.20 the plate was 0.1 too long and needed force. Target 0.2 total: printed 45.80 -> modelled 46.10 -> -0.05 (the model's plate is 0.05 a side into the shell's +/-Y walls, 91 expects that overlap; printed edge 23.05 - 0.15 = 22.90 vs cavity 23.00, 0.1 a side). Was -0.20 from the first print's 45.43 / 46.34"),
        ("wingGap", "-0.12 mm", "wing half-width = pirBoxHalfY - this. Box cavity width prints 0.2 over (27.2 for 27.0), wing 0.24 under (26.46 for 26.7): (0.2 - 0.24 - 0.2) / 2 = -0.12; the same shrink is assumed for the 31 mm box of Task 9d. The wing's far end in X uses rimGapX (an outside wall against a cavity face in X)"),
        # PIR socket (step 14), the shell's pod box (03_shell.py step 5c)
        # and the bezel ring (03_shell.py step 8), fifth layout (Task 9e,
        # 2026-10-25): the sensor's axis is parallel to the radar's
        # (pirTilt 0), the plate carries only a straight, snug socket on
        # its wing, the shell's box covers it, and a thin ring dropped into
        # the lens gap from the front, clocked to the lens's latch tabs,
        # closes the gap and holds the lens ring by friction (no plug, no
        # keeper pin, no bayonet). Radii measured on Panasonic's STEP by
        # point probing (2026-10-11, re-probed 2026-10-25): base/can r 5.5
        # (calipers on the real part: 5.4), neck r 5.3 -> 5.0, flange
        # r 9.4 with its underside at sensor z 6.4, lens ring r 10.3 (top
        # at z 8.4), TWO lens latch tabs centred at 45/225 deg, 5.0 wide,
        # reaching r 11.0 over sensor z 6.2..8.4 (case 14.2..16), whose
        # hook lips (r 9.6..10.7) hang down to z 5.5; the dome's flank
        # just above the ring is r 10.35 (a 2 deg taper, then the R 10.89
        # cap above case z 19.8).
        ("pirBoreR", "5.55 mm", "socket bore radius (Ø11.1): the sensor's metal base measured Ø10.8 with calipers (the STEP says 11.0) and the printed Ø11.8 bore measured 11.8 (holes print true), i.e. 0.5 mm of radial play; 5.55 is 0.15 a side on the measured base. Was 5.9. The neck (r 5.3..5.0) passes"),
        ("pirSocketR", "7.7 mm", "socket boss outer radius: 2.15 mm wall round the r 5.55 bore; the flange (r 9.4) seats on its top rim and the latch hook lips (r 9.6..10.7) hang outside it"),
        ("pirSeatZ", "intD + wall - 2.0 mm", "socket boss top = the flange's underside (sensor z 6.4), 2.0 under the shell's face so the lens ring's top (sensor z 8.4) is flush with it (= 14.0)"),
        ("pirCx", "35.5 mm", "socket / lens axis x. 34.5 would centre it in the box, but the Technic hole at (24.95, 4) would then pass 0.20 mm from the boss's foot in plan; 35.5 gives 1.13 (step 14d asserts >= 0.6). The box in 03_shell.py follows"),
        ("pirBoxHalfY", "13.5 mm", "shell pod box: inner half-width in Y (walls outside it); the plate's wing is this less wingGap (13.5 again since Task 9e; 9d's bayonet lugs had it at 15.5)"),
        ("pirBoxHalfX", "13.5 mm", "shell pod box: cavity +X wall at pirCx + this (= 49); the wing ends rimGapX short of it. Separate from pirBoxHalfY since Task 9d"),
        ("pirHoleR", "11.65 mm", "lens hole radius in the shell's pod box top (Task 9e; 11.5 as pirRecessR in 9c, 12.8 in 9d): the lens ring (r 10.3) and latch tabs (r 11.0) pass, and the bezel ring's skirt (OD = this, an outside wall that prints 0.2 under in a true hole: 0.1 a side) is a light push fit in it. 11.65 so the skirt wall (this - pirBezelInnerR) is 1.25, two 0.6 lines"),
        ("pirTilt", "0 deg", "PIR axis tilt from the plate normal: 0 since 2026-10-25 (the PIR looks where the radar looks, max field overlap). Step 14 refuses anything else: a tilted axis needs the 9b tower, which is gone"),
        ("pirTiltSign", "1", "+1: XIAO end hangs DOWN on the wall (confirmed 2026-10-11); -1: up. Unused by the geometry while pirTilt is 0; the firmware reads the orientation"),
        ("pirWireDia", "3.0 mm", "wire hole out of the socket's -X side, level, into the pod cavity"),
        ("pirWireZ", "4.0 mm", "wire hole centre z: pin-tip level (sensor pins end at z 2.1; the cap standing on them reaches down to z -0.9), so the wires leave the pins radially through the hole"),
        # Bezel ring (03_shell.py step 8, Task 9e; its own frame: flange
        # underside on z 0 = the shell's face, axis +Z). A flat flange on
        # the face round the lens, two arc skirts below it filling the
        # lens hole, two notches 180 deg apart (through the skirt, and
        # as blind pockets in the flange's underside, so its top stays
        # whole) that the lens's two latch tabs sit in. Inserted
        # from the front clocked to the tabs; a light push fit in the hole
        # and round the lens ring; holds the lens ring by friction and
        # closes the gap. Nothing clamps along the axis (user's decision:
        # wall-mounted, horizontal axis, snug socket). Prints flange-down.
        ("pirBezelFlangeR", "12.5 mm", "bezel flange outer radius: 0.9 of face round the r 11.6 hole, 1.1 of bridge outside the flange notches (to r 11.4)"),
        ("pirBezelFlangeT", "1.5 mm", "bezel flange thickness (z 0..1.5 in the bezel frame, 16..17.5 in the case): the only part above the face; its top is continuous (the lens tabs are cleared by blind pockets in its underside, pirTabRelief), so 1.1 of solid flange stays over them"),
        ("pirTabRelief", "0.4 mm", "bezel: depth of the two blind relief pockets in the flange's underside over the lens tabs (r pirBezelInnerR..pirHoleR - 0.2, pirNotchW wide): the tab tops are at the face plane, so this is their clearance under the solid flange"),
        ("pirBezelInnerR", "10.40 mm", "bezel inner radius (flange and skirt): lens ring r 10.3 + 0.10, dome flank r 10.35 (at the face) + 0.05; the bore is an inside surface and prints true, so the ring just grips the lens"),
        ("pirBezelSkirtH", "2.0 mm", "bezel skirt height below the flange: the top's thickness (wall), so the skirt's foot is flush with the top's underside and above the latch hook lips (which hang to case z 13.1 under the tabs, in the notches anyway)"),
        ("pirBezelSkirtRo", "11.80 mm", "bezel skirt outer radius (Ø23.6), decoupled from the hole (pirHoleR 11.65, Ø23.3) on 2026-10-26: the first ring's skirt printed Ø22.79 for Ø23.3 modelled (0.5 under: a thin two-perimeter ring shrinks more than a wall) in a hole that printed Ø23.2, and was loose. Ø23.6 should print about 23.1 in the 23.2 hole; the model overlaps the hole by 0.15 a side and 91 expects that press-fit pair. Skirt wall = this - pirBezelInnerR = 1.40"),
        ("pirTabW", "5.0 mm", "lens latch tab tangential width, probed on the STEP 2026-10-25 (chord 5.04 at r 10.5, 5.00 at r 10.8; the tabs are at 45/225 deg in the sensor frame, r to 11.0, sensor z 6.2..8.4)"),
        ("pirNotchW", "pirTabW + 1 mm", "bezel notch tangential width (two, 180 deg apart, through the skirt and the flange's inner region): tab width + 0.5 a side (= 6.0)"),
        # Wing snap pair (Task 9d): the shell's +X-wall bumps and the
        # plate's +X-edge pockets (snapYpx, retired) are replaced by bumps
        # on the pod box's inner +/-Y walls (03_shell.py step 5d) into
        # blind pockets in the wing's +/-Y faces (step 14a'), so the lid
        # snaps at both ends as before.
        ("wingSnapX", "40 mm", "x centre of the wing snap pair (6 mm long along X): between the boss (to x 43.2 at y 0; the pockets are at the wing's +/-Y faces, far outside it) and the wing's corner fillets (from x 46.35)"),
        ("wingSnapZ", "-5.0 mm", "z centre of the wing snap pair: bumps +/-0.5, pockets +/-0.6, in the wing's z -8..-2 with 2.4 of wing above and below"),
        # LED light pipe (2026-10-27): the XIAO's yellow user LED (GPIO15,
        # flashed per published event) sits beside the B button between it
        # and the USB shell, on the 5V-column side. Measured on the user's
        # top-view photo against the 17.8 mm board width: 4.2 in from the
        # board's USB end (edge at x -1.72 -> x 2.5), 5.7 off the
        # centreline. After the 180 deg rotation the 5V column is +Y. The
        # hole is centred 0.3 further out (y 6.0) so a 3 mm pipe clears the
        # USB shell's footprint (|y| < 4.47, top z 7.46); the B button
        # under the outer half is only 0.5 tall. 03_shell.py step 7b.
        ("ledX", "2.5 mm", "XIAO user LED centre x in the case (board USB end at x -1.72, LED 4.2 inboard of it)"),
        ("ledY", "6.0 mm", "light-pipe hole centre y: LED at 5.7 on the 5V-column (+Y since the 2026-10-27 rotation) side, hole 0.3 further out to clear the USB shell footprint (|y| 4.47)"),
        # Corner rounding (2026-10-27, user's print review): an FDM printer
        # cannot make the cavity's sharp inside corner (it rounds to about
        # half the nozzle width or more) while the plate's outside corner
        # prints nearly sharp, so the plate bound on four points before
        # the flats touched. The plate's four corners are rounded (step 15)
        # to a larger radius than the cavity's modelled inside corners
        # (03_shell.py step 7c), which leaves a defined ~0.2 mm diagonal
        # gap: (sqrt(2) * (plateCornerR - cavityCornerR)) - (plateCornerR -
        # cavityCornerR) = 0.207 at 1.5 / 1.0.
        ("plateCornerR", "1.5 mm", "plate outside corner radius (four vertical corners); must exceed cavityCornerR"),
        ("cavityCornerR", "1.0 mm", "shell cavity inside corner radius, modelled so the printed corner is defined (a 0.6 nozzle rounds a sharp inside corner to r 0.3..0.5 anyway)"),
        ("ledPipeD", "3.0 mm", "light-pipe hole through the shell's front wall over the LED (a 3 mm clear rod; set 1.8 for a stub of 1.75 mm clear filament). Holes print true"),
    ]
    ups = des.userParameters
    for name, expr, comment in spec:
        if ups.itemByName(name) is None:
            unit = "deg" if "deg" in expr else ("" if expr.lstrip("-").isdigit() else "mm")
            ups.add(name, adsk.core.ValueInput.createByString(expr),
                    unit, comment)
            print("added param", name, "=", expr)


def run(_context: str):
    app = adsk.core.Application.get()
    des = adsk.fusion.Design.cast(app.activeProduct)
    root = des.rootComponent
    # parameters of the tilted layouts (the shell pod of 2026-10-11 and the
    # 9b wing tower of 2026-10-25 morning): recess depth, flange ledge,
    # hook groove, pod wall, sloped wire hole, shell notch top and the
    # along-the-axis pin depth; and (Task 9d, the bezel) the 9c plug,
    # keeper pin, +X snap pair position and the old lens hole radius
    # (pirRecessR -> pirHoleR); and (Task 9e, the plain ring) the 9d
    # bayonet bezel's lugs, lip, skirt radii and dome radius. Nothing
    # reads them any more; delete them so Change Parameters shows only
    # live values. Dependents first: pirPinZ is an expression on pirSeatD
    # / pirPlugL / pirPinDia, pirBezelLipH on pirDomeR / pirBezelLipR /
    # pirBezelPreload.
    for name in ("pirRecessD", "pirFlangeR", "pirHookD", "pirPodWall", "pirWireD",
                 "pirWireExitZ", "pirNotchTop", "pirPinD",
                 "pirPinZ", "pirPinDia", "pirPlugSlotW", "pirPlugL", "pirPlugID",
                 "pirPlugOD", "pirSeatD", "snapYpx", "pirRecessR",
                 "pirBezelLipH", "pirBezelLipR", "pirBezelPreload", "pirDomeR",
                 "pirNotchR", "pirLugT", "pirLugW", "pirLugRo",
                 "pirBezelSkirtRi", "pirBezelSkirtRo"):
        old = des.userParameters.itemByName(name)
        if old is not None:
            try:
                old.deleteMe()
                print("deleted obsolete param", name)
            except Exception as exc:  # still referenced by something: say so, carry on
                print("could not delete obsolete param %s: %s" % (name, exc))
    ensure_params(des)

    for occ in list(root.occurrences):
        name = occ.component.name
        if name.startswith(("BackPlate", "PirPlug")):
            # rename before deleting: the dead component keeps its name
            # reserved in the document's name registry (until save), which
            # would force the rebuilt component to "BackPlate (1)". PirPlug
            # (the 9c retaining plug) is gone since Task 9d (the bezel on
            # the shell side holds the sensor); a document that still has
            # one gets it removed here and nothing rebuilds it.
            occ.component.name = name + "_deleted"
            occ.deleteMe()
            print("removed existing", name)
        elif name.startswith(("EKMC", "PaPIRs")):
            # the PIR sensor placed by 91_pir_fit.py against the plate's
            # pod; it is re-imported against the rebuilt plate by re-running
            # that script
            occ.deleteMe()
            print("removed prior sensor import:", name)

    occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    comp = occ.component
    comp.name = "BackPlate"

    intW, intH = p(des, "intW"), p(des, "intH")
    backT = p(des, "backT")
    # fit allowances (see ensure_params): per-side model gaps, X and Y
    # differ and may be negative; rimGap itself is no longer read
    rimGapX, rimGapY, wingGap = p(des, "rimGapX"), p(des, "rimGapY"), p(des, "wingGap")
    rW, rH, rT = p(des, "radarW"), p(des, "radarH"), p(des, "radarT")
    rCx = p(des, "radarCx")
    xW, xH, xCx = p(des, "xiaoW"), p(des, "xiaoH"), p(des, "xiaoCx")
    postH, clear = p(des, "postH"), p(des, "boardClear")
    radarClear = p(des, "radarClear")            # the radar bay's X clearance (see ensure_params)
    intD, wall, winT = p(des, "intD"), p(des, "wall"), p(des, "windowT")
    MM = 0.1

    # 1. plate: intW - 2 rimGapX by intH - 2 rimGapY (41.94 x 46.1: the
    # +/-Y edges sit 0.05 INTO the shell's walls in the model, which the
    # measured Y shrink of the print takes back; 91_pir_fit.py expects
    # that overlap)
    sk = comp.sketches.add(comp.xYConstructionPlane)
    rect(sk, 0, 0, intW - 2 * rimGapX, intH - 2 * rimGapY)
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

    # 3. snap pockets at the plate's -X edge (BLIND: z -1.7..-0.3, leaving
    # material ledges at both z ends so the shell's bumps (z -1.6..-0.4)
    # are retained axially with 0.1mm slop per side), at y +/-12. The +X
    # pair (at y +/-19 outboard of the pod box for most of 2026-10-25,
    # snapYpx) is gone since Task 9d: the lid's +X end snaps into the
    # WING instead (pockets in its +/-Y faces, step 14a'; bumps on the
    # box's inner walls, 03_shell.py step 5d). The plate's +X edge is
    # plain again.
    sk = comp.sketches.add(comp.xYConstructionPlane)
    edge = -(intW / 2 - rimGapX)
    for sy in (-1, 1):
        # rect centered on the edge, 1.2 wide -> cuts 0.6 deep into plate
        rect(sk, edge, sy * 12 * MM, 0.12, 6.2 * MM)
    profs = collection([sk.profiles.item(i) for i in range(sk.profiles.count)])
    extrude(comp, profs, -1.7 * MM, -0.3 * MM,
            adsk.fusion.FeatureOperations.CutFeatureOperation,
            participants=[plate_body])
    print("snap pockets ok (-X at y +/-12; the +X pair is in the wing, step 14a')")

    # 4. radar bay: two +/-X side walls + end bars. (Thin-wall fix
    # 2026-09-07: the old full perimeter fence ring left 0.6 mm +/-Y wall
    # segments after the plate-outline trim - unprintable on a 0.6 mm
    # nozzle. The +/-Y restraint was two retention ribs inside the
    # FrontShell until 2026-10-27; the corner pins (6b) do it now. The
    # plate keeps only the 1.5 mm-thick +/-X walls, spanning the full old
    # ring extent in Y and still trimmed by the plate outline in step 6.)
    # bay width from radarClear (0.10 a side, measured print 2026-10-26);
    # the bay's length keeps boardClear (it only sets the walls' Y extent,
    # which the plate outline trims anyway). Everything below that is
    # built from bayW - the walls, the end bars, the 4b opening, the 5a
    # window, the three clips (8a) - follows.
    bayW, bayH = rW + 2 * radarClear, rH + 2 * clear
    t = 1.5 * MM
    RW_OUT, RW_IN = rCx - bayW / 2 - t, rCx - bayW / 2     # -X wall faces, -20.65 / -19.15
    RE_OUT, RE_IN = rCx + bayW / 2 + t, rCx + bayW / 2     # +X wall faces, -2.35 / -3.85
    sk = comp.sketches.add(comp.xYConstructionPlane)
    rect(sk, rCx - bayW / 2 - t / 2, 0, t, bayH + 2 * t)   # -X wall
    rect(sk, rCx + bayW / 2 + t / 2, 0, t, bayH + 2 * t)   # +X wall
    profs = collection([sk.profiles.item(i) for i in range(sk.profiles.count)])
    extrude(comp, profs, 0, 11 * MM,
            adsk.fusion.FeatureOperations.JoinFeatureOperation,
            participants=[plate_body])
    PCB_REAR_Z = 10.46 * MM      # measured bare-PCB rear face of the RD-03D
    # End bars (2026-10-27, user review of the 2026-10-26 print): carry the
    # board under its ENDS, where the rear side is bare PCB across the full
    # width (probed read-only on the placed vendor body: y -22.0..-20.7 and
    # y +19.8..+22.0 bare; the 5-pin connector starts at y -20.7 and reaches
    # z 6.64 over x -15.3..-9.3). The two crossbars at y -12 and +18.75 that
    # sat between rear components are gone, and with them the crossbar A
    # cable slot (old step 13) and the corner cable exit (old step 12): the
    # connector pocket is now open to the floor and the cable leaves through
    # the floor opening in the +X wall (step 4b/5a).
    #   -Y bar y -22.0..-20.8 (1.2 wide): 0.1 clear of the connector.
    #   +Y bar y +20.0..+22.0 (2.0 wide).
    # Both run the full bay width between the walls' inner faces and tie
    # into both walls. The board's ends overhang them by 0.02 (edge 22.02).
    ENDBARS = ((-21.4 * MM, 1.2 * MM),    # -Y: y -22.0..-20.8
               (21.0 * MM, 2.0 * MM))     # +Y: y +20.0..+22.0
    sk = comp.sketches.add(comp.xYConstructionPlane)
    for cy, w in ENDBARS:
        rect(sk, rCx, cy, bayW, w)
    profs = collection([sk.profiles.item(i) for i in range(sk.profiles.count)])
    extrude(comp, profs, 0, PCB_REAR_Z,
            adsk.fusion.FeatureOperations.JoinFeatureOperation,
            participants=[plate_body])
    print("radar bay ok (X walls + end bars bearing on the PCB ends; "
          "Y-location is the corner pins' job), bar top z(mm)=",
          round(PCB_REAR_Z * 10, 3), "board total thickness radarT(mm)=",
          round(rT * 10, 2))
    print("radar bay walls: inner faces x %.2f / %.2f (bay %.2f wide = radarW %.1f + 2 x "
          "radarClear %.2f), outer faces %.2f / %.2f"
          % (RW_IN * 10, RE_IN * 10, bayW * 10, rW * 10, radarClear * 10, RW_OUT * 10, RE_OUT * 10))

    # 4b. open the radar fence +X wall where the XIAO sits (2026-10-27: now
    # floor to top). The XIAO's USB end faces this wall since the 180 deg
    # rotation (04_boards.py), so nothing rests on the old 3 mm stub, and
    # the radar cable leaves the bay at FLOOR level through here instead
    # of over the top. Over |y| < 9.4 the wall's only remaining job was
    # that stub; the clip B and C stretches beyond |y| 9.4 are untouched.
    # The XIAO fence's -X wall (step 5, x -5.0..-3.5, z 0..5) is built
    # after this cut and keeps the XIAO's -X stop face at x -3.5; step 5a
    # windows it for the wires.
    nx0 = rCx + bayW / 2 - 0.01
    nx1 = rCx + bayW / 2 + 1.5 * MM + 0.01
    ny = xH / 2 + clear + 0.25 * MM
    sk = comp.sketches.add(comp.xYConstructionPlane)
    rect(sk, (nx0 + nx1) / 2, 0, nx1 - nx0, 2 * ny)
    extrude(comp, sk.profiles.item(0), -0.01 * MM, 11 * MM + 0.01,
            adsk.fusion.FeatureOperations.CutFeatureOperation,
            participants=[plate_body])
    print("radar fence +X wall opened floor to top over |y| < %.1f" % (ny * 10))

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

    # 5a. wire window (2026-10-27): the radar's 4-wire cable comes off the
    # connector, drops to the floor, runs under the board and through this
    # window in the XIAO fence's -X wall. The rotated XIAO's 5V, GND, 3V3
    # and D1 pads are at this -X end (5V/GND come up in the channels
    # beside the USB receptacle); D6 and D7 are at the +X end, so their
    # two wires run on under the board (it stands on 3 mm posts) to the
    # fence's open +X end. |y| < 3.5, z 0..5,
    # through the full 1.5 mm wall. Narrower than the USB-C receptacle
    # (8.9 wide) on purpose: the receptacle's shoulders stay the XIAO's -X
    # stop against the fence face at x -3.5.
    WIN_HALF_Y = 3.5 * MM
    fx0 = xCx - fW / 2 - t - 0.01            # fence outer face, -5.0
    fx1 = rCx + bayW / 2 + 1.5 * MM + 0.01   # through the old wall footprint too
    sk = comp.sketches.add(comp.xYConstructionPlane)
    box(sk, fx0, fx1, -WIN_HALF_Y, WIN_HALF_Y)
    extrude(comp, sk.profiles.item(0), -0.01 * MM, 5 * MM + 0.01,
            adsk.fusion.FeatureOperations.CutFeatureOperation,
            participants=[plate_body])
    print("wire window ok (XIAO fence -X wall, |y| < %.1f, z 0..5)" % (WIN_HALF_Y * 10))

    # 6. trim everything to the plate outline (the radar fence and the xiao
    # fence ±Y bars as drawn overhang the 41.7 x 45.7 plate; the shell's
    # interior walls occupy that space, so intersect with the plate footprint)
    sk = comp.sketches.add(comp.xYConstructionPlane)
    rect(sk, 0, 0, intW - 2 * rimGapX, intH - 2 * rimGapY)
    extrude(comp, sk.profiles.item(0), -backT, 11 * MM,
            adsk.fusion.FeatureOperations.IntersectFeatureOperation,
            participants=[plate_body])
    print("trimmed to plate outline")

    # 6b. LOCATING PINS (2026-10-27, user review): the RD-03D has two open
    # half-notches in diagonal corners of its PCB, radius 1.14, probed on
    # the placed vendor body at (-18.25, -21.40) and (-4.75, +21.30) in the
    # case frame (the other two corners are r 1.8 roundings, not holes).
    # A pin in each locates the board in Y and rotation; X is shared with
    # the bay walls at radarClear. This retires the shell's retention ribs
    # (03_shell.py 4b/4c, deleted the same day).
    #
    # O2.2 modelled (thin pillars print ~0.2 under: ~0.15 radial play in
    # the O2.28 notch), floor to z 12.4 (0.5 under the shell's 12.9 radome
    # step), top edge chamfered 0.4 as lead-in. Each pin is a D: cut flat
    # on the outboard side at |y| 22.0, the board's end line, which keeps
    # it inside the board's footprint and clear of the shell's +/-Y wall
    # (the shell is reprinted anyway: its boss moved, 03 step 5b). The
    # inboard side merges into the bay wall (x overlap 0.2) and the end
    # bar, so only 2 mm of pin stands free above the bar.
    #
    # Built AFTER step 6 because the outline trim only keeps z -backT..11.
    PIN_R = 1.1 * MM
    PIN_TOP = 12.4 * MM
    PIN_FLAT_Y = 22.0 * MM
    # the notch centres are symmetric about the board: 0.8 in from each
    # side edge, i.e. radarCx -/+ 6.75; keyed off rCx like the walls
    PIN_DX = 6.75 * MM
    PINS = ((rCx - PIN_DX, -21.40 * MM), (rCx + PIN_DX, 21.30 * MM))
    # each pin must merge into its bay wall (0.2 nominal at radarClear
    # 0.10); below 0.05 the pin would stand alone and flex
    pin_wall_overlap = (RW_IN - (PINS[0][0] - PIN_R))
    if pin_wall_overlap < 0.05 * MM - 1e-9:
        raise RuntimeError("locating pins overlap the bay walls by only %.2f mm: "
                           "radarClear too big" % (pin_wall_overlap * 10))
    for cx, cy in PINS:
        sy = 1 if cy > 0 else -1
        sk = comp.sketches.add(comp.xYConstructionPlane)
        sk.sketchCurves.sketchCircles.addByCenterRadius(
            adsk.core.Point3D.create(cx, cy, 0), PIN_R)
        # the flat: a line across the circle at the board's end line
        sk.sketchCurves.sketchLines.addByTwoPoints(
            adsk.core.Point3D.create(cx - 1.5 * MM, sy * PIN_FLAT_Y, 0),
            adsk.core.Point3D.create(cx + 1.5 * MM, sy * PIN_FLAT_Y, 0))
        # keep the inboard (larger) profile: its centroid lies toward y=0
        if sk.profiles.count != 2:
            raise RuntimeError("pin at (%.2f, %.2f): the flat should split the circle "
                               "into 2 profiles, got %d" % (cx * 10, cy * 10, sk.profiles.count))
        best, best_area = None, 0.0
        for i in range(sk.profiles.count):
            pr = sk.profiles.item(i)
            ap = pr.areaProperties()
            if abs(ap.centroid.y) < PIN_FLAT_Y and ap.area > best_area:
                best, best_area = pr, ap.area
        if best is None:
            raise RuntimeError("pin at (%.2f, %.2f): no inboard profile" % (cx * 10, cy * 10))
        extrude(comp, best, 0, PIN_TOP,
                adsk.fusion.FeatureOperations.JoinFeatureOperation,
                participants=[plate_body])
    # lead-in chamfer on each pin's top arc (nice-to-have; a square top
    # still locates). Select arc edges at z = PIN_TOP with radius PIN_R.
    try:
        edges = adsk.core.ObjectCollection.create()
        for e in plate_body.edges:
            g = e.geometry
            if (isinstance(g, adsk.core.Arc3D)
                    and abs(g.radius - PIN_R) < 0.005
                    and abs(g.center.z - PIN_TOP) < 0.005):
                edges.add(e)
        if edges.count != 2:
            raise RuntimeError("expected 2 pin top arcs, found %d" % edges.count)
        ch = comp.features.chamferFeatures
        chi = ch.createInput(edges, False)
        chi.setToEqualDistance(adsk.core.ValueInput.createByReal(0.4 * MM))
        ch.add(chi)
        print("locating pins ok (O%.1f at %s, top z %.1f, flat at |y| %.1f, 0.4 chamfer)"
              % (PIN_R * 20, [(round(x * 10, 2), round(y * 10, 2)) for x, y in PINS],
                 PIN_TOP * 10, PIN_FLAT_Y * 10))
    except Exception as exc:
        print("locating pins ok, PIN CHAMFER SKIPPED:", exc)

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
    # harmless but the ordering keeps that selection simple. The pins of
    # 6b, built before step 7, only add Arc3D edges of r 1.1, which the
    # step-7 Circle3D/r 2.45 filter cannot match).
    #
    # Measurement provenance (probed on the live vendor solids, not derived):
    #   RD-03D  PCB rear face z = 10.46 (rests on the end bars); PCB FRONT
    #           face - the antenna/patch plane - z = 11.70, flat across both
    #           board edges over the whole clip range; board x -19.05..-3.95,
    #           y +/-22.01. Its 45-degree IC protrudes to 12.95, but only over
    #           about x -15..-5, y -3..+3, i.e. nowhere near either edge.
    #   XIAO    PCB top z = 4.20, flat along both long edges (the header
    #           holes are further in at y ~ +/-7.5); board x -3.23..19.23,
    #           y +/-8.89. Edge castellations bite ~0.24 mm in at a ~2.54 mm
    #           pitch, so a lip reaching 0.34 mm past the edge still lands on
    #           solid board (0.10 mm) even where it crosses a castellation.
    #   Fence walls as built: radar +/-X walls x -20.65..-19.15 (inner
    #           face -19.15) and x -3.85..-2.35 (inner face -3.85) since
    #           radarClear 0.10 (2026-10-26; -20.8/-19.3 and -3.7/-2.2 with
    #           boardClear 0.25 before); XIAO +/-Y walls y +/-9.15..+/-10.65
    #           (inner faces +/-9.15), 1.5 thick. The radar clips below
    #           take the wall faces from RW_*/RE_* (step 4).
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
    # from the step-4b opening's edge (y=9.4) to the plate outline.
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
    # the lip (0.85) reaches past the board's edge (x -19.05 / -3.95,
    # probed on the vendor solid) by this much nominally; printed lips
    # come out about 0.2 shorter
    RADAR_BOARD_HALF = 7.55 * MM
    lip_overlap = R_LIP - ((rCx - RADAR_BOARD_HALF) - RW_IN)
    if lip_overlap < 0.05 - 1e-9:
        raise RuntimeError("radar clip lips overlap the board edge by only %.2f mm (need 0.5): "
                           "radarClear too big" % (lip_overlap * 10))
    print("  radar clip lips reach %.2f mm over the board's edges (lip %.2f, wall to board %.2f)"
          % (lip_overlap * 10, R_LIP * 10, ((rCx - RADAR_BOARD_HALF) - RW_IN) * 10))

    # A - LEFT wall, finger centred on y=0. This is the radar IC's y band,
    # which is exactly why it is free: the shell keeps its front inner face
    # at 14.0 over y -4..+4 (the radome step in 03_shell.py skips that band
    # for the IC), so a 12.50 clip top has 1.50 mm of headroom.
    clip(comp, plate_body, "x", RW_OUT, RW_IN,
         -3.5 * MM, 3.5 * MM,
         NO_SLOTS,
         R_SLOT_Z0, R_RAISE_Z0, R_TOP_Z, R_LIP_Z, R_LIP, label="radar A -X")

    # The +X wall cannot carry a clip at y=0: step 4b opens it floor to top
    # over |y| < 9.4 (since 2026-10-27; before that it was cut down to
    # z=postH) because the XIAO board (x -3.23..19.23) crosses the wall's
    # x -3.7..-2.2 footprint. So the two +X clips take
    # the two full-height stretches of that wall, one under each radome
    # zone, each placed to sit CLEAR of an end bar - a bar runs the full
    # bay width and butts into both walls, so a lip band over one would be
    # locally braced and would not flex (crossbars, same rule, until
    # 2026-10-27).
    #
    # B - +X wall under the TX radome. The -Y end bar occupies y -22.0..-20.8
    # (2026-10-27), so the band starts at -20.0 (0.8 mm clear, same rule as
    # the old 0.7 to crossbar A) and runs to -13.0; crossbar A is gone, so
    # nothing bounds it on the +Y side before the 4b opening at -9.4.
    clip(comp, plate_body, "x", RE_OUT, RE_IN,
         -20.0 * MM, -13.0 * MM,
         NO_SLOTS,
         R_SLOT_Z0, R_RAISE_Z0, R_TOP_Z_PX, R_LIP_Z, R_LIP,
         label="radar B +X")

    # C - +X wall under the RX radome, in the free stretch between the
    # step-4b opening's edge (y=9.4) and the +Y end bar (y +20.0..+22.0):
    # y +10.0..+17.0 leaves 0.60 mm to the opening and 3.0 mm to the bar
    # (it was 0.70 to crossbar B until 2026-10-27; the span is unchanged).
    clip(comp, plate_body, "x", RE_OUT, RE_IN,
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
    # 2026-09-10: the user reports the printed ribs look fragile. RIB_W (the
    # rib's width along X) doubles 1.2 -> 2.4 mm - four perimeters on a 0.6
    # nozzle instead of two, and twice the arm section. RIB_ARM (the radial
    # arm thickness at the equator) deliberately stays 1.2: it sets RIB_R and
    # therefore the rib's Y extent, and at 1.5 the block would run y
    # 10.95..22.55, leaving only 0.3 mm to both the XIAO fence and the plate
    # edge. Widening in X is linear in stiffness, thickening radially is
    # cubic - but the cubic one is the one with nowhere to go.
    RIB_W = 2.4 * MM             # rib width along X
    RIB_ARM = 1.2 * MM           # radial arm thickness at the equator
    RIB_R = capR + RIB_ARM                                 # 5.5
    RIB_TOP = CAP_Z + 2.5 * MM                             # 8.0 -> 7.0 mouth
    # -X rib nudged 5.0 -> 5.6 so the wider block still clears the LEGO bore
    # at (0.95, +12) by 1.00 mm: the bore reaches x 3.40 and the rib now
    # spans x 4.40..6.80. Span 9.2 mm, cap centred at x 10.2.
    RIB_X = (5.6 * MM, 14.8 * MM)

    sk = comp.sketches.add(comp.xYConstructionPlane)
    for rx in RIB_X:
        box(sk, rx - RIB_W / 2, rx + RIB_W / 2,
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
    BORE_X0 = 1.0 * MM           # plane offset; ribs live at x 4.4..16.0
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
    # removed against the closed form: per rib, RIB_W times the part of the
    # bore circle below the rib top, i.e. the full circle less the segment
    # standing proud of RIB_TOP. (The circle's bottom, CAP_Z - capR = 1.2, is
    # above the plate floor, so nothing else limits it.)
    d = RIB_TOP - CAP_Z                                   # 2.5
    seg = capR ** 2 * math.acos(d / capR) - d * math.sqrt(capR ** 2 - d ** 2)
    want_cut = len(RIB_X) * RIB_W * (math.pi * capR ** 2 - seg)
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
             CAP_Z * 10, RIB_W * 10, mouth * 10, RIB_TOP * 10, cut * 1000))

    # 11: (deleted 2026-09-10) the 3.5 x 2.5 mm wire notches in both XIAO
    # fence walls at x 14.5..18.0. They were defensive and cost more than
    # they gave. The wall top is z 5.00 and the XIAO's pads are at 4.20, so a
    # wire laid over the wall climbs 0.8 mm with ~9 mm of headroom to the
    # shell - the notch only ever saved that climb. Meanwhile the clip
    # rework (8b) removed the isolating slots, so the finger's stiffness now
    # comes from being continuous with the wall either side of it, and a
    # notch 3 mm past the finger's end at x 11.5 is a discontinuity in
    # exactly that load path. The radar cable reaches the XIAO through the
    # step-5a floor window (over the top via the 4b notch before 2026-10-27)
    # and never needed these either.

    # 12/13. (deleted 2026-10-27) the corner cable exit and the crossbar A
    # cable slot: crossbar A is gone (step 4) and the cable leaves at floor
    # level through the step-4b opening and the step-5a window.

    # 14. PIR SOCKET ON A WING (2026-10-25, fourth layout, Task 9d).
    # History: the pod lived on the front shell's +X wall from 2026-10-11
    # (03_shell.py, up to commit 582091f); after the first test print it
    # moved to a tower on the plate's wing, tilted 18 deg with a canted
    # top (9b, same day); two user decisions then fixed the straight
    # socket-in-a-box layout (9c, commit 71b7312): the PIR looks where the
    # radar looks (pirTilt 0, maximum field overlap), and the plate only
    # HOLDS the sensor while the shell carries the housing (its pod box,
    # 03_shell.py step 5c, replaces the +X wall over the pod's width).
    # After 9c's print the user wanted the gap round the lens closed and a
    # part fitted from the FRONT instead of the back-side plug: 9d tried
    # a bayonet bezel clamping the dome, 9e (same day) settled on a thin
    # ring in the lens gap clocked to the lens tabs (03_shell.py step 8),
    # so 9c's retaining plug (PirPlug) and its filament keeper pin are
    # gone, the bore is BLIND at the wing top and snug on the base, and
    # the +X snap pair moved into the wing.
    #
    # Shape (case frame; the plate's occurrence is at identity):
    #   wing    z -8..-2 (6 mm, coplanar with the plate's back), from the
    #           plate's +X edge (x 20.97, fused to it) out to the box
    #           cavity's +X wall less rimGapX (x 48.97), y +/-(pirBoxHalfY
    #           - wingGap) = +/-13.62, so it sits in the shell's box like
    #           the plate sits in the shell (the fit allowances are
    #           measured, see ensure_params; the wing is 0.12 a side into
    #           the box walls in the model). Blind snap pockets in its
    #           +/-Y faces (14a') take the box's bumps.
    #   boss    a straight cylinder r pirSocketR (7.7) at (pirCx, 0),
    #           standing on the wing from z -2 up to pirSeatZ (14.0): the
    #           sensor drops in from the FRONT, neck and can into the bore,
    #           and its flange's underside (r 9.4) seats on the boss's top
    #           rim; the lens's latch hook lips (r 9.6..10.7, down to
    #           z 13.1) hang outside the boss. The lens ring and tabs are
    #           in the shell's lens hole above, the ring's top flush with
    #           the shell's face, with the bezel ring in the gap round it.
    #   cuts    bore r pirBoreR along Z from above the boss top down to the
    #           WING TOP (z -2) only: the pins (to case z 2.1) and the
    #           decoupling cap standing on them (to about z -0.9) hang in
    #           it with the floor 1.1 mm below; level wire hole dia
    #           pirWireDia along -X from the bore at z pirWireZ, out of the
    #           boss's side into the pod cavity.
    #   holes   two more Technic holes in the wing at (24.95, +/-4), on the
    #           8 mm grid, THROUGH the wing (a pin stands 2 mm proud into
    #           the pod cavity, which is empty there).
    #
    # MUST come after step 6 (the plate-outline Intersect would trim the
    # wing off) and after step 7 (whose chamfer counts the rear bore edges
    # and expects six).
    boreR, socketR = p(des, "pirBoreR"), p(des, "pirSocketR")
    seatZ, pirCx = p(des, "pirSeatZ"), p(des, "pirCx")
    boxHalfY = p(des, "pirBoxHalfY")
    wireR, wireZ = p(des, "pirWireDia") / 2, p(des, "pirWireZ")
    snapX, snapZ = p(des, "wingSnapX"), p(des, "wingSnapZ")
    snap = p(des, "snapBump")
    # Fusion hands angle parameters back in radians; the geometry below is
    # only right for an upright axis, so refuse anything else rather than
    # silently building a straight socket for a tilted sensor.
    if abs(p(des, "pirTilt")) > 1e-9:
        raise RuntimeError("pirTilt is %.3f, not 0: the straight socket (step 14) has no "
                           "tilt; set it to 0 deg (the 9b tilted tower is gone)"
                           % p(des, "pirTilt"))
    xEdge = intW / 2 - rimGapX                   # plate's +X edge, 20.97
    xBoxIn = pirCx + p(des, "pirBoxHalfX")       # box cavity's +X wall, 49
    xWing1 = xBoxIn - rimGapX                    # wing's far end, 48.97
    wingHalfY = boxHalfY - wingGap               # 15.62 (0.12 INTO the box walls, see wingGap)
    WING_T = 6.0 * MM
    zTop, zBack = intD + wall, -backT            # 16, -8
    zWing = zBack + WING_T                       # -2: wing top = the bore floor
    # the sensor in the socket (91_pir_fit.py places it the same way): its
    # origin (metal base plane) at zTop - 8.4 (ring top on the face); pins
    # end at sensor z -5.5 and the cap soldered standing on them (user
    # photo, 2026-10-25: top about 8.5 mm above the base) at about -8.5
    SENSOR_ORIGIN_Z = zTop - 8.4 * MM            # 7.6
    PIN_TIP_Z = SENSOR_ORIGIN_Z - 5.5 * MM       # 2.1
    CAP_BOTTOM_Z = SENSOR_ORIGIN_Z - 8.5 * MM    # -0.9

    # sensor-driven guards (radii from the STEP probe, see ensure_params)
    HOOK_LIP_R = 9.6 * MM                        # latch hook lips' inner radius
    if socketR > HOOK_LIP_R - 0.03:
        raise RuntimeError("pirSocketR %.2f is not 0.3 mm inside the latch hook lips (r 9.6)"
                           % (socketR * 10))
    if socketR < boreR + 0.15:
        raise RuntimeError("pirSocketR %.2f leaves under 1.5 mm of boss wall round the "
                           "r %.2f bore" % (socketR * 10, boreR * 10))
    if not (zWing < seatZ < zTop):
        raise RuntimeError("pirSeatZ %.2f is not between the wing top and the shell face"
                           % (seatZ * 10))
    if pirCx - socketR < intW / 2 + 0.3:
        raise RuntimeError("socket boss reaches x %.2f, under 3 mm from the shell's old "
                           "wall line (21)" % ((pirCx - socketR) * 10))
    if pirCx + socketR > xWing1 - 0.1:
        raise RuntimeError("socket boss runs past the wing's far end")
    # the blind bore's floor (the wing top) must clear the cap on the pins
    # by >= 1 mm, or the sensor would stand on the cap instead of seating
    # its flange on the boss rim
    if CAP_BOTTOM_Z - zWing < 0.1 - 1e-9:
        raise RuntimeError("bore floor z %.1f is %.2f mm under the cap on the pins (z %.1f); "
                           "need 1.0" % (zWing * 10, (CAP_BOTTOM_Z - zWing) * 10,
                                         CAP_BOTTOM_Z * 10))

    # 14a. wing, overlapping 0.5 mm into the plate so the Join merges by
    # volume; the plate is solid there (the -X snap pockets are at the far
    # edge; the jack is at y < -17 and the wing reaches +/-13.62 at the
    # plate's edge, where the jack slot's +X wall at x 18.265 is 2.7 mm
    # inboard).
    sk = comp.sketches.add(comp.xYConstructionPlane)
    box(sk, xEdge - 0.5 * MM, xWing1, -wingHalfY, wingHalfY)
    extrude(comp, sk.profiles.item(0), zBack, zWing,
            adsk.fusion.FeatureOperations.JoinFeatureOperation,
            participants=[plate_body])
    # 14b. socket boss, overlapping 0.5 mm down into the wing
    sk = comp.sketches.add(comp.xYConstructionPlane)
    sk.sketchCurves.sketchCircles.addByCenterRadius(
        adsk.core.Point3D.create(pirCx, 0.0, 0), socketR)
    extrude(comp, sk.profiles.item(0), zWing - 0.5 * MM, seatZ,
            adsk.fusion.FeatureOperations.JoinFeatureOperation,
            participants=[plate_body])
    if comp.bRepBodies.count != 1:
        raise RuntimeError("pir wing/boss did not merge with the plate: %d bodies"
                           % comp.bRepBodies.count)
    print("pir wing ok (x %.2f..%.2f, y +/-%.2f, z %.0f..%.0f); socket boss r %.2f "
          "(bore r %.2f, wall %.2f) at (%.1f, 0), z %.0f..%.1f"
          % (xEdge * 10, xWing1 * 10, wingHalfY * 10, zBack * 10, zWing * 10,
             socketR * 10, boreR * 10, (socketR - boreR) * 10, pirCx * 10,
             zWing * 10, seatZ * 10))

    # 14a'. WING SNAP POCKETS (Task 9d): the same section as the plate's
    # -X pockets (step 3) - 6.2 long, 1.4 tall, blind at both z ends, and
    # deep enough to clear the bump (see POCKET_D below; 0.72 with the
    # measured allowances) - cut into the wing's +/-Y faces, centred on (wingSnapX,
    # wingSnapZ), for the bumps on the pod box's inner +/-Y walls
    # (03_shell.py step 5d: 0.5 proud, 6 long, 1.0 tall). The lid comes
    # down over the wing from the front, the box walls ride over the
    # wing's edge and click in here. Guards: pocket inside the wing's x
    # span with 1 mm to the plate edge and clear of the corner fillets,
    # >= 1 mm of wing above and below it, and its floor outside the boss's
    # foot fillet toe and the Technic counterbores.
    # Depth: with the measured wingGap NEGATIVE (the wing is 0.12 a side
    # into the box walls in the model) a 0.6 pocket like the plate's
    # would put its floor (15.02) 0.02 INSIDE the bump's tip (15.0), so
    # the depth is derived: the bump's proud amount, plus 0.1 of floor
    # clearance, plus whatever the wing overlaps the wall by (0.72 here).
    # Printed, the wing's face shrinks 0.12 to 15.5 and the cavity grows
    # 0.1, so the bump overlaps the face line by about 0.4 (the
    # retention) and the floor stays clear.
    POCKET_D = snap + 0.01 + max(-wingGap, 0.0)
    POCKET_HL, POCKET_HZ = 3.1 * MM, 0.6 * MM
    if boxHalfY - snap < wingHalfY - POCKET_D + 0.01 - 1e-6:
        raise RuntimeError("wing bump tip (y %.2f) is under 0.1 off the pocket floor (y %.2f)"
                           % ((boxHalfY - snap) * 10, (wingHalfY - POCKET_D) * 10))
    corner = p(des, "cornerFillet")
    if not (xEdge + 0.1 <= snapX - POCKET_HL and snapX + POCKET_HL <= xWing1 - corner - 0.05):
        raise RuntimeError("wing snap pocket x %.2f..%.2f is not inside the wing's straight "
                           "+/-Y faces (x %.2f..%.2f)"
                           % ((snapX - POCKET_HL) * 10, (snapX + POCKET_HL) * 10,
                              (xEdge + 0.1) * 10, (xWing1 - corner - 0.05) * 10))
    if not (zBack + 0.1 <= snapZ - POCKET_HZ and snapZ + POCKET_HZ <= zWing - 0.1):
        raise RuntimeError("wing snap pocket z %.2f..%.2f leaves under 1 mm of wing above "
                           "or below it" % ((snapZ - POCKET_HZ) * 10, (snapZ + POCKET_HZ) * 10))
    if wingHalfY - POCKET_D < socketR + 0.1 + 0.1:
        raise RuntimeError("wing snap pocket floor (y %.2f) is inside the boss foot fillet's "
                           "toe (r %.2f) + 1 mm" % ((wingHalfY - POCKET_D) * 10, (socketR + 0.1) * 10))
    sk = comp.sketches.add(comp.xYConstructionPlane)
    for sy in (-1, 1):
        # rect centred on the wing's face, 1.2 wide -> cuts 0.6 deep
        box(sk, snapX - POCKET_HL, snapX + POCKET_HL,
            sy * (wingHalfY - POCKET_D), sy * (wingHalfY + POCKET_D))
    profs = collection([sk.profiles.item(i) for i in range(sk.profiles.count)])
    if profs.count != 2:
        raise RuntimeError("expected 2 wing pocket profiles, found %d" % profs.count)
    extrude(comp, profs, snapZ - POCKET_HZ, snapZ + POCKET_HZ,
            adsk.fusion.FeatureOperations.CutFeatureOperation,
            participants=[plate_body])
    if comp.bRepBodies.count != 1:
        raise RuntimeError("wing snap pockets split the plate: %d bodies" % comp.bRepBodies.count)
    print("wing snap pockets ok: x %.1f..%.1f, z %.1f..%.1f, %.1f deep into the wing's "
          "+/-Y faces (y +/-%.2f), floor at y +/-%.2f"
          % ((snapX - POCKET_HL) * 10, (snapX + POCKET_HL) * 10,
             (snapZ - POCKET_HZ) * 10, (snapZ + POCKET_HZ) * 10, POCKET_D * 10,
             wingHalfY * 10, (wingHalfY - POCKET_D) * 10))

    # 14c. the cuts, one Combine restricted to the plate body:
    #   bore   r boreR along Z from above the boss top down to the wing
    #          top, z -2 (BLIND since Task 9d: no plug goes in from the
    #          back any more; the bezel holds the sensor from the front).
    #          The pin tips (z 2.1) and the cap on them (to z -0.9) hang
    #          free above the floor.
    #   wire   dia pirWireDia, level, along -X from the bore axis at
    #          z pirWireZ, through the boss's -X wall and 1 mm past its
    #          outer face into the pod cavity (air), at the level of the
    #          pin tips / the cap on the pins, so the wires leave the pins
    #          radially; the only way out of the blind bore.
    # Guard: the wire hole must sit inside the bore's blind span, above
    # the floor and below the seat.
    if not (zWing + 0.05 < wireZ - wireR and wireZ + wireR < seatZ - 0.1):
        raise RuntimeError("wire hole z %.2f..%.2f is not inside the bore's span z %.2f..%.2f"
                           % ((wireZ - wireR) * 10, (wireZ + wireR) * 10,
                              zWing * 10, seatZ * 10))
    # (all parameters are read above: inside a base feature the design is
    # in direct-modelling mode and userParameters raises)
    tbm = adsk.fusion.TemporaryBRepManager.get()
    base = comp.features.baseFeatures.add()
    base.startEdit()
    bore_cyl = tbm.createCylinderOrCone(
        adsk.core.Point3D.create(pirCx, 0.0, zTop + 0.05), boreR,
        adsk.core.Point3D.create(pirCx, 0.0, zWing), boreR)
    wire_cyl = tbm.createCylinderOrCone(
        adsk.core.Point3D.create(pirCx, 0.0, wireZ), wireR,
        adsk.core.Point3D.create(pirCx - socketR - 0.1, 0.0, wireZ), wireR)
    for b in (bore_cyl, wire_cyl):
        comp.bRepBodies.add(b, base)
    base.finishEdit()
    # the proxies returned by bRepBodies.add() go stale when the edit
    # closes (Combine fails with ALL_TOOL_BODY_REFERENCE_LOST); use the
    # base feature's own body list instead
    tools = [base.bodies.item(i) for i in range(base.bodies.count)]
    if len(tools) != 2:
        raise RuntimeError("expected 2 pir tool bodies, found %d" % len(tools))
    ci = comp.features.combineFeatures.createInput(plate_body, collection(tools))
    ci.operation = adsk.fusion.FeatureOperations.CutFeatureOperation
    ci.isKeepToolBodies = False
    comp.features.combineFeatures.add(ci)
    if comp.bRepBodies.count != 1:
        raise RuntimeError("pir socket cuts split the plate: %d bodies" % comp.bRepBodies.count)
    print("pir bore r=%.2f along Z at (%.1f, 0) from the boss top (z %.1f) BLIND to the "
          "wing top (z %.1f); pin tips at z %.1f, cap on the pins to z %.1f, %.1f mm "
          "above the floor; flange seat on the boss rim r %.2f..%.2f at z %.1f ok"
          % (boreR * 10, pirCx * 10, seatZ * 10, zWing * 10, PIN_TIP_Z * 10,
             CAP_BOTTOM_Z * 10, (CAP_BOTTOM_Z - zWing) * 10, boreR * 10, socketR * 10,
             seatZ * 10))
    print("pir wire hole dia %.1f level at z %.1f (rim z %.2f..%.2f) along -X from the "
          "bore, out of the boss's side at x %.2f into the pod cavity ok"
          % (wireR * 20, wireZ * 10, (wireZ - wireR) * 10, (wireZ + wireR) * 10,
             (pirCx - socketR) * 10))
    # (the 9c keeper pin cross-hole through the wing at (pirCx, -4.75) is
    # gone with the plug: the wing is solid under the bore floor)

    # 14c'. FOOT FILLET (2026-10-25, review): a 1.0 mm concave fillet where
    # the boss meets the wing top, so a side knock on the 16 mm post does
    # not crack it at the joint. Concave, on a vertical cylinder over a
    # horizontal face, so it prints as ordinary layers. Its toe (r 8.7)
    # stays 0.13 mm clear of the Technic holes' rims in plan (they are
    # 1.13 from the boss, 14d) and well under the wire hole (z >= 2.5).
    FOOT_R = 1.0 * MM
    foot = [e for e in plate_body.edges
            if isinstance(e.geometry, adsk.core.Circle3D)
            and abs(e.geometry.radius - socketR) < 0.005
            and abs(e.geometry.center.z - zWing) < 0.005
            and abs(e.geometry.center.x - pirCx) < 0.005
            and abs(e.geometry.center.y) < 0.005]
    if len(foot) != 1:
        raise RuntimeError("expected 1 boss foot edge (circle r %.2f at z %.1f), found %d"
                           % (socketR * 10, zWing * 10, len(foot)))
    fil = comp.features.filletFeatures
    finp = fil.createInput()
    try:
        finp.edgeSetInputs.addConstantRadiusEdgeSet(
            collection(foot), adsk.core.ValueInput.createByReal(FOOT_R), False)
    except AttributeError:  # older API shape
        finp.addConstantRadiusEdgeSet(
            collection(foot), adsk.core.ValueInput.createByReal(FOOT_R), False)
    fil.add(finp)
    if comp.bRepBodies.count != 1:
        raise RuntimeError("boss foot fillet split the plate: %d bodies" % comp.bRepBodies.count)
    print("pir boss foot fillet ok (r %.1f mm, concave, on 1 edge; toe at r %.1f)"
          % (FOOT_R * 10, (socketR + FOOT_R) * 10))

    # 14d. two more Technic holes in the wing, on the step-7 grid (x = 0.95
    # + 3*8 = 24.95, y +/-4), the same pattern as step 7: legoHole bore
    # THROUGH the 6 mm wing (open into the pod cavity above it, where a pin
    # stands 2 mm proud in empty space), legoCbDia x legoCbDepth
    # counterbore on the back face, 0.3 mm entry chamfer. Clearances, all
    # measured in plan between circles: the bore to the socket boss's foot
    # (>= 0.6 mm, so a pin's proud end never rubs the boss: this is what
    # moved pirCx from 34.5 to 35.5, 0.20 -> 1.13), the counterbore to the
    # socket bore (>= 0.6 mm of wing; the bore is blind at the wing top
    # since Task 9d, so in the wing itself only the counterbore matters,
    # but the guard is kept as a plan-view rule).
    wx = x1 + 3 * pitch                           # 24.95
    wing_centers = [(wx, s * pitch / 2) for s in (-1, 1)]
    dc = math.hypot(pirCx - wx, pitch / 2)        # hole centre to the axis
    gap_boss = dc - socketR - holeD / 2
    gap_bore = dc - boreR - cbD / 2
    for label, gap in (("socket boss foot", gap_boss), ("socket bore", gap_bore)):
        if gap < 0.06 - 1e-9:
            raise RuntimeError("wing Technic holes at (%.2f, +/-%.0f) are %.2f mm from the "
                               "%s (need 0.6): move pirCx" % (wx * 10, pitch / 2 * 10, gap * 10, label))
    if wx - cbD / 2 <= xEdge + 0.05:
        raise RuntimeError("wing Technic counterbores reach the plate's edge")

    def wing_circles(radius):
        sk = comp.sketches.add(comp.xYConstructionPlane)
        for cx, cy in wing_centers:
            sk.sketchCurves.sketchCircles.addByCenterRadius(
                adsk.core.Point3D.create(cx, cy, 0), radius)
        return collection([sk.profiles.item(i)
                           for i in range(sk.profiles.count)])

    extrude(comp, wing_circles(holeD / 2), -backT, zWing + 0.1 * MM,
            adsk.fusion.FeatureOperations.CutFeatureOperation,
            participants=[plate_body])
    extrude(comp, wing_circles(cbD / 2), -backT, -backT + cbZ,
            adsk.fusion.FeatureOperations.CutFeatureOperation,
            participants=[plate_body])
    try:
        edges = adsk.core.ObjectCollection.create()
        for e in plate_body.edges:
            g = e.geometry
            if (isinstance(g, adsk.core.Circle3D)
                    and abs(g.radius - holeD / 2) < 0.005
                    and abs(g.center.z - (-backT + cbZ)) < 0.005
                    and g.center.x > xEdge):
                edges.add(e)
        if edges.count != 2:
            raise RuntimeError("expected 2 wing bore edges, found %d"
                               % edges.count)
        ch = comp.features.chamferFeatures
        chi = ch.createInput(edges, False)
        chi.setToEqualDistance(adsk.core.ValueInput.createByReal(0.3 * MM))
        ch.add(chi)
        print("wing rear entry chamfers ok (0.3mm x 45deg on 2 edges)")
    except Exception as exc:  # counterbore alone is acceptable
        print("WING CHAMFER SKIPPED:", exc)
    if comp.bRepBodies.count != 1:
        raise RuntimeError("wing Technic holes split the plate: %d bodies"
                           % comp.bRepBodies.count)
    print("wing technic holes ok:",
          [(round(cx / MM, 2), round(cy / MM, 2)) for cx, cy in wing_centers],
          "through the %.0f mm wing; plan clearance to the socket boss %.2f mm, "
          "counterbore to the bore %.2f mm"
          % (WING_T * 10, gap_boss * 10, gap_bore * 10))

    # 14d'. SOFTEN THE WING'S EDGES: the same treatment the shell gets in
    # 03_shell.py steps 6a-6c, so the two parts match in the hand. After
    # all the cuts, so the selectors see the final topology (the snap
    # pockets in the +/-Y faces, 14a', touch neither the back rim at z -8
    # nor the far corners). Fillet features act on the plate
    # body's edges only, so they are participant-safe by construction. The
    # boss keeps every edge sharp: the flange seats on its top rim.
    EPS = 0.005                                   # 0.05 mm (cm)
    corner = p(des, "cornerFillet")
    soft = p(des, "softFillet")

    def near(a, b):
        return abs(a - b) < EPS

    def mid(g):
        return ((g.startPoint.x + g.endPoint.x) / 2,
                (g.startPoint.y + g.endPoint.y) / 2,
                (g.startPoint.z + g.endPoint.z) / 2)

    def line_dir(g):
        v = g.startPoint.vectorTo(g.endPoint)
        v.normalize()
        return v

    def add_fillet(edges, radius, label):
        fil = comp.features.filletFeatures
        inp = fil.createInput()
        rv = adsk.core.ValueInput.createByReal(radius)
        try:
            inp.edgeSetInputs.addConstantRadiusEdgeSet(collection(edges), rv, False)
        except AttributeError:  # older API shape
            inp.addConstantRadiusEdgeSet(collection(edges), rv, False)
        feat = fil.add(inp)
        if comp.bRepBodies.count != 1:
            raise RuntimeError("%s split the plate: %d bodies" % (label, comp.bRepBodies.count))
        return feat

    # (i) vertical corner fillets, r cornerFillet, on the wing's two outer
    # corners (x xWing1, y +/-wingHalfY), z -8..-2. The wing's -X end is
    # fused into the plate; its concave junctions with the plate's +X edge
    # stay sharp.
    verts = []
    for e in plate_body.edges:
        g = e.geometry
        if not isinstance(g, adsk.core.Line3D):
            continue
        d = line_dir(g)
        if abs(abs(d.z) - 1) > 1e-6:
            continue
        mx, my, _ = mid(g)
        if near(mx, xWing1) and near(abs(my), wingHalfY):
            verts.append(e)
    print("wing corner fillet edges found:", len(verts))
    if len(verts) != 2:
        raise RuntimeError("expected 2 wing vertical corner edges, found %d" % len(verts))
    add_fillet(verts, corner, "wing corner fillet")
    print("wing corner fillets ok (r=%.2f mm on 2 edges)" % (corner * 10))

    # (ii) softFillet on the wing's back-rim outer edges at z -8: the part
    # of the back face's boundary outside the plate's footprint, i.e. the
    # +X edge (x 48.85), the two +-Y edges (y +/-13.35, x 20.85..46.35)
    # and the two corner-fillet arcs between them = 5. The plate's own
    # back perimeter stays sharp as it always was; the bore's exit circle
    # and the counterbores are circles of other radii and are skipped.
    rim = []
    for e in plate_body.edges:
        g = e.geometry
        if isinstance(g, adsk.core.Line3D):
            if not (near(g.startPoint.z, zBack) and near(g.endPoint.z, zBack)):
                continue
            mx, my, _ = mid(g)
            if near(mx, xWing1) or (near(abs(my), wingHalfY) and mx > xEdge + EPS):
                rim.append(e)
        elif isinstance(g, (adsk.core.Arc3D, adsk.core.Circle3D)):
            c = g.center
            if (near(c.z, zBack) and near(g.radius, corner)
                    and near(c.x, xWing1 - corner) and near(abs(c.y), wingHalfY - corner)):
                rim.append(e)
    print("wing back rim edges found:", len(rim))
    if len(rim) != 5:
        raise RuntimeError("expected 5 wing back rim edges (3 lines + 2 arcs), found %d"
                           % len(rim))
    add_fillet(rim, soft, "wing rim fillet")
    print("wing rim fillet ok (r=%.2f mm on 5 edges)" % (soft * 10))

    # 15. PLATE CORNER ROUNDING (2026-10-27). Each of the four outside
    # corners is cut with a "square minus quarter disc" profile over the
    # plate's whole height (z -8..11, so the -X fence wall's corner at
    # x -20.65 is rounded too), radius plateCornerR. A cut rather than a
    # fillet: the -X corners are shared by the plate and its 1.5 mm wall,
    # and a fillet equal to the wall thickness is refused by the kernel.
    # The corner pieces are inboard of nothing: the pins (|x| <= 19.35),
    # the end bars (|x| <= 19.15) and the snap pockets (|y| = 12) all lie
    # inside the |x| 19.47 / |y| 21.55 corner squares.
    pcr = p(des, "plateCornerR")
    ccr = p(des, "cavityCornerR")
    if pcr <= ccr + 0.3 * MM - 1e-9:
        raise RuntimeError("plateCornerR %.2f must exceed cavityCornerR %.2f by 0.3 mm"
                           % (pcr * 10, ccr * 10))
    xe, ye = intW / 2 - rimGapX, intH / 2 - rimGapY
    cut_profiles = []
    sk = comp.sketches.add(comp.xYConstructionPlane)
    for sx in (-1, 1):
        for sy in (-1, 1):
            cx, cy = sx * (xe - pcr), sy * (ye - pcr)        # arc centre
            box(sk, min(cx, sx * xe), max(cx, sx * xe), min(cy, sy * ye), max(cy, sy * ye))
            sk.sketchCurves.sketchCircles.addByCenterRadius(
                adsk.core.Point3D.create(cx, cy, 0), pcr)
    for i in range(sk.profiles.count):
        pr = sk.profiles.item(i)
        ap = pr.areaProperties()
        c = ap.centroid
        # the corner piece's centroid lies ~0.78 r out from the arc centre
        # toward the corner; the quarter disc's only ~0.42 r
        if abs(c.x) > xe - 0.4 * pcr and abs(c.y) > ye - 0.4 * pcr:
            cut_profiles.append(pr)
    if len(cut_profiles) != 4:
        raise RuntimeError("expected 4 plate corner profiles, found %d" % len(cut_profiles))
    extrude(comp, collection(cut_profiles), -backT - 0.01 * MM, 11 * MM + 0.01,
            adsk.fusion.FeatureOperations.CutFeatureOperation,
            participants=[plate_body])
    if comp.bRepBodies.count != 1:
        raise RuntimeError("corner rounding split the plate: %d bodies" % comp.bRepBodies.count)
    print("plate corner rounding ok (r %.2f at (+/-%.2f, +/-%.2f), z -8..11; cavity corners r %.2f -> %.2f mm diagonal gap)"
          % (pcr * 10, xe * 10, ye * 10, ccr * 10, ((pcr - ccr) * (2 ** 0.5 - 1)) * 10))

    # 14e. (deleted, Task 9d) the PirPlug component: a slotted tube pressed
    # into the bore from the back to hold the sensor's base down, backed
    # by a filament keeper pin. The snug bore and the bezel ring on the
    # shell (03_shell.py step 8) hold the sensor instead; the bore is blind.

    print("BackPlate bodies:", comp.bRepBodies.count)
