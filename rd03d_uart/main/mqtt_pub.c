#include "mqtt_pub.h"

#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "mdns.h"
#include "mqtt_client.h"
#include "sdkconfig.h"

#include "led.h"
#include "mqtt_throttle.h"
#include "wifi_link.h"

static const char *TAG = "mqtt_pub";

#define STATUS_TOPIC        "rd03d/status"
#define RESOLVE_RETRY_MS    30000
#define MQTT_KEEPALIVE_S    15  /* short keepalive so the LWT fires quickly */

static esp_mqtt_client_handle_t s_client;
static volatile bool s_connected;
static volatile bool s_reset_pending;
static mqtt_throttle_t s_throttle;

/* Last parsed frame, copied on the radar task and read on the PIR task. The
 * spinlock makes the copy atomic; a torn read would pair one target's x with
 * another frame's y. */
static rd03d_frame_t s_last_frame;
static portMUX_TYPE s_frame_lock = portMUX_INITIALIZER_UNLOCKED;
static int64_t s_last_frame_us;
/* Latest PIR hold state, kept even while disconnected so it can be
 * republished on connect (the retained copy may be stale by then). */
static volatile bool s_pir_state;

#define PIR_FRAME_MAX_AGE_US 300000

static void on_mqtt_event(void *arg, esp_event_base_t base, int32_t id,
                          void *data)
{
    (void)arg;
    (void)base;
    (void)data;
    if (id == MQTT_EVENT_CONNECTED) {
        s_reset_pending = true; /* throttle reset runs on the radar task */
        s_connected = true;
        esp_mqtt_client_publish(s_client, STATUS_TOPIC, "online", 0, 0, 1);
#if CONFIG_RD03D_ENABLE_PIR
        esp_mqtt_client_publish(s_client, "rd03d/pir/state",
                                s_pir_state ? "1" : "0", 1, 1, 1);
#endif
        ESP_LOGI(TAG, "connected to broker");
    } else if (id == MQTT_EVENT_DISCONNECTED) {
        s_connected = false;
        ESP_LOGW(TAG, "disconnected from broker");
    }
}

/* esp-mqtt resolves via plain DNS, which cannot see mDNS names — resolve
 * .local hosts ourselves through the already-running mDNS stack. */
static bool resolve_broker_uri(char *uri, size_t uri_len)
{
    const char *host = CONFIG_RD03D_MQTT_HOST;
    const char *suffix = ".local";
    size_t hlen = strlen(host);
    size_t slen = strlen(suffix);

    if (hlen > slen && strcmp(host + hlen - slen, suffix) == 0) {
        char name[64];
        if (hlen - slen >= sizeof(name)) {
            ESP_LOGE(TAG, "broker hostname too long");
            return false;
        }
        memcpy(name, host, hlen - slen);
        name[hlen - slen] = '\0';

        esp_ip4_addr_t addr = { 0 };
        esp_err_t err = mdns_query_a(name, 3000, &addr);
        if (err != ESP_OK) {
            ESP_LOGW(TAG, "mdns query for %s failed: %s", host,
                     esp_err_to_name(err));
            return false;
        }
        snprintf(uri, uri_len, "mqtt://" IPSTR ":%d", IP2STR(&addr),
                 CONFIG_RD03D_MQTT_PORT);
    } else {
        snprintf(uri, uri_len, "mqtt://%s:%d", host, CONFIG_RD03D_MQTT_PORT);
    }
    return true;
}

static void mqtt_connect_task(void *arg)
{
    (void)arg;
    while (!wifi_link_is_up()) {
        vTaskDelay(pdMS_TO_TICKS(1000));
    }

    char uri[96];
    while (!resolve_broker_uri(uri, sizeof(uri))) {
        vTaskDelay(pdMS_TO_TICKS(RESOLVE_RETRY_MS));
    }
    ESP_LOGI(TAG, "broker: %s", uri);

    const esp_mqtt_client_config_t cfg = {
        .broker.address.uri = uri,
        .session = {
            .keepalive = MQTT_KEEPALIVE_S,
            .last_will = {
                .topic = STATUS_TOPIC,
                .msg = "offline",
                .qos = 0,
                .retain = 1,
            },
        },
    };
    s_client = esp_mqtt_client_init(&cfg); /* config strings are copied */
    if (s_client == NULL) {
        ESP_LOGE(TAG, "mqtt client init failed; MQTT unavailable");
        vTaskDelete(NULL);
        return;
    }
    ESP_ERROR_CHECK(esp_mqtt_client_register_event(s_client, ESP_EVENT_ANY_ID,
                                                   on_mqtt_event, NULL));
    ESP_ERROR_CHECK(esp_mqtt_client_start(s_client));
    vTaskDelete(NULL);
}

