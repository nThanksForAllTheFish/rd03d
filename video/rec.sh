#!/bin/bash
# Narration take recorder.  rec.sh start <shot> [mic name]   |   rec.sh stop   |   rec.sh status
# The mic is an avfoundation input name (ffmpeg -f avfoundation -list_devices true -i ""); or set RD_MIC.
# Records mono 48 kHz WAV from the chosen microphone into takes/<shot>_<n>.wav until `stop`.
cd "$(dirname "$0")"; mkdir -p takes
case "$1" in
  start)
    shot="$2"; mic="${3:-${RD_MIC:?pass the avfoundation input name as the 3rd argument or set RD_MIC}}"
    [ -f takes/.pid ] && { echo "already recording (pid $(cat takes/.pid))"; exit 1; }
    n=$(ls takes/${shot}_*.wav 2>/dev/null | wc -l | tr -d ' '); n=$((n+1))
    out="takes/${shot}_${n}.wav"
    /opt/homebrew/bin/ffmpeg -hide_banner -loglevel error -y -f avfoundation -i ":${mic}" -t 900 -ac 1 -ar 48000 "$out" </dev/null >takes/.log 2>&1 &
    echo $! > takes/.pid; echo "$out" > takes/.current; sleep 1
    kill -0 $(cat takes/.pid) 2>/dev/null && echo "recording $out from '$mic'" || { echo "ffmpeg failed:"; cat takes/.log; rm -f takes/.pid; exit 1; }
    ;;
  stop)
    [ -f takes/.pid ] || { echo "not recording"; exit 1; }
    kill -INT $(cat takes/.pid); sleep 1.5; rm -f takes/.pid; out=$(cat takes/.current)
    d=$(/opt/homebrew/bin/ffprobe -v error -show_entries format=duration -of csv=p=0 "$out")
    /opt/homebrew/bin/ffmpeg -hide_banner -i "$out" -af volumedetect -f null - 2>&1 | grep -E "mean_volume|max_volume" | sed 's/.*\] //' | tr '\n' ' '
    echo "| $out ${d%.*} s"
    ;;
  status) [ -f takes/.pid ] && echo "recording $(cat takes/.current)" || echo "idle"; ls -la takes/*.wav 2>/dev/null ;;
esac
