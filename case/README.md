# RD-03D + XIAO ESP32-C6 Case

Two-part snap-fit case designed natively in Fusion 360 (built via its MCP
API — the numbered scripts in `fusion_scripts/` are the construction record).
The living design is in your Fusion; save it to your own project.

## Parts

- `rd03d_case_back.stl` — back plate (8 mm thick): radar bay left, XIAO
  posts right; six LEGO Technic pin holes (8 mm pitch, counterbored both
  faces) through the back for pin/ball-pin mounting. The rear face is
  otherwise fully flat (great first layer; tape sticks directly to it).
- `rd03d_case_shell.stl` — front shell: two 1.2 mm radar windows covering
  all six antenna patches (pocketed from the interior, so the exterior
  face is smooth), USB-C notch, a hold-down boss over the XIAO, four snap
  bumps engage the plate's edge grooves.

## Printing

PLA or PETG, 0.4–0.6 mm nozzle, 0.2 mm layers, no supports.
Back plate: print flat (back face down). Shell: print open-side-up.
Exterior edges are filleted/chamfered for comfort; the front face's 1 mm
chamfer prints cleanly bed-side.

## Assembly

1. Wire the boards (radar TX→D7, RX→D6, 5V, GND), seat the RD-03D in its
   bay patch-side out, the XIAO on its posts with USB-C toward the notch
   (the radar is Y-loose until the shell closes). The radar lands on two
   crossbars that bear on the bare PCB, in the two component-free bands
   across the board's back — its 5-pin connector hangs free in the space
   between them, so don't force the board down onto anything. A 7 × 7 mm
   boss on the inside of the shell's front wall comes down onto the
   XIAO's RF shield can and holds that board on its posts.
2. Snap the shell on (bumps click into the plate grooves). Unclip with a
   fingernail in the USB notch.
3. Mounting: push Technic pins / ball-pins into the six back holes
   (8 mm LEGO pitch: 1×4 column + 1×2 column); a ball-and-socket arm
   gives adjustable aim. Or stick VHB tape directly to the flat back
   if you prefer adhesive mounting.

## Tweaking fit

Open the design in Fusion → Modify → Change Parameters. `boardClear`,
`rimGap`, and `snapBump` are the fit-critical ones; `windowT` is the radar
window thickness (keep ≤1.6 mm, no metal/foil in front of the radar);
`legoHole` is the Technic pin hole diameter (tune ±0.1 mm if pins are
too tight/loose after a test print).
Re-export STLs after edits (File → 3D Print, or re-run
`fusion_scripts/05_export.py` via `run_fusion.py`).

## Design notes

- All free-standing printed walls are ≥1.5 mm (0.6 mm-nozzle friendly); the shell's radar ribs and snap bumps are thinner but are wall-attached, so they print as local wall thickening. The radar's side
  (Y) restraint comes from two ribs inside the shell, so the radar sits
  loose in Y until the lid snaps on — normal.
- All six antenna patches now radiate through 1.2 mm of plastic: two
  interior window pockets, one over the 2×2 RX array at the +Y end and
  one over the two TX patches nearer the connector. The ~3 mm of
  full-thickness wall left between them (over the radar IC) is a
  deliberate stiffening rib for the thin panel.
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
- Caution: re-running `fusion_scripts/01_setup.py` resets ALL user
  parameters to the repo defaults, overwriting any tuning you did in
  Fusion's Change Parameters dialog.
- If the lid snaps on too hard/soft, tune the `snapBump` user parameter
  (0.4-0.6 mm) and reprint the shell only.
