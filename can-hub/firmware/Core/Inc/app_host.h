#ifndef APP_HOST_H
#define APP_HOST_H

#include <stdint.h>

void app_host_init(void);
void app_host_on_rx_byte(uint8_t byte);
void app_host_poll(void);

#endif /* APP_HOST_H */
