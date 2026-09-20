#include "app_config.h"
#include "app_ports.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MCP_COUNT 5U
#define REG_SPACE 0x1000U

static uint8_t s_regs[MCP_COUNT][REG_SPACE];
static bool s_silent[HUB_PORT_COUNT];
static int s_failures;

static uint32_t read_u32(uint8_t device, size_t address)
{
    const uint8_t *p = &s_regs[device][address];
    return ((uint32_t)p[0]) | ((uint32_t)p[1] << 8) |
           ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

static void write_u32(uint8_t device, size_t address, uint32_t value)
{
    uint8_t *p = &s_regs[device][address];
    p[0] = (uint8_t)value;
    p[1] = (uint8_t)(value >> 8);
    p[2] = (uint8_t)(value >> 16);
    p[3] = (uint8_t)(value >> 24);
}

bool app_ports_hw_fdcan_init(uint8_t instance, uint32_t bitrate)
{
    (void)instance;
    return bitrate == 1000000UL;
}

bool app_ports_hw_mcp_spi_transfer(uint8_t device, const uint8_t *tx,
                                   uint8_t *rx, uint32_t len)
{
    const uint8_t instruction = tx[0] >> 4;
    const size_t address = (((size_t)tx[0] & 0x0FU) << 8) | tx[1];
    memset(rx, 0, len);

    if (instruction == 0U) {
        memset(s_regs[device], 0, sizeof(s_regs[device]));
        return true;
    }
    if ((address + len - 2U) > REG_SPACE) {
        return false;
    }
    if (instruction == 2U) {
        memcpy(&s_regs[device][address], &tx[2], len - 2U);
        if ((address == 0U) && (len == 6U)) {
            uint32_t con = read_u32(device, 0U);
            con = (con & ~(7UL << 21)) | (((con >> 24) & 7UL) << 21);
            write_u32(device, 0U, con);
        }
        return true;
    }
    if (instruction == 3U) {
        memcpy(&rx[2], &s_regs[device][address], len - 2U);
        return true;
    }
    return false;
}

bool app_ports_hw_adm3055_silent(uint8_t port, bool level)
{
    s_silent[port] = level;
    return true;
}

int main(void)
{
    port_status_t status;

    hub_config_init();
    if (!port_init_all(1000000UL)) {
        fprintf(stderr, "FAIL port init\n");
        return EXIT_FAILURE;
    }

    for (uint8_t device = 0U; device < MCP_COUNT; ++device) {
        /* Independent datasheet fixture: CiTREC.TXBO is bit 21. */
        write_u32(device, 0x034U, (1UL << 21));
    }
    port_monitor_faults();

    for (uint8_t port = 3U; port < HUB_PORT_COUNT; ++port) {
        if (!port_get_status(port, &status) || !status.fault ||
            !s_silent[port]) {
            ++s_failures;
        }
    }

    if (s_failures != 0) {
        return EXIT_FAILURE;
    }
    puts("port_fault_host: ok");
    return EXIT_SUCCESS;
}
