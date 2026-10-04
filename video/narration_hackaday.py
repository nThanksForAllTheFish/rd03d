"""Narration text per shot, public (Hackaday) variant: no employer, no personal-vs-work thread."""
from narration import SHOTS as _BASE

_OVERRIDES = {
    "04_cad": ("Fusion, driven live",
     "The enclosure was not designed by generating a mesh. Autodesk ships a Model Context Protocol "
     "server for Fusion 360, a small local endpoint that lets an agent run Python against the live "
     "Fusion API inside the open document. The agent wrote a driver for it, then built the case as "
     "a sequence of numbered scripts: set up parameters, build the back plate, build the shell, "
     "place the boards, export. About nineteen hundred lines of Python, and those scripts are the "
     "design. Every clip, ramp, counterbore and wire notch is a few lines, with the dimension and "
     "the reason side by side. Here are the crossbars that carry the radar board, and the comment "
     "that records why they moved. The last script is read-only. It probes the finished bodies with "
     "point-containment queries, asking Fusion whether there is material at a coordinate, and "
     "asserts that the walls are where the spec says, that the bores are open, and that nothing "
     "roofs a Technic hole. It caught exactly that, a capacitor rib placed over a pin hole, before "
     "I printed it. A unit test for a mechanical part. None of this depends on Fusion. Any CAD "
     "package with a scripting API can be driven the same way: FreeCAD, OpenSCAD, Onshape, or "
     "SolidWorks through its automation interface."),

    "06_meaning": ("What it means for your next part",
     "Most of what gets printed in a home shop is a one-off: a bracket for a sensor, a jig to hold "
     "a board while you solder it, a mount, a box for the thing you just built. The loop I ran "
     "here, describe the part, have the agent build it parametrically with a probe harness, print "
     "it, hold it, correct it, re-run the script, is the loop we already run with a human at the "
     "keyboard. Except that the keyboard part now takes minutes, and leaves a reviewable script and "
     "a self-test behind. "
     "Three cautions. The agent's confidence tells you nothing about its correctness on anything "
     "it cannot measure, and in CAD that is everything. Every print I did without a section view "
     "first, I did twice. The physics has to come from somewhere, and the quarter-wave mistake "
     "would have shipped. And treat the scripts, not the live CAD document, as the source of "
     "truth, under version control. The one time a parameter was tuned in the Fusion window "
     "instead of the script, the next run of the setup script silently reset it."),
}

SHOTS = [(k, _OVERRIDES[k][0], _OVERRIDES[k][1]) if k in _OVERRIDES else (k, n, t) for k, n, t in _BASE]
