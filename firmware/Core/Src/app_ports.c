#include "app_ports.h"

bool port_send(uint8_t port, uint32_t id, bool ide, const uint8_t *data, uint8_t len)
{
    (void)port;
    (void)id;
    (void)ide;
    (void)data;
    (void)len;
    return true;
}
