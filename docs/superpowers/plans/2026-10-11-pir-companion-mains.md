# PIR Companion (mains mode) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Panasonic EKMC1603111 PIR to the radar node so both sensors publish events from one firmware, the chart and the Node-RED flow show both, and a CSV log compares them. Mains mode only; the battery/deep-sleep work is a later plan gated on the latency numbers this plan produces.

**Architecture:** A pure-C gate (`pir_gate.c`, host-tested) turns raw edges into one event per pass with a hold; an IDF driver (`pir.c`) feeds it from a GPIO interrupt via a queue and calls one callback. `main.c` wires the callback to the LED and the publisher. The publisher (`mqtt_pub.c`) emits `rd03d/pir` with the radar's nearest target attached and a retained `rd03d/pir/state`. SNTP gives wall-clock timestamps so Node-RED can compute one-way latency. The web page shows PIR state. The case gets a pod on the shell's +X wall, built by the Fusion scripts and checked by the probe harness.

**Tech Stack:** ESP-IDF v5.5 (`source ~/esp/esp-idf-v5.5/export.sh`), target esp32c6, host tests with `cc`, Node-RED flow JSON validated by `node-red/validate_flow.py`, Fusion 360 via `case/fusion_scripts/run_fusion.py`.

**Spec:** `docs/superpowers/specs/2026-10-11-pir-companion-design.md`

**Deferred to the battery plan (on purpose):** `RD03D_POWER_MODE`, `RD03D_RADAR_EN_GPIO`, `RD03D_AWAKE_WINDOW_S`, deep/light sleep, the boost converter and cell holder. This plan only makes sure the pin choices leave room for them.

**Working copy:** `~/Documents/rd03d-public` on branch `feat/pir-companion`. The STA build needs `rd03d_uart/sdkconfig` (home WiFi credentials) which lives ONLY in `~/Documents/Code/VSCode/Claude/rd03d_uart/sdkconfig`; copy it and `sdkconfig.ap` into `rd03d_uart/` before building. Both are gitignored. Never commit them, never print their contents.

**Commit convention:** every commit message ends with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. Author identity is already set in the clone (`nThanksForAllTheFish`, no-reply address).

---

## File map

| file | responsibility |
| --- | --- |
| `rd03d_uart/main/pir_gate.h/.c` | pure C: edges in, events out, hold timing; no IDF includes |
| `rd03d_uart/tests/test_pir_gate.c` | host test for the gate |
| `rd03d_uart/main/pir.h/.c` | IDF driver: GPIO ISR, queue, task, hold-expiry timer, callback |
| `rd03d_uart/main/clock_ms.h/.c` | SNTP start + `clock_epoch_ms()` (0 until synced) |
| `rd03d_uart/main/mqtt_pub.h/.c` | adds `mqtt_pub_pir_event()` and `mqtt_pub_pir_state()`, keeps the last radar frame |
| `rd03d_uart/main/web_server.h/.c`, `index.html` | `"pir"` field in the WebSocket frame; page lamp + log line |
| `rd03d_uart/main/main.c` | starts the clock and the PIR driver, wires the callback |
| `rd03d_uart/main/Kconfig.projbuild`, `CMakeLists.txt` | `RD03D_ENABLE_PIR`, `RD03D_PIR_GPIO`, `RD03D_PIR_HOLD_MS`; conditional sources |
| `node-red/flows-stair-light.json`, `validate_flow.py`, `README.md` | PIR input, source switch, comparison/latency CSV |
| `case/fusion_scripts/03_shell.py`, `90_verify.py`, `05_export.py` | pod on the +X wall, plug, probe check, STL export |
| `README.md`, `rd03d_uart/README.md` | wiring, topics, build notes |

---

### Task 1: PIR gate (pure C) with host test

**Files:**
- Create: `rd03d_uart/main/pir_gate.h`
- Create: `rd03d_uart/main/pir_gate.c`
- Create: `rd03d_uart/tests/test_pir_gate.c`

- [ ] **Step 1: Write the failing test**

```c
/* rd03d_uart/tests/test_pir_gate.c */
#include <assert.h>
#include <stdio.h>
#include "../main/pir_gate.h"

static void test_first_edge_is_an_event(void)
{
    pir_gate_t g;
    pir_gate_init(&g, 500);
    assert(pir_gate_edge(&g, 1000) == PIR_GATE_EVENT);
    assert(pir_gate_active(&g, 1000));
}

static void test_edges_inside_hold_are_silent_but_extend(void)
{
    pir_gate_t g;
    pir_gate_init(&g, 500);
    pir_gate_edge(&g, 1000);                     /* hold until 1500 */
    assert(pir_gate_edge(&g, 1400) == PIR_GATE_NONE); /* extends to 1900 */
    assert(pir_gate_active(&g, 1800));
    assert(!pir_gate_active(&g, 1900));
}

static void test_edge_after_hold_is_a_new_event(void)
{
    pir_gate_t g;
    pir_gate_init(&g, 500);
    pir_gate_edge(&g, 1000);
    assert(pir_gate_edge(&g, 1500) == PIR_GATE_EVENT); /* exactly at expiry */
    assert(pir_gate_edge(&g, 3000) == PIR_GATE_EVENT);
}

static void test_hold_end_time(void)
{
    pir_gate_t g;
    pir_gate_init(&g, 500);
    pir_gate_edge(&g, 1000);
    assert(pir_gate_hold_end(&g) == 1500);
    pir_gate_edge(&g, 1200);
    assert(pir_gate_hold_end(&g) == 1700);
}

static void test_inactive_before_any_edge(void)
{
    pir_gate_t g;
    pir_gate_init(&g, 500);
    assert(!pir_gate_active(&g, 0));
    assert(!pir_gate_active(&g, 123456789));
}

static void test_zero_hold_every_edge_is_an_event(void)
{
    pir_gate_t g;
    pir_gate_init(&g, 0);
    assert(pir_gate_edge(&g, 10) == PIR_GATE_EVENT);
    assert(pir_gate_edge(&g, 10) == PIR_GATE_EVENT);
    assert(!pir_gate_active(&g, 10));
}

static void test_event_count(void)
{
    pir_gate_t g;
    pir_gate_init(&g, 500);
    pir_gate_edge(&g, 1000);
    pir_gate_edge(&g, 1100);
    pir_gate_edge(&g, 5000);
    assert(pir_gate_count(&g) == 2);
}

static void test_wraparound_64bit_not_a_concern_but_large_values_ok(void)
{
    pir_gate_t g;
    pir_gate_init(&g, 500);
    int64_t t = 4000000000000LL; /* ~127 years of ms */
    assert(pir_gate_edge(&g, t) == PIR_GATE_EVENT);
    assert(pir_gate_active(&g, t + 499));
    assert(!pir_gate_active(&g, t + 500));
}

int main(void)
{
    test_first_edge_is_an_event();
    test_edges_inside_hold_are_silent_but_extend();
    test_edge_after_hold_is_a_new_event();
    test_hold_end_time();
    test_inactive_before_any_edge();
    test_zero_hold_every_edge_is_an_event();
    test_event_count();
    test_wraparound_64bit_not_a_concern_but_large_values_ok();
    printf("all tests passed\n");
    return 0;
}
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
```bash
cd ~/Documents/rd03d-public/rd03d_uart/tests && cc -Wall -Wextra -o test_pir_gate test_pir_gate.c ../main/pir_gate.c && ./test_pir_gate
```
Expected: compile error, `../main/pir_gate.h: No such file or directory`.

- [ ] **Step 3: Write the gate**

```c
/* rd03d_uart/main/pir_gate.h */
#pragma once

#include <stdbool.h>
#include <stdint.h>

/* Turns raw PIR output edges into one event per pass.
 *
 * The EKMC1603111 output goes high for about 2 s per detection, but a person
 * crossing several lens zones produces a burst of rising edges. The gate
 * reports the first edge as an event and swallows edges that land inside a
 * hold window, extending the window each time. Pure C, no IDF: the caller
 * supplies time in milliseconds from any monotonic source. */

typedef enum {
    PIR_GATE_NONE = 0,
    PIR_GATE_EVENT,
} pir_gate_action_t;

typedef struct {
    uint32_t hold_ms;
    int64_t hold_until_ms;   /* exclusive: active while now < hold_until */
    bool armed_once;         /* false until the first edge ever */
    uint32_t count;          /* events reported since init */
} pir_gate_t;

void pir_gate_init(pir_gate_t *g, uint32_t hold_ms);

/* Feed one rising edge at time now_ms. */
pir_gate_action_t pir_gate_edge(pir_gate_t *g, int64_t now_ms);

/* True while a hold window is open. */
bool pir_gate_active(const pir_gate_t *g, int64_t now_ms);

/* End of the current hold window (ms), meaningful after the first edge. */
int64_t pir_gate_hold_end(const pir_gate_t *g);

uint32_t pir_gate_count(const pir_gate_t *g);
```

```c
/* rd03d_uart/main/pir_gate.c */
#include "pir_gate.h"

void pir_gate_init(pir_gate_t *g, uint32_t hold_ms)
{
    g->hold_ms = hold_ms;
    g->hold_until_ms = 0;
    g->armed_once = false;
    g->count = 0;
}

pir_gate_action_t pir_gate_edge(pir_gate_t *g, int64_t now_ms)
{
    bool inside = g->armed_once && now_ms < g->hold_until_ms;
    g->hold_until_ms = now_ms + (int64_t)g->hold_ms;
    g->armed_once = true;
    if (inside) {
        return PIR_GATE_NONE;       /* same pass: extend only */
    }
    g->count++;
    return PIR_GATE_EVENT;
}

bool pir_gate_active(const pir_gate_t *g, int64_t now_ms)
{
    return g->armed_once && now_ms < g->hold_until_ms;
}

