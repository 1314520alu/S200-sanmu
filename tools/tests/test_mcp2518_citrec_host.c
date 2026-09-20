#include "drv_mcp2518.h"

#include <stdio.h>
#include <stdlib.h>

static int failures;

static void expect_u8(const char *label, uint8_t actual, uint8_t expected)
{
    if (actual != expected) {
        fprintf(stderr, "FAIL %s: got %u expected %u\n",
                label, (unsigned)actual, (unsigned)expected);
        ++failures;
    }
}

static void expect_bool(const char *label, bool actual, bool expected)
{
    if (actual != expected) {
        fprintf(stderr, "FAIL %s: got %d expected %d\n",
                label, actual ? 1 : 0, expected ? 1 : 0);
        ++failures;
    }
}

static void test_tec_rec_decode(void)
{
    mcp2518_error_status_t status;
    const uint8_t rec = 42U;
    const uint8_t tec = 200U;
    const uint32_t citrec = ((uint32_t)tec << 8) | rec;

    mcp2518_decode_citrec(citrec, &status);
    expect_u8("rx_errors (REC)", status.rx_errors, rec);
    expect_u8("tx_errors (TEC)", status.tx_errors, tec);
    expect_bool("error_passive from TEC>=128", status.error_passive, true);
    expect_bool("bus_off clear", status.bus_off, false);
}

static void test_error_passive_from_rec(void)
{
    mcp2518_error_status_t status;
    const uint32_t citrec = 128U; /* REC=128, TEC=0 */

    mcp2518_decode_citrec(citrec, &status);
    expect_u8("rx_errors", status.rx_errors, 128U);
    expect_u8("tx_errors", status.tx_errors, 0U);
    expect_bool("error_passive from REC>=128", status.error_passive, true);
}

static void test_txbp_alone_not_required(void)
{
    mcp2518_error_status_t status;
    const uint32_t citrec = (1UL << 20); /* TXBP set, counters zero */

    mcp2518_decode_citrec(citrec, &status);
    expect_u8("tx_errors", status.tx_errors, 0U);
    expect_u8("rx_errors", status.rx_errors, 0U);
    expect_bool("error_passive from TXBP", status.error_passive, true);
}

static void test_bus_off_txbo_bit(void)
{
    mcp2518_error_status_t status;
    const uint32_t citrec = (1UL << 22); /* TXBO at CiTREC bit 22 */

    mcp2518_decode_citrec(citrec, &status);
    expect_bool("bus_off from TXBO", status.bus_off, true);
}

int main(void)
{
    test_tec_rec_decode();
    test_error_passive_from_rec();
    test_txbp_alone_not_required();
    test_bus_off_txbo_bit();

    if (failures != 0) {
        fprintf(stderr, "%d assertion(s) failed\n", failures);
        return EXIT_FAILURE;
    }
    puts("mcp2518_citrec_host: ok");
    return EXIT_SUCCESS;
}
