#include "clock_ms.h"

#include <sys/time.h>
#include "esp_log.h"
#include "esp_netif_sntp.h"
#include "sdkconfig.h"

static const char *TAG = "clock";

void clock_start(void)
{
#if CONFIG_RD03D_NET_MODE_STA
    esp_sntp_config_t cfg = ESP_NETIF_SNTP_DEFAULT_CONFIG("pool.ntp.org");
    cfg.wait_for_sync = false;     /* nothing waits on the sync semaphore */
    /* Started here, before WiFi is up. lwIP sends its first request after the
     * interface has an address, with a short random startup delay and
     * exponential retry, so the first sync lands some seconds after the IP. */
    esp_err_t err = esp_netif_sntp_init(&cfg);
    if (err != ESP_OK) {
        /* A missing clock must not take the radar node down. */
        ESP_LOGW(TAG, "sntp init failed (%s); timestamps stay 0",
                 esp_err_to_name(err));
        return;
    }
    ESP_LOGI(TAG, "sntp started (pool.ntp.org)");
#else
    ESP_LOGI(TAG, "AP mode: no SNTP, timestamps stay 0");
#endif
}

int64_t clock_epoch_ms(void)
{
    struct timeval tv;
    if (gettimeofday(&tv, NULL) != 0) {
        return 0;
    }
    /* Before the first sync the RTC reads 1970; report 0 so a consumer can
     * tell "unsynced" from "very early". 1e9 s is 2001-09-09. */
    if (tv.tv_sec < 1000000000) {
        return 0;
    }
    return (int64_t)tv.tv_sec * 1000 + tv.tv_usec / 1000;
}
