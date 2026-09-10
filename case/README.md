# RD-03D + XIAO ESP32-C6 Case

Two-part snap-fit case designed natively in Fusion 360 (built via its MCP
API — the numbered scripts in `fusion_scripts/` are the construction record).
The living design is in your Fusion; save it to your own project.

## Parts

- `rd03d_case_back.stl` — back plate (8 mm thick): radar bay left, XIAO
  posts right, with five cantilever retention clips (three on the radar's
  ±X fence walls, one on each of the XIAO's ±Y walls);
  six LEGO Technic pin holes (8 mm pitch, counterbored on the **rear face
  only**) through the back for pin/ball-pin mounting; and a **USB-C power
  jack**, with a capacitor cradle and wire notches inside. Apart from the
  jack's mouth — which sits flush in it — the rear face is flat (great
  first layer; tape sticks directly to it), and so is the interior floor,
  which carries no counterbores.
- `rd03d_case_shell.stl` — front shell: a radome step that brings the
  front wall down to 1.2 mm in front of the antennas (solid 3.1 mm of
  plastic there, exterior face still perfectly flat), a hold-down boss
  over the XIAO, four snap bumps engage the plate's edge grooves. Its
  side walls are unbroken: the old side USB notch is **gone** — see the
  USB-C base jack section below.

## Printing

**PETG preferred** — the five retention clips are live springs and PLA is
brittle enough to snap one on the first insertion. 0.4–0.6 mm nozzle,
0.2 mm layers, no supports.
Back plate: print flat (back face down). Shell: print open-side-up.
Print the **shell at high or solid infill** (≥50 %, ideally 100 % over the
front wall): the 3.1 mm radome in front of the antennas should be
homogeneous plastic — sparse infill puts a patchwork of air pockets in the
radar's beam path and scatters it unpredictably.
Exterior edges are filleted/chamfered for comfort; the front face's 1 mm
chamfer prints cleanly bed-side.

## Assembly

Fit the USB-C power jack **first** — see the next section. It goes in from
inside the case, and its wires have to reach the XIAO's pads, so doing it
after the boards are clipped down means working around them.

1. Wire the boards (radar TX→D7, RX→D6, 5V, GND), then **press each board
   straight down until it clicks under its retention clips** — three for
   the radar, two for the XIAO. Each clip's tapered face cams open as the
   board's edge goes past and springs back over it; to remove a board,
   push the clips outward with a fingernail. Seat the RD-03D patch-side
   out, the XIAO on its posts with its own USB-C connector at the +X end
   (that port no longer reaches daylight — power comes in through the base
   jack instead). The radar is still Y-loose until the shell closes;
   that's normal.
   - **Insertion tip:** don't press a board down flat. Tuck one long edge
     under its clip(s) first, then rock/press the opposite edge down —
     you then only flex the clips on one side at a time, which roughly
     halves the force and keeps you from bowing the PCB.
   - Radar clips: 0.6 mm of grab per side, **three** of them — one on the
     −X fence wall at mid-height (y ≈ 0, over the radar IC), and two on
     the +X wall, at y ≈ −17 and y ≈ +13.5. The +X wall cannot carry a
     clip at y ≈ 0 because the XIAO board crosses it there, so its share
     is split into two clips, one behind each antenna group. These three
     have **no relief slots**: the lip sits 11.8 mm above the plate, so
     the 1.5 mm fence wall is already a long enough cantilever to give up
     the 0.6 mm of deflection at about 1 % surface strain. Slotting it
     would only have weakened the wall's real job, which is holding the
     radar board laterally.
   - XIAO clips: 0.34 mm of grab per side, on the ±Y fence walls, and
     these **do keep their relief slots**. Their lip is only 4.3 mm up,
     and wall stiffness scales as (thickness/length)³ — a slot-free
     1.5 mm wall at that length would be roughly 22× stiffer than the
     isolated finger and would need of order 65 N to move 0.2 mm, i.e.
     you would flex the PCB before the wall budged. The finger itself is
     the wall's full 1.5 mm — a 1.0 mm finger will not print on a 0.6 mm
     nozzle — and the bending strain is kept survivable by lengthening
     the lever rather than thinning it: a 1.2 mm trench either side sinks
     the cantilever root to 1.5 mm *below* the interior floor. They are
     still the light pair of the five. They locate the board; the
     7 × 7 mm boss on the inside of
     the shell's front wall, which comes down onto the XIAO's RF shield
     can, is what actually backs them up once the lid is on.
   The radar lands on two crossbars that bear on the bare PCB, in the two
   component-free bands across the board's back — its 5-pin connector
   hangs free in the space between them, so don't force the board down
   onto anything.
