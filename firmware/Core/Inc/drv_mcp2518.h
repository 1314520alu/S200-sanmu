#ifndef DRV_MCP2518_H
#define DRV_MCP2518_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define MCP2518_CLASSIC_MAX_DLEN 8U

typedef bool (*mcp2518_spi_transfer_fn)(void *user,
                                        const uint8_t *tx,
                                        uint8_t *rx,
                                        size_t len);
typedef void (*mcp2518_delay_us_fn)(void *user, uint32_t delay_us);

typedef struct {
    mcp2518_spi_transfer_fn spi_transfer;
    mcp2518_delay_us_fn delay_us;
    void *user;
    uint32_t oscillator_hz;
    uint8_t tx_fifo;
    uint8_t rx_fifo;
} mcp2518_t;

typedef struct {
    uint32_t id;
    uint8_t data[MCP2518_CLASSIC_MAX_DLEN];
    uint8_t len;
    bool ide;
    bool rtr;
} mcp2518_frame_t;

typedef struct {
    uint8_t tx_errors;
    uint8_t rx_errors;
    bool error_passive;
    bool bus_off;
} mcp2518_error_status_t;

void mcp2518_bind(mcp2518_t *dev,
                  mcp2518_spi_transfer_fn spi_transfer,
                  mcp2518_delay_us_fn delay_us,
                  void *user,
                  uint32_t oscillator_hz);
bool mcp2518_reset(mcp2518_t *dev);
bool mcp2518_init_1mbps_classic(mcp2518_t *dev);
bool mcp2518_send(mcp2518_t *dev, const mcp2518_frame_t *frame);
bool mcp2518_receive(mcp2518_t *dev, mcp2518_frame_t *frame);
bool mcp2518_get_error_status(mcp2518_t *dev,
                              mcp2518_error_status_t *status);

#ifdef __cplusplus
}
#endif

#endif /* DRV_MCP2518_H */
