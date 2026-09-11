# rd03d_uart

XIAO ESP32-C6 firmware that reads an Ai-Thinker RD-03D 24GHz mmWave radar over
UART1, prints decoded targets to the USB-C serial console, and serves a live
radar chart over WiFi.

The tree builds two images from the same sources:

| | Station (default) | Access point |
| --- | --- | --- |
| WiFi | joins an existing 2.4 GHz WPA2 network | is its own WPA2 access point |
| Chart at | http://rd03d.local | http://192.168.4.1 |
| MQTT | published | compiled out |
| Build dir | `build/` | `build.ap/` |
| Config | `sdkconfig` | `sdkconfig.ap` |

Use the AP image where the device is not allowed onto the local WiFi — a work
site that only admits registered hardware, or anywhere there is no network to
join.

## Wiring

| RD-03D | XIAO ESP32-C6 |
| --- | --- |
| TX | D7 (GPIO17) |
| RX | D6 (GPIO16) |
| 5V | 5V |
| GND | GND |

Radar UART: 256000 baud, 8N1.

## Build & flash

Find the port rather than assuming it — boards enumerate differently, and a
second board plugged into the same Mac will not get the same number:

```bash
ls /dev/cu.usbmodem*
```

With more than one board attached, confirm which is which before flashing.

Station image (joins your WiFi):

```bash
source ~/esp/esp-idf-v5.5/export.sh
idf.py set-target esp32c6   # first time only
idf.py build
idf.py -p /dev/cu.usbmodemXXXX flash monitor
```

Access-point image:

```bash
source ~/esp/esp-idf-v5.5/export.sh
idf.py -B build.ap -D SDKCONFIG=sdkconfig.ap build
idf.py -B build.ap -D SDKCONFIG=sdkconfig.ap -p /dev/cu.usbmodemXXXX flash monitor
```

The two configurations never collide: each keeps its own build directory and
its own config file, so switching between them needs no clean and no
`set-target`.

### The config files hold the credentials, and git does not

`sdkconfig` holds the home/office network SSID and password. `sdkconfig.ap`
holds the SoftAP PSK. **Both are untracked and deliberately gitignored, so
neither is in any commit — delete one and the credentials in it are gone.**
Keep a copy somewhere outside the repo before doing anything drastic, and
never `rm` them to "get a clean build" (use a different `-B` directory
instead). Everything else in them regenerates from `idf.py menuconfig`
(*RD03D Configuration*); the passwords do not.

## Output

One line per radar frame (up to 3 targets), plus link stats every 5 s:

```
T1: x=-123mm y=456mm v=-12cm/s | T2: --- | T3: ---
I (5210) rd03d: link stats: dropped=0 bad_frames=0
```

`dropped` counts parser resync bytes only (not any UART driver-level loss);
`bad_frames` counts frames with a corrupt tail. Both should stay flat while a
monitor is attached.

Note that the USB-Serial-JTAG console does not reset the board when you attach,
so connecting late shows radar frames but no boot banner. Reset the board (or
use `idf.py monitor`, which resets for you) to see the startup log.

## Web UI

Either image serves the same live chart: targets on an XY plot with trails,
plus link stats.

- Data path: `GET /ws` WebSocket pushes one JSON message per radar frame,
  e.g. `{"t":[{"x":-551,"y":550,"v":0},null,null],"dropped":0,"bad":0}`
  (x/y in mm, v in cm/s, absent targets `null`).
- At boot the firmware puts the radar in multi-target mode itself; viewers
  never send radar commands.
- Untethered use: power the XIAO from a USB power bank; the USB console is
  optional diagnostics only.

### Station image

Joins the network configured in `idf.py menuconfig` (*RD03D Configuration* →
SSID/password, stored only in `sdkconfig`; 2.4 GHz WPA2 only). Open
**http://rd03d.local** from any browser on that network.

### Access-point image

The XIAO brings up its own network on boot; nothing else is required, and
there is no router, DHCP lease, or broker involved.

- SSID **`rd03d-radar`**. The PSK is not written down here — this file is
  tracked in git. It lives in `sdkconfig.ap` as `RD03D_AP_PASSWORD`, visible
  through `idf.py -B build.ap -D SDKCONFIG=sdkconfig.ap menuconfig`.