2. Snap the shell on (bumps click into the plate grooves). There is no
   longer a USB notch to hook a fingernail into, so to get the lid back
   off, work a thin plastic spudger or guitar pick into the parting seam
   at a corner and walk it along until the bumps let go.
3. Mounting: push Technic pins / ball-pins into the six back holes
   (8 mm LEGO pitch: 1×4 column + 1×2 column); a ball-and-socket arm
   gives adjustable aim. Or stick VHB tape directly to the flat back
   if you prefer adhesive mounting.

## USB-C base jack (added 2026-09-09)

Power comes in through a USB-C jack in the back plate — the LEGO-mount face.
The XIAO's own USB-C is **no longer reachable with the case closed**: the
shell's side notch is gone. Serial console and USB reflash need the lid
unclipped; OTA over WiFi is unaffected.

**Fit the CC pulldowns first.** The jack needs 5.1 kOhm from CC1 and from CC2
to GND. Without them a modern USB-C charger never enables VBUS — but a
USB-A-to-C cable works either way, because A ports always have VBUS live,
which makes this failure very confusing to diagnose.

**Assembly order:**

1. Solder the two supply wires to the jack's VBUS and GND pads on the bench.
   Do this before the jack goes anywhere near the case.
2. Push the jack into the collar **from inside the case**, mouth first. It
   stops when the metal shell wedges on the two 45 degree ramps, with the
   mouth flush at the back face and about 6.4 mm of the body standing above
   the floor. The tail pads stay exposed above the 4.5 mm collar.
3. Plug a cable in and confirm it seats fully **before** gluing.
4. Two dabs of epoxy in the collar. This is the only thing resisting
   pull-out — the connector has no rearward-facing surface for a printed
   feature to catch, so the ramps take the push-in load and the glue takes
   the rest.

**Capacitor.** The 100 uF electrolytic lies on its side in the two-rib cradle
in the +Y band, lead end toward +X. It snaps down past its equator; no lid
feature holds it.

**Wire routes.**

- Jack to XIAO: out of the collar, through the notch in the -Y fence wall at
  x 14.5..18.0, onto the XIAO's 5V and GND pads. There is a matching notch in
  the +Y wall if your board reads the other way round.
- Capacitor to the 5V rail: the XIAO fence is open on +X, giving a full-height
  channel at x 19.3..20.85 from the +Y band into the -Y band. Join at the jack
  pads or at the XIAO pads, whichever is tidier.

**Plug clearance.** A plug overmold wider than about 14 mm will foul a ball
joint in the LEGO hole at (8.95, -12). Use a plain Technic pin in that hole,
or a right-angle plug.

## Tweaking fit

Open the design in Fusion → Modify → Change Parameters. `boardClear`,
`rimGap`, and `snapBump` are the fit-critical ones; `legoHole` is the
Technic pin hole diameter (tune ±0.1 mm if pins are too tight/loose after
a test print). No metal or foil in front of the radar, ever.
The retention clips and the radome step are local constants inside
`fusion_scripts/02_backplate.py` and `03_shell.py` (grab amounts, lip
heights, `RADOME_Z0`), not user parameters — edit them there and re-run
those two scripts.
The eight `usbJack*` / `cap*` parameters are created by `02_backplate.py`,
not by `01_setup.py`, so they only exist once that script has run.
Re-export STLs after edits (File → 3D Print, or re-run
`fusion_scripts/05_export.py` via `run_fusion.py`).
`fusion_scripts/90_verify.py` is a read-only probe harness that asserts the
jack, cradle, notches, clips and the absent shell notch with
`pointContainment`; run it after any change and expect `VERIFY OK`.

## Design notes

- All free-standing printed walls are ≥1.5 mm (0.6 mm-nozzle friendly); the shell's radar ribs and snap bumps are thinner but are wall-attached, so they print as local wall thickening. The radar's side
  (Y) restraint comes from two ribs inside the shell, so the radar sits
  loose in Y until the lid snaps on — normal.
- **Antenna gap (corrected 2026-09-08).** The RD-03D's patch plane — the
  front face of its PCB — sits at z = 11.70 mm; the shell's front wall
  runs 14.00–16.00. That left a **3.10 mm air gap** in front of the
  patches, which at 24 GHz (λ = 12.5 mm) is almost exactly λ/4 = 3.125 mm:
  the worst possible spacing, because a quarter-wave air layer acts as an
  impedance transformer and the reflection off the plastic returns to the
  patches in phase. Thinning the wall to 1.2 mm (the old "window pockets")
  made it worse, not better — it pushed the plastic *further away*, to
  14.80. The wall is now stepped **down** to z = 12.90 over the two
  antenna zones, so the gap is **1.20 mm ≈ λ/10** and the plastic there is
  a solid 3.10 mm (12.90–16.00). The exterior face is untouched and still
  perfectly flat.
  The 3 mm band over the radar IC (y −4…+4) stays at 14.00: the IC
  protrudes to 12.95 and needs the room (1.05 mm), and the band doubles as
  a stiffening rib for the panel.
  For the record: the "1 mm gap" quoted in the original design was never
  the antenna gap — it was **IC-to-wall clearance** (board overall front
  extent 13.0 vs the wall at 14.0), and the patch plane is 1.3 mm behind
  the IC's tip.
