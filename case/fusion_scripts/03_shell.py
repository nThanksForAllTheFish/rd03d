import math

import adsk.core
import adsk.fusion


def p(des, name):
    return des.userParameters.itemByName(name).value  # cm


def p02(des, name):
    """A parameter 02_backplate.py owns (its ensure_params creates it)."""
    if des.userParameters.itemByName(name) is None:
        raise RuntimeError("parameter %s is missing: run 02_backplate.py first "
                           "(it creates the pir*, wingSnap* parameters)" % name)
    return p(des, name)


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
        name = occ.component.name
        if name.startswith(("FrontShell", "PirBezel")):
            # rename before deleting: the dead component keeps its name
            # reserved in the document's name registry (until save), which
            # would force the rebuilt component to "FrontShell (1)". The
            # bezel (step 8) is rebuilt with the shell since Task 9d. (The
            # sensor import belongs to 02_backplate.py / 91_pir_fit.py.)
            occ.component.name = name + "_deleted"
            occ.deleteMe()
            print("removed existing", name)

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

    # 3: RADOME STEP over the antenna zones (RF fix 2026-09-08). This
    # REPLACES the two interior window pockets built on 2026-09-07 - they
    # made the RF worse, not better.
    #
    # What was wrong: the pockets cut the front wall from z=14.0 up to 14.8,
    # thinning it to windowT (1.2 mm) but putting the radome's INNER face at
    # 14.80. Probed on the live model, the RD-03D's PCB FRONT face - the
    # antenna/patch plane - sits at z = 11.70 (its PCB rear rests on the
    # crossbars at 10.46; the 13.0 figure quoted in earlier notes is the
    # board's overall front extent, i.e. the 45-degree IC, not the patches).
    # That left a 3.10 mm AIR gap in front of the patches, which at 24 GHz
    # (lambda = 12.5 mm) is essentially exactly lambda/4 = 3.125 mm - the
    # WORST possible spacing. A quarter-wave air layer is an impedance
    # transformer: the reflection off the plastic comes back to the patches
    # in phase and adds instead of cancelling.
    #
    # The fix is to bring the plastic DOWN to the patches instead of thinning
    # it. Solid material is JOINED from z = RADOME_Z0 (12.90) up to the front
    # inner face (intD = 14.0) over the two antenna zones, leaving a 1.20 mm
    # air gap ~ lambda/10, well inside the near field where the transformer
    # effect is negligible. The wall is then solid 12.90..16.00 (3.10 mm)
    # over the antennas and unchanged at 14.00..16.00 (2.00 mm) everywhere
    # else. Nothing touches the z=16 face - the exterior stays perfectly flat.
    #
    # Print note: this is a raised plateau in the shell's print orientation
    # (front face on the bed, so the boss is printed on top of the already-
    # laid front wall) - no overhang, no support.
    #
    # The IC band y -4..+4 is deliberately EXCLUDED: the radar's 45-degree IC
    # protrudes to z = 12.95 over about x -15..-5, y -3..+3, so the wall stays
    # at 14.00 there (1.05 mm clearance) - and the band keeps doing the
    # stiffening-rib job the gap between the old pockets did.
    #
    # X runs to -21.5 and the RX zone's +Y to 23.5, i.e. 0.5 mm INTO the
    # cavity walls (x=-21, y=+23). Those slabs are already solid at this
    # height, so the geometry is identical either way; the overlap just makes
    # the Join merge by volume instead of by coplanar faces.
    RADOME_Z0 = 12.90 * MM         # -> 1.20 mm air gap at the 11.70 patches
    RADOME_X0, RADOME_X1 = -21.5 * MM, -2.0 * MM
    RADOME_ZONES = ((-17.0 * MM, -4.0 * MM),     # TX pair
                    (4.0 * MM, 23.5 * MM))       # RX 2x2 array
    sk = comp.sketches.add(comp.xYConstructionPlane)
    for y0, y1 in RADOME_ZONES:
        rect(sk, (RADOME_X0 + RADOME_X1) / 2, (y0 + y1) / 2,
             RADOME_X1 - RADOME_X0, y1 - y0)
    profs = collection([sk.profiles.item(i) for i in range(sk.profiles.count)])
    if profs.count != 2:
        raise RuntimeError("expected 2 radome profiles, found %d"
                           % profs.count)
    extrude(comp, profs, RADOME_Z0, intD,
            adsk.fusion.FeatureOperations.JoinFeatureOperation,
            participants=[shell_body])
    if comp.bRepBodies.count != 1:
        raise RuntimeError("radome step did not merge with the shell: "
                           "%d bodies" % comp.bRepBodies.count)
    print("radome step ok (inner face z=%.2f, TX y-17..-4, RX y+4..+23, "
          "x -21..-2; IC band y-4..+4 left at %.2f). windowT=%.2f is now "
          "unused by the antenna zones." % (RADOME_Z0 * 10, intD * 10,
                                            winT * 10))

    # 4: (deleted 2026-09-09) the USB notch through the +X wall. The base
    # jack in the back plate replaces it entirely, so the XIAO's own USB-C
    # is no longer reachable with the case closed - serial console and USB
    # reflash now need the lid unclipped. `usbClear` joins `tapeRecess` as a
    # dead user parameter; both are left in place rather than re-running
    # 01_setup.py, which resets user-tuned values.

    # 4b: radar retention ribs (thin-wall fix 2026-09-07). The plate's old
    # 0.6 mm +/-Y fence segments were unprintable on a 0.6 mm nozzle, so
    # the radar's side (Y) restraint moved here: two ribs joined to the
    # +/-Y cavity walls over the radar bay. X span = radarCx +/-
    # (bayW - 0.6mm)/2 = -19.0..-4.0 mm (print-fix 2026-09-07: 0.3 mm
    # clearance per end to the plate's +/-X fence walls' inner faces at
    # -19.3/-3.7 so the lid doesn't force-fit against them; was coplanar).
    # Rib inner faces at y = +/-(intH/2 - 0.74 mm) = +/-22.26 -> 0.25 mm
    # clearance per side to the board edges (+/-22.01). z 6..14: top face
    # coplanar with the interior window-pocket floor (z=14), no volume
    # overlap. The rects extend 0.5 mm into the walls so the Join
    # reliably merges.
    rW, clear = p(des, "radarW"), p(des, "boardClear")
    bayW = rW + 2 * clear
    ribL = bayW - 0.6 * MM            # rib X length (cm), centered on rCx
    ribT = 0.74 * MM
    ribInY = intH / 2 - ribT          # rib inner face (cm)
    sk = comp.sketches.add(comp.xYConstructionPlane)
    for sy in (-1, 1):
        y0, y1 = ribInY, intH / 2 + 0.5 * MM
        rect(sk, rCx, sy * (y0 + y1) / 2, ribL, y1 - y0)
    profs = collection([sk.profiles.item(i) for i in range(sk.profiles.count)])
    extrude(comp, profs, 6 * MM, 14 * MM,
            adsk.fusion.FeatureOperations.JoinFeatureOperation,
            participants=[shell_body])
    print("radar retention ribs ok (inner faces y=+/-%.2f mm, x %.1f..%.1f, "
          "z 6..14)" % (ribInY * 10, (rCx - ribL / 2) * 10,
                        (rCx + ribL / 2) * 10))

    # 4c: rib self-centering lead-in chamfer (print-fix 2026-09-07):
    # 45 deg on each rib's lower-inner edge (the long X-direction edges
    # at z=6, y=+/-22.26) so an off-center radar board is nudged into
    # the bay as the lid closes. The prescribed 0.8 mm is refused by the
    # kernel (ASM_BL_UNFIN_SHEET): the rib is only 0.74 mm thick, so the
    # chamfer's horizontal leg overruns the rib's bottom face into the
    # concave wall corner at y=+/-23. Fallback (same intent, recorded):
    # 0.6 mm equal-distance, leaving 0.14 mm of bottom face to the wall.
    # Nice-to-have: if both sizes are refused, continue without.
    def rib_edges():
        edges = adsk.core.ObjectCollection.create()
        for e in shell_body.edges:
            g = e.geometry
            if not isinstance(g, adsk.core.Line3D):
                continue
            v = g.startPoint.vectorTo(g.endPoint)
            v.normalize()
            if abs(abs(v.x) - 1) > 1e-6:
                continue
            mz = (g.startPoint.z + g.endPoint.z) / 2
            my = (g.startPoint.y + g.endPoint.y) / 2
            if (abs(mz - 6 * MM) < 0.005 and abs(abs(my) - ribInY) < 0.005):
                edges.add(e)
        return edges

    applied = None
    for dist_mm in (0.8, 0.6):
        try:
            edges = rib_edges()
            if edges.count != 2:
                raise RuntimeError("expected 2 rib lower-inner edges, "
                                   "found %d" % edges.count)
            ch = comp.features.chamferFeatures
            chi = ch.createInput(edges, False)
            chi.setToEqualDistance(
                adsk.core.ValueInput.createByReal(dist_mm * MM))
            ch.add(chi)
            applied = dist_mm
            break
        except Exception as exc:
            print("rib chamfer %.1fmm refused: %s" % (dist_mm, exc))
    if applied:
        print("rib lead-in chamfers ok (%.1fmm x 45deg on 2 edges)" % applied)
    else:  # nice-to-have; square rib is acceptable
        print("RIB CHAMFER SKIPPED entirely")

    # 5: snap bumps on the inner -X wall, z centered -1mm (rects extend
    # into the wall so the Join reliably merges with the shell body; proud
    # amount into the cavity is snapBump), at y +/-12. The +X pair (at
    # y +/-19 outboard of the pod box for most of 2026-10-25, snapYpx) is
    # gone since Task 9d: the box's inner +/-Y walls carry the lid's +X
    # snaps instead (step 5d, into the wing's pockets), so the +X wall
    # stubs beside the box are plain.
    snap = p(des, "snapBump")
    sk = comp.sketches.add(comp.xYConstructionPlane)
    cx = -(intW / 2 + (wall - snap) / 2)  # spans -(intW/2+wall) .. -(intW/2-snap)
    for sy in (-1, 1):
        rect(sk, cx, sy * 12 * MM, snap + wall, 6 * MM)
    profs = collection([sk.profiles.item(i) for i in range(sk.profiles.count)])
    extrude(comp, profs, -1.6 * MM, -0.4 * MM,
            adsk.fusion.FeatureOperations.JoinFeatureOperation,
            participants=[shell_body])
    print("snap bumps ok (-X at y +/-12; the +X pair is on the pod box's walls, step 5d)")

    # 5b. XIAO hold-down boss (change request 2026-09-07). Nothing held the
    # XIAO down on its four 3 mm posts; the board could lift off them. This
    # boss descends from the shell's front inner face to just above the
    # XIAO's RF shield can, capturing the board when the lid snaps shut.
    #   Measured on the live vendor model: the shield can is a flat plateau
    #   at z = 6.25 mm spanning about x +0.5..+11.5, y -6..+6; the USB-C
    #   connector is TALLER (z = 7.40) at x +13..+17, so the boss must stay
    #   well clear of it.
    #   Boss: 7 x 7 mm square centered at (x=+6.0, y=0) -> x 2.5..9.5,
    #   y -3.5..+3.5, entirely on the shield plateau and 3.5 mm clear of the
    #   USB connector. Extruded z 6.40 (0.15 mm above the shield) up to the
    #   front inner face at intD = 14.0. It lands on solid front wall: the
    #   radar window pockets span x -21..-2, so there is no overlap.
    BOSS_CX, BOSS_CY = 6.0 * MM, 0.0
    BOSS_W = 7.0 * MM
    BOSS_Z0 = 6.40 * MM          # RF shield top 6.25 + 0.15 clearance
    sk = comp.sketches.add(comp.xYConstructionPlane)
    rect(sk, BOSS_CX, BOSS_CY, BOSS_W, BOSS_W)
    extrude(comp, sk.profiles.item(0), BOSS_Z0, intD,
            adsk.fusion.FeatureOperations.JoinFeatureOperation,
            participants=[shell_body])
    if comp.bRepBodies.count != 1:
        raise RuntimeError("boss did not merge with the shell: %d bodies"
                           % comp.bRepBodies.count)
    print("xiao hold-down boss ok (%.1f x %.1f mm at x=%.1f, y=%.1f, "
          "z %.2f..%.2f)" % (BOSS_W * 10, BOSS_W * 10, BOSS_CX * 10,
                             BOSS_CY * 10, BOSS_Z0 * 10, intD * 10))

    # 5c. POD BOX (2026-10-25, third PIR layout; widened and given the
    # bayonet notches by the fourth, Task 9d, the same day). The PIR sensor
    # sits in a straight socket on the back plate's wing (02_backplate.py
    # step 14); the shell covers it with a hollow box that REPLACES its +X
    # wall over the pod's width, and the bezel (step 8) holds the sensor
    # down through the box's top. Done BEFORE step 6 so the edge-softening
    # selectors see the final outline and fillet/chamfer the box with the
    # rest.
    #
    #   old wall   x 21..23 (the shell's +X wall) is removed over
    #              |y| <= pirBoxHalfY from the back rim up to z 14, so the
    #              cavity opens straight into the box: the plate's wing
    #              passes through at z -8..-2 and the sensor's wires run
    #              over it into the XIAO bay with nothing in the way. The
    #              2 mm top (z 14..16) stays: it is the shell's flat front
    #              face, which continues over the box.
    #   box        outer x 21..(pirCx + pirBoxHalfX + wall) = 21..51,
    #              y +/-(pirBoxHalfY + wall) = +/-17.5, z -8..16, joined
    #              (it overlaps the wall stubs at |y| 15.5..17.5, which
    #              become the box's +/-Y walls' first 2 mm); its cavity
    #              x 21..(pirCx + pirBoxHalfX) = 21..49, y +/-15.5,
    #              z -8..14 is cut out again. Walls 2 mm, same as the
    #              shell's; the wing sits in it with rimGap all round like
    #              the plate in the shell. (9c: y +/-13.5 inside; 9d
    #              widened it for the bezel's lugs, which reach r 14.3.)
    #   lens hole  r pirHoleR (12.8) through the top at (pirCx, 0): the
    #              lens ring (r 10.3) and its two latch tabs (r 11.1) pass,
    #              the ring's top face is flush with the shell's face, the
    #              dome stands 11 mm proud, and the bezel's skirt (r 12.6)
    #              drops through round the lens with 0.2 to spare. Its rim
    #              stays sharp (the front chamfer in 6b skips it).
    #   notches    three, through the top skin (z 14..16) at 60, 180 and
    #              300 deg from +X: radial pirHoleR..pirNotchR (12.8..14.6),
    #              tangential width pirNotchW (4.6). The bezel's lugs
    #              (r 12.6..14.3, 4.0 wide) drop through them; a 30 deg turn
    #              then parks the lugs under the solid top at 90/210/330
    #              (step 8 checks the lug sweep against the cavity walls).
    #              They are hidden under the bezel's flange (r 15.3) once
    #              it is on.
    # Print: face-down the box is walls plus a flat top with a hole and
    # three small cut-outs, no overhang anywhere.
    pirCx = p02(des, "pirCx")
    boxHalfY = p02(des, "pirBoxHalfY")                       # 15.5 mm
    boxOutY = boxHalfY + wall                                # 17.5 mm
    lensR = p02(des, "pirHoleR")
    notchW, notchR = p02(des, "pirNotchW"), p02(des, "pirNotchR")
    boxHalfX = p02(des, "pirBoxHalfX")
    xIn = intW / 2                               # 21: the old wall's inner line
    xBoxIn = pirCx + boxHalfX                    # 49
    xBoxOut = xBoxIn + wall                      # 51
    z_top, z_back = intD + wall, -backT          # 16, -8
    NOTCH_ANGLES = (60.0, 180.0, 300.0)          # deg from +X; rest = +30
    if lensR + 0.1 >= boxHalfY:
        raise RuntimeError("lens hole r %.1f leaves under 1 mm of top to the box cavity "
                           "wall (y %.1f)" % (lensR * 10, boxHalfY * 10))
    if pirCx - lensR < xIn + 0.1:
        raise RuntimeError("lens hole reaches x %.2f, under 1 mm from the old wall line"
                           % ((pirCx - lensR) * 10))
    # (9d: the r 12.8 hole at x 35.5 ends 0.7 from the cavity's +X wall at
    # 49, where the top runs on over the 2 mm wall, so 2.7 mm of material
    # to the outside; 9c asked 1 mm here, 0.5 is the rule now)
    if xBoxIn - (pirCx + lensR) < 0.05:
        raise RuntimeError("lens hole leaves under 0.5 mm of top before the box's +X wall")
    # the notches must stay over open ceiling: inside the box's +/-Y
    # cavity walls and its +X wall by 0.5 (the lug then has a solid top to
    # turn under), and at 180 deg they may run past the old wall line
    # (x 21) onto the main cavity's ceiling, which is the same z 14, but
    # not as far as the XIAO hold-down boss (x 2.5..9.5)
    notch_corners = []
    for a in NOTCH_ANGLES:
        ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
        for rr in (lensR, notchR):
            for t in (-notchW / 2, notchW / 2):
                notch_corners.append((pirCx + rr * ca - t * sa, rr * sa + t * ca))
    for x, y in notch_corners:
        if abs(y) > boxHalfY - 0.05 or x > xBoxIn - 0.05 or x < 1.5:
            raise RuntimeError("bayonet notch corner (%.2f, %.2f) is not over open ceiling "
                               "(|y| < %.2f, %.1f < x < %.2f)"
                               % (x * 10, y * 10, (boxHalfY - 0.05) * 10, 15.0,
                                  (xBoxIn - 0.05) * 10))
    # (a) remove the old +X wall over the box's width, back rim to z 14
    sk = comp.sketches.add(comp.xYConstructionPlane)
    rect(sk, (xIn + intW / 2 + wall) / 2, 0, wall + 0.2 * MM, 2 * boxHalfY)
    extrude(comp, sk.profiles.item(0), z_back - 0.1 * MM, intD,
            adsk.fusion.FeatureOperations.CutFeatureOperation,
            participants=[shell_body])
    # (b) the box's outer block, full height, joined to the wall stubs
    sk = comp.sketches.add(comp.xYConstructionPlane)
    rect(sk, (xIn + xBoxOut) / 2, 0, xBoxOut - xIn, 2 * boxOutY)
    extrude(comp, sk.profiles.item(0), z_back, z_top,
            adsk.fusion.FeatureOperations.JoinFeatureOperation,
            participants=[shell_body])
    if comp.bRepBodies.count != 1:
        raise RuntimeError("pod box did not merge with the shell: %d bodies"
                           % comp.bRepBodies.count)
    # (c) its cavity, open to the shell's cavity at x 21 (the cut starts
    # 0.1 mm inside the main cavity so no sliver of wall survives there)
    sk = comp.sketches.add(comp.xYConstructionPlane)
    rect(sk, (xIn - 0.1 * MM + xBoxIn) / 2, 0, xBoxIn - xIn + 0.1 * MM, 2 * boxHalfY)
    extrude(comp, sk.profiles.item(0), z_back - 0.1 * MM, intD,
            adsk.fusion.FeatureOperations.CutFeatureOperation,
            participants=[shell_body])
    # (d) lens hole through the top
    sk = comp.sketches.add(comp.xYConstructionPlane)
    sk.sketchCurves.sketchCircles.addByCenterRadius(
        adsk.core.Point3D.create(pirCx, 0.0, 0), lensR)
    extrude(comp, sk.profiles.item(0), intD - 0.1 * MM, z_top + 0.1 * MM,
            adsk.fusion.FeatureOperations.CutFeatureOperation,
            participants=[shell_body])
    # (e) the three bayonet notches: each a box in plan, radial from
    # 0.3 inside the hole (so no sliver of top survives at the hole's rim)
    # out to notchR, tangential +/-notchW/2, rotated to its angle about the
    # hole's axis; one sketch, three profiles, one cut through the top
    sk = comp.sketches.add(comp.xYConstructionPlane)
    lines = sk.sketchCurves.sketchLines
    for a in NOTCH_ANGLES:
        ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
        pts = []
        for rr, t in ((lensR - 0.03, -notchW / 2), (notchR, -notchW / 2),
                      (notchR, notchW / 2), (lensR - 0.03, notchW / 2)):
            pts.append(adsk.core.Point3D.create(pirCx + rr * ca - t * sa,
                                                rr * sa + t * ca, 0))
        for i in range(4):
            lines.addByTwoPoints(pts[i], pts[(i + 1) % 4])
    profs = collection([sk.profiles.item(i) for i in range(sk.profiles.count)])
    if profs.count != 3:
        raise RuntimeError("expected 3 bayonet notch profiles, found %d" % profs.count)
    extrude(comp, profs, intD - 0.1 * MM, z_top + 0.1 * MM,
            adsk.fusion.FeatureOperations.CutFeatureOperation,
            participants=[shell_body])
    if comp.bRepBodies.count != 1:
        raise RuntimeError("pod box cavity / lens hole / notches split the shell: %d bodies"
                           % comp.bRepBodies.count)
    print("pod box ok: +X wall removed over y +/-%.1f (z %.0f..%.0f); box x %.0f..%.0f, "
          "y +/-%.1f, z %.0f..%.0f, cavity to x %.0f; lens hole r %.1f at (%.1f, 0) "
          "through the top; bayonet notches r %.1f..%.1f, %.1f wide, at %s deg"
          % (boxHalfY * 10, z_back * 10, intD * 10, xIn * 10, xBoxOut * 10,
             boxOutY * 10, z_back * 10, z_top * 10, xBoxIn * 10, lensR * 10,
             pirCx * 10, lensR * 10, notchR * 10, notchW * 10,
             "/".join("%.0f" % a for a in NOTCH_ANGLES)))

    # 5d. WING SNAP BUMPS (Task 9d): the lid's +X snap pair, on the box's
    # inner +/-Y walls, snapBump (0.5) proud into the cavity, 6 long along
    # X centred wingSnapX, z wingSnapZ +/-0.5, matching the blind pockets
    # in the plate's wing (02_backplate.py step 14a': 0.6 deep, 6.2 long,
    # +/-0.6 tall, so 0.1 of slop a side). The rects extend 1 mm into the
    # wall so the Join merges by volume. The lid comes down over the wing
    # from the front: the walls ride over the wing's edge (z -2) and click
    # in 2.5 mm further down. Same guards as 02 on the position, so a
    # hand-edited parameter cannot slip past a stale plate.
    snapX, snapZ = p02(des, "wingSnapX"), p02(des, "wingSnapZ")
    corner = p(des, "cornerFillet")
    zWing = z_back + 6.0 * MM                    # wing top, -2
    rimGapX = p02(des, "rimGapX")                # the plate/wing X allowance (02 owns it)
    xWing1 = xBoxIn - rimGapX
    if not (intW / 2 - rimGapX + 0.1 <= snapX - 0.31 and snapX + 0.31 <= xWing1 - corner - 0.05):
        raise RuntimeError("wing snap bump x %.1f..%.1f is not inside the wing's straight "
                           "+/-Y faces" % ((snapX - 0.3) * 10, (snapX + 0.3) * 10))
    if not (z_back + 0.1 <= snapZ - 0.06 and snapZ + 0.06 <= zWing - 0.1):
        raise RuntimeError("wing snap bump z %.1f..%.1f: the pocket would leave under 1 mm "
                           "of wing above or below it" % ((snapZ - 0.05) * 10, (snapZ + 0.05) * 10))
    sk = comp.sketches.add(comp.xYConstructionPlane)
    for sy in (-1, 1):
        y0, y1 = boxHalfY - snap, boxHalfY + 1.0 * MM
        rect(sk, snapX, sy * (y0 + y1) / 2, 6 * MM, y1 - y0)
    profs = collection([sk.profiles.item(i) for i in range(sk.profiles.count)])
    if profs.count != 2:
        raise RuntimeError("expected 2 wing bump profiles, found %d" % profs.count)
    extrude(comp, profs, snapZ - 0.5 * MM, snapZ + 0.5 * MM,
            adsk.fusion.FeatureOperations.JoinFeatureOperation,
            participants=[shell_body])
    if comp.bRepBodies.count != 1:
        raise RuntimeError("wing snap bumps did not merge with the shell: %d bodies"
                           % comp.bRepBodies.count)
    print("wing snap bumps ok: on the box's inner +/-Y walls (y +/-%.1f), %.1f proud, "
          "x %.1f..%.1f, z %.1f..%.1f"
          % (boxHalfY * 10, snap * 10, (snapX - 0.3) * 10, (snapX + 0.3) * 10,
             (snapZ - 0.05) * 10, (snapZ + 0.05) * 10))

    # 6. soften exterior edges for hand comfort (change request 2026-09-07).
    # Operates on shell_body ONLY (fillet/chamfer features act on its edges,
    # so they are participant-safe by construction; BackPlate untouched).
    # Order matters: vertical corner fillets FIRST (they change the corner
    # topology the later perimeter selections rely on).
    # Outline since 2026-10-25 (pod box, step 5c): the shell rectangle with
    # the box grown off its +X side over |y| <= boxOutY (17.5 since Task
    # 9d, 15.5 before), so the outer boundary at any z level is 8
    # straights (-X; +/-Y; the two +X stubs at |y| 17.5..22.5; the box's
    # +/-Y sides; the box's +X end) and, after 6a, 6 corner arcs (the
    # shell's 4 and the box's 2) = 14 edges. The two concave T-junction
    # corners at (23, +/-17.5) are vertices, not edges, and stay sharp.
    # The lens hole and the three bayonet notches lie inside the front
    # face, away from its perimeter, so the counts did not change with 9d
    # (checked on the 2026-10-25 build: 6 / 14 / 14).
    corner = p(des, "cornerFillet")
    cham = p(des, "frontChamfer")
    soft = p(des, "softFillet")
    ox, oy = intW / 2 + wall, intH / 2 + wall   # outer half-extents (cm)
    EPS = 0.005  # 0.05 mm tolerance (cm)

    def mid(g):
        return ((g.startPoint.x + g.endPoint.x) / 2,
                (g.startPoint.y + g.endPoint.y) / 2,
                (g.startPoint.z + g.endPoint.z) / 2)

    def line_dir(g):
        v = g.startPoint.vectorTo(g.endPoint)
        v.normalize()
        return v

    def add_fillet(edges, radius):
        fil = comp.features.filletFeatures
        inp = fil.createInput()
        rv = adsk.core.ValueInput.createByReal(radius)
        try:
            inp.edgeSetInputs.addConstantRadiusEdgeSet(
                collection(edges), rv, False)
        except AttributeError:  # older API shape
            inp.addConstantRadiusEdgeSet(collection(edges), rv, False)
        return fil.add(inp)

    # 6a. six outer vertical corner edges: lines parallel to Z with |x|
    # and |y| at the shell's outer values (4), or at the box's far corners
    # (xBoxOut, +/-boxOutY) (2). The box corners run the full z -8..16
    # like the shell's.
    verts = []
    for e in shell_body.edges:
        g = e.geometry
        if not isinstance(g, adsk.core.Line3D):
            continue
        d = line_dir(g)
        if abs(abs(d.z) - 1) > 1e-6:
            continue
        mx, my, _ = mid(g)
        if ((abs(abs(mx) - ox) < EPS and abs(abs(my) - oy) < EPS)
                or (abs(mx - xBoxOut) < EPS and abs(abs(my) - boxOutY) < EPS)):
            verts.append(e)
    print("corner fillet edges found:", len(verts))
    if len(verts) != 6:
        raise RuntimeError("expected 6 vertical corner edges (4 shell + 2 box), found %d"
                           % len(verts))
    add_fillet(verts, corner)
    print("corner fillets ok (r=%.2f mm on 6 edges)" % (corner * 10))

    # Outer-perimeter edge selector at a z level: straight edges lying on the
    # outer faces (|x|=ox, |y|=oy, the box's |y|=boxOutY beyond x ox, or
    # the box's x=xBoxOut) plus the six corner-fillet arcs. The lens hole's
    # circle (r pirHoleR, cut into arcs by the notches), the notches'
    # short lines (at x 20.9..23.7 / y +/-2.3 for the 180 deg one, nowhere
    # near |x| = 23 or |y| = 17.5 on a z-level face) and the cavity
    # outlines are other radii / other coordinates and are never picked.
    # At both z_top and z_back the boundary is one closed loop of 8
    # straights + 6 arcs = 14 edges (8 before the pod box, 2026-10-25).
    def perimeter_edges(zlev):
        found = []
        for e in shell_body.edges:
            g = e.geometry
            if isinstance(g, adsk.core.Line3D):
                if (abs(g.startPoint.z - zlev) > EPS
                        or abs(g.endPoint.z - zlev) > EPS):
                    continue
                mx, my, _ = mid(g)
                if (abs(abs(mx) - ox) < EPS or abs(abs(my) - oy) < EPS
                        or (abs(abs(my) - boxOutY) < EPS and mx > ox - EPS)
                        or abs(mx - xBoxOut) < EPS):
                    found.append(e)
            elif isinstance(g, (adsk.core.Arc3D, adsk.core.Circle3D)):
                c = g.center
                if abs(c.z - zlev) >= EPS or abs(g.radius - corner) >= EPS:
                    continue
                if ((abs(abs(c.x) - (ox - corner)) < EPS
                        and abs(abs(c.y) - (oy - corner)) < EPS)
                        or (abs(c.x - (xBoxOut - corner)) < EPS
                            and abs(abs(c.y) - (boxOutY - corner)) < EPS)):
                    found.append(e)
        return found

    def add_chamfer(edges, dist):
        ch = comp.features.chamferFeatures
        chi = ch.createInput(collection(edges), False)
        chi.setToEqualDistance(adsk.core.ValueInput.createByReal(dist))
        return ch.add(chi)

    # 6b. front-face perimeter chamfer (prints clean bed-side). The z=16
    # outer boundary, shell plus box, is one closed loop of 14 edges,
    # chamfered as a single feature; the lens hole rim is left sharp.
    front = perimeter_edges(z_top)
    print("front perimeter edges found:", len(front))
    if len(front) != 14:
        raise RuntimeError("expected 14 front perimeter edges (8 lines + 6 arcs), found %d"
                           % len(front))
    add_chamfer(front, cham)
    print("front chamfer ok (%.2f mm on %d edges)" % (cham * 10, len(front)))

    # 6c. back rim outer edge fillet, the same 14-edge loop at z -8 (the
    # box's cavity is open at the back rim like the shell's, so its walls'
    # outer edges continue the rim).
    rim = perimeter_edges(z_back)
    print("back rim edges found:", len(rim))
    if len(rim) != 14:
        raise RuntimeError("expected 14 back rim edges (8 lines + 6 arcs), found %d"
                           % len(rim))
    add_fillet(rim, soft)
    print("rim fillet ok (r=%.2f mm on %d edges)" % (soft * 10, len(rim)))
    if comp.bRepBodies.count != 1:
        raise RuntimeError("edge softening split the shell: %d bodies"
                           % comp.bRepBodies.count)

    # 7. (deleted 2026-10-25 evening) the wing notch in the +X wall. The
    # pod box (step 5c) removes that stretch of wall entirely and encloses
    # the wing instead.

    print("FrontShell bodies:", comp.bRepBodies.count)

    # 8. PIR BEZEL (Task 9d, 2026-10-25). A separate component, built in
    # its OWN frame (axis +Z, the flange's underside on z 0 = the shell's
    # face when fitted; r is distance from the axis), exported as its own
    # STL. It retains the sensor from the front: a bayonet ring that drops
    # on over the dome, its lugs through the top's notches, and turns
    # 30 deg so the lugs sit under the top; its lip then bears on the
    # dome's flank with a designed preload, clamping the sensor's flange
    # onto the socket boss's rim (the sensor still turns freely before the
    # bezel goes on). One revolved profile plus three lugs = one body.
    #
    #   flange  ring r pirBezelInnerR..pirBezelFlangeR (11.6..15.3), z 0..
    #           pirBezelFlangeT (1.2): sits on the face, hides the hole
    #           and the notches.
    #   lip     above the flange: inner surface a cone from (r 11.6, z 1.2)
    #           up and in to (r pirBezelLipR 10.0, z 1.2 + pirBezelLipH),
    #           outer surface the parallel cone 1.0 further out (from
    #           r pirBezelSkirtRo 12.6 to 11.0), flat top 1 mm wide. The
    #           upper inner edge is the bearing ring on the dome's
    #           spherical cap (sphere R pirDomeR centred on the axis at
    #           the face, valid above case z 19.8): the dome's surface at
    #           r 10.0 is sqrt(R^2 - r^2) = 4.311 above the face, and
    #           pirBezelLipH is COMPUTED (02's ensure_params) so that edge
    #           sits pirBezelPreload (0.2) below it (= 2.912). Below the
    #           cap the dome's flank is a 2 deg taper (r 10.35 at z 16.1
    #           to 10.21 at z 19.8, probed on the STEP); the cone comes
    #           in at 29 deg so it clears that flank except in the last
    #           ~0.4 mm under the edge, where it wedges into the dome by
    #           at most ~0.08 radially: that is the preload band, and the
    #           guard below keeps it under 1 mm tall.
    #   skirt   below the flange: tube r pirBezelSkirtRi..pirBezelSkirtRo
    #           (11.5..12.6) from z 0 down to -pirBezelSkirtH (-3.8,
    #           computed: through the 2 mm top, 0.3 of clearance, then the
    #           lug): passes the r 12.8 hole with 0.2 and the lens's latch
    #           tabs (r 11.1) with 0.4.
    #   lugs    three, at the skirt's foot: z -3.8..-2.3 (pirLugT 1.5),
    #           radial from inside the skirt wall out to pirLugRo (14.3),
    #           tangential pirLugW (4.0), centred at 60/180/300 deg: they
    #           drop through the notches (14.6 / 4.6) and, after a 30 deg
    #           turn, sit at 90/210/330 under the top with their tops 0.3
    #           below its underside (case z 13.7 vs 14.0). At 330 the
    #           leading corner comes within about 0.1 mm of the box
    #           cavity's +X wall (x 49) and meets it about 1.3 deg further
    #           on: that wall is the turn's stop (the pattern is symmetric
    #           about X, so turning the other way stops the same way at
    #           30/150/270). The sweep is checked below.
    # The occurrence is parked in the case at (pirCx, 0, zTop), turned to
    # the REST angles, so 91_pir_fit.py tests the fitted state; the STL
    # comes out in the local frame (05_export.py exports the component).
    for occ in list(root.occurrences):
        if occ.component.name.startswith("PirBezel"):
            occ.component.name = occ.component.name + "_deleted"
            occ.deleteMe()
    flangeR, flangeT = p02(des, "pirBezelFlangeR"), p02(des, "pirBezelFlangeT")
    innerR, lipR = p02(des, "pirBezelInnerR"), p02(des, "pirBezelLipR")
    lipH, preload = p02(des, "pirBezelLipH"), p02(des, "pirBezelPreload")
    skirtRi, skirtRo = p02(des, "pirBezelSkirtRi"), p02(des, "pirBezelSkirtRo")
    skirtH = p02(des, "pirBezelSkirtH")
    lugT, lugW, lugRo = p02(des, "pirLugT"), p02(des, "pirLugW"), p02(des, "pirLugRo")
    domeR = p02(des, "pirDomeR")
    lipWall = skirtRo - innerR                   # 1.0: the lip wall's horizontal width
    lipTop = flangeT + lipH                      # 4.112 above the face
    # the dome's flank below its spherical cap, probed on the STEP in the
    # case frame (bezel frame = case - z_top): straight taper between
    DOME_FLANK = ((16.1 * MM - z_top, 10.346 * MM), (19.8 * MM - z_top, 10.21 * MM))
    REST_TURN = 30.0                             # deg, insertion -> rest
    TAB_R, HOLE_CLEAR, LUG_CLEAR = 11.1 * MM, 0.02, 0.03
    # --- guards, all in the bezel frame unless said ---
    domeZ = math.sqrt(domeR * domeR - lipR * lipR)       # dome surface above the face at r lipR
    if abs((domeZ - lipTop) - preload) > 1e-6:
        raise RuntimeError("pirBezelLipH %.4f does not put the lip edge pirBezelPreload under "
                           "the dome (dome %.4f, edge %.4f): it is an expression, re-create it"
                           % (lipH * 10, domeZ * 10, lipTop * 10))
    if lipR >= innerR or lipWall < 0.08:
        raise RuntimeError("lip profile is not a cone leaning inward with >= 0.8 mm of wall")
    # the lip edge must be on the spherical cap (above the taper flank)...
    (zf0, rf0), (zf1, rf1) = DOME_FLANK
    if lipTop < zf1 or lipR > rf1:
        raise RuntimeError("lip edge (r %.2f, %.3f above the face) is on the dome's taper flank, "
                           "not its spherical cap (cap above %.2f, r < %.2f): pirBezelLipR too big"
                           % (lipR * 10, lipTop * 10, zf1 * 10, rf1 * 10))
    # ...and the inner cone must clear the flank below the preload band:
    # where the cone's radius is under the flank's, it is inside the dome;
    # that may only happen within 1 mm under the edge (the band)
    def cone_r(z):
        return innerR - (innerR - lipR) * (z - flangeT) / lipH
    def flank_r(z):
        if z <= zf0:
            return rf0
        if z >= zf1:
            return math.sqrt(max(domeR * domeR - z * z, 0.0))
        return rf0 + (rf1 - rf0) * (z - zf0) / (zf1 - zf0)
    band_z0 = lipTop
    z = flangeT
    while z < lipTop:
        if cone_r(z) < flank_r(z):
            band_z0 = min(band_z0, z)
        z += 0.001
    if lipTop - band_z0 > 0.1 + 1e-9:
        raise RuntimeError("the lip's inner cone is inside the dome from %.3f to %.3f above the "
                           "face (%.2f mm): more than the 1 mm preload band; steepen the cone "
                           "(pirBezelInnerR) or move the edge" % (band_z0 * 10, lipTop * 10,
                                                                  (lipTop - band_z0) * 10))
    if skirtRo + HOLE_CLEAR > lensR + 1e-9:
        raise RuntimeError("skirt r %.2f does not pass the r %.2f hole with 0.2" % (skirtRo * 10, lensR * 10))
    if skirtRi < TAB_R + 0.04 - 1e-9:
        raise RuntimeError("skirt inner r %.2f is under 0.4 mm from the latch tabs (r 11.1)" % (skirtRi * 10))
    if lugRo + LUG_CLEAR > notchR + 1e-9 or lugW + 2 * LUG_CLEAR > notchW + 1e-9:
        raise RuntimeError("lugs (r %.1f, %.1f wide) do not pass the notches (r %.1f, %.1f wide) "
                           "with 0.3" % (lugRo * 10, lugW * 10, notchR * 10, notchW * 10))
    lugTopCase = z_top - skirtH + lugT                   # 13.7
    lugClear = intD - lugTopCase                         # 0.3
    if lugClear < 0.02 - 1e-9:
        raise RuntimeError("lug tops (case z %.2f) are under 0.2 mm below the top's underside "
                           "(%.1f)" % (lugTopCase * 10, intD * 10))
    if z_top - skirtH > intD - 0.05:
        raise RuntimeError("skirt foot (case z %.2f) does not reach 0.5 under the top" % ((z_top - skirtH) * 10))
    # lug sweep from the notches to the rest angles (and on to the stop):
    # every corner of every lug must stay inside the box cavity (x < xBoxIn,
    # |y| < boxHalfY); the lugs at 180 deg run over the main cavity (x < 21)
    # where the ceiling is the same z 14, and must stay clear of the XIAO
    # boss (x 9.5) by far
    def lug_corners(angle_deg):
        ca, sa = math.cos(math.radians(angle_deg)), math.sin(math.radians(angle_deg))
        out = []
        for rr in (skirtRi, lugRo):
            for t in (-lugW / 2, lugW / 2):
                out.append((pirCx + rr * ca - t * sa, rr * sa + t * ca))
        return out
    min_clear = 1e9
    for step in range(0, int(REST_TURN * 10) + 1):
        turn = step / 10.0
        for a0 in NOTCH_ANGLES:
            for x, y in lug_corners(a0 + turn):
                c = min(xBoxIn - x, boxHalfY - abs(y))
                min_clear = min(min_clear, c)
                if c < 0.005 or x < 1.5:
                    raise RuntimeError("lug corner (%.2f, %.2f) at %.1f deg hits the box cavity "
                                       "wall (x < %.1f, |y| < %.1f)"
                                       % (x * 10, y * 10, a0 + turn, xBoxIn * 10, boxHalfY * 10))
    stop_turn = None
    for step in range(int(REST_TURN * 10), int(REST_TURN * 10) + 300):
        turn = step / 10.0
        hit = any(x > xBoxIn or abs(y) > boxHalfY
                  for a0 in NOTCH_ANGLES for x, y in lug_corners(a0 + turn))
        if hit:
            stop_turn = turn
            break
    print("bezel lug sweep ok: %s -> +%.0f deg, min corner clearance to the box cavity "
          "walls %.2f mm (at rest); the +X wall stops the turn at +%s deg"
          % ("/".join("%.0f" % a for a in NOTCH_ANGLES), REST_TURN, min_clear * 10,
             ("%.1f" % stop_turn) if stop_turn is not None else "never"))
    print("bezel lip: upper inner edge r %.2f at %.3f above the face; dome surface there "
          "%.3f; designed preload %.2f mm; the inner cone wedges into the dome over the "
          "last %.2f mm under the edge. Lug tops %.2f under the top's underside (note: "
          "the preload lifts the bezel by up to %.2f before the lugs touch the top)"
          % (lipR * 10, lipTop * 10, domeZ * 10, preload * 10, (lipTop - band_z0) * 10,
             lugClear * 10, lugClear * 10))

    bz_occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    bz = bz_occ.component
    bz.name = "PirBezel"
    # (a) the revolved profile: a closed polygon in the plane through the
    # axis, (r, z) points, drawn with model->sketch mapping so the XZ
    # plane's sketch axes need no guessing
    sk = bz.sketches.add(bz.xZConstructionPlane)
    prof = [(skirtRi, -skirtH), (skirtRo, -skirtH), (skirtRo, 0.0),
            (flangeR, 0.0), (flangeR, flangeT), (skirtRo, flangeT),
            (lipR + lipWall, lipTop), (lipR, lipTop), (innerR, flangeT),
            (innerR, 0.0), (skirtRi, 0.0)]
    spts = [sk.modelToSketchSpace(adsk.core.Point3D.create(r, 0.0, z)) for r, z in prof]
    for i in range(len(spts)):
        sk.sketchCurves.sketchLines.addByTwoPoints(spts[i], spts[(i + 1) % len(spts)])
    if sk.profiles.count != 1:
        raise RuntimeError("bezel profile sketch has %d profiles, expected 1" % sk.profiles.count)
    rev = bz.features.revolveFeatures
    ri = rev.createInput(sk.profiles.item(0), bz.zConstructionAxis,
                         adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    ri.setAngleExtent(False, adsk.core.ValueInput.createByReal(2 * math.pi))
    rev.add(ri)
    if bz.bRepBodies.count != 1:
        raise RuntimeError("bezel revolve left %d bodies" % bz.bRepBodies.count)
    bz_body = bz.bRepBodies.item(0)
    # (b) the lugs: rotated rectangles in plan, from inside the skirt
    # wall (chord at r skirtRi + 0.3, whose corners stay inside r skirtRo)
    # out to lugRo, extruded z -skirtH..-skirtH + lugT and joined. Sketched
    # on the XY plane: extrude()'s start offset is measured from the
    # sketch plane, so a sketch already at -skirtH would land the lugs at
    # -2 skirtH, in the air (the first build did exactly that: 4 bodies).
    sk = bz.sketches.add(bz.xYConstructionPlane)
    r_in = skirtRi + 0.03
    if math.hypot(r_in, lugW / 2) >= skirtRo:
        raise RuntimeError("lug root chord corners fall outside the skirt wall")
    lines = sk.sketchCurves.sketchLines
    for a in NOTCH_ANGLES:
        ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
        pts = []
        for rr, t in ((r_in, -lugW / 2), (lugRo, -lugW / 2), (lugRo, lugW / 2), (r_in, lugW / 2)):
            pts.append(adsk.core.Point3D.create(rr * ca - t * sa, rr * sa + t * ca, 0))
        for i in range(4):
            lines.addByTwoPoints(pts[i], pts[(i + 1) % 4])
    profs = collection([sk.profiles.item(i) for i in range(sk.profiles.count)])
    if profs.count != 3:
        raise RuntimeError("expected 3 lug profiles, found %d" % profs.count)
    extrude(bz, profs, -skirtH, -skirtH + lugT,
            adsk.fusion.FeatureOperations.JoinFeatureOperation,
            participants=[bz_body])
    if bz.bRepBodies.count != 1:
        raise RuntimeError("bezel lugs did not merge: %d bodies" % bz.bRepBodies.count)
    sk.isVisible = False
    # sanity on the built body, in its own frame (the lip mid-wall probe
    # sits halfway up the cone, 0.55 of the way across its horizontal
    # width from the inner surface)
    IN = adsk.fusion.PointContainment.PointInsidePointContainment
    def bz_solid(r, ang, z):
        a = math.radians(ang)
        return bz_body.pointContainment(adsk.core.Point3D.create(r * math.cos(a), r * math.sin(a), z)) == IN
    checks = ((True, (flangeR + innerR) / 2, 0.0, flangeT / 2, "flange"),
              (True, lipR + lipWall / 2 + 0.55 * (innerR - lipR), 0.0, flangeT + lipH / 2, "lip mid-wall"),
              (False, lipR - 0.02, 0.0, lipTop - 0.01, "inside the lip edge"),
              (False, lipR + lipWall / 2, 0.0, lipTop + 0.02, "above the lip top"),
              (True, (skirtRi + skirtRo) / 2, 0.0, -skirtH / 2, "skirt"),
              (False, skirtRi - 0.03, 0.0, -skirtH / 2, "inside the skirt"),
              (True, (skirtRo + lugRo) / 2, NOTCH_ANGLES[0], -skirtH + lugT / 2, "lug at 60"),
              (True, (skirtRo + lugRo) / 2, NOTCH_ANGLES[1], -skirtH + lugT / 2, "lug at 180"),
              (True, (skirtRo + lugRo) / 2, NOTCH_ANGLES[2], -skirtH + lugT / 2, "lug at 300"),
              (False, (skirtRo + lugRo) / 2, NOTCH_ANGLES[0] + 30, -skirtH + lugT / 2, "no lug at 90"),
              (False, (skirtRo + lugRo) / 2, NOTCH_ANGLES[0], -skirtH + lugT + 0.02, "above the lug at 60"))
    for want, r, ang, z, label in checks:
        if bz_solid(r, ang, z) != want:
            raise RuntimeError("bezel probe %s at (r %.2f, %.0f deg, z %.2f): expected %s"
                               % (label, r * 10, ang, z * 10, "solid" if want else "void"))
    # (c) park it in the case, turned to the rest angles
    m = adsk.core.Matrix3D.create()
    m.setToRotation(math.radians(REST_TURN), adsk.core.Vector3D.create(0, 0, 1),
                    adsk.core.Point3D.create(0, 0, 0))
    m.translation = adsk.core.Vector3D.create(pirCx, 0.0, z_top)
    bz_occ.transform2 = m
    if des.snapshots.hasPendingSnapshot:
        des.snapshots.add()
    print("pir bezel ok: flange r %.1f..%.1f x %.1f, lip to %.3f (wall %.1f wide, edge r %.1f), "
          "skirt r %.1f..%.1f to -%.1f, 3 lugs r ..%.1f x %.1f x %.1f at %s deg; parked at "
          "(%.1f, 0, %.0f) turned +%.0f (lugs at %s)"
          % (innerR * 10, flangeR * 10, flangeT * 10, lipTop * 10, lipWall * 10, lipR * 10,
             skirtRi * 10, skirtRo * 10, skirtH * 10, lugRo * 10, lugW * 10, lugT * 10,
             "/".join("%.0f" % a for a in NOTCH_ANGLES), pirCx * 10, z_top * 10, REST_TURN,
             "/".join("%.0f" % (a + REST_TURN) for a in NOTCH_ANGLES)))
    print("PirBezel bodies:", bz.bRepBodies.count)
