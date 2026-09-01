#include <assert.h>
#include <stdio.h>
#include "../main/rd03d.h"

static void test_decode_sign_mag(void)
{
    /* MSB of high byte set -> positive: 0x8102 -> +0x0102 = +258 */
    assert(rd03d_decode_sign_mag(0x02, 0x81) == 258);
    /* MSB clear -> negative: 0x03E8 -> -1000 */
    assert(rd03d_decode_sign_mag(0xE8, 0x03) == -1000);
    /* Positive small value: 0x8019 -> +25 */
    assert(rd03d_decode_sign_mag(0x19, 0x80) == 25);
    /* Zero stays zero */
    assert(rd03d_decode_sign_mag(0x00, 0x00) == 0);
    /* Max magnitudes */
    assert(rd03d_decode_sign_mag(0xFF, 0xFF) == 32767);
    assert(rd03d_decode_sign_mag(0xFF, 0x7F) == -32767);
    /* Positive zero (0x8000) is also zero */
    assert(rd03d_decode_sign_mag(0x00, 0x80) == 0);
}

/* One valid frame: T1 at x=+258mm y=-1000mm v=+25cm/s res=360mm; T2/T3 absent. */
static const uint8_t GOOD_FRAME[RD03D_FRAME_LEN] = {
    0xAA, 0xFF, 0x03, 0x00,
    /* T1 */ 0x02, 0x81, 0xE8, 0x03, 0x19, 0x80, 0x68, 0x01,
    /* T2 */ 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    /* T3 */ 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x55, 0xCC,
};

static int feed_all(rd03d_parser_t *p, const uint8_t *bytes, size_t n,
                    rd03d_frame_t *frame)
{
    int frames = 0;
    for (size_t i = 0; i < n; i++) {
        if (rd03d_parser_feed(p, bytes[i], frame)) {
            frames++;
        }
    }
    return frames;
}

static void test_parse_good_frame(void)
{
    rd03d_parser_t p;
    rd03d_frame_t f;
    rd03d_parser_init(&p);

    assert(feed_all(&p, GOOD_FRAME, sizeof(GOOD_FRAME), &f) == 1);
    assert(f.targets[0].present);
    assert(f.targets[0].x_mm == 258);
    assert(f.targets[0].y_mm == -1000);
    assert(f.targets[0].speed_cms == 25);
    assert(f.targets[0].resolution_mm == 360);
    assert(!f.targets[1].present);
    assert(!f.targets[2].present);
    assert(p.dropped_bytes == 0);
    assert(p.bad_frames == 0);
}

static void test_resync_after_garbage(void)
{
    rd03d_parser_t p;
    rd03d_frame_t f;
    rd03d_parser_init(&p);

    /* Garbage prefix, including a lone 0xAA that is NOT a real header start. */
    const uint8_t garbage[] = {0x12, 0xAA, 0x34, 0x55, 0xCC};
    assert(feed_all(&p, garbage, sizeof(garbage), &f) == 0);
    assert(feed_all(&p, GOOD_FRAME, sizeof(GOOD_FRAME), &f) == 1);
    assert(f.targets[0].x_mm == 258);
    assert(p.dropped_bytes > 0);
}

static void test_bad_tail_counted_then_recovers(void)
{
    rd03d_parser_t p;
    rd03d_frame_t f;
    rd03d_parser_init(&p);

    uint8_t bad[RD03D_FRAME_LEN];
    for (size_t i = 0; i < RD03D_FRAME_LEN; i++) bad[i] = GOOD_FRAME[i];
    bad[29] = 0x00; /* corrupt tail */

    assert(feed_all(&p, bad, sizeof(bad), &f) == 0);
    assert(p.bad_frames == 1);
    /* Parser recovers: next clean frame parses. */
    assert(feed_all(&p, GOOD_FRAME, sizeof(GOOD_FRAME), &f) == 1);
}

int main(void)
{
    test_decode_sign_mag();
    test_parse_good_frame();
    test_resync_after_garbage();
    test_bad_tail_counted_then_recovers();
    printf("all tests passed\n");
    return 0;
}
