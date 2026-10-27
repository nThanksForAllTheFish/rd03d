# Back plate: PCB-notch locating pins, end bars, rotated XIAO — Design

**Date:** 2026-10-27
**Branch:** `feat/pir-companion`
**Scripts:** `case/fusion_scripts/02_backplate.py`, `03_shell.py`, `04_boards.py`, `90_verify.py`
**Supersedes:** the radar Y-restraint and crossbar parts of `2026-09-06-rd03d-case-design.md`; the XIAO orientation in `2026-09-09-usb-c-base-jack-design.md`

## Goal

Three plate changes from the user's review of the 2026-10-26 print, now that the
layout is otherwise final:

1. Locate the RD-03D with the two half-notches in its own PCB corners instead of
   the shell's retention ribs.
2. Support the board at its ends instead of on two crossbars placed between
   rear components, and let the connector's wires drop to the floor and leave
   the bay through an opening at the foot of the +X wall, not over the top of it.
3. Turn the XIAO 180°. Its USB port is blocked in every layout since the base
   jack, so point the ceramic antenna at the plastic PIR wing instead of at the
   radar's ground plane.

Nothing else on the plate moves: Technic grid, jack, capacitor cradle, wing,
socket boss, bezel, −X wall and its snap pockets, the three radar clips (one
shifts 0.5 mm) and the two XIAO clips all stay.

## What the vendor model says (probed read-only on the placed body, mm, case frame)

- Board x −19.06..−3.94, y ±22.02. Bare PCB rear face z 10.46, front face 11.76.
- Two corners are open half-notches, radius 1.14 (Ø2.28), the arc confirmed by
  containment from the centre in both inboard directions:
  - (−18.25, −21.40) at the −X/−Y corner
  - (−4.75, +21.30) at the +X/+Y corner
- The other two corners are r 1.8 rounded corners, not holes (solid at their
  centres).
- Rear side: the 5-pin connector reaches z 6.64 over y −20.7..−13.5, x about
  −15.3..−9.3. Scattered passives reach z 9.0..9.3 over the middle of the board.
  The end bands are bare PCB: y −22.0..−20.7 across the full width, and
  y +19.8..+22.0 across the full width.

## Design

### Locating pins (new, 02 step 6b)

Two pins, modelled Ø2.2 (thin pillars print about 0.2 under, giving roughly
0.15 mm of radial play in the Ø2.28 notch; diameter chosen by the agent, 2026-10-27), centred on the notch centres above,
from the plate floor (z 0) to z 12.4, with a 0.4 × 45° chamfer on the top edge
as lead-in. 12.4 keeps 0.5 under the shell's 12.9 radome step.

