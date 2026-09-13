# RD-03D SoftAP Variant Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the same firmware tree build either the existing WiFi-station image or a WPA2 SoftAP image with MQTT compiled out, so the prototype node works on a work site that forbids unregistered devices on its network.

**Architecture:** A `RD03D_NET_MODE` Kconfig choice selects station or access-point behaviour inside `wifi_link.c` — the only file whose behaviour changes. Everything downstream (radar parser, chart, WebSocket, OTA) is network-agnostic. The AP image builds from a second sdkconfig and build directory, so both images coexist without a branch.

**Tech Stack:** ESP-IDF v5.5, esp32c6 target, C. `source ~/esp/esp-idf-v5.5/export.sh` before any `idf.py` command.

---

## Read this before Task 1

1. **NEVER delete or regenerate `rd03d_uart/sdkconfig` from scratch.** The user's home WiFi SSID and password exist ONLY in that untracked file. Losing it means the working station node cannot be rebuilt without the user re-entering credentials. Adding Kconfig options does not endanger it; deleting the file does.
2. **Never print the WiFi password** in output, commit messages, or reports. Same for the new SoftAP PSK.
3. **`rd03d_uart/main/rd03d.c` and `rd03d.h` are frozen.** The radar parser is host-tested and must not change.
4. **`depends on` removes symbols entirely.** When `RD03D_NET_MODE_AP` is selected, `CONFIG_RD03D_WIFI_SSID` is *undefined*, not empty — so every reference to it must sit inside `#if CONFIG_RD03D_NET_MODE_STA`. The reverse applies to the AP symbols. A missing guard is a compile error, which is the point.
5. Two build trees, never mixed:
   - station: `idf.py build` → `build/`, `sdkconfig`
   - AP: `idf.py -B build.ap -D SDKCONFIG=sdkconfig.ap build` → `build.ap/`, `sdkconfig.ap`
6. The board is a Seeed XIAO ESP32-C6. **Discover its port, never assume it** — boards enumerate differently, and the assembled node has appeared as `/dev/cu.usbmodem1101` while the prototype appears as `/dev/cu.usbmodem101`. Find it with `ls /dev/cu.* | grep -i usbmodem`. Flash with full `idf.py flash`, never `app-flash` alone — on a board that has taken OTA updates, `app-flash` writes the image but the bootloader keeps booting the old slot unless otadata is erased too.

**Host tests** (unaffected by this work, but run them to prove it):

```bash
cd /path/to/rd03d/rd03d_uart/tests && cc -Wall -Wextra -o test_rd03d test_rd03d.c ../main/rd03d.c && ./test_rd03d && cc -Wall -Wextra -o test_mqtt_throttle test_mqtt_throttle.c ../main/mqtt_throttle.c && ./test_mqtt_throttle
```

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `rd03d_uart/main/Kconfig.projbuild` | Build-time options | Add mode choice, AP options, MQTT toggle; add `depends on` to existing options |
| `rd03d_uart/main/wifi_link.c` | Brings the network up; reports whether it is up | Add AP branch; set the up-flag on `WIFI_EVENT_AP_START` |
| `rd03d_uart/main/wifi_link.h` | That module's interface | Rename `wifi_link_has_ip` → `wifi_link_is_up` |
| `rd03d_uart/main/main.c` | Boot, radar loop, OTA validation | Renamed accessor; `#if` guards around the two MQTT calls |
| `rd03d_uart/main/mqtt_pub.c` | MQTT client | Renamed accessor (one call site) |
| `rd03d_uart/main/CMakeLists.txt` | Component sources | Drop MQTT sources when the option is off |
| `.gitignore` (repo root) | Keeps credentials out of git | Add `rd03d_uart/sdkconfig.ap` |
| `rd03d_uart/README.md` | How to build, flash, use | Document both variants |

`rd03d.c`, `web_server.c`, `ota_update.c`, `mqtt_throttle.c` and `index.html` are untouched.

---

### Task 1: Rename `wifi_link_has_ip` to `wifi_link_is_up`

A pure rename, done first and alone so it cannot be confused with behaviour changes later. The old name is what hides the AP-mode rollback bug: in AP mode there is no IP, but the network is up.

