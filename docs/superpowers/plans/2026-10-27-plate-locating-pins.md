# Back plate: locating pins, end bars, wire window, rotated XIAO — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Locate the RD-03D on two pins in its own PCB corner notches, carry it on bars under its ends, route its cable through a floor window, turn the XIAO 180°, and drop the shell's retention ribs, with the probe harness proving each piece before export.

**Architecture:** Every case part is rebuilt by a Python script run against the live Fusion 360 document (`run_fusion.py script <file>`); the scripts are the source of truth and the STLs are exports. `90_verify.py` is the test suite: point-containment probes in millimetres, read-only, run after every rebuild. The order is always probes first (they fail against the old geometry), then the script change, then rebuild and probe again, then commit.

**Tech Stack:** Fusion 360 API via `case/fusion_scripts/run_fusion.py` (units cm inside scripts, `MM = 0.1`), Python 3, PIL for the wiring diagram.

**Spec:** `docs/superpowers/specs/2026-10-27-plate-locating-pins-design.md`

---

## Ground rules for every task

- Run scripts from the repo root: `python3 case/fusion_scripts/run_fusion.py script case/fusion_scripts/<file> [--read-only]`. Fusion must be open on the `rd-03d_case` document. Never run or edit `01_setup.py`. Never save, close or discard the document.
- Scripts work in centimetres; multiply millimetre values by `MM`. Every boolean passes `participants=[...]`. Read parameters before `baseFeatures.startEdit()` (the existing scripts already do; keep the pattern).
- `90_verify.py` prints `VERIFY OK` or raises with every `FAIL:` line listed. Treat it like a test run: read the failures, do not loosen a probe to make it pass unless the spec says the geometry changed.
- `02_backplate.py` prints one line per step. If a step raises, the whole rebuild fails; read the traceback from `run_fusion.py`'s output.
- Commit after each task with the no-reply author: `git -c user.name=nThanksForAllTheFish -c user.email=nThanksForAllTheFish@users.noreply.github.com commit ...`. Every commit message ends with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. Before committing, a `git grep` of `case` and `docs` for the maintainer's real name or home path must print nothing.
- Coordinates below are in the case frame (mm): X across the plate (radar bay at negative X, wing at positive X), Y along the radar's long axis, Z up from the plate's top face (floor of the cavity). The radar PCB's rear face is at z 10.46, its front at 11.76.

## File map

| File | Change |
|---|---|
| `case/fusion_scripts/90_verify.py` | probes for end bars, pins, wire window, moved clip B; crossbar/cable-exit probes removed; rib-void probes on the shell |
| `case/fusion_scripts/02_backplate.py` | step 4 end bars, step 4b full-height cut, step 5a wire window, step 6b pins, clip B span, steps 12 and 13 deleted |
| `case/fusion_scripts/03_shell.py` | steps 4b and 4c (ribs and their chamfers) deleted |
| `case/fusion_scripts/04_boards.py` | XIAO placed with `flip180=True` |
| `case/fusion_scripts/91_pir_fit.py` | run only; must still report 0 unexpected pairs |
| `case/fusion_scripts/05_export.py` | run only; STLs land in `case/` |
| `docs/wiring.png` | redrawn for the rotated XIAO |
| `docs/superpowers/plans/2026-10-27-plate-locating-pins.md` | as-built notes |

---

### Task 1: Probes for the new plate geometry (red)

**Files:**
- Modify: `case/fusion_scripts/90_verify.py` (`check_baseline`, `check_radar_bay`, `check_radar_cable_exit`, `run`)

- [ ] **Step 1: Replace the crossbar line in `check_baseline`**

In `check_baseline`, replace

```python
    solid(plate, rCx, -12.0, 1.0, "radar bay crossbar A (y -12.8..-11.2)")
    void(plate, rCx, 0, 1.0, "radar bay is open between the crossbars")
```

with

```python
    void(plate, rCx, -12.0, 1.0, "no crossbar A: the bay floor is open at y -12")
    void(plate, rCx, 18.75, 1.0, "no crossbar B: the bay floor is open at y 18.75")
    void(plate, rCx, 0, 1.0, "radar bay is open between the end bars")
```

- [ ] **Step 2: Move the clip B lip probe**

In `check_radar_bay`, the lip loop probes clip B at `y = -17.0`. Clip B moves to y −20.0..−13.0, so −17.0 is still inside it; leave the value but update the comment line above the loop to read:

```python
    # the lips: solid 0.5 past the board edge at lip height, void just under
    # the lip (the board's own space, 0.1 float) for all three clips
    # (B spans y -20.0..-13.0 since 2026-10-27; -17.0 is mid-finger)
```

- [ ] **Step 3: Replace `check_radar_cable_exit` with three new checks**

Delete the whole `check_radar_cable_exit` function and add these three in its place:

