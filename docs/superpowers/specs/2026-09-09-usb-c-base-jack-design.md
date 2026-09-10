# USB-C Base Jack, Capacitor Cradle and Wire Routing — Design

**Date:** 2026-09-09
**Applies to:** the live Fusion 360 document `rd-03d_case`, built by
`case/fusion_scripts/02_backplate.py` and `03_shell.py` via the MCP driver.
**Supersedes:** the shell's side USB notch (deleted here) and the XIAO clip
finger geometry set on 2026-09-08.

## Goal

Power the node through a USB-C jack in the back plate — the LEGO-mount face —
instead of through the XIAO's own connector, give the user's 100 uF bulk
capacitor a defined home, and route both to the XIAO's 5V/GND pads. Delete the
shell's side USB notch, which the base jack replaces entirely.

## Measured inputs

**Jack** (user's part, calipers, 2026-09-09):

| dimension | value |
|---|---|
| overall length | 14.42 mm |
| metal shell length | 10.58 mm |
| PCB tail length | 5.50 mm (overlaps the shell by 1.66 mm) |
| widest section (PCB) | 9.08 mm |
| thickness | 3.17 mm |

The PCB tail therefore begins 8.92 mm back from the mouth. With the mouth flush
at the back face (z = -8) the tail's leading edge is at z = +0.92 — **above the
interior floor**, so the plate's through-slot only ever contains the metal
shell. Solder pads are on the tail's outer face at its far end.

**Capacitor:** 100 uF electrolytic, 12.0 mm tall, 8.2 mm diameter, radial
leads from one end.

**XIAO 5V/GND:** user-confirmed on the same long edge as D7, at the end nearest
the XIAO's own USB-C — i.e. the **+X end** of one long edge. The standard
top-view pinout puts that edge at **-Y** in case coordinates (x 14…18,
y -8.89, z 4.2). The design does not depend on this: the fence notch is cut in
**both** ±Y walls, so a mirrored board costs nothing.

## Decision: through-slot with an internal seating ramp

The user selected "Option B" (jack fully recessed, captured against a plate
shelf) before the part was measured. **B does not survive the measurements** and
is not what is built here:

- B's advertised strength — the plate shelf taking pull-out load — does not
  exist. At the mouth end this connector is a plain box with no flange. Its only
  step (shell to PCB, 8.92 mm back) faces *inward*: it resists the plug being
  pushed in, not the jack being pulled out.
- "Nothing protrudes" is geometrically impossible: the part is 14.42 mm long,
  the plate is 8 mm and the interior cavity is 14.0 mm. Any plate left between
  plug and receptacle also steals insertion depth from a 6.5 mm plug shell.

What is built instead keeps B's ledge idea but puts it on the inside, and leaves
the back face flatter than B would have (no overmold relief pocket needed,
because the mouth is flush).

## Geometry

All values in mm, in the existing document frame: plate spans x ±20.85,
y ±22.85, z -8…0; interior cavity ceiling z = 14.

### 1. Jack slot and collar (`02_backplate.py`, new step)

- **Through-slot** `usbJackW + usbJackClear` x `usbJackT + usbJackClear`
  = **9.33 x 3.42**, z -8…0, centred at **(x 13.6, y -19.0)**.
  Long axis along X. 0.5 mm chamfer on the back face so the plug finds it.
- **Collar**: closed four-wall box, 1.5 mm walls, interior matching the slot,
  z 0…4.5. Outer extent x 7.435…19.765, y -22.21…-15.79.
- **Seating ramps**: on both ±Y collar walls, a 45° ramp rising inward 0.8 mm
  from **z = 2.58** (= `usbShellL - backT`) to z = 3.38. The shell's rear edge
  wedges symmetrically into the pair and stops there. Above the ramps a
  **1.82 mm** channel guides the PCB tail.
- The tail's far end lands at z = 6.42, clear above the 4.5 mm collar, so the
  pads stay reachable with an iron after the jack is seated.

Why ramps rather than a flat ledge: they self-centre, they print without an
unsupported horizontal overhang, and because USB-C is reversible they work
whichever face the PCB tail is flush with — a dimension not measured and not
needed.

**Pull-out retention is adhesive.** Two dabs of epoxy in the collar. There is no
printed alternative: the part presents no rearward-facing surface to catch. The
load is the plug's own latch force on unplug (order 10 N) spread over ~40 mm² of
glued wall, so this is adequate, not marginal — but it is glue, and the README
must say so.

**Clearances:** 1.09 mm from the collar to the +X plate edge, 0.64 mm to the
-Y edge, 2.09 mm of solid plate between the slot and the nearest rear LEGO
counterbore. The ±X snap pockets (y ±12) are untouched — they are on the X
edges only, so both Y bands are free.

### 2. Capacitor cradle (`02_backplate.py`, new step)

Laid on its side in the **+Y band**, which is otherwise empty. Standing it was
rejected: 12 mm in a 14 mm cavity, leads pointing at the lid, and a footprint
that only fits the -Y band by ~0.1 mm alongside the jack.

- Two C-clip saddle ribs, **1.2 mm** thick, inner radius 4.3 (= `capDia/2` +
  `capClear/2`), outer radius 5.5, at **x 3.0 and x 12.5**.
- Cap axis at **y +16.75, z 5.5**; body occupies x 1.5…13.5, y 12.65…20.85,
  z 1.4…9.6. Ribs span y 11.25…22.25 — 0.6 mm clear of both the XIAO fence
  and the plate edge.
- Top opening 7.0 mm so the cap snaps down past the equator (0.6 mm deflection
  per arm). No lid boss required.
- Rib positions are chosen to clear the +Y clip trenches at x 4.5…11.5.
- Lead end faces **+X**.

### 3. Wire routing

- **Jack to XIAO:** ~10 mm within the -Y band. A **3.5 mm wide x 2.5 mm deep
  notch** is cut in the -Y fence wall at **x 14.5…18.0**, directly outboard of
  the 5V/GND pads, so the pair drops straight down instead of being pinched
  between the board edge and the wall. Clear of the XIAO clip at x 4.5…11.5.
  The same notch is cut in the **+Y** wall for symmetry and as insurance
  against the pads being on that edge.
- **Capacitor to the 5V rail:** the XIAO fence is open on **+X**, giving a
  full-height channel at x 19.3…20.85 from the +Y band into the -Y band. The
  cap's leads run +X and round that corner. No new feature needed.
- The junction may be made at the jack pads or at the XIAO pads; the case
  supports either.

### 4. Shell USB notch deleted (`03_shell.py`)

Remove step 4 (the notch cut through the +X wall) and step 6d (the notch
edge-softening pass). The step-6 edge-count guard expects the notch to split the
+X segment at `z_back` into 9 edges; that becomes **8**. `usbClear` joins
`tapeRecess` as a dead user parameter — both are left in place rather than
re-running `01_setup.py`, which resets user-tuned values.

Consequence, to be recorded in the README: **the XIAO's USB-C is no longer
reachable with the case closed.** Serial console and USB reflash require
unclipping the lid. OTA remains the normal update path.

### 5. Interior LEGO counterbores deleted (`02_backplate.py`, step 7)

The 6.4 x 0.9 counterbores on the **front (interior)** face are removed; the
rear ones are unchanged. A Technic pin is only ever inserted from the back, so
the interior counterbores serve nothing and their recesses fall where printed
features want flat floor. Result: one flat interior floor.

### 6. XIAO clips — 1.5 mm fingers on a longer lever (`02_backplate.py`, 8b)

The finger goes to **1.5 mm**, the fence wall's own thickness, so the `thin=`
shave disappears. A 1.0 mm wall is not reliably printable on the user's 0.6 mm
nozzle.

At the current 4.30 mm lever a 1.5 mm finger at 0.34 mm grab reaches **4.1%**
strain, which is at PETG's yield. The fix is a longer lever, **not** a smaller
lip: at 0.6 mm the nozzle resolves 0.6 and 1.2 cleanly, so a reduced 0.51 mm lip
would print worse than the 0.60 mm already there.

- **Trenches:** 1.2 mm wide x 1.5 mm deep, one either side of each finger,
  spanning x 4.5…11.5 — inboard at y ±7.95…±9.15, outboard at y ±10.65…±11.85,
  z -1.5…0.
- **Slots:** the two end slots extend down from the finger top to **z = -1.5**
  (was 0.0), so the blade below the floor is free on all four sides and rooted
  only at z = -1.5.
- **Lip and grab unchanged:** 0.60 mm projection, 0.34 mm grab per side.

| | before | after |
|---|---|---|
| finger thickness | 1.0 mm | 1.5 mm |
| lever | 4.30 mm | 5.80 mm |
| lip / grab | 0.60 / 0.34 mm | unchanged |
| peak strain | 2.8% | 2.3% |
| retention force | 1x | 1.4x |

The cantilever model is conservative: the blade is also restrained along its
root line, so real strain is slightly lower and force slightly higher.

Trench placement is checked clear of the snap pockets (±X edges, z -1.7…-0.3)
and of every LEGO hole — the x 8.95 column carries holes only at y ±4, and the
x 0.95 column lies outside x 4.5…11.5.

## New Fusion user parameters

Added by `02_backplate.py` itself via `des.userParameters.add`, **not** by
`01_setup.py`, which must not be run or edited.

| name | value | meaning |
|---|---|---|
| `usbJackW` | 9.08 mm | jack widest section (PCB) |
| `usbJackT` | 3.17 mm | jack thickness |
| `usbJackL` | 14.42 mm | jack overall length |
| `usbShellL` | 10.58 mm | metal shell length; sets the ramp height |
| `usbJackClear` | 0.25 mm | total slot clearance (0.125/side) |
| `capDia` | 8.2 mm | capacitor diameter |
| `capLen` | 12.0 mm | capacitor body length |
| `capClear` | 0.4 mm | total cradle clearance |

## Printability

User prints **PETG on a 0.6 mm nozzle**. Every new wall is 1.2 or 1.5 mm — two
clean extrusions or two at 0.75. The seating ramps *add* material (1.5 to
2.3 mm) rather than thinning anything. Slot, fence notches and clip trenches are
voids, where 1.2 mm is comfortable. The only sub-1.2 mm feature in the design is
the **0.60 mm clip lip**, which is exactly one extrusion and is deliberate.

## Verification

Scripted, before anything is printed:

1. **Interference:** a proxy solid of the jack (14.42 x 9.08 x 3.17 with the
   shell/tail step) positioned mouth-flush, and a 8.2 x 12.0 cylinder at the cap
   axis, each intersected with the plate and with the shell — all must give
   zero volume.
2. **Probe:** measure and assert slot cross-section, ramp start z = 2.58, collar
   outer extents, trench depth -1.5, slot z0 -1.5, lip projection 0.60.
3. **Body counts** after every join/cut, with explicit `participantBodies` on
   every boolean (the all-body-participation trap that consumed the BackPlate
   once already).
4. **Shell:** exactly one body; the +X wall is continuous, 8 edges at `z_back`.
5. **Export** both STLs; report bounding boxes and triangle counts, and confirm
   the shell's bbox lost the notch.

Physical acceptance is the user's: print, seat the jack, check the plug bottoms
out and the ramps stop it; snap the cap in; clip the XIAO in and confirm the
1.5 mm fingers still snap by hand.

## Deliverables

- `case/fusion_scripts/02_backplate.py` — jack slot + collar + ramps, cap
  cradle, ±Y fence notches, interior counterbores deleted, XIAO clip rework.
- `case/fusion_scripts/03_shell.py` — USB notch and its edge-softening removed,
  edge-count guard corrected.
- `case/rd03d_case_back.stl`, `case/rd03d_case_shell.stl` — re-exported.
- `case/README.md` — jack assembly order (solder tail first, seat from inside,
  epoxy), the 5.1 kOhm CC pulldown reminder, cap orientation, wire routes, and
  the note that closing the case now blocks the XIAO's USB-C.

## Risks and assumptions

- **Plug overmold size is assumed 12.4 x 6.8 mm.** At the specified slot centre
  it clears the LEGO hole at (8.95, -12) by ~0.4 mm. An overmold 14 mm or wider
  will foul a ball joint in that hole; use a plain pin there, or a right-angle
  plug.
- **PCB tail thickness was not measured.** The 1.82 mm channel above the ramps
  accepts anything from 0.8 to 1.8 mm, so it does not need to be.
- **Pull-out retention is glue**, by necessity, not choice.
- Fusion API length unit is **cm**; the scripts use the existing `MM = 0.1`
  convention.

## Out of scope

- The 5.1 kOhm CC1/CC2 pulldowns — the user is fitting these to the jack's pads.
- Any change to `01_setup.py`, or renaming `xiaoW`/`xiaoH`.
- The deferred slim in-line case variant.
- Firmware changes; a second sensor node.
