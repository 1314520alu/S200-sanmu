#include "app_config.h"

#include "app_ports.h"

#include <string.h>

#ifndef HUB_CONFIG_USE_FLASH
/* TODO(production): enable and implement Flash persistence before release. */
#define HUB_CONFIG_USE_FLASH 0
#endif

#ifndef HUB_CONFIG_ALLOW
#define HUB_CONFIG_ALLOW 0
#endif

#define HUB_CONFIG_MAGIC 0x48554221U /* "HUB!" */

#if defined(__GNUC__) || defined(__clang__)
#define APP_CONFIG_WEAK __attribute__((weak))
#else
#define APP_CONFIG_WEAK
#endif

static hub_config_t s_config;
static bool s_locked;

APP_CONFIG_WEAK bool hub_config_hw_config_allowed(void)
{
    return HUB_CONFIG_ALLOW != 0;
}

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
    /* Production stays locked unless the board's config-allow input is asserted. */
    s_locked = !hub_config_hw_config_allowed();

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
    if (s_locked || (enable == NULL)) {
        return false;
    }

    uint8_t next_enable[HUB_PORT_COUNT];
    for (uint8_t i = 0U; i < HUB_PORT_COUNT; ++i) {
        if (enable[i] > 1U) {
            return false;
        }
        next_enable[i] = enable[i];
    }

    if (force_fc_on || next_enable[0] == 0U) {
        next_enable[0] = 1U;
    }

    memcpy(s_config.enable, next_enable, sizeof(s_config.enable));
    s_config.magic = HUB_CONFIG_MAGIC;
    port_apply_enable_state();

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
