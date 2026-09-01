#include "rd03d.h"

int16_t rd03d_decode_sign_mag(uint8_t lo, uint8_t hi)
{
    int16_t magnitude = (int16_t)(((hi & 0x7F) << 8) | lo);
    return (hi & 0x80) ? magnitude : (int16_t)-magnitude;
}
