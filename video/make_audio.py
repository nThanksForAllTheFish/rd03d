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
    ("RD-03D", "arr-dee-zero-three-dee"),
    ("RISC-V", "RISC Five"),
    ("written as plain C and", "written as plain, C, and"),
    ("Node-RED", "Node Redd"),
    ("OpenSCAD", "Open S CAD"),
    ("0.6 millimetre", "point six millimetre"),
    ("0.6 mm", "point six millimetre"),
    ("recreation", "re creation"),          # re-creation, not the leisure word
    ("synthesized from them: renders", "synthesized from them. Renders"),   # a colon makes the voice rise; close the sentence
]
# Per-voice overrides (the author's Personal Voice reads some respellings differently from Ava).
PERSONAL_VOICE = os.environ.get("RD_PERSONAL_VOICE", "Personal Voice")   # name of your own Personal Voice, as `say -v ?` lists it
SPOKEN_BY_VOICE = {
    PERSONAL_VOICE: [
        ("RD-03D", "RD-zero-3D"),
        ("Seeed XIAO ESP32-C6", "Seed Studio SheOw, ESP thirty two C6"),
        ("XIAO ESP32-C6", "SheOw, ESP thirty two C6"),
        ("XIAO", "SheOw"),
        ("written as plain C and", "written as plain C, and"),
        ("0.6 millimetre", "zero point six millimetre"),
        ("0.6 mm", "zero point six millimetre"),
    ],
}
def spoken(text, voice_name=None):
    rules = dict(SPOKEN)
    rules.update(dict(SPOKEN_BY_VOICE.get(voice_name or voice, [])))
    for a, b in sorted(rules.items(), key=lambda kv: -len(kv[0])):   # longest written form first
        text = text.replace(a, b)
    return text

installed = [ln.split("  ")[0].strip() for ln in subprocess.run(["say", "-v", "?"], capture_output=True, text=True).stdout.splitlines()]
UV = os.path.expanduser("~/.local/bin/uv")
AV_CMD = [UV, "run", "--quiet", "--with", "pyobjc-framework-AVFoundation", "python3",
          os.path.join(os.path.dirname(os.path.abspath(__file__)), "av_speak.py")]
engine = "say"
if voice not in installed:
    # Not a `say` voice. A macOS Personal Voice (the user's own recorded voice) is only
    # reachable through AVFoundation; see av_speak.py. Check there before giving up.
    av_list = subprocess.run(AV_CMD + ["--list"], capture_output=True, text=True).stdout
    hits = [ln for ln in av_list.splitlines() if ln.startswith(voice + " ") or (" " + voice) in ln]
    if hits and "[personal]" in hits[0]:
        # Apple only lets a Personal Voice be spoken aloud: capture the speaker output instead.
        engine = "capture"
        AV_CMD = [UV, "run", "--quiet", "--with", "pyobjc-framework-AVFoundation", "--with", "pyobjc-framework-ScreenCaptureKit",
                  "--with", "pyobjc-framework-CoreMedia", "python3",
                  os.path.join(os.path.dirname(os.path.abspath(__file__)), "pv_capture.py")]
        print("Personal Voice: capturing from the speaker output in real time; keep the Mac silent.")
    elif hits:
        engine = "av"
    else:
        sys.exit("voice %r is not installed. `say` would silently use the default instead.\n"
                 "Installed `say` voices:\n  " % voice + "\n  ".join(v for v in installed if v)
                 + "\n\nAVFoundation voices (Personal Voice shows here once authorized):\n" + av_list)
print("engine:", engine)

LEAD, TAIL = 0.6, 0.9      # must match build_video.py
os.makedirs(AUDIO, exist_ok=True)
durs = {}
for key, title, text in SHOTS:
    aiff = os.path.join(AUDIO, key + ".aiff")
    if engine == "say":
        subprocess.run(["say", "-v", voice, "-r", rate, "-o", aiff, spoken(text, voice)], check=True)
    else:
        caf = aiff[:-5] + ".caf"
        subprocess.run(AV_CMD + [voice, rate, caf, spoken(text, voice)], check=True, stdout=subprocess.DEVNULL)
        subprocess.run(["/opt/homebrew/bin/ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", caf, aiff], check=True)
        os.remove(caf)
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
