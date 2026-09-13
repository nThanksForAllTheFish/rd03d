#include "wifi_link.h"

#include <string.h>

#include "esp_event.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_wifi.h"
#include "mdns.h"
#include "nvs_flash.h"
#include "sdkconfig.h"

static const char *TAG = "wifi_link";
static volatile bool s_up;

/* strlcpy silently truncates; catch oversize credentials at compile time.
 * (sizeof includes the NUL; the driver fields are 32 and 64 bytes.)
 * The two modes see different Kconfig symbols - `depends on` leaves the
 * unselected mode's symbols UNDEFINED, not empty - so each set of asserts
 * lives inside its own branch. */
#if CONFIG_RD03D_NET_MODE_AP
_Static_assert(sizeof(CONFIG_RD03D_AP_SSID) <= 32,
               "SoftAP SSID longer than 31 chars would be truncated");
_Static_assert(sizeof(CONFIG_RD03D_AP_PASSWORD) <= 64,
               "SoftAP password longer than 63 chars would be truncated");
/* WPA2's minimum is 8 characters. Below that esp_wifi_set_config fails at
 * runtime with an opaque error, on a device with no console attached. */
_Static_assert(sizeof(CONFIG_RD03D_AP_PASSWORD) >= 9,
               "SoftAP password must be at least 8 characters (WPA2 minimum)");
#else
_Static_assert(sizeof(CONFIG_RD03D_WIFI_SSID) <= 32,
               "WiFi SSID longer than 31 chars would be truncated");
_Static_assert(sizeof(CONFIG_RD03D_WIFI_PASSWORD) <= 64,
               "WiFi password longer than 63 chars would be truncated");
#endif

static void on_wifi_event(void *arg, esp_event_base_t base, int32_t id,
                          void *data)
{
    (void)arg;
#if CONFIG_RD03D_NET_MODE_AP
    if (base == WIFI_EVENT && id == WIFI_EVENT_AP_START) {
        /* No IP_EVENT_STA_GOT_IP ever fires in AP mode. The device is
         * reachable the moment the AP starts, and main.c's OTA validation
         * keys off wifi_link_is_up() - so without this line every OTA'd
         * image would sit unvalidated and roll back after 90 s. */
        s_up = true;
        ESP_LOGI(TAG, "softap up, ssid=%s channel=%d, http://192.168.4.1",
                 CONFIG_RD03D_AP_SSID, CONFIG_RD03D_AP_CHANNEL);
    } else if (base == WIFI_EVENT && id == WIFI_EVENT_AP_STOP) {
        s_up = false;
        ESP_LOGW(TAG, "softap stopped");
    } else if (base == WIFI_EVENT && id == WIFI_EVENT_AP_STACONNECTED) {
        ESP_LOGI(TAG, "client joined (aid=%d)",
                 ((wifi_event_ap_staconnected_t *)data)->aid);
    } else if (base == WIFI_EVENT && id == WIFI_EVENT_AP_STADISCONNECTED) {
        ESP_LOGI(TAG, "client left (aid=%d)",
                 ((wifi_event_ap_stadisconnected_t *)data)->aid);
    }
#else
    if (base == WIFI_EVENT && id == WIFI_EVENT_STA_START) {
        esp_wifi_connect();
    } else if (base == WIFI_EVENT && id == WIFI_EVENT_STA_DISCONNECTED) {
        s_up = false;
        ESP_LOGW(TAG, "disconnected, retrying");
        esp_wifi_connect();
    } else if (base == IP_EVENT && id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t *e = (ip_event_got_ip_t *)data;
        s_up = true;
        ESP_LOGI(TAG, "got ip " IPSTR, IP2STR(&e->ip_info.ip));
    }
#endif
}

void wifi_link_start(void)
{
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        err = nvs_flash_init();
    }
    ESP_ERROR_CHECK(err);

    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());

#if CONFIG_RD03D_NET_MODE_AP
    esp_netif_create_default_wifi_ap();

    if (CONFIG_RD03D_AP_PASSWORD[0] == '\0') {
        ESP_LOGE(TAG, "SoftAP password not set - see RD03D_AP_PASSWORD");
        return;
    }

    wifi_init_config_t init_cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&init_cfg));
    ESP_ERROR_CHECK(esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID,
                                               on_wifi_event, NULL));

    wifi_config_t ap_cfg = { 0 };
    strlcpy((char *)ap_cfg.ap.ssid, CONFIG_RD03D_AP_SSID,
            sizeof(ap_cfg.ap.ssid));
    ap_cfg.ap.ssid_len = strlen(CONFIG_RD03D_AP_SSID);
    strlcpy((char *)ap_cfg.ap.password, CONFIG_RD03D_AP_PASSWORD,
            sizeof(ap_cfg.ap.password));
    ap_cfg.ap.channel = CONFIG_RD03D_AP_CHANNEL;
    ap_cfg.ap.authmode = WIFI_AUTH_WPA2_PSK;
    ap_cfg.ap.max_connection = 4;
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_AP));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_AP, &ap_cfg));
    ESP_ERROR_CHECK(esp_wifi_start());

    ESP_LOGI(TAG, "softap starting, ssid=%s", CONFIG_RD03D_AP_SSID);
#else
    esp_netif_create_default_wifi_sta();

    if (CONFIG_RD03D_WIFI_SSID[0] == '\0' || CONFIG_RD03D_WIFI_PASSWORD[0] == '\0') {
        ESP_LOGE(TAG, "WiFi credentials not set - run idf.py menuconfig "
                      "(RD03D Configuration)");
        return;
    }

    wifi_init_config_t init_cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&init_cfg));

    ESP_ERROR_CHECK(esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID,
                                               on_wifi_event, NULL));
    ESP_ERROR_CHECK(esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP,
                                               on_wifi_event, NULL));

    wifi_config_t sta_cfg = { 0 };
    strlcpy((char *)sta_cfg.sta.ssid, CONFIG_RD03D_WIFI_SSID,
            sizeof(sta_cfg.sta.ssid));
    strlcpy((char *)sta_cfg.sta.password, CONFIG_RD03D_WIFI_PASSWORD,
            sizeof(sta_cfg.sta.password));
    /* Refuse to associate with an open AP spoofing our SSID. */
    sta_cfg.sta.threshold.authmode = WIFI_AUTH_WPA2_PSK;
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &sta_cfg));
    ESP_ERROR_CHECK(esp_wifi_start());

    ESP_LOGI(TAG, "wifi starting, ssid=%s", CONFIG_RD03D_WIFI_SSID);
#endif

    ESP_ERROR_CHECK(mdns_init());
    ESP_ERROR_CHECK(mdns_hostname_set("rd03d"));
    ESP_ERROR_CHECK(mdns_instance_name_set("RD-03D radar stream"));
    ESP_ERROR_CHECK(mdns_service_add(NULL, "_http", "_tcp", 80, NULL, 0));

    ESP_LOGI(TAG, "mdns hostname set: rd03d.local");
}

bool wifi_link_is_up(void)
{
    return s_up;
}
