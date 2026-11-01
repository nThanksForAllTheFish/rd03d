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

/* NOT thread-safe and not ISR-safe: init/edge/active/hold_end/count must
 * all run on (or be serialized with) one task. In this firmware that is
 * the PIR task; the ISR and expiry timer only post to its queue. */

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

/* hold_ms = 0 means every edge is an event and the gate is never active. */
void pir_gate_init(pir_gate_t *g, uint32_t hold_ms);

/* Feed one rising edge at time now_ms. */
pir_gate_action_t pir_gate_edge(pir_gate_t *g, int64_t now_ms);

/* True while a hold window is open. */
bool pir_gate_active(const pir_gate_t *g, int64_t now_ms);

/* End of the current hold window (ms). Returns 0 before the first edge. */
int64_t pir_gate_hold_end(const pir_gate_t *g);

uint32_t pir_gate_count(const pir_gate_t *g);
