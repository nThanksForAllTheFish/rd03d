# mqtt_throttle.c is in both variants despite the name: it is pure geometry
# with no MQTT dependency, and the LED is driven from the same movement
# decision so both images blink identically.
set(rd03d_srcs "main.c" "rd03d.c" "wifi_link.c" "web_server.c" "ota_update.c"
               "led.c" "mqtt_throttle.c")

# Leaving mqtt_pub.c out keeps esp-mqtt from being linked at all, so the AP
# image genuinely shrinks rather than carrying dead code.
if(CONFIG_RD03D_ENABLE_MQTT)
    list(APPEND rd03d_srcs "mqtt_pub.c")
endif()

idf_component_register(SRCS ${rd03d_srcs}
                    INCLUDE_DIRS ""
                    EMBED_FILES "index.html")
