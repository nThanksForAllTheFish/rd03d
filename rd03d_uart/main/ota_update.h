#pragma once

#include "esp_http_server.h"

/* Registers GET /update (upload page) and POST /update (firmware upload)
 * on an already-started HTTP server. NULL server -> logs and does nothing. */
void ota_update_register(httpd_handle_t server);
