#ifndef APP_PORTS_H
#define APP_PORTS_H

#include <stdint.h>
#include <stdbool.h>

typedef struct {
    uint32_t id;
    uint8_t data[8];
    uint8_t len;
    bool ide;
} port_frame_t;

typedef struct {
    uint32_t tx;
    uint32_t rx;
    uint32_t err;
    bool fault;
} port_status_t;

bool port_init_all(uint32_t bitrate);
bool port_send(uint8_t port, uint32_t id, bool ide, const uint8_t *data, uint8_t len);
bool port_poll_rx(uint8_t port, uint32_t *id, bool *ide,
                  uint8_t *data, uint8_t *len);
void port_apply_enable_state(void);
void port_monitor_faults(void);
bool port_get_status(uint8_t port, port_status_t *status);

/*
 * CubeMX board hooks. app_ports.c contains weak, host-compilable defaults;
 * main.c (or a board adapter) overrides these and calls HAL FDCAN/SPI/GPIO.
 */
bool app_ports_hw_fdcan_init(uint8_t instance, uint32_t bitrate);
bool app_ports_hw_fdcan_send(uint8_t instance, const port_frame_t *frame);
bool app_ports_hw_fdcan_receive(uint8_t instance, port_frame_t *frame);
bool app_ports_hw_mcp_spi_transfer(uint8_t device, const uint8_t *tx,
                                   uint8_t *rx, uint32_t len);
void app_ports_hw_delay_us(uint32_t delay_us);
bool app_ports_hw_adm3055_silent(uint8_t port, bool level);
bool app_ports_hw_adm3055_standby(uint8_t port, bool level);

#endif /* APP_PORTS_H */
