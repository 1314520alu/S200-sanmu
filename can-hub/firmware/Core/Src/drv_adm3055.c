#include "drv_adm3055.h"

#include <string.h>

static adm3055_gpio_write_fn s_silent_write;
static adm3055_gpio_write_fn s_standby_write;
static void *s_user;
static bool s_silent[ADM3055_PORT_COUNT];
static bool s_standby[ADM3055_PORT_COUNT];

void adm3055_bind(adm3055_gpio_write_fn silent_write,
                  adm3055_gpio_write_fn standby_write,
                  void *user)
{
    s_silent_write = silent_write;
    s_standby_write = standby_write;
    s_user = user;
    memset(s_silent, 0, sizeof(s_silent));
    memset(s_standby, 0, sizeof(s_standby));
}

bool adm3055_set_silent(uint8_t port, bool silent)
{
    if (port >= ADM3055_PORT_COUNT) {
        return false;
    }
    if ((s_silent_write != NULL) &&
        !s_silent_write(port, silent, s_user)) {
        return false;
    }
    s_silent[port] = silent;
    return true;
}

bool adm3055_set_standby(uint8_t port, bool standby)
{
    if (port >= ADM3055_PORT_COUNT) {
        return false;
    }
    if ((s_standby_write != NULL) &&
        !s_standby_write(port, standby, s_user)) {
        return false;
    }
    s_standby[port] = standby;
    return true;
}

bool adm3055_is_silent(uint8_t port)
{
    return (port < ADM3055_PORT_COUNT) ? s_silent[port] : true;
}

bool adm3055_is_standby(uint8_t port)
{
    return (port < ADM3055_PORT_COUNT) ? s_standby[port] : true;
}
