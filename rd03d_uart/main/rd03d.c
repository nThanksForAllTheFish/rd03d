#include "rd03d.h"
#include <string.h>

int16_t rd03d_decode_sign_mag(uint8_t lo, uint8_t hi)
{
    int16_t magnitude = (int16_t)(((hi & 0x7F) << 8) | lo);
    return (hi & 0x80) ? magnitude : (int16_t)-magnitude;
}

static const uint8_t RD03D_HEADER[4] = {0xAA, 0xFF, 0x03, 0x00};

void rd03d_parser_init(rd03d_parser_t *p)
{
    memset(p, 0, sizeof(*p));
}

bool rd03d_parser_feed(rd03d_parser_t *p, uint8_t byte, rd03d_frame_t *frame)
{
    if (p->pos < sizeof(RD03D_HEADER)) {
        /* Hunting for / matching the header. */
        if (byte == RD03D_HEADER[p->pos]) {
            p->buf[p->pos++] = byte;
        } else {
            p->dropped_bytes += (uint32_t)p->pos + 1;
            /* The mismatched byte itself may start a new header. */
            if (byte == RD03D_HEADER[0]) {
                p->buf[0] = byte;
                p->pos = 1;
                p->dropped_bytes--; /* it wasn't dropped after all */
            } else {
                p->pos = 0;
            }
        }
        return false;
    }

    p->buf[p->pos++] = byte;
    if (p->pos < RD03D_FRAME_LEN) {
        return false;
    }
    p->pos = 0;

    if (p->buf[28] != 0x55 || p->buf[29] != 0xCC) {
        p->bad_frames++;
        return false;
    }

    for (int i = 0; i < RD03D_NUM_TARGETS; i++) {
        const uint8_t *b = &p->buf[4 + 8 * i];
        rd03d_target_t *t = &frame->targets[i];
        t->x_mm = rd03d_decode_sign_mag(b[0], b[1]);
        t->y_mm = rd03d_decode_sign_mag(b[2], b[3]);
        t->speed_cms = rd03d_decode_sign_mag(b[4], b[5]);
        t->resolution_mm = (uint16_t)(b[6] | (b[7] << 8));
        t->present = (t->x_mm != 0 || t->y_mm != 0);
    }
    return true;
}
