#include "web_server.h"

#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "esp_http_server.h"
#include "esp_log.h"

static const char *TAG = "web_server";

extern const uint8_t index_html_start[] asm("_binary_index_html_start");
extern const uint8_t index_html_end[] asm("_binary_index_html_end");

/* Matches HTTPD_DEFAULT_CONFIG's max_open_sockets (7); big enough for a
 * handful of viewers (Mac + phone) with room to spare. */
#define MAX_WS_CLIENTS 7

static httpd_handle_t s_server;

typedef struct {
    char json[192];
} ws_msg_t;

static esp_err_t root_get(httpd_req_t *req)
{
    httpd_resp_set_type(req, "text/html");
    return httpd_resp_send(req, (const char *)index_html_start,
                           index_html_end - index_html_start);
}

static esp_err_t ws_get(httpd_req_t *req)
{
    /* NOTE: esp_http_server completes the WS opening handshake internally
     * and does NOT call this handler for it (see httpd_uri.c: "If the
     * request is websocket handshake, then do not call the uri->handler").
     * So this handler only ever runs for frames a client actually sends.
     * We are push-only, so just drain and ignore whatever arrives; new
     * clients are discovered by enumerating the live socket list in
     * ws_send_work instead of tracking a handshake callback. */
    httpd_ws_frame_t frame = { 0 };
    esp_err_t ret = httpd_ws_recv_frame(req, &frame, 0);
    if (ret != ESP_OK) {
        return ret;
    }
    if (frame.len > 128) {
        return ESP_FAIL; /* push-only endpoint; oversized inbound frame */
    }
    if (frame.len > 0) {
        uint8_t *buf = malloc(frame.len);
        if (buf == NULL) {
            return ESP_ERR_NO_MEM;
        }
        frame.payload = buf;
        ret = httpd_ws_recv_frame(req, &frame, frame.len);
        free(buf);
    }
    return ret;
}

/* Runs on the httpd task via httpd_queue_work. */
static void ws_send_work(void *arg)
{
    ws_msg_t *msg = arg;
    httpd_ws_frame_t frame = {
        .final = true,
        .type = HTTPD_WS_TYPE_TEXT,
        .payload = (uint8_t *)msg->json,
        .len = strlen(msg->json),
    };

    int fds[MAX_WS_CLIENTS];
    size_t fd_count = MAX_WS_CLIENTS;
    if (httpd_get_client_list(s_server, &fd_count, fds) == ESP_OK) {
        for (size_t i = 0; i < fd_count; i++) {
            int fd = fds[i];
            if (httpd_ws_get_fd_info(s_server, fd) != HTTPD_WS_CLIENT_WEBSOCKET) {
                continue; /* plain HTTP client, not a WS viewer */
            }
            if (httpd_ws_send_frame_async(s_server, fd, &frame) != ESP_OK) {
                ESP_LOGW(TAG, "ws send failed, dropping fd %d", fd);
                httpd_sess_trigger_close(s_server, fd);
            }
        }
    }
    free(msg);
}

void web_server_start(void)
{
    httpd_config_t cfg = HTTPD_DEFAULT_CONFIG();
    if (httpd_start(&s_server, &cfg) != ESP_OK) {
        ESP_LOGE(TAG, "httpd_start failed, web UI unavailable");
        s_server = NULL;
        return;
    }

    static const httpd_uri_t root_uri = {
        .uri = "/",
        .method = HTTP_GET,
        .handler = root_get,
    };
    static const httpd_uri_t ws_uri = {
        .uri = "/ws",
        .method = HTTP_GET,
        .handler = ws_get,
        .is_websocket = true,
    };
    ESP_ERROR_CHECK(httpd_register_uri_handler(s_server, &root_uri));
    ESP_ERROR_CHECK(httpd_register_uri_handler(s_server, &ws_uri));
    ESP_LOGI(TAG, "http server listening on port %d", cfg.server_port);
}

httpd_handle_t web_server_handle(void)
{
    return s_server;
}

void web_server_send_frame(const rd03d_frame_t *f, uint32_t dropped,
                           uint32_t bad)
{
    if (s_server == NULL) {
        return;
    }
    ws_msg_t *msg = malloc(sizeof(*msg));
    if (msg == NULL) {
        return;
    }

    int off = snprintf(msg->json, sizeof(msg->json), "{\"t\":[");
    for (int i = 0; i < RD03D_NUM_TARGETS; i++) {
        if (off <= 0 || off >= (int)sizeof(msg->json)) {
            break;
        }
        const rd03d_target_t *t = &f->targets[i];
        const char *sep = (i < RD03D_NUM_TARGETS - 1) ? "," : "";
        if (t->present) {
            off += snprintf(msg->json + off, sizeof(msg->json) - (size_t)off,
                            "{\"x\":%d,\"y\":%d,\"v\":%d}%s",
                            t->x_mm, t->y_mm, t->speed_cms, sep);
        } else {
            off += snprintf(msg->json + off, sizeof(msg->json) - (size_t)off,
                            "null%s", sep);
        }
    }
    if (off > 0 && off < (int)sizeof(msg->json)) {
        off += snprintf(msg->json + off, sizeof(msg->json) - (size_t)off,
                        "],\"dropped\":%" PRIu32 ",\"bad\":%" PRIu32 "}",
                        dropped, bad);
    }
    if (off <= 0 || off >= (int)sizeof(msg->json)) {
        free(msg); /* formatting error or truncation: drop this frame */
        return;
    }

    if (httpd_queue_work(s_server, ws_send_work, msg) != ESP_OK) {
        free(msg);
    }
}
