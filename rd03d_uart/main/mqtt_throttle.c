#include "mqtt_throttle.h"

#include <string.h>

void mqtt_throttle_init(mqtt_throttle_t *t, uint32_t threshold_mm)
{
    memset(t, 0, sizeof(*t));
    t->threshold_mm = threshold_mm;
}

void mqtt_throttle_reset(mqtt_throttle_t *t)
{
    for (int i = 0; i < RD03D_NUM_TARGETS; i++) {
        t->slots[i].published = false;
    }
}

mqtt_throttle_action_t mqtt_throttle_eval(mqtt_throttle_t *t, int i,
                                          const rd03d_target_t *target)
{
    mqtt_throttle_slot_t *s = &t->slots[i];

    if (!target->present) {
        if (s->published) {
            s->published = false;
            return MQTT_THROTTLE_GONE;
        }
        return MQTT_THROTTLE_NONE;
    }

    if (s->published) {
        int64_t dx = (int64_t)target->x_mm - s->x_mm;
        int64_t dy = (int64_t)target->y_mm - s->y_mm;
        int64_t thr = (int64_t)t->threshold_mm * t->threshold_mm;
        if (dx * dx + dy * dy < thr) {
            return MQTT_THROTTLE_NONE;
        }
    }

    s->published = true;
    s->x_mm = target->x_mm;
    s->y_mm = target->y_mm;
    return MQTT_THROTTLE_MOVED;
}
