#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define RD03D_NUM_TARGETS 3
#define RD03D_FRAME_LEN   30

typedef struct {
    bool present;            /* false when x==0 && y==0 */
    int16_t x_mm;
    int16_t y_mm;
    int16_t speed_cms;
    uint16_t resolution_mm;
} rd03d_target_t;

typedef struct {
    rd03d_target_t targets[RD03D_NUM_TARGETS];
} rd03d_frame_t;

typedef struct {
    uint8_t buf[RD03D_FRAME_LEN];
    size_t pos;
    uint32_t dropped_bytes;  /* bytes discarded while hunting for a header */
    uint32_t bad_frames;     /* frames with a corrupt tail */
} rd03d_parser_t;

/* RD-03D sign-magnitude: high-byte MSB set = positive, clear = negative. */
int16_t rd03d_decode_sign_mag(uint8_t lo, uint8_t hi);

void rd03d_parser_init(rd03d_parser_t *p);

/* Feed one byte. Returns true when a complete valid frame was written to *frame. */
bool rd03d_parser_feed(rd03d_parser_t *p, uint8_t byte, rd03d_frame_t *frame);
