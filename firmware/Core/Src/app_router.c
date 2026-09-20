#include "app_router.h"

#include "app_config.h"
#include "app_ports.h"

void router_on_frame(uint8_t src_port, const uint8_t *data, uint8_t len,
                     uint32_t id, bool ide)
{
    const hub_config_t *cfg = hub_config_get();

    if (src_port >= HUB_PORT_COUNT) {
        return;
    }

    if (cfg->enable[src_port] == 0U) {
        return;
    }

    if (src_port == 0U) {
        for (uint8_t dst = 1U; dst < HUB_PORT_COUNT; dst++) {
            if (cfg->enable[dst] != 0U) {
                (void)port_send(dst, id, ide, data, len);
            }
        }
        return;
    }

    if (cfg->enable[0] != 0U) {
        (void)port_send(0U, id, ide, data, len);
    }
}
