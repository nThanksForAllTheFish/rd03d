# RD-03D UART Reader — Design

**Date:** 2026-08-31
**Target:** Seeed Studio XIAO ESP32-C6
**Framework:** ESP-IDF v5.5 (`~/esp/esp-idf-v5.5`; the v5.3.5 install referenced by .vscode/settings.json no longer exists on this machine)

## Goal

First step of a new radar project: the XIAO ESP32-C6 reads binary frames from an
Ai-Thinker RD-03D 24GHz mmWave radar over UART, decodes them, and prints
human-readable target data to the USB-C serial console.

## Hardware / Wiring

| RD-03D pin | XIAO ESP32-C6 pin | Notes |
| --- | --- | --- |
| TX | D7 (GPIO17) | UART1 RX on the XIAO |
| RX | D6 (GPIO16) | UART1 TX; unused for now, wired for future mode commands |
| 5V | 5V | RD-03D is 5V powered (3.3V logic on UART) |
| GND | GND | |

- Radar UART: **256000 baud, 8N1**, no flow control.
- Console: built-in **USB-Serial-JTAG** on the USB-C port — no GPIOs consumed;
  monitor baud rate setting is irrelevant to the radar link.

## Project Structure

New ESP-IDF project `rd03d_uart/` alongside `blink/` and `hello_world/`:

```
rd03d_uart/
  CMakeLists.txt
  sdkconfig.defaults          # target esp32c6, console on USB-Serial-JTAG
  main/
    CMakeLists.txt
    main.c                    # UART1 setup + read task + logging
    rd03d.c                   # frame parser (pure C, no IDF dependencies)
    rd03d.h                   # rd03d_frame_t, rd03d_target_t, parser API
  README.md
```

## Frame Format (from RD03D_RadarChart README / user manual)

30-byte frame: header `AA FF 03 00`, three 8-byte target blocks, tail `55 CC`.

Each target block:

| Offset | Field | Encoding |
| --- | --- | --- |
| 0–1 | X (mm) | 16-bit sign-magnitude, little-endian; MSB of high byte = sign |
| 2–3 | Y (mm) | same sign-magnitude encoding |
| 4–5 | Velocity (cm/s) | same sign-magnitude encoding |
| 6–7 | Resolution (mm) | plain 16-bit little-endian |

An all-zero block means no target in that slot.

## Data Flow

1. `uart_read_bytes()` in a single FreeRTOS task (Approach A: simple polling
   loop; no UART event queue).
2. Bytes are fed one at a time into a parser state machine that hunts for the
   header, accumulates 30 bytes, and validates the tail.
3. On a valid frame the parser fills `rd03d_frame_t` (up to 3 targets, each with
   a `present` flag and decoded x/y/velocity/resolution).
4. `main.c` prints one line per frame, e.g.
   `T1: x=-123mm y=456mm v=-12cm/s | T2: --- | T3: ---`.

## Error Handling

- Garbage or partial frames never crash the parser: any byte that breaks the
  expected sequence resets the state machine, which resynchronizes on the next
  header.
- The parser counts dropped bytes and invalid frames; `main.c` logs these
  counters periodically (~every 5 s) as a link-quality indicator.

## Testing / Verification

- Build and flash with ESP-IDF v5.5 (`source ~/esp/esp-idf-v5.5/export.sh`)
  (`idf.py set-target esp32c6`, `idf.py flash monitor`, port
  `/dev/cu.usbmodem101`).
- Verify parsed target lines appear when a person moves in front of the radar,
  and that the no-target case prints `---` slots.
- The parser is pure C with no IDF dependencies, so it can be unit-tested on
  the host against known capture bytes if needed later.

## Out of Scope (for this step)

- Raw binary pass-through mode for the Processing sketch.
- Sending mode-switch commands to the radar (multi-target mode is the RD-03D
  default).
- Wi-Fi/BLE, storage, or any visualization on the ESP32 side.
