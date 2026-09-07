# rd03d_uart

XIAO ESP32-C6 firmware that reads an Ai-Thinker RD-03D 24GHz mmWave radar over
UART1 and prints decoded targets to the USB-C serial console.

## Wiring

| RD-03D | XIAO ESP32-C6 |
| --- | --- |
| TX | D7 (GPIO17) |
| RX | D6 (GPIO16) |
| 5V | 5V |
| GND | GND |

Radar UART: 256000 baud, 8N1.

## Build & flash

```bash
source ~/esp/esp-idf-v5.5/export.sh
idf.py set-target esp32c6   # first time only
idf.py -p /dev/cu.usbmodem11101 flash monitor
```

(The port may enumerate with a different number; check `ls /dev/cu.usbmodem*`.)

## Output

One line per radar frame (up to 3 targets), plus link stats every 5 s:

```
T1: x=-123mm y=456mm v=-12cm/s | T2: --- | T3: ---
I (5210) rd03d: link stats: dropped=0 bad_frames=0
```

`dropped` counts parser resync bytes only (not any UART driver-level loss);
`bad_frames` counts frames with a corrupt tail. Both should stay flat while a
monitor is attached.

## WiFi + web UI

The firmware joins the WiFi network configured via `idf.py menuconfig`
(*RD03D Configuration* → SSID/password; stored only in the untracked
`sdkconfig`, 2.4 GHz WPA2 networks only) and serves a live radar chart:

- Open **http://rd03d.local** from any browser on the same network (Mac or
  phone). The page shows targets on an XY chart with trails, plus link stats.
- Data path: `GET /ws` WebSocket pushes one JSON message per radar frame,
  e.g. `{"t":[{"x":-551,"y":550,"v":0},null,null],"dropped":0,"bad":0}`
  (x/y in mm, v in cm/s, absent targets `null`).
- At boot the firmware puts the radar in multi-target mode itself; viewers
  never send radar commands.
- Untethered use: power the XIAO from a USB power bank; the USB console is
  optional diagnostics only.

## OTA firmware updates

The device carries two firmware slots with automatic rollback — a bad update
reverts to the previous firmware by itself (it must join WiFi and start the
web server within 90 s to become permanent).

Update over WiFi (no USB needed):

```bash
idf.py build
curl -X POST --data-binary @build/rd03d_uart.bin http://rd03d.local/update
```

or open **http://rd03d.local/update** in a browser and upload
`build/rd03d_uart.bin`. The running version shows at `/version`, on the
update page, and in the chart HUD.

USB flashing is only needed for first-time setup (partition table changes
require `idf.py erase-flash flash`).

Note: after any OTA, a plain USB `idf.py flash` writes to `ota_0` but the
device may keep booting the newer image in `ota_1` (otadata still points
there). For a USB reflash to take effect after OTAs, use
`idf.py erase-otadata flash` (or a full `erase-flash flash`).

## Host-side parser tests

```bash
cd tests
cc -Wall -Wextra -o test_rd03d test_rd03d.c ../main/rd03d.c && ./test_rd03d
```

Frame format and sign-magnitude decoding match
`../RD03D_RadarChart/README.md` (Processing visualizer for the same sensor).
