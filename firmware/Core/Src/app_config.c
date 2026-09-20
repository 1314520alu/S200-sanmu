#include "app_config.h"

#include <string.h>

#ifndef HUB_CONFIG_USE_FLASH
#define HUB_CONFIG_USE_FLASH 0
#endif

#define HUB_CONFIG_MAGIC 0x48554221U /* "HUB!" */

static hub_config_t s_config;
static bool s_locked;

static void hub_config_defaults(hub_config_t *cfg)
{
    memset(cfg->enable, 0, sizeof(cfg->enable));
    cfg->enable[0] = 1;
    for (uint8_t i = 1; i < HUB_PORT_COUNT; i++) {
        cfg->enable[i] = 1;
    }
    cfg->enable[7] = 0;
    cfg->magic = HUB_CONFIG_MAGIC;
}

#if HUB_CONFIG_USE_FLASH
static bool hub_config_load_flash(hub_config_t *cfg)
{
    (void)cfg;
    return false;
}

static bool hub_config_save_flash(const hub_config_t *cfg)
{
    (void)cfg;
    return true;
}
#endif

void hub_config_init(void)
{
    s_locked = false;

#if HUB_CONFIG_USE_FLASH
    if (!hub_config_load_flash(&s_config)) {
        hub_config_defaults(&s_config);
        hub_config_save_flash(&s_config);
    }
#else
    hub_config_defaults(&s_config);
#endif
}

const hub_config_t *hub_config_get(void)
{
    return &s_config;
}

bool hub_config_set_enable(const uint8_t enable[HUB_PORT_COUNT], bool force_fc_on)
{
    if (s_locked) {
        return false;
    }

    uint8_t next_enable[HUB_PORT_COUNT];
    memcpy(next_enable, enable, sizeof(next_enable));

    if (force_fc_on || next_enable[0] == 0U) {
        next_enable[0] = 1U;
    }

    memcpy(s_config.enable, next_enable, sizeof(s_config.enable));
    s_config.magic = HUB_CONFIG_MAGIC;

#if HUB_CONFIG_USE_FLASH
    return hub_config_save_flash(&s_config);
#else
    return true;
#endif
}

bool hub_config_is_locked(void)
{
    return s_locked;
}

void hub_config_set_locked(bool locked)
{
    s_locked = locked;
}
