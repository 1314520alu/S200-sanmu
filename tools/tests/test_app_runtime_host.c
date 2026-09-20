#include "app_runtime.h"

#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define PORT_COUNT 8U

static uint8_t s_polled[PORT_COUNT];
static uint8_t s_router_calls;
static uint8_t s_host_polls;
static uint8_t s_fault_polls;
static int s_failures;

bool port_poll_rx(uint8_t port, uint32_t *id, bool *ide,
                  uint8_t *data, uint8_t *len)
{
    ++s_polled[port];
    if (port != 5U) {
        return false;
    }
    *id = 0x321U;
    *ide = false;
    *len = 2U;
    data[0] = 0xAAU;
    data[1] = 0x55U;
    return true;
}

void port_monitor_faults(void)
{
    ++s_fault_polls;
}

void router_on_frame(uint8_t src_port, const uint8_t *data, uint8_t len,
                     uint32_t id, bool ide)
{
    if ((src_port != 5U) || (id != 0x321U) || ide || (len != 2U) ||
        (data[0] != 0xAAU) || (data[1] != 0x55U)) {
        ++s_failures;
    }
    ++s_router_calls;
}

void app_host_poll(void)
{
    ++s_host_polls;
}

int main(void)
{
    app_runtime_poll();
    for (uint8_t port = 0U; port < PORT_COUNT; ++port) {
        if (s_polled[port] != 1U) {
            ++s_failures;
        }
    }
    if ((s_router_calls != 1U) || (s_host_polls != 1U) ||
        (s_fault_polls != 1U)) {
        ++s_failures;
    }

    if (s_failures != 0) {
        return EXIT_FAILURE;
    }
    puts("app_runtime_host: ok");
    return EXIT_SUCCESS;
}
