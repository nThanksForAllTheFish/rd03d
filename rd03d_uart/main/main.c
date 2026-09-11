#include <inttypes.h>
#include <stdio.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/uart.h"
#include "esp_log.h"
#include "esp_ota_ops.h"

#if CONFIG_RD03D_ENABLE_MQTT
#include "mqtt_pub.h"
#endif
#include "ota_update.h"
#include "rd03d.h"
#include "web_server.h"
#include "wifi_link.h"

/* XIAO ESP32-C6, ESP side: D6 = GPIO16 (UART1 TX), D7 = GPIO17 (UART1 RX). */
#define RADAR_UART_NUM   UART_NUM_1
#define RADAR_PIN_TX     16
#define RADAR_PIN_RX     17
#define RADAR_BAUD       256000
#define UART_RX_BUF_SIZE 1024
#define STATS_PERIOD_MS  5000
#define OTA_VALID_DEADLINE_MS 90000

static const char *TAG = "rd03d";

/* Ai-Thinker multi-target detection mode command. The RD-03D powers up in
 * multi-target mode; sending this makes the mode explicit and removes the
 * sketch's need to send it (spec: firmware owns radar config). */
static const uint8_t RD03D_CMD_MULTI_TARGET[] = {
    0xFD, 0xFC, 0xFB, 0xFA, 0x02, 0x00, 0x90, 0x00, 0x04, 0x03, 0x02, 0x01,
};

static void print_frame(const rd03d_frame_t *f)
{
    char line[128];
    size_t off = 0;

    line[0] = '\0';
    for (int i = 0; i < RD03D_NUM_TARGETS; i++) {
        const rd03d_target_t *t = &f->targets[i];
        const char *sep = (i < RD03D_NUM_TARGETS - 1) ? " | " : "";
        int n;
        if (t->present) {
            n = snprintf(line + off, sizeof(line) - off,
                         "T%d: x=%dmm y=%dmm v=%dcm/s%s",
                         i + 1, t->x_mm, t->y_mm, t->speed_cms, sep);
        } else {
            n = snprintf(line + off, sizeof(line) - off, "T%d: ---%s",
                         i + 1, sep);
        }
        if (n < 0 || (size_t)n >= sizeof(line) - off) {
            break;
        }
        off += (size_t)n;
    }
    printf("%s\n", line);
}

/* A freshly-OTA'd image boots pending-verify. Mark it valid only once the
 * device is provably updatable again (WiFi up + web server running); if that
 * never happens, restart while still pending so the bootloader rolls back
 * to the previous firmware. USB-flashed images are never pending: no-op. */
static void ota_validation_task(void *arg)
{
    (void)arg;
    const esp_partition_t *running = esp_ota_get_running_partition();
    esp_ota_img_states_t state;
    if (esp_ota_get_state_partition(running, &state) != ESP_OK ||
        state != ESP_OTA_IMG_PENDING_VERIFY) {
        vTaskDelete(NULL);
        return;
    }
    TickType_t deadline =
        xTaskGetTickCount() + pdMS_TO_TICKS(OTA_VALID_DEADLINE_MS);
    while ((int32_t)(deadline - xTaskGetTickCount()) > 0) {
        if (wifi_link_is_up() && web_server_handle() != NULL) {
            ESP_ERROR_CHECK(esp_ota_mark_app_valid_cancel_rollback());
            ESP_LOGI(TAG, "firmware validated (WiFi + web server up)");
            vTaskDelete(NULL);
            return;
        }
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
    if (wifi_link_is_up() && web_server_handle() != NULL) {
        ESP_ERROR_CHECK(esp_ota_mark_app_valid_cancel_rollback());
        ESP_LOGI(TAG, "firmware validated (WiFi + web server up)");
        vTaskDelete(NULL);
        return;
    }
    ESP_LOGE(TAG, "validation deadline missed - restarting to roll back");
    esp_restart();
}

void app_main(void)
{
    const uart_config_t cfg = {
        .baud_rate = RADAR_BAUD,
        .data_bits = UART_DATA_8_BITS,
        .parity = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_DEFAULT,
    };
    ESP_ERROR_CHECK(uart_driver_install(RADAR_UART_NUM, UART_RX_BUF_SIZE,
                                        0, 0, NULL, 0));
    ESP_ERROR_CHECK(uart_param_config(RADAR_UART_NUM, &cfg));
    ESP_ERROR_CHECK(uart_set_pin(RADAR_UART_NUM, RADAR_PIN_TX, RADAR_PIN_RX,
                                 UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE));

    ESP_LOGI(TAG, "RD-03D reader: UART%d RX=GPIO%d TX=GPIO%d @ %d baud",
             RADAR_UART_NUM, RADAR_PIN_RX, RADAR_PIN_TX, RADAR_BAUD);

    int written = uart_write_bytes(RADAR_UART_NUM, RD03D_CMD_MULTI_TARGET,
                                   sizeof(RD03D_CMD_MULTI_TARGET));
    if (written != (int)sizeof(RD03D_CMD_MULTI_TARGET)) {
        ESP_LOGW(TAG, "multi-target command short write (%d)", written);
    }
    vTaskDelay(pdMS_TO_TICKS(200));
    /* Discard the radar's command ACK so it doesn't hit the frame parser. */
    ESP_ERROR_CHECK(uart_flush_input(RADAR_UART_NUM));
    ESP_LOGI(TAG, "multi-target mode command sent");

    wifi_link_start();
    web_server_start();
    ota_update_register(web_server_handle());
    xTaskCreate(ota_validation_task, "ota_valid", 3072, NULL, 5, NULL);
#if CONFIG_RD03D_ENABLE_MQTT
    mqtt_pub_start();
#endif

    rd03d_parser_t parser;
    rd03d_parser_init(&parser);
    rd03d_frame_t frame;
    uint8_t buf[128];
    TickType_t last_stats = xTaskGetTickCount();

    for (;;) {
        int n = uart_read_bytes(RADAR_UART_NUM, buf, sizeof(buf),
                                pdMS_TO_TICKS(100));
        for (int i = 0; i < n; i++) {
            if (rd03d_parser_feed(&parser, buf[i], &frame)) {
                print_frame(&frame);
                web_server_send_frame(&frame, parser.dropped_bytes,
                                      parser.bad_frames);
#if CONFIG_RD03D_ENABLE_MQTT
                mqtt_pub_frame(&frame);
#endif
            }
        }
        if (xTaskGetTickCount() - last_stats >= pdMS_TO_TICKS(STATS_PERIOD_MS)) {
            ESP_LOGI(TAG, "link stats: dropped=%" PRIu32 " bad_frames=%" PRIu32,
                     parser.dropped_bytes, parser.bad_frames);
            last_stats = xTaskGetTickCount();
        }
    }
}