**Files:**
- Modify: `rd03d_uart/main/wifi_link.h:11`, `wifi_link.c:87`, `main.c:77`, `main.c:85`, `mqtt_pub.c:80`

- [ ] **Step 1: Confirm the call sites**

```bash
cd /path/to/rd03d/rd03d_uart && grep -rn "wifi_link_has_ip" main/
```

Expected: exactly 5 hits — the declaration, the definition, two in `main.c`, one in `mqtt_pub.c`. If the count differs, stop and report; the plan was written against 5.

- [ ] **Step 2: Rename everywhere**

```bash
cd /path/to/rd03d/rd03d_uart && sed -i '' 's/wifi_link_has_ip/wifi_link_is_up/g' main/wifi_link.h main/wifi_link.c main/main.c main/mqtt_pub.c && grep -rn "wifi_link_has_ip\|wifi_link_is_up" main/
```

Expected: 5 hits, all now `wifi_link_is_up`, and zero `wifi_link_has_ip`.

- [ ] **Step 3: Update the header comment**

In `rd03d_uart/main/wifi_link.h`, replace:

```c
/* True while the station holds an IP address. */
bool wifi_link_is_up(void);
```

with:

```c
/* True while the device is reachable over WiFi: in station mode, once it holds
 * an IP; in SoftAP mode, once the AP has started. Deliberately NOT "has IP" -
 * no IP event ever fires in AP mode, and main.c's OTA validation keys off this
 * function, so a station-only definition would roll back every OTA'd AP image. */
bool wifi_link_is_up(void);
```

Also rename the static in `wifi_link.c` from `s_has_ip` to `s_up`:

```bash
cd /path/to/rd03d/rd03d_uart && sed -i '' 's/s_has_ip/s_up/g' main/wifi_link.c
```

- [ ] **Step 4: Build and prove nothing changed behaviourally**

```bash
cd /path/to/rd03d/rd03d_uart && source ~/esp/esp-idf-v5.5/export.sh >/dev/null 2>&1 && idf.py build 2>&1 | tail -12
```

Expected: `Project build complete.` No warnings about implicit declarations.

- [ ] **Step 5: Run the host tests**

```bash
cd /path/to/rd03d/rd03d_uart/tests && cc -Wall -Wextra -o test_rd03d test_rd03d.c ../main/rd03d.c && ./test_rd03d && cc -Wall -Wextra -o test_mqtt_throttle test_mqtt_throttle.c ../main/mqtt_throttle.c && ./test_mqtt_throttle
```

Expected: both report all tests passing.

- [ ] **Step 6: Commit**

```bash
cd /path/to/rd03d && git add rd03d_uart/main && git commit -m "refactor(rd03d_uart): wifi_link_has_ip -> wifi_link_is_up

Pure rename ahead of the SoftAP variant. In AP mode no IP event ever fires,
so a function named has_ip would return false forever while the network is
perfectly up - and main.c gates the OTA rollback-cancel on it, which would
roll back every OTA'd AP image. The name is what hides that.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2: Kconfig options

**Files:**
- Modify: `rd03d_uart/main/Kconfig.projbuild`

- [ ] **Step 1: Replace the file**

Write `rd03d_uart/main/Kconfig.projbuild` with exactly this:

```
menu "RD03D Configuration"

choice RD03D_NET_MODE
    prompt "Network mode"
    default RD03D_NET_MODE_STA
    help
        STA joins an existing 2.4 GHz network - the normal deployment.
        AP makes the device its own WPA2 access point so a laptop can connect
        to it directly, for sites where it may not join the local network.

config RD03D_NET_MODE_STA
    bool "Station (join an existing network)"

config RD03D_NET_MODE_AP
    bool "Access point (SoftAP)"

endchoice

config RD03D_WIFI_SSID
    string "WiFi SSID"
    depends on RD03D_NET_MODE_STA
    default ""
    help
        SSID of the 2.4 GHz network the radar streamer joins.

config RD03D_WIFI_PASSWORD
    string "WiFi password"
    depends on RD03D_NET_MODE_STA
    default ""
    help
        WPA2 password for the network. Stored only in the untracked sdkconfig.

