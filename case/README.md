# RD-03D + XIAO ESP32-C6 Case

Two-part snap-fit case designed natively in Fusion 360 (built via its MCP
API — the numbered scripts in `fusion_scripts/` are the construction record).
The living design is in your Fusion; save it to your own project.

## Parts

- `rd03d_case_back.stl` — back plate (8 mm thick): radar bay left, XIAO
  posts right, with five snap retention clips (three on the radar's
  ±X fence walls, one on each of the XIAO's ±Y walls);
  six LEGO Technic pin holes (8 mm pitch, counterbored on the **rear face
  only**) through the back for pin/ball-pin mounting; and a **USB-C power
  jack**, with a capacitor cradle and wire notches inside. Apart from the
  jack's mouth — which sits flush in it — the rear face is flat (great
  first layer; tape sticks directly to it), and so is the interior floor,
  which carries no counterbores. The plate's own back perimeter is square;
  only the wing's outer back edges (below) carry a 0.8 mm fillet.
  Since 2026-10-25 the plate also carries the **PIR socket**, on a
  **wing**: a 6 mm tab (z −8..−2, the same back face as the plate) growing
  out of the plate's +X edge (the end that hangs down) to x 48.97, 27.2 mm
  wide, sized to sit inside the shell's pod box (next item) with the
  measured fit allowance (see Fit, under Tweaking fit). On it stands a
  plain cylindrical **socket boss**, Ø15.4
  outside with a Ø11.1 bore straight along the case's Z axis, centred at
  x 35.5 (`pirCx`), rising to z 14.0 — 2 mm under the shell's face. It is
  for a Panasonic EKMC1603111 PaPIRs with the long-distance lens. The
  sensor drops in from the **front**, dome out: its neck and Ø11 base go
  down the bore and the underside of its flange (Ø18.8) lands on the
  boss's top rim; the lens's two latch hooks hang outside the boss.
  A 1 mm concave fillet at the boss's foot ties it into the wing. The
  PIR's axis is **parallel to the radar's** (`pirTilt` 0): the user wants
  the two fields to overlap as much as they can, and the case already
  hangs on a ball joint aimed at the stairs. The bore is **blind**: it
  stops at the wing's top (z −2), 1.1 mm below the decoupling cap that
  stands on the sensor's pins, so the back face is solid there — nothing
  goes in from the back any more (the 9c plug and its keeper pin are
  gone; the snug bore and the bezel ring hold the sensor, see below). A level Ø3
  wire hole leaves the bore's −X side at z 4 (pin-tip level) through the
  boss wall into the pod cavity; the three wires then run over the wing
  straight into the XIAO bay, with no wall in the way. The lid's +X snap
  pair engages the **wing**: a blind pocket in each of the wing's ±Y
  faces (6.2 × 1.4 mm, 0.72 deep, centred x 40, z −5) takes a bump on
  the box's inner wall; the plate's own +X edge is plain. Two more Technic
  holes, at (24.95, ±4) on the same 8 mm grid, go **through** the wing
  from the back with the same counterbore (a pin stands 2 mm proud into
  the empty pod cavity); with the original six that is eight mount
  points.
- `rd03d_case_shell.stl` — front shell: a radome step that brings the
  front wall down to 1.2 mm in front of the antennas (solid 3.1 mm of
  plastic there, exterior face still perfectly flat), a hold-down boss
  over the XIAO, four snap bumps engage the plate's edge grooves. The old
  side USB notch is **gone** — see the USB-C base jack section below.
  Since 2026-10-25 the shell carries the **PIR pod box**: its +X wall is
  replaced, over y ±13.5, by a hollow box 30 mm long (x 21..51), 31 mm
  wide (y ±15.5), full height, with the same 2 mm walls, open to the
  shell's cavity so the wing passes through and the wires run straight
  to the boards. Its top is the shell's flat front face carried on, with
  a **Ø23.3 hole** at the socket's axis: the lens ring (Ø20.6) and its
  latch tabs (Ø22) pass through, the ring's top face sits **flush with
  the face**, the dome stands 11 mm proud, and the bezel ring (next
  item) fills the gap between the hole and the lens. The lid's +X snaps
  are two bumps on the box's inner ±Y walls (0.5 proud, 6 long at x 40,
  z −5) that click into the wing's pockets; the −X pair stays on the −X
  wall at y ±12. The box's outer edges get the same rounding as the rest
  of the shell. (The pod lived on this wall as a tilted tower from
  2026-10-11, and on the plate's wing as a tilted tower for most of
  2026-10-25; the straight socket-in-a-box layout came from the test
  print: the plate holds the sensor, the shell covers it, the shell lifts
  off clean, and nothing needs supports. The ring came from the second
  print: the user wanted the gap round the lens closed and the back-side
  plug gone; a bayonet bezel clamping the dome was designed and dropped
  the same day for this simpler part.)
