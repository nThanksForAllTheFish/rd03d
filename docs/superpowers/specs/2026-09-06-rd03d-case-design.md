# RD-03D + XIAO Case — Design

**Date:** 2026-09-06
**Deliverable:** 3D-printable two-part case, built as a NATIVE Fusion 360
parametric design directly in the user's running Fusion instance via its MCP
server (http://127.0.0.1:27182/mcp — Autodesk adapter, `script` feature runs
Python against the live Fusion API). Revised 2026-09-07 from the earlier
CadQuery/STEP-import approach at the user's request: this yields a real
feature timeline and Fusion **user parameters**, fully editable in Fusion.
**Boards (from the user's STEP models, measured with the OCC kernel):**
- RD-03D radar stick: 15.10 × 44.02 mm, 6.35 mm thick incl. rear connector
  (`/Users/me/Downloads/rd-03d-sensor-1/RD-03D.step`)
- XIAO ESP32-C6: 22.46 × 17.78 mm footprint (incl. USB-C overhang), 4.46 mm
  tall (`/Users/me/Downloads/seeed-studio-xiao-esp32-c6-1/Seeed
  Studio XIAO ESP32-C6.step`)

## Decisions Made

- **Mounting (revised 2026-09-07 change request):** LEGO Technic interface —
  the back plate is 8 mm thick (`backT`) with SIX ⌀4.9 mm through-holes on
  the exact 8 mm LEGO pitch (a 1×4 column at x=0.95 plus a 1×2 column at
  x=8.95, rows y=±4 / ±12), counterbored 6.4×0.9 both faces with chamfered
  entries, so standard pins/ball-pins/socket arms mount the case with
  adjustable aim. The flat back + 0.6 mm tape recess remain as a secondary
  adhesive option. Case deepens to 46×50×24 overall.
- **Assembly:** snap-fit — front shell with four cantilever clips engaging the
  back plate rim. Tool-free open.
- **Format:** native Fusion design. All key dimensions become Fusion USER
  PARAMETERS (wall, window thickness, clearances, snap sizes) so the user
  edits them in Modify → Change Parameters and the model updates. The MCP
  build scripts are committed to the repo for reproducibility; the design
  itself lives in the user's Fusion (they save it to their own project).

## Layout

Two printed parts:

1. **Back plate** — flat, ~2 mm, adhesive face with a 0.6 mm recessed tape
   pocket. Carries the board mounts:
   - RD-03D: edge-rail pocket (board has no mounting holes) holding the stick
     patch-side-forward; small retention nubs; ≥7 mm clearance behind the
     board for its rear connector + jumper wires.
   - XIAO: corner posts registering the board outline, USB-C port aligned to
     the shell's short-side cutout.
   - Boards side by side; open channel between them for the 4 jumper wires.
2. **Front shell** — 2 mm walls, drops over the back plate, four snap clips.
   - **Radar window:** front wall thinned to 1.2 mm in a panel covering the
     RD-03D antenna end. No other feature in front of the patches.
   - **USB-C cutout:** a notch through the shell rim on a short side (prints
     support-free), sized for a typical USB-C plug overmold (~10.5 × 6 mm
     opening + 0.4 mm clearance).

Interior target ≈ 48 × 40 × 14 mm; exact numbers derive from the parameter
block (board dims + clearances), not hardcoded magic values.

## Parameters (Fusion user parameters)

`wall`, `windowT`, `boardClear` (0.25 mm), `usbClear` (0.4 mm), snap clip
dimensions/engagement (FDM-tolerant), `tapeRecess`, fillet radii — created
via the API as named user parameters with expressions, editable in Fusion's
Change Parameters dialog. Sketches/features reference the parameters, not
literal numbers, wherever the API reasonably allows.

## Verification (scripted in Fusion, before anything is printed)

The build imports the user's actual board STEP models into the design
(reference components, positioned) and checks:
1. **No interference:** boolean intersection of each board with each case part
   has (near-)zero volume.
2. **USB alignment:** the XIAO's USB-C connector solid projects through the
   shell cutout with clearance on all sides.
3. **Window coverage:** the thinned panel fully covers the radar patch end
   (top ~20 mm of the stick) with margin.
4. **Assembly sanity:** back plate rim fits inside shell cavity with the
   design gap; combined bounding box reported.
Interference via Fusion's own interference analysis / measure API; visual
verification via the MCP screenshot query (front/back/open views) — and the
user watches the model appear live in their own Fusion window.

## Deliverables

- The design itself: a new Fusion document built live in the user's Fusion
  (components: BackPlate, FrontShell, plus the two imported board models),
  with user parameters. The user saves it to their own hub/project.
- Committed under `case/` in the repo:
  - `case/fusion_scripts/*.py` — the numbered MCP build scripts (rerunnable
    record of how the design was constructed).
  - `case/rd03d_case_back.stl`, `case/rd03d_case_shell.stl` — exported from
    Fusion via the API, print-ready.
  - `case/README.md` — print settings (PLA/PETG, 0.2 mm layers, no supports,
    shell printed opening-up), assembly/wiring note, which user parameters to
    tweak for fit.

## Print Assumptions

FDM, PLA or PETG, 0.4 mm nozzle, 0.2 mm layers, no supports for either part.
Snap clips oriented so layer lines don't peel (clips print vertically as part
of the shell walls).

## Out of Scope

- Keyhole/screw mounting variants, light pipes, button access (device is
  OTA-updated; physical access = unclip the lid).
- CadQuery/OpenSCAD sources (superseded by the native build).
- A second-node case variant (same design reprints as-is).
- Cloud-saving the document for the user (they save into their own project).
