#!/usr/bin/env python3
"""Synthesize the narration per shot with macOS `say`, record durations, write the SRT.

    uv run --quiet python3 make_audio.py "Ava (Premium)" [rate]

Run from the directory that holds narration.py. Writes audio/<shot>.aiff,
audio/durations.json (read by build_video.py) and narration.srt.

The voice name must appear EXACTLY as `say -v '?'` lists it. `say` does not
error on an unknown voice -- it silently falls back to the system default --
so this script checks the list first and refuses. Premium/Enhanced voices are
downloaded in System Settings > Accessibility > Spoken Content > System Voice >
Manage Voices... and then show up as e.g. "Ava (Premium)" or "Tom (Enhanced)".

Any voice change alters the durations, so re-render every shot afterwards
(build_video.py render <shot> for each, then build_video.py concat).
"""
import json, os, re, subprocess, sys

VARIANT = os.environ.get("RD_VARIANT", "")          # "" = internal, "hackaday" = public
if VARIANT == "hackaday":
    from narration_hackaday import SHOTS
else:
    from narration import SHOTS
SUFFIX = ("_" + VARIANT) if VARIANT else ""
AUDIO = "audio" + SUFFIX

voice = sys.argv[1] if len(sys.argv) > 1 else "Samantha"
rate = sys.argv[2] if len(sys.argv) > 2 else "172"

# Spoken-form substitutions: applied ONLY to the text sent to `say`. The SRT and the
# on-screen text keep the written forms. Order matters (longer phrases first).
SPOKEN = [
    ("Seeed XIAO ESP32-C6", "Seed Studio SheOw E S P thirty two C 6"),
    ("XIAO ESP32-C6", "SheOw E S P thirty two C 6"),
    ("XIAO", "SheOw"),
    ("Fusion 360", "Fusion three sixty"),
    ("RD-03D", "R, D zero three D"),
    ("RISC-V", "RISC Five"),
    ("written as plain C and", "written as plain, C, and"),
    ("Node-RED flow,", "Node, Red, flow,"),
    ("Node-RED flow", "Node, Red, flow,"),
    ("OpenSCAD", "Open S CAD"),
    ("0.6 millimetre", "point six millimetre"),
    ("0.6 mm", "point six millimetre"),
]
def spoken(text):
    for a, b in SPOKEN:
        text = text.replace(a, b)
    return text

installed = [ln.split("  ")[0].strip() for ln in subprocess.run(["say", "-v", "?"], capture_output=True, text=True).stdout.splitlines()]
if voice not in installed:
    sys.exit("voice %r is not installed. `say` would silently use the default instead.\nInstalled English voices:\n  "
             % voice + "\n  ".join(v for v in installed if v))

LEAD, TAIL = 0.6, 0.9      # must match build_video.py
os.makedirs(AUDIO, exist_ok=True)
durs = {}
for key, title, text in SHOTS:
    aiff = os.path.join(AUDIO, key + ".aiff")
    subprocess.run(["say", "-v", voice, "-r", rate, "-o", aiff, spoken(text)], check=True)
    out = subprocess.run(["/opt/homebrew/bin/ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", aiff], capture_output=True, text=True).stdout.strip()
    durs[key] = float(out)
    print("%-12s %6.1f s" % (key, durs[key]))
json.dump(durs, open(os.path.join(AUDIO, "durations.json"), "w"), indent=1)
print("total %.1f s  voice=%s rate=%s" % (sum(durs.values()), voice, rate))

def ts(s):
    m, sec = divmod(s, 60); h, m = divmod(int(m), 60)
    return "%02d:%02d:%02d,%03d" % (h, m, int(sec), int(round((sec - int(sec)) * 1000)))
cues = []; t0 = 0.0; n = 1
for key, title, text in SHOTS:
    sents = re.split(r"(?<=[.!?:])\s+", text.strip()); total = sum(len(s) for s in sents); cur = t0 + LEAD
    for s in sents:
        d = durs[key] * len(s) / total
        cues.append("%d\n%s --> %s\n%s\n" % (n, ts(cur), ts(cur + d - 0.05), s)); n += 1; cur += d
    t0 += durs[key] + LEAD + TAIL
open("narration%s.srt" % SUFFIX, "w").write("\n".join(cues))
print("narration%s.srt: %d cues, video length %.1f s" % (SUFFIX, n - 1, t0))