- `rd03d_pir_bezel.stl` — the PIR **bezel ring**: a thin ring dropped
  into the lens gap from the front. A flat flange (Ø20.8 inside, Ø25
  outside, 1.5 thick, its top continuous, with a 0.5 mm chamfer on its
  outer top edge and a 0.3 mm round on the inner one) lies on the
  shell's face round the hole, and two arc **skirts** under it
  (Ø20.8..23.6, 1.4 mm wall, 2 mm tall, the top's thickness) fill the
  Ø23.3 hole down to its underside. Two **notches** 180° apart, 6 mm wide, cut through the
  skirt and continue into the flange's underside as blind 0.4 mm relief
  pockets (out to r 11.45, hidden under 1.1 mm of solid flange) so the
  lens's two
  latch tabs (5 mm wide, at 45° and 225° round the lens, reaching the
  face) sit in them with nothing showing on top. The skirt's outside is
  Ø23.6 for the Ø23.3 hole on purpose: the first ring, made the hole's
  size, printed Ø22.79 (0.5 under — a thin two-perimeter ring shrinks
  more than a wall) in a hole that printed Ø23.2, and was loose; Ø23.6
  should print about 23.1 for a light press fit. Inside, its bore (an inside
  surface, prints true) is 0.10 off the lens ring and 0.05 off the
  dome's flank, so it just grips the lens. It closes the gap and holds
  the lens ring by friction; the snug Ø11.1 socket holds the base. Nothing clamps
  the sensor along its axis — on a wall mount the axis is horizontal and
  nothing pulls it out (the user's call). To remove it, lift the flange
  with a fingernail.

## Printing

**PETG preferred** — the five retention clips are live springs and PLA is
brittle enough to snap one on the first insertion. 0.4–0.6 mm nozzle,
0.2 mm layers. **No supports** on the plate or the shell: the socket
boss is a plain vertical tube on the wing, the bore is a blind vertical
hole, and the shell's pod box (printed face-down with the rest of the
shell) is walls plus a flat top with a hole and three small cut-outs.
The one small horizontal hole in the plate, the Ø3 wire hole out of the
boss's side, prints on its side and may close up a little; run a 3 mm
drill through it if the wires are snug. The two wing Technic holes go
right through the 6 mm wing, nothing to bridge. The socket boss is a
16 mm tall Ø15.4 post with a Ø11.1 bore, so its wall is 2.15 mm — three
perimeters on a 0.6 mm nozzle; print the plate with at least three
walls so it comes out solid, and do not scale the plate.
Back plate: print flat (back face down). Shell: print open-side-up.
Bezel ring: print it **flange-down**, no supports — it is a flat 1.5 mm
ring with two 2 mm arcs standing on it, 3.5 mm tall in all, nothing
overhangs; the two 0.4 mm tab pockets are two-layer recesses in the
bed-side face. The skirt arcs are 1.4 mm thick: two 0.6 mm lines plus
a little gap fill on a 0.6 nozzle, three and a half on a 0.4. Slow
outer perimeters; the flange's top face is the one you see.
Print the **shell at high or solid infill** (≥50 %, ideally 100 % over the
front wall): the 3.1 mm radome in front of the antennas should be
homogeneous plastic — sparse infill puts a patchwork of air pockets in the
radar's beam path and scatters it unpredictably.
Exterior edges are filleted/chamfered for comfort; the front face's 1 mm
chamfer runs round the whole outline, pod box included, and prints
cleanly bed-side. The plate's wing gets the same treatment (2.5 mm
fillets on its two outer corners, 0.8 mm fillet on its back rim); the
plate's own back edges stay sharp for the flat first layer, and the
socket boss keeps every edge sharp because the flange seats on its rim.

