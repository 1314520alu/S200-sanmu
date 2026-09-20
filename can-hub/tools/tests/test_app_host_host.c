#include "app_config.h"
#include "app_host.h"
#include "app_ports.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static char s_last_tx[512];
static int s_failures;
static bool s_receive_once;

static void expect_str(const char *label, const char *actual, const char *expected)
{
    if (strcmp(actual, expected) != 0) {
        fprintf(stderr, "FAIL %s:\n  got: %s\n  exp: %s\n",
                label, actual, expected);
        ++s_failures;
    }
}

void app_host_tx(const char *line)
{
    strncpy(s_last_tx, line, sizeof(s_last_tx) - 1U);
    s_last_tx[sizeof(s_last_tx) - 1U] = '\0';
}

bool app_ports_hw_fdcan_init(uint8_t instance, uint32_t bitrate)
{
    (void)instance;
    return bitrate == 1000000UL;
}

bool app_ports_hw_fdcan_send(uint8_t instance, const port_frame_t *frame)
{
    return (instance == 0U) && (frame->id == 0x123U) &&
           !frame->ide && (frame->len == 1U) && (frame->data[0] == 0xA5U);
}

bool app_ports_hw_fdcan_receive(uint8_t instance, port_frame_t *frame)
{
    if ((instance != 0U) || !s_receive_once) {
        return false;
    }
    s_receive_once = false;
    frame->id = 0x456U;
    frame->ide = false;
    frame->len = 1U;
    frame->data[0] = 0x5AU;
    return true;
}

static void feed_line(const char *line)
{
    for (const char *p = line; *p != '\0'; ++p) {
        app_host_on_rx_byte((uint8_t)*p);
    }
    app_host_on_rx_byte('\n');
}

static void test_ping(void)
{
    feed_line("{\"cmd\":\"ping\"}");
    expect_str("ping", s_last_tx, "{\"ok\":true,\"cmd\":\"ping\"}\n");
}

static void test_get_config(void)
{
    feed_line("{\"cmd\":\"get_config\"}");
    expect_str("get_config", s_last_tx,
               "{\"ok\":true,\"cmd\":\"get_config\",\"enable\":[1,1,1,1,1,1,1,0],"
               "\"lock\":false}\n");
}

static void test_set_config(void)
{
    feed_line("{\"cmd\":\"set_config\",\"enable\":[1,1,0,1,0,0,0,0]}");
    expect_str("set_config", s_last_tx,
               "{\"ok\":true,\"cmd\":\"set_config\",\"enable\":[1,1,0,1,0,0,0,0]}\n");
}

static void test_malformed_enable_arrays(void)
{
    static const char *bad_arrays[] = {
        "{\"cmd\":\"set_config\",\"enable\":[1,1,1,1,1,1,1]}",
        "{\"cmd\":\"set_config\",\"enable\":[1,1,1,1,1,1,1,0,0]}",
        "{\"cmd\":\"set_config\",\"enable\":[1,1,1,1,1,1,1,2]}",
        "{\"cmd\":\"set_config\",\"enable\":[1,1,1,1,1,1,1,01]}",
        "{\"cmd\":\"set_config\",\"enable\":[1,,1,1,1,1,1,0]}"
    };

    for (size_t i = 0U; i < sizeof(bad_arrays) / sizeof(bad_arrays[0]); ++i) {
        feed_line(bad_arrays[i]);
        expect_str("malformed enable", s_last_tx,
                   "{\"ok\":false,\"err\":\"bad_json\"}\n");
    }
}

static void test_locked(void)
{
    hub_config_set_locked(true);
    feed_line("{\"cmd\":\"set_config\",\"enable\":[1,1,1,1,1,1,1,0]}");
    expect_str("locked", s_last_tx, "{\"ok\":false,\"err\":\"locked\"}\n");
    hub_config_set_locked(false);
}

static void test_bad_json(void)
{
    feed_line("{not json}");
    expect_str("bad_json", s_last_tx, "{\"ok\":false,\"err\":\"bad_json\"}\n");
}

