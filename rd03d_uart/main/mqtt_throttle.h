#pragma once

#include <stdbool.h>
#include <stdint.h>

#include "rd03d.h"

/* NOT thread-safe: init/reset/eval must all run on (or be serialized with)
 * one task. In this firmware that is the radar loop task. */

typedef enum {
    MQTT_THROTTLE_NONE = 0, /* nothing to publish for this target */
    MQTT_THROTTLE_MOVED,    /* publish coordinates */
    MQTT_THROTTLE_GONE,     /* publish the gone event */
} mqtt_throttle_action_t;

typedef struct {
    bool published;         /* a position has been published since reset */
    int16_t x_mm;           /* last PUBLISHED position (anchor for distance) */
    int16_t y_mm;
} mqtt_throttle_slot_t;

typedef struct {
    mqtt_throttle_slot_t slots[RD03D_NUM_TARGETS];
    uint32_t threshold_mm;
} mqtt_throttle_t;

void mqtt_throttle_init(mqtt_throttle_t *t, uint32_t threshold_mm);

/* Clear published state (call on MQTT reconnect) so present targets
 * republish immediately. Keeps the threshold. */
void mqtt_throttle_reset(mqtt_throttle_t *t);

/* Decide what to publish for target slot i (0-based) given its state in the
 * newest frame. Updates internal state when returning MOVED or GONE. Only
 * call while the MQTT connection is up — state must not advance while
 * publishes would be dropped.
 * i must be in [0, RD03D_NUM_TARGETS). A MOVED/GONE return obligates the
 * caller to publish: state advances assuming the publish happens. */
mqtt_throttle_action_t mqtt_throttle_eval(mqtt_throttle_t *t, int i,
                                          const rd03d_target_t *target);