## Assembly

Fit the USB-C power jack **first** — see the next section. It goes in from
the **back face**, tail first, and it is soldered *after* it is seated, so
you want the empty bay to work in: doing it after the boards are clipped
down means holding an iron over them.

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
   - XIAO clips: 0.34 mm of grab per side, on the ±Y fence walls, and as
     of **2026-09-10 these have no relief slots and no root trenches
     either** — the wall is continuous. The first printed version *was*
     slotted, with a 1.2 mm trench either side sinking the cantilever
     root below the floor, all to keep bending strain low on a short
     lever. It held the board far too weakly in the hand ("very wimpy"),
     so the slots and trenches came out. What is left is a 7 mm stretch
     of the plain 1.5 mm fence wall, raised locally to 5.6 mm, carrying
     the same 0.60 mm lip with its underside 0.10 mm above the board.
     Anchored along its whole base and continuous with the wall either
     side, it is far stiffer than the old isolated finger and holds much
     harder. **The trade is insertion force** — expect a firm push to
     click the XIAO in, and use a fingernail or a spudger on the lip to
     get it out. The rock-one-edge-in tip above matters more here than
     anywhere else. The 7 × 7 mm boss on the inside of the shell's front
     wall, which comes down onto the XIAO's RF shield can, still backs
     them up once the lid is on.
   The radar lands on two crossbars that bear on the bare PCB, in the two
   component-free bands across the board's back — its 5-pin connector
   hangs free in the space between them, so don't force the board down
   onto anything.
2. PIR sensor, into the plate's socket, **before the shell goes on** so
   you can see the wires land:
   - Drop the sensor into the socket from the front, dome out, at any
     rotation. The neck and base slide down the bore and the flange's
     underside lands on the boss's top rim; the latch hooks hang outside
     the boss. The pins and the cap soldered on them hang in the blind
     bore, 1 mm above its floor. Nothing holds it yet; it turns freely.
   - Lead the three wires out through the Ø3 hole in the boss's −X side
     (the only way out of the bore), over the wing, and onto the plate at
     the XIAO's +X end (the fence bars are 5 mm tall; the wires climb
     over the −Y one or run across the bay above the board to D1, 3V3
     and GND).
3. Drop the shell on over the sensor: the pod box comes down over the
   wing and the socket, the lens passes up through the hole until its
   ring is flush with the face, and both snap pairs click — the −X pair
   into the plate's edge grooves, the box's two bumps into the wing's
   side pockets. There is no USB notch to hook a fingernail into, so to
   get the lid back off, work a thin plastic spudger or guitar pick into
   the parting seam at a corner and walk it along until the bumps let go.
3b. Bezel ring: look at the lens — its two latch tabs stick out of the
   ring at opposite sides. Hold the bezel flange-up with its two notches
   over the tabs, drop it into the gap and press it home until the
   flange sits on the face; it is a light push fit. The sensor can still
   be turned by turning the bezel with it (the notches carry the tabs
   round), so aim it however you like. To remove, lift the flange with a
   fingernail and the ring comes out; the sensor stays in its socket.
4. Mounting: push Technic pins / ball-pins into the back holes (8 mm LEGO
   pitch: 1×4 column + 1×2 column on the plate, plus a 1×2 pair through
   the wing under the pod); a ball-and-socket arm gives adjustable aim.
   Or stick VHB tape directly to the flat back if you prefer adhesive
   mounting.

## USB-C base jack (added 2026-09-09)

Power comes in through a USB-C jack in the back plate — the LEGO-mount face.
The XIAO's own USB-C is **no longer reachable with the case closed**: the
shell's side notch is gone. Serial console and USB reflash need the lid
unclipped; OTA over WiFi is unaffected.

**Fit the CC pulldowns first.** The jack needs 5.1 kOhm from CC1 and from CC2
to GND. Without them a modern USB-C charger never enables VBUS — but a
USB-A-to-C cable works either way, because A ports always have VBUS live,
which makes this failure very confusing to diagnose.

**Assembly order — seat the jack from the BACK, and solder it afterwards.**

The jack goes in the way a plug does: from outside, through the back face.
It cannot go in from the inside, and it must not be pre-soldered.