- Once joined, open **http://192.168.4.1**. mDNS is also registered, so
  **http://rd03d.local** usually works too — but 192.168.4.1 is the address
  that always works, so reach for it first when something seems wrong.
- **Joining the AP takes the laptop off its normal WiFi**, since a client can
  hold only one association at a time. Run the intranet over ethernet
  alongside it; macOS will use the wired interface for everything that is not
  192.168.4.x.
- The boot log confirms the AP is up:
  `wifi_link: softap up, ssid=rd03d-radar channel=6, http://192.168.4.1`

If the link feels slow or drops, **`RD03D_AP_CHANNEL` is the first knob to
turn** (*RD03D Configuration* → SoftAP 2.4 GHz channel, default 6). Offices
are usually congested on channels 1 and 11, which is where most access points
land by default; 6 avoids the worst of it, and the other non-overlapping
choices are worth trying before suspecting the firmware.

## OTA firmware updates

The device carries two firmware slots with automatic rollback — a bad update
reverts to the previous firmware by itself. To become permanent, a new image
must bring the WiFi link up *and* have the web server running within 90 s.
That check is mode-independent: in station mode the link counts as up once
the device has an IP, in AP mode once the SoftAP has started.

Update over WiFi (no USB needed) — station image:

```bash
idf.py build
curl -X POST --data-binary @build/rd03d_uart.bin http://rd03d.local/update
```

Access-point image, with the laptop joined to `rd03d-radar`:

```bash
idf.py -B build.ap -D SDKCONFIG=sdkconfig.ap build
curl -X POST --data-binary @build.ap/rd03d_uart.bin http://192.168.4.1/update
```

Push the image built from the matching config — flashing a station image over
the AP link works, but the device then joins your WiFi and disappears from
192.168.4.1, and recovering it needs USB. Either endpoint also takes a browser
upload at `/update`. The running version shows at `/version`, on the update
page, and in the chart HUD; confirm it still reports the *new* commit a couple
of minutes after an update, which is what proves the image was validated
rather than silently rolled back.

USB flashing is only needed for first-time setup and for switching an already
flashed board between the two images (partition table changes require
`idf.py erase-flash flash`).

**After any OTA, use the full `idf.py flash`, never `idf.py app-flash` alone.**
`app-flash` writes only the app partition; it leaves otadata pointing at
whichever slot the last OTA selected, so the bootloader keeps starting the old
image and the board looks like the flash silently did nothing. The full
`flash` rewrites otadata along with the app. If you have already used
`app-flash`, follow it with `idf.py erase-otadata`.

## MQTT events

**Station image only.** MQTT is compiled out of the AP image (`RD03D_ENABLE_MQTT`
is off in `sdkconfig.ap`): the esp-mqtt client is not linked in, no broker is
needed, and none is contacted — an AP-mode device has no route to one anyway.
The AP image is ~140 KB smaller as a result.

The station image publishes to the broker configured in `idf.py menuconfig`
(*RD03D Configuration*, default `iotstack.local:1883`, anonymous):

- `rd03d/target/1..3` — `{"x":-551,"y":550,"v":0}` when that target first
  appears or has moved ≥ the configured distance (default 200 mm) since the
  last published position; `{"gone":true}` once when it disappears.
  QoS 0, not retained.
- `rd03d/status` — retained `online`/`offline` (Last-Will), so consumers
  (e.g. Node-RED) always know whether the sensor is alive.

While the broker is unreachable nothing is queued; on (re)connect the device
republishes `online` and the current position of every present target.
The broker hostname is resolved (via mDNS for `.local` names) once at boot —
if the broker's IP changes, reboot the XIAO (or just re-upload firmware).

## Host-side tests

These compile the parser and throttle sources directly on the host, so they
are unaffected by which image you are building:

```bash
cd tests
cc -Wall -Wextra -o test_rd03d test_rd03d.c ../main/rd03d.c && ./test_rd03d
cc -Wall -Wextra -o test_mqtt_throttle test_mqtt_throttle.c ../main/mqtt_throttle.c && ./test_mqtt_throttle
```

Frame format and sign-magnitude decoding match
`../RD03D_RadarChart/README.md` (Processing visualizer for the same sensor).