Each pin is cut flat on its outboard side at |y| = 22.0 (the board's end line),
which keeps it inside the board's footprint and clear of the shell's ±Y wall.
Each pin merges into the adjacent ±X bay wall (the −Y pin spans x −19.35..−17.15 and the
−X wall's inner face is −19.15; the +Y pin spans −5.85..−3.65 against the +X
wall's −3.85) and into its end bar, so its free length above the bar is 2 mm.

The pins own the board's Y location and rotation. X location stays shared with
the bay walls at radarClear 0.10; the two agree to within the play, so this is
not an over-constraint that can bind.

### End bars (replace crossbars A and B, 02 step 4)

Two bars from the floor to PCB_REAR_Z (10.46), full bay width between the walls:

- −Y bar: y −22.0..−20.8 (1.2 wide). It stops 0.1 short of the connector at −20.7.
- +Y bar: y +20.0..+22.0 (2.0 wide).

Both tie into both bay walls. Crossbar A, its cable slot (step 13) and the
corner cable exit (step 12) are deleted; the +Y pin and bar replace crossbar B.
Clip B moves from y −20.5..−13.5 to y −20.0..−13.0, leaving 0.8 mm between its
raised span and the −Y bar's face at −20.8 (the old rule for crossbar A asked
for 0.7). Clip C (y 10..17) is
already 3 mm clear of the +Y bar.

### Wire opening (replaces the 4b notch)

Over |y| < 9.4 the radar's +X wall and the XIAO fence's −X wall overlap into
one 2.65 mm slab (x −5.0..−2.35). It becomes:

- x −3.5..−2.35 removed from the floor to the wall top (z 0..11): with the
  XIAO's USB end now on this side nothing rests on the old 3 mm stub, and the
  clip B and C stretches beyond |y| 9.4 are all this wall does.
- x −5.0..−3.5 kept as the fence wall, z 0..5, so the XIAO keeps its −X stop
  face at x −3.5. Above z 5 the radar wall is gone over this band too.
- a wire window through the kept fence wall, |y| < 3.5, z 0..5.

The 4-wire cable drops from the connector to the floor, runs under the radar
board and through the window. The window exits directly under the rotated
USB-C receptacle (z 3.3..7.5), and the XIAO stands on 3 mm posts, so the wires
carry on under the XIAO (below z 3, clear of the four 3 × 3 corner posts at
x −3.25..−0.25 and 16.25..19.25, |y| 5.9..8.9).

Which pads are at which end: on the XIAO, 5V, GND, 3V3 and D0..D2 sit at the
USB end and D6/D7 at the antenna end. After the rotation (mirror about xCx =
8.0 of the pre-rotation record 5V ≈ 14.9, GND ≈ 12.4, D6/D7 ≈ −0.4) that is
5V ≈ x 1.1, GND ≈ 3.6, D1 ≈ 3.6 and 3V3 ≈ 6.2 at the −X (window) end, and D6
and D7 ≈ 16.4 at the +X (wing) end. So the radar's 5V and GND come up in the
two channels beside the receptacle (x −3.5..−1.75, |y| 4.45..5.9), and only the
two UART wires (OT1→D7, RX←D6) run the length of the board underneath, about
25 mm, and come up at the fence's open +X end past x 19.25. The board-to-fence
gap along the ±Y edges is 0.25 mm, so nothing rises there. The PIR's 3V3, GND
and D1 come over the wing and across the board top to the window end. 3V3 at
x ≈ 6.2 is inside the clip lips' span (x 4.5..11.5, 0.10 above the board), so
that joint must stay flat; the other five pads are outside it.

The window is narrower than the USB-C receptacle (8.9 wide) on purpose: the
receptacle's shoulders are the XIAO's −X stop against the fence face at x −3.5,
0.25 mm away as today.

### XIAO rotation (04_boards, 02 step 5)

`04_boards.py` places the XIAO with the extra 180° about Z (`flip180=True`
in `rot_matrix`), component side still up. USB overhang at x −3.25, board body
x −1.75..19.25. The bay envelope is symmetric about xCx so the posts, the ±Y
fences and the XIAO clips are unchanged.

No +X end wall is added (user's call, 2026-10-27): the XIAO keeps its −X stop
only, as today, and the antenna end faces the open pod box.

### Shell (03 steps 4b/4c and 5b)

The radar retention ribs and their lead-in chamfers are deleted. The XIAO
hold-down boss (step 5b) moves from x 2.5..9.5 to x 6.5..13.5 so it still
lands on the shield can after the rotation; at its old position it would
have hit the rotated USB shell (x −3.2..4.1, z 3.3..7.5) by 11.6 mm³. Found
by the boards script's interference check on 2026-10-27; the spec missed it.
Both the plate and the shell must be reprinted; the bezel is unchanged.

### Verification (90_verify.py, 91_pir_fit.py)

- Replace the crossbar probes with: solid in both end bars at their midlines
  (z 5 and 10.2), void at the old crossbar positions, void over the bars above
  10.6.
- Pins: solid at both notch centres at z 1, 11, 12.2; void at z 12.6; solid 0.9
  inboard of each centre at z 11; void at the flat side 1.2 outboard.
- Wire window: void in the fence wall at (−4.25, 0, 2.5); solid at (−4.25, ±4.5,
  2.5); void in the radar +X wall at (−3.1, 0, 1.0) and (−3.1, ±8, 8).
- Clip B lip probes move with it; the cable exit and crossbar A tunnel checks go.
- 91: the interference run must report no plate/radar pair; the plate/shell
  allowance and bezel/shell press pairs are unchanged.

### Docs

`docs/wiring.png` is redrawn for the rotated XIAO (pad positions mirrored, the
radar wires entering at the −X end through the window, the jack's 5V/GND along
the −Y band to the same end). The plan's as-built notes record the probe
numbers above.

## Out of scope

Putting the XIAO under the radar (considered 2026-10-27, parked), narrowing the
plate, and any change to the wing, bezel or socket.