```python
def check_end_bars(plate, des):
    """Two bars carry the RD-03D under its ends (2026-10-27, replacing
    crossbars A and B): -Y bar y -22.0..-20.8, +Y bar y +20.0..+22.0, both
    full bay width from the floor to the PCB rear face (10.46)."""
    wo, wi, ei, eo, rCx = radar_walls(des)
    for y, tag in ((-21.4, "-Y"), (21.0, "+Y")):
        for x in (wi + 1.0, rCx, ei - 1.0):
            solid(plate, x, y, 5.0, "%s end bar solid at x %.2f z 5" % (tag, x))
            solid(plate, x, y, 10.3, "%s end bar reaches the PCB rear at x %.2f" % (tag, x))
            void(plate, x, y, 10.6, "%s end bar stops at the PCB rear at x %.2f" % (tag, x))
    # the -Y bar stops short of the radar's 5-pin connector (y -20.7)
    void(plate, -12.0, -20.6, 8.0, "-Y bar clear of the connector at y -20.6")
    solid(plate, -12.0, -20.9, 8.0, "-Y bar material at y -20.9")
    # the +Y bar's inboard face
    void(plate, rCx, 19.8, 8.0, "+Y bar starts at y 20.0, open at 19.8")
    solid(plate, rCx, 20.2, 8.0, "+Y bar material at y 20.2")


def check_locating_pins(plate, des):
    """Two O2.2 pins in the RD-03D's corner half-notches (2026-10-27):
    centres (-18.25, -21.40) and (-4.75, +21.30), floor to z 12.4, cut flat
    on the outboard side at |y| 22.0. Each merges into its bay wall and its
    end bar."""
    for cx, cy, tag in ((-18.25, -21.40, "-Y"), (-4.75, 21.30, "+Y")):
        sy = 1 if cy > 0 else -1
        for z in (1.0, 11.0, 12.2):
            solid(plate, cx, cy, z, "%s pin solid at its centre z %.1f" % (tag, z))
        void(plate, cx, cy, 12.6, "%s pin top is below 12.6" % tag)
        solid(plate, cx + (0.9 if cx < -10 else -0.9), cy, 11.0,
              "%s pin reaches 0.9 inboard in x (r 1.1)" % tag)
        solid(plate, cx, cy - sy * 0.9, 11.0, "%s pin reaches 0.9 inboard in y" % tag)
        void(plate, cx, cy + sy * 1.2, 11.0, "%s pin cut flat at |y| 22.0: void 1.2 outboard" % tag)
        void(plate, cx, cy + sy * 0.7, 11.0, "%s pin flat: void 0.7 outboard (|y| 22.1)" % tag)
        # nothing of the pin above the PCB front face beyond r 1.1 + chamfer
        void(plate, cx + (1.6 if cx < -10 else -1.6), cy, 12.0,
             "%s pin no wider than r 1.1 above the board" % tag)


def check_radar_wire_window(plate, des):
    """The radar cable leaves the bay at floor level (2026-10-27): the +X
    bay wall is gone over |y| < 9.4 from floor to top, the XIAO fence's -X
    wall (x -5.0..-3.5, z 0..5) stays as the XIAO's stop and has a window
    |y| < 3.5, z 0..5."""
    wo, wi, ei, eo, rCx = radar_walls(des)
    wx = (ei + eo) / 2                       # +X bay wall centre line, -3.10
    for z in (1.0, 4.0, 8.0):
        void(plate, wx, 0.0, z, "+X bay wall open at y 0 z %.1f" % z)
        void(plate, wx, 8.0, z, "+X bay wall open at y 8 z %.1f" % z)
        void(plate, wx, -8.0, z, "+X bay wall open at y -8 z %.1f" % z)
    solid(plate, wx, 15.0, 5.0, "+X bay wall intact beyond |y| 9.4 (+Y)")
    solid(plate, wx, -15.0, 5.0, "+X bay wall intact beyond |y| 9.4 (-Y)")
    # XIAO fence -X wall: kept at |y| 3.5..10.65, windowed at |y| < 3.5
    for y in (4.5, -4.5, 8.0, -8.0):
        solid(plate, -4.25, y, 2.5, "XIAO fence -X wall kept at y %.1f" % y)
        solid(plate, -4.25, y, 4.5, "XIAO fence -X wall to z 5 at y %.1f" % y)
    for y in (0.0, 2.5, -2.5):
        void(plate, -4.25, y, 0.5, "wire window open at floor, y %.1f" % y)
        void(plate, -4.25, y, 4.5, "wire window open to z 5, y %.1f" % y)
    void(plate, -4.25, 0.0, 5.5, "nothing above the fence wall at y 0")
    # the old corner cable exit is gone: wall solid at the -Y corner under clip B
    solid(plate, wx, -21.8, 5.0, "+X bay wall solid at the -Y corner (old exit closed)")
    # the lane from the window to the XIAO's -X end is clear at floor level
    void(plate, -2.0, 0.0, 1.0, "lane clear just +X of the window")
```

- [ ] **Step 4: Call the new checks from `run`**

Replace `    check_radar_cable_exit(plate, des)` in `run` with:

```python
    check_end_bars(plate, des)
    check_locating_pins(plate, des)
    check_radar_wire_window(plate, des)
```

- [ ] **Step 5: Run the probes against the current plate and confirm they fail**

Run: `python3 case/fusion_scripts/run_fusion.py script case/fusion_scripts/90_verify.py --read-only`
Expected: a RuntimeError listing failures that include `no crossbar A`, `-Y end bar solid`, `-Y pin solid at its centre`, `+X bay wall open at y 0 z 1.0`, `wire window open at floor`. Nothing else in the file should fail (the baseline, snaps, jack, cradle, pod, socket and bezel checks still pass).

