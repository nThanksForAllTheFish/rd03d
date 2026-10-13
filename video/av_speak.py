#!/usr/bin/env python3
"""Synthesize text to an audio file through Apple's AVSpeechSynthesizer.

    uv run --quiet --with pyobjc-framework-AVFoundation python3 av_speak.py --list
    uv run --quiet --with pyobjc-framework-AVFoundation python3 av_speak.py <voice> <rate_wpm> <out.caf> <text>

Why this exists: the `say` command cannot use a macOS Personal Voice (the user's own
recorded voice). Only apps that ask permission through AVFoundation can, and the
permission gate is System Settings > Accessibility > Personal Voice > "Allow Apps to
Request to Use Personal Voice". The same path works for any installed voice, so it is
also a second engine for Ava etc.

<voice> may be a voice name ("Ava (Premium)", or the Personal Voice's name as shown in
System Settings) or a full identifier. Personal voices are listed with [personal].
Output is CAF (PCM); convert with ffmpeg if AIFF/M4A is wanted.
"""
import sys, time
import AVFoundation as AV
from Foundation import NSRunLoop, NSDate, NSURL

def pump(seconds):
    NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(seconds))

def authorize():
    st = AV.AVSpeechSynthesizer.personalVoiceAuthorizationStatus()
    if st == 0:  # notDetermined -> ask (macOS shows a dialog attributed to the running process)
        box = {}
        AV.AVSpeechSynthesizer.requestPersonalVoiceAuthorizationWithCompletionHandler_(lambda s: box.__setitem__("s", s))
        t0 = time.time()
        while "s" not in box and time.time() - t0 < 120: pump(0.2)
        st = box.get("s", st)
    return {0: "notDetermined", 1: "denied", 2: "unsupported", 3: "authorized"}.get(st, st)

def voices():
    out = []
    for v in AV.AVSpeechSynthesisVoice.speechVoices():
        personal = bool(v.voiceTraits() & AV.AVSpeechSynthesisVoiceTraitIsPersonalVoice)
        out.append((v.name(), v.identifier(), v.language(), int(v.quality()), personal, v))
    return out

if len(sys.argv) >= 2 and sys.argv[1] == "--list":
    print("personal voice authorization:", authorize())
    for name, ident, lang, q, personal, _ in sorted(voices(), key=lambda t: (not t[4], -t[3], t[0])):
        if personal or q >= 2 or lang.startswith("en"):
            print("%-24s %-6s quality=%d %s  %s" % (name, lang, q, "[personal]" if personal else "", ident))
    sys.exit(0)

if len(sys.argv) < 5:
    sys.exit(__doc__)
want, rate_wpm, out_path, text = sys.argv[1], float(sys.argv[2]), sys.argv[3], " ".join(sys.argv[4:])
print("personal voice authorization:", authorize())
match = [t for t in voices() if t[0] == want or t[1] == want]
if not match:
    sys.exit("voice %r not found; run with --list" % want)
voice = match[0][5]

utt = AV.AVSpeechUtterance.speechUtteranceWithString_(text)
utt.setVoice_(voice)
# AVSpeechUtteranceDefaultSpeechRate (0.5) is roughly 175-180 wpm for English voices;
# map the wpm the rest of the pipeline uses onto that scale.
utt.setRate_(max(0.0, min(1.0, 0.5 * rate_wpm / 178.0)))

synth = AV.AVSpeechSynthesizer.alloc().init()
chunks = []
def on_buffer(buf):
    chunks.append(buf)
synth.writeUtterance_toBufferCallback_(utt, on_buffer)
t0 = time.time()
# writeUtterance delivers buffers asynchronously and ends with a zero-length buffer
while time.time() - t0 < 600:
    pump(0.1)
    if chunks and chunks[-1].frameLength() == 0: break
    if chunks and time.time() - t0 > 5 and all(c.frameLength() == 0 for c in chunks[-3:]): break
pcm = [c for c in chunks if c.frameLength() > 0]
if not pcm:
    sys.exit("no audio produced (voice not authorized, or unusable from this process)")
fmt = pcm[0].format()
url = NSURL.fileURLWithPath_(out_path)
settings = dict(fmt.settings())
f, err = AV.AVAudioFile.alloc().initForWriting_settings_error_(url, settings, None)
if err: sys.exit("cannot open %s: %s" % (out_path, err))
for c in pcm:
    ok, err = f.writeFromBuffer_error_(c, None)
    if err: sys.exit("write failed: %s" % err)
frames = sum(c.frameLength() for c in pcm)
print("wrote %s: %.2f s at %d Hz, voice=%s" % (out_path, frames / fmt.sampleRate(), int(fmt.sampleRate()), match[0][0]))