> **Why not from inside, mouth first?** The two seating ramps narrow the
> collar bore to **1.82 mm** from z 3.38 upward, and the jack's metal shell
> is **3.17 mm** thick. Pushing the shell down through that channel means
> levering a 3.17 mm metal part against two 1.5 mm PETG collar walls — they
> break before it passes. Only the thin PCB tail fits the 1.82 mm channel,
> which is exactly what the ramps are for.

1. **Seat the jack from the back face, tail first.** The PCB tail passes up
   through the slot and out through the 1.82 mm channel between the ramps;
   the metal shell follows into the full 3.42 mm slot and wedges to a stop
   on the ramps, with the mouth flush at the back face. About 6.4 mm of the
   body then stands above the interior floor, and the tail's solder pads
   end up at z ≈ 6.42 — clear above the 4.5 mm collar, which is the whole
   reason this order works.
2. **Plug a cable in and confirm it bottoms out properly** — while the jack
   is still free to be pushed back out and re-seated.
3. **Then solder** the two supply wires to the tail's VBUS and GND pads.
   They are standing exposed above the collar, so the iron reaches them
   easily with the jack in place.
4. **Then two dabs of epoxy** in the collar. This is the only thing
   resisting pull-out — the connector has no rearward-facing surface for a
   printed feature to catch, so the ramps take the push-in load and the glue
   takes the rest.

**Capacitor.** The 100 uF electrolytic lies on its side in the two-rib cradle
in the +Y band, lead end toward +X. It snaps down past its equator; no lid
feature holds it.

**RD-03D connector cable (added 2026-09-10).** The connector sits in a pocket
sealed on three sides by the two bay walls and by crossbar A, the rib that
carries the board's rear face. Crossbar A has a 4.0 x 3.5 mm notch in its
TOP, hard against the +X wall, so the cable can get out:

1. Plug the cable in, then lay the four wires through the notch in the top of
   crossbar A, hugging the +X wall. They stay at connector height (its
   underside is z 6.70) rather than diving to the floor, and once the radar
   board is clipped down they are captured between the notch floor and the
   board's rear face, so they cannot wander.
2. Run them +Y along that wall, under the radar board (there is 10.46 mm of
   headroom), to the step-4b notch at |y| < 9.4.
3. Cross the wall there. That notch is open from z 3 to the ceiling, i.e.
   ABOVE the XIAO, whose top face is at 4.20 - so the wires land on top of
   the board and both long edges are in reach. That matters: D6 is on the +Y
   edge and D7 on the -Y edge, so a route arriving from one side would
   strand one of them.

Do this before clipping the radar board down. There is also a 2.15 mm notch
in the -Y corner of the +X wall if you would rather take 5V/GND out to the
-Y band, where the jack and capacitor already are.

**Wire routes.**

- Jack to XIAO: out of the collar and straight over the top of the -Y fence
  bar onto the 5V and GND pads. The bar tops out at z 5.00 and the pads sit
  at 4.20, so it is an 0.8 mm climb with ~9 mm of headroom to the shell.
  (There were wire notches here until 2026-09-10; they were deleted because
  the clip rework made wall continuity matter more than the 0.8 mm.)
- **Solder on the top face only, and mind the clip lips.** The lips overhang
  the board's ±Y edges by 0.34 mm with just 0.10 mm of clearance above it,
  over x 4.5..11.5. A solder joint on an edge pad in that span will foul
  one. The four pads you need are all outside it — 5V ≈ x 14.9, GND ≈ 12.4,
  D6 and D7 ≈ −0.4 — but GND clears the finger's end by under a millimetre,
  so check it before you commit to a fat joint.
- Capacitor to the 5V rail: **over a fence bar.**
  There is *no* channel round the +X end of the XIAO fence — both ±Y fence
  bars run the full width of the plate, out to the edge at x 20.85. (Only the
  *board* stops short, at x 19.23; the wall beside it does not.) So take the
  leads either **over the top of a bar** — they are 5 mm tall in a 14 mm
  cavity, leaving about 9 mm of headroom — or **through the ±Y wire notches
  and across the bay above the XIAO**. Join at the jack pads or at the XIAO
  pads, whichever is tidier.

