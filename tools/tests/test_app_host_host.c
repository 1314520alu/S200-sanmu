#include "app_config.h"
#include "app_host.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static char s_last_tx[512];
static int s_failures;

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

int main(void)
{
    hub_config_init();
    app_host_init();

    test_ping();
    test_get_config();
    test_set_config();
    test_locked();
    test_bad_json();

    if (s_failures != 0) {
        fprintf(stderr, "%d assertion(s) failed\n", s_failures);
        return EXIT_FAILURE;
    }

    puts("app_host_host: ok");
    return EXIT_SUCCESS;
}
