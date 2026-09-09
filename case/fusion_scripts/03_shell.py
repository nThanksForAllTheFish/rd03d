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
        if occ.component.name.startswith("FrontShell"):
            # rename before deleting: the dead component keeps its name
            # reserved in the document's name registry (until save), which
            # would force the rebuilt component to "FrontShell (1)"
            occ.component.name = "FrontShell_deleted"
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

    # 4: usb notch through +X wall, back rim z=-backT up to z=8mm
    sk = comp.sketches.add(comp.xYConstructionPlane)
    rect(sk, intW / 2 + wall / 2, 0, wall + 0.02, 11.3 * MM)
    extrude(comp, sk.profiles.item(0), -backT, 8 * MM,
            adsk.fusion.FeatureOperations.CutFeatureOperation,
            participants=[shell_body])
    print("usb notch ok")

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

    # 6. soften exterior edges for hand comfort (change request 2026-09-07).
    # Operates on shell_body ONLY (fillet/chamfer features act on its edges,
    # so they are participant-safe by construction; BackPlate untouched).
    # Order matters: vertical corner fillets FIRST (they change the corner
    # topology the later perimeter selections rely on).
    corner = p(des, "cornerFillet")
    cham = p(des, "frontChamfer")
    soft = p(des, "softFillet")
    ox, oy = intW / 2 + wall, intH / 2 + wall   # outer half-extents (cm)
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

    # 6a. four outer vertical corner edges: lines parallel to Z with both
    # |x| and |y| at the outer values.
    verts = []
    for e in shell_body.edges:
        g = e.geometry
        if not isinstance(g, adsk.core.Line3D):
            continue
        d = line_dir(g)
        if abs(abs(d.z) - 1) > 1e-6:
            continue
        mx, my, _ = mid(g)
        if abs(abs(mx) - ox) < EPS and abs(abs(my) - oy) < EPS:
            verts.append(e)
    print("corner fillet edges found:", len(verts))
    if len(verts) != 4:
        raise RuntimeError("expected 4 vertical corner edges, found %d"
                           % len(verts))
    add_fillet(verts, corner)
    print("corner fillets ok (r=%.2f mm on 4 edges)" % (corner * 10))

    # Outer-perimeter edge selector at a z level: straight edges lying on the
    # outer faces (|x|=ox or |y|=oy) plus the corner-fillet arcs. The window
    # pocket is on the interior face and never touches the outer boundary.
    # At z_top the boundary is one clean closed loop (4 straights + 4 arcs
    # = 8 edges); at z_back the USB notch splits the +X segment (9 edges).
    def perimeter_edges(zlev):
        found = []
        for e in shell_body.edges:
            g = e.geometry
            if isinstance(g, adsk.core.Line3D):
                if (abs(g.startPoint.z - zlev) > EPS
                        or abs(g.endPoint.z - zlev) > EPS):
                    continue
                mx, my, _ = mid(g)
                if abs(abs(mx) - ox) < EPS or abs(abs(my) - oy) < EPS:
                    found.append(e)
            elif isinstance(g, (adsk.core.Arc3D, adsk.core.Circle3D)):
                c = g.center
                if (abs(c.z - zlev) < EPS
                        and abs(g.radius - corner) < EPS
                        and abs(abs(c.x) - (ox - corner)) < EPS
                        and abs(abs(c.y) - (oy - corner)) < EPS):
                    found.append(e)
        return found

    def add_chamfer(edges, dist):
        ch = comp.features.chamferFeatures
        chi = ch.createInput(collection(edges), False)
        chi.setToEqualDistance(adsk.core.ValueInput.createByReal(dist))
        return ch.add(chi)

    # 6b. front-face perimeter chamfer (prints clean bed-side). With the
    # window pocket on the interior face, the z=16 outer boundary is one
    # clean closed loop - 4 straights + 4 corner-fillet arcs = 8 edges -
    # chamfered as a single feature.
    front = perimeter_edges(z_top)
    print("front perimeter edges found:", len(front))
    if len(front) != 8:
        raise RuntimeError("expected 8 front perimeter edges, found %d"
                           % len(front))
    add_chamfer(front, cham)
    print("front chamfer ok (%.2f mm on 8 edges)" % (cham * 10))

    # 6c. back rim outer edge fillet.
    rim = perimeter_edges(z_back)
    print("back rim edges found:", len(rim))
    if not 8 <= len(rim) <= 10:
        raise RuntimeError("back rim edge count out of range: %d" % len(rim))
    add_fillet(rim, soft)
    print("rim fillet ok (r=%.2f mm on %d edges)" % (soft * 10, len(rim)))

    # 6d. USB-notch outer-edge soften: the two vertical edges where the notch
    # meets the outer +X face (x=ox, y=+/-5.65) and the notch's outer top
    # edge (x=ox, z=8, spanning y). Comfort feature - skip (and report) any
    # edge the kernel refuses rather than failing the build.
    usb_y = 11.3 / 2 * MM

    def usb_targets():
        vs, ts = [], []
        for e in shell_body.edges:
            g = e.geometry
            if not isinstance(g, adsk.core.Line3D):
                continue
            d = line_dir(g)
            mx, my, mz = mid(g)
            if abs(mx - ox) > EPS:
                continue
            if abs(abs(d.z) - 1) < 1e-6 and abs(abs(my) - usb_y) < EPS:
                vs.append(e)
            elif (abs(abs(d.y) - 1) < 1e-6 and abs(mz - 8 * MM) < EPS
                  and abs(my) < EPS):
                ts.append(e)
        return vs, ts

    vs, ts = usb_targets()
    total = len(vs) + len(ts)
    print("usb notch edges found: %d vertical + %d top" % (len(vs), len(ts)))
    done = 0
    try:
        add_fillet(vs + ts, soft)
        done = total
    except Exception as exc:
        print("usb group fillet refused (%s); retrying per-edge" % exc)
        failed = set()
        while True:  # re-scan after each success: topology changes
            vs, ts = usb_targets()
            nxt = None
            for e in vs + ts:
                key = tuple(round(v, 3) for v in mid(e.geometry))
                if key not in failed:
                    nxt = (e, key)
                    break
            if nxt is None:
                break
            try:
                add_fillet([nxt[0]], soft)
                done += 1
            except Exception as exc2:
                failed.add(nxt[1])
                print("USB EDGE SKIPPED at mm",
                      tuple(round(v * 10, 2) for v in nxt[1]), ":", exc2)
    print("usb notch soften: %d/%d edges filleted (r=%.2f mm)"
          % (done, total, soft * 10))

    print("FrontShell bodies:", comp.bRepBodies.count)
