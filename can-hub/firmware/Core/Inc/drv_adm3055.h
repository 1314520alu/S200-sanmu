#ifndef DRV_ADM3055_H
#define DRV_ADM3055_H

#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define ADM3055_PORT_COUNT 8U

typedef bool (*adm3055_gpio_write_fn)(uint8_t port, bool level, void *user);

/*
 * Board code supplies GPIO writers for the active-high SILENT and STANDBY
 * controls. Either writer may be NULL when that control is not routed.
 */
void adm3055_bind(adm3055_gpio_write_fn silent_write,
                  adm3055_gpio_write_fn standby_write,
                  void *user);
bool adm3055_set_silent(uint8_t port, bool silent);
bool adm3055_set_standby(uint8_t port, bool standby);
bool adm3055_is_silent(uint8_t port);
bool adm3055_is_standby(uint8_t port);

#ifdef __cplusplus
}
#endif

#endif /* DRV_ADM3055_H */
