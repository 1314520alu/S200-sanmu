#ifndef APP_CONFIG_H
#define APP_CONFIG_H

#include <stdint.h>
#include <stdbool.h>

#define HUB_PORT_COUNT 8

typedef struct {
    uint8_t enable[HUB_PORT_COUNT];
    uint32_t magic;
} hub_config_t;

void hub_config_init(void);
const hub_config_t *hub_config_get(void);
bool hub_config_set_enable(const uint8_t enable[HUB_PORT_COUNT], bool force_fc_on);
bool hub_config_is_locked(void);
void hub_config_set_locked(bool locked);

#endif /* APP_CONFIG_H */
