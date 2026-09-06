#pragma once

#include <stdbool.h>

/* Joins the WiFi network configured via menuconfig (RD03D_WIFI_SSID/PASSWORD)
 * as a station and keeps it connected (auto-reconnect on drop). Returns after
 * starting WiFi; connection proceeds in the background and is logged. */
void wifi_link_start(void);

/* True while the station holds an IP address. */
bool wifi_link_has_ip(void);
