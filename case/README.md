# RD-03D + XIAO ESP32-C6 Case

Two-part snap-fit case designed natively in Fusion 360 (built via its MCP
API — the numbered scripts in `fusion_scripts/` are the construction record).
The living design is in your Fusion; save it to your own project.

## Parts

- `rd03d_case_back.stl` — back plate (8 mm thick): radar bay left, XIAO
  posts right; six LEGO Technic pin holes (8 mm pitch, counterbored both
  faces) through the back for pin/ball-pin mounting. The rear face is
  otherwise fully flat (great first layer; tape sticks directly to it).
- `rd03d_case_shell.stl` — front shell: 1.2 mm radar window (pocketed from
  the interior, so the exterior face is smooth), USB-C notch, four snap
  bumps engage the plate's edge grooves.

## Printing

PLA or PETG, 0.4–0.6 mm nozzle, 0.2 mm layers, no supports.
Back plate: print flat (back face down). Shell: print open-side-up.
Exterior edges are filleted/chamfered for comfort; the front face's 1 mm
chamfer prints cleanly bed-side.

## Assembly

1. Wire the boards (radar TX→D7, RX→D6, 5V, GND), seat the RD-03D in its
   bay patch-side out, the XIAO on its posts with USB-C toward the notch
   (the radar is Y-loose until the shell closes).
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

- All printed walls are ≥1.3 mm (0.6 mm-nozzle friendly). The radar's side
  (Y) restraint comes from two ribs inside the shell, so the radar sits
  loose in Y until the lid snaps on — normal.
- The radar's two TX patches sit under the full 2 mm wall (only the RX
  array end is under the 1.2 mm window). PLA/PETG at 24 GHz makes this a
  minor loss; if range matters, enlarging the window toward -Y is a
  parameter-and-rerun change.
- There is no wire channel between the bays (the boards sit 0.7 mm apart);
  route the four jumpers over the notched fence wall between the bays
  (cut down to 3 mm height there for exactly this).
- The radar board rests on its rear connector and can tilt slightly until
  the shell's front wall stops it; harmless, but seat it patch-side out
  before closing.
- Caution: re-running `fusion_scripts/01_setup.py` resets ALL user
  parameters to the repo defaults, overwriting any tuning you did in
  Fusion's Change Parameters dialog.
- If the lid snaps on too hard/soft, tune the `snapBump` user parameter
  (0.4-0.6 mm) and reprint the shell only.