void mqtt_pub_start(void)
{
    mqtt_throttle_init(&s_throttle, CONFIG_RD03D_MQTT_MOVE_MM);
    xTaskCreate(mqtt_connect_task, "mqtt_connect", 4096, NULL, 5, NULL);
}

void mqtt_pub_frame(const rd03d_frame_t *f)
{
    portENTER_CRITICAL(&s_frame_lock);
    s_last_frame = *f;
    s_last_frame_us = esp_timer_get_time();
    portEXIT_CRITICAL(&s_frame_lock);

    if (!s_connected) {
        return;
    }
    esp_mqtt_client_handle_t client = s_client;
    if (client == NULL) {
        return;
    }
    if (s_reset_pending) {
        s_reset_pending = false;
        mqtt_throttle_reset(&s_throttle);
    }
    for (int i = 0; i < RD03D_NUM_TARGETS; i++) {
        mqtt_throttle_action_t act =
            mqtt_throttle_eval(&s_throttle, i, &f->targets[i]);
        if (act == MQTT_THROTTLE_NONE) {
            continue;
        }
        char topic[24];
        snprintf(topic, sizeof(topic), "rd03d/target/%d", i + 1);
        int msg_id = -1;
        if (act == MQTT_THROTTLE_MOVED) {
            char payload[64];
            int n = snprintf(payload, sizeof(payload),
                             "{\"x\":%d,\"y\":%d,\"v\":%d}",
                             f->targets[i].x_mm, f->targets[i].y_mm,
                             f->targets[i].speed_cms);
            if (n > 0 && n < (int)sizeof(payload)) {
                msg_id = esp_mqtt_client_enqueue(client, topic, payload, n,
                                                 0, 0, true);
            }
        } else { /* MQTT_THROTTLE_GONE */
            msg_id = esp_mqtt_client_enqueue(client, topic, "{\"gone\":true}",
                                             0, 0, 0, true);
        }
        if (msg_id < 0) {
            /* Dropped (outbox full / disconnect race). Self-heals: the next
             * movement or the reconnect reset re-triggers a publish. */
            ESP_LOGW(TAG, "publish dropped for %s (%d)", topic, msg_id);
        } else {
            /* Only on success, so the LED means "a message reached the
             * broker" rather than "we considered sending one". */
            led_pulse();
        }
    }
}

void mqtt_pub_pir_event(uint32_t n, int64_t t_ms)
{
    esp_mqtt_client_handle_t client = s_client;
    if (!s_connected || client == NULL) {
        return;
    }
    rd03d_frame_t f;
    int64_t frame_us;
    portENTER_CRITICAL(&s_frame_lock);
    f = s_last_frame;
    frame_us = s_last_frame_us;
    portEXIT_CRITICAL(&s_frame_lock);

    /* A stalled radar must not be reported as a current target. */
    bool fresh = frame_us != 0 &&
                 esp_timer_get_time() - frame_us <= PIR_FRAME_MAX_AGE_US;

    const rd03d_target_t *nearest = NULL;
    uint32_t best = UINT32_MAX;
    for (int i = 0; i < RD03D_NUM_TARGETS; i++) {
        const rd03d_target_t *t = &f.targets[i];
        if (!fresh || !t->present) {
            continue;
        }
        uint32_t d2 = (uint32_t)((int32_t)t->x_mm * t->x_mm) +
                      (uint32_t)((int32_t)t->y_mm * t->y_mm);
        if (d2 < best) {
            best = d2;
            nearest = t;
        }
    }
    char payload[128];
    int len;
    if (nearest) {
        len = snprintf(payload, sizeof(payload),
                       "{\"n\":%lu,\"t\":%lld,\"radar\":{\"x\":%d,\"y\":%d,\"v\":%d}}",
                       (unsigned long)n, (long long)t_ms,
                       nearest->x_mm, nearest->y_mm, nearest->speed_cms);
    } else {
        len = snprintf(payload, sizeof(payload),
                       "{\"n\":%lu,\"t\":%lld,\"radar\":null}",
                       (unsigned long)n, (long long)t_ms);
    }
    if (len <= 0 || len >= (int)sizeof(payload)) {
        return;
    }
    if (esp_mqtt_client_enqueue(client, "rd03d/pir", payload, len, 0, 0, true) < 0) {
        ESP_LOGW(TAG, "pir event %lu dropped", (unsigned long)n);
    }
}

void mqtt_pub_pir_state(bool active)
{
    s_pir_state = active;
    esp_mqtt_client_handle_t client = s_client;
    if (!s_connected || client == NULL) {
        return;
    }
    /* Retained so a fresh Node-RED subscriber learns the current state. */
    if (esp_mqtt_client_enqueue(client, "rd03d/pir/state", active ? "1" : "0",
                                1, 1, 1, true) < 0) {
        ESP_LOGW(TAG, "pir state %d dropped", active ? 1 : 0);
    }
}
