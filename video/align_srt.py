#!/usr/bin/env python3
"""Write an SRT whose cue times are snapped to the real pauses in the synthesized narration.

    RD_VARIANT=hackaday uv run --quiet --with numpy python3 align_srt.py "Ava (Premium)" [rate]

make_audio.py spaces sentences by character count, which drifts by up to a couple of
seconds inside a long shot. This script splits each sentence into caption-sized chunks,
estimates each chunk's share of the shot by synthesizing it on its own, then snaps every
boundary to the nearest silence found in audio<variant>/<shot>.aiff. Run it after
make_audio.py; it reads the same narration and durations and writes
narration<variant>_aligned.srt.
"""
import json, os, re, subprocess, sys, tempfile, wave
import numpy as np

VARIANT = os.environ.get("RD_VARIANT", "")
if VARIANT == "hackaday":
    from narration_hackaday import SHOTS
else:
    from narration import SHOTS
SUFFIX = ("_" + VARIANT) if VARIANT else ""
AUDIO = "audio" + SUFFIX
voice = sys.argv[1] if len(sys.argv) > 1 else "Ava (Premium)"
rate = sys.argv[2] if len(sys.argv) > 2 else "172"
LEAD, TAIL = 0.6, 0.9      # must match make_audio.py / build_video.py
MAXC = 84                  # two caption lines of 42 characters
FFMPEG = "/opt/homebrew/bin/ffmpeg"

src = open("make_audio.py").read()
SPOKEN = eval(src[src.index("SPOKEN = [") + 9: src.index("]\n", src.index("SPOKEN = [")) + 1])
def spoken(t):
    for a, b in SPOKEN: t = t.replace(a, b)
    return t

def envelope(path):
    with tempfile.NamedTemporaryFile(suffix=".wav") as f:
        subprocess.run([FFMPEG, "-v", "error", "-y", "-i", path, "-ar", "16000", "-ac", "1", f.name], check=True)
        w = wave.open(f.name); x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(float)
    n = 160; x = x[: len(x) // n * n].reshape(-1, n)
    return np.sqrt((x ** 2).mean(1))          # 10 ms frames

def speech_len(text):
    with tempfile.NamedTemporaryFile(suffix=".aiff") as f:
        subprocess.run(["say", "-v", voice, "-r", rate, "-o", f.name, spoken(text)], check=True)
        e = envelope(f.name)
    v = np.nonzero(e > e.max() * 0.02)[0]
    return (v[-1] - v[0] + 1) / 100.0

def pauses(e, min_ms=90):
    sil = e < e.max() * 0.02; out = []; i = 0
    while i < len(sil):
        if sil[i]:
            j = i
            while j < len(sil) and sil[j]: j += 1
            if (j - i) * 10 >= min_ms and i > 0 and j < len(sil): out.append((i / 100.0, j / 100.0))
            i = j
        else: i += 1
    return out

def chunks(sentence):
    """Split a sentence at clause punctuation into pieces of at most MAXC characters."""
    parts = re.split(r"(?<=[,;:])\s+", sentence); out = []; cur = ""
    for p in parts:
        if cur and len(cur) + 1 + len(p) > MAXC: out.append(cur); cur = p
        else: cur = (cur + " " + p).strip()
    if cur: out.append(cur)
    final = []
    for c in out:                              # a long clause with no punctuation: break near the middle
        while len(c) > 95:
            mid = len(c) // 2
            cands = [m.start() for m in re.finditer(r" (?=(?:that|and|before|against|from|which|are|to the) )", c)] or \
                    [m.start() for m in re.finditer(" ", c)]
            k = min(cands, key=lambda x: abs(x - mid))
            if not 25 < k < len(c) - 25: k = min([m.start() for m in re.finditer(" ", c)], key=lambda x: abs(x - mid))
            final.append(c[:k]); c = c[k + 1:]
        final.append(c)
    return final

def ts(s):
    ms = int(round(s * 1000)); h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); sec, ms = divmod(ms, 1000)
    return "%02d:%02d:%02d,%03d" % (h, m, sec, ms)

