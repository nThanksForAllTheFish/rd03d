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


def check_baseline(plate, shell):
    """Geometry that predates this plan and must survive every change."""
    solid(plate, 0, 0, -4, "plate core")
    void(plate, 0.95, -12, -4, "LEGO through-bore at x0.95 y-12")
    solid(plate, -11.5, -12.0, 1.0, "radar bay crossbar A (y -12.8..-11.2)")
    void(plate, -11.5, 0, 1.0, "radar bay is open between the crossbars")
    solid(plate, -20.0, 0, 6.0, "radar clip A wall at x -20.8..-19.3")
    solid(plate, 8.0, -9.9, 2.0, "XIAO -Y fence wall")
    solid(plate, 8.0, 9.9, 2.0, "XIAO +Y fence wall")
    void(plate, 8.0, -9.9, 6.5, "above the XIAO clip top (5.6)")
    solid(shell, 0, 0, 15.0, "shell front wall above the 14 mm ceiling")
    void(shell, 0, 0, 7.0, "shell interior cavity")


def check_snaps(plate, shell, des):
    """Snap pairs: -X at y +/-12 as always; the +X pair at y +/-snapYpx
    (19 since 2026-10-25 evening), outboard of the shell's pod box walls
    (y +/-15.5) so the lid's +X end is still retained. Bumps are 6 mm long
    and 0.5 proud of the inner wall (x 20.5..23 on +X), z -1.6..-0.4;
    pockets 6.2 long, 0.6 into the plate edge (x 20.25..20.85), z -1.7..-0.3.
    The bump's inboard end must clear the box wall by 0.3 and its outboard
    end the cavity's +/-Y wall by 0.5 (03_shell.py step 5 asserts the same;
    here so a hand-edited parameter cannot slip past a stale shell)."""
    ypx = des.userParameters.itemByName("snapYpx").value * 10
    boxOutY = (des.userParameters.itemByName("pirBoxHalfY").value
               + des.userParameters.itemByName("wall").value) * 10
    intH = des.userParameters.itemByName("intH").value * 10
    if not (ypx - 3 >= boxOutY + 0.3 - 1e-9):
        FAILURES.append("snapYpx %.1f: the +X bump's inboard end (y %.1f) is under 0.3 mm "
                        "from the pod box wall (y %.1f)" % (ypx, ypx - 3, boxOutY))
    if not (ypx + 3 <= intH / 2 - 0.5 + 1e-9):
        FAILURES.append("snapYpx %.1f: the +X bump's outboard end (y %.1f) is under 0.5 mm "
                        "from the cavity wall (y %.1f)" % (ypx, ypx + 3, intH / 2))
    for sy in (-1, 1):
        # +X side: bump and pocket at +/-ypx, none at +/-12 (where the box
        # cavity is open now: at x 20.75 that point is in the main cavity)
        void(shell, 20.75, sy * 12, -1.0, "no +X bump at y %+.0f (box cavity)" % (sy * 12))
        solid(shell, 20.75, sy * ypx, -1.0, "+X bump at y %+.1f" % (sy * ypx))
        solid(shell, 20.75, sy * (ypx + 2.5), -1.0, "+X bump reaches y %+.1f" % (sy * (ypx + 2.5)))
        void(shell, 20.75, sy * (ypx + 3.5), -1.0, "+X bump ends before y %+.1f" % (sy * (ypx + 3.5)))
        solid(shell, 20.75, sy * (ypx - 2.9), -1.0, "+X bump's inboard end at y %+.1f" % (sy * (ypx - 2.9)))
        void(shell, 20.75, sy * (ypx - 3.5), -1.0, "+X bump starts after y %+.1f (box wall clear)" % (sy * (ypx - 3.5)))
        void(shell, 20.75, sy * ypx, -3.0, "+X bump only spans z -1.6..-0.4")
        solid(shell, 22.0, sy * ypx, -1.0, "+X wall solid behind the bump (outboard of the box)")
        void(plate, 20.6, sy * ypx, -1.0, "+X pocket at y %+.1f" % (sy * ypx))
        void(plate, 20.6, sy * (ypx + 2.9), -1.0, "+X pocket reaches y %+.1f" % (sy * (ypx + 2.9)))
        solid(plate, 20.6, sy * (ypx + 3.5), -1.0, "plate edge solid past the +X pocket")
        solid(plate, 20.6, sy * 12, -1.0, "no +X pocket at y %+.0f" % (sy * 12))
        solid(plate, 20.6, sy * ypx, -2.5, "plate solid below the +X pocket (blind)")
        solid(plate, 20.6, sy * ypx, -0.1, "plate solid above the +X pocket (blind)")
        # -X side unchanged at +/-12
        solid(shell, -20.75, sy * 12, -1.0, "-X bump at y %+.0f" % (sy * 12))
        void(shell, -20.75, sy * ypx, -1.0, "no -X bump at y %+.1f" % (sy * ypx))
        void(plate, -20.6, sy * 12, -1.0, "-X pocket at y %+.0f" % (sy * 12))
        solid(plate, -20.6, sy * ypx, -1.0, "no -X pocket at y %+.1f" % (sy * ypx))


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


