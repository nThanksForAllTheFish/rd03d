set(rd03d_srcs "main.c" "rd03d.c" "wifi_link.c" "web_server.c" "ota_update.c")

# Leaving these out keeps esp-mqtt from being linked at all, so the AP image
# genuinely shrinks rather than carrying dead code.
if(CONFIG_RD03D_ENABLE_MQTT)
    list(APPEND rd03d_srcs "mqtt_throttle.c" "mqtt_pub.c")
endif()

idf_component_register(SRCS ${rd03d_srcs}
                    INCLUDE_DIRS ""
                    EMBED_FILES "index.html")
