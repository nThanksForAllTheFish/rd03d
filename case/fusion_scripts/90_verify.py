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
    """1.5 mm fingers, slots and trenches reaching z = -1.5."""
    for sy in (-1, 1):
        tag = "+Y" if sy > 0 else "-Y"
        # trenches: 1.2 mm wide, 1.5 mm deep, either side of the finger
        void(plate, 8.0, sy * 8.55, -0.75, "inboard clip trench " + tag)
        void(plate, 8.0, sy * 11.25, -0.75, "outboard clip trench " + tag)
        # the blade between them survives, and is rooted below the trenches
        solid(plate, 8.0, sy * 9.9, -0.75, "clip blade " + tag)
        solid(plate, 8.0, sy * 9.9, -2.0, "clip blade root below trench " + tag)
        # isolating slots now reach the trench depth
        void(plate, 4.0, sy * 9.9, -0.75, "clip slot runs to -1.5 " + tag)
        void(plate, 12.0, sy * 9.9, -0.75, "clip slot runs to -1.5 " + tag)
        # finger is full 1.5 mm: the old 0.5 mm outer shave is gone
        solid(plate, 8.0, sy * 10.4, 3.0, "finger at full thickness " + tag)
        # lip material spans lip_z(4.30)..top_z(5.60); z=4.30 is the board
        # top + 0.10 float, so probe just inside the lip, not in the gap
        solid(plate, 8.0, sy * 8.7, 4.40, "clip lip " + tag)
        # trenches are local to the finger: plate is solid beyond them in x.
        # Probed on the inboard trench's y band - the outboard band at
        # y +/-11.25 passes within 1.00 mm of the LEGO bore at (0.95, +/-12)
        # (nearest trench corner (4.4, 11.85): 3.453 from the bore centre,
        # less the 2.45 bore radius). This comment previously said 1.29 mm,
        # which was wrong in the unsafe direction.
        solid(plate, 2.0, sy * 8.55, -0.75, "plate solid beyond trench " + tag)
        solid(plate, 14.0, sy * 8.55, -0.75, "plate solid beyond trench " + tag)


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
    """
    for cx, cy in ((0.95, -12), (0.95, -4), (0.95, 4), (0.95, 12),
                   (8.95, -4), (8.95, 4)):
        for dx in (-1.5, 0.0, 1.5):
            void(plate, cx + dx, cy, 0.5,
                 "Technic bore (%.2f, %+.0f) unroofed at dx=%+.1f"
                 % (cx, cy, dx))
    # The clip slots' web to the same bore pair. The slots were narrowed
    # 1.0 -> 0.7 mm (02_backplate step 8b) because at 1.0 the web was
    # 0.431 mm - below what a 0.6 mm nozzle resolves. x = 3.3 is inside the
    # restored 0.70 mm web (bore wall reaches x 2.887 at y = +/-10.5, slot
    # now starts at 3.8), so this fails if either the slot creeps back out
    # or the bore grows.
    for sy in (-1, 1):
        solid(plate, 3.3, sy * 10.5, -0.75,
              "slot-to-bore web survives at y=%+.1f" % (sy * 10.5))


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
    # the +Y clip trench is not FILLED by a rib. The -X rib (x 4.4..5.6) now
    # overlaps the trench (x 4.4..11.6, y 10.65..11.85) in plan over
    # y 11.25..11.85 - deliberately, and harmlessly, because the rib is
    # z 0..8 and the trench z -1.5..0. This probe is the guard on that: it
    # fails the moment a rib is given a start below z = 0.
    void(plate, 5.0, 11.5, -0.75, "trench open UNDER the -X cradle rib")
    void(plate, 8.0, 11.25, -0.75, "outboard +Y clip trench still open")


def check_fence_notches(plate):
    """3.5 mm wide x 2.5 mm deep wire notches at x 14.5..18.0, both walls."""
    for sy in (-1, 1):
        tag = "+Y" if sy > 0 else "-Y"
        void(plate, 16.0, sy * 9.9, 4.0, "wire notch open " + tag)
        void(plate, 16.0, sy * 9.9, 2.8, "wire notch open " + tag)
        solid(plate, 16.0, sy * 9.9, 1.0, "wall below the notch " + tag)
        solid(plate, 13.0, sy * 9.9, 4.0, "wall intact -X of the notch " + tag)
        solid(plate, 19.5, sy * 9.9, 4.0, "wall intact +X of the notch " + tag)
        solid(plate, 8.0, sy * 9.9, 4.0, "clip finger untouched " + tag)


def check_no_shell_notch(shell):
    """The +X wall is continuous: the old notch spanned y +/-5.65, z -8..8."""
    for z in (-6.0, -2.0, 2.0, 6.0):
        solid(shell, 22.0, 0.0, z, "+X wall solid at z=%.1f" % z)
    solid(shell, 22.0, 4.0, 0.0, "+X wall solid at y=4")
    solid(shell, 22.0, -4.0, 0.0, "+X wall solid at y=-4")
    void(shell, 19.0, 0.0, 7.0, "cavity still open inside the +X wall")


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
    check_fence_notches(plate)
    check_no_shell_notch(shell)

    if FAILURES:
        for f in FAILURES:
            print("FAIL:", f)
        raise RuntimeError("%d verification failure(s)" % len(FAILURES))
    print("VERIFY OK")
