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

    # 3: radar window pocket on the INTERIOR front face over the patch end
    # (design review 2026-09-07: flipped from the exterior so the outside
    # stays perfectly smooth). Cut z from intD up (wall - windowT); the
    # remaining window panel is windowT thick at z intD+(wall-winT)..intD+wall.
    # rect x in [rCx-9.5mm, rCx+9.5mm], y in [1mm, 23mm] - the +Y extent is
    # clamped to the cavity edge intH/2 (the exterior pocket ran to 25/the
    # outer face; on the interior, cutting past 23 would tunnel through the
    # solid top wall and open a slot on the outer +Y face).
    sk = comp.sketches.add(comp.xYConstructionPlane)
    rect(sk, rCx, 12 * MM, 19 * MM, 22 * MM)
    extrude(comp, sk.profiles.item(0), intD, intD + (wall - winT),
            adsk.fusion.FeatureOperations.CutFeatureOperation,
            participants=[shell_body])
    print("window pocket (interior) ok")

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