config RD03D_AP_SSID
    string "SoftAP SSID"
    depends on RD03D_NET_MODE_AP
    default "rd03d-radar"
    help
        Network name the device broadcasts in AP mode.

config RD03D_AP_PASSWORD
    string "SoftAP WPA2 password"
    depends on RD03D_NET_MODE_AP
    default ""
    help
        At least 8 characters - WPA2's minimum, enforced at compile time.
        Stored only in the untracked sdkconfig.ap.

config RD03D_AP_CHANNEL
    int "SoftAP 2.4 GHz channel"
    depends on RD03D_NET_MODE_AP
    default 6
    range 1 13
    help
        1 and 11 are usually the most congested in offices. Change this if
        the link feels slow; it is the knob to turn first.

config RD03D_ENABLE_MQTT
    bool "Publish targets over MQTT"
    default y
    help
        Off for standalone/AP use, where there is no broker. When off the MQTT
        sources are not compiled and esp-mqtt is not linked.

config RD03D_MQTT_HOST
    string "MQTT broker host"
    depends on RD03D_ENABLE_MQTT
    default "iotstack.local"
    help
        Broker hostname. A .local name is resolved via mDNS by the firmware.

config RD03D_MQTT_PORT
    int "MQTT broker port"
    depends on RD03D_ENABLE_MQTT
    default 1883
    range 1 65535

config RD03D_MQTT_MOVE_MM
    int "Minimum movement (mm) between MQTT publishes per target"
    depends on RD03D_ENABLE_MQTT
    default 200
    range 0 30000

endmenu
```

- [ ] **Step 2: Reconfigure the station build and confirm credentials survived**

```bash
cd /path/to/rd03d/rd03d_uart && source ~/esp/esp-idf-v5.5/export.sh >/dev/null 2>&1 && idf.py reconfigure >/dev/null 2>&1; grep -c "^CONFIG_RD03D_WIFI_SSID=\"..*\"" sdkconfig; grep "^CONFIG_RD03D_NET_MODE_STA\|^CONFIG_RD03D_ENABLE_MQTT" sdkconfig
```

Expected: `1` (the SSID is still set and non-empty — do NOT print the value), then `CONFIG_RD03D_NET_MODE_STA=y` and `CONFIG_RD03D_ENABLE_MQTT=y`.

If the SSID count is `0`, stop immediately and report — the credentials were lost and the user must re-enter them.

- [ ] **Step 3: Build**

```bash
cd /path/to/rd03d/rd03d_uart && source ~/esp/esp-idf-v5.5/export.sh >/dev/null 2>&1 && idf.py build 2>&1 | tail -8
```

Expected: `Project build complete.` — the station path is unchanged because STA is the default choice.

- [ ] **Step 4: Commit**

```bash
cd /path/to/rd03d && git add rd03d_uart/main/Kconfig.projbuild && git commit -m "feat(rd03d_uart): Kconfig for network mode, SoftAP and MQTT toggle

RD03D_NET_MODE chooses station or SoftAP; the AP gets SSID, WPA2 password
and channel (default 6 - 1 and 11 are the congested ones in offices).
RD03D_ENABLE_MQTT defaults on and gates the broker options.

Existing station credentials gain depends-on so an AP build never prompts
for them. STA remains the default, so the working node is unaffected.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 3: Second build configuration

Creates `sdkconfig.ap` and keeps it out of git. Done before the code change so Task 4 has something to build against.

**Files:**
- Create: `rd03d_uart/sdkconfig.ap` (untracked)
- Modify: `.gitignore` (repo root)

- [ ] **Step 1: Ignore the new config first**

Do this *before* creating the file, so it can never be staged by accident. In the repo root `.gitignore`, after the line `rd03d_uart/sdkconfig.old` (line 23), add:

```
rd03d_uart/sdkconfig.ap
rd03d_uart/sdkconfig.ap.old
```

Verify:

```bash
cd /path/to/rd03d && printf 'x' > rd03d_uart/sdkconfig.ap && git status --short rd03d_uart/ && git check-ignore -v rd03d_uart/sdkconfig.ap
```

Expected: `git status` shows nothing for that path, and `check-ignore` prints the matching rule.

- [ ] **Step 2: Generate the AP config from defaults**

