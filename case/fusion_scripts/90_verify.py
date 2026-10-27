"""Read-only geometric assertions over the rd-03d_case document.

Run with:  python3 run_fusion.py script 90_verify.py --read-only

Every check is a point-containment probe in MILLIMETRES. `solid(...)` asserts
the point is inside material; `void(...)` asserts it is not. Failures are
collected and raised together so one run reports every problem.
"""
import adsk.core
import adsk.fusion

MM = 0.1
FAILURES = []


def find(root, prefix):
    """The single body of the component whose name starts with `prefix`.

    A rebuilt component keeps a cosmetic "(1)" suffix until the document is
    saved, so match on prefix rather than equality.
    """
    for occ in root.occurrences:
        if occ.component.name.startswith(prefix):
            comp = occ.component
            if comp.bRepBodies.count != 1:
                raise RuntimeError("%s has %d bodies, expected 1"
                                   % (comp.name, comp.bRepBodies.count))
            return comp.bRepBodies.item(0)
    raise RuntimeError("no component starting with " + prefix)


def _inside(body, x, y, z):
    pt = adsk.core.Point3D.create(x * MM, y * MM, z * MM)
    pc = body.pointContainment(pt)
    return pc == adsk.fusion.PointContainment.PointInsidePointContainment


def solid(body, x, y, z, why):
    if not _inside(body, x, y, z):
        FAILURES.append("EXPECTED SOLID at (%.2f, %.2f, %.2f): %s"
                        % (x, y, z, why))


def void(body, x, y, z, why):
    if _inside(body, x, y, z):
        FAILURES.append("EXPECTED VOID at (%.2f, %.2f, %.2f): %s"
                        % (x, y, z, why))


def radar_walls(des):
    """The radar fence walls' faces (mm) as 02 step 4 builds them: inner
    faces at radarCx +/- (radarW/2 + radarClear), 1.5 thick outside."""
    def pv(n): return des.userParameters.itemByName(n).value * 10
    rCx, half = pv("radarCx"), pv("radarW") / 2 + pv("radarClear")
    return rCx - half - 1.5, rCx - half, rCx + half, rCx + half + 1.5, rCx


def check_baseline(plate, shell, des):
    """Geometry that predates this plan and must survive every change."""
    wo, wi, ei, eo, rCx = radar_walls(des)
    solid(plate, 0, 0, -4, "plate core")
    void(plate, 0.95, -12, -4, "LEGO through-bore at x0.95 y-12")
    void(plate, rCx, -12.0, 1.0, "no crossbar A: the bay floor is open at y -12")
    void(plate, rCx, 18.75, 1.0, "no crossbar B: the bay floor is open at y 18.75")
    void(plate, rCx, 0, 1.0, "radar bay is open between the end bars")
    solid(plate, (wo + wi) / 2, 0, 6.0, "radar clip A wall at x %.2f..%.2f" % (wo, wi))
    solid(plate, 8.0, -9.9, 2.0, "XIAO -Y fence wall")
    solid(plate, 8.0, 9.9, 2.0, "XIAO +Y fence wall")
    void(plate, 8.0, -9.9, 6.5, "above the XIAO clip top (5.6)")
    solid(shell, 0, 0, 15.0, "shell front wall above the 14 mm ceiling")
    void(shell, 0, 0, 7.0, "shell interior cavity")


def check_fit_allowances(plate, shell, des):
    """Measured fit allowances (02 ensure_params, 2026-10-25 calipers):
    plate half-width intW/2 - rimGapX (20.97), half-length intH/2 -
    rimGapY (23.05: 0.05 INTO the shell's +/-Y walls in the model, which
    the print's Y shrink, 0.15 a side, takes back to a 0.1 gap a side
    against the 46.00 cavity of the reprint; was -0.20 after the first
    print), wing half-width pirBoxHalfY - wingGap (13.62, 0.12 into the
    box walls). Probes: the plate is solid just inside each
    modelled edge and void just outside; the shell's walls are where they
    always were (so the overlap is the plate's, by design)."""
    def pv(n): return des.userParameters.itemByName(n).value * 10
    intW, intH, hy = pv("intW"), pv("intH"), pv("pirBoxHalfY")
    gx, gy, gw = pv("rimGapX"), pv("rimGapY"), pv("wingGap")
    cx = pv("pirCx")
    ex, ey, wy = intW / 2 - gx, intH / 2 - gy, hy - gw
    for sx in (1, -1):
        # (probed at y 20: the wing is fused to the +X edge over |y| < 15.62)
        solid(plate, sx * (ex - 0.05), 20.0, -4.0, "plate solid 0.05 inside its %sX edge (x %.2f)" % ("+" if sx > 0 else "-", sx * ex))
        void(plate, sx * (ex + 0.05), 20.0, -4.0, "nothing 0.05 past the plate's %sX edge (outside the wing)" % ("+" if sx > 0 else "-"))
    for sy in (1, -1):
        solid(plate, 0.0, sy * (ey - 0.05), -4.0, "plate solid 0.05 inside its %sY edge (y %.2f)" % ("+" if sy > 0 else "-", sy * ey))
        void(plate, 0.0, sy * (ey + 0.05), -4.0, "nothing 0.05 past the plate's %sY edge" % ("+" if sy > 0 else "-"))
        solid(shell, 0.0, sy * (intH / 2 + 0.05), -4.0, "shell %sY wall still starts at y %.1f (the overlap is the plate's)" % ("+" if sy > 0 else "-", sy * intH / 2))
        solid(plate, cx, sy * (wy - 0.05), -5.0, "wing solid 0.05 inside its %sY face (y %.2f)" % ("+" if sy > 0 else "-", sy * wy))
        void(plate, cx, sy * (wy + 0.05), -5.0, "nothing 0.05 past the wing's %sY face" % ("+" if sy > 0 else "-"))
        solid(shell, cx, sy * (hy + 0.05), -5.0, "box %sY wall still starts at y %.1f" % ("+" if sy > 0 else "-", sy * hy))
    if not (gy < 0 and gw < 0 and gx >= 0):
        FAILURES.append("fit allowances changed sign (rimGapX %.2f, rimGapY %.2f, wingGap %.2f): "
                        "re-derive the probes and 91's expected overlap" % (gx, gy, gw))
    # reprint 2026-10-26: plate Y prints 0.30 under (0.15 a side), the
    # cavity 46.00 (true) on this shell; the printed edge must stay
    # >= 0.05 a side inside the printed cavity wall
    if not (ey - 0.15 <= intH / 2 - 0.05 + 1e-9):
        FAILURES.append("printed plate edge (%.3f) is under 0.05 inside the printed cavity wall (%.2f)"
                        % (ey - 0.15, intH / 2))


