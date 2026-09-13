#pragma once

/* Visual echo of radar publish events on the board's user LED, so a deployed
 * node can be checked at a glance without a laptop or a browser. One flash
 * per event the publisher emits - or, in builds without MQTT, per event it
 * would have emitted.
 *
 * Compiles to no-ops when RD03D_LED_GPIO is negative. */

/* Configure the LED pin and the one-shot timer. Call once at boot. */
void led_init(void);

/* Light the LED for RD03D_LED_MS then extinguish it. Retriggerable: a pulse
 * arriving mid-pulse restarts the timer rather than stacking, so a burst of
 * events reads as one longer flash. Non-blocking; safe from the radar task. */
void led_pulse(void);