static void test_get_status(void)
{
    static const char *expected =
        "{\"ok\":true,\"cmd\":\"get_status\",\"ports\":["
        "{\"tx\":0,\"rx\":0,\"err\":0,\"fault\":false},"
        "{\"tx\":0,\"rx\":0,\"err\":0,\"fault\":false},"
        "{\"tx\":0,\"rx\":0,\"err\":0,\"fault\":false},"
        "{\"tx\":0,\"rx\":0,\"err\":0,\"fault\":false},"
        "{\"tx\":0,\"rx\":0,\"err\":0,\"fault\":false},"
        "{\"tx\":0,\"rx\":0,\"err\":0,\"fault\":false},"
        "{\"tx\":0,\"rx\":0,\"err\":0,\"fault\":false},"
        "{\"tx\":0,\"rx\":0,\"err\":0,\"fault\":false}"
        "]}\n";

    feed_line("{\"cmd\":\"get_status\"}");
    expect_str("get_status", s_last_tx, expected);
}

static void test_status_counters(void)
{
    uint32_t id;
    uint8_t data[8];
    uint8_t len;
    bool ide;
    const uint8_t tx_data = 0xA5U;
    static const char *expected =
        "{\"ok\":true,\"cmd\":\"get_status\",\"ports\":["
        "{\"tx\":1,\"rx\":1,\"err\":0,\"fault\":false},"
        "{\"tx\":0,\"rx\":0,\"err\":0,\"fault\":false},"
        "{\"tx\":0,\"rx\":0,\"err\":0,\"fault\":false},"
        "{\"tx\":0,\"rx\":0,\"err\":0,\"fault\":false},"
        "{\"tx\":0,\"rx\":0,\"err\":0,\"fault\":false},"
        "{\"tx\":0,\"rx\":0,\"err\":0,\"fault\":false},"
        "{\"tx\":0,\"rx\":0,\"err\":0,\"fault\":false},"
        "{\"tx\":0,\"rx\":0,\"err\":0,\"fault\":false}"
        "]}\n";

    if (!port_send(0U, 0x123U, false, &tx_data, 1U)) {
        ++s_failures;
    }
    s_receive_once = true;
    if (!port_poll_rx(0U, &id, &ide, data, &len)) {
        ++s_failures;
    }
    feed_line("{\"cmd\":\"get_status\"}");
    expect_str("status counters", s_last_tx, expected);
}

static void test_line_overflow(void)
{
    int i;

    app_host_init();
    for (i = 0; i < 256; ++i) {
        app_host_on_rx_byte((uint8_t)'x');
    }
    feed_line("{\"cmd\":\"ping\"}");
    expect_str("overflow257", s_last_tx, "{\"ok\":false,\"err\":\"bad_json\"}\n");
    feed_line("{\"cmd\":\"ping\"}");
    expect_str("post-overflow line", s_last_tx,
               "{\"ok\":true,\"cmd\":\"ping\"}\n");
}

static void emit_samples(void)
{
    feed_line("{\"cmd\":\"ping\"}");
    printf("SAMPLE ping %s", s_last_tx);
    feed_line("{\"cmd\":\"get_config\"}");
    printf("SAMPLE get_config %s", s_last_tx);
    feed_line("{\"cmd\":\"get_status\"}");
    printf("SAMPLE get_status %s", s_last_tx);
    hub_config_set_locked(true);
    feed_line("{\"cmd\":\"set_config\",\"enable\":[1,1,1,1,1,1,1,0]}");
    printf("SAMPLE locked %s", s_last_tx);
    hub_config_set_locked(false);
    feed_line("{not json}");
    printf("SAMPLE bad_json %s", s_last_tx);
}

int main(void)
{
    hub_config_init();
    if (!hub_config_is_locked()) {
        ++s_failures;
    }
    hub_config_set_locked(false);
    (void)port_init_all(1000000UL);
    app_host_init();

    test_ping();
    test_get_config();
    test_set_config();
    test_malformed_enable_arrays();
    test_locked();
    test_bad_json();
    test_get_status();
    test_status_counters();
    test_line_overflow();

    if (s_failures != 0) {
        fprintf(stderr, "%d assertion(s) failed\n", s_failures);
        return EXIT_FAILURE;
    }

    emit_samples();
    puts("app_host_host: ok");
    return EXIT_SUCCESS;
}
