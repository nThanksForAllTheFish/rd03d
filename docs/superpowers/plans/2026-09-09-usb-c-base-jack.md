# USB-C Base Jack, Capacitor Cradle and Clip Rework — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a rear-facing USB-C power jack, a 100 uF capacitor cradle and wire routes to the RD-03D case back plate; delete the shell's side USB notch and the interior LEGO counterbores; take the XIAO retention clips to 1.5 mm fingers on a deeper root.

**Architecture:** The case is a live Fusion 360 parametric document (`rd-03d_case`) rebuilt by re-running numbered Python scripts through Fusion's MCP server. `02_backplate.py` deletes and rebuilds the whole `BackPlate` component every run, so "edit the script, re-run it" is the normal edit cycle — there is no incremental state to protect. Verification is a separate read-only script, `90_verify.py`, that probes the rebuilt solids with `BRepBody.pointContainment` and raises on the first bad assertion. Each task adds its assertions to `90_verify.py` **first**, watches them fail, then changes the build script.

**Tech Stack:** Python 3 (stdlib only) driving `http://127.0.0.1:27182/mcp` via `case/fusion_scripts/run_fusion.py`; the Fusion 360 Python API (`adsk.core`, `adsk.fusion`).

---

## Read this before Task 1

These are hard constraints. Violating any of them destroys the user's work or wastes a print.

1. **NEVER run or edit `01_setup.py`.** It rewrites every Fusion user parameter back to its literal default and would discard values the user has tuned by hand. New parameters are added by `02_backplate.py` itself.
2. **NEVER save, close or discard the user's Fusion document.** Do not call `doc.save`, `doc.close` or `app.activeDocument.close`. Saving is the user's step.
3. **Every boolean feature must pass `participantBodies`.** A Fusion Cut/Intersect with no participant list consumes *every* intersecting body in the design — this silently deleted the whole BackPlate once. The `extrude()` helper in `02_backplate.py` takes `participants=[body]`; always supply it.
4. **The Fusion API length unit is centimetres.** Both scripts define `MM = 0.1` and multiply. Every number in this plan is stated in **mm**; write `13.6 * MM` in the code.
5. **If a script fails, Fusion rolls the whole thing back** — you get a clean document, not a half-built one. Re-run after fixing.
6. **A modal dialog open in Fusion blocks mutating scripts.** If a run hangs or reports a stale error, ask the user to check for an open dialog (Change Parameters, etc.) in their Fusion window.
7. The RD-03D parser `rd03d_uart/main/rd03d.c` and its header are out of scope and must not change.

**Running a script:**

```bash
python3 run_fusion.py script 02_backplate.py
```

**Running the verifier (read-only, safe at any time):**

```bash
cd /path/to/rd03d/case/fusion_scripts && python3 run_fusion.py script 90_verify.py --read-only
```

`run_fusion.py` exits non-zero when the script reports failure, so `echo $?` distinguishes pass from fail.

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `case/fusion_scripts/90_verify.py` | Read-only geometric assertions over both components | **Create** |
| `case/fusion_scripts/02_backplate.py` | Builds the BackPlate: plate, LEGO holes, bays, fences, clips, and now the jack collar / cap cradle / notches | Modify |
| `case/fusion_scripts/03_shell.py` | Builds the FrontShell: box, cavity, radome step, ribs, boss, edge softening | Modify (delete notch + its softening) |
| `case/fusion_scripts/05_export.py` | STL export of both components | Unchanged, re-run |
| `case/README.md` | Print settings, assembly, wiring | Modify |
| `case/rd03d_case_back.stl`, `case/rd03d_case_shell.stl` | Print-ready meshes | Regenerated |

`01_setup.py`, `00_smoke.py`, `04_boards.py` and `run_fusion.py` are untouched.

---

## Coordinate cheat-sheet (mm)

Referenced constantly below; all confirmed by probe in earlier sessions.

- Plate: x -20.85…20.85, y -22.85…22.85, z -8…0. Interior cavity ceiling z = 14.
- Radar bay: x -19.3…-3.7 between fence walls at x -20.8…-19.3 and x -3.7…-2.2.
- XIAO board: x -3.23…19.23, y ±8.89, PCB top z = 4.20. Bay posts z 0…3.
- XIAO fence walls: y ±9.15…±10.65, z 0…5, spanning x -5…20.85, **open on +X**.
- XIAO clip fingers: x 4.5…11.5 on each ±Y wall; isolating slots x 3.5…4.5 and 11.5…12.5.
- LEGO holes: ⌀4.9 at x 0.95 (y -12, -4, +4, +12) and x 8.95 (y -4, +4); ⌀6.4 × 0.9 counterbores on both faces.
- Snap pockets: **±X plate edges only**, y ±12, z -1.7…-0.3. Both ±Y edges are free.

---

### Task 1: Verification harness

Creates the probe script every later task extends. It must pass against the **current** model before anything changes, which also proves the MCP link works.

**Files:**
- Create: `case/fusion_scripts/90_verify.py`

- [ ] **Step 1: Create the branch**

```bash
cd /path/to/rd03d && git checkout -b feat/case-usb-jack
```

- [ ] **Step 2: Write the harness**

Create `case/fusion_scripts/90_verify.py` with exactly this content:

```python
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


def run(_context: str):
    app = adsk.core.Application.get()
    des = adsk.fusion.Design.cast(app.activeProduct)
    root = des.rootComponent
    plate = find(root, "BackPlate")
    shell = find(root, "FrontShell")
    print("plate volume %.3f cm3   shell volume %.3f cm3"
          % (plate.volume, shell.volume))

    check_baseline(plate, shell)

    if FAILURES:
        for f in FAILURES:
            print("FAIL:", f)
        raise RuntimeError("%d verification failure(s)" % len(FAILURES))
    print("VERIFY OK")
```

- [ ] **Step 3: Run it against the current model**

```bash
cd /path/to/rd03d/case/fusion_scripts && python3 run_fusion.py script 90_verify.py --read-only; echo "exit=$?"
```

Expected: prints two volumes then `VERIFY OK`, `exit=0`.

If it reports "no component starting with BackPlate", the user's Fusion has a different document in front; stop and ask them to activate `rd-03d_case`. If a baseline probe fails, do **not** edit the probe to make it pass — report the discrepancy, because it means the live model differs from what this plan assumes.

- [ ] **Step 4: Commit**