**Plug clearance.** The constraint is the plug overmold's **thickness** — its
short dimension, which runs along **Y**, across the slot's short axis. The
slot is centred at y −19.0 and the shell's skirt puts an inner rim face at
y −23.0 (at z −8), so an overmold thicker than about **8 mm** cannot reach the
mouth. The overmold's *width* runs along the slot's long axis (X) and is
unconstrained. Measure the plug **across its thin dimension**, not its wide
one, and if it is over ~8 mm use a right-angle or slim plug.
(There is no LEGO hole at (8.95, −12) — the x 8.95 column carries holes only
at y ±4. The six centres are (0.95, ±12), (0.95, ±4) and (8.95, ±4).)

## Tweaking fit

Open the design in Fusion → Modify → Change Parameters. `boardClear`,
the three fit allowances below, and `snapBump` are the fit-critical ones
(`wingSnapX` 40 and
`wingSnapZ` −5 place the +X snap pair on the wing: keep the 6 mm bump
between the plate's edge and the wing's corner fillets, and the pocket
with a millimetre of wing above and below it); `legoHole` is the
Technic pin hole diameter (tune ±0.1 mm if pins are too tight/loose after
a test print).

**Fit.** Calipers on the 9c print (2026-10-25), model → measured: plate
outside X 41.7 → 41.53 (0.17 under); plate outside Y 45.7 → 45.43 (0.27
under); shell cavity inside X 42.0 → 41.98 (true); cavity inside Y 46.0
→ 46.34 (0.34 over); wing width 26.7 → 26.46 (0.24 under); box cavity
width 27.0 → 27.2 (0.2 over). So on this printer outside walls print
0.17..0.27 under, and cavities print true in X but 0.2..0.34 over in Y
(the long walls bow out). The printed gaps were 0.45 total in X, 0.91 in
Y and 0.74 wing-to-box; the target is 0.2 total, 0.1 a side, a light
push fit. The old single `rimGap` (0.15 a side) is superseded by three
allowances, each the per-side model gap that lands the print at 0.1 a
side, (0.2 − outside shrink − cavity growth) / 2: `rimGapX` 0.03 (plate
half-width = `intW`/2 − `rimGapX`), `rimGapY` −0.05 (plate half-length =
`intH`/2 − `rimGapY`: negative, the model's plate sits 0.05 a side into
the shell's long walls and the print takes it back), `wingGap` −0.12
(wing half-width = `pirBoxHalfY` − `wingGap`). `rimGapY` was −0.20 after
the first print; the reprint of 2026-10-26 came out 46.10 long for 46.40
modelled (plate Y prints 0.30 under) against a cavity that measures
46.00 on this shell (the 46.34 was another shell or spot), 0.1 too long
and needing force, so the target printed 45.80 → modelled 46.10 →
−0.05. X and the wing were reported good and stay. `91_pir_fit.py`
expects the model's plate/shell overlap (about 60 mm³ now) as a designed
pair, and the bezel skirt's press overlap in the hole as another. If
your printer behaves differently, measure the same six things and set
the three allowances from the formula. The radar bay follows the same
rule: its fence walls' inner faces measured 15.68 apart for 15.60
modelled (`radarW` 15.1 + 2 × `boardClear` 0.25; this cavity printed
+0.08) while the RD-03D PCB is 15.09 wide, so the board had 0.6 mm of
side play and the clip lips (0.85 mm, printing about 0.65) barely
caught its edge. The bay now uses its own `radarClear` 0.10 a side
(15.30 modelled, about 15.38 printed, 0.15 a side on the board, lips
0.75 over the edge nominal); the XIAO bay keeps `boardClear`. Rule:
0.1 a side on a measured part. The sensor's socket follows the same rule: the sensor's metal base measured Ø10.8 with calipers (the
STEP says 11.0) and the printed Ø11.8 bore measured 11.8 (holes print
true), 0.5 mm of play; `pirBoreR` is now 5.55 (Ø11.1), 0.15 a side on
the measured base. Holes print true to size, so size holes 0.1..0.2 a
side over the part they take; outside walls print 0.2 under.
The bezel ring: its skirt's outside is `pirBezelSkirtRo` (11.80, 0.15
a side over the `pirHoleR` 11.65 hole, because the printed ring came
out 0.5 under on the diameter); if it is still loose, up 0.05; if it
will not go in, down 0.05. Its bore is `pirBezelInnerR` (10.40: lens ring 10.3 +
0.10, dome flank 10.35 + 0.05; it prints true, so the ring just grips
the lens); the notches are `pirNotchW` = `pirTabW` + 1 (the tabs measured
5.0 wide on the STEP). No
metal or foil in front of the radar, ever.
The retention clips and the radome step are local constants inside
`fusion_scripts/02_backplate.py` and `03_shell.py` (grab amounts, lip
heights, `RADOME_Z0`), not user parameters — edit them there and re-run
those two scripts.
The eight `usbJack*` / `cap*` parameters are created by `02_backplate.py`,
not by `01_setup.py`, so they only exist once that script has run.
Re-export STLs after edits (File → 3D Print, or re-run
`fusion_scripts/05_export.py` via `run_fusion.py`).
The `pir*` parameters (socket bore and boss radii, seat height, axis x
`pirCx`, box half-width and length, lens hole radius, wire hole, the
bezel ring's flange, skirt and notch sizes, the lens tab width,
`pirTilt`) and the `wingSnap*` pair are created by `02_backplate.py` the
same way; `03_shell.py` reads them to build its box, lens hole, wing
bumps and the bezel, so moving the socket moves the box. `pirTilt` must
stay 0: the
straight socket has no tilt and 02 refuses anything else; if it refuses
on a document that still has the old 18°, set `pirTilt` to 0 by hand in
Change Parameters and re-run. `pirCx` is
35.5 rather than the 34.5 that would centre the socket in the box,
because at 34.5 the Technic hole at (24.95, 4) passes 0.2 mm from the
boss's foot; at 35.5 it is 1.13 mm clear. The radii come from
point-probing Panasonic's STEP of the sensor (base r 5.5, flange r 9.4,
hook lips r 9.6..10.7, latch tabs r 11.1), not from its datasheet
drawing, with 0.3–0.4 mm of clearance on each.
`fusion_scripts/90_verify.py` is a read-only probe harness that asserts the
fit allowances, the jack, cradle, notches, clips, the shell's pod box and
lens hole, both snap pairs, the PIR socket (wing, boss, blind bore, wire
hole, the two wing Technic holes) and the bezel ring's own geometry with
`pointContainment`; run it after any change and expect `VERIFY OK`.
`fusion_scripts/91_pir_fit.py` imports the sensor's STEP (a local vendor
download under `case/models/`, not in the repo), drops it upright into
the plate's socket with its ring flush with the shell's face, checks the
bezel ring sits in the gap with the tabs in its notches and prints its
clearance to the lens, and runs Fusion's interference analysis against
the plate, the shell and the bezel; expect `PIR FIT OK` (one expected
pair: the plate against the shell, the designed fit-allowance overlap of
about 180 mm³ that the print's shrink takes back; the bezel must touch
nothing).

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
- **Retention clips (2026-09-08, revised 2026-09-09 and 2026-09-10).**
  Each lip's flat
  underside sits 0.10 mm above its board's face (radar 11.80 vs 11.70;
  XIAO 4.30 vs 4.20), so the clips do not preload the boards at rest —
  they only bear if a board tries to lift. That float is deliberate: a
  permanently strained PETG finger would creep. Radar clips are three
  7 mm lip bands on the full-thickness (1.5 mm) fence walls, tops at
  12.50 (−X, under the shell's 14.00 IC band) and 12.30 (both +X, under
  the 12.90 radome zones); the two XIAO clips are the same idea at 7 mm
  wide on the ±Y walls, with a 0.34 mm grab rather than 0.60 mm because
  their board edge is only 4.2 mm up. All five are now lip bands on
  continuous walls — no slots, no trenches anywhere (see below).
  Insertion deflection is ~0.6 mm (radar) and ~0.34 mm (XIAO). Each lip's
  0.6–0.85 mm flat underside is a small unsupported overhang printing
  back-face-down; that is expected and bridges fine at 0.2 mm layers.
  PETG still matters: these are stiff walls being flexed, and PLA is
  brittle enough to crack one.
