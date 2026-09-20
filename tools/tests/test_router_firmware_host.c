#include "app_config.h"
#include "app_router.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static hub_config_t s_config;
static uint8_t s_destinations[HUB_PORT_COUNT];
static size_t s_destination_count;
static int s_failures;

const hub_config_t *hub_config_get(void)
{
    return &s_config;
}

bool port_send(uint8_t port, uint32_t id, bool ide,
               const uint8_t *data, uint8_t len)
{
    if ((id != 0x1ABCDEUL) || !ide || (len != 2U) ||
        (data[0] != 0x12U) || (data[1] != 0x34U)) {
        ++s_failures;
    }
    s_destinations[s_destination_count++] = port;
    return true;
}

static void expect_destinations(const uint8_t *expected, size_t count)
{
    if ((s_destination_count != count) ||
        (memcmp(s_destinations, expected, count) != 0)) {
        fprintf(stderr, "FAIL destinations: got %u expected %u\n",
                (unsigned)s_destination_count, (unsigned)count);
        ++s_failures;
    }
}

int main(void)
{
    const uint8_t payload[2] = {0x12U, 0x34U};
    const uint8_t fc_expected[2] = {1U, 3U};
    const uint8_t branch_expected[1] = {0U};

    memset(&s_config, 0, sizeof(s_config));
    s_config.enable[0] = 1U;
    s_config.enable[1] = 1U;
    s_config.enable[3] = 1U;

    router_on_frame(0U, payload, 2U, 0x1ABCDEUL, true);
    expect_destinations(fc_expected, 2U);

    s_destination_count = 0U;
    router_on_frame(3U, payload, 2U, 0x1ABCDEUL, true);
    expect_destinations(branch_expected, 1U);

    s_destination_count = 0U;
    router_on_frame(2U, payload, 2U, 0x1ABCDEUL, true);
    expect_destinations(NULL, 0U);

    if (s_failures != 0) {
        return EXIT_FAILURE;
    }
    puts("router_firmware_host: ok");
    return EXIT_SUCCESS;
}
