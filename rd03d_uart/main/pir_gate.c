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