- **Why the radar clips have no relief slots (2026-09-09).** The radar lip
  is 11.8 mm above the plate. Treating the 1.5 mm wall as a cantilever of
  that length, the 0.6 mm of tip deflection needed to clear the board edge
  works out at ≈1 % peak surface strain — a quarter of PETG's yield — for
  of order 12 N at the lip. So the wall flexes enough unaided, and the
  slots that used to isolate each finger were pure cost: they cut into the
  wall that restrains the radar board sideways. Removing them also freed
  the budget for a third clip.
- **The XIAO clips lost their slots and trenches too (2026-09-10) — the
  one change here driven by a printed part rather than a calculation.**
  Through 2026-09-09 the XIAO clips kept 0.7 mm relief slots at each end
  of the finger and a 1.2 × 1.5 mm trench either side that dropped the
  cantilever root to z = −1.5, lengthening the lever from 4.30 to 5.80 mm
  and holding peak bending strain to ≈2.3 %. The reasoning was sound and
  the arithmetic was right, and it optimised for the wrong thing: the
  printed clips were *very wimpy — barely holding the board in*. Strain
  was never the binding constraint; retention was.

  Slots and trenches are gone. Each XIAO clip is now a 7 mm stretch
  (x 4.5…11.5) of the continuous 1.5 mm fence wall, raised locally to
  5.6 mm, carrying the same 0.60 mm lip with its flat underside at
  z 4.30 — 0.10 mm over the XIAO's 4.20 mm top face — for 0.34 mm of grab
  per side. The lip is deliberately unchanged; the user declined a lip
  change, and 0.6 mm is what a 0.6 mm nozzle resolves cleanly anyway.

  No strain or force figure is quoted for the new arrangement, on purpose.
  The old numbers modelled an isolated end-loaded cantilever; this wall is
  anchored along its entire base and continuous with its neighbours out to
  the plate edge, which is a different problem, and any figure put on it
  here would be invented precision. Qualitatively it is much stiffer and
  holds much better, **and the trade is insertion force** — it takes a
  firm push to seat the board and a fingernail or spudger to release it.
