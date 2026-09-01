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
}

int main(void)
{
    test_decode_sign_mag();
    printf("all tests passed\n");
    return 0;
}
