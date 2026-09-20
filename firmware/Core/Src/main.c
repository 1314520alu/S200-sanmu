#include "app_config.h"
#include "app_host.h"
#include "app_ports.h"

/*
 * USB-CDC host link (when CubeMX HAL USB device is present):
 *   - In CDC receive callback: app_host_on_rx_byte(byte) for each RX byte.
 *   - In main loop: app_host_poll().
 * UART fallback: feed the same API from USART RX interrupt or polling.
 */

int main(void)
{
    hub_config_init();
    (void)port_init_all(1000000UL);
    app_host_init();

    for (;;) {
        app_host_poll();
        /* TODO: CAN router poll, fault monitor, USB stack */
    }
}