- [ ] **Step 6: Commit**

```bash
git add case/fusion_scripts/90_verify.py
git commit -m "verify: probes for end bars, locating pins and the wire window (red)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: Plate script — end bars, wire opening, pins, clip B (green)

**Files:**
- Modify: `case/fusion_scripts/02_backplate.py` (step 4 crossbars, step 4b, after step 5, after step 6, step 8a clip B, steps 12 and 13)

- [ ] **Step 1: End bars replace the crossbars (step 4)**

Find the block starting `    PCB_REAR_Z = 10.46 * MM` through the `print("radar bay walls: ...")` call. Replace the `XBARS` definition and its extrude with:

```python
    PCB_REAR_Z = 10.46 * MM      # measured bare-PCB rear face of the RD-03D
    # End bars (2026-10-27, user review of the 2026-10-26 print): carry the
    # board under its ENDS, where the rear side is bare PCB across the full
    # width (probed read-only on the placed vendor body: y -22.0..-20.7 and
    # y +19.8..+22.0 bare; the 5-pin connector starts at y -20.7 and reaches
    # z 6.64 over x -15.3..-9.3). The two crossbars at y -12 and +18.75 that
    # sat between rear components are gone, and with them the crossbar A
    # cable slot (old step 13) and the corner cable exit (old step 12): the
    # connector pocket is now open to the floor and the cable leaves through
    # the floor opening in the +X wall (step 4b/5a).
    #   -Y bar y -22.0..-20.8 (1.2 wide): 0.1 clear of the connector.
    #   +Y bar y +20.0..+22.0 (2.0 wide).
    # Both run the full bay width between the walls' inner faces and tie
    # into both walls. The board's ends overhang them by 0.02 (edge 22.02).
    ENDBARS = ((-21.4 * MM, 1.2 * MM),    # -Y: y -22.0..-20.8
               (21.0 * MM, 2.0 * MM))     # +Y: y +20.0..+22.0
    sk = comp.sketches.add(comp.xYConstructionPlane)
    for cy, w in ENDBARS:
        rect(sk, rCx, cy, bayW, w)
    profs = collection([sk.profiles.item(i) for i in range(sk.profiles.count)])
    extrude(comp, profs, 0, PCB_REAR_Z,
            adsk.fusion.FeatureOperations.JoinFeatureOperation,
            participants=[plate_body])
    print("radar bay ok (X walls + end bars bearing on the PCB ends; "
          "Y-location is the corner pins' job), bar top z(mm)=",
          round(PCB_REAR_Z * 10, 3), "board total thickness radarT(mm)=",
          round(rT * 10, 2))
```

Keep the existing `print("radar bay walls: ...")` line after it. Delete the long "Board-seating fix 2026-09-07" comment block above `PCB_REAR_Z` down to and including the "since the board simply rests on whatever height the bars are." line, and replace it with the comment shown above (the bars' provenance now lives there).

- [ ] **Step 2: Full-height cut in step 4b**

Replace step 4b's comment and code with:

```python
    # 4b. open the radar fence +X wall where the XIAO sits (2026-10-27: now
    # floor to top). The XIAO's USB end faces this wall since the 180 deg
    # rotation (04_boards.py), so nothing rests on the old 3 mm stub, and
    # the radar cable leaves the bay at FLOOR level through here instead
    # of over the top. Over |y| < 9.4 the wall's only remaining job was
    # that stub; the clip B and C stretches beyond |y| 9.4 are untouched.
    # The XIAO fence's -X wall (step 5, x -5.0..-3.5, z 0..5) is built
    # after this cut and keeps the XIAO's -X stop face at x -3.5; step 5a
    # windows it for the wires.
    nx0 = rCx + bayW / 2 - 0.01
    nx1 = rCx + bayW / 2 + 1.5 * MM + 0.01
    ny = xH / 2 + clear + 0.25 * MM
    sk = comp.sketches.add(comp.xYConstructionPlane)
    rect(sk, (nx0 + nx1) / 2, 0, nx1 - nx0, 2 * ny)
    extrude(comp, sk.profiles.item(0), -0.01 * MM, 11 * MM + 0.01,
            adsk.fusion.FeatureOperations.CutFeatureOperation,
            participants=[plate_body])
    print("radar fence +X wall opened floor to top over |y| < %.1f" % (ny * 10))
```

- [ ] **Step 3: Wire window after step 5**

Immediately after step 5's `print("xiao bay ok")`, add:

```python
    # 5a. wire window (2026-10-27): the radar's 4-wire cable comes off the
    # connector, drops to the floor, runs under the board and through this
    # window in the XIAO fence's -X wall to the XIAO's -X end, where the
    # rotated board's 5V, GND, D6 and D7 pads now are. |y| < 3.5, z 0..5,
    # through the full 1.5 mm wall. Narrower than the USB-C receptacle
    # (8.9 wide) on purpose: the receptacle's shoulders stay the XIAO's -X
    # stop against the fence face at x -3.5.
    WIN_HALF_Y = 3.5 * MM
    fx0 = xCx - fW / 2 - t - 0.01            # fence outer face, -5.0
    fx1 = rCx + bayW / 2 + 1.5 * MM + 0.01   # through the old wall footprint too
    sk = comp.sketches.add(comp.xYConstructionPlane)
    box(sk, fx0, fx1, -WIN_HALF_Y, WIN_HALF_Y)
    extrude(comp, sk.profiles.item(0), -0.01 * MM, 5 * MM + 0.01,
            adsk.fusion.FeatureOperations.CutFeatureOperation,
            participants=[plate_body])
    print("wire window ok (XIAO fence -X wall, |y| < %.1f, z 0..5)" % (WIN_HALF_Y * 10))