def check_snaps(plate, shell, des):
    """Snap pairs since Task 9d (2026-10-25): the -X pair at y +/-12 as
    always (bumps 6 long, 0.5 proud of the inner wall, z -1.6..-0.4;
    pockets 6.2 long, 0.6 into the plate edge (x -20.97..-20.37 with the
    measured rimGapX; the bump tip at -20.5 clears the floor by 0.13),
    z -1.7..-0.3, blind both ends), and the lid's +X end snapped into the WING: bumps on the pod
    box's inner +/-Y walls (y +/-pirBoxHalfY, 0.5 proud, x wingSnapX +/-3,
    z wingSnapZ +/-0.5) into blind pockets in the wing's +/-Y faces
    (y +/-(pirBoxHalfY - wingGap), snapBump + 0.1 - wingGap = 0.72 deep,
    +/-3.1 long, +/-0.6 tall).
    The old +X pair at y +/-snapYpx (19) on the shell's +X wall stubs and
    the plate's +X edge is gone: those places are plain wall and plain
    edge now."""
    def pv(n): return des.userParameters.itemByName(n).value * 10
    hy, wingGap = pv("pirBoxHalfY"), pv("wingGap")
    sx, sz, bump = pv("wingSnapX"), pv("wingSnapZ"), pv("snapBump")
    wy = hy - wingGap                                            # 15.62 (wingGap is negative)
    pd = bump + 0.1 + max(-wingGap, 0.0)                         # pocket depth, as 02 derives it (0.72)
    for sy in (-1, 1):
        # -X side unchanged at +/-12
        solid(shell, -20.75, sy * 12, -1.0, "-X bump at y %+.0f" % (sy * 12))
        void(shell, -20.75, sy * 19, -1.0, "no -X bump at y %+.0f" % (sy * 19))
        void(plate, -20.6, sy * 12, -1.0, "-X pocket at y %+.0f" % (sy * 12))
        solid(plate, -20.6, sy * 19, -1.0, "no -X pocket at y %+.0f" % (sy * 19))
        # RETIRED 9d: the +X pair at y +/-19. The shell's +X wall stub
        # (|y| 17.5..23) is plain and the plate's +X edge is plain.
        void(shell, 20.75, sy * 19, -1.0, "no +X bump at y %+.0f (retired with snapYpx)" % (sy * 19))
        solid(shell, 22.0, sy * 19, -1.0, "+X wall stub solid at y %+.0f" % (sy * 19))
        solid(plate, 20.6, sy * 19, -1.0, "no +X pocket at y %+.0f (retired with snapYpx)" % (sy * 19))
        void(shell, 20.75, sy * 12, -1.0, "no +X bump at y %+.0f (box cavity)" % (sy * 12))
        # wing pair: bump on the box's inner +/-Y wall
        tag = "+Y" if sy > 0 else "-Y"
        solid(shell, sx, sy * (hy - bump / 2), sz, "wing bump on the box's %s wall" % tag)
        solid(shell, sx + 2.5, sy * (hy - bump / 2), sz, "wing bump reaches x %.1f, %s" % (sx + 2.5, tag))
        solid(shell, sx - 2.5, sy * (hy - bump / 2), sz, "wing bump reaches x %.1f, %s" % (sx - 2.5, tag))
        void(shell, sx + 3.5, sy * (hy - bump / 2), sz, "wing bump ends before x %.1f, %s" % (sx + 3.5, tag))
        void(shell, sx - 3.5, sy * (hy - bump / 2), sz, "wing bump starts after x %.1f, %s" % (sx - 3.5, tag))
        void(shell, sx, sy * (hy - bump - 0.25), sz, "wing bump is only %.1f proud, %s" % (bump, tag))
        void(shell, sx, sy * (hy - bump / 2), sz + 1.0, "wing bump spans z +/-0.5 only (above), %s" % tag)
        void(shell, sx, sy * (hy - bump / 2), sz - 1.0, "wing bump spans z +/-0.5 only (below), %s" % tag)
        solid(shell, sx, sy * (hy + 1.0), sz, "box wall solid behind the wing bump, %s" % tag)
        # wing pair: pocket in the wing's +/-Y face
        void(plate, sx, sy * (wy - 0.3), sz, "wing pocket in the %s face" % tag)
        void(plate, sx + 2.9, sy * (wy - 0.3), sz, "wing pocket reaches x %.1f, %s" % (sx + 2.9, tag))
        void(plate, sx - 2.9, sy * (wy - 0.3), sz, "wing pocket reaches x %.1f, %s" % (sx - 2.9, tag))
        solid(plate, sx + 3.5, sy * (wy - 0.3), sz, "wing face solid past the pocket (+X), %s" % tag)
        solid(plate, sx - 3.5, sy * (wy - 0.3), sz, "wing face solid past the pocket (-X), %s" % tag)
        void(plate, sx, sy * (wy - pd + 0.05), sz, "wing pocket open to its floor (%.2f deep), %s" % (pd, tag))
        solid(plate, sx, sy * (wy - pd - 0.1), sz, "wing solid 0.1 behind the pocket floor, %s" % tag)
        solid(plate, sx, sy * (wy - 0.3), sz + 0.9, "wing solid above the pocket (blind), %s" % tag)
        solid(plate, sx, sy * (wy - 0.3), sz - 0.9, "wing solid below the pocket (blind), %s" % tag)
        # the bump's tip (y hy - 0.5 = 15.0) must clear the pocket floor
        # (wy - pd = 14.9) by 0.1 and lie inside the wing's face line
        # (15.62: with the measured negative wingGap the wing is 0.12 into
        # the box wall in the model; printed, the face shrinks to 15.5 and
        # the cavity grows to 15.6, so the bump overlaps the face line by
        # about 0.4 and the floor stays clear)
        if not (hy - bump >= wy - pd + 0.1 - 1e-9):
            FAILURES.append("wing bump tip (y %.2f) is under 0.1 off the pocket floor (y %.2f)"
                            % (hy - bump, wy - pd))
        if not (hy - bump < wy - 1e-9):
            FAILURES.append("wing bump tip (y %.2f) does not reach inside the wing's face (y %.2f)"
                            % (hy - bump, wy))


def check_xiao_clips(plate):
    """Lips on a CONTINUOUS 1.5 mm fence wall: no slots, no trenches.

    Retargeted 2026-09-10. The user printed the slotted-and-trenched design
    and reported the clips "very wimpy - barely holding it in", then asked
    for the slots and trenches to go. So the probes that used to assert an
    isolated blade rooted at z = -1.5 now assert the opposite: that region
    is plain solid plate again, above the floor as well as below it. The
    lip geometry (0.60 mm projection, underside at 4.30, 0.34 mm grab) is
    unchanged and its probes are unchanged with it.
    """
    for sy in (-1, 1):
        tag = "+Y" if sy > 0 else "-Y"
        # WAS the two clip trenches (1.2 mm wide, z -1.5..0, either side of
        # the finger). Deleted: with no slots the wall is not a cantilever,
        # so there is no root to lengthen. Now solid floor.
        solid(plate, 8.0, sy * 8.55, -0.75, "no inboard clip trench " + tag)
        solid(plate, 8.0, sy * 11.25, -0.75, "no outboard clip trench " + tag)
        # the wall's footprint in the plate, which never was cut
        solid(plate, 8.0, sy * 9.9, -0.75, "plate under the clip wall " + tag)
        solid(plate, 8.0, sy * 9.9, -2.0, "plate under the clip wall " + tag)
        # WAS the isolating slots, cut z -1.5..6.6 at x 3.8..4.5 and
        # 11.5..12.2. Below the floor they are gone...
        solid(plate, 4.0, sy * 9.9, -0.75, "no clip slot below floor " + tag)
        solid(plate, 12.0, sy * 9.9, -0.75, "no clip slot below floor " + tag)
        # ...and, the point that actually matters, gone ABOVE the floor too,
        # where the fence wall is. A below-floor-only check would pass on a
        # wall still sliced through at full height. x 4.1 and 11.85 are
        # inside the old 0.7 mm slot bands; z 2.0 is mid-wall.
        solid(plate, 4.1, sy * 9.9, 2.0, "wall continuous at old slot " + tag)
        solid(plate, 11.85, sy * 9.9, 2.0, "wall continuous at old slot " + tag)
        # finger is full 1.5 mm: the old 0.5 mm outer shave is gone
        solid(plate, 8.0, sy * 10.4, 3.0, "finger at full thickness " + tag)
        # lip material spans lip_z(4.30)..top_z(5.60); z=4.30 is the board
        # top + 0.10 float, so probe just inside the lip, not in the gap
        solid(plate, 8.0, sy * 8.7, 4.40, "clip lip " + tag)
        # plate floor is solid either side of the clip in x as well
        solid(plate, 2.0, sy * 8.55, -0.75, "plate solid beyond clip " + tag)
        solid(plate, 14.0, sy * 8.55, -0.75, "plate solid beyond clip " + tag)


def check_no_interior_counterbores(plate):
    """Interior face is flat: only the 4.9 mm bores break it."""
    for cx, cy in ((0.95, -12), (0.95, -4), (0.95, 4), (0.95, 12),
                   (8.95, -4), (8.95, 4)):
        # 2.8 mm out from the bore centre: inside the old 3.2 mm
        # counterbore radius, outside the 2.45 mm through-bore
        solid(plate, cx, cy + 2.8, -0.45,
              "interior counterbore removed at (%.2f, %.2f)" % (cx, cy))
        # the rear counterbore is unchanged
        void(plate, cx, cy + 2.8, -7.55,
             "rear counterbore kept at (%.2f, %.2f)" % (cx, cy))
        # the through-bore is unchanged
        void(plate, cx, cy, -4.0, "through-bore at (%.2f, %.2f)" % (cx, cy))


