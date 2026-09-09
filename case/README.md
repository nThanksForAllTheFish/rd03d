# RD-03D + XIAO ESP32-C6 Case

Two-part snap-fit case designed natively in Fusion 360 (built via its MCP
API — the numbered scripts in `fusion_scripts/` are the construction record).
The living design is in your Fusion; save it to your own project.

## Parts

- `rd03d_case_back.stl` — back plate (8 mm thick): radar bay left, XIAO
  posts right, with a cantilever retention clip on each board's two side
  walls; six LEGO Technic pin holes (8 mm pitch, counterbored both faces)
  through the back for pin/ball-pin mounting. The rear face is otherwise
  fully flat (great first layer; tape sticks directly to it).
- `rd03d_case_shell.stl` — front shell: a radome step that brings the
  front wall down to 1.2 mm in front of the antennas (solid 3.1 mm of
  plastic there, exterior face still perfectly flat), USB-C notch, a
  hold-down boss over the XIAO, four snap bumps engage the plate's edge
  grooves.

## Printing

**PETG preferred** — the four retention clips are live springs and PLA is
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

1. Wire the boards (radar TX→D7, RX→D6, 5V, GND), then **press each board
   straight down until it clicks under its retention clips** — two per
   board, one on each side wall. Each clip's tapered face cams open as the
   board's edge goes past and springs back over it; to remove a board,
   push both clips outward with a fingernail. Seat the RD-03D patch-side
   out, the XIAO on its posts with USB-C toward the notch. The radar is
   still Y-loose until the shell closes; that's normal.
   - Radar clips: 0.6 mm of grab per side, on the ±X fence walls. The
     right-hand one sits toward the +Y end of the wall rather than at
     mid-height-centre, because the XIAO board crosses that wall at y≈0.
   - XIAO clips: 0.34 mm of grab per side, on the ±Y fence walls. They are
     deliberately lighter — the XIAO's top face is only 4.2 mm up, so the
     finger is short and is thinned to 1.0 mm to keep the bending strain
     survivable. They locate the board; the 7 × 7 mm boss on the inside of
     the shell's front wall, which comes down onto the XIAO's RF shield
     can, is what actually backs them up once the lid is on.
   The radar lands on two crossbars that bear on the bare PCB, in the two
   component-free bands across the board's back — its 5-pin connector
   hangs free in the space between them, so don't force the board down
   onto anything.
2. Snap the shell on (bumps click into the plate grooves). Unclip with a
   fingernail in the USB notch.
3. Mounting: push Technic pins / ball-pins into the six back holes
   (8 mm LEGO pitch: 1×4 column + 1×2 column); a ball-and-socket arm
   gives adjustable aim. Or stick VHB tape directly to the flat back
   if you prefer adhesive mounting.

## Tweaking fit

Open the design in Fusion → Modify → Change Parameters. `boardClear`,
`rimGap`, and `snapBump` are the fit-critical ones; `legoHole` is the
Technic pin hole diameter (tune ±0.1 mm if pins are too tight/loose after
a test print). No metal or foil in front of the radar, ever.
The retention clips and the radome step are local constants inside
`fusion_scripts/02_backplate.py` and `03_shell.py` (grab amounts, lip
heights, `RADOME_Z0`), not user parameters — edit them there and re-run
those two scripts.
Re-export STLs after edits (File → 3D Print, or re-run
`fusion_scripts/05_export.py` via `run_fusion.py`).

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
- **Retention clips (2026-09-08).** Each lip's flat underside sits
  0.10 mm above its board's face (radar 11.80 vs 11.70; XIAO 4.30 vs
  4.20), so the clips do not preload the boards at rest — they only bear
  if a board tries to lift. That float is deliberate: a permanently
  strained PETG finger would creep. Radar fingers are 7 mm wide × 1.5 mm
  thick with ~10 mm of lever (slots from z = 2.0); XIAO fingers are 7 mm
  wide but thinned to 1.0 mm with only ~4 mm of lever, which is why their
  grab is 0.34 mm rather than 0.60 mm. Insertion deflection is ~0.6 mm
  (radar, ≈1.4 % surface strain) and ~0.34 mm (XIAO, ≈3 % — the reason
  for PETG and for keeping the grab small). Each lip's 0.6–0.85 mm flat
  underside is a small unsupported overhang printing back-face-down;
  that is expected and bridges fine at 0.2 mm layers.
- Caution: re-running `fusion_scripts/01_setup.py` resets ALL user
  parameters to the repo defaults, overwriting any tuning you did in
  Fusion's Change Parameters dialog.
- If the lid snaps on too hard/soft, tune the `snapBump` user parameter
  (0.4-0.6 mm) and reprint the shell only.
