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
        # 2026-10-25: the +X snap pair (shell bumps, plate pockets) moved
        # from y +/-12 to y +/-17 so it sits OUTBOARD of the shell's wing
        # notch (y +/-13.8), which had swallowed all but 1.2 mm of it. Read
        # by 03_shell.py step 5 and 02 step 3; the -X pair stays at +/-12.
        ("snapYpx", "17 mm", "y of the +X-side snap bump/pocket pair (the -X pair stays at 12): outboard of the wing notch, 6 mm long so it spans y 14..20"),
        # PIR pod (moved here from 03_shell.py on 2026-10-25, when the pod
        # moved from the shell to the plate's wing; step 14). Radii measured
        # on Panasonic's STEP by point probing (2026-10-11): base/can r 5.5
        # (not the 4.65 first assumed), neck r 5.3 -> 5.0, flange r 9.3 with
        # its underside at z 6.4..6.6, lens ring r 10.3, and TWO lens latch
        # tabs at 45/225 deg reaching r 11.1 over z 6.6..8.4 whose hook lips
        # (r 9.6..10.7) hang down to z 5.5.
        ("pirRecessR", "11.5 mm", "recess radius: latch tabs r 11.1 + 0.3 (lens ring is r 10.3)"),
        ("pirRecessD", "2.0 mm", "recess depth to the flange ledge (flange underside at sensor z 6.4..6.6)"),
        ("pirFlangeR", "9.3 mm", "flange radius: the sensor seats on the ledge r pirBoreR..pirFlangeR"),
        ("pirHookD", "3.3 mm", "groove depth outside the ledge for the latch hook lips (bottom at z 5.5 -> d 2.9)"),
        ("pirBoreR", "5.9 mm", "bore radius: base/can r 5.5 + 0.3; neck r 5.3..5.0 passes"),
        ("pirTilt", "18 deg", "bore tilt from the plate normal, toward +X"),
        ("pirTiltSign", "1", "+1: XIAO end hangs DOWN on the wall (confirmed 2026-10-11); -1: up"),
        ("pirPodWall", "2.0 mm", "pod wall around the recess"),
        ("pirWireDia", "3.0 mm", "wire pass-through out of the tower's -X face into the shell notch"),
        # The wire hole's centre line starts on the bore axis at this depth
        # (z 4.6) and slopes 17 deg down to the exit (pirWireExitZ) on the
        # tower's -X face. On the way it crosses the -X bore wall at about
        # d 16.1, and its oblique opening in that wall spans about
        # d 14.3..18.0: behind the pin tips (d 13.9), inside the plug span
        # (d 9.3..19.3) and its slot, level with the cap on the pins.
        ("pirWireD", "12.0 mm", "wire hole: axis depth where its sloped centre line starts (crosses the -X bore wall at d ~16.1, opening d ~14.3..18.0: behind the pin tips, inside the plug slot)"),
        ("pirWireExitZ", "0.4 mm", "wire hole exit centre on the tower's -X face: 0.4 puts the rim 0.8 mm above the wing top (z -2) and under the shell notch top (pirNotchTop)"),
        # Shell notch top (03_shell.py step 7 cuts the +X wall from the back
        # rim up to here; the 4.5 mm above the wing top is the wire slot).
        # Owned here so 02's wire-exit guard, 03's notch and 90's probes
        # read one value.
        ("pirNotchTop", "2.5 mm", "top of the shell's +X wall notch (z): wing z -8..-2 passes under, -2..pirNotchTop is the wire slot; the wire hole's rim must stay under it"),
        # Test print 2026-10-25: bore measured 11.8 (holes on this printer
        # come out true to size), plug OD measured 11.5 for 11.7 nominal
        # (outside walls print 0.2 under), and the plug fell out under
        # gravity. 12.1 nominal prints at about 11.9 for the 11.8 bore:
        # 0.05 mm per side of interference, taken up by the slot.
        ("pirPlugOD", "12.1 mm", "plug tube OD: holes print true, outside walls 0.2 under (measured 2026-10-25); 12.1 prints ~11.9 for the 11.8 bore, 0.05/side interference taken up by the slot"),
        # 2026-10-25, from a photo of the real wiring: the user soldered the
        # 0.1 uF film decoupling cap STANDING on the sensor's pins (a block
        # about 7 x 2.5 x 6.5 mm over the VDD/GND pins, top about 8.5 mm
        # above the base, d ~17.8), so the plug's bore has to hold the cap
        # and the solder joints as well as the pins: ID 9.0 (slotted wall
        # 1.55, still over the 1.2 mm check) and 10 mm long, spanning
        # d 9.3..19.3. The keeper pin expression then lands the pin at
        # d 20.75, in the wing (z about -3.7, 3.3 mm of wing behind it).
        ("pirPlugID", "9.0 mm", "plug tube ID: pins on r2.5 plus room for the decoupling cap standing on the pins (7 x 2.5 x 6.5 block to d ~17.8) and its solder joints"),
        ("pirPlugL", "10.0 mm", "plug tube length: covers the pins and the cap standing on them (to d ~17.8) from the seat at d 9.3"),
        ("pirSeatD", "9.3 mm", "plug front rim depth: the base's underside (sensor z -0.9); read by 02_backplate.py and 91_pir_fit.py"),
        ("pirPlugSlotW", "3.2 mm", "lengthwise slot through one plug wall: wire exit into the pass-through, and a little compliance for the press fit"),
        # Keeper pin (2026-10-25): a stub of 1.75 mm filament pushed through
        # a cross-hole in the pod, along Y, that crosses the bore just
        # behind the plug's back end so the plug cannot fall out even if
        # the press fit is loose. The axis depth is the plug's back end
        # (pirSeatD + pirPlugL = 19.3) plus the pin's radius plus 0.5 mm of
        # clearance between the plug and the pin's front surface: 20.75.
        # (Measuring the 0.5 from the axis instead would put the hole's
        # front edge 0.45 mm into the plug's wall.) pirPinD is an
        # expression, so it follows the plug parameters.
        ("pirPinDia", "1.9 mm", "keeper pin cross-hole diameter: 1.75 mm filament stub plus 0.15"),
        ("pirPinD", "pirSeatD + pirPlugL + pirPinDia / 2 + 0.5 mm", "keeper pin axis depth along the bore from the front face: plug back end + pin radius + 0.5 clearance (= 20.75, in the wing)"),
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
    ensure_params(des)

    for occ in list(root.occurrences):
        name = occ.component.name
        if name.startswith(("BackPlate", "PirPlug")):
            # rename before deleting: the dead component keeps its name
            # reserved in the document's name registry (until save), which
            # would force the rebuilt component to "BackPlate (1)". The
            # plug (step 14e) is rebuilt with the plate since 2026-10-25.
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

    # 3. snap pockets at plate +/-X edges (BLIND: z -1.7..-0.3, leaving
    # material ledges at both z ends so the shell's bumps (z -1.6..-0.4)
    # are retained axially with 0.1mm slop per side). -X pair at y +/-12;
    # the +X pair at y +/-snapYpx (17) since 2026-10-25, clear of the
    # shell's wing notch (y +/-13.8): pockets y 13.9..20.1, 2.75 mm clear
    # of the plate's +/-Y edges (half-height 22.85) and above the wing
    # (z < -2). The -Y pocket (x 20.25..20.85) leaves a 1.99 mm web to the
    # jack slot's +X wall at x 18.265 (step 9; the slot spans y
    # -20.71..-17.29, inside the pocket's y range).
    snapYpx = p(des, "snapYpx")
    if snapYpx + 3.1 * MM >= intH / 2 - rimGap:
        raise RuntimeError("snapYpx %.1f puts the +X pocket end (y %.2f) past the "
                           "plate's +/-Y edge (%.2f)"
                           % (snapYpx * 10, (snapYpx + 3.1 * MM) * 10,
                              (intH / 2 - rimGap) * 10))
    sk = comp.sketches.add(comp.xYConstructionPlane)
    for sx in (-1, 1):
        edge = sx * (intW / 2 - rimGap)
        snapY = snapYpx if sx > 0 else 12 * MM
        for sy in (-1, 1):
            # rect centered on the edge, 1.2 wide -> cuts 0.6 deep into plate
            rect(sk, edge, sy * snapY, 0.12, 6.2 * MM)
    profs = collection([sk.profiles.item(i) for i in range(sk.profiles.count)])
    extrude(comp, profs, -1.7 * MM, -0.3 * MM,
            adsk.fusion.FeatureOperations.CutFeatureOperation,
            participants=[plate_body])
    print("snap pockets ok (-X at y +/-12, +X at y +/-%.1f)" % (snapYpx * 10))

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
    # exactly that load path. The radar cable crosses above the board via
    # the step-4b notch and never needed these either.

    # 12. Radar cable exit (2026-09-10). The user photographed the assembled
    # plate: the RD-03D's 4-wire connector cable leaves the connector heading
    # -Y, straight off the end of the board, and had nowhere to go. The
    # connector pocket is sealed on three sides - the two 1.5 mm bay walls at
    # +/-X, and CROSSBAR A, which spans the full bay width at y -12.8..-11.2
    # from the floor up to PCB_REAR_Z where the board rests on it. There is no
    # gap over the bar, because the board is what sits on it. So the pocket's
    # only exits were the open -Y end, which runs into the 0.84 mm between the
    # board edge (y -22.01) and the plate edge (-22.85), and the +X wall.
    #
    # Cut the extreme -Y corner out of that wall. It lines up with where the
    # cable already goes, and it is the ONLY free stretch: clip B occupies
    # y -20.5..-13.5, crossbar A butts into the wall at -12.8..-11.2, and the
    # step-4b notch starts at -9.4, leaving only 0.7 mm and 1.8 mm gaps
    # between them. Ends at y -20.7 so it stops 0.2 mm clear of clip B's
    # raised span rather than sharing a face with it.
    #
    # Structurally free: the board's -Y end is already cantilevered over the
    # connector pocket with no support nearer than crossbar A, and lateral
    # retention still comes from ~40 mm of remaining wall plus all three
    # clips. Deliberately NOT cut as a wider, shorter window under clip B -
    # that would leave the clip backed by a 7 mm-span beam instead of a solid
    # wall, softening it, and the user's complaint this round was that clips
    # feel too weak.
    CABLE_Y0, CABLE_Y1 = -23.0 * MM, -20.7 * MM
    cx_in = rCx + bayW / 2                 # +X wall inner face, -3.70
    sk = comp.sketches.add(comp.xYConstructionPlane)
    box(sk, cx_in - 0.1 * MM, cx_in + 1.6 * MM, CABLE_Y0, CABLE_Y1)
    extrude(comp, sk.profiles.item(0), -0.01 * MM, 11.01 * MM,
            adsk.fusion.FeatureOperations.CutFeatureOperation,
            participants=[plate_body])
    print("radar cable exit ok (+X bay wall notched y -22.85..%.2f, full "
          "height, %.2f mm of wall removed)"
          % (CABLE_Y1 * 10, (-20.7 - -22.85)))

    # 13. Crossbar A cable slot (2026-09-10, user's proposal). Better route
    # than step 12's corner notch: come up THROUGH the bar that seals the
    # connector pocket, then use the open space under the radar board.
    #
    # Crossbar A spans the full bay width at y -12.8..-11.2 from the floor to
    # PCB_REAR_Z, so slotting it opens the pocket into the rest of the bay.
    # From there the wires run +X/+Y under the board (up to 10.46 mm of
    # headroom) and cross the +X wall through the step-4b notch, which is
    # open from z=postH to z=14 over |y|<9.4 - i.e. ABOVE the XIAO board,
    # whose top face is at 4.20. That matters: it lands the wires on top of
    # the board, where BOTH long edges are reachable. D6 sits on the +Y edge
    # and D7 on the -Y edge, so any route that arrives from one side only
    # would strand one of them.
    #
    # A 4.0 x 3.5 mm notch in the TOP of the bar, FLUSH AGAINST THE +X WALL.
    # Three of the user's calls, in order (2026-09-10): it began as a
    # full-height slot mid-bay, became a 3.5 mm tunnel at the base, then
    # moved to the top.
    #
    # Top-opening is the one that prints with no support at all - nothing
    # spans the gap, the bar simply stops at CBL_Z0 - whereas a base tunnel
    # leaves a 4 mm bridge. It also suits the cable better: the connector's
    # underside is at z 6.70, so wires leaving it stay at that height and run
    # straight through instead of diving to the floor and climbing back.
    #
    # Cost, stated plainly: the notch takes 4.0 mm out of the bar's 15.6 mm
    # bearing line on the PCB rear, leaving 11.6 mm on the -X side. The board
    # is still carried at two y stations (this bar and crossbar B) and held
    # down by all three clips and the lid, so the offset does not let it rock.
    #
    # Flush to the wall means the wires emerge already hugging the surface
    # they run +Y along, to the step-4b notch, where they cross ABOVE the
    # XIAO board - the only crossing that reaches both its long edges.
    CBL_X1 = rCx + bayW / 2 + 0.1 * MM     # 0.1 into the wall: no shared face
    CBL_X0 = CBL_X1 - 4.1 * MM
    CBL_Z0 = PCB_REAR_Z - 3.5 * MM         # 6.96
    cbl_y, cbl_w = XBARS[0]
    sk = comp.sketches.add(comp.xYConstructionPlane)
    box(sk, CBL_X0, CBL_X1,
        cbl_y - cbl_w / 2 - 0.1 * MM, cbl_y + cbl_w / 2 + 0.1 * MM)
    extrude(comp, sk.profiles.item(0), CBL_Z0, PCB_REAR_Z + 0.01 * MM,
            adsk.fusion.FeatureOperations.CutFeatureOperation,
            participants=[plate_body])
    print("crossbar A cable notch ok (x %.2f..%.2f, z %.2f..%.2f, open at "
          "the top - no bridge; %.1f mm of bearing line left)"
          % (CBL_X0 * 10, CBL_X1 * 10, CBL_Z0 * 10, PCB_REAR_Z * 10,
             (CBL_X0 - (rCx - bayW / 2)) * 10))

    # 14. PIR POD ON A WING (2026-10-25). The pod lived on the front shell's
    # +X wall from 2026-10-11 (03_shell.py, up to commit 582091f). After the
    # first test print the user asked for it on the PLATE instead, so that
    # all wiring stays on one platform and the shell lifts off clean, and
    # because a pod standing up from the plate prints its recess as a
    # top-side pocket: no supports anywhere any more.
    #
    # Shape (shell frame; the plate's occurrence is at identity):
    #   wing   z -8..-2 (6 mm, coplanar with the plate's back), from the
    #          plate's +X edge (x 20.85, fused to it) out to the tower's
    #          far end, y +/-13.5 (the tower's length).
    #   tower  the same 34.8 x 27 pod block as before, standing on the wing
    #          from z -2, starting 0.3 mm outside the shell's +X outer wall
    #          (x 23.3) so the two parts never touch there. Its TOP FACE is
    #          CANTED pirTilt, normal to the bore axis, through the axis
    #          point at z 16 on the tower's centre (2026-10-25, user review
    #          of the side view: with a flat top the lens ring broke
    #          through on the uphill side). Uphill (-X) corner about z 21.7,
    #          downhill (+X) edge about z 10.4; every depth along the axis
    #          (recess, ledge, groove, seat, pin, wire hole) is unchanged.
    #   cuts   recess, flange ledge, latch-hook groove, tilted bore, wire
    #          hole and keeper pin cross-hole: the code from 03_shell.py
    #          step 8, re-anchored on the tower's centre. The bore exits the
    #          back face through the wing, so the plug still goes in from
    #          the back; with the 10 mm plug the keeper pin's cross-hole
    #          runs through the WING (z about -3.7), along Y.
    #   holes  two more Technic holes in the wing under the tower's far end,
    #          on the existing 8 mm grid, clear of the bore exit and the pin.
    #   plug   the PirPlug component (was 03 step 8b), parked in the bore.
    # The shell gets a matching notch in its +X wall (03_shell.py step 7):
    # z -8..-2 for the wing to pass under the wall, z -2..+2 as the wire
    # slot above it.
    #
    # MUST come after step 6 (the plate-outline Intersect would trim the
    # wing off) and after step 7 (whose chamfer counts the rear bore edges
    # and expects six).
    recessR, recessD = p(des, "pirRecessR"), p(des, "pirRecessD")
    boreR, podWall = p(des, "pirBoreR"), p(des, "pirPodWall")
    flangeR, hookD = p(des, "pirFlangeR"), p(des, "pirHookD")
    # Fusion hands angle parameters back in radians (18 deg -> 0.314); the
    # guard also accepts a value typed in degrees.
    tilt = p(des, "pirTilt") if p(des, "pirTilt") < 1.6 else math.radians(p(des, "pirTilt"))
    sgn = 1.0 if p(des, "pirTiltSign") >= 0 else -1.0
    xOuter = intW / 2 + wall                     # shell's +X outer face, 23
    xEdge = intW / 2 - rimGap                    # plate's +X edge, 20.85
    POD_GAP = 0.3 * MM                           # tower to shell wall
    WING_T = 6.0 * MM
    zTop, zBack = intD + wall, -backT            # 16, -8
    zWing = zBack + WING_T                       # -2: wing top
    depth = zTop - zBack                         # 24
    podW = 2 * (recessR + podWall) + depth * math.tan(tilt)   # 34.8 along X
    podL = 2 * (recessR + podWall)                            # 27 along Y
    xTow0 = xOuter + POD_GAP                     # 23.3: tower's -X face
    xTow1 = xTow0 + podW                         # 58.1: tower's +X face
    podCx = xTow0 + podW / 2

    # 14a. wing, overlapping 0.5 mm into the plate so the Join merges by
    # volume; the plate is solid there (the snap pockets at the edge sit
    # above the wing, z -1.7..-0.3, and the jack is at y < -17).
    sk = comp.sketches.add(comp.xYConstructionPlane)
    box(sk, xEdge - 0.5 * MM, xTow1, -podL / 2, podL / 2)
    extrude(comp, sk.profiles.item(0), zBack, zWing,
            adsk.fusion.FeatureOperations.JoinFeatureOperation,
            participants=[plate_body])
    # 14b. tower, overlapping 0.5 mm down into the wing, extruded past the
    # canted top's uphill corner (zTop + podW/2 * tan tilt) so the cant cut
    # below has material to shape on the -X side
    zTowerBox = zTop + (podW / 2) * math.tan(tilt) + 0.1
    sk = comp.sketches.add(comp.xYConstructionPlane)
    box(sk, xTow0, xTow1, -podL / 2, podL / 2)
    extrude(comp, sk.profiles.item(0), zWing - 0.5 * MM, zTowerBox,
            adsk.fusion.FeatureOperations.JoinFeatureOperation,
            participants=[plate_body])
    if comp.bRepBodies.count != 1:
        raise RuntimeError("pir wing/tower did not merge with the plate: %d bodies"
                           % comp.bRepBodies.count)
    print("pir wing ok (x %.2f..%.2f, y +/-%.1f, z %.0f..%.0f); tower %.1f x %.1f "
          "at x %.2f..%.2f, z %.0f up (box to %.2f before the cant), %.1f mm clear "
          "of the shell wall"
          % (xEdge * 10, xTow1 * 10, podL / 2 * 10, zBack * 10, zWing * 10,
             podW * 10, podL * 10, xTow0 * 10, xTow1 * 10, zWing * 10,
             zTowerBox * 10, POD_GAP * 10))

    # bore axis through the tower centre at z 16, direction (sgn*sin t, 0,
    # cos t) pointing OUT of the pod; along(d) is the axis point d into the
    # pod; uvec is the in-plane direction across the tilt (toward +X when
    # the pod leans +X), so (uvec, +Y, ax) is a right-handed frame on the
    # canted top: uvec x Y = ax.
    ax = adsk.core.Vector3D.create(sgn * math.sin(tilt), 0.0, math.cos(tilt))
    uvec = adsk.core.Vector3D.create(math.cos(tilt), 0.0, -sgn * math.sin(tilt))
    front_pt = adsk.core.Point3D.create(podCx, 0.0, zTop)

    def along(d):
        return adsk.core.Point3D.create(front_pt.x - ax.x * d, 0.0, front_pt.z - ax.z * d)

    def on_top(d, u, y=0.0):
        """Point d along the axis INTO the pod, u across the tilt, y sideways."""
        return adsk.core.Point3D.create(front_pt.x - ax.x * d + uvec.x * u,
                                        y, front_pt.z - ax.z * d + uvec.z * u)

    # 14b'. CANT THE TOP: remove everything above the plane through front_pt
    # with normal ax. Tool: a 200 x 200 x 100 mm oriented box whose height
    # axis is ax and whose bottom face is that plane, Combine-cut from the
    # plate body only. The plane rises toward -X (z 22.5 over the plate's
    # edge, higher beyond), so nothing else of the plate is touched.
    z_up = zTop + (podCx - xTow0) * math.tan(tilt)      # uphill (-X) top edge
    z_dn = zTop - (xTow1 - podCx) * math.tan(tilt)      # downhill (+X) top edge
    if sgn < 0:
        z_up, z_dn = z_dn, z_up
    if max(z_up, z_dn) >= 2.3:
        raise RuntimeError("canted top's uphill edge at z %.2f is not below 23 mm"
                           % (max(z_up, z_dn) * 10))
    tbm = adsk.fusion.TemporaryBRepManager.get()
    BIG, H = 20.0, 10.0
    centre = adsk.core.Point3D.create(front_pt.x + ax.x * H / 2, 0.0,
                                      front_pt.z + ax.z * H / 2)
    obb = adsk.core.OrientedBoundingBox3D.create(centre, uvec,
                                                 adsk.core.Vector3D.create(0, 1, 0),
                                                 BIG, BIG, H)
    half_space = tbm.createBox(obb)
    base = comp.features.baseFeatures.add()
    base.startEdit()
    comp.bRepBodies.add(half_space, base)
    base.finishEdit()
    tools = [base.bodies.item(i) for i in range(base.bodies.count)]
    if len(tools) != 1:
        raise RuntimeError("expected 1 cant tool body, found %d" % len(tools))
    vol_before = plate_body.volume
    ci = comp.features.combineFeatures.createInput(plate_body, collection(tools))
    ci.operation = adsk.fusion.FeatureOperations.CutFeatureOperation
    ci.isKeepToolBodies = False
    comp.features.combineFeatures.add(ci)
    if comp.bRepBodies.count != 1:
        raise RuntimeError("cant cut split the plate: %d bodies" % comp.bRepBodies.count)
    # the box's height axis is taken to be length x width = ax; prove it on
    # the result rather than trust the OBB convention: material 0.3 mm
    # under the plane and none 0.3 mm over it, at the four rim points and
    # at both tower ends; and the box must have removed only the tower's
    # downhill wedge, i.e. a volume well under the tower's own
    IN = adsk.fusion.PointContainment.PointInsidePointContainment
    u_edge = (xTow1 - podCx) / math.cos(tilt)      # tower end, in-plane, at d 0
    for u in (-u_edge + 0.05, -(recessR + 0.1), 0.0, recessR + 0.1, u_edge - 0.05):
        for y in (0.0, podL / 2 - 0.05, -(podL / 2 - 0.05)):
            if plate_body.pointContainment(on_top(0.03, u, y)) != IN:
                raise RuntimeError("no tower under the canted top at u %.1f y %.1f"
                                   % (u * 10, y * 10))
            if plate_body.pointContainment(on_top(-0.03, u, y)) == IN:
                raise RuntimeError("tower material above the canted top at u %.1f y %.1f"
                                   % (u * 10, y * 10))
    removed = vol_before - plate_body.volume
    # the pivot is the tower's centre, so the uphill wedge kept above zTop
    # equals the downhill wedge removed below it and the net removal is
    # exactly the box's slab above zTop
    slab = podW * podL * (zTowerBox - zTop)
    if abs(removed - slab) > 0.02:
        raise RuntimeError("cant cut removed %.3f cm3, expected the %.3f cm3 slab"
                           % (removed, slab))
    # recess rim wall: the recess (r recessR, d 0..hookD) must keep at
    # least pirPodWall of tower around it. +-Y: podL/2 - recessR = podWall
    # by construction. Across the tilt the tower's +-X faces are vertical,
    # so the in-plane wall changes with depth: measure it at the top (d 0)
    # and at the groove floor (d hookD), both directions.
    walls = {}
    for d in (0.0, hookD):
        a = along(d)
        walls[("downhill" if sgn > 0 else "uphill", d)] = (xTow1 - a.x) / math.cos(tilt) - recessR
        walls[("uphill" if sgn > 0 else "downhill", d)] = (a.x - xTow0) / math.cos(tilt) - recessR
        walls[("+Y", d)] = walls[("-Y", d)] = podL / 2 - recessR
    thin = min(walls.values())
    if thin < podWall - 1e-6:
        raise RuntimeError("recess rim wall %.2f mm is under pirPodWall %.2f: %s"
                           % (thin * 10, podWall * 10,
                              {k: round(v * 10, 2) for k, v in walls.items()}))
    # the downhill top edge sits above the groove floor's downhill rim
    floor_dn = on_top(hookD, (recessR if sgn > 0 else -recessR))
    if z_dn <= floor_dn.z:
        raise RuntimeError("downhill top edge z %.2f is below the recess floor's rim z %.2f"
                           % (z_dn * 10, floor_dn.z * 10))
    print("pir tower top canted %.1f deg (normal to the bore axis, through the axis "
          "point at z %.1f): uphill edge z %.2f, downhill edge z %.2f (%.2f mm above "
          "the groove floor's downhill rim at z %.2f); removed %.2f cm3; recess rim "
          "wall at d 0 / d %.1f: downhill %.2f / %.2f, uphill %.2f / %.2f, +-Y %.2f ok"
          % (math.degrees(tilt), zTop * 10, z_up * 10, z_dn * 10,
             (z_dn - floor_dn.z) * 10, floor_dn.z * 10, removed, hookD * 10,
             walls[("downhill", 0.0)] * 10, walls[("downhill", hookD)] * 10,
             walls[("uphill", 0.0)] * 10, walls[("uphill", hookD)] * 10,
             walls[("+Y", 0.0)] * 10))

    # 14c. the cuts. The EKMC1603111's lens (dia 20.6, 11 mm tall) is wider
    # than its neck, so the sensor enters from the FRONT: lens ring + flange
    # in a 2 mm recess, the flange seated on a ledge with an annular groove
    # outside it for the lens's two latch hooks (so the sensor can go in at
    # any rotation), neck and base through a bore, a plug tube pressed in
    # from the back holds it. The bore tilts pirTilt toward +X so the PIR
    # looks 18 deg down with the case hanging XIAO-end-down.
    #
    # (ax, front_pt, along() are defined above, with the cant.)
    # read every parameter BEFORE startEdit(): inside a base feature the
    # design is in direct-modelling mode and userParameters raises
    # "this is not a parametric design".
    wireR, wp = p(des, "pirWireDia") / 2, along(p(des, "pirWireD"))
    pinR, pinD = p(des, "pirPinDia") / 2, p(des, "pirPinD")
    plugBack = p(des, "pirSeatD") + p(des, "pirPlugL")
    pp = along(pinD)
    # Wire hole. Its centre line starts on the bore axis at d pirWireD
    # (z 4.6) and slopes about 17 deg down to the exit on the tower's -X
    # face, centred at z pirWireExitZ (0.4) in the shell's wire slot (z -2
    # ..pirNotchTop, between the wing top and the notched wall's bottom
    # edge). It cannot run level as it did through the shell wall: level
    # at z 4.6 it would miss the slot, and lower on the axis it would meet
    # the keeper pin. Along the way the centre line crosses the -X bore
    # wall at about d 16.1 and the oblique opening in that wall spans
    # about d 14.3..18.0: behind the pin tips (d 13.9), inside the plug
    # span (d 9.3..19.3) and its slot, level with the cap on the pins, so
    # the wires leave the slot straight into it. At the exit the rim is
    # 0.8 mm (four layers) above the wing top and must stay under the
    # notch top; the assertion keeps both. The sloped cylinder is extended
    # 0.8 mm past the face so the exit is a clean hole, and it only cuts
    # air there (the wing top is lower).
    WIRE_EXIT_Z = p(des, "pirWireExitZ")
    notchTop = p(des, "pirNotchTop")
    wire_exit = adsk.core.Point3D.create(xTow0, 0.0, WIRE_EXIT_Z)
    slope = math.atan2(wp.z - wire_exit.z, wp.x - wire_exit.x)   # from -X
    rimZ = wireR / math.cos(slope)          # the exit ellipse's z half-extent
    wire_end = adsk.core.Point3D.create(xTow0 - 0.8 * MM, 0.0,
                                        WIRE_EXIT_Z - 0.8 * MM * math.tan(slope))
    if not (zWing + 0.05 < wire_exit.z - rimZ and wire_exit.z + rimZ < notchTop):
        raise RuntimeError("wire hole exit z %.2f..%.2f mm is not inside the "
                           "shell's wire slot (z %.1f..%.1f, pirNotchTop)"
                           % ((wire_exit.z - rimZ) * 10, (wire_exit.z + rimZ) * 10,
                              zWing * 10, notchTop * 10))
    # keeper pin guards (see ensure_params): its front surface must be
    # behind the plug's back end, it must stay clear of the wire hole
    # (both sit at y 0, so only their z separation where the hole passes
    # the pin's x keeps them apart) and leave at least 1 mm of wing between
    # its rear surface and the back face (the pin crosses the bore inside
    # the wing; it must not break out of the back). The hole's centre line
    # at x = pp.x:
    wire_z_at_pin = wire_exit.z + (pp.x - wire_exit.x) * math.tan(slope)
    if pinD - pinR <= plugBack:
        raise RuntimeError("keeper pin front surface at d %.2f is not behind the "
                           "plug's back end at d %.2f" % ((pinD - pinR) * 10, plugBack * 10))
    if abs(pp.z - wire_z_at_pin) <= pinR + rimZ + 0.05:
        raise RuntimeError("keeper pin (z %.2f) would break into the wire hole (z %.2f at x %.2f)"
                           % (pp.z * 10, wire_z_at_pin * 10, pp.x * 10))
    if pp.z - pinR <= zBack + 0.1:
        raise RuntimeError("keeper pin z %.2f leaves under 1 mm of wing behind it "
                           "(back face z %.1f)" % (pp.z * 10, zBack * 10))
    base = comp.features.baseFeatures.add()
    base.startEdit()
    # the top is normal to the axis (14b'), so the recess cylinder meets it
    # square all round and can start just 0.5 mm proud of it
    recess_cyl = tbm.createCylinderOrCone(along(-0.05), recessR, along(recessD), recessR)
    # latch-hook groove: the recess floor stays at recessD only over the
    # flange ledge (r boreR..flangeR); outside it the floor drops to hookD
    groove = tbm.createCylinderOrCone(along(recessD - 0.01), recessR, along(hookD), recessR)
    ledge = tbm.createCylinderOrCone(along(recessD - 0.02), flangeR, along(hookD + 0.01), flangeR)
    tbm.booleanOperation(groove, ledge, adsk.fusion.BooleanTypes.DifferenceBooleanType)
    # bore: through the tower and the wing, out of the back face
    bore_cyl = tbm.createCylinderOrCone(along(recessD - 0.01), boreR,
                                        along(depth / math.cos(tilt) + 0.3), boreR)
    wire_cyl = tbm.createCylinderOrCone(
        adsk.core.Point3D.create(wp.x, 0.0, wp.z), wireR, wire_end, wireR)
    # keeper pin cross-hole: along Y (perpendicular to the bore axis and to
    # the tilt plane) at the axis point pinD, through both tower walls and
    # across the bore, overrunning the tower's +-Y faces by 1 mm
    pin_cyl = tbm.createCylinderOrCone(
        adsk.core.Point3D.create(pp.x, -(podL / 2 + 0.1), pp.z), pinR,
        adsk.core.Point3D.create(pp.x, podL / 2 + 0.1, pp.z), pinR)
    for b in (recess_cyl, groove, bore_cyl, wire_cyl, pin_cyl):
        comp.bRepBodies.add(b, base)
    base.finishEdit()
    # the proxies returned by bRepBodies.add() go stale when the edit
    # closes (Combine fails with ALL_TOOL_BODY_REFERENCE_LOST); use the
    # base feature's own body list instead
    tools = [base.bodies.item(i) for i in range(base.bodies.count)]
    if len(tools) != 5:
        raise RuntimeError("expected 5 pir tool bodies, found %d" % len(tools))
    ci = comp.features.combineFeatures.createInput(plate_body, collection(tools))
    ci.operation = adsk.fusion.FeatureOperations.CutFeatureOperation
    ci.isKeepToolBodies = False
    comp.features.combineFeatures.add(ci)
    if comp.bRepBodies.count != 1:
        raise RuntimeError("pir pod cuts split the plate: %d bodies" % comp.bRepBodies.count)
    exit_pt = along(depth / math.cos(tilt))      # bore axis at the back face
    print("pir recess r=%.2f d=%.2f (ledge r %.2f..%.2f, hook groove to d %.2f), "
          "bore r=%.2f, tilt %.1f deg, exits the back face centred x %.2f ok"
          % (recessR * 10, recessD * 10, boreR * 10, flangeR * 10, hookD * 10,
             boreR * 10, math.degrees(tilt), exit_pt.x * 10))
    print("pir wire hole dia %.1f from the bore axis at d %.1f (x %.2f z %.2f) "
          "sloping %.1f deg down to the tower's -X face at z %.2f "
          "(rim z %.2f..%.2f; wing top %.1f, notch top %.1f) ok"
          % (wireR * 20, p(des, "pirWireD") * 10, wp.x * 10, wp.z * 10,
             math.degrees(slope), wire_exit.z * 10, (wire_exit.z - rimZ) * 10,
             (wire_exit.z + rimZ) * 10, zWing * 10, notchTop * 10))
    # hand-drill location for a print made without the pin: on the pod's
    # +-Y side faces (the wing's, with the 10 mm plug), measured up from the
    # back face and from the tower's -X face
    print("pir keeper pin hole dia %.2f along Y at d %.2f (plug back end d %.1f, "
          "clearance %.2f): on the pod's +-Y side faces at z %.2f, %.2f mm above "
          "the back face (%.2f mm of material behind the hole), %.2f mm from the "
          "tower's -X face ok"
          % (pinR * 20, pinD * 10, plugBack * 10, (pinD - pinR - plugBack) * 10,
             pp.z * 10, (pp.z - zBack) * 10, (pp.z - pinR - zBack) * 10,
             (pp.x - xTow0) * 10))

    # 14d. two more Technic holes in the wing, on the step-7 grid (x = 0.95
    # + k*8 -> 48.95, y +/-4), the same pattern as step 7: legoHole through
    # bore from the back face 8 mm up (they end blind inside the tower's
    # solid material at z 0), legoCbDia x legoCbDepth counterbore on the
    # back face, 0.3 mm entry chamfer. They must clear the bore's exit on
    # the back face (centred x ~32.9, X half-width boreR/cos(tilt)) and the
    # keeper pin's cross-hole (x pp.x, which runs the wing's full width
    # along Y at the holes' depth), by at least 0.6 mm of wall, and stay
    # inside the tower's far end.
    WING_HOLE_D = 8.0 * MM
    wx = x1 + 6 * pitch                           # 48.95
    wing_centers = [(wx, s * pitch / 2) for s in (-1, 1)]
    exit_half_w = boreR / math.cos(tilt)
    bore_reach = max(exit_pt.x + exit_half_w, pp.x + pinR)
    if wx - cbD / 2 - 0.06 <= bore_reach:
        raise RuntimeError("wing Technic holes at x %.2f (counterbore edge %.2f) "
                           "are under 0.6 mm from the bore exit / keeper pin (reach %.2f)"
                           % (wx * 10, (wx - cbD / 2) * 10, bore_reach * 10))
    if wx + cbD / 2 + 0.06 >= xTow1:
        raise RuntimeError("wing Technic holes run past the tower's far end")

    def wing_circles(radius):
        sk = comp.sketches.add(comp.xYConstructionPlane)
        for cx, cy in wing_centers:
            sk.sketchCurves.sketchCircles.addByCenterRadius(
                adsk.core.Point3D.create(cx, cy, 0), radius)
        return collection([sk.profiles.item(i)
                           for i in range(sk.profiles.count)])

    extrude(comp, wing_circles(holeD / 2), -backT, -backT + WING_HOLE_D,
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
          "%.0f mm deep from the back, %.2f mm clear of the bore exit, %.2f mm "
          "clear of the keeper pin hole"
          % (WING_HOLE_D * 10, (wx - cbD / 2 - exit_pt.x - exit_half_w) * 10,
             (wx - cbD / 2 - pp.x - pinR) * 10))

    # 14d'. SOFTEN THE WING AND TOWER EDGES (2026-10-25, user: "redo the
    # chamfering"): the same treatment the shell gets in 03_shell.py steps
    # 6a-6c, so the two parts match in the hand. After all the cuts, so
    # the selectors see the final topology; before the plug, which is its
    # own component. Fillet/chamfer features act on the plate body's edges
    # only, so they are participant-safe by construction.
    EPS = 0.005                                   # 0.05 mm (cm)
    corner = p(des, "cornerFillet")
    cham = p(des, "frontChamfer")
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

    def add_chamfer(edges, dist, label):
        ch = comp.features.chamferFeatures
        chi = ch.createInput(collection(edges), False)
        chi.setToEqualDistance(adsk.core.ValueInput.createByReal(dist))
        feat = ch.add(chi)
        if comp.bRepBodies.count != 1:
            raise RuntimeError("%s split the plate: %d bodies" % (label, comp.bRepBodies.count))
        return feat

    # (i) vertical corner fillets, r cornerFillet: the pod's four outer
    # vertical edges. The wing's and tower's +X faces (x 58.1) and +-Y
    # faces (y +-13.5) are coplanar and merge on the Join, so the +X
    # corners are single edges from the back face (z -8) to the canted
    # top; the -X corners (x 23.3) run from the wing's top (z -2) to the
    # canted top. Filleting the x 23.3 corners only rounds the outside of
    # the tower; the flat -X face (the 0.3 mm gap to the shell) keeps its
    # full height over |y| < 11. If Fusion ever left the +X faces unmerged
    # the corners would be two collinear edges each (6 in all): accepted,
    # same fillet.
    verts = []
    for e in plate_body.edges:
        g = e.geometry
        if not isinstance(g, adsk.core.Line3D):
            continue
        d = line_dir(g)
        if abs(abs(d.z) - 1) > 1e-6:
            continue
        mx, my, _ = mid(g)
        if (near(mx, xTow0) or near(mx, xTow1)) and near(abs(my), podL / 2):
            verts.append(e)
    print("pod corner fillet edges found:", len(verts))
    if len(verts) not in (4, 6):
        raise RuntimeError("expected 4 (or 6 unmerged) pod vertical corner edges, found %d"
                           % len(verts))
    add_fillet(verts, corner, "pod corner fillet")
    print("pod corner fillets ok (r=%.2f mm on %d edges)" % (corner * 10, len(verts)))

    # (ii) 1 mm chamfer round the canted top's outer perimeter, as the
    # shell's front face has. The top is the plane through front_pt with
    # normal ax, so select every edge whose ends and midpoint lie in that
    # plane, then drop the recess rim (the circle r recessR about the
    # axis, which must stay sharp: the lens ring seats on it). What is
    # left is 4 straight edges + 4 corner-fillet arcs (ellipse arcs, the
    # tilted plane cutting the fillet cylinders) = 8. On the +-Y sides the
    # chamfer takes 1 mm off the 2 mm wall at the very top edge only.
    def on_plane(pt):
        return abs((pt.x - front_pt.x) * ax.x + (pt.z - front_pt.z) * ax.z) < EPS

    def axis_r(pt):
        dx, dz = pt.x - front_pt.x, pt.z - front_pt.z
        a = dx * ax.x + dz * ax.z
        return math.sqrt(max((dx - a * ax.x) ** 2 + pt.y ** 2 + (dz - a * ax.z) ** 2, 0.0))

    top = []
    for e in plate_body.edges:
        ev = e.evaluator
        ok, p0, p1 = ev.getParameterExtents()
        pts = []
        for t in (p0, (p0 + p1) / 2, p1):
            ok, pt = ev.getPointAtParameter(t)
            pts.append(pt)
        if not all(on_plane(pt) for pt in pts):
            continue
        if all(axis_r(pt) < recessR + 0.05 for pt in pts):
            continue                              # the recess rim
        top.append(e)
    print("pod top perimeter edges found:", len(top))
    if len(top) != 8:
        raise RuntimeError("expected 8 pod top perimeter edges (4 lines + 4 fillet arcs), "
                           "found %d" % len(top))
    add_chamfer(top, cham, "pod top chamfer")
    print("pod top chamfer ok (%.2f mm on 8 edges)" % (cham * 10))

    # (iii) softFillet on the wing's back-rim outer edges at z -8: the part
    # of the back face's boundary outside the plate's footprint, i.e. the
    # +X edge (x 58.1), the two +-Y edges (y +-13.5, x 20.85..55.6) and the
    # two corner-fillet arcs between them (circular here: a horizontal
    # plane cutting the fillet cylinders) = 5. The plate's own back
    # perimeter stays sharp as it always was. The +-Y fillets end at the
    # concave junction with the plate's +X edge at x 20.85.
    rim = []
    for e in plate_body.edges:
        g = e.geometry
        if isinstance(g, adsk.core.Line3D):
            if not (near(g.startPoint.z, zBack) and near(g.endPoint.z, zBack)):
                continue
            mx, my, _ = mid(g)
            if near(mx, xTow1) or (near(abs(my), podL / 2) and mx > xEdge + EPS):
                rim.append(e)
        elif isinstance(g, (adsk.core.Arc3D, adsk.core.Circle3D)):
            c = g.center
            if (near(c.z, zBack) and near(g.radius, corner)
                    and near(c.x, xTow1 - corner) and near(abs(c.y), podL / 2 - corner)):
                rim.append(e)
    print("wing back rim edges found:", len(rim))
    if len(rim) != 5:
        raise RuntimeError("expected 5 wing back rim edges (3 lines + 2 arcs), found %d"
                           % len(rim))
    add_fillet(rim, soft, "wing rim fillet")
    print("wing rim fillet ok (r=%.2f mm on 5 edges)" % (soft * 10))

    # 14e. PLUG: tube pressed into the bore from the back; its front rim
    # bears on the base's underside (r up to 5.5, pins inside r 2.5).
    # Separate component, exported as its own STL, printed standing on
    # either end.
    plug_occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    plug = plug_occ.component
    plug.name = "PirPlug"
    sk = plug.sketches.add(plug.xYConstructionPlane)
    sk.sketchCurves.sketchCircles.addByCenterRadius(adsk.core.Point3D.create(0, 0, 0), p(des, "pirPlugOD") / 2)
    sk.sketchCurves.sketchCircles.addByCenterRadius(adsk.core.Point3D.create(0, 0, 0), p(des, "pirPlugID") / 2)
    # the annular profile, not the inner disc: the one bounded by TWO loops.
    # (Until 2026-10-25 this picked the larger-area profile, which is the
    # annulus only while ID < OD/sqrt(2); at ID 9 / OD 12.1 the disc is
    # bigger and that rule silently built a solid plug.)
    ring = None
    for i in range(sk.profiles.count):
        pr = sk.profiles.item(i)
        if pr.profileLoops.count == 2:
            ring = pr
    if ring is None:
        raise RuntimeError("plug sketch has no annular profile")
    plugL = p(des, "pirPlugL")
    want_ring = math.pi * ((p(des, "pirPlugOD") / 2) ** 2 - (p(des, "pirPlugID") / 2) ** 2)
    if abs(ring.areaProperties().area - want_ring) > 1e-3:
        raise RuntimeError("plug annulus area %.3f cm2, expected %.3f"
                           % (ring.areaProperties().area, want_ring))
    slotWall = (p(des, "pirPlugOD") - p(des, "pirPlugID")) / 2
    if slotWall < 0.12:
        raise RuntimeError("plug wall %.2f mm is under 1.2 mm" % (slotWall * 10))
    plug_ext = extrude(plug, ring, 0, plugL,
                       adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    plug_body = plug_ext.bodies.item(0)
    # lengthwise slot through the -X wall, full length: the wires leave the
    # pins radially through it into the pass-through (which runs -X from
    # the bore axis), and the split lets the tube compress a little for the
    # press fit. The parking frame below maps local -X toward the case
    # (world -X), so "slot toward the case" is the insertion rule.
    slotW, odR = p(des, "pirPlugSlotW"), p(des, "pirPlugOD") / 2
    sk = plug.sketches.add(plug.xYConstructionPlane)
    rect(sk, -(odR + 0.1) / 2, 0, odR + 0.1, slotW)      # x -(odR+1mm)..0
    extrude(plug, sk.profiles.item(0), -0.05, plugL + 0.05,
            adsk.fusion.FeatureOperations.CutFeatureOperation,
            participants=[plug_body])
    if plug.bRepBodies.count != 1:
        raise RuntimeError("plug slot left %d bodies" % plug.bRepBodies.count)
    print("pir plug slot ok (%.1f mm wide, -X wall, full length)" % (slotW * 10))
    # park the occurrence in the bore where it will sit: local +Z along the
    # bore (deeper = -Z of the plate), local z=0 (the front rim) at d 9.3,
    # the can's underside (sensor z -0.9). Purely for the picture and for
    # 91_pir_fit.py's interference check; the STL is exported in local coords.
    # Explicit frame rather than setToRotateTo(): that would spin the tube
    # 162 deg about -Y and put the slot on the +X side. Local Z = inward
    # along the bore, local X = the in-plane direction that keeps -X
    # pointing at the case, Y = Z x X.
    m = adsk.core.Matrix3D.create()
    inward = adsk.core.Vector3D.create(-ax.x, 0.0, -ax.z)
    xloc = adsk.core.Vector3D.create(math.cos(tilt), 0.0, -sgn * math.sin(tilt))
    yloc = inward.crossProduct(xloc)
    seat = along(p(des, "pirSeatD"))
    m.setWithCoordinateSystem(seat, xloc, yloc, inward)
    # guard for future edits of the frame above: the slot (local -X) must
    # end up on the case side, where the wire hole is, or the README's
    # insertion rule and the fit check stop describing the same thing
    chk = adsk.core.Point3D.create(-odR, 0, 0)
    chk.transformBy(m)
    if chk.x >= seat.x:
        raise RuntimeError("plug parked with its slot away from the case")
    plug_occ.transform2 = m
    if des.snapshots.hasPendingSnapshot:
        des.snapshots.add()
    print("pir plug ok (OD %.1f ID %.1f L %.1f, wall %.2f, rim at d %.1f)"
          % (p(des, "pirPlugOD") * 10, p(des, "pirPlugID") * 10, plugL * 10,
             slotWall * 10, p(des, "pirSeatD") * 10))

    print("BackPlate bodies:", comp.bRepBodies.count)
