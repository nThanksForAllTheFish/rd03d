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
    # The two WING holes (2026-10-25, 02_backplate step 14d) at (48.95,
    # +/-4) are BLIND: 8 mm deep from the back face, ending inside the
    # tower's solid material at z 0, so the "unroofed" probe is inverted for
    # them: open and counterbored at the back, solid 0.5 mm past the end.
    for cy in (-4, 4):
        void(plate, 48.95, cy, -7.5, "wing bore (48.95, %+.0f) open 0.5 mm above the back face" % cy)
        void(plate, 48.95 + 2.8, cy, -7.55, "wing bore (48.95, %+.0f) rear counterbore" % cy)
        void(plate, 48.95, cy, -4.0, "wing bore (48.95, %+.0f) mid-depth" % cy)
        void(plate, 48.95, cy, -0.5, "wing bore (48.95, %+.0f) open to its full 8 mm" % cy)
        solid(plate, 48.95, cy, 0.5, "wing bore (48.95, %+.0f) ends blind in the tower" % cy)
        solid(plate, 48.95 + 2.8, cy, -6.5, "tower/wing solid beside the wing bore (48.95, %+.0f)" % cy)


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


# RETIRED 2026-10-25: check_no_shell_notch. It asserted the +X wall solid at
# (22, 0, -6), (22, 0, -2), (22, 0, 2) and (22, +/-4, 0) - exactly the
# region the wing notch now removes (y +/-13.8, z -8..+2). Its probes and
# the notch's cannot both hold, so the def is gone rather than left to fail
# or to be rewritten into check_shell_notch's negation. check_shell_notch
# below owns that wall now, including the "still solid above the notch"
# probe at z +4 that replaces the old z 7 one.


def check_shell_notch(shell):
    """The +X wall is cut away over the wing's width from the back rim to
    z +2 (03_shell.py step 7): the wing passes under it (z -8..-2) and the
    4 mm above is the wire slot. The wall is intact above and beyond it."""
    void(shell, 22.0, 0.0, -4.0, "notch open where the wing passes under the wall")
    void(shell, 22.0, 0.0, 1.0, "wire slot open above the wing")
    void(shell, 22.0, 13.0, -4.0, "notch reaches the wing's +Y side (13.5)")
    void(shell, 22.0, -13.0, -4.0, "notch reaches the wing's -Y side")
    solid(shell, 22.0, 0.0, 4.0, "+X wall solid above the notch")
    solid(shell, 22.0, 0.0, 10.0, "+X wall solid at mid-height")
    solid(shell, 22.0, 16.0, -4.0, "+X wall solid beyond the notch (+Y)")
    solid(shell, 22.0, -16.0, -4.0, "+X wall solid beyond the notch (-Y)")
    void(shell, 19.0, 0.0, 7.0, "cavity still open inside the +X wall")


