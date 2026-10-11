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
