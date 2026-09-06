#include "ota_update.h"

#include <stdio.h>
#include <string.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_app_desc.h"
#include "esp_log.h"
#include "esp_ota_ops.h"
#include "esp_system.h"

static const char *TAG = "ota_update";

static bool s_upload_in_progress;

static const char UPDATE_PAGE_FMT[] =
"<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
"<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
"<title>rd03d update</title></head>"
"<body style=\"font-family:system-ui;background:#121212;color:#ddd;padding:24px\">"
"<h2>rd03d firmware update</h2>"
"<p>Running: %s (slot %s)</p>"
"<input type=\"file\" id=\"f\" accept=\".bin\"> "
"<button onclick=\"up()\">Upload</button>"
"<p id=\"s\"></p><a href=\"/\" style=\"color:#00b4ff\">back to chart</a>"
"<script>async function up(){const f=document.getElementById('f').files[0];"
"const s=document.getElementById('s');if(!f){s.textContent='pick a .bin first';return;}"
"s.textContent='uploading '+f.name+' ('+f.size+' bytes)...';"
"try{const r=await fetch('/update',{method:'POST',body:f});"
"s.textContent=await r.text();}catch(e){s.textContent='upload failed: '+e;}}"
"</script></body></html>";

static esp_err_t update_get(httpd_req_t *req)
{
    const esp_app_desc_t *app = esp_app_get_description();
    const esp_partition_t *running = esp_ota_get_running_partition();
    char page[sizeof(UPDATE_PAGE_FMT) + 96];
    int n = snprintf(page, sizeof(page), UPDATE_PAGE_FMT,
                     app->version, running ? running->label : "?");
    if (n < 0 || n >= (int)sizeof(page)) {
        return httpd_resp_send_500(req);
    }
    httpd_resp_set_type(req, "text/html");
    return httpd_resp_send(req, page, n);
}

static void restart_task(void *arg)
{
    (void)arg;
    vTaskDelay(pdMS_TO_TICKS(1000)); /* let the HTTP response flush */
    esp_restart();
}

static esp_err_t update_post(httpd_req_t *req)
{
    if (s_upload_in_progress) {
        httpd_resp_set_status(req, "409 Conflict");
        httpd_resp_sendstr(req, "another upload is in progress\n");
        return ESP_OK;
    }
    s_upload_in_progress = true;

    const esp_partition_t *target = esp_ota_get_next_update_partition(NULL);
    esp_ota_handle_t ota = 0;
    esp_err_t err = (target == NULL) ? ESP_ERR_NOT_FOUND : ESP_OK;

    if (err == ESP_OK &&
        (req->content_len == 0 || req->content_len > target->size)) {
        err = ESP_ERR_INVALID_SIZE;
    }
    if (err == ESP_OK) {
        ESP_LOGI(TAG, "OTA start: %u bytes -> %s",
                 (unsigned)req->content_len, target->label);
        err = esp_ota_begin(target, req->content_len, &ota);
    }

    /* Single-flight upload (guarded above), so a static buffer is safe and
     * keeps the httpd task's small stack out of trouble. */
    static char buf[4096];
    size_t remaining = (err == ESP_OK) ? req->content_len : 0;
    while (err == ESP_OK && remaining > 0) {
        int n = httpd_req_recv(req, buf,
                               remaining < sizeof(buf) ? remaining
                                                       : sizeof(buf));
        if (n <= 0) {
            err = ESP_FAIL; /* client gone or receive timeout */
            break;
        }
        err = esp_ota_write(ota, buf, (size_t)n);
        remaining -= (size_t)n;
    }

    if (err == ESP_OK) {
        err = esp_ota_end(ota); /* verifies image magic + hash */
        ota = 0;
    } else if (ota != 0) {
        esp_ota_abort(ota);
        ota = 0;
    }
    if (err == ESP_OK) {
        err = esp_ota_set_boot_partition(target);
    }

    if (err != ESP_OK) {
        s_upload_in_progress = false;
        ESP_LOGW(TAG, "OTA failed: %s", esp_err_to_name(err));
        char msg[96];
        snprintf(msg, sizeof(msg), "update failed: %s\n",
                 esp_err_to_name(err));
        httpd_resp_set_status(req, "400 Bad Request");
        httpd_resp_sendstr(req, msg);
        return ESP_OK;
    }

    /* Leave s_upload_in_progress latched: we are rebooting, and any POST
     * that lands in the restart window must get the 409, not a fresh
     * esp_ota_begin racing esp_restart. */
    ESP_LOGI(TAG, "OTA ok, rebooting into %s", target->label);
    httpd_resp_sendstr(req, "update ok, rebooting\n");
    xTaskCreate(restart_task, "ota_restart", 2048, NULL, 5, NULL);
    return ESP_OK;
}

void ota_update_register(httpd_handle_t server)
{
    if (server == NULL) {
        ESP_LOGE(TAG, "no http server; OTA unavailable");
        return;
    }
    static const httpd_uri_t get_uri = {
        .uri = "/update",
        .method = HTTP_GET,
        .handler = update_get,
    };
    static const httpd_uri_t post_uri = {
        .uri = "/update",
        .method = HTTP_POST,
        .handler = update_post,
    };
    ESP_ERROR_CHECK(httpd_register_uri_handler(server, &get_uri));
    ESP_ERROR_CHECK(httpd_register_uri_handler(server, &post_uri));
    ESP_LOGI(TAG, "OTA endpoint ready at /update");
}