def check_radar_cable_exit(plate):
    """The +X bay wall is notched at its -Y corner for the radar cable.

    The connector pocket is otherwise sealed: bay walls at +/-X, crossbar A
    (full height, y -12.8..-11.2) at +Y, and only 0.84 mm to the plate edge
    at -Y. This notch is the cable's only route to the XIAO.
    """
    for z in (1.0, 5.0, 9.0):
        void(plate, -2.95, -21.8, z, "cable exit open at z=%.1f" % z)
    solid(plate, -2.95, -19.5, 5.0, "+X bay wall intact under clip B")
    # NB not probed at y=0: step 4b deliberately cuts this wall away above
    # z=postH over |y|<9.4 to clear the XIAO board, leaving only a 3 mm stub
    solid(plate, -2.95, 0.0, 1.5, "step-4b stub survives at mid-span")
    solid(plate, -2.95, 15.0, 5.0, "+X bay wall intact beyond the 4b notch")
    # crossbar A is slotted so the pocket opens into the bay under the board
    # crossbar A is tunnelled (not severed) hard against the +X wall, so the
    # bar still bears on the PCB across its full width
    void(plate, -5.6, -12.0, 8.0, "crossbar A cable notch open")
    void(plate, -4.0, -12.0, 9.0, "notch runs right up to the +X wall")
    solid(plate, -5.6, -12.0, 6.0, "bar solid below the notch (no bridge)")
    solid(plate, -5.6, -12.0, 1.0, "bar solid to the floor under the notch")
    solid(plate, -15.0, -12.0, 10.0, "bar still reaches the PCB rear at -X")
    solid(plate, -15.0, -12.0, 5.0, "crossbar A untouched away from the tunnel")
    solid(plate, -9.0, -12.0, 1.0, "crossbar A solid -X of the tunnel")
    # step-4b notch is open above the XIAO board so wires reach both edges
    void(plate, -2.95, 0.0, 6.0, "4b notch open above the XIAO board")
    # the lane the cable then runs along, between jack collar and XIAO fence
    void(plate, 3.0, -13.0, 2.0, "cable lane clear of the collar")
    void(plate, 12.0, -13.0, 2.0, "cable lane clear at the collar's +Y face")


# RETIRED 2026-10-25 (morning): check_no_shell_notch, which asserted the +X
# wall solid where the wing notch then cut it.
# RETIRED 2026-10-25 (evening): check_shell_notch and check_pir_pod. The
# notch is gone with the wing tower it served: the shell's +X wall over the
# pod's width is now replaced by the pod box (check_pod_box), and the tower
# with its recess, ledge, groove, canted top and sloped wire hole by the
# straight socket boss (check_pir_socket). Nothing those two asserted can
# hold any more, so they are deleted rather than left to fail.


