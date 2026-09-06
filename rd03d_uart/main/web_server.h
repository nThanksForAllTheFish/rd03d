#pragma once

#include <stdint.h>

#include "rd03d.h"

#include "esp_http_server.h"

/* Starts the HTTP server: GET / serves the embedded page, GET /ws is a
 * WebSocket that pushes one JSON message per radar frame. */
void web_server_start(void);

/* The running HTTP server handle, or NULL if the server failed to start. */
httpd_handle_t web_server_handle(void);

/* Formats {"t":[{x,y,v}|null x3],"dropped":N,"bad":N} and sends it to every
 * connected WebSocket client. Never blocks the caller beyond queueing work;
 * clients whose sends fail are dropped. No server/clients -> no-op. */
void web_server_send_frame(const rd03d_frame_t *f, uint32_t dropped,
                           uint32_t bad);
