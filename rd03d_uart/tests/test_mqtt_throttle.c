#include <assert.h>
#include <stdio.h>
#include "../main/mqtt_throttle.h"

static rd03d_target_t at(int16_t x, int16_t y)
{
    rd03d_target_t t = { .present = true, .x_mm = x, .y_mm = y,
                         .speed_cms = 0, .resolution_mm = 360 };
    return t;
}

static rd03d_target_t absent(void)
{
    rd03d_target_t t = { 0 };
    return t;
}

static void test_first_appearance_publishes(void)
{
    mqtt_throttle_t th;
    mqtt_throttle_init(&th, 200);
    rd03d_target_t t = at(100, 500);
    assert(mqtt_throttle_eval(&th, 0, &t) == MQTT_THROTTLE_MOVED);
}

static void test_small_move_is_silent(void)
{
    mqtt_throttle_t th;
    mqtt_throttle_init(&th, 200);
    rd03d_target_t t = at(100, 500);
    mqtt_throttle_eval(&th, 0, &t);
    t = at(199, 500); /* 99 mm from published anchor */
    assert(mqtt_throttle_eval(&th, 0, &t) == MQTT_THROTTLE_NONE);
    t = at(100, 640); /* 140 mm */
    assert(mqtt_throttle_eval(&th, 0, &t) == MQTT_THROTTLE_NONE);
}

static void test_drift_accumulates_from_anchor(void)
{
    /* Two sub-threshold steps in the same direction cross the threshold
     * relative to the PUBLISHED anchor, so the second one publishes. */
    mqtt_throttle_t th;
    mqtt_throttle_init(&th, 200);
    rd03d_target_t t = at(0, 500);
    mqtt_throttle_eval(&th, 0, &t);
    t = at(150, 500);
    assert(mqtt_throttle_eval(&th, 0, &t) == MQTT_THROTTLE_NONE);
    t = at(300, 500); /* 300 mm from anchor */
    assert(mqtt_throttle_eval(&th, 0, &t) == MQTT_THROTTLE_MOVED);
}

static void test_exact_threshold_publishes(void)
{
    mqtt_throttle_t th;
    mqtt_throttle_init(&th, 200);
    rd03d_target_t t = at(0, 500);
    mqtt_throttle_eval(&th, 0, &t);
    t = at(200, 500); /* exactly 200 mm */
    assert(mqtt_throttle_eval(&th, 0, &t) == MQTT_THROTTLE_MOVED);
}

static void test_moved_updates_anchor(void)
{
    mqtt_throttle_t th;
    mqtt_throttle_init(&th, 200);
    rd03d_target_t t = at(0, 500);
    mqtt_throttle_eval(&th, 0, &t);
    t = at(300, 500);
    mqtt_throttle_eval(&th, 0, &t); /* anchor now (300,500) */
    t = at(400, 500); /* 100 mm from new anchor */
    assert(mqtt_throttle_eval(&th, 0, &t) == MQTT_THROTTLE_NONE);
}

static void test_gone_fires_once(void)
{
    mqtt_throttle_t th;
    mqtt_throttle_init(&th, 200);
    rd03d_target_t t = at(100, 500);
    mqtt_throttle_eval(&th, 0, &t);
    rd03d_target_t a = absent();
    assert(mqtt_throttle_eval(&th, 0, &a) == MQTT_THROTTLE_GONE);
    assert(mqtt_throttle_eval(&th, 0, &a) == MQTT_THROTTLE_NONE);
}

static void test_absent_without_publish_is_silent(void)
{
    mqtt_throttle_t th;
    mqtt_throttle_init(&th, 200);
    rd03d_target_t a = absent();
    assert(mqtt_throttle_eval(&th, 0, &a) == MQTT_THROTTLE_NONE);
}

static void test_reset_republishes_present_target(void)
{
    mqtt_throttle_t th;
    mqtt_throttle_init(&th, 200);
    rd03d_target_t t = at(100, 500);
    mqtt_throttle_eval(&th, 0, &t);
    mqtt_throttle_reset(&th);
    assert(mqtt_throttle_eval(&th, 0, &t) == MQTT_THROTTLE_MOVED);
}

static void test_slots_are_independent(void)
{
    mqtt_throttle_t th;
    mqtt_throttle_init(&th, 200);
    rd03d_target_t t0 = at(100, 500);
    rd03d_target_t t1 = at(-900, 2000);
    assert(mqtt_throttle_eval(&th, 0, &t0) == MQTT_THROTTLE_MOVED);
    assert(mqtt_throttle_eval(&th, 1, &t1) == MQTT_THROTTLE_MOVED);
    t0 = at(100, 500);
    assert(mqtt_throttle_eval(&th, 0, &t0) == MQTT_THROTTLE_NONE);
    rd03d_target_t a = absent();
    assert(mqtt_throttle_eval(&th, 1, &a) == MQTT_THROTTLE_GONE);
}

static void test_extreme_coordinates_no_overflow(void)
{
    /* Corner-to-corner jump: dx=dy=65534 -> dx^2+dy^2 needs 64-bit math. */
    mqtt_throttle_t th;
    mqtt_throttle_init(&th, 200);
    rd03d_target_t t = at(-32767, -32767);
    mqtt_throttle_eval(&th, 0, &t);
    t = at(32767, 32767);
    assert(mqtt_throttle_eval(&th, 0, &t) == MQTT_THROTTLE_MOVED);
}

static void test_threshold_zero_publishes_every_frame(void)
{
    mqtt_throttle_t th;
    mqtt_throttle_init(&th, 0);
    rd03d_target_t t = at(100, 500);
    assert(mqtt_throttle_eval(&th, 0, &t) == MQTT_THROTTLE_MOVED);
    assert(mqtt_throttle_eval(&th, 0, &t) == MQTT_THROTTLE_MOVED);
}

static void test_flapping_target(void)
{
    mqtt_throttle_t th;
    mqtt_throttle_init(&th, 200);
    rd03d_target_t t = at(100, 500);
    rd03d_target_t a = absent();
    assert(mqtt_throttle_eval(&th, 0, &t) == MQTT_THROTTLE_MOVED);
    assert(mqtt_throttle_eval(&th, 0, &a) == MQTT_THROTTLE_GONE);
    assert(mqtt_throttle_eval(&th, 0, &t) == MQTT_THROTTLE_MOVED);
    assert(mqtt_throttle_eval(&th, 0, &a) == MQTT_THROTTLE_GONE);
    assert(mqtt_throttle_eval(&th, 0, &a) == MQTT_THROTTLE_NONE);
}

static void test_reset_while_absent_no_spurious_gone(void)
{
    mqtt_throttle_t th;
    mqtt_throttle_init(&th, 200);
    rd03d_target_t t = at(100, 500);
    rd03d_target_t a = absent();
    mqtt_throttle_eval(&th, 0, &t);
    mqtt_throttle_eval(&th, 0, &a); /* GONE */
    mqtt_throttle_reset(&th);
    assert(mqtt_throttle_eval(&th, 0, &a) == MQTT_THROTTLE_NONE);
}

int main(void)
{
    test_first_appearance_publishes();
    test_small_move_is_silent();
    test_drift_accumulates_from_anchor();
    test_exact_threshold_publishes();
    test_moved_updates_anchor();
    test_gone_fires_once();
    test_absent_without_publish_is_silent();
    test_reset_republishes_present_target();
    test_slots_are_independent();
    test_extreme_coordinates_no_overflow();
    test_threshold_zero_publishes_every_frame();
    test_flapping_target();
    test_reset_while_absent_no_spurious_gone();
    printf("all tests passed\n");
    return 0;
}
