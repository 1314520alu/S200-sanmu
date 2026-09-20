#include "drv_mcp2518.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int failures;
static uint8_t device_memory[0x800];

static uint32_t read_u32(size_t address)
{
    return ((uint32_t)device_memory[address]) |
           ((uint32_t)device_memory[address + 1U] << 8) |
           ((uint32_t)device_memory[address + 2U] << 16) |
           ((uint32_t)device_memory[address + 3U] << 24);
}

static void write_u32(size_t address, uint32_t value)
{
    device_memory[address] = (uint8_t)value;
    device_memory[address + 1U] = (uint8_t)(value >> 8);
    device_memory[address + 2U] = (uint8_t)(value >> 16);
    device_memory[address + 3U] = (uint8_t)(value >> 24);
}

static bool fake_spi(void *user, const uint8_t *tx, uint8_t *rx, size_t len)
{
    const uint8_t instruction = tx[0] >> 4;
    const size_t address = (((size_t)tx[0] & 0x0FU) << 8) | tx[1];
    (void)user;

    if ((address + len - 2U) > sizeof(device_memory)) {
        return false;
    }
    memset(rx, 0, len);
    if (instruction == 0x2U) {
        memcpy(&device_memory[address], &tx[2], len - 2U);
    } else if (instruction == 0x3U) {
        memcpy(&rx[2], &device_memory[address], len - 2U);
    } else {
        return false;
    }
    return true;
}

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

static void expect_u32(const char *label, uint32_t actual, uint32_t expected)
{
    if (actual != expected) {
        fprintf(stderr, "FAIL %s: got 0x%08lx expected 0x%08lx\n",
                label, (unsigned long)actual, (unsigned long)expected);
        ++failures;
    }
}

static void prepare_fifo(mcp2518_t *dev, uint8_t fifo, uint32_t ua)
{
    const size_t fifo_base = 0x050U + ((size_t)fifo * 0x00CU);
    write_u32(fifo_base + 4U, 1U);
    write_u32(fifo_base + 8U, ua);
    write_u32(fifo_base, 0U);
    dev->tx_fifo = fifo;
    dev->rx_fifo = fifo;
}

static void test_tx_object_flag_layout(void)
{
    mcp2518_t dev;
    mcp2518_frame_t frame = {
        .id = 0x1ABCDE3UL,
        .len = 4U,
        .ide = true,
        .rtr = true
    };
    uint32_t expected_id =
        ((frame.id >> 18) & 0x7FFUL) | ((frame.id & 0x3FFFFUL) << 11);

    memset(device_memory, 0, sizeof(device_memory));
    mcp2518_bind(&dev, fake_spi, NULL, NULL, 40000000UL);
    prepare_fifo(&dev, 2U, 0U);
    expect_bool("extended RTR send", mcp2518_send(&dev, &frame), true);

    expect_u32("TX word0 contains SID/EID only", read_u32(0x400U), expected_id);
    /* MCP2518FD message object word1: DLC[3:0], IDE[4], RTR[5]. */
    expect_u32("TX word1 contains DLC/IDE/RTR", read_u32(0x404U),
               4U | (1UL << 4) | (1UL << 5));
}

static void test_rx_object_flag_layout(void)
{
    mcp2518_t dev;
    mcp2518_frame_t frame;
    const uint32_t id = 0x5A3U;

    memset(device_memory, 0, sizeof(device_memory));
    mcp2518_bind(&dev, fake_spi, NULL, NULL, 40000000UL);
    prepare_fifo(&dev, 1U, 0U);
    write_u32(0x400U, id);
    /* Standard RTR fixture: word1 DLC[3:0]=2, IDE[4]=0, RTR[5]=1. */
    write_u32(0x404U, 2U | (1UL << 5));

    expect_bool("standard RTR receive", mcp2518_receive(&dev, &frame), true);
    expect_u32("RX standard ID", frame.id, id);
    expect_bool("RX IDE from word1", frame.ide, false);
    expect_bool("RX RTR from word1", frame.rtr, true);
    expect_u8("RX DLC from word1", frame.len, 2U);
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
    const uint32_t citrec = (1UL << 20); /* Datasheet CiTREC.TXBP bit 20. */

    mcp2518_decode_citrec(citrec, &status);
    expect_u8("tx_errors", status.tx_errors, 0U);
    expect_u8("rx_errors", status.rx_errors, 0U);
    expect_bool("error_passive from TXBP", status.error_passive, true);
}

static void test_rxbp_datasheet_bit(void)
{
    mcp2518_error_status_t status;
    const uint32_t citrec = (1UL << 19); /* Datasheet CiTREC.RXBP bit 19. */

    mcp2518_decode_citrec(citrec, &status);
    expect_bool("error_passive from RXBP", status.error_passive, true);
}

static void test_bus_off_txbo_bit(void)
{
    mcp2518_error_status_t status;
    const uint32_t citrec = (1UL << 21); /* Datasheet CiTREC.TXBO bit 21. */

    mcp2518_decode_citrec(citrec, &status);
    expect_bool("bus_off from TXBO", status.bus_off, true);
    mcp2518_decode_citrec(1UL << 23, &status);
    expect_bool("reserved bit 23 is not RXBO", status.bus_off, false);
}

int main(void)
{
    test_tx_object_flag_layout();
    test_rx_object_flag_layout();
    test_tec_rec_decode();
    test_error_passive_from_rec();
    test_txbp_alone_not_required();
    test_rxbp_datasheet_bit();
    test_bus_off_txbo_bit();

    if (failures != 0) {
        fprintf(stderr, "%d assertion(s) failed\n", failures);
        return EXIT_FAILURE;
    }
    puts("mcp2518_citrec_host: ok");
    return EXIT_SUCCESS;
}
