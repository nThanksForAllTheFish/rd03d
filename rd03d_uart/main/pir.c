#include "pir.h"

#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include "driver/gpio.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "sdkconfig.h"
#include "clock_ms.h"
#include "pir_gate.h"

static const char *TAG = "pir";

typedef enum { MSG_EDGE, MSG_HOLD_EXPIRED } pir_msg_t;

static QueueHandle_t s_queue;
static esp_timer_handle_t s_expiry;
static pir_gate_t s_gate;
static volatile bool s_active;
static pir_event_cb_t s_on_event;
static pir_state_cb_t s_on_state;

static int64_t now_ms(void)
{
    return esp_timer_get_time() / 1000;   /* monotonic since boot */
}

static void IRAM_ATTR pir_isr(void *arg)
{
    (void)arg;
    pir_msg_t m = MSG_EDGE;
    BaseType_t woken = pdFALSE;
    xQueueSendFromISR(s_queue, &m, &woken);
    if (woken) {
        portYIELD_FROM_ISR();
    }
}

static void expiry_cb(void *arg)
{
    (void)arg;
    pir_msg_t m = MSG_HOLD_EXPIRED;
    xQueueSend(s_queue, &m, 0);
}

static void arm_expiry(int64_t hold_end_ms)
{
    int64_t delay_us = (hold_end_ms - now_ms()) * 1000;
    if (delay_us < 1000) {
        delay_us = 1000;
    }
    esp_timer_stop(s_expiry);          /* INVALID_STATE when idle: fine */
    esp_timer_start_once(s_expiry, (uint64_t)delay_us);
}

static void pir_task(void *arg)
{
    (void)arg;
    pir_msg_t m;
    for (;;) {
        if (xQueueReceive(s_queue, &m, portMAX_DELAY) != pdTRUE) {
            continue;
        }
        int64_t t = now_ms();
        if (m == MSG_EDGE) {
            pir_gate_action_t act = pir_gate_edge(&s_gate, t);
            arm_expiry(pir_gate_hold_end(&s_gate));
            if (act == PIR_GATE_EVENT) {
                s_active = true;
                pir_event_t ev = {
                    .n = pir_gate_count(&s_gate),
                    .t_ms = clock_epoch_ms(),
                };
                ESP_LOGI(TAG, "event %lu", (unsigned long)ev.n);
                if (s_on_state) {
                    s_on_state(true);
                }
                if (s_on_event) {
                    s_on_event(&ev);
                }
            }
        } else { /* MSG_HOLD_EXPIRED */
            if (!pir_gate_active(&s_gate, t)) {
                if (s_active) {
                    s_active = false;
                    if (s_on_state) {
                        s_on_state(false);
                    }
                }
            } else {
                arm_expiry(pir_gate_hold_end(&s_gate)); /* extended meanwhile */
            }
        }
    }
}

void pir_init(pir_event_cb_t on_event, pir_state_cb_t on_state)
{
    s_on_event = on_event;
    s_on_state = on_state;
    pir_gate_init(&s_gate, CONFIG_RD03D_PIR_HOLD_MS);

    s_queue = xQueueCreate(8, sizeof(pir_msg_t));
    const esp_timer_create_args_t targs = {
        .callback = expiry_cb,
        .name = "pir_hold",
    };
    ESP_ERROR_CHECK(esp_timer_create(&targs, &s_expiry));

    gpio_config_t cfg = {
        .pin_bit_mask = 1ULL << CONFIG_RD03D_PIR_GPIO,
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_ENABLE,  /* sensor output floats when idle */
        .intr_type = GPIO_INTR_POSEDGE,
    };
    ESP_ERROR_CHECK(gpio_config(&cfg));
    /* Shared ISR service; ESP_ERR_INVALID_STATE means another module already
     * installed it, which is fine. */
    esp_err_t err = gpio_install_isr_service(0);
    if (err != ESP_OK && err != ESP_ERR_INVALID_STATE) {
        ESP_ERROR_CHECK(err);
    }
    ESP_ERROR_CHECK(gpio_isr_handler_add(CONFIG_RD03D_PIR_GPIO, pir_isr, NULL));

    xTaskCreate(pir_task, "pir", 3072, NULL, 6, NULL);
    ESP_LOGI(TAG, "PIR on GPIO%d, hold %d ms", CONFIG_RD03D_PIR_GPIO,
             CONFIG_RD03D_PIR_HOLD_MS);
}

bool pir_active(void)
{
    return s_active;
}
