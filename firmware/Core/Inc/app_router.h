#ifndef APP_ROUTER_H
#define APP_ROUTER_H

#include <stdint.h>
#include <stdbool.h>

void router_on_frame(uint8_t src_port, const uint8_t *data, uint8_t len,
                     uint32_t id, bool ide);

#endif /* APP_ROUTER_H */
