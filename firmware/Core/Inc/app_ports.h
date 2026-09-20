#ifndef APP_PORTS_H
#define APP_PORTS_H

#include <stdint.h>
#include <stdbool.h>

bool port_send(uint8_t port, uint32_t id, bool ide, const uint8_t *data, uint8_t len);

#endif /* APP_PORTS_H */
