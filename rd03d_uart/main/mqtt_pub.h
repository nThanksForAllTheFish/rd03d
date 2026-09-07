#pragma once

#include "rd03d.h"

/* Starts the MQTT client: waits for WiFi, resolves the configured broker
 * (mDNS for .local names), connects with a Last-Will on rd03d/status, and
 * auto-reconnects. Safe to call once at boot. */
void mqtt_pub_start(void);

/* Publish per-target movement/gone events for a parsed frame, throttled by
 * the configured minimum movement. No-op while disconnected; never blocks
 * meaningfully (QoS 0, esp-mqtt handles the socket). */
void mqtt_pub_frame(const rd03d_frame_t *f);
