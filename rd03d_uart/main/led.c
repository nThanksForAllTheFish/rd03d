#include "led.h"

#include "driver/gpio.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "sdkconfig.h"

#if CONFIG_RD03D_LED_GPIO >= 0

static const char *TAG = "led";
static esp_timer_handle_t s_off_timer;

/* The XIAO ESP32-C6's user LED is wired to 3V3, so the GPIO sinks it: a LOW
 * level lights it. Kconfig exposes the polarity because this is board wiring,
 * not a property of the chip. */
#if CONFIG_RD03D_LED_ACTIVE_LOW
#define LED_ON_LEVEL  0
#define LED_OFF_LEVEL 1
#else
#define LED_ON_LEVEL  1
#define LED_OFF_LEVEL 0
#endif

static void led_off_cb(void *arg)
{
    (void)arg;
    gpio_set_level(CONFIG_RD03D_LED_GPIO, LED_OFF_LEVEL);
}

void led_init(void)
{
    gpio_config_t cfg = {
        .pin_bit_mask = 1ULL << CONFIG_RD03D_LED_GPIO,
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    ESP_ERROR_CHECK(gpio_config(&cfg));
    gpio_set_level(CONFIG_RD03D_LED_GPIO, LED_OFF_LEVEL);

    const esp_timer_create_args_t targs = {
        .callback = led_off_cb,
        .name = "led_off",
    };
    ESP_ERROR_CHECK(esp_timer_create(&targs, &s_off_timer));

    ESP_LOGI(TAG, "user LED on GPIO%d (%s), %d ms pulse per event",
             CONFIG_RD03D_LED_GPIO,
             LED_ON_LEVEL == 0 ? "active low" : "active high",
             CONFIG_RD03D_LED_MS);
}

void led_pulse(void)
{
    if (s_off_timer == NULL) {
        return;             /* led_init() not called, or it failed */
    }
    gpio_set_level(CONFIG_RD03D_LED_GPIO, LED_ON_LEVEL);
    /* Return values deliberately ignored. stop() on an idle timer reports
     * ESP_ERR_INVALID_STATE, which is the normal case here, and a failed
     * start would leave the LED lit until the next event - a cosmetic fault
     * that must not take a working radar node down with ESP_ERROR_CHECK. */
    esp_timer_stop(s_off_timer);
    esp_timer_start_once(s_off_timer, (uint64_t)CONFIG_RD03D_LED_MS * 1000);
}

#else  /* RD03D_LED_GPIO < 0: no LED on this board */

void led_init(void) { }
void led_pulse(void) { }

#endif
