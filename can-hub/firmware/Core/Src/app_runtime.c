#include "app_runtime.h"

#include "app_config.h"
#include "app_host.h"
#include "app_ports.h"
#include "app_router.h"

void app_runtime_poll(void)
{
    for (uint8_t port = 0U; port < HUB_PORT_COUNT; ++port) {
        uint32_t id;
        uint8_t data[8];
        uint8_t len;
        bool ide;

        if (port_poll_rx(port, &id, &ide, data, &len)) {
            router_on_frame(port, data, len, id, ide);
        }
    }

    port_monitor_faults();
    app_host_poll();
}