```

`fW` and `t` are the step-5 locals (`fW = xW + 2 * clear`, `t = 1.5 * MM`); `box` is the module helper `box(sk, x0, x1, y0, y1)`.

- [ ] **Step 4: Locating pins after step 6 (they are taller than the step-6 trim)**

Immediately after step 6's `print("trimmed to plate outline")`, add:

```python
    # 6b. LOCATING PINS (2026-10-27, user review): the RD-03D has two open
    # half-notches in diagonal corners of its PCB, radius 1.14, probed on
    # the placed vendor body at (-18.25, -21.40) and (-4.75, +21.30) in the
    # case frame (the other two corners are r 1.8 roundings, not holes).
    # A pin in each locates the board in Y and rotation; X is shared with
    # the bay walls at radarClear. This retires the shell's retention ribs
    # (03_shell.py 4b/4c, deleted the same day).
    #
    # O2.2 modelled (thin pillars print ~0.2 under: ~0.15 radial play in
    # the O2.28 notch), floor to z 12.4 (0.5 under the shell's 12.9 radome
    # step), top edge chamfered 0.4 as lead-in. Each pin is a D: cut flat
    # on the outboard side at |y| 22.0, the board's end line, so it stays
    # inside the current printed shell's ribs (inner faces 22.26). The
    # inboard side merges into the bay wall (x overlap 0.2) and the end
    # bar, so only 2 mm of pin stands free above the bar.
    #
    # Built AFTER step 6 because the outline trim only keeps z -backT..11.
    PIN_R = 1.1 * MM
    PIN_TOP = 12.4 * MM
    PIN_FLAT_Y = 22.0 * MM
    PINS = ((-18.25 * MM, -21.40 * MM), (-4.75 * MM, 21.30 * MM))
    for cx, cy in PINS:
        sy = 1 if cy > 0 else -1
        sk = comp.sketches.add(comp.xYConstructionPlane)
        sk.sketchCurves.sketchCircles.addByCenterRadius(
            adsk.core.Point3D.create(cx, cy, 0), PIN_R)
        # the flat: a line across the circle at the board's end line
        sk.sketchCurves.sketchLines.addByTwoPoints(
            adsk.core.Point3D.create(cx - 1.5 * MM, sy * PIN_FLAT_Y, 0),
            adsk.core.Point3D.create(cx + 1.5 * MM, sy * PIN_FLAT_Y, 0))
        # keep the inboard (larger) profile: its centroid lies toward y=0
        best = None
        for i in range(sk.profiles.count):
            pr = sk.profiles.item(i)
            c = pr.areaProperties().centroid
            if abs(c.y) < PIN_FLAT_Y and (best is None or pr.areaProperties().area > best.areaProperties().area):
                best = pr
        if best is None:
            raise RuntimeError("pin at (%.2f, %.2f): no inboard profile" % (cx * 10, cy * 10))
        extrude(comp, best, 0, PIN_TOP,
                adsk.fusion.FeatureOperations.JoinFeatureOperation,
                participants=[plate_body])
    # lead-in chamfer on each pin's top arc (nice-to-have; a square top
    # still locates). Select arc edges at z = PIN_TOP with radius PIN_R.
    try:
        edges = adsk.core.ObjectCollection.create()
        for e in plate_body.edges:
            g = e.geometry
            if (isinstance(g, adsk.core.Arc3D)
                    and abs(g.radius - PIN_R) < 0.005
                    and abs(g.center.z - PIN_TOP) < 0.005):
                edges.add(e)
        if edges.count != 2:
            raise RuntimeError("expected 2 pin top arcs, found %d" % edges.count)
        ch = comp.features.chamferFeatures
        chi = ch.createInput(edges, False)
        chi.setToEqualDistance(adsk.core.ValueInput.createByReal(0.4 * MM))
        ch.add(chi)
        print("locating pins ok (O%.1f at %s, top z %.1f, flat at |y| %.1f, 0.4 chamfer)"
              % (PIN_R * 20, [(round(x * 10, 2), round(y * 10, 2)) for x, y in PINS],
                 PIN_TOP * 10, PIN_FLAT_Y * 10))
    except Exception as exc:
        print("locating pins ok, PIN CHAMFER SKIPPED:", exc)
```

- [ ] **Step 5: Shift clip B**

In step 8a, change clip B's finger span and its comment:

```python
    # B - +X wall under the TX radome. The -Y end bar occupies y -22.0..-20.8
    # (2026-10-27), so the band starts at -20.0 (0.8 mm clear, same rule as
    # the old 0.7 to crossbar A) and runs to -13.0; crossbar A is gone, so
    # nothing bounds it on the +Y side before the 4b opening at -9.4.
    clip(comp, plate_body, "x", RE_OUT, RE_IN,
         -20.0 * MM, -13.0 * MM,
         NO_SLOTS,
         R_SLOT_Z0, R_RAISE_Z0, R_TOP_Z_PX, R_LIP_Z, R_LIP,
         label="radar B +X")