int64_t pir_gate_hold_end(const pir_gate_t *g)
{
    return g->hold_until_ms;
}

uint32_t pir_gate_count(const pir_gate_t *g)
{
    return g->count;
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run the same command as step 2.
Expected: `all tests passed`.

- [ ] **Step 5: Add the test to both READMEs' test blocks**

In `README.md` (the block under "Quick start", currently two `cc` lines) and `rd03d_uart/README.md` (the block near line 203), add a third line:

```bash
cc -Wall -Wextra -o test_pir_gate test_pir_gate.c ../main/pir_gate.c && ./test_pir_gate
```

Also add `rd03d_uart/tests/test_pir_gate` to `.gitignore` next to the other two test binaries.

- [ ] **Step 6: Commit**

```bash
cd ~/Documents/rd03d-public && git add rd03d_uart/main/pir_gate.h rd03d_uart/main/pir_gate.c rd03d_uart/tests/test_pir_gate.c README.md rd03d_uart/README.md .gitignore
git commit -m "pir: pure-C edge gate with host tests

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: Kconfig and CMake for the PIR

**Files:**
- Modify: `rd03d_uart/main/Kconfig.projbuild` (append before the final `endmenu`)
- Modify: `rd03d_uart/main/CMakeLists.txt`

- [ ] **Step 1: Add the Kconfig entries**

Insert before `endmenu` at the end of `Kconfig.projbuild`:

```
config RD03D_ENABLE_PIR
    bool "PIR companion sensor"
    default y
    help
        Panasonic EKMC1603111 on a GPIO: publishes rd03d/pir events next to
        the radar's. Off in the AP image (sdkconfig.ap), which has no PIR
        fitted. When off, pir.c and pir_gate.c are not compiled.

config RD03D_PIR_GPIO
    int "PIR output GPIO"
    depends on RD03D_ENABLE_PIR
    default 1
    range 0 30
    help
        XIAO ESP32-C6 D1 = GPIO1. Keep it in GPIO0..7: those are the LP IOs,
        the only ones that can wake the chip from deep sleep, which the
        battery variant will need. The sensor drives the pin high on
        detection and floats otherwise; the driver enables the internal
        pull-down.

config RD03D_PIR_HOLD_MS
    int "PIR hold window (ms)"
    depends on RD03D_ENABLE_PIR
    default 500
    range 0 10000
    help
        Edges inside this window after an event are the same pass and do not
        publish; each one extends the window. rd03d/pir/state is 1 while the
        window is open.
```

- [ ] **Step 2: Add the sources conditionally**

In `CMakeLists.txt`, after the `if(CONFIG_RD03D_ENABLE_MQTT)` block:

```cmake
# pir_gate.c is pure C (host-tested); pir.c is the GPIO driver around it.
if(CONFIG_RD03D_ENABLE_PIR)
    list(APPEND rd03d_srcs "pir.c" "pir_gate.c" "clock_ms.c")
endif()
```

- [ ] **Step 3: Turn the PIR off in the AP config**

`rd03d_uart/sdkconfig.ap` is gitignored and local. Append one line to it (the file has no PIR entries yet, so there is nothing to replace):

```bash
cd ~/Documents/rd03d-public/rd03d_uart && grep -q RD03D_ENABLE_PIR sdkconfig.ap || printf '\n# PIR not fitted on the prototype that runs the AP image\nCONFIG_RD03D_ENABLE_PIR=n\n' >> sdkconfig.ap
```

Expected: no output; `grep RD03D_ENABLE_PIR sdkconfig.ap` prints `CONFIG_RD03D_ENABLE_PIR=n`.

- [ ] **Step 4: Commit** (CMake references files that Tasks 3 and 4 create; the build is checked in Task 7)

```bash
cd ~/Documents/rd03d-public && git add rd03d_uart/main/Kconfig.projbuild rd03d_uart/main/CMakeLists.txt
git commit -m "pir: Kconfig switch, GPIO and hold; conditional sources

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: Wall-clock milliseconds via SNTP

**Files:**
- Create: `rd03d_uart/main/clock_ms.h`
- Create: `rd03d_uart/main/clock_ms.c`

- [ ] **Step 1: Write the header**

```c
/* rd03d_uart/main/clock_ms.h */
#pragma once

#include <stdint.h>

/* Starts SNTP (pool.ntp.org) once WiFi is up. Station mode only: an access
 * point with no uplink has nothing to sync to, and clock_epoch_ms() stays 0. */
void clock_start(void);

/* Milliseconds since the Unix epoch, or 0 until the first SNTP sync. Node-RED
 * subtracts this from its own arrival time to get one-way latency, which is
 * the number the battery variant's deep-sleep gate is decided on. */
int64_t clock_epoch_ms(void);
```

- [ ] **Step 2: Write the implementation**

```c
/* rd03d_uart/main/clock_ms.c */
#include "clock_ms.h"

#include <sys/time.h>
#include "esp_log.h"
#include "esp_netif_sntp.h"
#include "sdkconfig.h"

static const char *TAG = "clock";

void clock_start(void)
{
#if CONFIG_RD03D_NET_MODE_STA
    esp_sntp_config_t cfg = ESP_NETIF_SNTP_DEFAULT_CONFIG("pool.ntp.org");
    cfg.start = true;              /* sends its first request as soon as the
                                      interface has an IP; retries on its own */
    ESP_ERROR_CHECK(esp_netif_sntp_init(&cfg));
    ESP_LOGI(TAG, "sntp started (pool.ntp.org)");
#else
    ESP_LOGI(TAG, "AP mode: no SNTP, timestamps stay 0");
#endif
}

int64_t clock_epoch_ms(void)
{
    struct timeval tv;
    if (gettimeofday(&tv, NULL) != 0) {
        return 0;
    }
    /* Before the first sync the RTC reads 1970; report 0 so a consumer can
     * tell "unsynced" from "very early". 1e9 s is 2001-09-09. */
    if (tv.tv_sec < 1000000000) {
        return 0;
    }
    return (int64_t)tv.tv_sec * 1000 + tv.tv_usec / 1000;
}
```

- [ ] **Step 3: Call it from `main.c`**

In `rd03d_uart/main/main.c`, add `#include "clock_ms.h"` under the `#if CONFIG_RD03D_ENABLE_PIR` include block (created in Task 5; if doing this task first, add the include inside the same guard) and call `clock_start();` right after `wifi_link_start();`. The full `app_main` wiring is shown in Task 5; this step only records where the call goes.

- [ ] **Step 4: Commit**

```bash
cd ~/Documents/rd03d-public && git add rd03d_uart/main/clock_ms.h rd03d_uart/main/clock_ms.c
git commit -m "pir: SNTP wall clock for event timestamps

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: PIR driver (`pir.c`)

**Files:**
- Create: `rd03d_uart/main/pir.h`
- Create: `rd03d_uart/main/pir.c`

- [ ] **Step 1: Write the header**

```c
/* rd03d_uart/main/pir.h */
#pragma once

#include <stdbool.h>
#include <stdint.h>

/* One PIR on one GPIO. A rising edge from the sensor goes ISR -> queue ->
 * pir task -> pir_gate; the gate's events reach the application through the
 * callback below, on the pir task, never in interrupt context. The hold
 * window is tracked so the callback also hears when activity ends. */

typedef struct {
    uint32_t n;          /* events since boot (pir_gate_count) */
    int64_t  t_ms;       /* clock_epoch_ms() at the edge, 0 if unsynced */
} pir_event_t;

typedef void (*pir_event_cb_t)(const pir_event_t *ev);
typedef void (*pir_state_cb_t)(bool active);

/* Configures the pin (input, pull-down, rising-edge interrupt), creates the
 * task and the hold-expiry timer. Call once at boot. The state callback
 * fires with true on each event's first edge and false when the hold ends. */
void pir_init(pir_event_cb_t on_event, pir_state_cb_t on_state);

/* True while the hold window is open. Safe from any task. */
bool pir_active(void);
```

- [ ] **Step 2: Write the driver**

```c
/* rd03d_uart/main/pir.c */
#include "pir.h"

#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include "driver/gpio.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "sdkconfig.h"
#include "clock_ms.h"
#include "pir_gate.h"

static const char *TAG = "pir";

typedef enum { MSG_EDGE, MSG_HOLD_EXPIRED } pir_msg_t;

static QueueHandle_t s_queue;
static esp_timer_handle_t s_expiry;
static pir_gate_t s_gate;
static volatile bool s_active;
static pir_event_cb_t s_on_event;
static pir_state_cb_t s_on_state;

static int64_t now_ms(void)
{
    return esp_timer_get_time() / 1000;   /* monotonic since boot */
}

static void IRAM_ATTR pir_isr(void *arg)
{
    (void)arg;
    pir_msg_t m = MSG_EDGE;
    BaseType_t woken = pdFALSE;
    xQueueSendFromISR(s_queue, &m, &woken);
    if (woken) {
        portYIELD_FROM_ISR();
    }
}

static void expiry_cb(void *arg)
{
    (void)arg;
    pir_msg_t m = MSG_HOLD_EXPIRED;
    xQueueSend(s_queue, &m, 0);
}

static void arm_expiry(int64_t hold_end_ms)
{
    int64_t delay_us = (hold_end_ms - now_ms()) * 1000;
    if (delay_us < 1000) {
        delay_us = 1000;
    }
    esp_timer_stop(s_expiry);          /* INVALID_STATE when idle: fine */
    esp_timer_start_once(s_expiry, (uint64_t)delay_us);
}

static void pir_task(void *arg)
{
    (void)arg;
    pir_msg_t m;
    for (;;) {
        if (xQueueReceive(s_queue, &m, portMAX_DELAY) != pdTRUE) {
            continue;
        }
        int64_t t = now_ms();
        if (m == MSG_EDGE) {
            pir_gate_action_t act = pir_gate_edge(&s_gate, t);
            arm_expiry(pir_gate_hold_end(&s_gate));
            if (act == PIR_GATE_EVENT) {
                s_active = true;
                pir_event_t ev = {
                    .n = pir_gate_count(&s_gate),
                    .t_ms = clock_epoch_ms(),
                };
                ESP_LOGI(TAG, "event %lu", (unsigned long)ev.n);
                if (s_on_state) {
                    s_on_state(true);
                }
                if (s_on_event) {
                    s_on_event(&ev);
                }
            }
        } else { /* MSG_HOLD_EXPIRED */
            if (!pir_gate_active(&s_gate, t)) {
                if (s_active) {
                    s_active = false;
                    if (s_on_state) {
                        s_on_state(false);
                    }
                }
            } else {
                arm_expiry(pir_gate_hold_end(&s_gate)); /* extended meanwhile */
            }
        }
    }
}

void pir_init(pir_event_cb_t on_event, pir_state_cb_t on_state)
{
    s_on_event = on_event;
    s_on_state = on_state;
    pir_gate_init(&s_gate, CONFIG_RD03D_PIR_HOLD_MS);

    s_queue = xQueueCreate(8, sizeof(pir_msg_t));
    const esp_timer_create_args_t targs = {
        .callback = expiry_cb,
        .name = "pir_hold",
    };
    ESP_ERROR_CHECK(esp_timer_create(&targs, &s_expiry));

    gpio_config_t cfg = {
        .pin_bit_mask = 1ULL << CONFIG_RD03D_PIR_GPIO,
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_ENABLE,  /* sensor output floats when idle */
        .intr_type = GPIO_INTR_POSEDGE,
    };
    ESP_ERROR_CHECK(gpio_config(&cfg));
    /* Shared ISR service; ESP_ERR_INVALID_STATE means another module already
     * installed it, which is fine. */
    esp_err_t err = gpio_install_isr_service(0);
    if (err != ESP_OK && err != ESP_ERR_INVALID_STATE) {
        ESP_ERROR_CHECK(err);
    }
    ESP_ERROR_CHECK(gpio_isr_handler_add(CONFIG_RD03D_PIR_GPIO, pir_isr, NULL));

    xTaskCreate(pir_task, "pir", 3072, NULL, 6, NULL);
    ESP_LOGI(TAG, "PIR on GPIO%d, hold %d ms", CONFIG_RD03D_PIR_GPIO,
             CONFIG_RD03D_PIR_HOLD_MS);
}

bool pir_active(void)
{
    return s_active;
}
```

- [ ] **Step 3: Commit**

```bash
cd ~/Documents/rd03d-public && git add rd03d_uart/main/pir.h rd03d_uart/main/pir.c
git commit -m "pir: GPIO driver around the gate, event and state callbacks

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: Publish `rd03d/pir` and `rd03d/pir/state`; wire `main.c`

**Files:**
- Modify: `rd03d_uart/main/mqtt_pub.h`
- Modify: `rd03d_uart/main/mqtt_pub.c`
- Modify: `rd03d_uart/main/main.c`

- [ ] **Step 1: Extend the publisher header**

Append to `mqtt_pub.h`:

```c
#include <stdbool.h>
#include <stdint.h>

/* Publish one PIR event on rd03d/pir (QoS 0, not retained):
 *   {"n":17,"t":1760190000123,"radar":{"x":-420,"y":2310,"v":38}}
 * "radar" is the nearest radar target from the last parsed frame, or null.
 * t_ms is 0 until SNTP has synced. No-op while disconnected. */
void mqtt_pub_pir_event(uint32_t n, int64_t t_ms);

/* Publish rd03d/pir/state, retained, "1" while the PIR hold is open, "0" when
 * it closes. No-op while disconnected. */
void mqtt_pub_pir_state(bool active);
```

- [ ] **Step 2: Keep the last frame and add the two publishers**

In `mqtt_pub.c`, after the `static mqtt_throttle_t s_throttle;` line add:

```c
/* Last parsed frame, copied on the radar task and read on the PIR task. The
 * spinlock makes the copy atomic; a torn read would pair one target's x with
 * another frame's y. */
static rd03d_frame_t s_last_frame;
static portMUX_TYPE s_frame_lock = portMUX_INITIALIZER_UNLOCKED;
```

At the top of `mqtt_pub_frame()`, before the `if (!s_connected)` check, add:

```c
    portENTER_CRITICAL(&s_frame_lock);
    s_last_frame = *f;
    portEXIT_CRITICAL(&s_frame_lock);
```

Append to the end of `mqtt_pub.c`:

```c
void mqtt_pub_pir_event(uint32_t n, int64_t t_ms)
{
    esp_mqtt_client_handle_t client = s_client;
    if (!s_connected || client == NULL) {
        return;
    }
    rd03d_frame_t f;
    portENTER_CRITICAL(&s_frame_lock);
    f = s_last_frame;
    portEXIT_CRITICAL(&s_frame_lock);

    const rd03d_target_t *nearest = NULL;
    int32_t best = INT32_MAX;
    for (int i = 0; i < RD03D_NUM_TARGETS; i++) {
        const rd03d_target_t *t = &f.targets[i];
        if (!t->present) {
            continue;
        }
        int32_t d2 = (int32_t)t->x_mm * t->x_mm + (int32_t)t->y_mm * t->y_mm;
        if (d2 < best) {
            best = d2;
            nearest = t;
        }
    }
    char payload[128];
    int len;
    if (nearest) {
        len = snprintf(payload, sizeof(payload),
                       "{\"n\":%lu,\"t\":%lld,\"radar\":{\"x\":%d,\"y\":%d,\"v\":%d}}",
                       (unsigned long)n, (long long)t_ms,
                       nearest->x_mm, nearest->y_mm, nearest->speed_cms);
    } else {
        len = snprintf(payload, sizeof(payload),
                       "{\"n\":%lu,\"t\":%lld,\"radar\":null}",
                       (unsigned long)n, (long long)t_ms);
    }
    if (len <= 0 || len >= (int)sizeof(payload)) {
        return;
    }
    if (esp_mqtt_client_enqueue(client, "rd03d/pir", payload, len, 0, 0, true) < 0) {
        ESP_LOGW(TAG, "pir event %lu dropped", (unsigned long)n);
    }
}

void mqtt_pub_pir_state(bool active)
{
    esp_mqtt_client_handle_t client = s_client;
    if (!s_connected || client == NULL) {
        return;
    }
    /* Retained so a fresh Node-RED subscriber learns the current state. */
    esp_mqtt_client_enqueue(client, "rd03d/pir/state", active ? "1" : "0",
                            1, 0, 1, true);
}
```

Add `#include <stdint.h>` and `#include <limits.h>` to the includes at the top of `mqtt_pub.c` if not already present (INT32_MAX needs `<stdint.h>`).

- [ ] **Step 3: Wire `main.c`**

In `main.c`, after the existing `#include "wifi_link.h"` add:

```c
#if CONFIG_RD03D_ENABLE_PIR
#include "clock_ms.h"
#include "pir.h"
#endif
```

Before `app_main`, add the two callbacks:

```c
#if CONFIG_RD03D_ENABLE_PIR
/* Runs on the PIR task. One LED flash per event, like a radar publish. */
static void on_pir_event(const pir_event_t *ev)
{
    led_pulse();
#if CONFIG_RD03D_ENABLE_MQTT
    mqtt_pub_pir_event(ev->n, ev->t_ms);
#endif
}

static void on_pir_state(bool active)
{
    web_server_set_pir(active);
#if CONFIG_RD03D_ENABLE_MQTT
    mqtt_pub_pir_state(active);
#endif
}
#endif
```

In `app_main`, replace the block

```c
    wifi_link_start();
    web_server_start();
    ota_update_register(web_server_handle());
    xTaskCreate(ota_validation_task, "ota_valid", 3072, NULL, 5, NULL);
    led_init();
```

with

```c
    wifi_link_start();
    web_server_start();
    ota_update_register(web_server_handle());
    xTaskCreate(ota_validation_task, "ota_valid", 3072, NULL, 5, NULL);
    led_init();
#if CONFIG_RD03D_ENABLE_PIR
    clock_start();
    pir_init(on_pir_event, on_pir_state);
#endif
```

(`web_server_set_pir` is created in Task 6; the build is first attempted after that task.)

- [ ] **Step 4: Commit**

```bash
cd ~/Documents/rd03d-public && git add rd03d_uart/main/mqtt_pub.h rd03d_uart/main/mqtt_pub.c rd03d_uart/main/main.c
git commit -m "pir: publish rd03d/pir with the nearest radar target, retained state

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 6: PIR state on the chart page

**Files:**
- Modify: `rd03d_uart/main/web_server.h`
- Modify: `rd03d_uart/main/web_server.c:133-175` (`web_server_send_frame`)
- Modify: `rd03d_uart/main/index.html:121-141` (`onMessage`) and the HUD markup

- [ ] **Step 1: Add the setter to the header**

Append to `web_server.h`:

```c
/* Latest PIR hold state, folded into every WebSocket frame as "pir":0|1.
 * Builds without the PIR never call this and the field stays 0. */
void web_server_set_pir(bool active);
```

Add `#include <stdbool.h>` to the header's includes.

- [ ] **Step 2: Fold the state into the frame**

In `web_server.c`, near the other statics add `static volatile bool s_pir;` and at the end of the file:

```c
void web_server_set_pir(bool active)
{
    s_pir = active;
}
```

In `web_server_send_frame`, change the closing `snprintf` from

```c
        off += snprintf(msg->json + off, sizeof(msg->json) - (size_t)off,
                        "],\"dropped\":%" PRIu32 ",\"bad\":%" PRIu32 "}",
                        dropped, bad);
```

to

```c
        off += snprintf(msg->json + off, sizeof(msg->json) - (size_t)off,
                        "],\"dropped\":%" PRIu32 ",\"bad\":%" PRIu32
                        ",\"pir\":%d}",
                        dropped, bad, s_pir ? 1 : 0);
```

Check `ws_msg_t.json` has room: find its declaration (`char json[...]`) and confirm the size is at least 160 bytes; the longest frame is now about 110 characters.

- [ ] **Step 3: Show it on the page**

In `index.html`, find the stats line `statsEl.textContent = "frames " + ...` and append the PIR state:

```javascript
  statsEl.textContent =
    "frames " + frames + " · dropped " + msg.dropped + " · bad " + msg.bad +
    " · PIR " + (msg.pir ? "ACTIVE" : "idle");
  if (msg.pir && !pirWasActive) {
    pirFlashUntil = performance.now() + 400;
    pirLog.unshift(new Date().toLocaleTimeString() + " PIR");
    if (pirLog.length > 6) pirLog.pop();
    document.getElementById("pirlog").textContent = pirLog.join("  ·  ");
  }
  pirWasActive = !!msg.pir;
```

Declare the state near the other page globals (next to `let frames = 0` or equivalent):

```javascript
let pirWasActive = false, pirFlashUntil = 0;
const pirLog = [];
```

In `drawGrid()` (the function that draws the range arcs), after the arcs are drawn, add a flash of the outer ring:

```javascript
  if (performance.now() < pirFlashUntil) {
    ctx.strokeStyle = "#ffb000";
    ctx.lineWidth = 4 * dpr;
    ctx.beginPath();
    ctx.arc(ox, oy, 8 * s, Math.PI, 2 * Math.PI);
    ctx.stroke();
  }
```

(`ox, oy, s, dpr` are the existing origin, scale and pixel-ratio variables used by the arcs in that function; `8 * s` is the 8 m outer arc.)

Add a line to the HUD markup, next to the element with id `targets`:

```html
<div id="pirlog" style="color:#ffb000"></div>
```

- [ ] **Step 4: Commit**

```bash
cd ~/Documents/rd03d-public && git add rd03d_uart/main/web_server.h rd03d_uart/main/web_server.c rd03d_uart/main/index.html
git commit -m "chart: PIR state in the WebSocket frame, ring flash and event log

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 7: Build both images, flash, bench test

**Files:** none new. Needs the sensor wired: VDD→3V3, GND→GND, OUT→D1, 0.1 µF across VDD/GND at the sensor.

- [ ] **Step 1: Bring in the local configs**

```bash
cp ~/Documents/Code/VSCode/Claude/rd03d_uart/sdkconfig ~/Documents/rd03d-public/rd03d_uart/sdkconfig
cp ~/Documents/Code/VSCode/Claude/rd03d_uart/sdkconfig.ap ~/Documents/rd03d-public/rd03d_uart/sdkconfig.ap
cd ~/Documents/rd03d-public && git status --short | grep sdkconfig || echo "sdkconfig files are ignored: ok"
```

Expected: `sdkconfig files are ignored: ok`. Then redo Task 2 step 3 (the AP line) if `sdkconfig.ap` was overwritten.

- [ ] **Step 2: Build the station image**

```bash
cd ~/Documents/rd03d-public/rd03d_uart && source ~/esp/esp-idf-v5.5/export.sh >/dev/null && idf.py build 2>&1 | tail -5
```

Expected: `Project build complete.` with the binary size line. Fix compile errors in place; the usual ones are a missing include or the `ws_msg_t.json` buffer size.

- [ ] **Step 3: Build the AP image**

```bash
cd ~/Documents/rd03d-public/rd03d_uart && source ~/esp/esp-idf-v5.5/export.sh >/dev/null && idf.py -B build.ap -D SDKCONFIG=sdkconfig.ap build 2>&1 | tail -3
```

Expected: `Project build complete.`; `grep -c pir build.ap/compile_commands.json` prints `0` (PIR sources not compiled in the AP image).

- [ ] **Step 4: Run the host tests**

```bash
cd ~/Documents/rd03d-public/rd03d_uart/tests && for t in test_rd03d test_mqtt_throttle test_pir_gate; do src=${t#test_}; cc -Wall -Wextra -o $t $t.c ../main/$src.c && ./$t; done
```

Expected: three lines of `all tests passed`.

- [ ] **Step 5: Flash the staircase node over OTA**

Only after the sensor is wired to that XIAO (the deployed node is the one with the PIR). Commit first so the version string is clean (no `-dirty`):

```bash
cd ~/Documents/rd03d-public && git status --short
```

Expected: empty. Then:

```bash
cd ~/Documents/rd03d-public/rd03d_uart && curl -4 -X POST --data-binary @build/rd03d_uart.bin http://rd03d.local/update && sleep 100 && curl -4 http://rd03d.local/version
```

Expected: the version string of the new commit. If the node is on the bench over USB instead, use `idf.py -p /dev/cu.usbmodem101 flash monitor` (port may differ; `ls /dev/cu.usbmodem*`).

- [ ] **Step 6: Bench test**

With `mosquitto_sub -h iotstack.local -t 'rd03d/pir/#' -v` running on the Mac and the chart open at `http://rd03d.local`:

1. Wave a hand at about 1 m, then 3 m, then 5 m in front of the sensor. Expected per pass: one `rd03d/pir` line with increasing `n`, a `rd03d/pir/state 1` then `0` about half a second later, one LED flash, the chart's outer ring flashes amber and a line appears in the PIR log.
2. Stand still for 10 s in view. Expected: no events (PIR needs motion).
3. `t` in the payload is a 13-digit number after about a minute of uptime (SNTP synced). If it stays 0, check the log for `sntp` lines.

Record the three ranges that triggered in the walk-test note (Task 10).

---

### Task 8: Node-RED: PIR input, source switch, comparison CSV

**Files:**
- Modify: `node-red/flows-stair-light.json`
- Modify: `node-red/validate_flow.py`
- Modify: `node-red/README.md`

- [ ] **Step 1: Write the validator checks first**

Append to `validate_flow.py` before its final success print (the script ends with a success message; place these checks above it):

```python
# PIR companion (2026-10-11)
pir_in = one("mqtt in", lambda n: n.get("topic") == "rd03d/pir", "for rd03d/pir")
src = one("function", lambda n: n.get("name", "").startswith("source switch"), "source switch")
log = one("function", lambda n: n.get("name", "").startswith("compare log"), "compare log")
csv = one("file", lambda n: True, "CSV file node")
zone = one("function", lambda n: n.get("name", "").startswith("zone filter"), "zone filter")
trig = one("trigger")
if "SOURCE" not in src["func"]:
    fail("source switch must define SOURCE")
for name, node, target in (("zone filter", zone, src["id"]), ("pir in", pir_in, src["id"]),
                           ("source switch", src, trig["id"]), ("compare log", log, csv["id"])):
    if not any(target in out for out in node.get("wires", [])):
        fail(f"{name} must wire to {target}")
if not any(log["id"] in out for out in pir_in.get("wires", [])):
    fail("pir in must also wire to the compare log")
if not any(log["id"] in out for out in zone.get("wires", [])):
    fail("zone filter must also wire to the compare log")
```

Run: `python3 node-red/validate_flow.py` — Expected: `FAIL: expected exactly one mqtt in for rd03d/pir, got 0`.

- [ ] **Step 2: Add the nodes to the flow**

Edit `flows-stair-light.json` with a small script so the JSON stays valid:

```bash
cd ~/Documents/rd03d-public/node-red && python3 - <<'PY'
import json
p = "flows-stair-light.json"
nodes = json.load(open(p))
by = {n["id"]: n for n in nodes}

# zone filter now feeds the source switch and the compare log instead of the trigger directly
by["stairzone1"]["wires"] = [["stairsrc1", "stairdbg1", "stairlog1"]]

SRC = r'''// Which sensor may turn the light on. Edit SOURCE:
//   "radar"  - only in-zone radar events (today's behaviour)
//   "pir"    - only PIR events
//   "either" - whichever fires first
const SOURCE = "radar";
const isPir = msg.topic === "rd03d/pir";
if (SOURCE === "radar" && isPir) return null;
if (SOURCE === "pir" && !isPir) return null;
return msg;'''

LOG = r'''// One CSV line per trigger episode: which sensor fired first and the
// delay to the other, plus the radar position the PIR event carried and
// the one-way latency of the PIR event (needs SNTP on the node; t=0 means
// unsynced and latency is left blank).
const GAP_MS = 60000;              // a new episode starts after this much quiet
const now = Date.now();
let ep = context.get("ep") || null;
const isPir = msg.topic === "rd03d/pir";
let d = {};
try { d = JSON.parse(msg.payload); } catch (e) { d = {}; }
if (!ep || now - ep.last > GAP_MS) {
    ep = { start: now, first: isPir ? "pir" : "radar", other: null, last: now,
           pirRadar: "", pirLatency: "" };
}
ep.last = now;
const src = isPir ? "pir" : "radar";
if (isPir) {
    ep.pirRadar = d.radar ? (d.radar.x + " " + d.radar.y) : "none";
    ep.pirLatency = d.t ? String(now - d.t) : "";
}
let line = null;
if (ep.other === null && src !== ep.first) {
    ep.other = src;
    line = [new Date(ep.start).toISOString(), ep.first, src, now - ep.start,
            ep.pirRadar, ep.pirLatency].join(",");
}
context.set("ep", ep);
if (!line) return null;
msg.payload = line;
return msg;'''

nodes += [
  {"id": "stairpir1", "type": "mqtt in", "z": "stairtab1", "name": "PIR events",
   "topic": "rd03d/pir", "qos": "0", "datatype": "utf8", "broker": "stairbroker1",
   "nl": False, "rap": True, "rh": 0, "inputs": 0, "x": 130, "y": 200,
   "wires": [["stairsrc1", "stairlog1"]]},
  {"id": "stairsrc1", "type": "function", "z": "stairtab1", "name": "source switch (EDIT SOURCE)",
   "func": SRC, "outputs": 1, "timeout": 0, "noerr": 0, "initialize": "", "finalize": "",
   "libs": [], "x": 360, "y": 120, "wires": [["stairtrig1"]]},
  {"id": "stairlog1", "type": "function", "z": "stairtab1", "name": "compare log",
   "func": LOG, "outputs": 1, "timeout": 0, "noerr": 0, "initialize": "", "finalize": "",
   "libs": [], "x": 360, "y": 260, "wires": [["stairfile1"]]},
  {"id": "stairfile1", "type": "file", "z": "stairtab1", "name": "stair_compare.csv",
   "filename": "/data/stair_compare.csv", "filenameType": "str", "appendNewline": True,
   "createDir": True, "overwriteFile": "false", "encoding": "none", "x": 600, "y": 260,
   "wires": [[]]},
]
# move the trigger's old input: it now comes from the source switch only
json.dump(nodes, open(p, "w"), indent=2)
open(p, "a").write("\n")
PY
python3 validate_flow.py
```

Expected: the validator's success message. (Node-RED in the IOTstack container writes `/data/stair_compare.csv`, which is `~/IOTstack/volumes/nodered/data/stair_compare.csv` on the Pi.)

- [ ] **Step 3: Document the import and the CSV**

In `node-red/README.md` add a section:

```markdown
## PIR companion (2026-10-11)

The flow also subscribes to `rd03d/pir`. Edit `SOURCE` in the "source switch"
node: `radar` (default) keeps today's behaviour, `pir` runs the light from the
PIR only, `either` from whichever fires first.

The "compare log" writes `/data/stair_compare.csv` (on the Pi:
`~/IOTstack/volumes/nodered/data/stair_compare.csv`), one line per trigger
episode:

    episode start (ISO), first sensor, second sensor, delay ms, radar x y at the PIR event, PIR one-way latency ms

A new episode starts after 60 s of quiet. The latency column is empty until
the node's SNTP has synced (`t` of 0 in the payload).
```

- [ ] **Step 4: Commit**

```bash
cd ~/Documents/rd03d-public && git add node-red/flows-stair-light.json node-red/validate_flow.py node-red/README.md
git commit -m "flow: PIR input, source switch, radar-vs-PIR comparison CSV

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

- [ ] **Step 5: Import on the user's Node-RED**

This is the user's step: import the JSON (Menu → Import → select file, "replace existing" for the Stair Light tab), keep the Tasmota topic he already edited, Deploy. Then `mosquitto_pub -h iotstack.local -t rd03d/pir -m '{"n":1,"t":0,"radar":null}'` from the Mac. Expected: with SOURCE `radar`, no light change and a line in the debug sidebar from the compare log only after a radar event follows; with SOURCE `either`, the light turns on.

---

### Task 9: Case: pod on the shell's +X wall for the long-distance lens, plug, probe check, export

**Files:**
- Modify: `case/fusion_scripts/03_shell.py` (new step 7 before the final `print("FrontShell bodies:...`)
- Modify: `case/fusion_scripts/90_verify.py`
- Modify: `case/fusion_scripts/05_export.py`
- Local only (gitignored): `case/models/EKMC1603111.STEP`, Panasonic's model of the sensor, used for the interference check

**The sensor, measured from Panasonic's STEP (2026-10-11, "PaPIRs WL VZ Long Distance Detection Type"; native frame: Z is the lens axis, z = 0 is the metal base):**

| feature | value |
| --- | --- |
| lens dome | sphere R 10.89 centred on the axis at z 8.4; apex at z 19.29 |
| lens base ring | Ø20.6 (r 10.3), z 7.4..8.4 |
| flange | Ø18.8 (r 9.4) round plate, z 6.4..7.4, with four small tabs reaching r ≈ 10.6 at the corners |
| neck | plastic, tapering 4° from r 5.0 at z 6.4 to r ≈ 4.6 at z 0.95 |
| metal can | r 4.65, z −0.9..0.95; underside is an annulus r 3.67..4.65 at z −0.9 |
| pins | three, Ø0.45, on a 2.5 mm radius circle, z −5.5..0 |

So this is not a small can with a lens on top: the lens is Ø20.6 and 11 mm tall, wider than everything below it. The sensor goes into the pod from the FRONT, dome out, flange seated in a recess, neck and can through a bore, and is held by a tube-shaped plug pressed into the bore from the back that bears on the can's underside annulus. The wires come off the pins inside the plug's bore and leave through a pass-through into the XIAO bay.

**Pod geometry.** Shell frame: outer box x ±23, y ±25, z −8 (back rim) to 16 (front face, printed on the bed). The user confirmed the case hangs XIAO end (+X) DOWN, so the bore tilts `pirTilt` (18°) from +Z toward +X and the PIR looks outward and 18° down. Depth `d` is measured along the bore axis from the pod's front face into the pod; the sensor's z maps to d = 8.4 − z (its lens base ring top sits on the front face plane).

- Pod block: fused to the outer +X wall, full shell depth (z −8..16) so its front face is coplanar with the shell's and prints on the bed. Width along X = 2·(recessR + podWall) + 24·tan(tilt), length along Y = 2·(recessR + podWall).
- Recess: cylinder r `pirRecessR` = 10.6 (0.3 clearance on the lens base ring), from d −0.5 (outside the face) to d 2.0 (the flange underside at sensor z 6.4). The dome then stands 11 mm proud of the face.
- Bore: cylinder r `pirBoreR` = 5.3 from d 2.0 through the back face. Neck (r ≤ 5.0) and can (r 4.65) pass with ≥ 0.3 clearance.
- Plug (separate body `PirPlug`): tube OD `pirPlugOD` = 10.5 (0.05 per side interference in the Ø10.6 bore; tune by sanding or scale in the slicer), ID 7.0, length 6.0, inserted from the back; its front rim bears on the can's underside annulus (r 3.67..4.65) at d 9.3. The three pins and the wires run inside the plug's Ø7 bore.
- Wire pass-through: Ø`pirWireDia` = 3.0, horizontal (−X) from the bore axis at d 13 (behind the plug's front, in the wire space) into the XIAO bay, ending at x = intW/2 − 0.15.
- Printing: front face on the bed; the recess is a pocket in the bed-side face and the bore is a hole tilted 18° from the print axis, both fine without supports.

**Interference check against the real sensor:** import `case/models/EKMC1603111.STEP` as an occurrence, place it with its Z axis along the bore axis and its z 8.4 plane on the pod front face (rotation about Y by −tilt·sign so +Z tips toward +X, then translate to the front-face point), and run `des.analyzeInterference` between the sensor body and the shell: must report zero. `04_boards.py` shows the import, placement and interference pattern; copy its approach, not its code, since the rotation axis differs (Y here, X there).

- [ ] **Step 1: Add the parameters and the pod to `03_shell.py`**

Add after the imports:

```python
def ensure_params(des):
    """PIR pod parameters. Not in 01_setup.py: re-running that resets hand-tuned values."""
    spec = [
        ("pirRecessR", "10.6 mm", "recess radius: lens base ring r10.3 + 0.3"),
        ("pirRecessD", "2.0 mm", "recess depth: lens ring + flange (sensor z 6.4..8.4)"),
        ("pirBoreR", "5.3 mm", "bore radius for the neck (r5.0) and can (r4.65)"),
        ("pirTilt", "18 deg", "bore tilt from the shell normal, toward +X"),
        ("pirTiltSign", "1", "+1: XIAO end hangs DOWN on the wall (confirmed 2026-10-11); -1: up"),
        ("pirPodWall", "2.0 mm", "pod wall around the recess"),
        ("pirWireDia", "3.0 mm", "wire pass-through into the XIAO bay"),
        ("pirWireD", "13.0 mm", "pass-through depth along the bore axis from the front face"),
        ("pirPlugOD", "10.5 mm", "plug tube OD: light interference in the Ø10.6 bore"),
        ("pirPlugID", "7.0 mm", "plug tube ID: pins on r2.5 and their wires pass"),
        ("pirPlugL", "6.0 mm", "plug tube length"),
    ]
    ups = des.userParameters
    for name, expr, comment in spec:
        if ups.itemByName(name) is None:
            unit = "deg" if "deg" in expr else ("" if expr.lstrip("-").isdigit() else "mm")
            ups.add(name, adsk.core.ValueInput.createByString(expr), unit, comment)
            print("added", name, "=", expr)
```

Call `ensure_params(des)` in `run()` right after `root = des.rootComponent`.

Add step 7 in `run()` just before `print("FrontShell bodies:", comp.bRepBodies.count)`:

```python
    # 7. PIR POD (2026-10-11): block on the outer +X wall, full shell depth
    # so its front face prints on the bed with the shell. The EKMC1603111's
    # lens (Ø20.6, 11 mm tall) is wider than its neck, so the sensor enters
    # from the FRONT: lens base ring + flange in a 2 mm recess, neck and can
    # through a bore, a plug tube pressed in from the back holds it. The bore
    # tilts pirTilt toward +X so the PIR looks 18 deg down with the case
    # hanging XIAO-end-down.
    import math
    recessR, recessD = p(des, "pirRecessR"), p(des, "pirRecessD")
    boreR, podWall = p(des, "pirBoreR"), p(des, "pirPodWall")
    # Fusion hands angle parameters back in radians (18 deg -> 0.314); the
    # guard also accepts a value typed in degrees.
    tilt = p(des, "pirTilt") if p(des, "pirTilt") < 1.6 else math.radians(p(des, "pirTilt"))
    sgn = 1.0 if p(des, "pirTiltSign") >= 0 else -1.0
    xOuter = intW / 2 + wall                     # +X outer face of the shell
    zTop, zBack = intD + wall, -backT
    depth = zTop - zBack
    podW = 2 * (recessR + podWall) + depth * math.tan(tilt)
    podL = 2 * (recessR + podWall)
    podCx = xOuter + podW / 2

    sk = comp.sketches.add(comp.xYConstructionPlane)
    rect(sk, podCx, 0, podW, podL)
    extrude(comp, sk.profiles.item(0), zBack, zTop,
            adsk.fusion.FeatureOperations.JoinFeatureOperation,
            participants=[shell_body])
    print("pir pod block ok (%.1f x %.1f mm at x=%.1f)" % (podW * 10, podL * 10, podCx * 10))

    # bore axis through the pod centre at the front face, direction
    # (sgn*sin t, 0, cos t); along(d) is the axis point d into the pod.
    ax = adsk.core.Vector3D.create(sgn * math.sin(tilt), 0.0, math.cos(tilt))
    front_pt = adsk.core.Point3D.create(podCx, 0.0, zTop)
    def along(d):
        return adsk.core.Point3D.create(front_pt.x - ax.x * d, 0.0, front_pt.z - ax.z * d)

    tbm = adsk.fusion.TemporaryBRepManager.get()
    base = comp.features.baseFeatures.add()
    base.startEdit()
    recess_cyl = tbm.createCylinderOrCone(along(-0.05), recessR, along(recessD), recessR)
    bore_cyl = tbm.createCylinderOrCone(along(recessD - 0.01), boreR,
                                        along(depth / math.cos(tilt) + 0.3), boreR)
    wp = along(p(des, "pirWireD"))
    wire_cyl = tbm.createCylinderOrCone(
        adsk.core.Point3D.create(wp.x, 0.0, wp.z), p(des, "pirWireDia") / 2,
        adsk.core.Point3D.create(intW / 2 - 0.015, 0.0, wp.z), p(des, "pirWireDia") / 2)
    tools = [comp.bRepBodies.add(b, base) for b in (recess_cyl, bore_cyl, wire_cyl)]
    base.finishEdit()
    ci = comp.features.combineFeatures.createInput(shell_body, collection(tools))
    ci.operation = adsk.fusion.FeatureOperations.CutFeatureOperation
    ci.isKeepToolBodies = False
    comp.features.combineFeatures.add(ci)
    if comp.bRepBodies.count != 1:
        raise RuntimeError("pir bore split the shell: %d bodies" % comp.bRepBodies.count)
    print("pir recess r=%.2f d=%.2f, bore r=%.2f, tilt %.1f deg ok"
          % (recessR * 10, recessD * 10, boreR * 10, math.degrees(tilt)))

    # 7b. PLUG: tube pressed into the bore from the back; its front rim bears
    # on the can's underside annulus (r 3.67..4.65). Separate component,
    # exported as its own STL, printed standing on either end.
    plug_occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    plug = plug_occ.component
    plug.name = "PirPlug"
    sk = plug.sketches.add(plug.xYConstructionPlane)
    sk.sketchCurves.sketchCircles.addByCenterRadius(adsk.core.Point3D.create(0, 0, 0), p(des, "pirPlugOD") / 2)
    sk.sketchCurves.sketchCircles.addByCenterRadius(adsk.core.Point3D.create(0, 0, 0), p(des, "pirPlugID") / 2)
    ring = None
    for i in range(sk.profiles.count):            # the annular profile, not the inner disc
        pr = sk.profiles.item(i)
        if ring is None or pr.areaProperties().area > ring.areaProperties().area:
            ring = pr
    extrude(plug, ring, 0, p(des, "pirPlugL"),
            adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    print("pir plug ok (OD %.1f ID %.1f L %.1f)" % (p(des, "pirPlugOD") * 10, p(des, "pirPlugID") * 10, p(des, "pirPlugL") * 10))
```

`wall`, `intW`, `intD`, `backT`, `shell_body`, `comp`, `root` are already defined earlier in `run()`. If `03_shell.py` deletes and rebuilds `FrontShell` at its start, also delete any existing `PirPlug` and `EKMC` occurrences there the same way (rename-then-delete, as the file does for FrontShell).

- [ ] **Step 2: Run the shell script and look at it**

Fusion is open on `rd-03d_case` with the MCP server running. Do NOT run `01_setup.py`; do not save, close or discard the document.

```bash
cd ~/Documents/rd03d-public/case/fusion_scripts && python3 run_fusion.py script 03_shell.py 2>&1 | tail -15
python3 run_fusion.py screenshot ../pir_pod_iso.png iso && python3 run_fusion.py screenshot ../pir_pod_right.png right
```

Expected: `pir pod block ok`, `pir recess ... ok`, `pir plug ok`, `FrontShell bodies: 1`. Look at both screenshots (Read the PNGs): a block on the +X side, a large elliptical recess on its front face with a smaller bore inside it, the bore reaching the back rim. Delete the two PNGs afterwards (they are not deliverables).

- [ ] **Step 3: Place the real sensor and check interference (new script `91_pir_fit.py`)**

Create `case/fusion_scripts/91_pir_fit.py`: imports `case/models/EKMC1603111.STEP` (path relative to the repo; resolve from `__file__` as `run_fusion.py` scripts do, or hard-code the absolute path as `05_export.py` does with `OUT`), deletes any prior `EKMC` occurrence first, then places it: build `adsk.core.Matrix3D`, `setToRotation(-sgn * tilt, Vector3D(0,1,0), Point3D(0,0,0))` so the model's +Z tips toward +X by `tilt`, then translate so the model's point (0,0,8.4 mm) lands on `front_pt` (same `podCx`, `zTop` formulas as `03_shell.py`; recompute them from the parameters). Snapshot (`des.snapshots.add()` if pending) and run `des.analyzeInterference` on the sensor body + the shell body; print the result count and the interfering volume. Expected: 0 results. If not zero, print which z range interferes and stop; the pod script is what gets fixed, never the sensor.

Run: `python3 run_fusion.py script 91_pir_fit.py 2>&1 | tail -8`.

- [ ] **Step 4: Add the probe check to `90_verify.py`**

Add after `check_radar_cable_exit`:

```python
def check_pir_pod(shell, des):
    """Pod on the +X wall: recess and bore void, recess floor and pod walls
    solid, bore open at the back, wire hole into the bay."""
    import math
    def pv(n): return des.userParameters.itemByName(n).value
    wall, intW, intD, backT = pv("wall"), pv("intW"), pv("intD"), pv("backT")
    recessR, recessD, boreR, podWall = pv("pirRecessR"), pv("pirRecessD"), pv("pirBoreR"), pv("pirPodWall")
    tilt = pv("pirTilt") if pv("pirTilt") < 1.6 else math.radians(pv("pirTilt"))
    sgn = 1.0 if pv("pirTiltSign") >= 0 else -1.0
    xOuter = intW / 2 + wall
    zTop, zBack = intD + wall, -backT
    depth = zTop - zBack
    podW = 2 * (recessR + podWall) + depth * math.tan(tilt)
    podCx = xOuter + podW / 2
    ax = (sgn * math.sin(tilt), math.cos(tilt))
    def along(d, side=0.0):            # cm along the axis in, cm sideways in Y -> mm tuple
        return ((podCx - ax[0] * d) * 10, side * 10, (zTop - ax[1] * d) * 10)
    x, y, z = along(0.1); void(shell, x, y, z, "recess centre")
    x, y, z = along(0.1, side=recessR - 0.03); void(shell, x, y, z, "recess edge")
    x, y, z = along(recessD + 0.05, side=(boreR + recessR) / 2); solid(shell, x, y, z, "recess floor ring")
    x, y, z = along(recessD + 0.2); void(shell, x, y, z, "bore just behind the floor")
    x, y, z = along(1.0, side=boreR - 0.03); void(shell, x, y, z, "bore edge mid-depth")
    x, y, z = along(depth / math.cos(tilt) - 0.1); void(shell, x, y, z, "bore open at the back")
    x, y, z = along(1.0, side=recessR + podWall / 2); solid(shell, x, y, z, "pod wall +Y")
    x, y, z = along(1.0, side=-(recessR + podWall / 2)); solid(shell, x, y, z, "pod wall -Y")
    xw, _, zw = along(pv("pirWireD"))
    void(shell, (intW / 2 + wall / 2) * 10, 0.0, zw, "wire hole through +X wall")
    if not (-backT * 10 + 2 < zw < intD * 10 - 1):
        FAILURES.append("wire hole at z=%.1f mm is outside the usable cavity depth" % zw)
```

In `run()`, add `check_pir_pod(shell, des)` after `check_no_shell_notch(shell)` (`des` already exists there).

Run: `python3 run_fusion.py script 90_verify.py --read-only 2>&1 | tail -8`. Expected: no `EXPECTED` lines, no `verification failure(s)`. Fix `03_shell.py`, not the probes, if one fails.

- [ ] **Step 5: Export the shell and the plug**

In `05_export.py`, add `("PirPlug", "rd03d_pir_plug.stl")` to the component tuple. Set `OUT` to the real path for the run and restore the placeholder before committing, as the existing workflow does. Run `python3 run_fusion.py script 05_export.py 2>&1 | tail -4 && ls -la ../*.stl`. Expected: both STLs exported; the shell STL is larger than before.

- [ ] **Step 6: Print check (user)**

Slice the shell front-face-down, no supports, PETG, 0.6 mm nozzle. Print the plug. Test-fit the sensor: flange seats in the recess, plug presses in from the back and holds it.

- [ ] **Step 7: Commit**

```bash
cd ~/Documents/rd03d-public && git add .gitignore case/fusion_scripts/03_shell.py case/fusion_scripts/90_verify.py case/fusion_scripts/91_pir_fit.py case/fusion_scripts/05_export.py case/rd03d_case_shell.stl case/rd03d_pir_plug.stl
git commit -m "case: PIR pod on the shell's +X wall for the EKMC long-distance lens, plug, fit check

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 9b: Move the PIR pod from the shell to the back plate (2026-10-25)

**Why:** the user wants all wiring on the plate (the shell lifts off clean), and a pod standing up from the plate prints its recess as a top-side pocket, so no supports. Supersedes the shell pod built in Task 9; keep that work in history, reuse its code.

**Files:**
- Modify: `case/fusion_scripts/02_backplate.py` (wing + pod tower + plug + pin hole + wire hole + two Technic holes; `ensure_params` gains the pir* parameters, moved from 03)
- Modify: `case/fusion_scripts/03_shell.py` (remove step 7/7b pod and plug; add the +X wall notch; keep the `pirTilt`/pod-width parameters it needs to size the notch by reading them, not creating them)
- Modify: `case/fusion_scripts/91_pir_fit.py` (place the sensor on the plate's pod; plug parked in the plate's bore)
- Modify: `case/fusion_scripts/90_verify.py` (`check_pir_pod(plate, shell, des)` for the new location; `check_shell_notch` for the cut-out; `check_lego_bores_clear` extended to the two wing holes; drop the shell-pod probes)
- Modify: `case/README.md`, `case/rd03d_case_back.stl`, `case/rd03d_case_shell.stl`, `case/rd03d_pir_plug.stl`

**Geometry (shell frame).** Plate outline is `intW − 2·rimGap` by `intH − 2·rimGap`, z −backT..0; its +X edge is at x = intW/2 − rimGap (20.85). Shell outer +X face at x = intW/2 + wall (23). Pod tower: width along X = 2·(pirRecessR + pirPodWall) + 24·tan(pirTilt) (≈ 34.8), length along Y = 2·(pirRecessR + pirPodWall) (27); it starts at x = 23 + 0.3 (gap to the shell wall) and spans z −2..16 standing on the wing. Wing: z −8..−2, x from the plate edge (20.85, fused to the plate) to the tower's far end, y ±13.5 (the tower's length). Bore axis as before: through the tower's centre at z 16, direction (sin18°, 0, cos18°) into −z, open at the back face z −8 (through the wing). Recess, ledge, groove, bore, plug, slot, keeper pin, wire hole exactly as in the current `03_shell.py` step 7/7b (copy the code, re-anchor `podCx` and `zTop`). Wire hole: Ø3 along −X from the bore at the pin-tip depth, exiting the tower's −X face at x 23.3 at z ≈ 0..+2, into the notch. Technic holes: two, at (x 48.95, y ±4) on the existing grid (x = 0.95 + k·8), Ø`legoHole` through the wing from the back with the `legoCbDia`/`legoCbDepth` counterbore on the back face, 8 mm deep in total (they end inside the tower's solid material); they must clear the bore exit (centred x ≈ 33 at z −8, r 5.9) and the keeper pin. Shell notch: in `03_shell.py`, cut the +X wall (x 21..23) over y ±(13.5 + 0.3) from z −8 up to z +2, so the wall sits on the wing (z −2) with a 4 mm wire slot above; then the edge-count assertions in 6a–6c must still pass (do the notch AFTER them, and only if the perimeter-edge selectors stay at 8, otherwise relax the assertion with a comment).

**Order inside `02_backplate.py`:** the wing and tower must be added AFTER step 6 (which trims everything to the plate outline) and after the Technic holes (step 7), as a new step 14; the two wing holes are cut in step 14 with the same code pattern as step 7.

- [ ] **Step 1:** `02_backplate.py`: `ensure_params` gains the pir* spec (copy from 03, including `pirPinDia`, `pirPinD` expression, `pirPlugOD` 12.1, `pirSeatD`); step 14 builds wing, tower, cuts (recess/ledge/groove/bore/wire/pin, one Combine, participants = plate body, one-body check), two Technic holes, and the `PirPlug` component (delete-then-rebuild). Run `02_backplate.py`; expect the pod prints and `BackPlate bodies: 1`.
- [ ] **Step 2:** `03_shell.py`: delete step 7/7b and the PirPlug/PaPIRs deletion lines; add the notch; run; expect the 6a–6c prints unchanged and `FrontShell bodies: 1`. Run `04_boards.py`? No: the boards are unaffected; skip.
- [ ] **Step 3:** `91_pir_fit.py`: front-face axis point now from the tower on the plate (`podCx`, `zTop` = 16); interference bodies: sensor + plate + shell + plug; the plug/plate press-fit annulus is the one expected pair; everything else 0. Expect `PIR FIT OK`.
- [ ] **Step 4:** `90_verify.py`: move `check_pir_pod` to probe the plate (recess, ledge, groove, bore mid-depth and at the back face, both ±Y tower walls, pin hole both walls, wire hole exit at x 23.3), add the two wing bores to `check_lego_bores_clear` (open from the back, counterbore present, bore clear 0.5 mm above the back face), add `check_shell_notch(shell)` (void at (22, 0, −4) and (22, 0, +1); solid at (22, 0, +4) and at (22, ±16, −4)), restore `check_no_shell_notch` to its original probes only if they do not overlap the new notch, otherwise retire it with a comment. Expect `VERIFY OK`.
- [ ] **Step 5:** export all three STLs; the back STL grows, the shell STL shrinks back toward its pre-pod size.
- [ ] **Step 6:** README: the pod paragraphs move to the plate section; Printing says no supports again; assembly order updated (sensor into the plate's pod, plug and keeper from the back, wires through the notch; shell last).
- [ ] **Step 7:** commit `case: move the PIR pod to the back plate wing; shell notch; no supports` with the usual trailer.

### Task 9c: Straight socket on the plate, pod box on the shell (2026-10-25)

As built (2026-10-25): pirCx 35.5 (34.5 put the Technic hole at (24.95, 4) 0.20 mm from the boss foot in plan), box x 21..51, cavity to 49, wing to 48.85, snapYpx 19; boss foot fillet r 1.0 added after review. Commits 71b7312, f02e55c.

**Why:** two user decisions after the test print: the PIR must look where the radar looks (`pirTilt` = 0, max field overlap), and the plate should only hold the sensor while the shell carries the housing. Supersedes 9b's wing tower; keep its wing, plug, keeper pin, Technic holes and probe style.

**Files:** `02_backplate.py` (step 14 rewritten: wing, socket boss, bore through, wire hole, keeper pin, two Technic holes at (24.95, ±4), `PirPlug`), `03_shell.py` (step 7 rewritten: pod box replacing the +X wall over the pod width, Ø23 lens hole in the top, edge softening; `snapYpx` 19), `90_verify.py`, `91_pir_fit.py`, `05_export.py` (unchanged unless needed), `case/README.md`, three STLs.

**Geometry (case frame).** Shell wall 2 (`wall`), interior ±21 × ±23, front face z 16, back rim z −8, plate z −8..0 with edge at ±20.85 (`intW/2 − rimGap`).
- Pod box (shell): inner cavity x from 21 (the old wall's inner line; the wall segment over |y| ≤ 13.5 is removed from z −8 to 16) to `xBoxIn` = 21 + 27 = 48, y ±13.5, z −8..14 (the top is the 2 mm front face z 14..16). Outer x 50, y ±15.5. Socket/lens axis at x `pirCx` = 21 + 13.5 = 34.5, y 0. Lens hole in the top: Ø23 (`pirRecessR` 11.5) through z 14..16. Box exterior: vertical corner fillets r 2.5 at (50, ±15.5), front chamfer 1.0 around the box's top perimeter (continuing the shell's), back rim fillet 0.8; the shell's own 6a–6c selectors must still find their edges (8/8 counts may change: assert the new true counts with a comment).
- Wing (plate): z −8..−2, x 20.85..(48 − rimGap = 47.85), y ±(13.5 − rimGap = 13.35), fused to the plate (0.5 mm overlap into the plate as 9b did). Wing rear entry chamfers as 9b.
- Socket boss (plate): cylinder outer r 7.7 (`pirSocketR`) at (34.5, 0) from z −2 to z 14.0 (`pirSeatZ` = 16 − 2.0: the flange underside); bore r 5.9 (`pirBoreR`) from z 16 (above the top) down through the wing to z −8.1. The flange (r 9.4) and hooks (r 9.6..10.7, hanging to z 13.1) sit outside the boss (r 7.7) and inside the lens hole/box cavity. Assert hooks clear the boss: `pirSocketR` < 9.6 − 0.3.
- Plug: OD 12.1, ID 9, L 10 (`pirPlugOD/ID/L`), slot 3.2 toward −X, pressed in from the back; front rim at z 16 − `pirSeatD` 9.3 = 6.7 bearing on the can's underside; back end at z −3.3. Keeper pin Ø1.9 along Y through the wing at z −3.3 − 0.95 − 0.5 = −4.75 (`pirPinZ` expression from pirSeatD, pirPlugL, pirPinDia), x = 34.5; assert ≥ 1.5 mm of wing below the hole and clear of the Technic holes.
- Wire hole: Ø3 along −X from the bore axis at z 4.0 (pin-tip level, inside the plug's slot) through the boss wall, exiting at x ≤ 26.8 into the pod cavity; the wires then run over the wing into the XIAO bay (no wall in the way).
- Technic holes: (24.95, ±4), Ø`legoHole` through the wing from the back, counterbore `legoCbDia` × `legoCbDepth` on the back face, through-hole (6 mm wing); assert clear of the boss (r 7.7 at x 34.5: edge 26.8 vs hole edge 27.4 — if that is under 0.6 mm, move the holes to (24.95, ±12)? No: wing is ±13.35; keep (24.95, ±4) and shrink nothing; if the clearance is < 0.6 mm, move the socket centre to x 35.5 and widen the box by 1 mm; print the clearance).
- Snaps: `snapYpx` 19 (bumps y 16..22 on the remaining +X wall segments, pockets likewise); assert the bump is clear of the box's ±Y walls (15.5) by ≥ 0.3 and of the cavity ±Y walls (23) by ≥ 0.5.
- Shell interior ceiling over the box is the same z 14 as the main cavity; the dome top at z 16 + 11 = 27 outside.

Steps: as Task 9b (params → 02 → 03 → 91 → 90 → 05 → README → commit "case: PIR socket on the plate, pod box on the shell, PIR parallel to the radar"). 91: sensor placed with its Z along +Z at (34.5, 0), z 8.4 plane at z 16 − 2.0 + 1.0 + 1.0 = 16.0 (ring top flush with the face): i.e. sensor origin z = 16 − 8.4 = 7.6; bodies: sensor + plate + shell + plug; expected pair: plug/plate annulus only. 90: probes for socket solid (r 6.8 ring at z 10), bore void (axis z 10, z −7.9), boss top at z 14 (solid at r 6.8 z 13.9, void at z 14.1), hooks clearance (void at r 10.1 z 13.5), wire hole (void at (27.5, 0, 4) and solid at (27.5, 0, 6.5)), pin hole both wing sides, Technic bores open from the back and through, wing fused (solid at (21.5, 0, −5)), box walls solid ((49, 0, 5), (34.5, ±14.5, 5)), box cavity void ((40, 0, 5), (34.5, 0, −5) above the wing? no: wing occupies z −8..−2 inside the box: void at (34.5, 10, −1)), lens hole void at (34.5, 0, 15), (34.5, ±11.2, 15), top solid at (34.5, ±12.0, 15), old +X wall gone at (22, 0, 5) and present at (22, ±18, 5), snaps at ±19, the shell's 6a–6c edges.

### Task 9d: Front bezel retains the sensor; no plug, no keeper (2026-10-25)

**Why:** after the first print of layout 9c the user asked for the Ø23 gap around the lens to go and for a part inserted from the front that holds the sensor down, keeping its free rotation. A bayonet bezel does both and makes the back-side plug and filament keeper unnecessary. The sensor is then clamped between the socket rim (flange underside) and the bezel's lip (on the dome's flank).

**Files:** `02_backplate.py` (step 14: bore becomes blind at the wing top, keeper-pin hole and `PirPlug` removed, wing widened to the new box cavity, snap pockets move from the plate's +X edge into the wing's ±Y faces), `03_shell.py` (box widened; lens hole Ø25.6 with three bayonet notches; +X-wall snap bumps replaced by bumps on the box's inner ±Y walls; new `PirBezel` component), `90_verify.py`, `91_pir_fit.py` (sensor + plate + shell + bezel, zero interference except the designed 0.2 mm lip preload on the dome, reported as expected), `05_export.py` (export `rd03d_pir_bezel.stl`; drop the plug), `case/README.md`, STLs.

**Geometry (case frame, lens axis at (pirCx 35.5, 0), shell face z 16; sensor origin z 7.6: flange underside z 14.0 on the boss rim, lens ring top z 16, dome sphere R 10.89 centred (pirCx, 0, 16), latch tabs to r 11.1 between z 14.2 and 16).**
- Pod box: inner cavity y ±`pirBoxHalfY` = 15.5 (was 13.5), x 21..49 unchanged, outer y ±17.5. Wing y ±(15.5 − rimGap). The shell's +X wall segments remain only at |y| > 17.5; the old +X snap bumps and the plate's +X pockets (snapYpx) are deleted. New snap pair: bumps on the box's inner ±Y walls (0.5 proud, 6 long along X centred x 40, z −5.5..−4.5) into blind pockets in the wing's ±Y faces (same pattern as the plate's −X pair, depth 0.5 + clearance). `snapYpx` retired.
- Lens hole in the top: r `pirHoleR` = 12.8 (Ø25.6). Three bayonet notches through the top skin (z 14..16) at angles 60°, 180°, 300° from +X: radial r 12.8..14.6, tangential width 4.6 mm.
- `PirBezel` (new component, prints flat on its flange, no supports): flange ring r 11.6..15.3 by 1.2 mm (z 16..17.2 when fitted); lip above it: a cone from (r 11.6, z 17.2) to (r 10.5, z 18.6) whose upper inner edge meets the dome sphere with 0.2 mm preload (dome surface at r 10.5 is z 16 + √(10.89² − 10.5²) = 18.88; the lip edge at 18.6 ⇒ 0.2 mm interference after the 0.1 fit); skirt below the flange r 11.5..12.6 from z 16 down to z 13.9 (passes the hole with 0.2 clearance, clears the lens tabs r 11.1 by 0.4); three lugs at the skirt's bottom, z 12.2..13.7, r 12.6..14.3, tangential 4.0 mm, at 60°, 180°, 300° so they drop through the notches; after a 30° turn they sit at 90°, 210°, 330° under 0.3 mm of clearance below the skin (lug top 13.7 vs skin underside 14.0) inside the cavity (lug at 90° reaches y 14.3 < 15.5; at 330° x 47.9 < 49; at 210° x 23.1 > 21). The lip preload pushes the bezel up so the lugs bear on the skin's underside and friction holds the rotation; a 0.3 mm detent bump on the skin's underside at the rest angle is optional, skip unless trivial.
- Plate: socket boss and bore as 9c but the bore stops at the wing top (z −2): the cap on the pins hangs to about z −0.9, 1.1 mm clear; keeper-pin hole deleted; `PirPlug` deleted; wire hole unchanged (z 4). Technic holes (24.95, ±4) unchanged.
- Assembly: sensor into the socket from the front (any rotation), wires out through the boss's side hole over the wing into the XIAO bay, shell on (snaps into the wing), bezel dropped on with its lugs in the notches and turned 30° clockwise until it stops; to remove, turn back and lift.

**Fit calibration:** holes print true, outside walls 0.2 under on this printer (measured 2026-10-25). The plate-to-shell gap is set by `rimGap` and will be re-set from caliper measurements of the printed plate and cavity (see the session); apply the same value to the wing/box fit.

Steps as 9c (params → 02 → 03 → 91 → 90 → 05 → README → commit "case: bayonet bezel retains the PIR from the front; plug and keeper removed"). 91: the only expected interference pair is bezel/sensor (the lip preload ring, bound its volume to the designed 0.2 mm × contact band and print it); everything else zero. 90: probes for the hole r 12.8 (void at r 12.6 z 15, solid at r 13.0 z 15 away from the notches), each notch (void at r 13.7 at 60/180/300°, solid at r 13.7 at the rest angles 90/210/330°), the bore floor (solid at (pirCx, 0, −2.2), void at z −1.8), no keeper hole (solid at the old pin position), wing snap pockets and box bumps, the lugs' rest positions free of the box walls (void at r 14.5 at 90°, z 13), the bezel's own geometry (solid flange at r 13.5 z 16.6, void inside the lip at r 10.3 z 18.4, solid lip at r 10.9 z 18.0, lug solid at (r 13.5, 60°, z 13), skirt solid at r 12.0 z 15 and void at r 12.0 z 13 between lugs) when probed in the bezel's own frame.

### Task 10: Walk test, numbers, docs

**Files:**
- Create: `docs/2026-10-pir-companion-notes.md`
- Modify: `README.md` (Parts list, firmware topics), `rd03d_uart/README.md` (wiring, Kconfig, topics)

- [ ] **Step 1: Walk test**

With the node on the wall, SOURCE set to `radar`, the chart open and the CSV branch deployed, the user walks the standard route: approach from downstairs on the left, up the stairs, out the top on the right, out of range, back, past the top, down, out to the left. Then read the CSV:

```bash
ssh pi@192.168.1.243 'tail -20 ~/IOTstack/volumes/nodered/data/stair_compare.csv'
```

Expected: one line per approach; the "first sensor" column and the delay in ms say which sensor led on each approach; the latency column holds a number (tens of ms on the LAN).

- [ ] **Step 2: Write the note**

`docs/2026-10-pir-companion-notes.md`, plain prose, with: bench ranges from Task 7, the walk-test lines pasted as a table (episode, first, delay, radar position), the median PIR latency, and the sentence that the battery gate needs: the mains-mode baseline latency in ms. End with the orientation that was actually used (XIAO end down or up) and the `pirTiltSign` that matched it.

- [ ] **Step 3: Update the READMEs**

`rd03d_uart/README.md`: add the PIR wiring table (VDD→3V3, OUT→D1/GPIO1 with internal pull-down, GND→GND, 0.1 µF at the sensor), the three Kconfig options, the two topics with their payloads, and the line that the AP image leaves the PIR out. `README.md`: add `Panasonic EKMC1603111 PIR` to the Parts list and one sentence under "What is in this repository" pointing at the spec and the notes.

- [ ] **Step 4: Commit and push the branch**

```bash
cd ~/Documents/rd03d-public && git add docs/2026-10-pir-companion-notes.md README.md rd03d_uart/README.md
git commit -m "docs: PIR companion wiring, topics, walk-test and latency numbers

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
git push -u origin feat/pir-companion
```

Merging to `main` is the user's call after he has read the numbers.