durs = json.load(open(os.path.join(AUDIO, "durations.json")))
cues = []; t0 = 0.0; snapped = total = 0
odd = []; ratios = []
for key, title, text in SHOTS:
    e = envelope(os.path.join(AUDIO, key + ".aiff"))
    v = np.nonzero(e > e.max() * 0.02)[0]; first, last = v[0] / 100.0, (v[-1] + 1) / 100.0
    P = pauses(e)
    items = []                                  # (text, ends_sentence)
    for s in re.split(r"(?<=[.!?:])\s+", text.strip()):
        cs = chunks(s)
        items += [(c, i == len(cs) - 1) for i, c in enumerate(cs)]
    L = np.array([speech_len(c) for c, _ in items])
    # Choose a pause for each break jointly: a run of chunks between two chosen pauses should last
    # about as long as those chunks do when spoken on their own. A break may stay unsnapped (some
    # commas carry no silence), at a cost; it is then placed in proportion inside its run.
    n = len(items); cum = np.concatenate([[0.0], np.cumsum(L)])
    INF = 1e9; skip = [2.5 if items[k][1] else 0.35 for k in range(n - 1)]
    best = {(-1, -1): (0.0, None)}             # (break index, pause index) -> (cost, previous state)
    order = [(-1, -1)]
    for k in range(n):                         # break k closes chunk k; k == n-1 is the end of the shot
        for q in (range(len(P)) if k < n - 1 else [len(P)]):
            end_t = P[q][0] if q < len(P) else last
            cand = None
            for (pk, pq) in order:
                if pk >= k or pq >= q or k - pk > 5: continue
                start_t = first if pq < 0 else P[pq][1]
                if end_t <= start_t: continue
                c = best[(pk, pq)][0] + abs((end_t - start_t) - (cum[k + 1] - cum[pk + 1])) + sum(skip[pk + 1:k])
                if q < len(P): c -= 0.5 * min(P[q][1] - P[q][0], 0.4) * (1.0 if items[k][1] else 0.3)
                if cand is None or c < cand[0]: cand = (c, (pk, pq))
            if cand: best[(k, q)] = cand
        order = [st for st in best]
    st = (n - 1, len(P)); chosen = {}
    while st and st != (-1, -1):
        chosen[st[0]] = st[1]; st = best[st][1]
    bounds = []; ks = sorted(chosen)
    for k in range(n - 1):
        total += 1
        if k in chosen: bounds.append(P[chosen[k]]); snapped += 1
        else:                                   # proportional point inside its run
            pk = max([x for x in ks if x < k], default=-1); nk = min(x for x in ks if x > k)
            a = first if pk < 0 else P[chosen[pk]][1]; b = P[chosen[nk]][0] if chosen[nk] < len(P) else last
            x = a + (b - a) * (cum[k + 1] - cum[pk + 1]) / (cum[nk + 1] - cum[pk + 1]); bounds.append((x, x))
    start = first
    for k, (c, _) in enumerate(items):
        end = bounds[k][0] if k < len(bounds) else last
        r = (end - start) / L[k]               # spoken length in context vs on its own
        if not 0.8 < r < 1.25: odd.append("%s  x%.2f  %s" % (key, r, c[:60]))
        ratios.append(r)
        cues.append((t0 + LEAD + max(start - 0.05, 0), t0 + LEAD + end + 0.15, c))
        if k < len(bounds): start = bounds[k][1]
    t0 += durs[key] + LEAD + TAIL
for i in range(len(cues) - 1):                 # never overlap the next cue
    a, b, c = cues[i]; cues[i] = (a, min(b, cues[i + 1][0] - 0.02), c)
out = "narration%s_aligned.srt" % SUFFIX
open(out, "w").write("\n".join("%d\n%s --> %s\n%s\n" % (i + 1, ts(a), ts(b), c) for i, (a, b, c) in enumerate(cues)))
print("%s: %d cues, %d of %d boundaries snapped to a pause, longest cue %.1f s, longest text %d chars"
      % (out, len(cues), snapped, total, max(b - a for a, b, c in cues), max(len(c) for a, b, c in cues)))
print("in-context / isolated length: median %.2f, range %.2f to %.2f; %d cues outside 0.80-1.25"
      % (np.median(ratios), min(ratios), max(ratios), len(odd)))
for o in odd: print("  check:", o)
