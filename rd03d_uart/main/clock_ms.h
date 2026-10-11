#pragma once

#include <stdint.h>

/* Starts SNTP (pool.ntp.org). Call it before WiFi is up; lwIP sends its first
 * request once the interface has an address. Station mode only: an access
 * point with no uplink has nothing to sync to, and clock_epoch_ms() stays 0. */
void clock_start(void);

/* Milliseconds since the Unix epoch, or 0 until the first SNTP sync. Node-RED
 * subtracts this from its own arrival time to get one-way latency, which is
 * the number the battery variant's deep-sleep gate is decided on. */
int64_t clock_epoch_ms(void);
