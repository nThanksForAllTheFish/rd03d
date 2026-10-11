#pragma once

#include <stdbool.h>
#include <stdint.h>

#include "rd03d.h"

/* Starts the MQTT client: waits for WiFi, resolves the configured broker
 * (mDNS for .local names), connects with a Last-Will on rd03d/status, and
 * auto-reconnects. Safe to call once at boot. */
void mqtt_pub_start(void);

/* Publish per-target movement/gone events for a parsed frame, throttled by
 * the configured minimum movement. No-op while disconnected. Publishes are
 * enqueued (non-blocking for the caller); an event can be dropped if the
 * outbox is full — the throttle re-triggers on the next movement and the
 * reconnect reset restores state after outages. */
void mqtt_pub_frame(const rd03d_frame_t *f);

/* Publish one PIR event on rd03d/pir (QoS 0, not retained):
 *   {"n":17,"t":1760190000123,"radar":{"x":-420,"y":2310,"v":38}}
 * "radar" is the nearest radar target from the last parsed frame, or null.
 * t_ms is 0 until SNTP has synced. No-op while disconnected. */
void mqtt_pub_pir_event(uint32_t n, int64_t t_ms);

/* Publish rd03d/pir/state, retained, "1" while the PIR hold is open, "0" when
 * it closes. No-op while disconnected. */
void mqtt_pub_pir_state(bool active);
