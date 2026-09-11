# RD-03D SoftAP Variant — Design

**Date:** 2026-09-11
**Branch:** `feat/softap-variant` (off `main`; unrelated to the case work on
`feat/case-usb-jack`)
**Firmware:** `rd03d_uart/`

## Goal

Let the user run the prototype XIAO + RD-03D on a work site where unregistered
devices may not join the corporate WiFi. The XIAO becomes its own access point;
the laptop joins it directly and opens the live radar chart. Nothing touches the
site network. MQTT is compiled out, since there is no broker there.

## Decisions Made

- **One codebase, two build configurations** — not a divergent branch and not a
  copied project. `RD03D_NET_MODE` is a Kconfig choice (`STA` / `AP`), and the
  AP image builds with its own sdkconfig and build directory:

  ```
  idf.py -B build.ap -D SDKCONFIG=sdkconfig.ap build
  ```

  Every radar, chart or OTA fix then lands in both images at once. A branch or a
  copied tree would force each fix to be applied twice and drift apart.
- **AP is WPA2-protected.** An open AP at a workplace shows up on any wireless
  scan and leaves the chart, `/version` and the OTA upload page reachable by
  anyone in range.
- **OTA stays.** It already works over the AP link and needs no toolchain on the
  machine at work.
- **Credentials never reach a committed file.** `sdkconfig.ap` holds the AP SSID
  and PSK and joins `sdkconfig` in `.gitignore`.

## Architecture

`wifi_link.c` is the only file whose behaviour changes. Everything downstream —
the radar parser, the WebSocket chart, OTA — is network-agnostic and does not
care which mode brought the interface up.

| mode | netif | wifi mode | address |
|---|---|---|---|
| STA (today) | `esp_netif_create_default_wifi_sta` | `WIFI_MODE_STA` | DHCP from the home router |
| AP (new) | `esp_netif_create_default_wifi_ap` | `WIFI_MODE_AP` | fixed **192.168.4.1**, DHCP server hands clients 192.168.4.2+ |

mDNS is registered in both modes and advertises over whichever interface is up,
so `rd03d.local` should resolve once the laptop joins. 192.168.4.1 is the
fallback that always works and is what the README will lead with.

## Kconfig

| option | type | default | notes |
|---|---|---|---|
| `RD03D_NET_MODE` | choice `STA`/`AP` | `STA` | selects the netif and wifi mode |
| `RD03D_AP_SSID` | string | `rd03d-radar` | AP builds only |
| `RD03D_AP_PASSWORD` | string | *(empty)* | AP builds only; must be >= 8 chars |
| `RD03D_AP_CHANNEL` | int | 6 | 1 and 11 are usually congested in offices |
| `RD03D_ENABLE_MQTT` | bool | `y` | set `n` for the AP image |

The existing `RD03D_WIFI_SSID` / `RD03D_WIFI_PASSWORD` gain `depends on` the STA
choice, so an AP build does not prompt for credentials it will not use.

## `wifi_link.c` changes

- AP branch: `wifi_config_t.ap` with `WIFI_AUTH_WPA2_PSK`, `max_connection = 4`,
  channel from Kconfig.
- Compile-time asserts mirroring the STA ones for SSID and password length,
  **plus a new one that the PSK is at least 8 characters.** WPA2's minimum;
  below it `esp_wifi_set_config` fails at runtime with an unhelpful error.
- The STA build's "credentials not set" guard gets an AP equivalent.

### The rollback trap (the reason this file needs care)

`main.c:77` and `main.c:85` gate `esp_ota_mark_app_valid_cancel_rollback()` on
`wifi_link_has_ip()`, which is set only by `IP_EVENT_STA_GOT_IP`. **That event
never fires in AP mode.** Left alone, the flag stays false, the 90-second
validation deadline expires, and every OTA'd image rolls back — while USB
flashing keeps working, because a full `idf.py flash` erases otadata and never
arms rollback in the first place.

The failure would therefore appear for the first time on a wireless update at
work, and present as "it rebooted into the old firmware for no reason."

**Fix:** set the flag on `WIFI_EVENT_AP_START` in the AP branch, and rename the
accessor to `wifi_link_is_up()`. Two call sites. The old name is what hides the
bug — "has IP" is false in AP mode even though the network is perfectly up.

## MQTT exclusion

`#if CONFIG_RD03D_ENABLE_MQTT` around the two calls in `main.c`
(`mqtt_pub_start()`, `mqtt_pub_frame()`), and `mqtt_pub.c` / `mqtt_throttle.c`
dropped from `idf_component_register(SRCS ...)` when the option is off — so the
esp-mqtt component does not link in and the image genuinely shrinks rather than
carrying dead code.

The 13 host tests for `mqtt_throttle` are unaffected; they build separately from
the firmware and continue to run.

## Verification

1. **STA image unchanged:** builds, flashes, reaches `rd03d.local` on the home
   network, radar frames stream, MQTT still publishes. This is the regression
   check — the refactor must not disturb the working node.
2. **AP image:** builds; SSID appears in the laptop's network list; joining it
   succeeds with the PSK; chart renders at `http://192.168.4.1`; `/version`
   responds; radar frames stream to the chart.
3. **The rollback trap is closed:** push an OTA over the AP link and confirm
   `/version` still reports the new build two minutes later. This is the check
   that matters — everything else would pass even with the bug present.
4. Both images built from one tree in the same session, proving the Kconfig
   split works.

## Deliverables

- `rd03d_uart/main/Kconfig.projbuild` — the five options above.
- `rd03d_uart/main/wifi_link.c` / `.h` — AP branch, `wifi_link_is_up()`.
- `rd03d_uart/main/main.c` — MQTT call guards, renamed accessor.
- `rd03d_uart/main/CMakeLists.txt` — conditional MQTT sources.
- Repo root `.gitignore` — add `rd03d_uart/sdkconfig.ap` beside the
  existing `rd03d_uart/sdkconfig` entry at line 22. There is no
  `rd03d_uart/.gitignore`; the root file carries these.
- `rd03d_uart/README.md` — how to build and flash each variant, how to join the
  AP, and the 192.168.4.1 address.

## Out of scope

- MQTT in AP builds; multi-node mDNS hostnames or topic prefixes.
- Anything touching the case, the Fusion model, or `feat/case-usb-jack`.
- Runtime mode switching (a button or a captive portal). Build-time only.
- Changes to `rd03d.c` / `rd03d.h`, which stay frozen.
