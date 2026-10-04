"""Narration text per shot. Imported by the audio and frame builders."""

SHOTS = [
    ("01_open", "Cold open",
     "This is a staircase light. It comes on before anyone reaches the first step, because a "
     "24 gigahertz radar in a printed case is watching the approach, and a four node Node-RED flow "
     "is controlling the relay. That is the whole gadget, and it is not why I made this video. "
     "Over four weeks of evenings, an AI agent wrote the firmware, the web chart you are looking at, "
     "the automation, and the CAD for the enclosure, driving my own copy of Fusion 360 while I "
     "watched. I was the reviewer and the lab tech. This is what that looked like, and where the "
     "reviewer earned his keep."),

    ("02_thing", "The thing itself",
     "The sensor is an Ai-Thinker RD-03D, a 24 gigahertz frequency-modulated continuous-wave "
     "module that tracks up to three targets and reports position and radial velocity over a "
     "serial link, thirty bytes per frame. It is wired to a Seeed XIAO ESP32-C6, a thumbnail-sized "
     "RISC-V board with WiFi. The case is two printed parts. The back plate is eight millimetres "
     "thick and carries the radar bay, posts for the XIAO, five cantilever retention clips, a USB-C "
     "power jack with its capacitor cradled inside, and six LEGO Technic holes on an eight "
     "millimetre pitch, so the whole thing hangs off a Technic ball joint and can be aimed. "
     "The shell has a thinned radome step over the antennas and a boss that holds the XIAO down. "
     "It printed in PETG on a 0.6 millimetre nozzle with no supports, after seven revisions of "
     "the plate."),

    ("03_firmware", "The firmware loop",
     "Every feature followed the same loop. I described what I wanted in a paragraph. The agent "
     "wrote a short design spec, I argued with it, and it wrote a numbered plan and worked through "
     "it, testing as it went. Ten of those spec and plan pairs are in the repository, dated, and "
     "they read like a lab notebook. The radar frame parser was written as plain C and tested on "
     "the Mac before it touched the board, and the MQTT throttle, which decides when a target has "
     "moved enough to be worth publishing, is a pure function with its own tests. Nineteen host "
     "tests in all. Over-the-air updates got a deliberate drill: we flashed an image built to fail, "
     "watched it boot, miss its ninety-second window, and roll itself back to the previous "
     "firmware. The agent also walked into real traps. The access-point variant rolled back after "
     "every update, because the rollback cancel waited for an IP address, and in access-point mode "
     "no IP event ever fires. One line to fix. An evening to find."),

    ("04_cad", "Fusion, driven live",
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
     "package with a scripting API can be driven the same way, and SolidWorks, with its mature "
     "automation interface, is if anything the easier target."),

    ("05_catches", "Where the human earned his keep",
     "Now the honest part: what the agent got confidently wrong, and how I caught it. "
     "First, the board was resting on its connector. The agent sized the support bars from the "
     "board's overall thickness, which includes a connector that sticks out the back. The bare "
     "PCB is nearly four millimetres further in, so in the first print the radar sat on the "
     "connector and nothing else. I measured the board's rear profile, found two component-free "
     "bands, and the bars moved to bear on bare PCB there, with the connector hanging free. "
     "Second, the radome gap. At 24 gigahertz the wavelength, lambda, equals c over f: twelve and "
     "a half millimetres. The agent had assured me several times that the air gap from the antenna "
     "to the inside of the radome was about a millimetre. It had measured from the tallest chip, "
     "not from the antenna plane. The true gap was 3.1 millimetres, and a quarter wavelength is "
     "3.125. At a quarter-wave gap, the reflection off the radome travels an extra half wavelength "
     "out and back, picks up its phase flip at the plastic, and arrives back at the antenna in "
     "phase with the transmitted wave. That is the maximum mismatch: an anti-reflection coating, "
     "run backwards. The rule became: keep the gap under a tenth of a wavelength. The radome came "
     "down to 1.21 millimetres over both antenna groups, with 3.1 millimetres of solid plastic in "
     "front, and the exterior still flat. I caught that from a section view, not from the script. "
     "Third, the antenna was going in sideways. The two receive channels that give the module its "
     "angle are spaced across the board's short axis, about half a wavelength apart, so the wide "
     "sixty-degree fan opens across the width, and the beam is narrow along the length. For a "
     "staircase the fan has to be vertical, so the board mounts landscape. "
     "Fourth, the printer disagreed with the design. Walls of 0.6 millimetres on a 0.6 millimetre "
     "nozzle. A tape recess that turned the first layer into a rim. And later, slender slotted "
     "clips with a correct two-percent strain analysis, which held the board about as well as a "
     "wet noodle. The slots came out. The clip is now a plain stretch of wall with a lip. It takes "
     "a firm push. That is fine."),

    ("06_meaning", "What it means for us",
     "Nearly everything here has an analogue at work: fixtures, cable guides, probe holders, "
     "optical mounts, test-head carriers. The loop I ran at home, describe the part, have the agent "
     "build it parametrically with a probe harness, print it, hold it, correct it, re-run the "
     "script, is the loop we already run with a human at the keyboard. Except that the keyboard "
     "part now takes minutes, and leaves a reviewable script and a self-test behind. "
     "Three cautions. The agent's confidence tells you nothing about its correctness on anything "
     "it cannot measure, and in CAD that is everything. Every print I did without a section view "
     "first, I did twice. The physics has to come from somewhere, and the quarter-wave mistake "
     "would have shipped. And the agent you use for company parts and company firmware has to be "
     "the company-provisioned one, on company accounts. This project was personal, on personal "
     "tools, and I kept it that way."),

    ("07_close", "Close",
     "The light goes off sixty seconds after the last step. The firmware, the Fusion scripts, the "
     "Node-RED flow, and the dated design notes are all in the repository. Everything you have seen "
     "was synthesized from them: renders of the actual STL files, a recreation of the live radar "
     "chart, and a synthetic voice."),
]
