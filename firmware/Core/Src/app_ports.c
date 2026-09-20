#include "app_ports.h"

#include "app_config.h"
#include "drv_adm3055.h"
#include "drv_mcp2518.h"

#include <stddef.h>
#include <stdint.h>
#include <string.h>

#define FDCAN_PORT_COUNT 3U
#define MCP_PORT_FIRST   3U
#define MCP_PORT_COUNT   5U
#define CLASSIC_BITRATE  1000000UL
#define MCP_OSC_HZ       40000000UL

#if defined(__GNUC__) || defined(__clang__)
#define APP_PORTS_WEAK __attribute__((weak))
#else
#define APP_PORTS_WEAK
#endif

static mcp2518_t s_mcp[MCP_PORT_COUNT];

APP_PORTS_WEAK bool app_ports_hw_fdcan_init(uint8_t instance,
                                            uint32_t bitrate)
{
    (void)instance;
    (void)bitrate;
    return false;
}

APP_PORTS_WEAK bool app_ports_hw_fdcan_send(uint8_t instance,
                                            const port_frame_t *frame)
{
    (void)instance;
    (void)frame;
    return false;
}

APP_PORTS_WEAK bool app_ports_hw_fdcan_receive(uint8_t instance,
                                               port_frame_t *frame)
{
    (void)instance;
    (void)frame;
    return false;
}

APP_PORTS_WEAK bool app_ports_hw_mcp_spi_transfer(uint8_t device,
                                                  const uint8_t *tx,
                                                  uint8_t *rx,
                                                  uint32_t len)
{
    (void)device;
    (void)tx;
    (void)rx;
    (void)len;
    return false;
}

APP_PORTS_WEAK void app_ports_hw_delay_us(uint32_t delay_us)
{
    (void)delay_us;
}

APP_PORTS_WEAK bool app_ports_hw_adm3055_silent(uint8_t port, bool level)
{
    (void)port;
    (void)level;
    return true;
}

APP_PORTS_WEAK bool app_ports_hw_adm3055_standby(uint8_t port, bool level)
{
    (void)port;
    (void)level;
    return true;
}

static bool mcp_spi_transfer(void *user, const uint8_t *tx,
                             uint8_t *rx, size_t len)
{
    const uint8_t device = (uint8_t)(uintptr_t)user;
    return app_ports_hw_mcp_spi_transfer(device, tx, rx, (uint32_t)len);
}

static void mcp_delay_us(void *user, uint32_t delay_us)
{
    (void)user;
    app_ports_hw_delay_us(delay_us);
}

static bool adm_silent_write(uint8_t port, bool level, void *user)
{
    (void)user;
    return app_ports_hw_adm3055_silent(port, level);
}

static bool adm_standby_write(uint8_t port, bool level, void *user)
{
    (void)user;
    return app_ports_hw_adm3055_standby(port, level);
}

static bool port_enabled(uint8_t port)
{
    const hub_config_t *cfg = hub_config_get();
    return (port < HUB_PORT_COUNT) && (cfg->enable[port] != 0U);
}

void port_apply_enable_state(void)
{
    for (uint8_t port = 0U; port < HUB_PORT_COUNT; ++port) {
        const bool disabled = !port_enabled(port);
        (void)adm3055_set_silent(port, disabled);
        (void)adm3055_set_standby(port, disabled);
    }
}

bool port_init_all(uint32_t bitrate)
{
    bool success = true;

    if (bitrate != CLASSIC_BITRATE) {
        return false;
    }

    adm3055_bind(adm_silent_write, adm_standby_write, NULL);
    for (uint8_t instance = 0U; instance < FDCAN_PORT_COUNT; ++instance) {
        if (!app_ports_hw_fdcan_init(instance, bitrate)) {
            success = false;
        }
    }
    for (uint8_t device = 0U; device < MCP_PORT_COUNT; ++device) {
        mcp2518_bind(&s_mcp[device], mcp_spi_transfer, mcp_delay_us,
                     (void *)(uintptr_t)device, MCP_OSC_HZ);
        if (!mcp2518_init_1mbps_classic(&s_mcp[device])) {
            success = false;
        }
    }

    port_apply_enable_state();
    return success;
}

bool port_send(uint8_t port, uint32_t id, bool ide, const uint8_t *data, uint8_t len)
{
    if ((port >= HUB_PORT_COUNT) || (len > 8U) ||
        (!ide && (id > 0x7FFUL)) || (ide && (id > 0x1FFFFFFFUL)) ||
        ((len != 0U) && (data == NULL)) || !port_enabled(port)) {
        if (port < HUB_PORT_COUNT) {
            (void)adm3055_set_silent(port, true);
        }
        return false;
    }

    (void)adm3055_set_standby(port, false);
    (void)adm3055_set_silent(port, false);

    if (port < FDCAN_PORT_COUNT) {
        port_frame_t frame = {
            .id = id,
            .len = len,
            .ide = ide
        };
        if (len != 0U) {
            memcpy(frame.data, data, len);
        }
        return app_ports_hw_fdcan_send(port, &frame);
    }

    mcp2518_frame_t frame = {
        .id = id,
        .len = len,
        .ide = ide,
        .rtr = false
    };
    if (len != 0U) {
        memcpy(frame.data, data, len);
    }
    return mcp2518_send(&s_mcp[port - MCP_PORT_FIRST], &frame);
}

bool port_poll_rx(uint8_t port, uint32_t *id, bool *ide,
                  uint8_t *data, uint8_t *len)
{
    port_frame_t frame;
    if ((port >= HUB_PORT_COUNT) || (id == NULL) || (ide == NULL) ||
        (data == NULL) || (len == NULL) || !port_enabled(port)) {
        if (port < HUB_PORT_COUNT) {
            (void)adm3055_set_silent(port, true);
        }
        return false;
    }

    memset(&frame, 0, sizeof(frame));
    if (port < FDCAN_PORT_COUNT) {
        if (!app_ports_hw_fdcan_receive(port, &frame)) {
            return false;
        }
    } else {
        mcp2518_frame_t mcp_frame;
        memset(&mcp_frame, 0, sizeof(mcp_frame));
        if (!mcp2518_receive(&s_mcp[port - MCP_PORT_FIRST], &mcp_frame)) {
            return false;
        }
        frame.id = mcp_frame.id;
        frame.ide = mcp_frame.ide;
        frame.len = mcp_frame.len;
        memcpy(frame.data, mcp_frame.data, mcp_frame.len);
    }

    if (frame.len > sizeof(frame.data)) {
        return false;
    }
    *id = frame.id;
    *ide = frame.ide;
    *len = frame.len;
    memcpy(data, frame.data, frame.len);
    return true;
}
