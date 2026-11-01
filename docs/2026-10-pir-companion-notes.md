# PIR companion: what was built and what the numbers say

A Panasonic EKMC1603111 PIR sits in a bezel on the shell's wing, next to the
RD-03D radar, and reports into the same stair-light flow. This note records
the wiring, the orientation, a week of comparison data from the wall, and the
flow change that data forced. Design and plan: `superpowers/specs/2026-10-11-pir-companion-design.md`,
`superpowers/plans/2026-10-11-pir-companion-mains.md`.

## Wiring and orientation

| PIR (bottom view, tabs at 3 and 9 o'clock) | XIAO ESP32-C6 |
| --- | --- |
| VDD, the single pin at 12 o'clock | 3V3 |
| GND, lower left | GND |
| OUT, lower right | D1 (GPIO1), internal pull-down |

The sensor's output stage sources VDD on detection and floats otherwise, with a
100 µA ceiling, so the pull-down inside the ESP32-C6 is the whole interface.
The datasheet gives up to 30 s of undefined output after power-up; the first
events after a boot are the sensor settling. No decoupling capacitor was
fitted at the sensor; the leads are a few centimetres from the XIAO's
regulator and no false triggers were seen in a 75 s idle capture on the wall.

The case hangs with the XIAO end down (`pirTiltSign` +1 in
`case/fusion_scripts/02_backplate.py`), confirmed on the wall 2026-10-11 and
unchanged for the 2026-10-27 plate. The PIR bore is cut 18° off the radar's
axis so the sensor looks outward and down the stairs.

## Firmware

`RD03D_ENABLE_PIR` (default on, off in the access-point image),
`RD03D_PIR_GPIO` (1) and `RD03D_PIR_HOLD_MS` (1500). A rising edge goes
interrupt → queue → task → gate; edges inside the hold window extend it and
do not publish. Each event is one `<name>/pir` message carrying the event
count, the SNTP-synced time in ms, and the radar's nearest target at that
instant, or `null` when the radar saw nothing. `<name>/pir/state` is 1 while
the window is open.

## What the wall data says

The flow's "compare log" writes one line per trigger episode: which sensor
fired first, the delay until the other fired, the radar position carried by
the PIR event, and the PIR event's one-way latency (publish time stamped on
the node, receipt time on the Pi). Between 2026-10-25 and 2026-11-01 it
logged 478 episodes.

| | |
| --- | --- |
| Episodes | 478 |
| PIR fired first | 445 (93 %) |
| Both sensors fired in the episode | 243 |
| PIR lead over the radar, when both fired | median 4.7 s, quartiles 2.3 s and 13.5 s |
| Radar lead, the 22 episodes it won | median 1.0 s |
| PIR one-way latency | median 74 ms, 90th percentile 129 ms, minimum 18 ms |

The latency number is the one the battery variant's gate asks for: the
mains-mode baseline is about 75 ms from PIR edge to Node-RED, nearly all of it
WiFi and broker time. 14 of 467 latencies were over a second; those cluster
right after boots, before SNTP had settled, and were excluded from the
percentiles.

The PIR's lead is not a faster sensor so much as a longer reach. 141 PIR
events carried a radar position, and 109 of those were beyond the zone's 4 m
limit, out to 5.7 m. The PIR fires on someone walking toward the stairs while
the radar is still watching them from outside the zone. That is the early
warning the companion was meant to give.

At first power-up a hand wave triggered the PIR out to 5 m, the farthest
distance tried, which the wall data above bears out.

## The flow change the data forced

With `SOURCE = "either"`, every PIR event extended the 60 s hold the same way
an in-zone radar target does. Because the PIR's cone reaches past the zone
and well off its axis, anyone moving within view kept the light on, and the
light took much longer than a minute to go off after the stairs were empty.
Since 2026-11-01 the PIR may only start the light: a "light state" node
remembers whether the hold is running (fed by the trigger's ON/OFF and by the
manual-OFF reset), and the source switch drops PIR events while it is. The
hold then ends 60 s after the last in-zone radar target, as it did before the
PIR, and the early switch-on is kept. See `node-red/README.md`.

## The spare unit

The installed node is a second board built from the same branch with
`RD03D_NODE_NAME="rd03d2"`; the flow was repointed at its topics instead of
renaming the board, so the two never shared a name on the air. The first
board, retired, still carries firmware that answers as `rd03d`.