```

Also update the paragraph above clip A that begins "The +X wall cannot carry a clip at y=0: step 4b notches it down to z=postH" to say the wall is open floor to top over |y| < 9.4 since 2026-10-27 (the rest of the reasoning stands).

- [ ] **Step 6: Delete steps 12 and 13**

Delete everything from the line `    # 12. Radar cable exit (2026-09-10).` to the end of step 13 (the `print("crossbar A cable notch ok ...")` call and its arguments). Leave a two-line marker in their place:

```python
    # 12/13. (deleted 2026-10-27) the corner cable exit and the crossbar A
    # cable slot: crossbar A is gone (step 4) and the cable leaves at floor
    # level through the step-4b opening and the step-5a window.
```

Check nothing later in the file references `XBARS`, `CABLE_Y0`, `CBL_X0` or `CBL_Z0`:

Run: `grep -n "XBARS\|CABLE_Y\|CBL_" case/fusion_scripts/02_backplate.py`
Expected: no output.

- [ ] **Step 7: Rebuild the plate**

Run: `python3 case/fusion_scripts/run_fusion.py script case/fusion_scripts/02_backplate.py`
Expected: the step prints in order, including `radar bay ok (X walls + end bars ...`, `radar fence +X wall opened floor to top over |y| < 9.4`, `wire window ok`, `locating pins ok (O2.2 at [(-18.25, -21.4), (-4.75, 21.3)], top z 12.4, flat at |y| 22.0, 0.4 chamfer)`, three `clip radar ...` lines, and the script's final OK line. If `PIN CHAMFER SKIPPED` prints, note the reason in the as-built line but continue (square tops are acceptable).

- [ ] **Step 8: Probe**

Run: `python3 case/fusion_scripts/run_fusion.py script case/fusion_scripts/90_verify.py --read-only`
Expected: `VERIFY OK`.

If a pin probe fails on `pin reaches 0.9 inboard in y`, the wrong profile was extruded (the outboard sliver): check the centroid test in step 4. If `wire window open at floor` fails, the window cut ran before the fence was built; it must come after step 5's fence extrude.

- [ ] **Step 9: Commit**

```bash
git add case/fusion_scripts/02_backplate.py
git commit -m "case: locating pins in the RD-03D's corner notches, end bars, floor-level wire window

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: Shell — delete the retention ribs

**Files:**
- Modify: `case/fusion_scripts/90_verify.py` (`check_baseline`)
- Modify: `case/fusion_scripts/03_shell.py` (steps 4b, 4c)

- [ ] **Step 1: Probe that the ribs are gone (red)**

In `check_baseline`, after `void(shell, 0, 0, 7.0, "shell interior cavity")`, add:

```python
    # the radar retention ribs are gone (2026-10-27): the corner pins on the
    # plate locate the board. Rib footprint was x -19.0..-4.0, y 22.26..23,
    # z 6..14.
    for sy in (-1, 1):
        void(shell, rCx, sy * 22.6, 10.0, "no retention rib at y %+.1f" % (sy * 22.6))
        solid(shell, rCx, sy * 24.0, 10.0, "shell +/-Y wall still there outside the old rib")
```

Run: `python3 case/fusion_scripts/run_fusion.py script case/fusion_scripts/90_verify.py --read-only`
Expected: exactly two failures, both `no retention rib at y ...`.

- [ ] **Step 2: Delete steps 4b and 4c from the shell script**

In `03_shell.py`, delete from the line `    # 4b: radar retention ribs (thin-wall fix 2026-09-07).` through the `else:  # nice-to-have; square rib is acceptable` / `print("RIB CHAMFER SKIPPED entirely")` pair, and put this in their place:

```python
    # 4b/4c. (deleted 2026-10-27) the radar retention ribs and their lead-in
    # chamfers: the board is located by two pins in its own PCB corner
    # notches on the back plate (02_backplate.py step 6b). The plate's pins
    # and end bars stay inside |y| 22.0, so shells printed with the ribs
    # (inner faces 22.26) still fit.
```

Check for leftover references:

Run: `grep -n "ribInY\|ribL\|ribT\|rib_edges" case/fusion_scripts/03_shell.py`
Expected: no output. (`rW`, `clear`, `bayW` may still be used by later steps; if the grep for `bayW` shows uses after the deleted block, keep the three lines that compute `rW, clear = ...` and `bayW = ...` above the marker comment.)

- [ ] **Step 3: Rebuild the shell and probe**

Run: `python3 case/fusion_scripts/run_fusion.py script case/fusion_scripts/03_shell.py`
Expected: the step prints without the `radar retention ribs ok` and `rib lead-in chamfers` lines, ending with the script's OK line.

Run: `python3 case/fusion_scripts/run_fusion.py script case/fusion_scripts/90_verify.py --read-only`
Expected: `VERIFY OK`.

- [ ] **Step 4: Commit**

