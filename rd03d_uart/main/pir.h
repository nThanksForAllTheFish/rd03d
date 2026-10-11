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