```bash
cd /path/to/rd03d/rd03d_uart && rm -f sdkconfig.ap && source ~/esp/esp-idf-v5.5/export.sh >/dev/null 2>&1 && idf.py -B build.ap -D SDKCONFIG=sdkconfig.ap reconfigure 2>&1 | tail -5
```

Expected: configuration succeeds and `sdkconfig.ap` now exists. It currently holds STA defaults; the next step switches it.

- [ ] **Step 3: Switch it to AP mode with a generated PSK**

The PSK is the user's AP password. Generate one rather than inventing a weak default, write it only to the gitignored file, and show it once so the user can type it into their laptop.

```bash
cd /path/to/rd03d/rd03d_uart && PSK=$(LC_ALL=C tr -dc 'a-z2-9' < /dev/urandom | head -c 12) && python3 - "$PSK" <<'PY'
import io, re, sys
psk = sys.argv[1]
p = "sdkconfig.ap"
s = io.open(p, encoding="utf-8").read()
# sdkconfig's canonical "off" form is the "is not set" comment, not "=n" or
# an empty value - kconfiglib writes it that way and reconfigure will fight
# anything else.
s = re.sub(r'^CONFIG_RD03D_NET_MODE_STA=y$',
           '# CONFIG_RD03D_NET_MODE_STA is not set', s, flags=re.M)
s = re.sub(r'^# CONFIG_RD03D_NET_MODE_AP is not set$',
           'CONFIG_RD03D_NET_MODE_AP=y', s, flags=re.M)
s = re.sub(r'^CONFIG_RD03D_ENABLE_MQTT=y$',
           '# CONFIG_RD03D_ENABLE_MQTT is not set', s, flags=re.M)
s += ('\nCONFIG_RD03D_AP_SSID="rd03d-radar"\n'
      'CONFIG_RD03D_AP_PASSWORD="%s"\n'
      'CONFIG_RD03D_AP_CHANNEL=6\n' % psk)
io.open(p, "w", encoding="utf-8").write(s)
print("sdkconfig.ap switched to AP mode")
PY
echo "AP SSID: rd03d-radar"; echo "AP password: $PSK"
```

Record the SSID and password for the user in your report. **Do not commit them anywhere** — `sdkconfig.ap` is gitignored precisely so they stay local.

- [ ] **Step 4: Confirm the AP config took**

```bash
cd /path/to/rd03d/rd03d_uart && source ~/esp/esp-idf-v5.5/export.sh >/dev/null 2>&1 && idf.py -B build.ap -D SDKCONFIG=sdkconfig.ap reconfigure >/dev/null 2>&1; grep "^CONFIG_RD03D_NET_MODE_AP\|^CONFIG_RD03D_ENABLE_MQTT\|^CONFIG_RD03D_AP_CHANNEL\|^CONFIG_RD03D_AP_SSID" sdkconfig.ap
```

Expected exactly:

```
CONFIG_RD03D_NET_MODE_AP=y
CONFIG_RD03D_AP_SSID="rd03d-radar"
CONFIG_RD03D_AP_CHANNEL=6
```

and `CONFIG_RD03D_ENABLE_MQTT` must NOT appear as `=y`. Confirm it is off:

```bash
cd /path/to/rd03d/rd03d_uart && grep -c "^CONFIG_RD03D_ENABLE_MQTT=y" sdkconfig.ap
```

Expected: `0`.

Also confirm the station config was not disturbed:

```bash
cd /path/to/rd03d/rd03d_uart && grep -c "^CONFIG_RD03D_WIFI_SSID=\"..*\"" sdkconfig && grep "^CONFIG_RD03D_NET_MODE_STA" sdkconfig
```

Expected: `1`, then `CONFIG_RD03D_NET_MODE_STA=y`.

- [ ] **Step 5: Commit the ignore rule only**