```bash
git add case/fusion_scripts/03_shell.py case/fusion_scripts/90_verify.py
git commit -m "case: drop the shell's radar retention ribs (the plate's pins locate the board)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: Boards — rotate the XIAO 180°

**Files:**
- Modify: `case/fusion_scripts/04_boards.py:28-33` (XIAO orientation config), `:118` (place call)

- [ ] **Step 1: Change the orientation config and the place call**

Replace the XIAO comment block and constant:

```python
# XIAO native frame: X = long axis w/ USB overhang at +X, Y = thickness
# (components/USB on +Y side), Z = board short axis.  Rotation about X keeps
# USB pointing +X; +90 puts native +Y (component side) up.  The extra 180
# about Z (2026-10-27, user review) points the USB overhang at -X, into the
# radar bay's floor opening, and the ceramic antenna at +X toward the
# plastic PIR wing; the bay envelope is symmetric about xCx so the posts,
# fences and clips are unchanged.
XIAO_XROT_DEG = 90
XIAO_FLIP180 = True
```

and the place call:

```python
    # XIAO: bottom on posts at z = postH (= 3 mm), USB end toward the radar
    place(xiao_occ, rot_matrix(XIAO_XROT_DEG, XIAO_FLIP180), xCx, 0.0, postH)
```

- [ ] **Step 2: Run the placement and read the bounding boxes**

Run: `python3 case/fusion_scripts/run_fusion.py script case/fusion_scripts/04_boards.py`
Expected: `xiao placed bbox(cm): x -0.325..1.925  y -0.890..0.890  z 0.299..0.749` (unchanged envelope). The radar line is unchanged: `x -1.906..-0.394  y -2.202..2.202  z 0.664..1.301`.

- [ ] **Step 3: Confirm the USB is now at −X with a read-only probe**

Save this as a scratch file outside the repo (for example `/tmp/xiao_probe.py` is fine locally; do not commit it) and run it with `--read-only`:

```python
import adsk.core, adsk.fusion
MM = 0.1
def bodies_of(occ, out):
    for b in occ.bRepBodies: out.append(b)
    for c in occ.childOccurrences: bodies_of(c, out)
def inside(bodies, x, y, z):
    pt = adsk.core.Point3D.create(x*MM, y*MM, z*MM)
    return any(b.pointContainment(pt) == adsk.fusion.PointContainment.PointInsidePointContainment for b in bodies)
def run(_c):
    root = adsk.fusion.Design.cast(adsk.core.Application.get().activeProduct).rootComponent
    occ = next(o for o in root.occurrences if "xiao" in o.component.name.lower())
    xb = []; bodies_of(occ, xb)
    print("USB shell at x -2.5 z 6.5:", inside(xb, -2.5, 0.0, 6.5))     # expect True
    print("USB shell at x 18.5 z 6.5:", inside(xb, 18.5, 0.0, 6.5))     # expect False
    print("board at x 18.5 z 3.8:", inside(xb, 18.5, 0.0, 3.8))         # expect True
```

Run: `python3 case/fusion_scripts/run_fusion.py script /tmp/xiao_probe.py --read-only`
Expected: `True`, `False`, `True`.

- [ ] **Step 4: Plate probes still pass with the boards in place**

Run: `python3 case/fusion_scripts/run_fusion.py script case/fusion_scripts/90_verify.py --read-only`
Expected: `VERIFY OK`.

- [ ] **Step 5: Commit**

```bash
git add case/fusion_scripts/04_boards.py
git commit -m "case: XIAO rotated 180 deg, USB toward the radar bay, antenna toward the wing

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: Fit check and export

**Files:**
- Run: `case/fusion_scripts/91_pir_fit.py`, `case/fusion_scripts/05_export.py`
- Output: `case/rd03d_case_back.stl`, `case/rd03d_case_shell.stl`, `case/rd03d_pir_bezel.stl`

- [ ] **Step 1: Interference run**

Run: `python3 case/fusion_scripts/run_fusion.py script case/fusion_scripts/91_pir_fit.py`
Expected: `PIR FIT OK` with `interference pairs: 2 (0 unexpected)`: the plate/shell fit allowance (about 69 mm³) and the bezel/shell press (about 18.5 mm³). A plate/radar pair means a pin or bar touches the board: compare the pin centres with the spec's probe numbers before changing anything, and do not widen the notch play to hide it.

- [ ] **Step 2: Export**

Run: `python3 case/fusion_scripts/run_fusion.py script case/fusion_scripts/05_export.py`
Expected: three STLs written under `case/`. `ls -la case/*.stl` shows fresh timestamps; the back plate is a different size from the previous 313,284 bytes.

- [ ] **Step 3: Commit the STLs**