- `windowT` (1.2 mm) is now unused by the antenna zones; it survives as a
  parameter only.
- There is no wire channel between the bays (the boards sit 0.7 mm apart);
  route the four jumpers over the notched fence wall between the bays
  (cut down to 3 mm height there for exactly this).
- Board seating (fixed 2026-09-07): the radar's two crossbar supports now
  top out at 10.46 mm, the measured rear face of its bare PCB, and sit in
  the two full-width component-free bands (y −12.8…−11.2 and
  y +17.7…+19.8). Previously both bars were cut to 6.65 mm — the board's
  total thickness including the rear connector — so the +Y bar missed the
  board by 3.85 mm and the −Y bar was the only support, resting on the
  connector; the board could rock on it. The board's resting height is
  unchanged (patch face still 1 mm behind the front inner wall), so the
  RF geometry is the same.
- The XIAO is held on its posts by a boss on the shell's inner front
  face, landing 0.2 mm above the RF shield can and clear of the USB-C
  connector.
- **Retention clips (2026-09-08, revised 2026-09-09).** Each lip's flat
  underside sits 0.10 mm above its board's face (radar 11.80 vs 11.70;
  XIAO 4.30 vs 4.20), so the clips do not preload the boards at rest —
  they only bear if a board tries to lift. That float is deliberate: a
  permanently strained PETG finger would creep. Radar clips are three
  7 mm lip bands on the full-thickness (1.5 mm) fence walls, tops at
  12.50 (−X, under the shell's 14.00 IC band) and 12.30 (both +X, under
  the 12.90 radome zones); XIAO fingers are 7 mm wide at the wall's full
  1.5 mm, slotted from z = −1.5, which is why their grab is 0.34 mm rather
  than 0.60 mm. Insertion deflection is ~0.6 mm (radar) and ~0.34 mm
  (XIAO, ≈2.3 % surface strain — the reason for PETG and for keeping the
  grab small). Each lip's 0.6–0.85 mm flat underside is a small unsupported
  overhang printing back-face-down; that is expected and bridges fine at
  0.2 mm layers.
- **Why the radar clips have no relief slots but the XIAO clips do
  (2026-09-09).** The radar lip is 11.8 mm above the plate. Treating the
  1.5 mm wall as a cantilever of that length, the 0.6 mm of tip
  deflection needed to clear the board edge works out at ≈1 % peak
  surface strain — a quarter of PETG's yield — for of order 12 N at the
  lip. So the wall flexes enough unaided, and the slots that used to
  isolate each finger were pure cost: they cut into the wall that
  restrains the radar board sideways. Removing them also freed the
  budget for a third clip. The XIAO lip is only 4.3 mm up. Stiffness
  goes as t³/L³, so the same 1.5 mm wall on a 4.3 mm lever is ≈22×
  stiffer than the isolated finger: ~65 N for 0.2 mm of travel. There the
  slots are what make the clip a spring at all, and they stay.
- **XIAO clip rework (2026-09-09).** The finger went from 1.0 mm back to
  the wall's own 1.5 mm — a 1.0 mm wall does not print on the 0.6 mm
  nozzle this case is designed around — and the strain that thinning used
  to buy is now bought by a longer lever instead: two 1.2 × 1.5 mm
  trenches drop the cantilever root to z = −1.5, taking the lever from
  4.30 to 5.80 mm. Peak strain 3·t·d/(2·L²) works out at 2.3 %, down from
  2.8 % at the old 1.0/4.30 and well clear of the 4.1 % a 1.5 mm finger
  would have seen on the old lever. Spring rate goes as t³/L³, so the
  insertion force is about 1.4× the old one. Lip (0.60) and grab (0.34)
  are unchanged: 0.6 and 1.2 are what a 0.6 mm nozzle resolves cleanly, so
  a *smaller* lip would print worse, not better.
- **Interior LEGO counterbores deleted (2026-09-09).** The six Technic
  bores keep their rear counterbore and rear entry chamfer but no longer
  have one on the inside — a pin only ever enters from the back — so the
  interior floor is flat and the bays gained a little usable depth.
- Caution: re-running `fusion_scripts/01_setup.py` resets ALL user
  parameters to the repo defaults, overwriting any tuning you did in
  Fusion's Change Parameters dialog.
- If the lid snaps on too hard/soft, tune the `snapBump` user parameter
  (0.4-0.6 mm) and reprint the shell only.
