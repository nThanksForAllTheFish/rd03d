#!/usr/bin/env python3
"""Render text with a macOS Personal Voice by speaking it aloud and capturing system audio.

    uv run --quiet --with pyobjc-framework-AVFoundation --with pyobjc-framework-ScreenCaptureKit \
        python3 pv_capture.py <voice name> <rate_wpm> <out.caf> <text>

Apple only lets a Personal Voice be spoken through the device speaker (no file rendering:
AVSpeechSynthesizer.writeUtterance returns no buffers for it, speakUtterance works). So this
script starts a ScreenCaptureKit system-audio capture, speaks the utterance, stops, and trims
the silence either side. Needs the Screen & System Audio Recording permission for the
calling app, and nothing else should be playing audio on the Mac while it runs.
The captured signal is tapped before the output volume control, so the speaker volume can be low.
"""
import os, sys, time
import AVFoundation as AV
import ScreenCaptureKit as SC
from Foundation import NSRunLoop, NSDate, NSObject, NSURL
from CoreMedia import CMTimeMake

def pump(s): NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(s))

want, rate_wpm, out_path, text = sys.argv[1], float(sys.argv[2]), sys.argv[3], " ".join(sys.argv[4:])
voice = [v for v in AV.AVSpeechSynthesisVoice.speechVoices() if v.name() == want or v.identifier() == want]
if not voice: sys.exit("voice %r not found" % want)
voice = voice[0]

# ---- shareable content (triggers the TCC prompt the first time)
box = {}
SC.SCShareableContent.getShareableContentExcludingDesktopWindows_onScreenWindowsOnly_completionHandler_(
    False, False, lambda c, e: box.update(c=c, e=e))
t0 = time.time()
while "c" not in box and time.time() - t0 < 120: pump(0.1)
if box.get("e") or not box.get("c"):
    sys.exit("ScreenCaptureKit unavailable: %s (grant Screen & System Audio Recording to the app, then retry)" % box.get("e"))
display = box["c"].displays()[0]
flt = SC.SCContentFilter.alloc().initWithDisplay_excludingWindows_(display, [])
cfg = SC.SCStreamConfiguration.alloc().init()
cfg.setCapturesAudio_(True); cfg.setExcludesCurrentProcessAudio_(False)
cfg.setSampleRate_(48000); cfg.setChannelCount_(1)
cfg.setWidth_(8); cfg.setHeight_(8); cfg.setMinimumFrameInterval_(CMTimeMake(1, 2)); cfg.setShowsCursor_(False)

raw = os.path.splitext(out_path)[0] + ".raw.caf"
if os.path.exists(raw): os.remove(raw)
url = NSURL.fileURLWithPath_(raw)
writer, err = AV.AVAssetWriter.alloc().initWithURL_fileType_error_(url, AV.AVFileTypeCoreAudioFormat, None)
if err: sys.exit("writer: %s" % err)
settings = {AV.AVFormatIDKey: 1819304813, AV.AVSampleRateKey: 48000.0, AV.AVNumberOfChannelsKey: 1,
            AV.AVLinearPCMBitDepthKey: 16, AV.AVLinearPCMIsFloatKey: False, AV.AVLinearPCMIsBigEndianKey: False,
            AV.AVLinearPCMIsNonInterleaved: False}
winput = AV.AVAssetWriterInput.assetWriterInputWithMediaType_outputSettings_(AV.AVMediaTypeAudio, settings)
winput.setExpectsMediaDataInRealTime_(True)
writer.addInput_(winput)

state = {"started": False, "n": 0, "dropped": 0}
class Out(NSObject):
    def stream_didOutputSampleBuffer_ofType_(self, stream, sbuf, typ):
        if typ != SC.SCStreamOutputTypeAudio: return
        if not state["started"]:
            writer.startWriting()
            from CoreMedia import CMSampleBufferGetPresentationTimeStamp
            writer.startSessionAtSourceTime_(CMSampleBufferGetPresentationTimeStamp(sbuf))
            state["started"] = True
        if winput.isReadyForMoreMediaData():
            winput.appendSampleBuffer_(sbuf); state["n"] += 1
        else:
            state["dropped"] += 1
out = Out.alloc().init()
stream = SC.SCStream.alloc().initWithFilter_configuration_delegate_(flt, cfg, None)
ok, err = stream.addStreamOutput_type_sampleHandlerQueue_error_(out, SC.SCStreamOutputTypeAudio, None, None)
if not ok: sys.exit("addStreamOutput: %s" % err)
done = {}
stream.startCaptureWithCompletionHandler_(lambda e: done.update(start=e or "ok"))
t0 = time.time()
while "start" not in done and time.time() - t0 < 30: pump(0.1)
if done.get("start") != "ok": sys.exit("startCapture: %s" % done.get("start"))
pump(0.6)  # settle

# ---- speak
ev = {}
class D(NSObject):
    def speechSynthesizer_didFinishSpeechUtterance_(self, s, u): ev["finish"] = time.time()
    def speechSynthesizer_didCancelSpeechUtterance_(self, s, u): ev["finish"] = time.time()
d = D.alloc().init()
synth = AV.AVSpeechSynthesizer.alloc().init(); synth.setDelegate_(d)
utt = AV.AVSpeechUtterance.speechUtteranceWithString_(text); utt.setVoice_(voice)
utt.setRate_(max(0.0, min(1.0, 0.5 * rate_wpm / 178.0)))
t_speak = time.time(); synth.speakUtterance_(utt)
while "finish" not in ev and time.time() - t_speak < 900: pump(0.05)
pump(0.5)

# ---- stop and finish
stream.stopCaptureWithCompletionHandler_(lambda e: done.update(stop=e or "ok"))
t0 = time.time()
while "stop" not in done and time.time() - t0 < 30: pump(0.1)
winput.markAsFinished()
fin = {}
writer.finishWritingWithCompletionHandler_(lambda: fin.update(ok=True))
t0 = time.time()
while "ok" not in fin and time.time() - t0 < 30: pump(0.1)
if writer.status() != 2: sys.exit("writer failed: %s" % writer.error())

# ---- trim silence either side (threshold -45 dB), keep 0.05 s pad
import subprocess
subprocess.run(["/opt/homebrew/bin/ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", raw,
                "-af", "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,areverse,"
                       "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,areverse",
                out_path], check=True)
os.remove(raw)
dur = subprocess.run(["/opt/homebrew/bin/ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", out_path],
                     capture_output=True, text=True).stdout.strip()
print("captured %d buffers (%d dropped), spoke %.2f s, trimmed file %.2f s -> %s"
      % (state["n"], state["dropped"], ev.get("finish", time.time()) - t_speak, float(dur), out_path))