def check_pir_pod(plate, shell, des):
    """Pod tower on the PLATE's wing (02_backplate.py step 14, 2026-10-25):
    recess and bore void, ledge and tower walls solid, bore open at the back
    face through the wing, keeper pin hole through both tower walls, wire
    hole out of the tower's -X face into the shell's notch, lens cone edges
    clear, the wing itself solid under the tower and fused to the plate."""
    import math
    def pv(n): return des.userParameters.itemByName(n).value
    wall, intW, intD, backT = pv("wall"), pv("intW"), pv("intD"), pv("backT")
    rimGap = pv("rimGap")
    recessR, recessD, boreR, podWall = pv("pirRecessR"), pv("pirRecessD"), pv("pirBoreR"), pv("pirPodWall")
    tilt = pv("pirTilt") if pv("pirTilt") < 1.6 else math.radians(pv("pirTilt"))
    sgn = 1.0 if pv("pirTiltSign") >= 0 else -1.0
    POD_GAP, WING_T = 0.03, 0.6                     # cm, as in 02 step 14
    xTow0 = intW / 2 + wall + POD_GAP               # 23.3
    zTop, zBack = intD + wall, -backT
    zWing = zBack + WING_T                          # -2
    depth = zTop - zBack
    podW = 2 * (recessR + podWall) + depth * math.tan(tilt)
    podL = 2 * (recessR + podWall)
    podCx = xTow0 + podW / 2
    xTow1 = xTow0 + podW
    ax = (sgn * math.sin(tilt), math.cos(tilt))
    # solid()/void() take MILLIMETRES (they scale by MM internally); the
    # parameters above are cm, so along() converts on the way out.
    def along(d, side=0.0):            # cm along the axis in, cm sideways in Y -> mm tuple
        return ((podCx - ax[0] * d) * 10, side * 10, (zTop - ax[1] * d) * 10)
    # wing: solid between the plate edge and the tower, under the tower,
    # and nothing above it outside the tower (the notch region)
    solid(plate, (intW / 2 - rimGap + xTow0) / 2 * 10, 0.0, -5.0, "wing fused to the plate edge")
    solid(plate, (intW / 2 - rimGap + xTow0) / 2 * 10, 12.5, -5.0, "wing full width (+Y)")
    solid(plate, (xTow1 - 0.1) * 10, 0.0, -5.0, "wing reaches the tower's far end")
    void(plate, (intW / 2 - rimGap + xTow0) / 2 * 10, 0.0, -1.0, "nothing above the wing between plate and tower")
    void(plate, (intW / 2 - rimGap + xTow0) / 2 * 10, 0.0, -8.5, "wing back face flush with the plate's")
    solid(plate, (xTow1 - 0.1) * 10, 12.5, 14.0, "tower corner solid near the top")
    # recess, ledge, groove
    x, y, z = along(0.1); void(plate, x, y, z, "recess centre")   # passes trivially: the bore is under it
    x, y, z = along(0.1, side=recessR - 0.03); void(plate, x, y, z, "recess edge")
    x, y, z = along(recessD - 0.05, side=recessR - 0.03); void(plate, x, y, z, "recess full depth at its edge (too-shallow recess)")
    flangeR, hookD = pv("pirFlangeR"), pv("pirHookD")
    x, y, z = along(recessD + 0.05, side=(boreR + flangeR) / 2); solid(plate, x, y, z, "flange ledge")
    x, y, z = along(recessD + 0.05, side=(flangeR + recessR) / 2); void(plate, x, y, z, "latch hook groove open below the ledge")
    x, y, z = along(hookD - 0.05, side=(flangeR + recessR) / 2); void(plate, x, y, z, "latch hook groove full depth")
    x, y, z = along(hookD + 0.05, side=(flangeR + recessR) / 2); solid(plate, x, y, z, "groove floor")
    # bore, through the tower and the wing
    x, y, z = along(recessD + 0.2); void(plate, x, y, z, "bore just behind the floor")
    x, y, z = along(1.0, side=boreR - 0.03); void(plate, x, y, z, "bore edge mid-depth")
    zb = (zWing - 0.05 - zTop) / -ax[1]             # axis depth at z -2.5 (inside the wing)
    x, y, z = along(zb); void(plate, x, y, z, "bore open through the wing")
    zb = (-0.79 - zTop) / -ax[1]                    # axis depth at z -7.9
    x, y, z = along(zb); void(plate, x, y, z, "bore open at the back face (z -7.9)")
    x, y, z = along(zb, side=boreR - 0.03); void(plate, x, y, z, "bore full radius at the back face")
    x, y, z = along(zb, side=boreR + 0.1); solid(plate, x, y, z, "wing solid 1 mm outside the bore at the back face")
    x, y, z = along(1.0, side=recessR + podWall / 2); solid(plate, x, y, z, "tower wall +Y")
    x, y, z = along(1.0, side=-(recessR + podWall / 2)); solid(plate, x, y, z, "tower wall -Y")
    # keeper pin (2026-10-25): a cross-hole along Y at axis depth pirPinD
    # through both +-Y pod walls (with the 10 mm plug the pin sits at
    # d 20.75, in the WING at z about -3.7). Its front surface must be
    # behind the plug's back end (pirSeatD + pirPlugL) or the filament stub
    # cannot go in with the plug seated; the wall 1.5 mm in front of and
    # behind the axis is solid, so it is a hole and not a slot; and at
    # least 1 mm of wing remains between the hole and the back face.
    pinDia, pinD = pv("pirPinDia"), pv("pirPinD")
    seatD, plugL = pv("pirSeatD"), pv("pirPlugL")
    if pinD - pinDia / 2 <= seatD + plugL:
        FAILURES.append("keeper pin front surface d %.2f mm is not behind the plug's "
                        "back end d %.2f mm" % ((pinD - pinDia / 2) * 10, (seatD + plugL) * 10))
    for sy in (1, -1):
        tag = "+Y" if sy > 0 else "-Y"
        x, y, z = along(pinD, side=sy * (podL / 2 - 0.05)); void(plate, x, y, z, "keeper pin hole through the %s pod wall" % tag)
    x, y, z = along(pinD - 0.15, side=podL / 2 - 0.05); solid(plate, x, y, z, "+Y pod wall solid 1.5 mm in front of the pin hole (hole, not a slot)")
    x, y, z = along(pinD + 0.15, side=podL / 2 - 0.05); solid(plate, x, y, z, "+Y pod wall solid 1.5 mm behind the pin hole")
    xp, _, zp = along(pinD)
    void(plate, xp, 0.0, zp, "keeper pin hole crosses the bore (open at y 0)")
    solid(plate, xp, podL / 2 * 10 - 0.5, zp - pinDia * 5 - 0.5, "wing solid 0.5 mm behind the pin hole (in the +Y wall), between it and the back face")
    solid(plate, xp, podL / 2 * 10 - 0.5, zp - pinDia * 5 - 2.0, "wing solid 2 mm behind the pin hole (in the +Y wall)")
    if not (zp - pinDia * 5 >= zBack * 10 + 1.0):
        FAILURES.append("keeper pin hole (z %.2f mm) leaves under 1 mm of wing to the back face" % zp)
    if not (xp + pinDia * 5 + 0.6 < 48.95 - 3.2):
        FAILURES.append("keeper pin hole at x %.2f mm is under 0.6 mm from the wing Technic holes" % xp)
    # wire hole (02 step 14c): leaves the bore at axis depth pirWireD and
    # slopes down to exit the tower's -X face at z WIRE_EXIT_Z = 0.2,
    # inside the shell's wire slot z -2..+2. Probe the exit just inside the
    # face, the same point outside it (free air, then the shell's notch at
    # the wall), and the hole's body half way along.
    WIRE_EXIT_Z = 0.02
    xw, _, zw = along(pv("pirWireD"))
    void(plate, (xTow0 + 0.05) * 10, 0.0, WIRE_EXIT_Z * 10 + 0.2, "wire hole exit on the tower's -X face")
    void(plate, (xTow0 + 0.05) * 10, 0.0, WIRE_EXIT_Z * 10 - 0.8, "wire hole exit, lower part")
    void(shell, 22.0, 0.0, WIRE_EXIT_Z * 10, "shell notch open in line with the wire hole exit")
    void(shell, 22.0, 0.0, -1.5, "shell notch open down to the wing top")
    # the hole's body 2.7 mm in from the exit (x 26: well outside the bore,
    # whose -X wall the hole meets at about x 30): on the sloped centre line,
    # with tower solid 2.5 mm above and below it
    slope = math.atan2(zw - WIRE_EXIT_Z * 10, xw - xTow0 * 10)
    xm = 26.0
    zm = WIRE_EXIT_Z * 10 + (xm - xTow0 * 10) * math.tan(slope)
    void(plate, xm, 0.0, zm, "wire hole body 2.7 mm in from the exit (sloped centre line)")
    solid(plate, xm, 0.0, zm - 2.5, "tower solid under the wire hole")
    solid(plate, xm, 0.0, zm + 2.5, "tower solid over the wire hole")
    solid(plate, (xTow0 + 0.05) * 10, 0.0, 3.0, "tower -X face solid above the wire exit")
    if not (zWing * 10 + 0.5 < WIRE_EXIT_Z * 10 - 1.6 and WIRE_EXIT_Z * 10 + 1.6 < 2.0):
        FAILURES.append("wire hole exit (centre z %.1f mm) is not inside the wire slot z -2..2" % (WIRE_EXIT_Z * 10))
    # lens cone edges: rays from the front-face axis point at +/-25 deg from
    # the bore axis in the XZ plane, probed 15 mm out, must be in free air
    # (neither the plate's tower nor the shell)
    for a in (25.0, -25.0):
        ang = tilt + math.radians(a)
        px = (podCx + sgn * math.sin(ang) * 1.5) * 10
        pz = (zTop + math.cos(ang) * 1.5) * 10
        void(plate, px, 0.0, pz, "lens cone edge %+.0f deg clear 15 mm out (plate)" % a)
        void(shell, px, 0.0, pz, "lens cone edge %+.0f deg clear 15 mm out (shell)" % a)
    # the tower never touches the shell: the 0.3 mm gap at x 23.0..23.3
    void(plate, 23.15, 0.0, 8.0, "gap between the tower and the shell wall (plate side)")
    void(shell, 23.15, 0.0, 8.0, "gap between the tower and the shell wall (shell side)")


def run(_context: str):
    app = adsk.core.Application.get()
    des = adsk.fusion.Design.cast(app.activeProduct)
    root = des.rootComponent
    plate = find(root, "BackPlate")
    shell = find(root, "FrontShell")
    print("plate volume %.3f cm3   shell volume %.3f cm3"
          % (plate.volume, shell.volume))

    check_baseline(plate, shell)
    check_xiao_clips(plate)
    check_no_interior_counterbores(plate)
    check_lego_bores_clear(plate)
    check_usb_jack(plate)
    check_cap_cradle(plate)
    check_fence_walls_continuous(plate)
    check_radar_cable_exit(plate)
    check_shell_notch(shell)
    check_pir_pod(plate, shell, des)

    if FAILURES:
        for f in FAILURES:
            print("FAIL:", f)
        raise RuntimeError("%d verification failure(s)" % len(FAILURES))
    print("VERIFY OK")
