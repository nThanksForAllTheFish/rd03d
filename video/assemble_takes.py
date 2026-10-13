#!/usr/bin/env python3
"""Turn the kept human takes (takes/keep/<shot>.wav) into the Hackaday shot audio + SRT.
Level-matches every take with EBU loudnorm (-16 LUFS, true peak -1.5 dB), writes
audio_hackaday/<shot>.aiff and durations.json, and the SRT with the same timing rules as make_audio.py."""
import json, os, re, subprocess
os.environ["RD_VARIANT"] = "hackaday"
from narration_hackaday import SHOTS
LEAD, TAIL = 0.6, 0.9
os.makedirs("audio_hackaday", exist_ok=True)
durs = {}
for key, title, text in SHOTS:
    src = f"takes/keep/{key}.wav"; dst = f"audio_hackaday/{key}.aiff"
    subprocess.run(["/opt/homebrew/bin/ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", src,
                    "-af", "highpass=f=70,loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", "48000", "-ac", "1", dst], check=True)
    durs[key] = float(subprocess.run(["/opt/homebrew/bin/ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", dst], capture_output=True, text=True).stdout)
    print("%-12s %6.1f s" % (key, durs[key]))
json.dump(durs, open("audio_hackaday/durations.json", "w"), indent=1)
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
open("narration_hackaday.srt", "w").write("\n".join(cues))
print("total %.1f s, video %.1f s, %d cues" % (sum(durs.values()), t0, n - 1))