def check_lego_bores_clear(plate):
    """Nothing printed on the interior floor may roof a Technic bore.

    Added 2026-09-09 after the capacitor cradle's x=3.0 rib was found
    sitting over the (0.95, +/-12) bore: the rib footprint x 2.40..3.60
    overlapped the 2.45 mm bore (which reaches x 3.40) by 1.00 mm over
    3.20 mm of y, capping ~11% of the bore's interior mouth for the rib's
    full 8 mm height. A pin pushed in from the back would bottom out on it.

    Why these three points per bore and not one: the CENTRE probe alone
    would NOT have caught that rib, which straddled only the bore's +x
    flank. The +/-1.5 mm offsets are what make the check bite - x = 2.45 on
    the (0.95, +12) bore is precisely where the old rib was. The centre
    probe stays because it catches the other failure shape (a feature
    landing squarely on a bore), and it costs one line.

    z = 0.5 is half a millimetre above the interior floor: every floor-borne
    feature in this design (ribs, fences, posts, collar) starts at z = 0, so
    anything overhanging a bore registers here.

    REMOVED 2026-09-10: a pair of probes at (3.3, +/-10.5, -0.75) that
    guarded the 0.70 mm web between the XIAO clip's inboard slot and the
    (0.95, +/-12) bore. The slots are gone (02_backplate step 8b), so there
    is no web and no hazard - but that also means those probes had become
    trivially true, asserting solid plate in the middle of solid plate.
    They are deleted rather than kept, so nobody reads a green run as
    evidence that the web hazard was re-checked. It cannot recur unless a
    clip feature is taken below z = 0 again; if one ever is, its clearance
    to these bores must be worked out afresh, not inherited.
    """
    for cx, cy in ((0.95, -12), (0.95, -4), (0.95, 4), (0.95, 12),
                   (8.95, -4), (8.95, 4)):
        for dx in (-1.5, 0.0, 1.5):
            void(plate, cx + dx, cy, 0.5,
                 "Technic bore (%.2f, %+.0f) unroofed at dx=%+.1f"
                 % (cx, cy, dx))
    # The two WING holes (2026-10-25 evening, 02_backplate step 14d) at
    # (24.95, +/-4) go THROUGH the 6 mm wing (z -8..-2) and open into the
    # shell's pod box cavity, which is empty there (a pin stands 2 mm
    # proud). Open and counterbored at the back, open at the wing top, wing
    # solid beside them, nothing of the plate above them (the socket boss
    # is 1.13 mm away in plan, 02 asserts it).
    for cy in (-4, 4):
        void(plate, 24.95, cy, -7.5, "wing bore (24.95, %+.0f) open 0.5 mm above the back face" % cy)
        void(plate, 24.95 + 2.8, cy, -7.55, "wing bore (24.95, %+.0f) rear counterbore" % cy)
        solid(plate, 24.95 + 2.8, cy, -6.5, "wing solid beside the wing bore (24.95, %+.0f) above its counterbore" % cy)
        void(plate, 24.95, cy, -5.0, "wing bore (24.95, %+.0f) mid-depth" % cy)
        void(plate, 24.95, cy, -2.3, "wing bore (24.95, %+.0f) open 0.3 mm under the wing top" % cy)
        for dx in (-1.5, 0.0, 1.5):
            void(plate, 24.95 + dx, cy, -1.5,
                 "wing bore (24.95, %+.0f) unroofed above the wing at dx=%+.1f" % (cy, dx))
        solid(plate, 24.95, cy + 2.8, -5.0, "wing solid beside the wing bore (24.95, %+.0f) in y" % cy)


def check_usb_jack(plate):
    """9.33 x 3.42 through-slot at (13.6, -19.0), collar, 45 deg ramps."""
    # slot is open the whole way through the plate and up the collar
    for z in (-7.5, -4.0, 0.5, 2.0):
        void(plate, 13.6, -19.0, z, "jack slot open at z=%.1f" % z)
    # slot walls are solid: 1.5 mm collar either side above the floor,
    # plate either side below it
    solid(plate, 13.6, -21.5, -4.0, "plate beside the slot (-Y)")
    solid(plate, 13.6, -16.5, -4.0, "plate beside the slot (+Y)")
    solid(plate, 13.6, -21.5, 2.0, "collar -Y wall")
    solid(plate, 13.6, -16.5, 2.0, "collar +Y wall")
    solid(plate, 8.0, -19.0, 2.0, "collar -X end wall")
    solid(plate, 19.2, -19.0, 2.0, "collar +X end wall")
    # below the ramp the channel is the full 3.42 mm
    void(plate, 13.6, -20.2, 2.0, "full-width channel below the ramp (-Y)")
    void(plate, 13.6, -17.8, 2.0, "full-width channel below the ramp (+Y)")
    # above the ramp it has narrowed to 1.82 mm
    solid(plate, 13.6, -20.2, 4.0, "ramped wall above z=3.38 (-Y)")
    solid(plate, 13.6, -17.8, 4.0, "ramped wall above z=3.38 (+Y)")
    void(plate, 13.6, -19.0, 4.0, "tail channel still open at z=4.0")
    # nothing above the collar top
    void(plate, 13.6, -19.0, 5.0, "above the 4.5 mm collar top")
    # the collar clears the plate edge and the LEGO counterbore band
    solid(plate, 20.3, -19.0, -4.0, "plate between collar and +X edge")
    void(plate, 13.6, -19.0, -8.5, "outside the back face")


def check_cap_cradle(plate):
    """Two 1.2 mm C-clip ribs saddling a 8.2 mm cap at y 16.75, z 5.5.

    Ribs moved 3.0/12.8 -> 5.0/14.8 on 2026-09-09 to clear the LEGO bore at
    (0.95, +12); see check_lego_bores_clear. Span (9.8 mm) is unchanged, so
    the cap sits the same way, centred at x 9.9 instead of x 7.9.
    """
    for rx in (5.0, 14.8):
        solid(plate, rx, 12.0, 2.0, "cradle rib body at x=%.1f" % rx)
        solid(plate, rx, 21.5, 2.0, "cradle rib body at x=%.1f" % rx)
        void(plate, rx, 16.75, 5.5, "cap bore at x=%.1f" % rx)
        solid(plate, rx, 16.75, 0.5, "rib material below the bore x=%.1f" % rx)
        void(plate, rx, 16.75, 8.5, "open above the rib top x=%.1f" % rx)
    # nothing between the ribs
    void(plate, 8.0, 16.75, 4.0, "clear between the cradle ribs")
    void(plate, 8.0, 12.0, 2.0, "clear between the cradle ribs")
    # ribs stop clear of the fence and the plate edge
    void(plate, 5.0, 11.0, 2.0, "gap between cradle rib and XIAO fence")
    void(plate, 5.0, 22.5, 2.0, "gap between cradle rib and plate edge")
    # REMOVED 2026-09-10: two probes at (5.0, 11.5, -0.75) and
    # (8.0, 11.25, -0.75) that asserted the +Y clip's outboard trench stayed
    # open under and beside the -X cradle rib. The trenches are gone
    # (02_backplate step 8b), so both points are ordinary solid plate and
    # the rib/trench interaction they guarded no longer exists. Flipping
    # them to `solid` here would only duplicate check_xiao_clips, which now
    # owns that ground; the rib's own placement is still guarded by
    # check_lego_bores_clear.


def check_radar_bay(plate, des):
    """Radar fence walls at radarCx +/- (radarW/2 + radarClear) (2026-10-26,
    radarClear 0.10 from the measured print: inner faces -19.15 / -3.85,
    outer -20.65 / -2.35): void 0.05 inside each inner face, solid 0.05
    into it, solid 0.05 inside each outer face, void 0.05 past it; the
    clip lips reach 0.5 past the board's edges (x -19.05 / -3.95)."""
    wo, wi, ei, eo, rCx = radar_walls(des)
    def pv(n): return des.userParameters.itemByName(n).value * 10
    if not (0.05 - 1e-9 <= pv("radarClear") <= 0.25 + 1e-9):
        FAILURES.append("radarClear %.2f is not 0.05..0.25" % pv("radarClear"))
    # -X wall at y 5 (clip A's band is y +/-3.5), +X wall at y 15 (clear of
    # the floor-to-top opening |y| < 9.4, clip C's band 10..17 only raises it above 10.5)
    void(plate, wi + 0.05, 5.0, 5.0, "radar bay open 0.05 inside the -X wall's inner face (x %.2f)" % wi)
    solid(plate, wi - 0.05, 5.0, 5.0, "-X fence wall solid 0.05 into its inner face")
    solid(plate, wo + 0.05, 5.0, 5.0, "-X fence wall solid 0.05 inside its outer face (x %.2f)" % wo)
    void(plate, wo - 0.05, 5.0, 5.0, "nothing 0.05 outside the -X fence wall")
    void(plate, ei - 0.05, 15.0, 5.0, "radar bay open 0.05 inside the +X wall's inner face (x %.2f)" % ei)
    solid(plate, ei + 0.05, 15.0, 5.0, "+X fence wall solid 0.05 into its inner face")
    solid(plate, eo - 0.05, 15.0, 5.0, "+X fence wall solid 0.05 inside its outer face (x %.2f)" % eo)
    void(plate, eo + 0.05, 15.0, 5.0, "nothing 0.05 outside the +X fence wall")
    # the lips: solid 0.5 past the board edge at lip height, void just under
    # the lip (the board's own space, 0.1 float) for all three clips
    # (B spans y -20.0..-13.0 since 2026-10-27; -17.0 is mid-finger)
    board_lo, board_hi = rCx - 7.55, rCx + 7.55
    for x, y, tag in ((board_lo + 0.3, 0.0, "A"), (board_hi - 0.3, -17.0, "B"), (board_hi - 0.3, 13.5, "C")):
        solid(plate, x, y, 11.95, "radar clip %s lip reaches 0.3 past the board edge (x %.2f)" % (tag, x))
        void(plate, x, y, 11.65, "radar clip %s lip floats above the board's front face" % tag)
    # clip B's finger spans y -20.0..-13.0 (2026-10-27): lip present at
    # -19.8, absent at -20.2
    solid(plate, board_hi - 0.3, -19.8, 11.95, "radar clip B lip starts by y -19.8")
    void(plate, board_hi - 0.3, -20.2, 11.95, "radar clip B lip absent at y -20.2")


