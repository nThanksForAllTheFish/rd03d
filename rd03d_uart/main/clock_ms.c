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
    cfg.start = true;              /* sends its first request as soon as the
                                      interface has an IP; retries on its own */
    ESP_ERROR_CHECK(esp_netif_sntp_init(&cfg));
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