```bash
cd /path/to/rd03d && git add case/fusion_scripts/90_verify.py && git commit -m "test(case): read-only geometry verifier for the Fusion model

Point-containment probes over BackPlate and FrontShell, run through the
MCP driver with --read-only. Baseline covers the plate core, a LEGO bore,
the radar clip wall, both XIAO fence walls and the shell cavity.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2: XIAO clips — 1.5 mm fingers on a 1.5 mm-deeper root

The finger goes to the fence wall's own 1.5 mm thickness (a 1.0 mm wall does not print on the user's 0.6 mm nozzle). To keep peak strain at 2.3% instead of 4.1% the cantilever root drops 1.5 mm into the plate: two trenches either side of each finger, and the existing isolating slots extended down to meet them. Lip (0.60 mm) and grab (0.34 mm) are unchanged — at a 0.6 mm nozzle, 0.60 is exactly one extrusion and a smaller lip would print worse.

**Files:**
- Modify: `case/fusion_scripts/90_verify.py`
- Modify: `case/fusion_scripts/02_backplate.py` (step 8b, near the end of `run()`)

- [ ] **Step 1: Write the failing checks**

In `90_verify.py`, add this function directly above `def run(`:

```python
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
        # lip still projects past the wall's inner face to +/-8.55
        solid(plate, 8.0, sy * 8.7, 4.25, "clip lip underside " + tag)
        # trenches are local to the finger: plate is solid beyond them
        solid(plate, 2.0, sy * 11.25, -0.75, "plate solid beyond trench " + tag)
        solid(plate, 14.0, sy * 11.25, -0.75, "plate solid beyond trench " + tag)
```

Then add the call inside `run()`, immediately after `check_baseline(plate, shell)`:

```python
    check_xiao_clips(plate)
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd /path/to/rd03d/case/fusion_scripts && python3 run_fusion.py script 90_verify.py --read-only; echo "exit=$?"
```

Expected: `exit=1`, with FAIL lines for the trenches, the slot depth and the finger thickness (the lip, blade and "solid beyond trench" checks already pass).

- [ ] **Step 3: Change the clip parameters**

In `02_backplate.py`, in step 8b near the end of `run()`, change these two constants:

```python
    X_SLOT_Z0 = 0.0
    X_RAISE_Z0 = 4.5 * MM                        # inside the 5 mm wall
    X_THIN = 0.5 * MM
```

to:

```python
    # 2026-09-09: finger taken to the wall's own 1.5 mm (a 1.0 mm wall does
    # not print on the user's 0.6 mm nozzle), and the root dropped 1.5 mm
    # into the plate by the trenches below so the lever grows 4.30 -> 5.80
    # mm. Peak strain 3*t*d/(2*L^2) = 3*1.5*0.34/(2*5.8^2) = 2.3%, down from
    # 2.8% at 1.0/4.30 and well clear of the 4.1% a 1.5 mm finger would see
    # on the old lever. Spring rate goes as t^3/L^3 -> 1.4x the old force.
    # The lip stays at 0.60 mm: a 0.6 mm nozzle resolves 0.6 and 1.2, so a
    # smaller lip would print worse, not better.
    X_TRENCH_Z0 = -1.5 * MM
    X_SLOT_Z0 = X_TRENCH_Z0
    X_RAISE_Z0 = 4.5 * MM                        # inside the 5 mm wall
    X_THIN = 0.0
```

- [ ] **Step 4: Add the trench cuts**

In `02_backplate.py`, immediately **after** the `for sy in (-1, 1):` clip loop in step 8b and **before** the final `print("BackPlate bodies:", ...)`, insert:

```python
    # 8c. Clip-root trenches. Free the finger below the plate floor so its
    # cantilever root sits at X_TRENCH_Z0 instead of z=0. Spans x 4.4..11.6
    # (0.1 mm into each isolating slot, so no coincident faces), 1.2 mm wide
    # - a void, not a wall, so the 0.6 mm nozzle is not a constraint. Clear
    # of the snap pockets (+/-X edges, y +/-12) and of every LEGO bore: the
    # x 8.95 column only has holes at y +/-4, and the x 0.95 column lies
    # outside x 4.4..11.6.
    sk = comp.sketches.add(comp.xYConstructionPlane)
    for sy in (-1, 1):
        box(sk, 4.4 * MM, 11.6 * MM, sy * 7.95 * MM, sy * 9.15 * MM)
        box(sk, 4.4 * MM, 11.6 * MM, sy * 10.65 * MM, sy * 11.85 * MM)
    profs = collection([sk.profiles.item(i) for i in range(sk.profiles.count)])
    if profs.count != 4:
        raise RuntimeError("expected 4 clip-trench profiles, found %d"
                           % profs.count)
    extrude(comp, profs, X_TRENCH_Z0, 0,
            adsk.fusion.FeatureOperations.CutFeatureOperation,
            participants=[plate_body])
    print("xiao clip trenches ok (x 4.4..11.6, 1.2 mm wide, to z %.2f)"
          % (X_TRENCH_Z0 * 10))
```

- [ ] **Step 5: Rebuild the back plate**

```bash
cd /path/to/rd03d/case/fusion_scripts && python3 run_fusion.py script 02_backplate.py; echo "exit=$?"
```

Expected: `exit=0`, ending with `xiao clip trenches ok ...` and `BackPlate bodies: 1`.

If it reports more than one body, the trenches severed the blade — check the x span covers the slots rather than butting against them.

- [ ] **Step 6: Verify**

```bash
cd /path/to/rd03d/case/fusion_scripts && python3 run_fusion.py script 90_verify.py --read-only; echo "exit=$?"
```

Expected: `VERIFY OK`, `exit=0`.

- [ ] **Step 7: Commit**

```bash
cd /path/to/rd03d && git add case/fusion_scripts/02_backplate.py case/fusion_scripts/90_verify.py && git commit -m "fix(case): XIAO clips to 1.5 mm fingers on a 1.5 mm-deeper root

A 1.0 mm finger does not print on the user's 0.6 mm nozzle, but 1.5 mm on
the old 4.30 mm lever reaches 4.1% strain - PETG's yield. Two 1.2 mm x
1.5 mm trenches either side of each finger, with the isolating slots
extended down to meet them, take the lever to 5.80 mm: 2.3% peak strain
and 1.4x the retention force, with the 0.60 mm lip and 0.34 mm grab
untouched.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 3: Delete the interior LEGO counterbores

A Technic pin is only ever inserted from the back, so the counterbores on the interior face do nothing but put 0.9 mm recesses where printed features want flat floor.

**Files:**
- Modify: `case/fusion_scripts/90_verify.py`
- Modify: `case/fusion_scripts/02_backplate.py` (step 7)

- [ ] **Step 1: Write the failing check**

In `90_verify.py`, add above `def run(`:

```python
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
```

Add the call in `run()` after `check_xiao_clips(plate)`:

```python
    check_no_interior_counterbores(plate)
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd /path/to/rd03d/case/fusion_scripts && python3 run_fusion.py script 90_verify.py --read-only; echo "exit=$?"
```

Expected: `exit=1`, six `EXPECTED SOLID ... interior counterbore removed` failures.

- [ ] **Step 3: Delete the interior counterbore cut**

In `02_backplate.py` step 7, delete this whole extrude (it is the third of three, cutting from `-cbZ` to `0`):

```python
    extrude(comp, circles(cbD / 2), -cbZ, 0,
            adsk.fusion.FeatureOperations.CutFeatureOperation,
            participants=[plate_body])
```

Then update the step-7 comment: change

```python
    # legoCbDia x legoCbDepth counterbore on BOTH faces so Technic
    # pin collars/tips seat flush, plus a 0.3mm 45 deg entry chamfer
    # on the rear opening.
```

to

```python
    # legoCbDia x legoCbDepth counterbore on the REAR face only, so pin
    # collars seat flush, plus a 0.3mm 45 deg entry chamfer on the rear
    # opening. (2026-09-09: the interior counterbores were deleted - a
    # Technic pin only ever goes in from the back, and their 0.9 mm
    # recesses fell where printed features want flat interior floor.)
```

`legoCbDia` and `legoCbDepth` stay as user parameters; the rear counterbore still uses them.

- [ ] **Step 4: Rebuild and verify**

```bash
cd /path/to/rd03d/case/fusion_scripts && python3 run_fusion.py script 02_backplate.py && python3 run_fusion.py script 90_verify.py --read-only; echo "exit=$?"
```

Expected: the build prints `technic holes ok: ...` and `rear entry chamfers ok (0.3mm x 45deg on 6 edges)`, then `VERIFY OK`, `exit=0`.

- [ ] **Step 5: Commit**

```bash
cd /path/to/rd03d && git add case/fusion_scripts/02_backplate.py case/fusion_scripts/90_verify.py && git commit -m "fix(case): delete the interior LEGO counterbores

A Technic pin is only ever inserted from the back, so the six 6.4 x 0.9
recesses on the interior face served nothing and fell where the new
capacitor cradle and clip trenches want flat floor. Rear counterbores and
the rear entry chamfers are unchanged.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 4: USB-C jack slot, collar and seating ramps

The jack measures 14.42 mm long with a 10.58 mm metal shell, 9.08 mm wide, 3.17 mm thick. Mouth flush at the back face, 6.42 mm protruding into the -Y band beside the XIAO. The shell's rear edge wedges to a stop on a pair of 45° ramps at z = 2.58 (= 10.58 - 8). Pull-out retention is epoxy — the part has no rearward-facing surface to catch, so there is no printed alternative.

**Files:**
- Modify: `case/fusion_scripts/90_verify.py`
- Modify: `case/fusion_scripts/02_backplate.py` (new step 9, after step 8c)

Target geometry (mm):

| feature | value |
|---|---|
| slot centre | x 13.6, y -19.0 |
| slot | 9.33 (X) × 3.42 (Y), z -8…0 → x 8.935…18.265, y -20.71…-17.29 |
| collar | 1.5 mm walls, z 0…4.5 → outer x 7.435…19.765, y -22.21…-15.79 |
| ramps | 45°, inward 0.8 mm, z 2.58 → 3.38 |
| channel above ramps | 1.82 mm → y -19.91…-18.09 |
| rear chamfer | 0.5 mm on the slot's back-face edges |

- [ ] **Step 1: Write the failing checks**

In `90_verify.py`, add above `def run(`:

```python
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
```

Add the call in `run()` after `check_no_interior_counterbores(plate)`:

```python
    check_usb_jack(plate)
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd /path/to/rd03d/case/fusion_scripts && python3 run_fusion.py script 90_verify.py --read-only; echo "exit=$?"
```

Expected: `exit=1`, with `EXPECTED VOID` failures for the slot (it is solid plate today) and `EXPECTED SOLID` failures for the collar walls.

- [ ] **Step 3: Add the user parameters**

In `02_backplate.py`, add this helper directly above `def run(`:

```python
def ensure_params(des):
    """Create this plan's user parameters if the document lacks them.

    Deliberately NOT added to 01_setup.py: re-running that script resets
    every parameter the user has hand-tuned. Existing values are left alone
    so the user can edit them in Modify -> Change Parameters.
    """
    spec = [
        ("usbJackW", "9.08 mm", "USB-C jack widest section (its PCB)"),
        ("usbJackT", "3.17 mm", "USB-C jack thickness"),
        ("usbJackL", "14.42 mm", "USB-C jack overall length"),
        ("usbShellL", "10.58 mm", "USB-C jack metal shell length"),
        ("usbJackClear", "0.25 mm", "total jack slot clearance"),
        ("capDia", "8.2 mm", "bulk capacitor diameter"),
        ("capLen", "12 mm", "bulk capacitor body length"),
        ("capClear", "0.4 mm", "total capacitor cradle clearance"),
    ]
    ups = des.userParameters
    for name, expr, comment in spec:
        if ups.itemByName(name) is None:
            ups.add(name, adsk.core.ValueInput.createByString(expr),
                    "mm", comment)
            print("added param", name, "=", expr)
```

Then call it near the top of `run()`, immediately after `root = des.rootComponent`:

```python
    ensure_params(des)
```

- [ ] **Step 4: Build the slot, collar and ramps**

In `02_backplate.py`, immediately after the step 8c trench block and before the final `print("BackPlate bodies:", ...)`, insert:

```python
    # 9. USB-C base jack (2026-09-09). The user powers the node through a
    # jack in the LEGO-mount face instead of the XIAO's own connector.
    # Measured part: 14.42 long overall, 10.58 of that metal shell, 9.08
    # wide (its PCB, the widest section), 3.17 thick. Mouth flush with the
    # back face at z=-8, so 6.42 protrudes into the free -Y band beside the
    # XIAO and the PCB tail starts at z=+0.92 - above the floor, which is
    # why the plate's slot only ever contains the metal shell.
    #
    # The shell's rear edge lands at z = usbShellL - backT = 2.58, where a
    # 45 deg ramp on each +/-Y collar wall rises 0.8 mm inward and wedges it
    # to a stop. Ramps rather than a flat ledge: they self-centre, they
    # print with no unsupported horizontal overhang, and since USB-C is
    # reversible they work whichever face the jack's PCB tail is flush with
    # (a dimension we never measured and do not need).
    #
    # PULL-OUT RETENTION IS EPOXY. The part presents no rearward-facing
    # surface to catch, so no printed feature can resist it; the collar
    # gives ~40 mm2 of glue wall against a plug latch force of order 10 N.
    jW = p(des, "usbJackW") + p(des, "usbJackClear")      # 9.33
    jT = p(des, "usbJackT") + p(des, "usbJackClear")      # 3.42
    JCX, JCY = 13.6 * MM, -19.0 * MM
    COLLAR_T = 1.5 * MM
    COLLAR_TOP = 4.5 * MM
    RAMP_Z0 = p(des, "usbShellL") - backT                 # 2.58
    RAMP_RISE = 0.8 * MM
    RAMP_Z1 = RAMP_Z0 + RAMP_RISE                         # 3.38
    ANCHOR = 0.3 * MM            # loft sections start inside the wall
    sx0, sx1 = JCX - jW / 2, JCX + jW / 2                 # 8.935 .. 18.265
    sy0, sy1 = JCY - jT / 2, JCY + jT / 2                 # -20.71 .. -17.29

    # 9a. collar box, then one cut for the slot AND the collar bore
    sk = comp.sketches.add(comp.xYConstructionPlane)
    box(sk, sx0 - COLLAR_T, sx1 + COLLAR_T,
        sy0 - COLLAR_T, sy1 + COLLAR_T)
    extrude(comp, sk.profiles.item(0), 0, COLLAR_TOP,
            adsk.fusion.FeatureOperations.JoinFeatureOperation,
            participants=[plate_body])
    sk = comp.sketches.add(comp.xYConstructionPlane)
    box(sk, sx0, sx1, sy0, sy1)
    extrude(comp, sk.profiles.item(0), -backT, COLLAR_TOP,
            adsk.fusion.FeatureOperations.CutFeatureOperation,
            participants=[plate_body])

    # 9b. seating ramps on both +/-Y collar walls, plus the narrowed wall
    # they lead into (z RAMP_Z1..COLLAR_TOP), leaving a 1.82 mm tail channel
    for s in (-1, 1):
        # s = -1 is the -Y wall, whose material lies at more negative y and
        # whose channel is toward +y; "inward" is therefore -s.
        face = sy0 if s < 0 else sy1          # the wall's inner face
        back_y = face + s * ANCHOR            # 0.3 mm INTO the wall
        tip_y = face - s * RAMP_RISE          # 0.8 mm INTO the channel
        ramp_loft(comp, RAMP_Z0,
                  (sx0, sx1, back_y, face),
                  RAMP_Z1,
                  (sx0, sx1, back_y, tip_y),
                  [plate_body])
        sk = comp.sketches.add(comp.xYConstructionPlane)
        box(sk, sx0, sx1, back_y, tip_y)
        extrude(comp, sk.profiles.item(0), RAMP_Z1, COLLAR_TOP,
                adsk.fusion.FeatureOperations.JoinFeatureOperation,
                participants=[plate_body])

    # 9c. 0.5 mm entry chamfer on the slot's back-face opening, so the plug
    # finds the mouth. Comfort feature: report and continue if refused.
    try:
        edges = adsk.core.ObjectCollection.create()
        for e in plate_body.edges:
            g = e.geometry
            if not isinstance(g, adsk.core.Line3D):
                continue
            mz = (g.startPoint.z + g.endPoint.z) / 2
            mx = (g.startPoint.x + g.endPoint.x) / 2
            my = (g.startPoint.y + g.endPoint.y) / 2
            if abs(mz + backT) > 0.005:
                continue
            on_x = (abs(abs(mx - JCX) - jW / 2) < 0.005
                    and abs(my - JCY) < jT / 2 + 0.005)
            on_y = (abs(abs(my - JCY) - jT / 2) < 0.005
                    and abs(mx - JCX) < jW / 2 + 0.005)
            if on_x or on_y:
                edges.add(e)
        if edges.count != 4:
            raise RuntimeError("expected 4 slot mouth edges, found %d"
                               % edges.count)
        ch = comp.features.chamferFeatures
        chi = ch.createInput(edges, False)
        chi.setToEqualDistance(adsk.core.ValueInput.createByReal(0.5 * MM))
        ch.add(chi)
        print("usb slot mouth chamfer ok (0.5mm x 45deg on 4 edges)")
    except Exception as exc:
        print("USB MOUTH CHAMFER SKIPPED:", exc)

    if comp.bRepBodies.count != 1:
        raise RuntimeError("usb jack step split the plate: %d bodies"
                           % comp.bRepBodies.count)
    print("usb jack ok: slot %.2f x %.2f at (%.2f, %.2f), collar to %.2f, "
          "ramp %.2f->%.2f, tail channel %.2f"
          % (jW * 10, jT * 10, JCX * 10, JCY * 10, COLLAR_TOP * 10,
             RAMP_Z0 * 10, RAMP_Z1 * 10, (jT - 2 * RAMP_RISE) * 10))
```

- [ ] **Step 5: Rebuild and verify**

```bash
cd /path/to/rd03d/case/fusion_scripts && python3 run_fusion.py script 02_backplate.py && python3 run_fusion.py script 90_verify.py --read-only; echo "exit=$?"
```

Expected: the build prints `added param usbJackW = 9.08 mm` (and the other seven) on its first run, then `usb jack ok: slot 9.33 x 3.42 at (13.60, -19.00), collar to 4.50, ramp 2.58->3.38, tail channel 1.82`, then `VERIFY OK`, `exit=0`.

If the ramp loft reports "participantBodies unsupported", that message is benign — the helper already handles it. If the chamfer is skipped, note it and continue; it is comfort only.

- [ ] **Step 6: Commit**

```bash
cd /path/to/rd03d && git add case/fusion_scripts/02_backplate.py case/fusion_scripts/90_verify.py && git commit -m "feat(case): USB-C base jack slot, collar and seating ramps

9.33 x 3.42 through-slot at (13.6, -19.0) with the mouth flush at the back
face; 6.42 mm of the 14.42 mm jack protrudes into the free -Y band beside
the XIAO. A 1.5 mm collar carries 45 deg ramps at z=2.58 - where the
10.58 mm metal shell ends - that wedge the shell to a stop and take the
plug-insertion load, narrowing to a 1.82 mm channel for the PCB tail so
the pads stay solderable above the collar.

Ramps rather than a flat ledge: self-centring, no unsupported overhang
when printed, and orientation-agnostic since USB-C is reversible.
Pull-out retention is epoxy - the part offers no rearward-facing surface.

Eight new user parameters are added by this script, not by 01_setup.py,
which must not be re-run.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 5: Capacitor cradle

The user's 100 uF electrolytic (12.0 mm long, 8.2 mm diameter) lies on its side in the +Y band, which is otherwise empty. Two C-clip saddle ribs snap it down past its equator.

**Files:**
- Modify: `case/fusion_scripts/90_verify.py`
- Modify: `case/fusion_scripts/02_backplate.py` (new step 10)

Target geometry (mm): axis at y +16.75, z 5.5; ribs 1.2 mm thick at x 3.0 and x 12.8; rib blocks y 11.25…22.25, z 0…8.0; bore radius 4.3 → 1.2 mm arms at the equator and a 7.0 mm opening at the top. Rib x positions clear the +Y clip trench at x 4.4…11.6 by ≥0.6 mm.

- [ ] **Step 1: Write the failing checks**

In `90_verify.py`, add above `def run(`:

```python
def check_cap_cradle(plate):
    """Two 1.2 mm C-clip ribs saddling a 8.2 mm cap at y 16.75, z 5.5."""
    for rx in (3.0, 12.8):
        solid(plate, rx, 12.0, 2.0, "cradle rib body at x=%.1f" % rx)
        solid(plate, rx, 21.5, 2.0, "cradle rib body at x=%.1f" % rx)
        void(plate, rx, 16.75, 5.5, "cap bore at x=%.1f" % rx)
        solid(plate, rx, 16.75, 0.5, "rib material below the bore x=%.1f" % rx)
        void(plate, rx, 16.75, 8.5, "open above the rib top x=%.1f" % rx)
    # nothing between the ribs
    void(plate, 8.0, 16.75, 4.0, "clear between the cradle ribs")
    void(plate, 8.0, 12.0, 2.0, "clear between the cradle ribs")
    # ribs stop clear of the fence and the plate edge
    void(plate, 3.0, 11.0, 2.0, "gap between cradle rib and XIAO fence")
    void(plate, 3.0, 22.5, 2.0, "gap between cradle rib and plate edge")
    # the +Y clip trench is not roofed by a rib
    void(plate, 8.0, 11.25, -0.75, "outboard +Y clip trench still open")
```

Add the call in `run()` after `check_usb_jack(plate)`:

```python
    check_cap_cradle(plate)
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd /path/to/rd03d/case/fusion_scripts && python3 run_fusion.py script 90_verify.py --read-only; echo "exit=$?"
```

Expected: `exit=1`, with `EXPECTED SOLID ... cradle rib body` failures.

- [ ] **Step 3: Build the cradle**

In `02_backplate.py`, immediately after the step 9 block and before the final `print("BackPlate bodies:", ...)`, insert:

```python
    # 10. Bulk capacitor cradle (2026-09-09). The user's 100 uF electrolytic
    # (12 x 8.2 dia) sits across the incoming 5 V. It lies on its SIDE in the
    # +Y band, which is otherwise empty: standing it would put 12 mm into a
    # 14 mm cavity with the leads pointing at the lid, and its footprint only
    # fits the -Y band alongside the jack by about 0.1 mm.
    #
    # Two rib blocks with the cap's cylinder bored through them: 1.2 mm of
    # arm at the equator (two clean extrusions on the 0.6 mm nozzle),
    # thicker below, and a 7.0 mm opening at the rib top (z=8.0) so the cap
    # snaps down past its widest point. Rib x positions sit clear of the +Y
    # clip trench at x 4.4..11.6. Lead end faces +X, where the XIAO fence is
    # open, giving a full-height wire channel at x 19.3..20.85 through to
    # the -Y band and the jack.
    capR = p(des, "capDia") / 2 + p(des, "capClear") / 2   # 4.3
    CAP_Y, CAP_Z = 16.75 * MM, 5.5 * MM
    RIB_T = 1.2 * MM
    RIB_R = capR + RIB_T                                   # 5.5
    RIB_TOP = CAP_Z + 2.5 * MM                             # 8.0 -> 7.0 mouth
    RIB_X = (3.0 * MM, 12.8 * MM)

    sk = comp.sketches.add(comp.xYConstructionPlane)
    for rx in RIB_X:
        box(sk, rx - RIB_T / 2, rx + RIB_T / 2,
            CAP_Y - RIB_R, CAP_Y + RIB_R)
    profs = collection([sk.profiles.item(i) for i in range(sk.profiles.count)])
    if profs.count != len(RIB_X):
        raise RuntimeError("expected %d cradle rib profiles, found %d"
                           % (len(RIB_X), profs.count))
    extrude(comp, profs, 0, RIB_TOP,
            adsk.fusion.FeatureOperations.JoinFeatureOperation,
            participants=[plate_body])

    # bore the cap's cylinder along X through both ribs. The sketch lives on
    # a YZ-parallel plane, where sketch X maps to world Y and sketch Y to
    # world Z; extruding along the plane normal sweeps in world X.
    pl_inp = comp.constructionPlanes.createInput()
    pl_inp.setByOffset(comp.yZConstructionPlane,
                       adsk.core.ValueInput.createByReal(1.0 * MM))
    pl = comp.constructionPlanes.add(pl_inp)
    pl.isLightBulbOn = False
    sk = comp.sketches.add(pl)
    sk.sketchCurves.sketchCircles.addByCenterRadius(
        adsk.core.Point3D.create(CAP_Y, CAP_Z, 0), capR)
    extrude(comp, sk.profiles.item(0), 0, 14.0 * MM,
            adsk.fusion.FeatureOperations.CutFeatureOperation,
            participants=[plate_body])
    sk.isVisible = False

    if comp.bRepBodies.count != 1:
        raise RuntimeError("cap cradle split the plate: %d bodies"
                           % comp.bRepBodies.count)
    print("cap cradle ok: ribs at x %s, bore r=%.2f at (y %.2f, z %.2f), "
          "arm %.2f, mouth %.2f at z %.2f"
          % ([round(v * 10, 2) for v in RIB_X], capR * 10, CAP_Y * 10,
             CAP_Z * 10, RIB_T * 10, 7.0, RIB_TOP * 10))
```

- [ ] **Step 4: Rebuild and verify**

```bash
cd /path/to/rd03d/case/fusion_scripts && python3 run_fusion.py script 02_backplate.py && python3 run_fusion.py script 90_verify.py --read-only; echo "exit=$?"
```

Expected: `cap cradle ok: ribs at x [3.0, 12.8], bore r=4.30 at (y 16.75, z 5.50), arm 1.20, mouth 7.00 at z 8.00`, then `VERIFY OK`, `exit=0`.

If the bore cut reports the wrong sketch orientation (a circle appearing in plan rather than in section), check that the construction plane was built from `yZConstructionPlane`, not `xYConstructionPlane`.

- [ ] **Step 5: Commit**

```bash
cd /path/to/rd03d && git add case/fusion_scripts/02_backplate.py case/fusion_scripts/90_verify.py && git commit -m "feat(case): capacitor cradle in the +Y band

Two 1.2 mm C-clip saddle ribs at x 3.0 and 12.8 with the cap's cylinder
bored through them - 1.2 mm arms at the equator, 7.0 mm mouth at z=8.0 so
the 8.2 mm cap snaps down past its widest point. Laid on its side rather
than standing: 12 mm upright in a 14 mm cavity points the leads at the lid,
and the footprint only fits the -Y band beside the jack by ~0.1 mm.

Rib x positions clear the +Y clip trench by 0.6 mm; lead end faces +X,
where the XIAO fence is already open as a wire channel.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 6: Fence notches for the 5V/GND pair

A notch outboard of the XIAO's 5V/GND pads so the wires drop straight down instead of being pinched between the board edge and the fence wall. Cut in **both** ±Y walls: the pads are on the -Y edge by the standard pinout, and a mirrored board then costs nothing.

**Files:**
- Modify: `case/fusion_scripts/90_verify.py`
- Modify: `case/fusion_scripts/02_backplate.py` (new step 11)

Target: x 14.5…18.0, z 2.5…5.0 (the wall top), through the full wall thickness at y ±9.15…±10.65. Clear of the clip fingers at x 4.5…11.5.

- [ ] **Step 1: Write the failing checks**

In `90_verify.py`, add above `def run(`:

```python
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
```

Add the call in `run()` after `check_cap_cradle(plate)`:

```python
    check_fence_notches(plate)
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd /path/to/rd03d/case/fusion_scripts && python3 run_fusion.py script 90_verify.py --read-only; echo "exit=$?"
```

Expected: `exit=1`, four `EXPECTED VOID ... wire notch open` failures.

- [ ] **Step 3: Cut the notches**

In `02_backplate.py`, immediately after the step 10 block and before the final `print("BackPlate bodies:", ...)`, insert:

```python
    # 11. Wire notches (2026-09-09). The jack's 5V/GND pair reaches the
    # XIAO's pads - user-confirmed on the long edge shared with D7, at the
    # end nearest the XIAO's own USB-C, i.e. x 14..18 - in about 10 mm
    # within the -Y band. This notch lets the pair drop straight down
    # instead of being pinched between the board edge and the fence wall.
    # Cut in BOTH walls: the standard pinout puts those pads on -Y, and
    # mirroring costs nothing if the board reads the other way round. Clear
    # of the clip fingers at x 4.5..11.5.
    NOTCH_X0, NOTCH_X1 = 14.5 * MM, 18.0 * MM
    NOTCH_Z0 = 2.5 * MM
    sk = comp.sketches.add(comp.xYConstructionPlane)
    for sy in (-1, 1):
        box(sk, NOTCH_X0, NOTCH_X1, sy * 9.05 * MM, sy * 10.75 * MM)
    profs = collection([sk.profiles.item(i) for i in range(sk.profiles.count)])
    if profs.count != 2:
        raise RuntimeError("expected 2 wire-notch profiles, found %d"
                           % profs.count)
    extrude(comp, profs, NOTCH_Z0, 5.1 * MM,
            adsk.fusion.FeatureOperations.CutFeatureOperation,
            participants=[plate_body])
    print("wire notches ok (x %.2f..%.2f, z %.2f..5.00, both fence walls)"
          % (NOTCH_X0 * 10, NOTCH_X1 * 10, NOTCH_Z0 * 10))
```

- [ ] **Step 4: Rebuild and verify**

```bash
cd /path/to/rd03d/case/fusion_scripts && python3 run_fusion.py script 02_backplate.py && python3 run_fusion.py script 90_verify.py --read-only; echo "exit=$?"
```

Expected: `wire notches ok (x 14.50..18.00, z 2.50..5.00, both fence walls)`, then `VERIFY OK`, `exit=0`.

- [ ] **Step 5: Commit**

```bash
cd /path/to/rd03d && git add case/fusion_scripts/02_backplate.py case/fusion_scripts/90_verify.py && git commit -m "feat(case): wire notches in both XIAO fence walls

3.5 x 2.5 mm notch at x 14.5..18.0, outboard of the XIAO's 5V/GND pads, so
the jack's pair drops straight down instead of being pinched between the
board edge and the wall. Cut in both walls so a mirrored board costs
nothing; clear of the clip fingers at x 4.5..11.5.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 7: Delete the shell's side USB notch

The base jack replaces it entirely. Removing it also removes the notch's edge-softening pass and tightens the back-rim edge count from a permissive range to exactly 8.

**Files:**
- Modify: `case/fusion_scripts/90_verify.py`
- Modify: `case/fusion_scripts/03_shell.py`

- [ ] **Step 1: Write the failing checks**

In `90_verify.py`, add above `def run(`:

```python
def check_no_shell_notch(shell):
    """The +X wall is continuous: the old notch spanned y +/-5.65, z -8..8."""
    for z in (-6.0, -2.0, 2.0, 6.0):
        solid(shell, 22.0, 0.0, z, "+X wall solid at z=%.1f" % z)
    solid(shell, 22.0, 4.0, 0.0, "+X wall solid at y=4")
    solid(shell, 22.0, -4.0, 0.0, "+X wall solid at y=-4")
    void(shell, 19.0, 0.0, 7.0, "cavity still open inside the +X wall")
```

Add the call in `run()` after `check_fence_notches(plate)`:

```python
    check_no_shell_notch(shell)
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd /path/to/rd03d/case/fusion_scripts && python3 run_fusion.py script 90_verify.py --read-only; echo "exit=$?"
```

Expected: `exit=1`, `EXPECTED SOLID ... +X wall solid` failures at the z values inside the notch.

- [ ] **Step 3: Delete the notch cut**

In `03_shell.py`, delete this whole block (step 4, around line 137):

```python
    # 4: usb notch through +X wall, back rim z=-backT up to z=8mm
    sk = comp.sketches.add(comp.xYConstructionPlane)
    rect(sk, intW / 2 + wall / 2, 0, wall + 0.02, 11.3 * MM)
    extrude(comp, sk.profiles.item(0), -backT, 8 * MM,
            adsk.fusion.FeatureOperations.CutFeatureOperation,
            participants=[shell_body])
    print("usb notch ok")
```

Replace it with a one-line record so the step numbering still reads:

```python
    # 4: (deleted 2026-09-09) the USB notch through the +X wall. The base
    # jack in the back plate replaces it entirely, so the XIAO's own USB-C
    # is no longer reachable with the case closed - serial console and USB
    # reflash now need the lid unclipped. `usbClear` joins `tapeRecess` as a
    # dead user parameter; both are left in place rather than re-running
    # 01_setup.py, which resets user-tuned values.
```

- [ ] **Step 4: Delete the notch edge-softening pass**

In `03_shell.py`, delete the whole of step 6d — everything from the comment

```python
    # 6d. USB-notch outer-edge soften: the two vertical edges where the notch
```

down to and including

```python
    print("usb notch soften: %d/%d edges filleted (r=%.2f mm)"
          % (done, total, soft * 10))
```

Leave the final `print("FrontShell bodies:", comp.bRepBodies.count)` in place.

- [ ] **Step 5: Tighten the rim edge-count guard**

In `03_shell.py`, change this comment (around line 320):

```python
    # At z_top the boundary is one clean closed loop (4 straights + 4 arcs
    # = 8 edges); at z_back the USB notch splits the +X segment (9 edges).
```

to:

```python
    # At both z_top and z_back the boundary is one clean closed loop
    # (4 straights + 4 arcs = 8 edges). Before 2026-09-09 the USB notch
    # split the +X segment at z_back, giving 9.
```

and change the guard:

```python
    rim = perimeter_edges(z_back)
    print("back rim edges found:", len(rim))
    if not 8 <= len(rim) <= 10:
        raise RuntimeError("back rim edge count out of range: %d" % len(rim))
```

to:

```python
    rim = perimeter_edges(z_back)
    print("back rim edges found:", len(rim))
    if len(rim) != 8:
        raise RuntimeError("back rim should be 8 edges with the USB notch "
                           "gone, found %d" % len(rim))
```

- [ ] **Step 6: Rebuild the shell and verify**

```bash
cd /path/to/rd03d/case/fusion_scripts && python3 run_fusion.py script 03_shell.py && python3 run_fusion.py script 90_verify.py --read-only; echo "exit=$?"
```

Expected: the build prints `back rim edges found: 8` and `rim fillet ok (r=0.80 mm on 8 edges)`, no `usb notch` lines at all, then `VERIFY OK`, `exit=0`.

If it reports a different rim edge count, print the count and stop — do not widen the guard. A count other than 8 means a feature other than the notch is touching the back rim, and that needs investigating rather than tolerating.

- [ ] **Step 7: Commit**

```bash
cd /path/to/rd03d && git add case/fusion_scripts/03_shell.py case/fusion_scripts/90_verify.py && git commit -m "feat(case): delete the shell's side USB notch

The base jack replaces it entirely. Removes the notch cut, its
edge-softening pass, and the permissive 8..10 back-rim edge guard - with
the notch gone the rim is exactly one 8-edge loop.

Consequence: the XIAO's own USB-C is no longer reachable with the case
closed. Serial console and USB reflash need the lid unclipped; OTA is
unaffected. usbClear becomes a dead parameter, left in place because
re-running 01_setup.py would reset user-tuned values.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 8: Export, document, and hand over

**Files:**
- Modify: `case/rd03d_case_back.stl`, `case/rd03d_case_shell.stl`
- Modify: `case/README.md`
- Modify: `/Users/me/.claude/projects/-path-to-rd03d/memory/rd03d_uart_project.md`

- [ ] **Step 1: Full clean rebuild of both parts**

Both scripts rebuild their component from scratch, so run them in order to prove the whole chain works from the committed sources:

```bash
cd /path/to/rd03d/case/fusion_scripts && python3 run_fusion.py script 02_backplate.py && python3 run_fusion.py script 03_shell.py && python3 run_fusion.py script 90_verify.py --read-only; echo "exit=$?"
```

Expected: `exit=0` and `VERIFY OK`.

- [ ] **Step 2: Export the STLs**

```bash
cd /path/to/rd03d/case/fusion_scripts && python3 run_fusion.py script 05_export.py
```

Expected: `exported rd03d_case_back.stl` and `exported rd03d_case_shell.stl`.

- [ ] **Step 3: Record the mesh stats**

```bash
cd /path/to/rd03d/case && python3 - <<'PY'
import struct
for f in ("rd03d_case_back.stl", "rd03d_case_shell.stl"):
    d = open(f, "rb").read()
    n = struct.unpack("<I", d[80:84])[0]
    lo = [1e9] * 3
    hi = [-1e9] * 3
    for i in range(n):
        base = 84 + i * 50 + 12
        for v in range(3):
            p = struct.unpack("<3f", d[base + v * 12: base + v * 12 + 12])
            for a in range(3):
                lo[a] = min(lo[a], p[a] * 10)
                hi[a] = max(hi[a], p[a] * 10)
    print(f, n, "tris",
          " ".join("%s %.2f..%.2f" % (ax, lo[i], hi[i])
                   for i, ax in enumerate("xyz")))
PY
```

Expected: the back plate's z range now runs from -8 to about 12.50 (clip A) and the shell's x range no longer shows the notch. Record the printed numbers in the commit message.

- [ ] **Step 4: Take review screenshots**

```bash
cd /path/to/rd03d/case/fusion_scripts && python3 run_fusion.py screenshot /tmp/case_iso.png iso-top-right && python3 run_fusion.py screenshot /tmp/case_back.png back
```

The `direction` value is hyphenated (`iso-top-right`); an unrecognised one leaves a dialog open in the user's Fusion and blocks the next mutating script. Send both images to the user with `SendUserFile`.

- [ ] **Step 5: Update `case/README.md`**

Append this section verbatim, after the existing print-settings section:

```markdown
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
```

- [ ] **Step 6: Update the project memory**

Append this paragraph to
`/Users/me/.claude/projects/-path-to-rd03d/memory/rd03d_uart_project.md`:

```markdown
**USB-C base jack + cap cradle (2026-09-09):** power now enters through a
USB-C jack in the back plate, and the shell's side USB notch is DELETED — the
XIAO's own port is unreachable with the case closed (OTA unaffected). Jack
measures 14.42 long / 10.58 of metal shell / 9.08 wide / 3.17 thick, so a
9.33 x 3.42 through-slot at (x 13.6, y -19.0) leaves the mouth flush at the
back face and 6.42 mm protruding into the free -Y band. A 1.5 mm collar
(z 0..4.5) carries 45 deg ramps at **z=2.58** (= usbShellL - backT) that wedge
the shell to a stop and take the plug-insertion load; above them a 1.82 mm
channel guides the PCB tail. **Pull-out retention is epoxy** — the part has no
rearward-facing surface, so no printed feature can hold it. The 100 uF cap
(12 x 8.2) lies on its side in the +Y band in two 1.2 mm C-clip ribs at
x 3.0/12.8, bore r=4.3 at (y 16.75, z 5.5). Wire notches (x 14.5..18.0,
z 2.5..5) in BOTH fence walls; the fence's open +X side is the cap's route
between bands. Interior LEGO counterbores deleted (a pin only ever goes in
from the back) so the interior floor is flat. XIAO clips reworked: finger
1.0 -> **1.5 mm** (a 1.0 mm wall will not print on the 0.6 nozzle) with two
1.2 x 1.5 mm trenches sinking the root to z=-1.5, lever 4.30 -> 5.80 mm —
2.3% peak strain, 1.4x force, lip 0.60 and grab 0.34 unchanged (0.6 and 1.2
are what a 0.6 nozzle resolves; a smaller lip prints worse). New probe
harness `case/fusion_scripts/90_verify.py` runs read-only and asserts all of
this with pointContainment. Eight new user params (usbJack*, cap*) are added
by 02_backplate.py, NOT by 01_setup.py.
```

Do not add a new line to `MEMORY.md` — the existing `rd03d_uart project` entry
already points at this file.

- [ ] **Step 7: Commit**

```bash
cd /path/to/rd03d && git add case/fusion_scripts/02_backplate.py case/fusion_scripts/90_verify.py && git commit -m "fix(case): XIAO clips to 1.5 mm fingers on a 1.5 mm-deeper root

A 1.0 mm finger does not print on the user's 0.6 mm nozzle, but 1.5 mm on
the old 4.30 mm lever reaches 4.1% strain - PETG's yield. Two 1.2 mm x
1.5 mm trenches either side of each finger, with the isolating slots
extended down to meet them, take the lever to 5.80 mm: 2.3% peak strain
and 1.4x the retention force, with the 0.60 mm lip and 0.34 mm grab
untouched.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 3: Delete the interior LEGO counterbores

A Technic pin is only ever inserted from the back, so the counterbores on the interior face do nothing but put 0.9 mm recesses where printed features want flat floor.

**Files:**
- Modify: `case/fusion_scripts/90_verify.py`
- Modify: `case/fusion_scripts/02_backplate.py` (step 7)

- [ ] **Step 1: Write the failing check**

In `90_verify.py`, add above `def run(`:

```python
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
```

Add the call in `run()` after `check_xiao_clips(plate)`:

```python
    check_no_interior_counterbores(plate)
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd /path/to/rd03d/case/fusion_scripts && python3 run_fusion.py script 90_verify.py --read-only; echo "exit=$?"
```

Expected: `exit=1`, six `EXPECTED SOLID ... interior counterbore removed` failures.

- [ ] **Step 3: Delete the interior counterbore cut**

In `02_backplate.py` step 7, delete this whole extrude (it is the third of three, cutting from `-cbZ` to `0`):

```python
    extrude(comp, circles(cbD / 2), -cbZ, 0,
            adsk.fusion.FeatureOperations.CutFeatureOperation,
            participants=[plate_body])
```

Then update the step-7 comment: change

```python
    # legoCbDia x legoCbDepth counterbore on BOTH faces so Technic
    # pin collars/tips seat flush, plus a 0.3mm 45 deg entry chamfer
    # on the rear opening.
```

to

```python
    # legoCbDia x legoCbDepth counterbore on the REAR face only, so pin
    # collars seat flush, plus a 0.3mm 45 deg entry chamfer on the rear
    # opening. (2026-09-09: the interior counterbores were deleted - a
    # Technic pin only ever goes in from the back, and their 0.9 mm
    # recesses fell where printed features want flat interior floor.)
```

`legoCbDia` and `legoCbDepth` stay as user parameters; the rear counterbore still uses them.

- [ ] **Step 4: Rebuild and verify**

```bash
cd /path/to/rd03d/case/fusion_scripts && python3 run_fusion.py script 02_backplate.py && python3 run_fusion.py script 90_verify.py --read-only; echo "exit=$?"
```

Expected: the build prints `technic holes ok: ...` and `rear entry chamfers ok (0.3mm x 45deg on 6 edges)`, then `VERIFY OK`, `exit=0`.

- [ ] **Step 5: Commit**

```bash
cd /path/to/rd03d && git add case/fusion_scripts/02_backplate.py case/fusion_scripts/90_verify.py && git commit -m "fix(case): delete the interior LEGO counterbores

A Technic pin is only ever inserted from the back, so the six 6.4 x 0.9
recesses on the interior face served nothing and fell where the new
capacitor cradle and clip trenches want flat floor. Rear counterbores and
the rear entry chamfers are unchanged.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 4: USB-C jack slot, collar and seating ramps

The jack measures 14.42 mm long with a 10.58 mm metal shell, 9.08 mm wide, 3.17 mm thick. Mouth flush at the back face, 6.42 mm protruding into the -Y band beside the XIAO. The shell's rear edge wedges to a stop on a pair of 45° ramps at z = 2.58 (= 10.58 - 8). Pull-out retention is epoxy — the part has no rearward-facing surface to catch, so there is no printed alternative.

**Files:**
- Modify: `case/fusion_scripts/90_verify.py`
- Modify: `case/fusion_scripts/02_backplate.py` (new step 9, after step 8c)

Target geometry (mm):

| feature | value |
|---|---|
| slot centre | x 13.6, y -19.0 |
| slot | 9.33 (X) × 3.42 (Y), z -8…0 → x 8.935…18.265, y -20.71…-17.29 |
| collar | 1.5 mm walls, z 0…4.5 → outer x 7.435…19.765, y -22.21…-15.79 |
| ramps | 45°, inward 0.8 mm, z 2.58 → 3.38 |
| channel above ramps | 1.82 mm → y -19.91…-18.09 |
| rear chamfer | 0.5 mm on the slot's back-face edges |

- [ ] **Step 1: Write the failing checks**

In `90_verify.py`, add above `def run(`:

```python
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
```

Add the call in `run()` after `check_no_interior_counterbores(plate)`:

```python
    check_usb_jack(plate)
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd /path/to/rd03d/case/fusion_scripts && python3 run_fusion.py script 90_verify.py --read-only; echo "exit=$?"
```

Expected: `exit=1`, with `EXPECTED VOID` failures for the slot (it is solid plate today) and `EXPECTED SOLID` failures for the collar walls.

- [ ] **Step 3: Add the user parameters**

In `02_backplate.py`, add this helper directly above `def run(`:

```python
def ensure_params(des):
    """Create this plan's user parameters if the document lacks them.

    Deliberately NOT added to 01_setup.py: re-running that script resets
    every parameter the user has hand-tuned. Existing values are left alone
    so the user can edit them in Modify -> Change Parameters.
    """
    spec = [
        ("usbJackW", "9.08 mm", "USB-C jack widest section (its PCB)"),
        ("usbJackT", "3.17 mm", "USB-C jack thickness"),
        ("usbJackL", "14.42 mm", "USB-C jack overall length"),
        ("usbShellL", "10.58 mm", "USB-C jack metal shell length"),
        ("usbJackClear", "0.25 mm", "total jack slot clearance"),
        ("capDia", "8.2 mm", "bulk capacitor diameter"),
        ("capLen", "12 mm", "bulk capacitor body length"),
        ("capClear", "0.4 mm", "total capacitor cradle clearance"),
    ]
    ups = des.userParameters
    for name, expr, comment in spec:
        if ups.itemByName(name) is None:
            ups.add(name, adsk.core.ValueInput.createByString(expr),
                    "mm", comment)
            print("added param", name, "=", expr)
```

Then call it near the top of `run()`, immediately after `root = des.rootComponent`:

```python
    ensure_params(des)
```

- [ ] **Step 4: Build the slot, collar and ramps**

In `02_backplate.py`, immediately after the step 8c trench block and before the final `print("BackPlate bodies:", ...)`, insert:

```python
    # 9. USB-C base jack (2026-09-09). The user powers the node through a
    # jack in the LEGO-mount face instead of the XIAO's own connector.
    # Measured part: 14.42 long overall, 10.58 of that metal shell, 9.08
    # wide (its PCB, the widest section), 3.17 thick. Mouth flush with the
    # back face at z=-8, so 6.42 protrudes into the free -Y band beside the
    # XIAO and the PCB tail starts at z=+0.92 - above the floor, which is
    # why the plate's slot only ever contains the metal shell.
    #
    # The shell's rear edge lands at z = usbShellL - backT = 2.58, where a
    # 45 deg ramp on each +/-Y collar wall rises 0.8 mm inward and wedges it
    # to a stop. Ramps rather than a flat ledge: they self-centre, they
    # print with no unsupported horizontal overhang, and since USB-C is
    # reversible they work whichever face the jack's PCB tail is flush with
    # (a dimension we never measured and do not need).
    #
    # PULL-OUT RETENTION IS EPOXY. The part presents no rearward-facing
    # surface to catch, so no printed feature can resist it; the collar
    # gives ~40 mm2 of glue wall against a plug latch force of order 10 N.
    jW = p(des, "usbJackW") + p(des, "usbJackClear")      # 9.33
    jT = p(des, "usbJackT") + p(des, "usbJackClear")      # 3.42
    JCX, JCY = 13.6 * MM, -19.0 * MM
    COLLAR_T = 1.5 * MM
    COLLAR_TOP = 4.5 * MM
    RAMP_Z0 = p(des, "usbShellL") - backT                 # 2.58
    RAMP_RISE = 0.8 * MM
    RAMP_Z1 = RAMP_Z0 + RAMP_RISE                         # 3.38
    ANCHOR = 0.3 * MM            # loft sections start inside the wall
    sx0, sx1 = JCX - jW / 2, JCX + jW / 2                 # 8.935 .. 18.265
    sy0, sy1 = JCY - jT / 2, JCY + jT / 2                 # -20.71 .. -17.29

    # 9a. collar box, then one cut for the slot AND the collar bore
    sk = comp.sketches.add(comp.xYConstructionPlane)
    box(sk, sx0 - COLLAR_T, sx1 + COLLAR_T,
        sy0 - COLLAR_T, sy1 + COLLAR_T)
    extrude(comp, sk.profiles.item(0), 0, COLLAR_TOP,
            adsk.fusion.FeatureOperations.JoinFeatureOperation,
            participants=[plate_body])
    sk = comp.sketches.add(comp.xYConstructionPlane)
    box(sk, sx0, sx1, sy0, sy1)
    extrude(comp, sk.profiles.item(0), -backT, COLLAR_TOP,
            adsk.fusion.FeatureOperations.CutFeatureOperation,
            participants=[plate_body])

    # 9b. seating ramps on both +/-Y collar walls, plus the narrowed wall
    # they lead into (z RAMP_Z1..COLLAR_TOP), leaving a 1.82 mm tail channel
    for s in (-1, 1):
        # s = -1 is the -Y wall, whose material lies at more negative y and
        # whose channel is toward +y; "inward" is therefore -s.
        face = sy0 if s < 0 else sy1          # the wall's inner face
        back_y = face + s * ANCHOR            # 0.3 mm INTO the wall
        tip_y = face - s * RAMP_RISE          # 0.8 mm INTO the channel
        ramp_loft(comp, RAMP_Z0,
                  (sx0, sx1, back_y, face),
                  RAMP_Z1,
                  (sx0, sx1, back_y, tip_y),
                  [plate_body])
        sk = comp.sketches.add(comp.xYConstructionPlane)
        box(sk, sx0, sx1, back_y, tip_y)
        extrude(comp, sk.profiles.item(0), RAMP_Z1, COLLAR_TOP,
                adsk.fusion.FeatureOperations.JoinFeatureOperation,
                participants=[plate_body])

    # 9c. 0.5 mm entry chamfer on the slot's back-face opening, so the plug
    # finds the mouth. Comfort feature: report and continue if refused.
    try:
        edges = adsk.core.ObjectCollection.create()
        for e in plate_body.edges:
            g = e.geometry
            if not isinstance(g, adsk.core.Line3D):
                continue
            mz = (g.startPoint.z + g.endPoint.z) / 2
            mx = (g.startPoint.x + g.endPoint.x) / 2
            my = (g.startPoint.y + g.endPoint.y) / 2
            if abs(mz + backT) > 0.005:
                continue
            on_x = (abs(abs(mx - JCX) - jW / 2) < 0.005
                    and abs(my - JCY) < jT / 2 + 0.005)
            on_y = (abs(abs(my - JCY) - jT / 2) < 0.005
                    and abs(mx - JCX) < jW / 2 + 0.005)
            if on_x or on_y:
                edges.add(e)
        if edges.count != 4:
            raise RuntimeError("expected 4 slot mouth edges, found %d"
                               % edges.count)
        ch = comp.features.chamferFeatures
        chi = ch.createInput(edges, False)
        chi.setToEqualDistance(adsk.core.ValueInput.createByReal(0.5 * MM))
        ch.add(chi)
        print("usb slot mouth chamfer ok (0.5mm x 45deg on 4 edges)")
    except Exception as exc:
        print("USB MOUTH CHAMFER SKIPPED:", exc)

    if comp.bRepBodies.count != 1:
        raise RuntimeError("usb jack step split the plate: %d bodies"
                           % comp.bRepBodies.count)
    print("usb jack ok: slot %.2f x %.2f at (%.2f, %.2f), collar to %.2f, "
          "ramp %.2f->%.2f, tail channel %.2f"
          % (jW * 10, jT * 10, JCX * 10, JCY * 10, COLLAR_TOP * 10,
             RAMP_Z0 * 10, RAMP_Z1 * 10, (jT - 2 * RAMP_RISE) * 10))
```

- [ ] **Step 5: Rebuild and verify**

```bash
cd /path/to/rd03d/case/fusion_scripts && python3 run_fusion.py script 02_backplate.py && python3 run_fusion.py script 90_verify.py --read-only; echo "exit=$?"
```

Expected: the build prints `added param usbJackW = 9.08 mm` (and the other seven) on its first run, then `usb jack ok: slot 9.33 x 3.42 at (13.60, -19.00), collar to 4.50, ramp 2.58->3.38, tail channel 1.82`, then `VERIFY OK`, `exit=0`.

If the ramp loft reports "participantBodies unsupported", that message is benign — the helper already handles it. If the chamfer is skipped, note it and continue; it is comfort only.

- [ ] **Step 6: Commit**

```bash
cd /path/to/rd03d && git add case/fusion_scripts/02_backplate.py case/fusion_scripts/90_verify.py && git commit -m "feat(case): USB-C base jack slot, collar and seating ramps

9.33 x 3.42 through-slot at (13.6, -19.0) with the mouth flush at the back
face; 6.42 mm of the 14.42 mm jack protrudes into the free -Y band beside
the XIAO. A 1.5 mm collar carries 45 deg ramps at z=2.58 - where the
10.58 mm metal shell ends - that wedge the shell to a stop and take the
plug-insertion load, narrowing to a 1.82 mm channel for the PCB tail so
the pads stay solderable above the collar.

Ramps rather than a flat ledge: self-centring, no unsupported overhang
when printed, and orientation-agnostic since USB-C is reversible.
Pull-out retention is epoxy - the part offers no rearward-facing surface.

Eight new user parameters are added by this script, not by 01_setup.py,
which must not be re-run.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 5: Capacitor cradle

The user's 100 uF electrolytic (12.0 mm long, 8.2 mm diameter) lies on its side in the +Y band, which is otherwise empty. Two C-clip saddle ribs snap it down past its equator.

**Files:**
- Modify: `case/fusion_scripts/90_verify.py`
- Modify: `case/fusion_scripts/02_backplate.py` (new step 10)

Target geometry (mm): axis at y +16.75, z 5.5; ribs 1.2 mm thick at x 3.0 and x 12.8; rib blocks y 11.25…22.25, z 0…8.0; bore radius 4.3 → 1.2 mm arms at the equator and a 7.0 mm opening at the top. Rib x positions clear the +Y clip trench at x 4.4…11.6 by ≥0.6 mm.

- [ ] **Step 1: Write the failing checks**

In `90_verify.py`, add above `def run(`:

```python
def check_cap_cradle(plate):
    """Two 1.2 mm C-clip ribs saddling a 8.2 mm cap at y 16.75, z 5.5."""
    for rx in (3.0, 12.8):
        solid(plate, rx, 12.0, 2.0, "cradle rib body at x=%.1f" % rx)
        solid(plate, rx, 21.5, 2.0, "cradle rib body at x=%.1f" % rx)
        void(plate, rx, 16.75, 5.5, "cap bore at x=%.1f" % rx)
        solid(plate, rx, 16.75, 0.5, "rib material below the bore x=%.1f" % rx)
        void(plate, rx, 16.75, 8.5, "open above the rib top x=%.1f" % rx)
    # nothing between the ribs
    void(plate, 8.0, 16.75, 4.0, "clear between the cradle ribs")
    void(plate, 8.0, 12.0, 2.0, "clear between the cradle ribs")
    # ribs stop clear of the fence and the plate edge
    void(plate, 3.0, 11.0, 2.0, "gap between cradle rib and XIAO fence")
    void(plate, 3.0, 22.5, 2.0, "gap between cradle rib and plate edge")
    # the +Y clip trench is not roofed by a rib
    void(plate, 8.0, 11.25, -0.75, "outboard +Y clip trench still open")
```

Add the call in `run()` after `check_usb_jack(plate)`:

```python
    check_cap_cradle(plate)
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd /path/to/rd03d/case/fusion_scripts && python3 run_fusion.py script 90_verify.py --read-only; echo "exit=$?"
```

Expected: `exit=1`, with `EXPECTED SOLID ... cradle rib body` failures.

- [ ] **Step 3: Build the cradle**

In `02_backplate.py`, immediately after the step 9 block and before the final `print("BackPlate bodies:", ...)`, insert:

```python
    # 10. Bulk capacitor cradle (2026-09-09). The user's 100 uF electrolytic
    # (12 x 8.2 dia) sits across the incoming 5 V. It lies on its SIDE in the
    # +Y band, which is otherwise empty: standing it would put 12 mm into a
    # 14 mm cavity with the leads pointing at the lid, and its footprint only
    # fits the -Y band alongside the jack by about 0.1 mm.
    #
    # Two rib blocks with the cap's cylinder bored through them: 1.2 mm of
    # arm at the equator (two clean extrusions on the 0.6 mm nozzle),
    # thicker below, and a 7.0 mm opening at the rib top (z=8.0) so the cap
    # snaps down past its widest point. Rib x positions sit clear of the +Y
    # clip trench at x 4.4..11.6. Lead end faces +X, where the XIAO fence is
    # open, giving a full-height wire channel at x 19.3..20.85 through to
    # the -Y band and the jack.
    capR = p(des, "capDia") / 2 + p(des, "capClear") / 2   # 4.3
    CAP_Y, CAP_Z = 16.75 * MM, 5.5 * MM
    RIB_T = 1.2 * MM
    RIB_R = capR + RIB_T                                   # 5.5
    RIB_TOP = CAP_Z + 2.5 * MM                             # 8.0 -> 7.0 mouth
    RIB_X = (3.0 * MM, 12.8 * MM)

    sk = comp.sketches.add(comp.xYConstructionPlane)
    for rx in RIB_X:
        box(sk, rx - RIB_T / 2, rx + RIB_T / 2,
            CAP_Y - RIB_R, CAP_Y + RIB_R)
    profs = collection([sk.profiles.item(i) for i in range(sk.profiles.count)])
    if profs.count != len(RIB_X):
        raise RuntimeError("expected %d cradle rib profiles, found %d"
                           % (len(RIB_X), profs.count))
    extrude(comp, profs, 0, RIB_TOP,
            adsk.fusion.FeatureOperations.JoinFeatureOperation,
            participants=[plate_body])

    # bore the cap's cylinder along X through both ribs. The sketch lives on
    # a YZ-parallel plane, where sketch X maps to world Y and sketch Y to
    # world Z; extruding along the plane normal sweeps in world X.
    pl_inp = comp.constructionPlanes.createInput()
    pl_inp.setByOffset(comp.yZConstructionPlane,
                       adsk.core.ValueInput.createByReal(1.0 * MM))
    pl = comp.constructionPlanes.add(pl_inp)
    pl.isLightBulbOn = False
    sk = comp.sketches.add(pl)
    sk.sketchCurves.sketchCircles.addByCenterRadius(
        adsk.core.Point3D.create(CAP_Y, CAP_Z, 0), capR)
    extrude(comp, sk.profiles.item(0), 0, 14.0 * MM,
            adsk.fusion.FeatureOperations.CutFeatureOperation,
            participants=[plate_body])
    sk.isVisible = False

    if comp.bRepBodies.count != 1:
        raise RuntimeError("cap cradle split the plate: %d bodies"
                           % comp.bRepBodies.count)
    print("cap cradle ok: ribs at x %s, bore r=%.2f at (y %.2f, z %.2f), "
          "arm %.2f, mouth %.2f at z %.2f"
          % ([round(v * 10, 2) for v in RIB_X], capR * 10, CAP_Y * 10,
             CAP_Z * 10, RIB_T * 10, 7.0, RIB_TOP * 10))
```

- [ ] **Step 4: Rebuild and verify**

```bash
cd /path/to/rd03d/case/fusion_scripts && python3 run_fusion.py script 02_backplate.py && python3 run_fusion.py script 90_verify.py --read-only; echo "exit=$?"
```

Expected: `cap cradle ok: ribs at x [3.0, 12.8], bore r=4.30 at (y 16.75, z 5.50), arm 1.20, mouth 7.00 at z 8.00`, then `VERIFY OK`, `exit=0`.

If the bore cut reports the wrong sketch orientation (a circle appearing in plan rather than in section), check that the construction plane was built from `yZConstructionPlane`, not `xYConstructionPlane`.

- [ ] **Step 5: Commit**

```bash
cd /path/to/rd03d && git add case/fusion_scripts/02_backplate.py case/fusion_scripts/90_verify.py && git commit -m "feat(case): capacitor cradle in the +Y band

Two 1.2 mm C-clip saddle ribs at x 3.0 and 12.8 with the cap's cylinder
bored through them - 1.2 mm arms at the equator, 7.0 mm mouth at z=8.0 so
the 8.2 mm cap snaps down past its widest point. Laid on its side rather
than standing: 12 mm upright in a 14 mm cavity points the leads at the lid,
and the footprint only fits the -Y band beside the jack by ~0.1 mm.

Rib x positions clear the +Y clip trench by 0.6 mm; lead end faces +X,
where the XIAO fence is already open as a wire channel.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 6: Fence notches for the 5V/GND pair

A notch outboard of the XIAO's 5V/GND pads so the wires drop straight down instead of being pinched between the board edge and the fence wall. Cut in **both** ±Y walls: the pads are on the -Y edge by the standard pinout, and a mirrored board then costs nothing.

**Files:**
- Modify: `case/fusion_scripts/90_verify.py`
- Modify: `case/fusion_scripts/02_backplate.py` (new step 11)

Target: x 14.5…18.0, z 2.5…5.0 (the wall top), through the full wall thickness at y ±9.15…±10.65. Clear of the clip fingers at x 4.5…11.5.

- [ ] **Step 1: Write the failing checks**

In `90_verify.py`, add above `def run(`:

```python
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
```

Add the call in `run()` after `check_cap_cradle(plate)`:

```python
    check_fence_notches(plate)
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd /path/to/rd03d/case/fusion_scripts && python3 run_fusion.py script 90_verify.py --read-only; echo "exit=$?"
```

Expected: `exit=1`, four `EXPECTED VOID ... wire notch open` failures.

- [ ] **Step 3: Cut the notches**

In `02_backplate.py`, immediately after the step 10 block and before the final `print("BackPlate bodies:", ...)`, insert:

```python
    # 11. Wire notches (2026-09-09). The jack's 5V/GND pair reaches the
    # XIAO's pads - user-confirmed on the long edge shared with D7, at the
    # end nearest the XIAO's own USB-C, i.e. x 14..18 - in about 10 mm
    # within the -Y band. This notch lets the pair drop straight down
    # instead of being pinched between the board edge and the fence wall.
    # Cut in BOTH walls: the standard pinout puts those pads on -Y, and
    # mirroring costs nothing if the board reads the other way round. Clear
    # of the clip fingers at x 4.5..11.5.
    NOTCH_X0, NOTCH_X1 = 14.5 * MM, 18.0 * MM
    NOTCH_Z0 = 2.5 * MM
    sk = comp.sketches.add(comp.xYConstructionPlane)
    for sy in (-1, 1):
        box(sk, NOTCH_X0, NOTCH_X1, sy * 9.05 * MM, sy * 10.75 * MM)
    profs = collection([sk.profiles.item(i) for i in range(sk.profiles.count)])
    if profs.count != 2:
        raise RuntimeError("expected 2 wire-notch profiles, found %d"
                           % profs.count)
    extrude(comp, profs, NOTCH_Z0, 5.1 * MM,
            adsk.fusion.FeatureOperations.CutFeatureOperation,
            participants=[plate_body])
    print("wire notches ok (x %.2f..%.2f, z %.2f..5.00, both fence walls)"
          % (NOTCH_X0 * 10, NOTCH_X1 * 10, NOTCH_Z0 * 10))
```

- [ ] **Step 4: Rebuild and verify**

```bash
cd /path/to/rd03d/case/fusion_scripts && python3 run_fusion.py script 02_backplate.py && python3 run_fusion.py script 90_verify.py --read-only; echo "exit=$?"
```

Expected: `wire notches ok (x 14.50..18.00, z 2.50..5.00, both fence walls)`, then `VERIFY OK`, `exit=0`.

- [ ] **Step 5: Commit**

```bash
cd /path/to/rd03d && git add case/fusion_scripts/02_backplate.py case/fusion_scripts/90_verify.py && git commit -m "feat(case): wire notches in both XIAO fence walls

3.5 x 2.5 mm notch at x 14.5..18.0, outboard of the XIAO's 5V/GND pads, so
the jack's pair drops straight down instead of being pinched between the
board edge and the wall. Cut in both walls so a mirrored board costs
nothing; clear of the clip fingers at x 4.5..11.5.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 7: Delete the shell's side USB notch

The base jack replaces it entirely. Removing it also removes the notch's edge-softening pass and tightens the back-rim edge count from a permissive range to exactly 8.

**Files:**
- Modify: `case/fusion_scripts/90_verify.py`
- Modify: `case/fusion_scripts/03_shell.py`

- [ ] **Step 1: Write the failing checks**

In `90_verify.py`, add above `def run(`:

```python
def check_no_shell_notch(shell):
    """The +X wall is continuous: the old notch spanned y +/-5.65, z -8..8."""
    for z in (-6.0, -2.0, 2.0, 6.0):
        solid(shell, 22.0, 0.0, z, "+X wall solid at z=%.1f" % z)
    solid(shell, 22.0, 4.0, 0.0, "+X wall solid at y=4")
    solid(shell, 22.0, -4.0, 0.0, "+X wall solid at y=-4")
    void(shell, 19.0, 0.0, 7.0, "cavity still open inside the +X wall")
```

Add the call in `run()` after `check_fence_notches(plate)`:

```python
    check_no_shell_notch(shell)
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd /path/to/rd03d/case/fusion_scripts && python3 run_fusion.py script 90_verify.py --read-only; echo "exit=$?"
```

Expected: `exit=1`, `EXPECTED SOLID ... +X wall solid` failures at the z values inside the notch.

- [ ] **Step 3: Delete the notch cut**

In `03_shell.py`, delete this whole block (step 4, around line 137):

```python
    # 4: usb notch through +X wall, back rim z=-backT up to z=8mm
    sk = comp.sketches.add(comp.xYConstructionPlane)
    rect(sk, intW / 2 + wall / 2, 0, wall + 0.02, 11.3 * MM)
    extrude(comp, sk.profiles.item(0), -backT, 8 * MM,
            adsk.fusion.FeatureOperations.CutFeatureOperation,
            participants=[shell_body])
    print("usb notch ok")
```

Replace it with a one-line record so the step numbering still reads:

```python
    # 4: (deleted 2026-09-09) the USB notch through the +X wall. The base
    # jack in the back plate replaces it entirely, so the XIAO's own USB-C
    # is no longer reachable with the case closed - serial console and USB
    # reflash now need the lid unclipped. `usbClear` joins `tapeRecess` as a
    # dead user parameter; both are left in place rather than re-running
    # 01_setup.py, which resets user-tuned values.
```

- [ ] **Step 4: Delete the notch edge-softening pass**

In `03_shell.py`, delete the whole of step 6d — everything from the comment

```python
    # 6d. USB-notch outer-edge soften: the two vertical edges where the notch
```

down to and including

```python
    print("usb notch soften: %d/%d edges filleted (r=%.2f mm)"
          % (done, total, soft * 10))
```

Leave the final `print("FrontShell bodies:", comp.bRepBodies.count)` in place.

- [ ] **Step 5: Tighten the rim edge-count guard**

In `03_shell.py`, change this comment (around line 320):

```python
    # At z_top the boundary is one clean closed loop (4 straights + 4 arcs
    # = 8 edges); at z_back the USB notch splits the +X segment (9 edges).
```

to:

```python
    # At both z_top and z_back the boundary is one clean closed loop
    # (4 straights + 4 arcs = 8 edges). Before 2026-09-09 the USB notch
    # split the +X segment at z_back, giving 9.
```

and change the guard:

```python
    rim = perimeter_edges(z_back)
    print("back rim edges found:", len(rim))
    if not 8 <= len(rim) <= 10:
        raise RuntimeError("back rim edge count out of range: %d" % len(rim))
```

to:

```python
    rim = perimeter_edges(z_back)
    print("back rim edges found:", len(rim))
    if len(rim) != 8:
        raise RuntimeError("back rim should be 8 edges with the USB notch "
                           "gone, found %d" % len(rim))
```

- [ ] **Step 6: Rebuild the shell and verify**

```bash
cd /path/to/rd03d/case/fusion_scripts && python3 run_fusion.py script 03_shell.py && python3 run_fusion.py script 90_verify.py --read-only; echo "exit=$?"
```

Expected: the build prints `back rim edges found: 8` and `rim fillet ok (r=0.80 mm on 8 edges)`, no `usb notch` lines at all, then `VERIFY OK`, `exit=0`.

If it reports a different rim edge count, print the count and stop — do not widen the guard. A count other than 8 means a feature other than the notch is touching the back rim, and that needs investigating rather than tolerating.

- [ ] **Step 7: Commit**

```bash
cd /path/to/rd03d && git add case/fusion_scripts/03_shell.py case/fusion_scripts/90_verify.py && git commit -m "feat(case): delete the shell's side USB notch

The base jack replaces it entirely. Removes the notch cut, its
edge-softening pass, and the permissive 8..10 back-rim edge guard - with
the notch gone the rim is exactly one 8-edge loop.

Consequence: the XIAO's own USB-C is no longer reachable with the case
closed. Serial console and USB reflash need the lid unclipped; OTA is
unaffected. usbClear becomes a dead parameter, left in place because
re-running 01_setup.py would reset user-tuned values.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 8: Export, document, and hand over

**Files:**
- Modify: `case/rd03d_case_back.stl`, `case/rd03d_case_shell.stl`
- Modify: `case/README.md`
- Modify: `/Users/me/.claude/projects/-path-to-rd03d/memory/rd03d_uart_project.md`

- [ ] **Step 1: Full clean rebuild of both parts**

Both scripts rebuild their component from scratch, so run them in order to prove the whole chain works from the committed sources:

```bash
cd /path/to/rd03d/case/fusion_scripts && python3 run_fusion.py script 02_backplate.py && python3 run_fusion.py script 03_shell.py && python3 run_fusion.py script 90_verify.py --read-only; echo "exit=$?"
```

Expected: `exit=0` and `VERIFY OK`.

- [ ] **Step 2: Export the STLs**

```bash
cd /path/to/rd03d/case/fusion_scripts && python3 run_fusion.py script 05_export.py
```

Expected: `exported rd03d_case_back.stl` and `exported rd03d_case_shell.stl`.

- [ ] **Step 3: Record the mesh stats**

```bash
cd /path/to/rd03d/case && python3 - <<'PY'
import struct
for f in ("rd03d_case_back.stl", "rd03d_case_shell.stl"):
    d = open(f, "rb").read()
    n = struct.unpack("<I", d[80:84])[0]
    lo = [1e9] * 3
    hi = [-1e9] * 3
    for i in range(n):
        base = 84 + i * 50 + 12
        for v in range(3):
            p = struct.unpack("<3f", d[base + v * 12: base + v * 12 + 12])
            for a in range(3):
                lo[a] = min(lo[a], p[a] * 10)
                hi[a] = max(hi[a], p[a] * 10)
    print(f, n, "tris",
          " ".join("%s %.2f..%.2f" % (ax, lo[i], hi[i])
                   for i, ax in enumerate("xyz")))
PY
```

Expected: the back plate's z range now runs from -8 to about 12.50 (clip A) and the shell's x range no longer shows the notch. Record the printed numbers in the commit message.

- [ ] **Step 4: Take review screenshots**

```bash
cd /path/to/rd03d/case/fusion_scripts && python3 run_fusion.py screenshot /tmp/case_iso.png iso-top-right && python3 run_fusion.py screenshot /tmp/case_back.png back
```

The `direction` value is hyphenated (`iso-top-right`); an unrecognised one leaves a dialog open in the user's Fusion and blocks the next mutating script. Send both images to the user with `SendUserFile`.

- [ ] **Step 5: Update `case/README.md`**

Add a section covering, in this order:

1. **USB-C jack assembly.** Solder the two wires to the tail pads on the bench first. Push the jack into the collar **from inside the case**, mouth first, until the metal shell wedges on the ramps — it should stop about 6.4 mm above the floor with the mouth flush at the back face. Check the plug seats fully before gluing. Then two dabs of epoxy in the collar; **this is the only thing resisting pull-out**, by necessity, since the part has no rearward-facing surface to catch.
2. **CC pulldowns.** The jack needs 5.1 kΩ from CC1 and CC2 to GND or a modern USB-C source will never enable VBUS. It works off a USB-A-to-C cable either way, which makes the failure confusing.
3. **Capacitor.** Lies on its side in the +Y cradle, lead end toward +X. The leads run round the fence's open +X side into the -Y band.
4. **Wire route.** Jack pads → the -Y fence notch at x 14.5…18.0 → the XIAO's 5V/GND pads. The junction may be made at either end.
5. **No USB access with the case closed.** Serial console and USB reflash need the lid unclipped; OTA is unaffected.
6. **Plug clearance caveat.** A plug overmold wider than about 14 mm will foul a ball joint in the LEGO hole at (8.95, -12) — use a plain pin there or a right-angle plug.

- [ ] **Step 6: Update the project memory**

Edit `/Users/me/.claude/projects/-path-to-rd03d/memory/rd03d_uart_project.md`, appending a paragraph that records: the base jack (dimensions, slot position, ramp stop at z=2.58, epoxy retention), the cap cradle location, the deleted shell notch and interior counterbores, the XIAO clip rework (1.5 mm finger, root at z=-1.5, lever 5.80 mm), and the new `90_verify.py` probe harness. Do not add a new line to `MEMORY.md` — the existing `rd03d_uart project` entry already points at this file.

- [ ] **Step 7: Commit**

```bash
cd /path/to/rd03d && git add case/ && git commit -m "feat(case): export STLs and document the base-jack build

Re-exported both parts after the jack, cradle, notch and clip changes.
README covers jack assembly order, the 5.1k CC pulldowns, cap orientation,
the wire route, and that the XIAO's USB-C is no longer reachable with the
case closed.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

- [ ] **Step 8: Report to the user**

Send the back-plate STL with `SendUserFile` and report: what changed, the mesh stats from Step 3, and the three things that are theirs to do — fit the 5.1 kΩ CC resistors, print and test-fit, and confirm their cable's overmold width against the 14 mm caveat.

Do **not** merge to main or save the Fusion document. Both are the user's call.

---

## Definition of done

- `90_verify.py` passes read-only against a document rebuilt from `02_backplate.py` and `03_shell.py` in sequence.
- Both STLs re-exported, back plate carrying the jack slot and cradle, shell carrying no notch.
- Every new wall is 1.2 or 1.5 mm; the only sub-1.2 mm feature in the design is the deliberate 0.60 mm clip lip.
- `01_setup.py` unmodified and never run. The user's Fusion document never saved or closed by a script.