```bash
git add case/rd03d_case_back.stl case/rd03d_case_shell.stl case/rd03d_pir_bezel.stl
git commit -m "case: STLs with the locating pins, end bars and ribless shell

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 6: Wiring diagram and as-built notes

**Files:**
- Modify: `docs/wiring.png` (regenerated)
- Modify: `docs/superpowers/plans/2026-10-27-plate-locating-pins.md` (this file, "As built" section at the end)
- Modify: `rd03d_uart/README.md` (one line in the wiring section)

- [ ] **Step 1: Redraw the wiring diagram**

The generator is a PIL script kept outside the repo (`wiring.py` in the agent's scratchpad; if it is gone, redraw with the same layout from the current `docs/wiring.png`). Changes to make:

- XIAO box title: `XIAO ESP32-C6  (USB end toward the radar)`.
- Add one note line under the title text: `The XIAO is rotated 180° in the case since 2026-10-27: its USB end and the 5V, GND, 3V3, D6 and D7 pads face the radar bay; the radar cable comes through the floor window in the XIAO fence. D1 for the PIR is at the wing end.`
- Pad-to-signal mapping is unchanged (the labels follow the pads, not the case), so no wire colours or endpoints change; only the orientation note and title.

Regenerate and copy to `docs/wiring.png`. View it once and check no label overlaps a wire.

- [ ] **Step 2: README line**

In `rd03d_uart/README.md`, in the wiring table's intro sentence (or directly after the table), add: `In the case the XIAO sits with its USB end toward the radar bay (rotated 180° since the 2026-10-27 plate); the radar cable passes through the window at the foot of the XIAO fence, the PIR leads arrive at the wing end.`

- [ ] **Step 3: As-built notes**

Append to this plan file:

```markdown
## As built (2026-10-27)

