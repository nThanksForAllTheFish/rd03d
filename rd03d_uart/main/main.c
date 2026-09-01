#include <inttypes.h>
#include <stdio.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/uart.h"
#include "esp_log.h"

#include "rd03d.h"

/* XIAO ESP32-C6, ESP side: D6 = GPIO16 (UART1 TX), D7 = GPIO17 (UART1 RX). */
#define RADAR_UART_NUM   UART_NUM_1
#define RADAR_PIN_TX     16
#define RADAR_PIN_RX     17
#define RADAR_BAUD       256000
#define UART_RX_BUF_SIZE 1024
#define STATS_PERIOD_MS  5000

static const char *TAG = "rd03d";

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
            }
        }
        if (xTaskGetTickCount() - last_stats >= pdMS_TO_TICKS(STATS_PERIOD_MS)) {
            ESP_LOGI(TAG, "link stats: dropped=%" PRIu32 " bad_frames=%" PRIu32,
                     parser.dropped_bytes, parser.bad_frames);
            last_stats = xTaskGetTickCount();
        }
    }
}
