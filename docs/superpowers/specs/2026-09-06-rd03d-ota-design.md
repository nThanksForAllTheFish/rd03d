# RD-03D Firmware OTA Updates — Design

**Date:** 2026-09-06
**Target:** Seeed Studio XIAO ESP32-C6 (existing `rd03d_uart/` project, 4 MB flash — verified via esptool `flash_id`)
**Framework:** ESP-IDF v5.5 (`~/esp/esp-idf-v5.5`)
**Builds on:** `2026-09-06-rd03d-wifi-design.md` (WiFi + web UI, done and verified)

## Goal

Update the wall-mounted XIAO's firmware over WiFi — upload a new `.bin` from a
browser page or one curl command — with automatic rollback so a bad update can
never strand the device: worst case it reboots back into the previous working
firmware.

## Decisions Made

- **Push to device** (no external hosting): the existing esp_http_server gains
  an upload endpoint.
- **Open endpoint** on the trusted home LAN — no token/auth (revisit if the
  network's trust model changes).
- **Rollback enabled** (`CONFIG_BOOTLOADER_APP_ROLLBACK_ENABLE`): a new image
  must prove itself before becoming permanent.

## Partition Layout (one-time USB migration)

Current state: config says 2 MB flash, single 1 MB factory app partition; the
app binary is ~982 KB (≈6% headroom). Actual flash chip is 4 MB.

New custom `rd03d_uart/partitions.csv`:

| Name     | Type | SubType  | Size     |
| -------- | ---- | -------- | -------- |
| nvs      | data | nvs      | 24 KB    |
| otadata  | data | ota      | 8 KB     |
| phy_init | data | phy      | 4 KB     |
| ota_0    | app  | ota_0    | ~1.5 MB  |
| ota_1    | app  | ota_1    | ~1.5 MB  |

`sdkconfig.defaults` gains: 4 MB flash size, custom partition table filename,
rollback enable. Installing the new table requires one final USB
`idf.py erase-flash flash` (nothing persistent is lost: WiFi credentials are
build-time config; NVS holds only RF calibration, which regenerates).

## Firmware Changes (`rd03d_uart/`)

- `main/ota_update.c/.h` — new module, registered on the existing HTTP server:
  - `ota_update_register(httpd_handle_t server)` — adds the two URI handlers.
  - `GET /update` — small self-contained embedded page (C string, not an
    EMBED_FILES asset): shows the running firmware version and the idle slot,
    file picker + upload button, status/progress text, link back to `/`.
  - `POST /update` — streams the request body in chunks via
    `esp_ota_begin` / `esp_ota_write` into the passive slot; on success
    `esp_ota_end` + `esp_ota_set_boot_partition`, respond with a success
    message, then `esp_restart()` after ~1 s (letting the response flush).
    On any failure (image header invalid, oversize, write/verify error):
    respond with the error text and leave everything untouched — the running
    slot is never written, so a failed upload has zero effect.
- `main/web_server.c/.h` — gains `httpd_handle_t web_server_handle(void)`
  (NULL when the server failed to start); `main.c` wires the modules:
  `ota_update_register(web_server_handle())` after `web_server_start()`.
  Chart page HUD additionally shows the firmware version string.
- `main/wifi_link.c/.h` — expose "has an IP" state (simple getter or event
  flag) for the validation logic.
- `main/main.c` — self-validation task/logic: after boot, once WiFi has an IP
  AND the web server started successfully, call
  `esp_ota_mark_app_valid_cancel_rollback()`. If that state is not reached
  within **90 s** of boot, call `esp_restart()` — with the image still
  pending-verify, the bootloader then reverts to the previous slot. (On a
  USB-flashed image or an already-validated image, the mark call is a no-op /
  skipped; the 90 s restart applies only while the image is pending-verify.)
- **Version visibility:** app version comes from git (`git describe --always
  --dirty` via CMake) into `esp_app_desc`; printed in the boot log, shown on
  the chart HUD and the `/update` page, so every update is visibly confirmed.
- `main/rd03d.c/.h` — untouched. Radar loop and chart streaming keep running
  during an upload (flash writes briefly stall tasks; the UART ring buffer
  absorbs it and the parser resyncs if a byte is ever lost).

## Update Flow (user's view)

1. `idf.py build` on the Mac.
2. Browser: open `http://rd03d.local/update`, pick
   `rd03d_uart/build/rd03d_uart.bin`, upload — or:
   `curl -X POST --data-binary @build/rd03d_uart.bin http://rd03d.local/update`
3. Device writes, verifies, reboots into the new slot (~15 s total).
4. New firmware joins WiFi, web server comes up → marks itself valid.
5. Chart page reconnects on its own; HUD shows the new version.

If step 4 never completes: the device restarts after 90 s and the bootloader
boots the previous firmware, which marks itself valid again. No ladder.

## Error Handling

- Upload of a non-firmware file / truncated file → `esp_ota_end` verification
  fails → error response, no state change.
- Upload larger than the slot → rejected mid-stream with an error response.
- Power loss during upload → old slot still boots (passive slot was the only
  thing being written).
- Crash loop in new firmware → watchdog/panic reboot while pending-verify →
  bootloader rollback.
- Concurrent uploads → second POST rejected while one is in progress.

## Testing / Verification

1. Host parser tests still pass (regression; parser untouched).
2. One-time USB migration: erase-flash + flash; radar frames, chart, mDNS all
   still work; boot log shows `ota_0` as the running partition and the new
   version string.
3. Happy-path OTA: bump the version (any commit), build, upload via curl;
   device reboots; HUD/boot log show the new version and the other slot.
4. Browser-path OTA: same via the `/update` page.
5. Rollback drill: build with a temporary test flag that skips validation and
   restarts (simulating a broken image); upload it; confirm the device comes
   back by itself on the previous version within ~2 minutes.
6. Bad-file drill: upload a text file; expect an error response and an
   unaffected running system.

## Out of Scope

- Authentication/signed images (open LAN endpoint by decision above; IDF's
  image hash check still rejects corrupt/non-firmware uploads).
- Pull-based updates, update servers, fleet management.
- OTA of the bootloader or partition table (not possible via esp_ota; USB
  only).