def check_fence_walls_continuous(plate):
    """Both XIAO fence walls run unbroken past the clip finger.

    Was check_fence_notches until 2026-09-10, asserting a wire notch at
    x 14.5..18.0. The notches were deleted: with the clip's isolating slots
    gone (02_backplate step 8b) the finger's stiffness comes from wall
    continuity, so this now asserts the opposite of what it used to.
    """
    for sy in (-1, 1):
        tag = "+Y" if sy > 0 else "-Y"
        for x in (13.0, 16.0, 19.5):
            solid(plate, x, sy * 9.9, 4.0,
                  "fence wall unbroken at x=%.1f %s" % (x, tag))
        solid(plate, 16.0, sy * 9.9, 1.0, "fence wall solid to the floor " + tag)
        solid(plate, 8.0, sy * 9.9, 4.0, "clip finger untouched " + tag)


def check_end_bars(plate, des):
    """Two bars carry the RD-03D under its ends (2026-10-27, replacing
    crossbars A and B): -Y bar y -22.0..-20.8, +Y bar y +20.0..+22.0, both
    full bay width from the floor to the PCB rear face (10.46)."""
    wo, wi, ei, eo, rCx = radar_walls(des)
    # x stations 3 mm in from the walls: 2.1 mm clear of the pin centres
    # (-18.25 / -4.75), so "void above the bar" is not fooled by a pin
    for y, tag in ((-21.4, "-Y"), (21.0, "+Y")):
        for x in (wi + 3.0, rCx, ei - 3.0):
            solid(plate, x, y, 5.0, "%s end bar solid at x %.2f z 5" % (tag, x))
            solid(plate, x, y, 10.3, "%s end bar reaches the PCB rear at x %.2f" % (tag, x))
            void(plate, x, y, 10.6, "%s end bar stops at the PCB rear at x %.2f" % (tag, x))
    # the -Y bar stops short of the radar's 5-pin connector (y -20.7)
    void(plate, -12.0, -20.6, 8.0, "-Y bar clear of the connector at y -20.6")
    solid(plate, -12.0, -20.9, 8.0, "-Y bar material at y -20.9")
    # the +Y bar's inboard face
    void(plate, rCx, 19.8, 8.0, "+Y bar starts at y 20.0, open at 19.8")
    solid(plate, rCx, 20.2, 8.0, "+Y bar material at y 20.2")


def check_locating_pins(plate, des):
    """Two O2.2 pins in the RD-03D's corner half-notches (2026-10-27):
    centres (-18.25, -21.40) and (-4.75, +21.30), floor to z 12.4, cut flat
    on the outboard side at |y| 22.0. Each merges into its bay wall and its
    end bar."""
    for cx, cy, tag in ((-18.25, -21.40, "-Y"), (-4.75, 21.30, "+Y")):
        sy = 1 if cy > 0 else -1
        inb = 1 if cx < -10 else -1          # inboard x direction
        for z in (11.0, 12.2):               # above the bar: pin material only
            solid(plate, cx, cy, z, "%s pin solid at its centre z %.1f" % (tag, z))
        void(plate, cx, cy, 12.6, "%s pin top is below 12.6" % tag)
        solid(plate, cx + inb * 0.9, cy, 11.0, "%s pin reaches 0.9 inboard in x (r 1.1)" % tag)
        solid(plate, cx, cy - sy * 0.9, 11.0, "%s pin reaches 0.9 inboard in y" % tag)
        void(plate, cx + inb * 1.25, cy, 11.0, "%s pin no wider than r 1.1 (void 1.25 inboard)" % tag)
        # the flat at |y| 22.0: absolute positions, the centres are asymmetric
        void(plate, cx, sy * 22.1, 11.0, "%s pin cut flat at |y| 22.0: void at |y| 22.1" % tag)
        void(plate, cx, sy * 22.6, 11.0, "%s pin flat: void at |y| 22.6" % tag)
    # the -Y pin stands proud of its bar on the inboard side (bar ends at
    # -20.8, pin reaches -20.3), so this point is pin material only
    solid(plate, -18.25, -20.5, 5.0, "-Y pin material below the PCB inboard of the bar")


def check_radar_wire_window(plate, des):
    """The radar cable leaves the bay at floor level (2026-10-27): the +X
    bay wall is gone over |y| < 9.4 from floor to top, the XIAO fence's -X
    wall (x -5.0..-3.5, z 0..5) stays as the XIAO's stop and has a window
    |y| < 3.5, z 0..5."""
    wo, wi, ei, eo, rCx = radar_walls(des)
    wx = (ei + eo) / 2                       # +X bay wall centre line, -3.10
    # at floor level the XIAO's -X corner posts (x -3.25..-0.25, |y|
    # 5.9..8.9, z 0..3, step 5) overlap the old wall footprint, so the
    # z 1.0 probes sit at |y| 4.5, between the wire window and the posts
    for z in (1.0, 4.0, 8.0):
        void(plate, wx, 0.0, z, "+X bay wall open at y 0 z %.1f" % z)
        for y in ((4.5, -4.5) if z < 3.0 else (8.0, -8.0)):
            void(plate, wx, y, z, "+X bay wall open at y %+.1f z %.1f" % (y, z))
    solid(plate, wx, 15.0, 5.0, "+X bay wall intact beyond |y| 9.4 (+Y)")
    solid(plate, wx, -15.0, 5.0, "+X bay wall intact beyond |y| 9.4 (-Y)")
    # XIAO fence -X wall: kept at |y| 3.5..10.65, windowed at |y| < 3.5
    for y in (4.5, -4.5, 8.0, -8.0):
        solid(plate, -4.25, y, 2.5, "XIAO fence -X wall kept at y %.1f" % y)
        solid(plate, -4.25, y, 4.5, "XIAO fence -X wall to z 5 at y %.1f" % y)
    for y in (0.0, 2.5, -2.5):
        void(plate, -4.25, y, 0.5, "wire window open at floor, y %.1f" % y)
        void(plate, -4.25, y, 4.5, "wire window open to z 5, y %.1f" % y)
    void(plate, -4.25, 0.0, 5.5, "nothing above the fence wall at y 0")
    # the kept fence wall's +X face is the XIAO's -X stop at x -3.5
    for y in (8.0, -8.0):
        solid(plate, -3.6, y, 2.5, "fence stop face: solid 0.1 inside x -3.5 at y %.1f" % y)
        void(plate, -3.4, y, 2.5, "fence stop face: void 0.1 outside x -3.5 at y %.1f" % y)
    # the +X bay wall's opening ends at |y| 9.4
    for sy in (-1, 1):
        void(plate, wx, sy * 9.0, 5.0, "+X bay wall open at y %+.1f" % (sy * 9.0))
        solid(plate, wx, sy * 9.8, 5.0, "+X bay wall solid at y %+.1f" % (sy * 9.8))
    # the old corner cable exit is gone: wall solid at the -Y corner under clip B
    solid(plate, wx, -21.8, 5.0, "+X bay wall solid at the -Y corner (old exit closed)")
    # the lane from the window to the XIAO's -X end is clear at floor level
    void(plate, -2.0, 0.0, 1.0, "lane clear just +X of the window")