- **Keeping the six Technic bores usable (2026-09-09, final review).** Two
  separate features had crept over the LEGO holes at (0.95, ±12), both while
  the *stated* clearance check only looked at the clip trenches:
  - The capacitor cradle's ribs were at x 3.0 and 12.8. The x = 3.0 rib
    (footprint x 2.40…3.60) sat over the bore, which reaches x 3.40 — a
    1.00 mm overlap across 3.20 mm of y, roofing about 11 % of that bore's
    interior mouth for the rib's full 8 mm height. A Technic pin pushed in
    from the back would have bottomed out on it, and you would only have
    found out after printing. The ribs moved to **x 5.0 and 14.8** — same
    9.8 mm span, so the capacitor sits identically (just centred at x 9.9
    instead of 7.9) — putting the rib edge 1.00 mm clear of the bore.
  - The XIAO clip slots, once they were taken down to z = −1.5, passed
    within **0.431 mm** of the same bore — thinner than a 0.6 mm nozzle can
    lay down, so the slicer would simply have dropped the web. They were
    narrowed from 1.0 mm to 0.7 mm to restore a 0.70 mm web. *(Moot since
    2026-09-10: the slots are gone entirely, and with them this hazard. The
    lesson is not moot — any future feature taken below z = 0 near x 3…4,
    y ±10…12 has to be checked against these bores on its own, not by
    inheriting some other feature's clearance.)*

  The `x = 5.0` rib no longer overlaps anything below the floor either,
  since the trench it used to cross in plan was deleted with the slots.
  `90_verify.py` probes all six bores (centre **and** ±1.5 mm in x, at
  z = 0.5) so nothing can roof one again.
- **Interior LEGO counterbores deleted (2026-09-09).** The six Technic
  bores keep their rear counterbore and rear entry chamfer but no longer
  have one on the inside — a pin only ever enters from the back — so the
  interior floor is flat and the bays gained a little usable depth.
- Caution: re-running `fusion_scripts/01_setup.py` resets ALL user
  parameters to the repo defaults, overwriting any tuning you did in
  Fusion's Change Parameters dialog.
- If the lid snaps on too hard/soft, tune the `snapBump` user parameter
  (0.4-0.6 mm) and reprint the shell only.