```bash
cd /path/to/rd03d && git add .gitignore && git commit -m "chore: gitignore rd03d_uart/sdkconfig.ap

The SoftAP build's own config carries the AP's WPA2 password, so it stays
untracked alongside sdkconfig, which carries the home network credentials.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 4: SoftAP branch in `wifi_link.c`

**Files:**
- Modify: `rd03d_uart/main/wifi_link.c`

- [ ] **Step 1: Write the file**

Replace `rd03d_uart/main/wifi_link.c` with exactly this:

```c
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
```

- [ ] **Step 2: Prove the WPA2 length assert actually fires**

This is the test. Temporarily set a 5-character PSK and confirm the build refuses it:

```bash
cd /path/to/rd03d/rd03d_uart && cp sdkconfig.ap /tmp/sdkconfig.ap.bak && sed -i '' 's/^CONFIG_RD03D_AP_PASSWORD=".*"$/CONFIG_RD03D_AP_PASSWORD="short"/' sdkconfig.ap && source ~/esp/esp-idf-v5.5/export.sh >/dev/null 2>&1 && idf.py -B build.ap -D SDKCONFIG=sdkconfig.ap build 2>&1 | grep -i "static_assert\|at least 8 characters" | head -3
```

Expected: a compile error quoting `SoftAP password must be at least 8 characters (WPA2 minimum)`. If the build *succeeds*, the assert is wrong — stop and report, because a silent WPA2 failure on a headless device is exactly what it exists to prevent.

- [ ] **Step 3: Restore the real PSK and build the AP image**

```bash
cd /path/to/rd03d/rd03d_uart && cp /tmp/sdkconfig.ap.bak sdkconfig.ap && rm /tmp/sdkconfig.ap.bak && source ~/esp/esp-idf-v5.5/export.sh >/dev/null 2>&1 && idf.py -B build.ap -D SDKCONFIG=sdkconfig.ap build 2>&1 | tail -8
```

**Expected: the AP build FAILS here, and that is correct.** Corrected 2026-09-11
after Task 4 ran — the original note claimed it would succeed, which was wrong.

Task 3 set `# CONFIG_RD03D_ENABLE_MQTT is not set` in `sdkconfig.ap`, and
`RD03D_MQTT_HOST` / `_PORT` / `_MOVE_MM` are `depends on` that option, so they
are *undefined* in the AP build. `mqtt_pub.c` is still in the source list until
Task 5, so it fails to compile:

```
main/mqtt_pub.c:48: error: 'CONFIG_RD03D_MQTT_HOST' undeclared
main/mqtt_pub.c:70: error: 'CONFIG_RD03D_MQTT_PORT' undeclared
main/mqtt_pub.c:116: error: 'CONFIG_RD03D_MQTT_MOVE_MM' undeclared
```

What this step actually verifies is that **`wifi_link.c` itself compiles clean**
in AP mode — look for `Building C object .../wifi_link.c.obj` passing with no
errors or warnings before ninja stops. Every reported error must be in
`mqtt_pub.c`; an error in `wifi_link.c` is a real failure.

This makes **Task 5 load-bearing for the AP build**, not a cleanup: until the
MQTT sources are conditional, `idf.py -B build.ap ... build` cannot succeed.

- [ ] **Step 4: Confirm the station image still builds unchanged**

```bash
cd /path/to/rd03d/rd03d_uart && source ~/esp/esp-idf-v5.5/export.sh >/dev/null 2>&1 && idf.py build 2>&1 | tail -6
```

Expected: `Project build complete.` This is the regression check — the station node must be unaffected.

- [ ] **Step 5: Commit**

```bash
cd /path/to/rd03d && git add rd03d_uart/main/wifi_link.c && git commit -m "feat(rd03d_uart): SoftAP branch in wifi_link

WIFI_MODE_AP with WPA2-PSK, channel and SSID from Kconfig, max 4 clients,
fixed 192.168.4.1 with the ESP running DHCP for joining laptops. mDNS is
registered in both modes and advertises over whichever interface is up.

wifi_link_is_up() is set on WIFI_EVENT_AP_START. Without that, main.c's OTA
validation would never see the network as up in AP mode and would roll back
every wirelessly-updated image after 90 s - while USB flashing kept working,
because a full flash erases otadata and never arms rollback.

A compile-time assert rejects a PSK under 8 characters; WPA2's minimum, and
otherwise esp_wifi_set_config fails at runtime on a headless device.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 5: Compile MQTT out of the AP image

**Files:**
- Modify: `rd03d_uart/main/main.c`, `rd03d_uart/main/CMakeLists.txt`

- [ ] **Step 1: Guard the include and the two call sites in `main.c`**

Replace line 10:

```c
#include "mqtt_pub.h"
```

with:

```c
#if CONFIG_RD03D_ENABLE_MQTT
#include "mqtt_pub.h"
#endif
```

Replace the `mqtt_pub_start();` line in `app_main` with:

```c
#if CONFIG_RD03D_ENABLE_MQTT
    mqtt_pub_start();