# RETIRED 2026-10-25 (morning): check_no_shell_notch, which asserted the +X
# wall solid where the wing notch then cut it.
# RETIRED 2026-10-25 (evening): check_shell_notch and check_pir_pod. The
# notch is gone with the wing tower it served: the shell's +X wall over the
# pod's width is now replaced by the pod box (check_pod_box), and the tower
# with its recess, ledge, groove, canted top and sloped wire hole by the
# straight socket boss (check_pir_socket). Nothing those two asserted can
# hold any more, so they are deleted rather than left to fail.
# RETIRED 2026-10-25 (Task 9d): the plug-seat, keeper-pin and snapYpx
# probes (in check_pir_socket and check_snaps). The retaining plug and its
# filament pin are gone (the snug socket and the bezel ring hold the
# sensor, check_bezel_fit) and the +X snap pair moved from the plate's
# edge at y +/-19 into the wing (check_snaps). Where it matters, the old
# positions are now probed SOLID so a stale build cannot pass.
# RETIRED 2026-10-25 (Task 9e): 9d's bayonet probes (notches in the top at
# 60/180/300, lug rest positions, lip/dome preload). The top is whole
# again round a r 11.6 hole (check_pod_box probes it at twelve angles).


def check_pod_box(shell, plate, des):
    """The shell's pod box (03_shell.py step 5c): the +X wall is gone over
    |y| <= pirBoxHalfY (13.5) from the back rim to z 14 and a 2 mm-walled
    box stands there, x 21..pirCx + pirBoxHalfX + wall (51), y
    +/-(pirBoxHalfY + wall) (15.5), z -8..16, open to the shell's cavity,
    with the r pirHoleR (11.6) lens hole through its top at (pirCx, 0)
    and nothing else cut in the top (9d's bayonet notches are gone). Its
    outer edges carry the shell's softening (r 2.5 corners, 1 mm front
    chamfer, 0.8 rim fillet); the lens hole rim and the two T-junction
    corners stay sharp."""
    import math
    def pv(n): return des.userParameters.itemByName(n).value * 10
    wall, intW, intD = pv("wall"), pv("intW"), pv("intD")
    cx, hy, hx, lensR = pv("pirCx"), pv("pirBoxHalfY"), pv("pirBoxHalfX"), pv("pirHoleR")
    xIn, xBoxIn, xBoxOut = intW / 2, cx + hx, cx + hx + wall     # 21, 49, 51
    by = hy + wall                                               # 15.5
    zTop = intD + wall                                           # 16
    # old +X wall gone over the box's width, present outboard of it
    for z in (-6.0, 5.0, 13.5):
        void(shell, 22.0, 0.0, z, "old +X wall gone at y 0, z %.1f" % z)
    for sy in (1, -1):
        void(shell, 22.0, sy * (hy - 0.5), 5.0, "old +X wall gone at y %+.1f" % (sy * (hy - 0.5)))
        solid(shell, 22.0, sy * (hy + 1.0), 5.0, "box +/-Y wall (y %+.1f) in the old wall's footprint" % (sy * (hy + 1.0)))
        solid(shell, 22.0, sy * (by + 1.5), 5.0, "+X wall present at y %+.1f" % (sy * (by + 1.5)))
        solid(shell, 22.0, sy * (by + 1.5), -4.0, "+X wall present at y %+.1f down to the rim (no notch)" % (sy * (by + 1.5)))
        solid(shell, 22.0, sy * (by + 1.5), 1.0, "+X wall present at y %+.1f (no wire slot)" % (sy * (by + 1.5)))
    solid(shell, 22.0, 0.0, 15.0, "front face continues over the old wall line")
    # box walls solid at three heights; cavity void; cavity open to the shell
    for z in (-6.0, 5.0, 12.0):
        solid(shell, xBoxOut - 1.0, 0.0, z, "box +X wall at z %.0f" % z)
        for sy in (1, -1):
            solid(shell, cx, sy * (hy + 1.0), z, "box %sY wall at z %.0f" % ("+" if sy > 0 else "-", z))
            if abs(z - pv("wingSnapZ")) > 1.0:        # (the wing bumps live at wingSnapZ +/-0.5)
                void(shell, cx, sy * (hy - 0.1), z, "box cavity open 0.1 mm inside its %sY wall" % ("+" if sy > 0 else "-"))
        void(shell, cx + 4.5, 0.0, z, "box cavity at z %.0f" % z)
        void(shell, xBoxIn - 0.1, 0.0, z, "box cavity open 0.1 mm inside its +X wall at z %.0f" % z)
    void(shell, cx, 10.0, -1.0, "box cavity open just above the wing top")
    void(shell, cx, 0.0, 13.5, "box cavity open up to the top's underside")
    void(shell, xIn, 0.0, 5.0, "box open to the shell's cavity at the old wall line")
    void(shell, xIn, 0.0, -6.0, "box open to the shell's cavity down at the rim (the wing passes)")
    # the plate's wing sits in the cavity with rimGap
    solid(plate, cx, hy - 0.35, -6.5, "wing reaches y %.2f inside the box cavity" % (hy - 0.35))
    void(shell, cx, hy - 0.35, -6.5, "box cavity clear of the wing's +Y side")
    solid(plate, xBoxIn - 0.3, 0.0, -5.0, "wing reaches x %.1f inside the box cavity" % (xBoxIn - 0.3))
    void(shell, xBoxIn - 0.3, 0.0, -5.0, "box cavity clear of the wing's far end")
    # top: 2 mm over the box with the lens hole
    for sy in (1, -1):
        solid(shell, cx, sy * (lensR + 0.5), 15.0, "top solid 0.5 mm outside the lens hole at y %+.1f" % (sy * (lensR + 0.5)))
        void(shell, cx, sy * (lensR - 0.3), 15.0, "lens hole open at y %+.1f" % (sy * (lensR - 0.3)))
        void(shell, cx + sy * (lensR - 0.3), 0.0, 15.0, "lens hole open at x %+.1f from the axis" % (sy * (lensR - 0.3)))
    void(shell, cx, 0.0, 15.0, "lens hole open on the axis")
    void(shell, cx, 0.0, 14.1, "lens hole open at the top's underside")
    void(shell, cx, 0.0, 15.9, "lens hole open at the face")
    solid(shell, cx + lensR + 0.5, 0.0, 15.0, "top solid 0.5 mm outside the lens hole (+X)")
    solid(shell, cx - lensR - 0.5, 0.0, 15.0, "top solid 0.5 mm outside the lens hole (-X)")
    solid(shell, xBoxIn - 0.5, 0.0, 15.0, "top solid over the box's +X wall")
    # the top round the hole is whole: solid at r lensR + 0.3 at twelve
    # angles (RETIRED 9d: three bayonet notches at 60/180/300) and the
    # hole rim sharp (no chamfer) at four
    for a in range(0, 360, 30):
        ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
        solid(shell, cx + (lensR + 0.3) * ca, (lensR + 0.3) * sa, 15.0, "top solid 0.3 outside the hole at %d deg (no notch)" % a)
        void(shell, cx + (lensR - 0.3) * ca, (lensR - 0.3) * sa, 15.0, "hole open 0.3 inside its wall at %d deg" % a)
    for a in (0.0, 90.0, 180.0, 270.0):
        ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
        solid(shell, cx + (lensR + 0.2) * ca, (lensR + 0.2) * sa, zTop - 0.2, "lens hole rim sharp (not chamfered) at %.0f deg" % a)
    # softening on the box: r cornerFillet on its two outer vertical
    # corners (void where the sharp corner was, solid 0.3 mm inside the
    # fillet surface on the diagonal), frontChamfer round its top edges,
    # softFillet on its back rim; the T-junction corners at (23, +/-17.5)
    # sharp (solid right into the concave corner on both faces, nothing
    # filled in outside it)
    r = pv("cornerFillet")
    k = (r - 0.3) / math.sqrt(2)
    for sy in (1, -1):
        tag = "(%.0f, %+.1f)" % (xBoxOut, sy * by)
        void(shell, xBoxOut - 0.3, sy * (by - 0.3), 5.0, "box sharp corner gone at " + tag)
        solid(shell, xBoxOut - r + k, sy * (by - r + k), 5.0, "box corner fillet surface solid inside at " + tag)
        solid(shell, 22.9, sy * (by + 0.1), 5.0, "T-junction: +X wall solid up to the concave corner, %sY" % ("+" if sy > 0 else "-"))
        solid(shell, 23.1, sy * (by - 0.1), 5.0, "T-junction: box wall solid up to the concave corner, %sY" % ("+" if sy > 0 else "-"))
        void(shell, 23.3, sy * (by + 0.3), 5.0, "T-junction left sharp (no concave fill), %sY" % ("+" if sy > 0 else "-"))
    ch = pv("frontChamfer")
    void(shell, xBoxOut - 0.3, 0.0, zTop - 0.3, "front chamfer: box's +X top edge gone")
    solid(shell, xBoxOut - ch - 0.3, 0.0, zTop - 0.1, "top solid inboard of the box's +X chamfer")
    void(shell, cx, by - 0.3, zTop - 0.3, "front chamfer: box's +Y top edge gone")
    void(shell, cx, -(by - 0.3), zTop - 0.3, "front chamfer: box's -Y top edge gone")
    void(shell, xBoxOut - 0.2, 0.0, -7.8, "rim fillet: box's +X back edge gone")
    solid(shell, xBoxOut - 0.2, 0.0, -6.5, "box +X face solid above the rim fillet")
    void(shell, cx, by - 0.2, -7.8, "rim fillet: box's +Y back edge gone")
    # the dome's field: rays from the face point at +/-46 deg (the lens's
    # vertical field) in the XZ plane and in the YZ plane, 15 mm out, in
    # free air (flat face, nothing can stand in the way, but recorded)
    for a in (46.0, -46.0):
        px, pz = cx + math.sin(math.radians(a)) * 15, zTop + math.cos(math.radians(a)) * 15
        void(shell, px, 0.0, pz, "lens field edge %+.0f deg (XZ) clear 15 mm out (shell)" % a)
        void(plate, px, 0.0, pz, "lens field edge %+.0f deg (XZ) clear 15 mm out (plate)" % a)
        void(shell, cx, px - cx, pz, "lens field edge %+.0f deg (YZ) clear 15 mm out (shell)" % a)


