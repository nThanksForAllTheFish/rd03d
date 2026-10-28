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


def corner_box(sk, x0, x1, y0, y1):
    """Axis-aligned rectangle by its two corners (cm), as 02_backplate.py's box();
    named apart from the `box` extrude feature in run()."""
    sk.sketchCurves.sketchLines.addTwoPointRectangle(
        adsk.core.Point3D.create(x0, y0, 0), adsk.core.Point3D.create(x1, y1, 0))


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
    winT = p(des, "windowT")
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
    # end bars at 10.46; the 13.0 figure quoted in earlier notes is the
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

    # 4b/4c. (deleted 2026-10-27) the radar retention ribs and their lead-in
    # chamfers: the board is located by two pins in its own PCB corner
    # notches on the back plate (02_backplate.py step 6b). The shell must
    # be reprinted regardless: the XIAO hold-down boss moved with the
    # rotated board (step 5b).

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
    #   at z = 6.25 mm spanning about x +0.5..+11.5, y -6..+6 with the USB
    #   at +X; the USB-C connector is TALLER (z = 7.40), so the boss must
    #   stay well clear of it.
    #   2026-10-27: the XIAO is rotated 180 deg about Z (04_boards.py), USB
    #   now at -X (shell x -3.2..4.1, z 3.3..7.5) and the shield plateau at
    #   x +5.7..+14.7 (probed on the placed body). The boss moves with it.
    #   Boss: 7 x 7 mm square centered at (x=+10.0, y=0) -> x 6.5..13.5,
    #   y -3.5..+3.5, entirely on the shield plateau and 2.4 mm clear of the
    #   USB connector (was x 2.5..9.5 until 2026-10-27, which the rotated
    #   USB shell would have hit by 11.6 mm^3). Extruded z 6.40 (0.15 mm
    #   above the shield) up to the front inner face at intD = 14.0. It
    #   lands on solid front wall: the radar window pockets span x -21..-2
    #   and the pod box starts at x 21, so there is no overlap.
    BOSS_CX, BOSS_CY = 10.0 * MM, 0.0
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

    # 5c. POD BOX (2026-10-25, third PIR layout; 9d widened it for a
    # bayonet bezel, 9e the same day put it back). The PIR sensor sits in
    # a straight socket on the back plate's wing (02_backplate.py step
    # 14); the shell covers it with a hollow box that REPLACES its +X wall
    # over the pod's width, and the bezel ring (step 8) fills the lens
    # gap in the box's top. Done BEFORE step 6 so the edge-softening
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
    #              y +/-(pirBoxHalfY + wall) = +/-15.5, z -8..16, joined
    #              (it overlaps the wall stubs at |y| 13.5..15.5, which
    #              become the box's +/-Y walls' first 2 mm); its cavity
    #              x 21..(pirCx + pirBoxHalfX) = 21..49, y +/-13.5,
    #              z -8..14 is cut out again. Walls 2 mm, same as the
    #              shell's; the wing sits in it with the measured fit
    #              allowance like the plate in the shell.
    #   lens hole  r pirHoleR (11.6) through the top at (pirCx, 0): the
    #              lens ring (r 10.3) and its two latch tabs (r 11.0) pass,
    #              the ring's top face is flush with the shell's face, the
    #              dome stands 11 mm proud, and the bezel ring (step 8,
    #              skirt OD = pirHoleR, prints 0.1 a side under in the
    #              true-printing hole) fills the gap round the lens. Its
    #              rim stays sharp (the front chamfer in 6b skips it).
    #              (9d had r 12.8 with three bayonet notches; gone.)
    # Print: face-down the box is walls plus a flat top with a hole, no
    # overhang anywhere.
    pirCx = p02(des, "pirCx")
    boxHalfY = p02(des, "pirBoxHalfY")                       # 13.5 mm
    boxOutY = boxHalfY + wall                                # 15.5 mm
    lensR = p02(des, "pirHoleR")
    boxHalfX = p02(des, "pirBoxHalfX")
    xIn = intW / 2                               # 21: the old wall's inner line
    xBoxIn = pirCx + boxHalfX                    # 49
    xBoxOut = xBoxIn + wall                      # 51
    z_top, z_back = intD + wall, -backT          # 16, -8
    if lensR + 0.1 >= boxHalfY:
        raise RuntimeError("lens hole r %.1f leaves under 1 mm of top to the box cavity "
                           "wall (y %.1f)" % (lensR * 10, boxHalfY * 10))
    if pirCx - lensR < xIn + 0.1:
        raise RuntimeError("lens hole reaches x %.2f, under 1 mm from the old wall line"
                           % ((pirCx - lensR) * 10))
    if xBoxIn - (pirCx + lensR) < 0.1:
        raise RuntimeError("lens hole leaves under 1 mm of top before the box's +X wall")
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
    if comp.bRepBodies.count != 1:
        raise RuntimeError("pod box cavity / lens hole split the shell: %d bodies"
                           % comp.bRepBodies.count)
    print("pod box ok: +X wall removed over y +/-%.1f (z %.0f..%.0f); box x %.0f..%.0f, "
          "y +/-%.1f, z %.0f..%.0f, cavity to x %.0f; lens hole r %.1f at (%.1f, 0) "
          "through the top (no notches)"
          % (boxHalfY * 10, z_back * 10, intD * 10, xIn * 10, xBoxOut * 10,
             boxOutY * 10, z_back * 10, z_top * 10, xBoxIn * 10, lensR * 10,
             pirCx * 10))

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
    # the box grown off its +X side over |y| <= boxOutY (15.5), so the
    # outer boundary at any z level is 8 straights (-X; +/-Y; the two +X
    # stubs at |y| 15.5..22.5; the box's +/-Y sides; the box's +X end)
    # and, after 6a, 6 corner arcs (the shell's 4 and the box's 2) = 14
    # edges. The two concave T-junction corners at (23, +/-15.5) are
    # vertices, not edges, and stay sharp. The lens hole lies inside the
    # front face, away from its perimeter (6 / 14 / 14 on every build
    # since the box, 2026-10-25).
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
    # circle (r pirHoleR) and the cavity outlines are other radii / other
    # coordinates and are never picked.
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

    # 7b. LED LIGHT-PIPE HOLE (2026-10-27). The XIAO's yellow user LED
    # (GPIO15) flashes for every published event and was visible through
    # the white shell; the blue one needs a pipe. A straight hole of
    # ledPipeD through the front wall over the LED at (ledX, ledY), the
    # params 02_backplate.py creates from the user's photo. Cut AFTER the
    # edge finishing (6b/6c count the front perimeter loop; a hole adds
    # two circles the loop filter would otherwise see). The LED is clear
    # of the radome pocket (x <= -2), the boss (x >= 6.5) and the USB
    # shell (|y| < 4.47), asserted below, so the pipe lands on plain wall.
    ledX, ledY, ledD = p02(des, "ledX"), p02(des, "ledY"), p02(des, "ledPipeD")
    if ledX - ledD / 2 < -2.0 * MM + 1.0 * MM:
        raise RuntimeError("LED hole runs into the radome pocket (x <= -2)")
    if ledX + ledD / 2 > BOSS_CX - BOSS_W / 2 - 1.0 * MM:
        raise RuntimeError("LED hole runs into the hold-down boss")
    if abs(ledY) - ledD / 2 < 4.47 * MM:
        raise RuntimeError("LED hole sits over the USB shell, not the LED")
    sk = comp.sketches.add(comp.xYConstructionPlane)
    sk.sketchCurves.sketchCircles.addByCenterRadius(
        adsk.core.Point3D.create(ledX, ledY, 0), ledD / 2)
    extrude(comp, sk.profiles.item(0), intD - 0.01 * MM, z_top + 0.01 * MM,
            adsk.fusion.FeatureOperations.CutFeatureOperation,
            participants=[shell_body])
    print("led light-pipe hole ok (O%.1f at (%.1f, %.1f), through the front wall z %.1f..%.1f)"
          % (ledD * 10, ledX * 10, ledY * 10, intD * 10, z_top * 10))

    # 7c. CAVITY CORNER FILLS (2026-10-27, user's print review). The
    # cavity's four inside vertical corners get a modelled radius of
    # cavityCornerR ("square minus quarter disc" joined into each corner,
    # z -8..14) so the printed corner is what the model says rather than
    # whatever the nozzle leaves. The plate's corners (02 step 15) are
    # rounded to plateCornerR, larger, so the parts meet on the flats with
    # a defined diagonal gap. After 6a-6c on purpose: the edge-loop
    # selectors must not see the new arcs.
    ccr = p02(des, "cavityCornerR")
    xi, yi = intW / 2, intH / 2
    fills = []
    sk = comp.sketches.add(comp.xYConstructionPlane)
    for sx in (-1, 1):
        for sy in (-1, 1):
            cx, cy = sx * (xi - ccr), sy * (yi - ccr)
            corner_box(sk, min(cx, sx * xi), max(cx, sx * xi), min(cy, sy * yi), max(cy, sy * yi))
            sk.sketchCurves.sketchCircles.addByCenterRadius(
                adsk.core.Point3D.create(cx, cy, 0), ccr)
    for i in range(sk.profiles.count):
        pr = sk.profiles.item(i)
        c = pr.areaProperties().centroid
        if abs(c.x) > xi - 0.4 * ccr and abs(c.y) > yi - 0.4 * ccr:
            fills.append(pr)
    if len(fills) != 4:
        raise RuntimeError("expected 4 cavity corner profiles, found %d" % len(fills))
    extrude(comp, collection(fills), -backT, intD,
            adsk.fusion.FeatureOperations.JoinFeatureOperation,
            participants=[shell_body])
    if comp.bRepBodies.count != 1:
        raise RuntimeError("cavity corner fills did not merge: %d bodies" % comp.bRepBodies.count)
    print("cavity corner fills ok (r %.2f at (+/-%.1f, +/-%.1f), z -8..14)" % (ccr * 10, xi * 10, yi * 10))

    print("FrontShell bodies:", comp.bRepBodies.count)

    # 8. PIR BEZEL RING (Task 9e, 2026-10-25; replaces 9d's bayonet bezel
    # of the same day). A separate component, built in its OWN frame
    # (axis +Z, the flange's underside on z 0 = the shell's face when
    # fitted; r is distance from the axis), exported as its own STL. It
    # fills the gap between the lens hole and the lens ring and holds the
    # lens ring by friction; the snug socket holds the base. Nothing
    # clamps along the axis (the user's decision: wall-mounted, the axis
    # horizontal). Inserted from the front, clocked to the lens's two
    # latch tabs, pressed home; lifted out with a fingernail under the
    # flange. One piece, prints FLANGE-DOWN with no supports.
    #
    #   flange  flat ring r pirBezelInnerR..pirBezelFlangeR (10.40..12.5),
    #           z 0..pirBezelFlangeT (1.5): sits on the face round the
    #           hole (0.85 of bearing outside the r 11.65 hole), 0.05
    #           clear of the dome's flank (r 10.35 just above the ring).
    #           Its TOP is continuous (user: no openings visible from
    #           above).
    #   skirt   two arcs r pirBezelInnerR..pirBezelSkirtRo (10.40..11.80,
    #           a 1.40 wall), z -pirBezelSkirtH..0 (-2.0..0): fill the
    #           r 11.65 hole with 0.15 a side of modelled overlap (the
    #           first ring, OD = the hole, printed 0.5 under on the
    #           diameter and was loose; 11.80 should print about 23.1 in
    #           the 23.2 hole: 91 expects the press-fit pair), 0.10 clear
    #           of the lens ring (r 10.3; the bore prints true, so it just
    #           grips the lens), foot flush with the top's underside.
    #   notches two, 180 deg apart, for the lens's latch tabs (5.0 wide,
    #           r to 11.0, case z 14.2..16, at 45/225 deg in the sensor
    #           frame): tangential width pirNotchW (= pirTabW + 1), cut
    #           through the skirt entirely, and continued into the
    #           flange's UNDERSIDE as blind relief pockets pirTabRelief
    #           (0.4) deep from the bore out to r BRIDGE_RI (11.45), so the
    #           tab (whose top is AT the face) has 0.4 under the flange
    #           and 1.1 of solid flange stays over it: nothing shows on
    #           top. Printed flange-down the pockets are two-layer
    #           recesses in the bed-side face. The notches are on the
    #           bezel's own +/-X; the occurrence is turned to the tabs'
    #           angle when parked.
    # 91_pir_fit.py tests the fitted state (no contact with the sensor or
    # the shell allowed); 05_export.py exports the component in its own
    # frame.
    for occ in list(root.occurrences):
        if occ.component.name.startswith("PirBezel"):
            occ.component.name = occ.component.name + "_deleted"
            occ.deleteMe()
    flangeR, flangeT = p02(des, "pirBezelFlangeR"), p02(des, "pirBezelFlangeT")
    innerR, skirtH = p02(des, "pirBezelInnerR"), p02(des, "pirBezelSkirtH")
    tabW, notchW = p02(des, "pirTabW"), p02(des, "pirNotchW")
    relief = p02(des, "pirTabRelief")
    skirtRo = p02(des, "pirBezelSkirtRo")        # 11.80: 0.15 over the hole, press fit after the print's shrink
    TAB_ANGLE = 45.0                             # deg, the sensor's tabs (STEP probe; 91 places it unrotated)
    TAB_R, RING_R, FLANK_R = 11.0 * MM, 10.3 * MM, 10.35 * MM    # STEP probes
    BRIDGE_RI = lensR - 0.02                     # tab pocket outer edge, 11.45: tab r 11.0 + 0.45 (tied to the hole, not the skirt)
    NOTCH_ANGLES = (0.0, 180.0)                  # bezel frame
    # --- guards ---
    if innerR < RING_R + 0.01 - 1e-9 or innerR < FLANK_R + 0.005 - 1e-9:
        raise RuntimeError("bezel inner r %.2f is under 0.10 off the lens ring (10.3) or 0.05 off "
                           "the dome flank (10.35)" % (innerR * 10))
    if skirtRo - innerR < 0.1:
        raise RuntimeError("bezel skirt wall %.2f is under 1.0 mm" % ((skirtRo - innerR) * 10))
    if not (lensR <= skirtRo <= lensR + 0.03 + 1e-9):
        raise RuntimeError("bezel skirt r %.2f is not 0..0.3 over the r %.2f hole (press fit by the print's "
                           "shrink)" % (skirtRo * 10, lensR * 10))
    if flangeR < lensR + 0.08:
        raise RuntimeError("bezel flange r %.1f bears under 0.8 on the face outside the r %.2f hole"
                           % (flangeR * 10, lensR * 10))
    if BRIDGE_RI < TAB_R + 0.03:
        raise RuntimeError("flange notch ends at r %.2f, under 0.3 past the tabs (r 11.0)" % (BRIDGE_RI * 10))
    if flangeR - BRIDGE_RI < 0.1:
        raise RuntimeError("flange bridge over the notches is %.2f wide, under 1.0" % ((flangeR - BRIDGE_RI) * 10))
    if relief < 0.02 or flangeT - relief < 0.1:
        raise RuntimeError("tab relief %.2f / flange %.2f: need >= 0.2 of relief and >= 1.0 of solid "
                           "flange over the pockets" % (relief * 10, flangeT * 10))
    if notchW < tabW + 0.1 - 1e-9:
        raise RuntimeError("bezel notch %.2f is under tab width %.2f + 1.0" % (notchW * 10, tabW * 10))
    if abs(skirtH - wall) > 0.05 + 1e-9:
        raise RuntimeError("bezel skirt height %.2f is not the top's thickness %.2f (+/-0.5)"
                           % (skirtH * 10, wall * 10))
    corner_r = math.hypot(BRIDGE_RI, notchW / 2)          # the flange notch's outer corners
    print("bezel ring: flange r %.2f..%.2f x %.2f (top continuous), skirt r %.2f..%.2f x %.1f "
          "(%.2f over the r %.2f hole: press fit), skirt notches %.1f wide; tab relief pockets "
          "%.2f deep in the flange's underside to r %.2f (%.2f of solid flange over them; outside "
          "the pockets %.2f on the centre line, %.2f at the corners); ring clearance %.2f, "
          "flank %.2f, tab radial %.2f"
          % (innerR * 10, flangeR * 10, flangeT * 10, innerR * 10, skirtRo * 10, skirtH * 10,
             (skirtRo - lensR) * 10, lensR * 10, notchW * 10, relief * 10, BRIDGE_RI * 10,
             (flangeT - relief) * 10, (flangeR - BRIDGE_RI) * 10, (flangeR - corner_r) * 10,
             (innerR - RING_R) * 10, (innerR - FLANK_R) * 10, (BRIDGE_RI - TAB_R) * 10))

    bz_occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    bz = bz_occ.component
    bz.name = "PirBezel"

    def annulus(r_in, r_out):
        sk = bz.sketches.add(bz.xYConstructionPlane)
        for r in (r_in, r_out):
            sk.sketchCurves.sketchCircles.addByCenterRadius(adsk.core.Point3D.create(0, 0, 0), r)
        ring = None
        for i in range(sk.profiles.count):
            if sk.profiles.item(i).profileLoops.count == 2:
                ring = sk.profiles.item(i)
        if ring is None:
            raise RuntimeError("no annular profile for r %.2f..%.2f" % (r_in * 10, r_out * 10))
        return ring

    # (a) flange, (b) skirt joined under it
    fe = extrude(bz, annulus(innerR, flangeR), 0.0, flangeT,
                 adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    bz_body = fe.bodies.item(0)
    extrude(bz, annulus(innerR, skirtRo), -skirtH, 0.0,
            adsk.fusion.FeatureOperations.JoinFeatureOperation, participants=[bz_body])
    if bz.bRepBodies.count != 1:
        raise RuntimeError("bezel skirt did not merge with the flange: %d bodies" % bz.bRepBodies.count)

    def notch_boxes(r_out):
        sk = bz.sketches.add(bz.xYConstructionPlane)
        lines = sk.sketchCurves.sketchLines
        for a in NOTCH_ANGLES:
            ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
            pts = []
            for rr, t in ((innerR - 0.05, -notchW / 2), (r_out, -notchW / 2),
                          (r_out, notchW / 2), (innerR - 0.05, notchW / 2)):
                pts.append(adsk.core.Point3D.create(rr * ca - t * sa, rr * sa + t * ca, 0))
            for i in range(4):
                lines.addByTwoPoints(pts[i], pts[(i + 1) % 4])
        profs = collection([sk.profiles.item(i) for i in range(sk.profiles.count)])
        if profs.count != 2:
            raise RuntimeError("expected 2 notch profiles, found %d" % profs.count)
        return profs

    # (c) notches: through the whole skirt wall (to past its OD), then
    # blind relief pockets in the flange's underside (to BRIDGE_RI, only
    # `relief` deep: the flange's top stays whole)
    extrude(bz, notch_boxes(skirtRo + 0.05), -skirtH - 0.01, 0.0,
            adsk.fusion.FeatureOperations.CutFeatureOperation, participants=[bz_body])
    extrude(bz, notch_boxes(BRIDGE_RI), -0.01, relief,
            adsk.fusion.FeatureOperations.CutFeatureOperation, participants=[bz_body])
    if bz.bRepBodies.count != 1:
        raise RuntimeError("bezel notches left %d bodies" % bz.bRepBodies.count)
    # (d) soften the two visible top edges (user request): a 0.5 mm 45 deg
    # chamfer on the flange's outer top edge (circle r flangeR at z
    # flangeT) and a 0.3 mm fillet on the inner top edge (circle r innerR
    # at z flangeT: a fillet keeps the ring's visible edge rounded without
    # widening the gap to the dome much). Both are full circles (the tab
    # pockets are blind, in the underside), selected by radius and z;
    # printed flange-down they are up-facing edges. The chamfer first, so
    # the fillet's selector (radius innerR exactly) cannot pick the
    # chamfer's new circles (r 12.0 at z 1.5, r 12.5 at z 1.0).
    EDGE_CHAM, EDGE_FIL = 0.05, 0.03
    def top_circle(radius, label):
        found = [e for e in bz_body.edges
                 if isinstance(e.geometry, adsk.core.Circle3D)
                 and abs(e.geometry.radius - radius) < 0.002
                 and abs(e.geometry.center.z - flangeT) < 0.002]
        if len(found) != 1:
            raise RuntimeError("expected 1 %s edge (circle r %.2f at z %.2f), found %d"
                               % (label, radius * 10, flangeT * 10, len(found)))
        return found[0]
    ch = bz.features.chamferFeatures
    chi = ch.createInput(collection([top_circle(flangeR, "flange outer top")]), False)
    chi.setToEqualDistance(adsk.core.ValueInput.createByReal(EDGE_CHAM))
    ch.add(chi)
    fil = bz.features.filletFeatures
    finp = fil.createInput()
    try:
        finp.edgeSetInputs.addConstantRadiusEdgeSet(
            collection([top_circle(innerR, "flange inner top")]),
            adsk.core.ValueInput.createByReal(EDGE_FIL), False)
    except AttributeError:  # older API shape
        finp.addConstantRadiusEdgeSet(
            collection([top_circle(innerR, "flange inner top")]),
            adsk.core.ValueInput.createByReal(EDGE_FIL), False)
    fil.add(finp)
    if bz.bRepBodies.count != 1:
        raise RuntimeError("bezel edge softening left %d bodies" % bz.bRepBodies.count)
    print("bezel top edges softened: %.1f mm chamfer on the outer edge (r %.1f), %.1f mm fillet "
          "on the inner edge (r %.2f)" % (EDGE_CHAM * 10, flangeR * 10, EDGE_FIL * 10, innerR * 10))
    # sanity on the built body, in its own frame
    IN = adsk.fusion.PointContainment.PointInsidePointContainment
    def bz_solid(r, ang, z):
        a = math.radians(ang)
        return bz_body.pointContainment(adsk.core.Point3D.create(r * math.cos(a), r * math.sin(a), z)) == IN
    rs = (innerR + skirtRo) / 2
    checks = ((True, (innerR + flangeR) / 2, 90, flangeT / 2, "flange"),
              (True, flangeR - 0.02, 90, flangeT / 2, "flange reaches its rim"),
              (False, flangeR + 0.02, 90, flangeT / 2, "nothing past the flange rim"),
              (False, innerR - 0.02, 90, flangeT / 2, "bore open through the flange"),
              (False, rs, 90, flangeT + 0.02, "nothing above the flange"),
              (True, rs, 90, -skirtH / 2, "skirt at 90"),
              (True, rs, 270, -skirtH / 2, "skirt at 270"),
              (True, rs, 90, -skirtH + 0.01, "skirt reaches its foot"),
              (False, rs, 90, -skirtH - 0.02, "nothing below the skirt's foot"),
              (False, skirtRo + 0.02, 90, -skirtH / 2, "nothing outside the skirt"),
              (False, innerR - 0.02, 90, -skirtH / 2, "bore open through the skirt"),
              (False, rs, 0, -skirtH / 2, "skirt notch at 0"),
              (False, rs, 180, -skirtH / 2, "skirt notch at 180"),
              (False, rs, 0, relief / 2, "tab relief pocket at 0 (r %.2f)" % (rs * 10)),
              (False, BRIDGE_RI - 0.02, 180, relief / 2, "relief pocket reaches r %.2f at 180" % ((BRIDGE_RI - 0.02) * 10)),
              (True, rs, 0, relief + 0.02, "flange solid 0.2 above the pocket at 0"),
              (True, rs, 180, flangeT - 0.02, "flange top continuous over the pocket at 180"),
              (True, rs, 90, relief / 2, "flange solid at 90 at the pocket's height"),
              (True, (BRIDGE_RI + flangeR) / 2, 0, relief / 2, "flange solid outside the pocket at 0"),
              (True, (BRIDGE_RI + flangeR) / 2, 180, relief / 2, "flange solid outside the pocket at 180"),
              (False, flangeR - 0.005, 90, flangeT - 0.005, "outer top edge chamfered (r 12.45, z 1.45 void)"),
              (True, flangeR - EDGE_CHAM, 90, flangeT - 0.005, "flange top solid inboard of the chamfer (r 12.0, z 1.45)"),
              (False, innerR + 0.005, 90, flangeT - 0.005, "inner top edge filleted (r 10.45, z 1.45 void)"),
              (True, innerR + 0.005, 90, flangeT - EDGE_FIL - 0.01, "flange solid under the fillet (r 10.45, z 1.1)"),
              (True, 1.09, 90, flangeT - 0.02, "flange top solid at r 10.9 (0.5 in from the inner edge, past the fillet)"))
    for want, r, ang, z, label in checks:
        if bz_solid(r, ang, z) != want:
            raise RuntimeError("bezel probe %s at (r %.2f, %.0f deg, z %.2f): expected %s"
                               % (label, r * 10, ang, z * 10, "solid" if want else "void"))
    # notch width, Cartesian at r_s on +X: open to +/-(notchW/2 - 0.3), solid at +/-(notchW/2 + 0.3)
    for t, want in ((notchW / 2 - 0.03, False), (notchW / 2 + 0.03, True)):
        for sgn in (1, -1):
            pt = adsk.core.Point3D.create(rs, sgn * t, -skirtH / 2)
            if (bz_body.pointContainment(pt) == IN) != want:
                raise RuntimeError("bezel notch width probe at t %+.2f: expected %s"
                                   % (sgn * t * 10, "solid" if want else "void"))
    # (d) park it in the case, turned to the tabs
    m = adsk.core.Matrix3D.create()
    m.setToRotation(math.radians(TAB_ANGLE), adsk.core.Vector3D.create(0, 0, 1),
                    adsk.core.Point3D.create(0, 0, 0))
    m.translation = adsk.core.Vector3D.create(pirCx, 0.0, z_top)
    bz_occ.transform2 = m
    if des.snapshots.hasPendingSnapshot:
        des.snapshots.add()
    print("pir bezel ok: one body, parked at (%.1f, 0, %.0f) turned %.0f deg (notches on the "
          "lens tabs at %.0f/%.0f)" % (pirCx * 10, z_top * 10, TAB_ANGLE, TAB_ANGLE, TAB_ANGLE + 180))
    print("PirBezel bodies:", bz.bRepBodies.count)
