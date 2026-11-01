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

static void test_extension_swallows_edge_past_original_window(void)
{
    pir_gate_t g;
    pir_gate_init(&g, 500);
    pir_gate_edge(&g, 1000);                            /* until 1500 */
    assert(pir_gate_edge(&g, 1400) == PIR_GATE_NONE);   /* until 1900 */
    assert(pir_gate_edge(&g, 1600) == PIR_GATE_NONE);   /* past 1500, inside 1900 */
    assert(pir_gate_edge(&g, 2100) == PIR_GATE_EVENT);
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
    test_extension_swallows_edge_past_original_window();
    test_hold_end_time();
    test_inactive_before_any_edge();
    test_zero_hold_every_edge_is_an_event();
    test_event_count();
    test_wraparound_64bit_not_a_concern_but_large_values_ok();
    printf("all tests passed\n");
    return 0;
}