def check_pir_socket(plate, shell, des):
    """Straight socket on the PLATE's wing (02_backplate.py step 14,
    2026-10-25; blind bore since Task 9d): boss ring solid round a void
    bore along +Z that ends at the wing top, boss top at pirSeatZ, hook
    clearance outside the boss, level wire hole out of the boss's -X
    side, the wing solid under the bore (no keeper pin hole any more),
    fused to the plate and softened like the shell."""
    import math
    def pv(n): return des.userParameters.itemByName(n).value * 10
    wall, intW, intD, backT = pv("wall"), pv("intW"), pv("intD"), pv("backT")
    rimGapX, wingGap = pv("rimGapX"), pv("wingGap")  # measured allowances (02 ensure_params)
    cx, boreR, socketR = pv("pirCx"), pv("pirBoreR"), pv("pirSocketR")
    seatZ, hy, hx = pv("pirSeatZ"), pv("pirBoxHalfY"), pv("pirBoxHalfX")
    wireZ, wireR = pv("pirWireZ"), pv("pirWireDia") / 2
    xEdge = intW / 2 - rimGapX                       # 20.97
    if abs(des.userParameters.itemByName("pirTilt").value) > 1e-9:
        FAILURES.append("pirTilt is not 0: the straight socket is only right upright")
    xWing1 = cx + hx - rimGapX                       # 48.97
    wy = hy - wingGap                                # 15.62
    zTop, zBack, zWing = intD + wall, -backT, -backT + 6.0
    ringR = (boreR + socketR) / 2                    # 6.8: mid-wall of the boss
    # parameter-level guards (02 asserts the same at build time; repeated
    # here so a hand-edited parameter cannot slip past a stale plate)
    if not (socketR <= 9.6 - 0.3 + 1e-9):
        FAILURES.append("pirSocketR %.2f is not 0.3 mm inside the latch hook lips (r 9.6)" % socketR)
    if not (socketR - boreR >= 1.5 - 1e-9):
        FAILURES.append("socket boss wall %.2f mm is under 1.5" % (socketR - boreR))
    # bore sized on the measured base (Ø10.8 with calipers, 2026-10-25;
    # holes print true): 0.1..0.2 a side
    if not (5.4 + 0.1 - 1e-9 <= boreR <= 5.4 + 0.2 + 1e-9):
        FAILURES.append("pirBoreR %.2f is not 0.1..0.2 over the measured base radius 5.4" % boreR)
    # the cap on the sensor's pins (to case z -0.9, 02 step 14) must hang
    # >= 1 mm above the bore floor (the wing top)
    if not (-0.9 - zWing >= 1.0 - 1e-9):
        FAILURES.append("bore floor z %.1f is under 1 mm below the cap on the pins (z -0.9)" % zWing)
    # wing: solid between the plate edge and the boss, under the boss, out
    # to its far end; nothing above it beside the boss; back face flush
    solid(plate, 21.5, 0.0, -5.0, "wing fused to the plate edge")
    solid(plate, 21.5, 12.5, -5.0, "wing full width (+Y)")
    solid(plate, 21.5, -12.5, -5.0, "wing full width (-Y)")
    solid(plate, cx, wy - 0.3, -6.5, "wing reaches y %.2f" % (wy - 0.3))
    solid(plate, xWing1 - 0.3, 0.0, -5.0, "wing reaches its far end x %.2f" % (xWing1 - 0.3))
    void(plate, xWing1 + 0.3, 0.0, -5.0, "nothing past the wing's far end")
    void(plate, 21.5, 0.0, -1.0, "nothing above the wing between the plate and the boss")
    void(plate, cx, 10.0, -1.0, "nothing above the wing beside the boss")
    void(plate, cx + socketR + 0.3, 0.0, 0.0, "nothing above the wing 0.3 mm outside the boss")
    void(plate, 21.5, 0.0, -8.5, "wing back face flush with the plate's")   # near-trivial: guards a future zBack change only
    void(plate, cx, 0.0, -1.0, "bore open where the boss meets the wing")
    # boss foot fillet (02 step 14c'): concave r 1.0 at the boss/wing
    # corner, arc centre at (r 8.7, z -1). Inside the fillet material at
    # (r 7.9, z -1.8) (1.13 from the centre; air without the fillet), air
    # at (r 8.2, z -1.5) (0.71 from the centre: the fillet is no bigger
    # than r 1.0) and beyond its toe at (r 9.0, z -1.0).
    solid(plate, cx + socketR + 0.2, 0.0, -1.8, "boss foot fillet material (r 7.9, z -1.8)")
    solid(plate, cx, -(socketR + 0.2), -1.8, "boss foot fillet material (-Y side)")
    void(plate, cx + socketR + 0.5, 0.0, -1.5, "boss foot fillet is r 1.0, not bigger (r 8.2, z -1.5)")
    void(plate, cx + socketR + 1.3, 0.0, -1.0, "nothing beyond the foot fillet's toe (r 9.0, z -1.0)")
    # socket boss: ring solid, bore void, top at pirSeatZ
    for z in (-1.0, 5.0, 10.0, 13.0):
        for tag, dx, dy in (("+X", ringR, 0), ("-X", -ringR, 0), ("+Y", 0, ringR), ("-Y", 0, -ringR)):
            if tag == "-X" and abs(z - wireZ) < wireR + 0.3:
                continue                         # the wire hole runs there
            solid(plate, cx + dx, dy, z, "socket ring solid at r %.1f, %s, z %.0f" % (ringR, tag, z))
        void(plate, cx, 0.0, z, "bore open on the axis at z %.0f" % z)
        void(plate, cx + boreR - 0.3, 0.0, z, "bore open 0.3 mm inside its wall at z %.0f" % z)
    # BLIND (9d): open 0.2 above the wing top, solid 0.2 below it and all
    # the way to the back face; no exit on the back
    void(plate, cx, 0.0, zWing + 0.2, "bore open 0.2 mm above its floor (the wing top, z %.1f)" % zWing)
    void(plate, cx, boreR - 0.3, zWing + 0.2, "bore full radius just above its floor")
    for z in (zWing - 0.2, -5.0, -7.9):
        solid(plate, cx, 0.0, z, "wing solid under the bore floor at z %.1f (blind bore, no plug)" % z)
        solid(plate, cx, boreR - 0.3, z, "wing solid under the bore floor at r %.2f, z %.1f" % (boreR - 0.3, z))
        solid(plate, cx + boreR + 1.0, 0.0, z, "wing solid 1 mm outside the bore line at z %.1f" % z)
    void(plate, cx, 0.0, -8.5, "no bore exit on the back face (outside the part)")
    solid(plate, cx + ringR, 0.0, seatZ - 0.1, "boss solid 0.1 mm under its top (z %.1f)" % seatZ)
    void(plate, cx + ringR, 0.0, seatZ + 0.1, "nothing 0.1 mm above the boss top")
    void(plate, cx + ringR, 0.0, zTop - 0.5, "nothing of the plate near the shell's face over the boss")
    void(plate, cx + socketR + 0.3, 0.0, 5.0, "nothing 0.3 mm outside the boss")
    void(plate, cx, socketR + 0.3, 5.0, "nothing 0.3 mm outside the boss (+Y)")
    # latch hook lips (r 9.6..10.7, down to z 13.1) clear: void at r 10.1
    # z 13.5 all round, in the plate AND the shell (box cavity)
    for tag, dx, dy in (("+X", 10.1, 0), ("-X", -10.1, 0), ("+Y", 0, 10.1), ("-Y", 0, -10.1)):
        void(plate, cx + dx, dy, 13.5, "hook clearance outside the boss, %s (plate)" % tag)
        void(shell, cx + dx, dy, 13.5, "hook clearance outside the boss, %s (shell)" % tag)
        void(plate, cx + dx, dy, 12.9, "hook clearance down to z 12.9, %s (plate)" % tag)
    # wire hole: level along -X at z pirWireZ, through the boss's -X wall
    # only; solid above and below it in the wall; no hole on the +X side
    xw = cx - socketR + 0.5
    void(plate, xw, 0.0, wireZ, "wire hole through the boss's -X wall")
    void(plate, cx - boreR - 0.3, 0.0, wireZ, "wire hole meets the bore")
    void(plate, xw, 0.0, wireZ + wireR - 0.2, "wire hole full height (top)")
    void(plate, xw, 0.0, wireZ - wireR + 0.2, "wire hole full height (bottom)")
    solid(plate, xw, 0.0, wireZ + wireR + 1.0, "boss wall solid 1 mm above the wire hole")
    solid(plate, xw, 0.0, wireZ - wireR - 1.0, "boss wall solid 1 mm below the wire hole")
    solid(plate, xw, wireR + 0.4, wireZ, "boss wall solid 0.4 mm beside the wire hole (+Y)")
    solid(plate, cx + socketR - 0.5, 0.0, wireZ, "no wire hole on the boss's +X side")
    void(plate, cx - socketR - 0.5, 0.0, wireZ, "wire hole exits into the pod cavity (air)")
    void(shell, cx - socketR - 0.5, 0.0, wireZ, "pod cavity open where the wire hole exits")
    # RETIRED 9d: the keeper pin cross-hole along Y at (pirCx, -4.75)
    # through both wing faces. Gone with the plug: those points are solid
    # wing now (probed so a stale plate cannot pass).
    for sy in (1, -1):
        tag = "+Y" if sy > 0 else "-Y"
        solid(plate, cx, sy * (wy - 0.5), -4.75, "no keeper pin hole in the %s wing face (retired)" % tag)
        solid(plate, cx, sy * 9.0, -4.75, "no keeper pin hole inside the wing (y %+.0f)" % (sy * 9))
    solid(plate, cx, 0.0, -4.75, "no keeper pin hole under the bore floor")
    # softened wing edges (02 step 14d'): r cornerFillet on its two outer
    # vertical corners, softFillet on its back rim; the boss stays sharp
    r = pv("cornerFillet")
    k = (r - 0.3) / math.sqrt(2)
    for sy in (1, -1):
        tag = "(%.2f, %+.2f)" % (xWing1, sy * wy)
        void(plate, xWing1 - 0.3, sy * (wy - 0.3), -5.0, "wing sharp corner gone at " + tag)
        solid(plate, xWing1 - r + k, sy * (wy - r + k), -5.0, "wing corner fillet surface solid inside at " + tag)
        void(plate, cx, sy * (wy - 0.2), -7.8, "wing rim fillet: %sY back edge gone" % ("+" if sy > 0 else "-"))
        solid(plate, cx, sy * (wy - 0.2), -6.5, "wing %sY face solid above the rim fillet" % ("+" if sy > 0 else "-"))
    void(plate, xWing1 - 0.2, 0.0, -7.8, "wing rim fillet: +X back edge gone")
    solid(plate, xWing1 - 0.2, 0.0, -6.5, "wing +X face solid above the rim fillet")
    solid(plate, cx + socketR - 0.15, 0.0, seatZ - 0.15, "boss top rim sharp (flange seat)")
    # plate and shell never touch here: the boss inside the lens hole's
    # footprint but under the top (z 14 vs 14..16), the wing inside the
    # cavity (rimGap), the shell's top over the boss
    # (not the biting probe: check_pod_box asserts the hole's rim at r 11.2 / 11.5 + 0.5; this one only says the boss region is under open top)
    void(shell, cx + socketR + 0.5, 0.0, 15.0, "lens hole (r %.1f) open over the boss rim region: the flange and hooks pass" % pv("pirHoleR"))
    void(shell, cx + socketR + 0.5, 0.0, 13.8, "shell cavity just under its top, outside the boss")
    void(plate, cx + socketR + 0.5, 0.0, 13.8, "plate: nothing there either")


