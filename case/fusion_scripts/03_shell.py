import math

import adsk.core
import adsk.fusion


def p(des, name):
    return des.userParameters.itemByName(name).value  # cm


def ensure_params(des):
    """PIR pod parameters. Not in 01_setup.py: re-running that resets hand-tuned values."""
    spec = [
        # radii measured on Panasonic's STEP by point probing (2026-10-11):
        # base/can r 5.5 (not the 4.65 first assumed), neck r 5.3 -> 5.0,
        # flange r 9.3 with its underside at z 6.4..6.6, lens ring r 10.3,
        # and TWO lens latch tabs at 45/225 deg reaching r 11.1 over
        # z 6.6..8.4 whose hook lips (r 9.6..10.7) hang down to z 5.5.
        ("pirRecessR", "11.5 mm", "recess radius: latch tabs r 11.1 + 0.3 (lens ring is r 10.3)"),
        ("pirRecessD", "2.0 mm", "recess depth to the flange ledge (flange underside at sensor z 6.4..6.6)"),
        ("pirFlangeR", "9.3 mm", "flange radius: the sensor seats on the ledge r pirBoreR..pirFlangeR"),
        ("pirHookD", "3.3 mm", "groove depth outside the ledge for the latch hook lips (bottom at z 5.5 -> d 2.9)"),
        ("pirBoreR", "5.9 mm", "bore radius: base/can r 5.5 + 0.3; neck r 5.3..5.0 passes"),
        ("pirTilt", "18 deg", "bore tilt from the shell normal, toward +X"),
        ("pirTiltSign", "1", "+1: XIAO end hangs DOWN on the wall (confirmed 2026-10-11); -1: up"),
        ("pirPodWall", "2.0 mm", "pod wall around the recess"),
        ("pirWireDia", "3.0 mm", "wire pass-through into the XIAO bay"),
        # The horizontal hole meets the -X bore wall pirBoreR*tan(pirTilt)
        # = 5.9*tan18 = 1.9 mm deeper than its axis point. The opening is
        # centred on the pin tips (sensor z -5.5 = d 13.9), inside the plug
        # span d 9.3..15.3 where the plug's slot is: 13.9 - 1.9 = 12.0.
        ("pirWireD", "12.0 mm", "pass-through axis point depth: pin tips d 13.9 minus boreR*tan(tilt) 1.9"),
        ("pirPlugOD", "11.7 mm", "plug tube OD: nominal 0.05 clearance per side in the bore; the press fit relies on printed holes coming out undersize"),
        ("pirPlugID", "8.0 mm", "plug tube ID: pins on r2.5 plus room for three soldered joints"),
        ("pirPlugL", "6.0 mm", "plug tube length"),
        ("pirSeatD", "9.3 mm", "plug front rim depth: the base's underside (sensor z -0.9); read by 03_shell.py and 91_pir_fit.py"),
        ("pirPlugSlotW", "3.2 mm", "lengthwise slot through one plug wall: wire exit into the pass-through, and a little compliance for the press fit"),
    ]
    ups = des.userParameters
    for name, expr, comment in spec:
        if ups.itemByName(name) is None:
            unit = "deg" if "deg" in expr else ("" if expr.lstrip("-").isdigit() else "mm")
            ups.add(name, adsk.core.ValueInput.createByString(expr), unit, comment)
            print("added", name, "=", expr)


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
    ensure_params(des)

    for occ in list(root.occurrences):
        name = occ.component.name
        if name.startswith(("FrontShell", "PirPlug")):
            # rename before deleting: the dead component keeps its name
            # reserved in the document's name registry (until save), which
            # would force the rebuilt component to "FrontShell (1)"
            occ.component.name = name + "_deleted"
            occ.deleteMe()
            print("removed existing", name)
        elif name.startswith(("EKMC", "PaPIRs")):
            # the PIR sensor placed by 91_pir_fit.py; it is re-imported
            # against the rebuilt shell by re-running that script
            occ.deleteMe()
            print("removed prior sensor import:", name)

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

    # 6. PIR POD BLOCK (2026-10-11; moved ahead of the edge finishing on
    # 2026-10-24): a block on the outer +X wall, full shell depth so its
    # front face prints on the bed with the shell. It is joined BEFORE the
    # corner fillets, front chamfer and rim fillet so those run around the
    # pod instead of stopping dead at its footprint (the pod used to be
    # added last, with sharp edges, and swallowed the finishing over its
    # footprint). The pod sits on the flat part of the +X face (|y| <=
    # podL/2 = 13.5, the shell's corner fillets start at |y| = 22.5). The
    # recess, bore, wire hole and plug are cut in step 8.
    recessR, recessD = p(des, "pirRecessR"), p(des, "pirRecessD")
    boreR, podWall = p(des, "pirBoreR"), p(des, "pirPodWall")
    flangeR, hookD = p(des, "pirFlangeR"), p(des, "pirHookD")
    # Fusion hands angle parameters back in radians (18 deg -> 0.314); the
    # guard also accepts a value typed in degrees.
    tilt = p(des, "pirTilt") if p(des, "pirTilt") < 1.6 else math.radians(p(des, "pirTilt"))
    sgn = 1.0 if p(des, "pirTiltSign") >= 0 else -1.0
    xOuter = intW / 2 + wall                     # +X outer face of the shell
    zTop, zBack = intD + wall, -backT
    depth = zTop - zBack
    podW = 2 * (recessR + podWall) + depth * math.tan(tilt)
    podL = 2 * (recessR + podWall)
    podCx = xOuter + podW / 2

    sk = comp.sketches.add(comp.xYConstructionPlane)
    rect(sk, podCx, 0, podW, podL)
    extrude(comp, sk.profiles.item(0), zBack, zTop,
            adsk.fusion.FeatureOperations.JoinFeatureOperation,
            participants=[shell_body])
    if comp.bRepBodies.count != 1:
        raise RuntimeError("pir pod did not merge with the shell: %d bodies"
                           % comp.bRepBodies.count)
    print("pir pod block ok (%.1f x %.1f mm at x=%.1f)" % (podW * 10, podL * 10, podCx * 10))

    # 7. soften exterior edges for hand comfort (change request 2026-09-07).
    # Operates on shell_body ONLY (fillet/chamfer features act on its edges,
    # so they are participant-safe by construction; BackPlate untouched).
    # Order matters: vertical corner fillets FIRST (they change the corner
    # topology the later perimeter selections rely on).
    # Since 2026-10-24 the outline includes the PIR pod: in plan it is the
    # shell rectangle with the pod rectangle standing off the +X face, so
    # there are 8 vertical edges (4 shell corners, 2 pod corners, 2 concave
    # junctions) and each z-level perimeter loop is 8 straights + 8 arcs.
    corner = p(des, "cornerFillet")
    cham = p(des, "frontChamfer")
    soft = p(des, "softFillet")
    ox, oy = intW / 2 + wall, intH / 2 + wall   # outer half-extents (cm)
    px, py = ox + podW, podL / 2                # pod outer face x, pod half-length
    z_top, z_back = intD + wall, -backT
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

    def near(a, b):
        return abs(a - b) < EPS

    # 7a. vertical edges: lines parallel to Z at the outline's corners.
    # Convex: shell (|x|=ox, |y|=oy) and pod (x=px, |y|=py). Concave: the
    # pod-to-wall junctions (x=ox, |y|=py). All get the same radius; the
    # concave pair is what blends the pod into the wall.
    def vertical_corner(mx, my):
        return ((near(abs(mx), ox) and near(abs(my), oy))
                or (near(mx, px) and near(abs(my), py))
                or (near(mx, ox) and near(abs(my), py)))

    verts = []
    for e in shell_body.edges:
        g = e.geometry
        if not isinstance(g, adsk.core.Line3D):
            continue
        d = line_dir(g)
        if abs(abs(d.z) - 1) > 1e-6:
            continue
        mx, my, _ = mid(g)
        if vertical_corner(mx, my):
            verts.append(e)
    print("corner fillet edges found:", len(verts))
    if len(verts) != 8:
        raise RuntimeError("expected 8 vertical corner edges (4 shell, 2 pod, "
                           "2 junction), found %d" % len(verts))
    add_fillet(verts, corner)
    print("corner fillets ok (r=%.2f mm on 8 edges)" % (corner * 10))

    # Outer-perimeter edge selector at a z level: straight edges lying on the
    # outer faces (shell |x|=ox or |y|=oy; pod x=px, or |y|=py beyond the
    # shell face) plus the corner-fillet arcs, whose centres sit at
    # (+-(ox-r), +-(oy-r)) for the shell corners, (px-r, +-(py-r)) for the
    # pod corners and (ox+r, +-(py+r)) for the concave junctions. The window
    # pocket is on the interior face and never touches the outer boundary.
    # At both z_top and z_back the boundary is one closed loop of 16 edges.
    arc_centres = [(sx * (ox - corner), sy * (oy - corner)) for sx in (1, -1) for sy in (1, -1)]
    arc_centres += [(px - corner, sy * (py - corner)) for sy in (1, -1)]
    arc_centres += [(ox + corner, sy * (py + corner)) for sy in (1, -1)]

    def perimeter_edges(zlev):
        found = []
        for e in shell_body.edges:
            g = e.geometry
            if isinstance(g, adsk.core.Line3D):
                if (abs(g.startPoint.z - zlev) > EPS
                        or abs(g.endPoint.z - zlev) > EPS):
                    continue
                mx, my, _ = mid(g)
                if (near(abs(mx), ox) or near(abs(my), oy) or near(mx, px)
                        or (near(abs(my), py) and mx > ox + EPS)):
                    found.append(e)
            elif isinstance(g, (adsk.core.Arc3D, adsk.core.Circle3D)):
                c = g.center
                if (abs(c.z - zlev) < EPS and near(g.radius, corner)
                        and any(near(c.x, cx) and near(c.y, cy) for cx, cy in arc_centres)):
                    found.append(e)
        return found

    def add_chamfer(edges, dist):
        ch = comp.features.chamferFeatures
        chi = ch.createInput(collection(edges), False)
        chi.setToEqualDistance(adsk.core.ValueInput.createByReal(dist))
        return ch.add(chi)

    # 7b. front-face perimeter chamfer (prints clean bed-side). The pod's
    # front face is coplanar with the shell's, so the loop runs around it:
    # 8 straights + 8 corner-fillet arcs, chamfered as a single feature.
    # On the pod's +-Y sides the chamfer takes 1 mm off a 2 mm wall at the
    # very front edge only; the recess behind it is a pocket for the lens
    # ring, not a load path.
    front = perimeter_edges(z_top)
    print("front perimeter edges found:", len(front))
    if len(front) != 16:
        raise RuntimeError("expected 16 front perimeter edges, found %d"
                           % len(front))
    add_chamfer(front, cham)
    print("front chamfer ok (%.2f mm on 16 edges)" % (cham * 10))

    # 7c. back rim outer edge fillet, same loop at z_back.
    rim = perimeter_edges(z_back)
    print("back rim edges found:", len(rim))
    if len(rim) != 16:
        raise RuntimeError("back rim should be 16 edges with the pod, "
                           "found %d" % len(rim))
    add_fillet(rim, soft)
    print("rim fillet ok (r=%.2f mm on %d edges)" % (soft * 10, len(rim)))


    # 8. PIR POD cuts (2026-10-11): the block itself is joined in step 6,
    # before the edge finishing, so the fillets and chamfer run around it.
    # The EKMC1603111's lens (dia 20.6, 11 mm tall) is wider than its neck,
    # so the sensor enters from the FRONT: lens ring + flange in a 2 mm
    # recess, the flange seated on a ledge with an annular groove outside it
    # for the lens's two latch hooks (so the sensor can go in at any
    # rotation), neck and base through a bore, a plug tube pressed in from
    # the back holds it. The bore tilts pirTilt toward +X so the PIR looks
    # 18 deg down with the case hanging XIAO-end-down.
    # PRINTING (review 2026-10-11): the recess opens onto the bed, so its
    # floor (the flange ledge and the groove floor) is an unsupported
    # overhang in the face-down orientation. Accepted: the shell now needs
    # supports INSIDE THE PIR RECESS ONLY (paint-on or tree supports in the
    # dia 23 pocket; the surface they touch is hidden under the sensor's
    # flange). Everything else prints as before, without supports.

    # bore axis through the pod centre at the front face, direction
    # (sgn*sin t, 0, cos t); along(d) is the axis point d into the pod.
    ax = adsk.core.Vector3D.create(sgn * math.sin(tilt), 0.0, math.cos(tilt))
    front_pt = adsk.core.Point3D.create(podCx, 0.0, zTop)

    def along(d):
        return adsk.core.Point3D.create(front_pt.x - ax.x * d, 0.0, front_pt.z - ax.z * d)

    # read every parameter BEFORE startEdit(): inside a base feature the
    # design is in direct-modelling mode and userParameters raises
    # "this is not a parametric design".
    wireR, wp = p(des, "pirWireDia") / 2, along(p(des, "pirWireD"))
    tbm = adsk.fusion.TemporaryBRepManager.get()
    base = comp.features.baseFeatures.add()
    base.startEdit()
    # The recess is a TILTED cylinder, so its +X rim exits the flat front
    # face recessR*tan(tilt) (~3.7 mm) further out along the axis than its
    # -X rim does. Starting the cut only 0.5 mm outside the face left a
    # crescent of pod under the dome's +X flank (180 mm^3 of interference
    # with the real sensor, 2026-10-11). Start it where the cylinder has
    # cleared the face plane entirely; beyond that it cuts only air.
    recess_out = recessR * math.tan(tilt) + 0.1
    recess_cyl = tbm.createCylinderOrCone(along(-recess_out), recessR, along(recessD), recessR)
    # latch-hook groove: the recess floor stays at recessD only over the
    # flange ledge (r boreR..flangeR); outside it the floor drops to hookD
    groove = tbm.createCylinderOrCone(along(recessD - 0.01), recessR, along(hookD), recessR)
    ledge = tbm.createCylinderOrCone(along(recessD - 0.02), flangeR, along(hookD + 0.01), flangeR)
    tbm.booleanOperation(groove, ledge, adsk.fusion.BooleanTypes.DifferenceBooleanType)
    bore_cyl = tbm.createCylinderOrCone(along(recessD - 0.01), boreR,
                                        along(depth / math.cos(tilt) + 0.3), boreR)
    wire_cyl = tbm.createCylinderOrCone(
        adsk.core.Point3D.create(wp.x, 0.0, wp.z), wireR,
        adsk.core.Point3D.create(intW / 2 - 0.015, 0.0, wp.z), wireR)
    for b in (recess_cyl, groove, bore_cyl, wire_cyl):
        comp.bRepBodies.add(b, base)
    base.finishEdit()
    # the proxies returned by bRepBodies.add() go stale when the edit
    # closes (Combine fails with ALL_TOOL_BODY_REFERENCE_LOST); use the
    # base feature's own body list instead
    tools = [base.bodies.item(i) for i in range(base.bodies.count)]
    if len(tools) != 4:
        raise RuntimeError("expected 4 pir tool bodies, found %d" % len(tools))
    ci = comp.features.combineFeatures.createInput(shell_body, collection(tools))
    ci.operation = adsk.fusion.FeatureOperations.CutFeatureOperation
    ci.isKeepToolBodies = False
    comp.features.combineFeatures.add(ci)
    if comp.bRepBodies.count != 1:
        raise RuntimeError("pir bore split the shell: %d bodies" % comp.bRepBodies.count)
    print("pir recess r=%.2f d=%.2f (ledge r %.2f..%.2f, hook groove to d %.2f), "
          "bore r=%.2f, tilt %.1f deg ok"
          % (recessR * 10, recessD * 10, boreR * 10, flangeR * 10, hookD * 10,
             boreR * 10, math.degrees(tilt)))

    # 8b. PLUG: tube pressed into the bore from the back; its front rim bears
    # on the base's underside (r up to 5.5, pins inside r 2.5). Separate component,
    # exported as its own STL, printed standing on either end.
    plug_occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    plug = plug_occ.component
    plug.name = "PirPlug"
    sk = plug.sketches.add(plug.xYConstructionPlane)
    sk.sketchCurves.sketchCircles.addByCenterRadius(adsk.core.Point3D.create(0, 0, 0), p(des, "pirPlugOD") / 2)
    sk.sketchCurves.sketchCircles.addByCenterRadius(adsk.core.Point3D.create(0, 0, 0), p(des, "pirPlugID") / 2)
    ring = None
    for i in range(sk.profiles.count):            # the annular profile, not the inner disc
        pr = sk.profiles.item(i)
        if ring is None or pr.areaProperties().area > ring.areaProperties().area:
            ring = pr
    plugL = p(des, "pirPlugL")
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
    # bore (deeper = -Z of the shell), local z=0 (the front rim) at d 9.3,
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

    print("FrontShell bodies:", comp.bRepBodies.count)