def check_pod_box(shell, plate, des):
    """The shell's pod box (03_shell.py step 5c): the +X wall is gone over
    |y| <= pirBoxHalfY from the back rim to z 14 and a 2 mm-walled box
    stands there, x 21..pirCx + pirBoxHalfY + wall, y +/-(pirBoxHalfY +
    wall), z -8..16, open to the shell's cavity, with the r pirRecessR
    lens hole through its top at (pirCx, 0). Its outer edges carry the
    shell's softening (r 2.5 corners, 1 mm front chamfer, 0.8 rim fillet),
    the lens hole rim and the two T-junction corners stay sharp."""
    import math
    def pv(n): return des.userParameters.itemByName(n).value * 10
    wall, intW, intD = pv("wall"), pv("intW"), pv("intD")
    cx, hy, lensR = pv("pirCx"), pv("pirBoxHalfY"), pv("pirRecessR")
    xIn, xBoxIn, xBoxOut = intW / 2, cx + hy, cx + hy + wall     # 21, 49, 51
    by = hy + wall                                               # 15.5
    zTop = intD + wall                                           # 16
    # old +X wall gone over the box's width, present outboard of it
    for z in (-6.0, 5.0, 13.5):
        void(shell, 22.0, 0.0, z, "old +X wall gone at y 0, z %.1f" % z)
    for sy in (1, -1):
        void(shell, 22.0, sy * 13.0, 5.0, "old +X wall gone at y %+.0f" % (sy * 13))
        solid(shell, 22.0, sy * 14.5, 5.0, "box +/-Y wall (y %+.1f) in the old wall's footprint" % (sy * 14.5))
        solid(shell, 22.0, sy * 18.0, 5.0, "+X wall present at y %+.0f" % (sy * 18))
        solid(shell, 22.0, sy * 18.0, -4.0, "+X wall present at y %+.0f down to the rim (no notch)" % (sy * 18))
        solid(shell, 22.0, sy * 18.0, 1.0, "+X wall present at y %+.0f (no wire slot)" % (sy * 18))
    solid(shell, 22.0, 0.0, 15.0, "front face continues over the old wall line")
    # box walls solid at three heights; cavity void; cavity open to the shell
    for z in (-6.0, 5.0, 12.0):
        solid(shell, xBoxOut - 1.0, 0.0, z, "box +X wall at z %.0f" % z)
        for sy in (1, -1):
            solid(shell, cx, sy * (hy + 1.0), z, "box %sY wall at z %.0f" % ("+" if sy > 0 else "-", z))
            void(shell, cx, sy * (hy - 0.1), z, "box cavity open 0.1 mm inside its %sY wall" % ("+" if sy > 0 else "-"))
        void(shell, cx + 4.5, 0.0, z, "box cavity at z %.0f" % z)
        void(shell, xBoxIn - 0.1, 0.0, z, "box cavity open 0.1 mm inside its +X wall at z %.0f" % z)
    void(shell, cx, 10.0, -1.0, "box cavity open just above the wing top")
    void(shell, cx, 0.0, 13.5, "box cavity open up to the top's underside")
    void(shell, xIn, 0.0, 5.0, "box open to the shell's cavity at the old wall line")
    void(shell, xIn, 0.0, -6.0, "box open to the shell's cavity down at the rim (the wing passes)")
    # the plate's wing sits in the cavity with rimGap
    # (z -6.5, not -5: the keeper pin hole runs along Y at (pirCx, -4.75))
    solid(plate, cx, 13.3, -6.5, "wing reaches y 13.3 inside the box cavity")
    void(shell, cx, 13.3, -6.5, "box cavity clear of the wing's +Y side")
    solid(plate, xBoxIn - 0.3, 0.0, -5.0, "wing reaches x %.1f inside the box cavity" % (xBoxIn - 0.3))
    void(shell, xBoxIn - 0.3, 0.0, -5.0, "box cavity clear of the wing's far end")
    # top: 2 mm over the box with the lens hole
    for sy in (1, -1):
        solid(shell, cx, sy * 12.0, 15.0, "top solid at y %+.0f (outside the lens hole)" % (sy * 12))
        void(shell, cx, sy * 11.2, 15.0, "lens hole open at y %+.1f" % (sy * 11.2))
        void(shell, cx + sy * 11.2, 0.0, 15.0, "lens hole open at x %+.1f from the axis" % (sy * 11.2))
    void(shell, cx, 0.0, 15.0, "lens hole open on the axis")
    void(shell, cx, 0.0, 14.1, "lens hole open at the top's underside")
    void(shell, cx, 0.0, 15.9, "lens hole open at the face")
    solid(shell, cx + lensR + 0.5, 0.0, 15.0, "top solid 0.5 mm outside the lens hole (+X)")
    solid(shell, cx - lensR - 0.5, 0.0, 15.0, "top solid 0.5 mm outside the lens hole (-X)")
    solid(shell, xBoxIn - 0.5, 0.0, 15.0, "top solid over the box's +X wall")
    # lens hole rim sharp (the front chamfer skips it): solid 0.2 mm
    # outside the rim 0.2 mm under the face, all round
    for tag, dx, dy in (("+X", lensR + 0.2, 0.0), ("-X", -(lensR + 0.2), 0.0),
                        ("+Y", 0.0, lensR + 0.2), ("-Y", 0.0, -(lensR + 0.2))):
        solid(shell, cx + dx, dy, zTop - 0.2, "lens hole rim sharp (not chamfered), %s" % tag)
    # softening on the box: r cornerFillet on its two outer vertical
    # corners (void where the sharp corner was, solid 0.3 mm inside the
    # fillet surface on the diagonal), frontChamfer round its top edges,
    # softFillet on its back rim; the T-junction corners at (23, +/-15.5)
    # sharp (solid right into the concave corner on both faces, nothing
    # filled in outside it)
    r = pv("cornerFillet")
    k = (r - 0.3) / math.sqrt(2)
    for sy in (1, -1):
        tag = "(%.0f, %+.1f)" % (xBoxOut, sy * by)
        void(shell, xBoxOut - 0.3, sy * (by - 0.3), 5.0, "box sharp corner gone at " + tag)
        solid(shell, xBoxOut - r + k, sy * (by - r + k), 5.0, "box corner fillet surface solid inside at " + tag)
        solid(shell, 22.9, sy * 15.6, 5.0, "T-junction: +X wall solid up to the concave corner, %sY" % ("+" if sy > 0 else "-"))
        solid(shell, 23.1, sy * 15.4, 5.0, "T-junction: box wall solid up to the concave corner, %sY" % ("+" if sy > 0 else "-"))
        void(shell, 23.3, sy * 15.8, 5.0, "T-junction left sharp (no concave fill), %sY" % ("+" if sy > 0 else "-"))
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
    2026-10-25 evening): boss ring solid round a void bore along +Z, boss
    top at pirSeatZ, hook clearance outside the boss, level wire hole out
    of the boss's -X side, keeper pin hole through the whole wing at
    pirPinZ, the wing fused to the plate and softened like the shell."""
    import math
    def pv(n): return des.userParameters.itemByName(n).value * 10
    wall, intW, intD, backT, rimGap = pv("wall"), pv("intW"), pv("intD"), pv("backT"), pv("rimGap")
    cx, boreR, socketR = pv("pirCx"), pv("pirBoreR"), pv("pirSocketR")
    seatZ, hy = pv("pirSeatZ"), pv("pirBoxHalfY")
    wireZ, wireR = pv("pirWireZ"), pv("pirWireDia") / 2
    pinZ, pinR = pv("pirPinZ"), pv("pirPinDia") / 2
    seatD, plugL = pv("pirSeatD"), pv("pirPlugL")
    xEdge = intW / 2 - rimGap                        # 20.85
    if abs(des.userParameters.itemByName("pirTilt").value) > 1e-9:
        FAILURES.append("pirTilt is not 0: the straight socket is only right upright")
    xWing1 = cx + hy - rimGap                        # 48.85
    wy = hy - rimGap                                 # 13.35
    zTop, zBack, zWing = intD + wall, -backT, -backT + 6.0
    ringR = (boreR + socketR) / 2                    # 6.8: mid-wall of the boss
    # parameter-level guards (02 asserts the same at build time; repeated
    # here so a hand-edited parameter cannot slip past a stale plate)
    if not (socketR <= 9.6 - 0.3 + 1e-9):
        FAILURES.append("pirSocketR %.2f is not 0.3 mm inside the latch hook lips (r 9.6)" % socketR)
    if not (socketR - boreR >= 1.5 - 1e-9):
        FAILURES.append("socket boss wall %.2f mm is under 1.5" % (socketR - boreR))
    plugBackZ = zTop - seatD - plugL
    if not (plugBackZ - (pinZ + pinR) >= 0.5 - 1e-9):
        FAILURES.append("plug back end z %.2f is under 0.5 mm in front of the keeper pin's top z %.2f"
                        % (plugBackZ, pinZ + pinR))
    if not (pinZ - pinR - zBack >= 1.5 - 1e-9):
        FAILURES.append("keeper pin hole (z %.2f) leaves under 1.5 mm of wing to the back face" % pinZ)
    # wing: solid between the plate edge and the boss, under the boss, out
    # to its far end; nothing above it beside the boss; back face flush
    solid(plate, 21.5, 0.0, -5.0, "wing fused to the plate edge")
    solid(plate, 21.5, 12.5, -5.0, "wing full width (+Y)")
    solid(plate, 21.5, -12.5, -5.0, "wing full width (-Y)")
    solid(plate, cx, wy - 0.3, -6.5, "wing reaches y %.2f (z -6.5: under the pin hole)" % (wy - 0.3))
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
    for z in (-7.9, -5.0, -2.5):
        void(plate, cx, 0.0, z, "bore open through the wing at z %.1f" % z)
        void(plate, cx, boreR - 0.3, z, "bore full radius in the wing at z %.1f" % z)
        solid(plate, cx + boreR + 1.0, 0.0, z, "wing solid 1 mm outside the bore at z %.1f (+X: the pin hole crosses at y 0 only within r pinR of the axis)" % z)
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
    # keeper pin: a cross-hole along Y at (pirCx, pirPinZ) through BOTH wing
    # side faces, crossing the bore; solid 1.5 mm in front of / behind it
    # on both sides (a hole, not a slot), solid above it to the wing top
    # and below it to the back face
    for sy in (1, -1):
        tag = "+Y" if sy > 0 else "-Y"
        void(plate, cx, sy * (wy - 0.5), pinZ, "keeper pin hole through the %s wing face" % tag)
        void(plate, cx, sy * 9.0, pinZ, "keeper pin hole inside the wing (y %+.0f)" % (sy * 9))
        solid(plate, cx - pinR - 1.5, sy * (wy - 0.5), pinZ, "wing solid 1.5 mm -X of the pin hole, %s face" % tag)
        solid(plate, cx + pinR + 1.5, sy * (wy - 0.5), pinZ, "wing solid 1.5 mm +X of the pin hole, %s face" % tag)
        solid(plate, cx, sy * (wy - 0.5), pinZ + pinR + 0.5, "wing solid 0.5 mm above the pin hole, %s face" % tag)
        solid(plate, cx, sy * (wy - 0.5), pinZ - pinR - 0.5, "wing solid 0.5 mm below the pin hole, %s face" % tag)
        solid(plate, cx, sy * (wy - 0.5), zWing - 0.3, "wing top solid above the pin hole, %s face" % tag)
    void(plate, cx, 0.0, pinZ, "keeper pin hole crosses the bore (open at y 0)")
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
    void(shell, cx + socketR + 0.5, 0.0, 15.0, "lens hole (r %.1f) open over the boss rim region: the flange and hooks pass" % pv("pirRecessR"))
    void(shell, cx + socketR + 0.5, 0.0, 13.8, "shell cavity just under its top, outside the boss")
    void(plate, cx + socketR + 0.5, 0.0, 13.8, "plate: nothing there either")


def run(_context: str):
    app = adsk.core.Application.get()
    des = adsk.fusion.Design.cast(app.activeProduct)
    root = des.rootComponent
    plate = find(root, "BackPlate")
    shell = find(root, "FrontShell")
    print("plate volume %.3f cm3   shell volume %.3f cm3"
          % (plate.volume, shell.volume))

    check_baseline(plate, shell)
    check_snaps(plate, shell, des)
    check_xiao_clips(plate)
    check_no_interior_counterbores(plate)
    check_lego_bores_clear(plate)
    check_usb_jack(plate)
    check_cap_cradle(plate)
    check_fence_walls_continuous(plate)
    check_radar_cable_exit(plate)
    check_pod_box(shell, plate, des)
    check_pir_socket(plate, shell, des)

    if FAILURES:
        for f in FAILURES:
            print("FAIL:", f)
        raise RuntimeError("%d verification failure(s)" % len(FAILURES))
    print("VERIFY OK")