- Probe numbers behind the design (read-only, placed vendor body, case mm): notch centres (-18.25, -21.40) and (-4.75, +21.30), arc radius 1.14 confirmed from the centre in both inboard directions; the other two corners solid at r 1.8 roundings. Bare PCB rear at 10.46 over y -22.0..-20.7 and +19.8..+22.0 full width; connector from y -20.7, lowest z 6.64, x -15.3..-9.3; passives to z 9.0..9.3 mid-board.
- 02 step prints: <paste the end-bar, 4b, window, pin and clip lines>.
- 90: VERIFY OK after Tasks 2, 3, 4. 91: <pairs and volumes>.
- STL sizes: <back / shell / bezel bytes>.
- Print the back plate and the shell (the old shell's boss would hit the rotated USB; see As built). Measure after printing: pin diameter (model 2.2), board drop-on by hand over both pins, the connector clearance to the -Y bar.
```

Fill in the angle-bracket items from the actual run output; no brackets may remain.

- [ ] **Step 4: Commit**

```bash
git add docs/wiring.png rd03d_uart/README.md docs/superpowers/plans/2026-10-27-plate-locating-pins.md
git commit -m "docs: wiring diagram for the rotated XIAO; as-built notes for the pin plate

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## Self-review against the spec

- Pins (spec "Locating pins"): Task 2 step 4, probes Task 1 step 3. Flat at |y| 22.0, top 12.4, chamfer 0.4, merge into wall and bar: covered.
- End bars, crossbars deleted, clip B shift, steps 12/13 gone: Task 2 steps 1, 5, 6; probes Task 1.
- Wire opening (4b full height, fence kept, window |y| < 3.5): Task 2 steps 2, 3; probes Task 1 step 3.
- XIAO rotation, no +X end wall: Task 4; nothing adds a wall.
- Shell ribs: Task 3.
- Verification list in the spec: Task 1 and Task 3 step 1 probes; 91 in Task 5.
- Docs: Task 6.
- No TBD/TODO placeholders; the only angle brackets are in the as-built template that Task 6 fills.

## As built (2026-10-27)

- Probe numbers behind the design (read-only, placed vendor body, case mm): notch centres (-18.25, -21.40) and (-4.75, +21.30), arc radius 1.14 confirmed from the centre in both inboard directions (1.14/1.12 and 1.14/1.16); the other two corners solid at r 1.8 roundings. Bare PCB rear at 10.46 over y -22.0..-20.7 and +19.8..+22.0 full width; connector from y -20.7, lowest z 6.64, x -15.3..-9.3; passives to z 9.0..9.3 mid-board.
- 02 step prints: `radar bay ok (X walls + end bars bearing on the PCB ends; Y-location is the corner pins' job), bar top z(mm)= 10.46`; `radar fence +X wall opened floor to top over |y| < 9.4`; `wire window ok (XIAO fence -X wall, |y| < 3.5, z 0..5)`; `locating pins ok (O2.2 at [(-18.25, -21.4), (-4.75, 21.3)], top z 12.4, flat at |y| 22.0, 0.4 chamfer)`; clips A -3.50..3.50 top 12.50, B -20.00..-13.00 top 12.30, C 10.00..17.00 top 12.30, lips 11.80 +0.85.
- Probe corrections during the build: the Task 1 "void above the end bar" stations were inside the pin footprints (moved 3 mm in from the walls); the z 1.0 probes at (-3.10, ±8) sat inside the XIAO's -X corner posts, which were always there (moved to |y| 4.5). Not geometry changes.
- Shell: ribs deleted; the XIAO hold-down boss moved from x 2.5..9.5 to x 6.5..13.5 because the rotated USB shell (x -3.2..4.1, z 3.3..7.5) would have hit the old boss by 11.6 mm^3 (found by the boards script's interference check; the spec missed it).
- 04: XIAO placed bbox x -3.23..19.23, y ±8.89, z 3.00..7.46; USB shell at x -3.23..4.07; ceramic antenna at x 17.1..19.1. The plan's probe point (-2.5, 0, 6.5) is inside the hollow USB shell and reads void; z 4.5 or 7.2 there read solid.
- 90: VERIFY OK after Tasks 2, 3, 4 and the boss move (plate 22.723 cm3, shell 16.752 cm3, bezel 0.371 cm3). 04 interference after the boss move: only the two expected case pairs (plate/shell 69.3 mm^3, shell/bezel 18.5 mm^3) plus the XIAO vendor model's own internal sub-body overlaps; no shell/XIAO and no plate/radar pair. 91: 2 pairs, 0 unexpected, 87.7 mm^3, PIR FIT OK.
- STL sizes: back 334,684 B, shell 158,684 B, bezel 158,284 B (bezel unchanged).
- Print the back plate and the shell. The old shell no longer fits: its hold-down boss at x 2.5..9.5 would hit the rotated XIAO's USB shell, so the shell must be reprinted with the boss at x 6.5..13.5. The bezel is unchanged. Measure after printing: pin diameter (model 2.2), board drop-on by hand over both pins, the connector clearance to the -Y bar.
- Pad ends after the rotation, corrected on review (from the XIAO pinout and the pre-rotation record in case/README.md, 5V ~ 14.9, GND ~ 12.4, D6/D7 ~ -0.4, mirrored about xCx 8.0): 5V ~ x 1.1, GND ~ 3.6, D1 ~ 3.6, 3V3 ~ 6.2 at the -X (window) end; D6 and D7 ~ 16.4 at the +X (wing) end. The spec's third reason for the rotation, that it puts "the radar-side pads (5V, GND, D6, D7) next to the radar", was wrong for D6/D7 and has been removed from the spec; the reasons that stand are the unreachable USB port and the antenna facing plastic instead of the radar's ground plane. Wire route as the geometry gives it: the window (x -5.0..-3.5, |y| < 3.5, z 0..5) exits directly under the rotated USB receptacle (z 3.3..7.5), so the wires run under the XIAO (3 mm posts; keep them below z 3 and clear of the four 3 x 3 corner posts at x -3.25..-0.25 and 16.25..19.25, |y| 5.9..8.9). 5V/GND rise in the two channels beside the receptacle (x -3.5..-1.75, |y| 4.45..5.9); only the two UART wires (OT1->D7, RX<-D6) run about 25 mm under the board and rise at the fence's open +X end past x 19.25. The board-to-fence gap along the +/-Y edges is 0.25, so nothing rises there. 3V3 (x ~ 6.2) is inside the clip lip span x 4.5..11.5 (lips 0.10 above the board): keep that joint flat. The earlier wiring.png, the 02 step 5a comment, the firmware README and the spec's wire-opening section said otherwise and were corrected the same day.
- Deviations from the spec: the pins are 02 step 6b (the spec heading said 4c); clip B's gap to the -Y bar is 0.8 (bar face -20.8, clip -20.0), not the spec's 0.7; the spec's pin probe at z 1 was not added because the pin centres sit inside the end bars there and the probe would prove nothing (z 11 and 12.2 are probed instead). The flat at |y| 22.0 stays, but its reason is that it keeps the pin inside the board's end line and clear of the shell's +/-Y wall, not that the old shell still fits; it does not (boss).
- Print guidance: if the -Y bar's +Y face prints proud and touches the radar's 5-pin connector, trim the bar face, not the connector. If the pins bind, file the pin, not the wall (the walls carry radarClear 0.10 in X). The pins stand 2 mm above the bars with about 0.15 radial play in the O2.28 notch, so a stringy pin top matters and an elephant's foot at the base does not; the 0.4 chamfer did apply.
- LED light pipe (evening, user request): the blue PETG shell hides the XIAO's yellow user LED (GPIO15) that showed through the white one. From the user's top-view photo the LED sits beside the B button on the 5V-column side, 4.2 in from the USB end and 5.7 off the centreline, i.e. case (2.5, +5.7) after the rotation. 03 step 7b cuts a O3.0 hole through the front wall at (ledX 2.5, ledY 6.0), the centre 0.3 outboard so the pipe clears the USB shell footprint (|y| 4.47); params ledX/ledY/ledPipeD are created by 02's ensure_params (set ledPipeD 1.8 for a stub of 1.75 mm clear filament). Probes added; VERIFY OK; shell STL 166,084 B. The shell print already running does not have the hole; drill O3 at (2.5, 6.0) from the plate origin or reprint.
- Corner fit (evening, user's print review): the plate's four outside corners and the cavity's inside corners were both modelled sharp; FDM rounds an inside corner to r 0.3..0.5 and prints an outside corner nearly sharp, so the plate bound on four points before the flats touched. 02 step 15 now cuts the plate's corners to r plateCornerR 1.5 (z -8..11, the -X wall's corner included); 03 step 7c fills the cavity's inside corners to r cavityCornerR 1.0 (z -8..14); diagonal gap 0.21 mm nominal. The wing's outer corners already carried the 2.5 mm fillet, so the pod box needed nothing. Probes added (void 0.15 in from each plate corner, solid past the arc; solid 0.15 in from each cavity corner, void at 0.6 r). VERIFY OK; 91 fit allowance 66.3 mm^3 (was 69.3), still the two expected pairs. STLs: back 347,084 B, shell 189,284 B. A sharp-cornered printed plate can be rescued with a file: round each corner to about r 1.5.
