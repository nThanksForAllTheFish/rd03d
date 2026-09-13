#pragma once

#include <stdbool.h>

/* Joins the WiFi network configured via menuconfig (RD03D_WIFI_SSID/PASSWORD)
 * as a station and keeps it connected (auto-reconnect on drop). Returns after
 * starting WiFi; connection proceeds in the background and is logged. */
void wifi_link_start(void);

/* True while the device is reachable over WiFi: in station mode, once it holds
 * an IP; in SoftAP mode, once the AP has started. Deliberately NOT "has IP" -
 * no IP event ever fires in AP mode, and main.c's OTA validation keys off this
 * function, so a station-only definition would roll back every OTA'd AP image. */
bool wifi_link_is_up(void);