#endif
```

And the `mqtt_pub_frame(&frame);` line in the radar loop with:

```c
#if CONFIG_RD03D_ENABLE_MQTT
                mqtt_pub_frame(&frame);
#endif
```

Keep the surrounding indentation exactly as it is — the `mqtt_pub_frame` call is nested inside the frame-handling block.

- [ ] **Step 2: Drop the sources when the option is off**

Replace `rd03d_uart/main/CMakeLists.txt` with:

```cmake
set(rd03d_srcs "main.c" "rd03d.c" "wifi_link.c" "web_server.c" "ota_update.c")

# Leaving these out keeps esp-mqtt from being linked at all, so the AP image
# genuinely shrinks rather than carrying dead code.
if(CONFIG_RD03D_ENABLE_MQTT)
    list(APPEND rd03d_srcs "mqtt_throttle.c" "mqtt_pub.c")
endif()

idf_component_register(SRCS ${rd03d_srcs}
                    INCLUDE_DIRS ""
                    EMBED_FILES "index.html")
```

- [ ] **Step 3: Build both images and compare**

Note: `build.ap/` may hold a stale artifact built with MQTT enabled (Task 4 used
that as a one-off link proof). This step rebuilds it against the real config, so
the comparison is valid — but do not flash anything from `build.ap/` until after
this step has run.

```bash
cd /path/to/rd03d/rd03d_uart && source ~/esp/esp-idf-v5.5/export.sh >/dev/null 2>&1 && idf.py build >/dev/null 2>&1 && idf.py -B build.ap -D SDKCONFIG=sdkconfig.ap build >/dev/null 2>&1 && ls -l build/rd03d_uart.bin build.ap/rd03d_uart.bin | awk '{print $9, $5}'
```

Expected: both binaries exist, and `build.ap/rd03d_uart.bin` is **smaller** than `build/rd03d_uart.bin`. If the AP image is the same size or larger, esp-mqtt is still being linked — check the CMake condition rather than moving on.

- [ ] **Step 4: Confirm esp-mqtt is genuinely absent from the AP image**

```bash
cd /path/to/rd03d/rd03d_uart && grep -c "esp_mqtt\|mqtt_client" build.ap/rd03d_uart.map || echo "0 (absent)"; grep -c "esp_mqtt\|mqtt_client" build/rd03d_uart.map
```

Expected: a much lower count for `build.ap` than for `build` — ideally 0 for the AP map.

- [ ] **Step 5: Host tests still pass**

`mqtt_throttle.c` is excluded from the AP firmware build but is still compiled directly by its host test, so the tests must be unaffected:

```bash
cd /path/to/rd03d/rd03d_uart/tests && cc -Wall -Wextra -o test_rd03d test_rd03d.c ../main/rd03d.c && ./test_rd03d && cc -Wall -Wextra -o test_mqtt_throttle test_mqtt_throttle.c ../main/mqtt_throttle.c && ./test_mqtt_throttle
```

Expected: both report all tests passing.

- [ ] **Step 6: Commit**

```bash
cd /path/to/rd03d && git add rd03d_uart/main/main.c rd03d_uart/main/CMakeLists.txt && git commit -m "feat(rd03d_uart): compile MQTT out when RD03D_ENABLE_MQTT is off

Guards around the include and the two call sites in main.c, and the MQTT
sources dropped from the component when the option is off - so esp-mqtt is
not linked and the AP image actually shrinks instead of carrying dead code.

mqtt_throttle.c leaves the firmware build but its 13 host tests compile it
directly and are unaffected.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 6: Flash, verify on hardware, and document

**Files:**
- Modify: `rd03d_uart/README.md`

- [ ] **Step 1: Flash the AP image to the prototype board**

Confirm the board is present first:

```bash
PORT=$(ls /dev/cu.* 2>/dev/null | grep -i usbmodem | head -1); echo "PORT=$PORT"; test -n "$PORT" || echo "NO BOARD - ask the user to plug in the prototype XIAO"
```

Export that `PORT` and use it in both commands below. Do not hardcode a port
name: the assembled node has appeared as `usbmodem1101`, the prototype as
`usbmodem101`, and flashing the wrong one is how a working node gets
overwritten.

Then flash. Full `flash`, never `app-flash`:

```bash
cd /path/to/rd03d/rd03d_uart && source ~/esp/esp-idf-v5.5/export.sh >/dev/null 2>&1 && idf.py -B build.ap -D SDKCONFIG=sdkconfig.ap -p "$PORT" flash 2>&1 | tail -8
```

Expected: `Hash of data verified.` for each region and `Done`.

- [ ] **Step 2: Confirm the AP comes up**

```bash
cd /path/to/rd03d/rd03d_uart && source ~/esp/esp-idf-v5.5/export.sh >/dev/null 2>&1 && python3 -c "
import serial, time, os
s = serial.Serial(os.environ['PORT'], 115200, timeout=1)
end = time.time() + 20
while time.time() < end:
    l = s.readline()
    if l: print(l.decode(errors='replace'), end='')
s.close()
" 2>&1 | grep -i "softap\|wifi_link\|rd03d:" | head -12
```

Expected: `softap starting, ssid=rd03d-radar` and `softap up, ssid=rd03d-radar channel=6, http://192.168.4.1`. Radar frame lines should also be streaming.

This is also where a wrong channel or a rejected PSK would show up as an `esp_wifi_set_config` failure.

- [ ] **Step 3: Hand the rest to the user**

The remaining checks need a human with a laptop, because this Mac cannot join the AP without dropping its own network. Report to the user and ask them to confirm:

1. `rd03d-radar` appears in their laptop's WiFi list.
2. Joining it with the PSK succeeds.
3. `http://192.168.4.1` renders the radar chart with live targets.
4. `http://192.168.4.1/version` returns the current commit hash.
5. **The rollback check** — push an OTA over the AP link and confirm `/version` still reports the *new* hash two minutes later:

```bash
curl -X POST --data-binary @build.ap/rd03d_uart.bin http://192.168.4.1/update
```

Item 5 is the one that matters. Everything else would pass even with the AP-mode rollback bug present.

- [ ] **Step 4: Update `rd03d_uart/README.md`**

Add a section covering, with the actual commands:

- The two build configurations and their exact command lines, stating plainly that `sdkconfig` holds the home network credentials and `sdkconfig.ap` holds the AP PSK, and that both are untracked.
- How to flash each (`idf.py flash` vs `idf.py -B build.ap -D SDKCONFIG=sdkconfig.ap ... flash`), and why `app-flash` alone is wrong after an OTA.
- Joining the AP: SSID `rd03d-radar`, the chart at **http://192.168.4.1**, and that `rd03d.local` may also resolve.
- That joining the AP takes the laptop off its normal WiFi — use ethernet for the intranet alongside it.
- That MQTT is absent from the AP image by design, so no broker is needed or attempted.
- `RD03D_AP_CHANNEL` is the knob to turn first if the link feels slow; 1 and 11 are the congested ones in offices.

- [ ] **Step 5: Commit**

```bash
cd /path/to/rd03d && git add rd03d_uart/README.md && git commit -m "docs(rd03d_uart): document the station and SoftAP build variants

Both command lines, which sdkconfig holds which credentials, how to join the
AP and reach the chart at 192.168.4.1, that the laptop leaves its normal WiFi
while connected, and that RD03D_AP_CHANNEL is the first knob to turn if the
link is slow.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Definition of done

- Station image builds and flashes exactly as before; home credentials intact in `sdkconfig`; `rd03d.local` still reachable with MQTT publishing.
- AP image builds from the same tree, brings up `rd03d-radar` on channel 6 with WPA2, serves the chart at 192.168.4.1, and carries no esp-mqtt.
- A PSK shorter than 8 characters fails the build with a readable message.
- An OTA pushed over the AP link survives past the 90-second validation window.
- Both host test suites pass.
- No credential appears in any tracked file or commit message.