def check_bezel_fit(shell, plate, des, bezel):
    """The bezel ring (03_shell.py step 8, Task 9e) and what it meets. The
    bezel body is probed in ITS OWN frame (flange underside on z 0, axis
    +Z, notches on +/-X): `find` returns the component's body, not the
    parked occurrence (91_pir_fit.py probes the fitted state in the case
    frame against the sensor). Flange ring r innerR..flangeR x flangeT,
    with a continuous top, two skirt arcs r innerR..pirHoleR x skirtH
    below it, two notches pirNotchW wide through the skirt, continued
    into the flange's underside as blind relief pockets pirTabRelief
    deep out to r pirHoleR - 0.2 (11.45)."""
    import math
    def pv(n): return des.userParameters.itemByName(n).value * 10
    intD, wall = pv("intD"), pv("wall")
    cx, lensR = pv("pirCx"), pv("pirHoleR")
    flangeR, flangeT = pv("pirBezelFlangeR"), pv("pirBezelFlangeT")
    innerR, skirtH = pv("pirBezelInnerR"), pv("pirBezelSkirtH")
    tabW, notchW = pv("pirTabW"), pv("pirNotchW")
    relief = pv("pirTabRelief")
    skirtRo, bridgeRi = pv("pirBezelSkirtRo"), lensR - 0.2
    if not (lensR <= skirtRo <= lensR + 0.3 + 1e-9):
        FAILURES.append("bezel skirt r %.2f is not 0..0.3 over the r %.2f hole" % (skirtRo, lensR))
    if not (0.2 - 1e-9 <= relief and flangeT - relief >= 1.0 - 1e-9):
        FAILURES.append("tab relief %.2f / flange %.2f: need >= 0.2 of relief and >= 1.0 of solid flange over it"
                        % (relief, flangeT))
    zTop = intD + wall
    # parameter-level guards (03 asserts the same at build time)
    if not (innerR >= 10.3 + 0.10 - 1e-9 and innerR >= 10.35 + 0.05 - 1e-9):
        FAILURES.append("bezel inner r %.2f is under 0.10 off the lens ring / 0.05 off the dome flank" % innerR)
    if not (lensR - innerR >= 1.2 - 1e-9):
        FAILURES.append("bezel skirt wall %.2f is under 1.2 (two 0.6 lines)" % (lensR - innerR))
    if not (notchW >= tabW + 1.0 - 1e-9):
        FAILURES.append("bezel notch %.2f is under the tab width %.2f + 1.0" % (notchW, tabW))
    if not (abs(tabW - 5.0) <= 0.3):
        FAILURES.append("pirTabW %.2f is not the probed 5.0 (+/-0.3)" % tabW)
    if not (bridgeRi >= 11.0 + 0.3 - 1e-9 and flangeR - bridgeRi >= 1.0 - 1e-9):
        FAILURES.append("flange notch end r %.2f / bridge %.2f: need tab 11.0 + 0.3 and >= 1.0 of bridge" % (bridgeRi, flangeR - bridgeRi))
    if not (abs(skirtH - wall) <= 0.5 + 1e-9):
        FAILURES.append("bezel skirt %.2f tall is not the top's thickness %.2f" % (skirtH, wall))
    if not (flangeR >= lensR + 0.8 - 1e-9):
        FAILURES.append("bezel flange r %.2f bears under 0.8 on the face outside the hole" % flangeR)
    # --- the bezel in its own frame ---
    def B(want, r, ang, z, why):
        a = math.radians(ang)
        (solid if want else void)(bezel, r * math.cos(a), r * math.sin(a), z, "bezel: " + why)
    rs = (innerR + skirtRo) / 2
    for a in (90, 270, 45, 135):
        B(True, (innerR + flangeR) / 2, a, flangeT / 2, "flange solid at %d deg" % a)
        B(True, flangeR - 0.1, a, flangeT / 2, "flange reaches r %.1f at %d deg" % (flangeR - 0.1, a))
        B(False, flangeR + 0.1, a, flangeT / 2, "nothing past the flange rim at %d deg" % a)
        B(False, innerR - 0.1, a, flangeT / 2, "bore open through the flange at %d deg" % a)
        B(False, (innerR + flangeR) / 2, a, flangeT + 0.1, "nothing above the flange at %d deg" % a)
        B(False, (innerR + flangeR) / 2, a, -0.1, "flange underside flush: nothing below it outside the skirt at %d deg" % a) if (innerR + flangeR) / 2 > skirtRo else None
        B(True, rs, a, -skirtH / 2, "skirt solid at %d deg" % a)
        B(True, rs, a, -skirtH + 0.1, "skirt reaches its foot at %d deg" % a)
        B(False, rs, a, -skirtH - 0.1, "nothing below the skirt's foot at %d deg" % a)
        B(False, skirtRo + 0.05, a, -skirtH / 2, "nothing outside the skirt (r %.2f) at %d deg" % (skirtRo + 0.05, a))
        B(True, skirtRo - 0.05, a, -skirtH / 2, "skirt reaches its OD (r %.2f) at %d deg" % (skirtRo - 0.05, a))
        B(False, innerR - 0.1, a, -skirtH / 2, "bore open through the skirt at %d deg" % a)
        B(True, innerR + 0.1, a, -skirtH / 2, "skirt starts at its ID at %d deg" % a)
    B(False, skirtRo + 0.3, 90, -0.1, "nothing below the flange outside the skirt (r %.1f)" % (skirtRo + 0.3))
    for a in (0, 180):
        B(False, rs, a, -skirtH / 2, "skirt notch open at %d deg" % a)
        B(False, rs, a, -skirtH + 0.1, "skirt notch open to the foot at %d deg" % a)
        # relief pocket in the underside (void at r 10.9 = case z 16.2;
        # solid above it at z 0.8 and on top at z 1.3; solid at +/-90 deg
        # at the pocket's height)
        B(False, 10.9, a, 0.2, "tab relief pocket open at %d deg (r 10.9, z 0.2)" % a)
        B(False, rs, a, relief - 0.1, "relief pocket open up to its ceiling at %d deg" % a)
        B(False, innerR + 0.1, a, relief / 2, "relief pocket open at the bore at %d deg" % a)
        B(False, bridgeRi - 0.1, a, relief / 2, "relief pocket reaches r %.2f at %d deg" % (bridgeRi - 0.1, a))
        B(True, 10.9, a, 0.8, "flange solid above the pocket at %d deg (z 0.8)" % a)
        B(True, 10.9, a, flangeT - 0.2, "flange top continuous over the pocket at %d deg (z %.1f; past the 0.3 inner fillet)" % (a, flangeT - 0.2))
        # top edges softened (03 step 8d): 0.5 chamfer outside, 0.3 fillet inside
        B(False, flangeR - 0.05, a + 90, flangeT - 0.05, "outer top edge chamfered: void at r %.2f, z %.2f (%d deg)" % (flangeR - 0.05, flangeT - 0.05, a + 90))
        B(True, flangeR - 0.5, a + 90, flangeT - 0.05, "flange top solid inboard of the chamfer at r %.1f (%d deg)" % (flangeR - 0.5, a + 90))
        B(False, innerR + 0.05, a + 90, flangeT - 0.05, "inner top edge filleted: void at r %.2f, z %.2f (%d deg)" % (innerR + 0.05, flangeT - 0.05, a + 90))
        B(True, innerR + 0.05, a + 90, flangeT - 0.4, "flange solid under the inner fillet at z %.1f (%d deg)" % (flangeT - 0.4, a + 90))
        B(True, 10.9, a + 90, 0.2, "flange solid at %d deg at the pocket's height" % (a + 90))
        B(True, bridgeRi + 0.1, a, relief / 2, "flange solid outside the pocket from r %.2f at %d deg" % (bridgeRi + 0.1, a))
        B(True, (bridgeRi + flangeR) / 2, a, 0.1, "flange solid to its underside outside the pocket at %d deg" % a)
        B(False, (bridgeRi + flangeR) / 2, a, -0.1, "nothing under the flange outside the skirt at %d deg" % a)
    # notch width: open to +/-(notchW/2 - 0.3), solid at +/-(notchW/2 + 0.3), Cartesian on +X at r_s
    for sgn in (1, -1):
        void(bezel, rs, sgn * (notchW / 2 - 0.3), -skirtH / 2, "bezel: skirt notch open %.2f off its centre" % (sgn * (notchW / 2 - 0.3)))
        solid(bezel, rs, sgn * (notchW / 2 + 0.3), -skirtH / 2, "bezel: skirt solid %.2f off the notch centre" % (sgn * (notchW / 2 + 0.3)))
        void(bezel, rs, sgn * (notchW / 2 - 0.3), relief / 2, "bezel: relief pocket open %.2f off its centre" % (sgn * (notchW / 2 - 0.3)))
        solid(bezel, rs, sgn * (notchW / 2 + 0.3), relief / 2, "bezel: flange solid %.2f off the pocket centre" % (sgn * (notchW / 2 + 0.3)))
    # --- the shell where the bezel lands (case frame): face solid under
    # the flange all round, hole open round the skirt, hole wall at r lensR
    for a in range(0, 360, 45):
        ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
        solid(shell, cx + (flangeR - 0.1) * ca, (flangeR - 0.1) * sa, zTop - 0.1, "shell face solid under the flange rim at %d deg" % a)
        solid(shell, cx + (lensR + 0.1) * ca, (lensR + 0.1) * sa, zTop - 0.1, "shell face solid just outside the hole at %d deg" % a)
        void(shell, cx + (lensR - 0.1) * ca, (lensR - 0.1) * sa, zTop - 1.0, "hole open where the skirt sits at %d deg" % a)
        void(shell, cx + (lensR - 0.1) * ca, (lensR - 0.1) * sa, zTop - skirtH + 0.1, "hole open down to the skirt's foot at %d deg" % a)
        void(shell, cx + rs * ca, rs * sa, zTop - skirtH - 0.1, "cavity open under the skirt's foot at %d deg" % a)
    # bore floor and no keeper hole (check_pir_socket probes these in
    # detail; the two that matter to the retention repeated here)
    solid(plate, cx, 0.0, -2.2, "bore floor: wing solid 0.2 under the wing top")
    void(plate, cx, 0.0, -1.8, "bore open 0.2 above the wing top")
    solid(plate, cx, 0.0, -4.75, "no keeper pin hole (retired with the plug)")


def run(_context: str):
    app = adsk.core.Application.get()
    des = adsk.fusion.Design.cast(app.activeProduct)
    root = des.rootComponent
    plate = find(root, "BackPlate")
    shell = find(root, "FrontShell")
    bezel = find(root, "PirBezel")
    print("plate volume %.3f cm3   shell volume %.3f cm3   bezel volume %.3f cm3"
          % (plate.volume, shell.volume, bezel.volume))

    check_baseline(plate, shell, des)
    check_radar_bay(plate, des)
    check_fit_allowances(plate, shell, des)
    check_snaps(plate, shell, des)
    check_xiao_clips(plate)
    check_no_interior_counterbores(plate)
    check_lego_bores_clear(plate)
    check_usb_jack(plate)
    check_cap_cradle(plate)
    check_fence_walls_continuous(plate)
    check_end_bars(plate, des)
    check_locating_pins(plate, des)
    check_radar_wire_window(plate, des)
    check_pod_box(shell, plate, des)
    check_pir_socket(plate, shell, des)
    check_bezel_fit(shell, plate, des, bezel)

    if FAILURES:
        for f in FAILURES:
            print("FAIL:", f)
        raise RuntimeError("%d verification failure(s)" % len(FAILURES))
    print("VERIFY OK")
