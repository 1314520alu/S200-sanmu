#include "app_host.h"

#include "app_config.h"

#include <ctype.h>
#include <stdio.h>
#include <string.h>

#define APP_HOST_LINE_MAX   256U
#define APP_HOST_TX_MAX     512U

#if defined(__GNUC__) || defined(__clang__)
#define APP_HOST_WEAK __attribute__((weak))
#else
#define APP_HOST_WEAK
#endif

static char s_line_buf[APP_HOST_LINE_MAX + 1U];
static size_t s_line_len;

APP_HOST_WEAK void app_host_tx(const char *line)
{
    (void)line;
}

static void app_host_send_line(const char *line)
{
    app_host_tx(line);
}

static void app_host_send_err(const char *err)
{
    char buf[64];
    (void)snprintf(buf, sizeof(buf), "{\"ok\":false,\"err\":\"%s\"}\n", err);
    app_host_send_line(buf);
}

static void trim_line(char *line)
{
    size_t start = 0U;
    size_t end = strlen(line);

    while ((start < end) && isspace((unsigned char)line[start])) {
        ++start;
    }
    while ((end > start) && isspace((unsigned char)line[end - 1U])) {
        --end;
    }
    if (start > 0U) {
        memmove(line, line + start, end - start);
    }
    line[end - start] = '\0';
}

static bool json_has_balanced_braces(const char *json)
{
    int depth = 0;

    for (const char *p = json; *p != '\0'; ++p) {
        if (*p == '{') {
            ++depth;
        } else if (*p == '}') {
            --depth;
            if (depth < 0) {
                return false;
            }
        }
    }
    return depth == 0;
}

static bool json_extract_cmd(const char *json, char *cmd, size_t cmd_cap)
{
    const char *key = strstr(json, "\"cmd\"");
    const char *value_start;
    const char *value_end;
    size_t len;

    if (key == NULL) {
        return false;
    }

    value_start = strchr(key, ':');
    if (value_start == NULL) {
        return false;
    }
    ++value_start;
    while (*value_start != '\0' && isspace((unsigned char)*value_start)) {
        ++value_start;
    }
    if (*value_start != '"') {
        return false;
    }
    ++value_start;
    value_end = strchr(value_start, '"');
    if (value_end == NULL) {
        return false;
    }

    len = (size_t)(value_end - value_start);
    if ((len == 0U) || (len >= cmd_cap)) {
        return false;
    }

    memcpy(cmd, value_start, len);
    cmd[len] = '\0';
    return true;
}

static bool json_parse_enable(const char *json, uint8_t enable[HUB_PORT_COUNT])
{
    const char *key = strstr(json, "\"enable\"");
    const char *cursor;
    int values = 0;

    if (key == NULL) {
        return false;
    }

    cursor = strchr(key, '[');
    if (cursor == NULL) {
        return false;
    }
    ++cursor;

    while (*cursor != '\0' && (*cursor != ']')) {
        while (*cursor != '\0' && (isspace((unsigned char)*cursor) || (*cursor == ','))) {
            ++cursor;
        }
        if (*cursor == ']') {
            break;
        }
        if ((*cursor != '0') && (*cursor != '1')) {
            return false;
        }
        if (values >= HUB_PORT_COUNT) {
            return false;
        }
        enable[values++] = (uint8_t)(*cursor - '0');
        ++cursor;
    }

    return values == HUB_PORT_COUNT;
}

static size_t append_enable(char *buf, size_t cap, size_t pos,
                            const uint8_t enable[HUB_PORT_COUNT])
{
    int written;
    uint8_t i;

    written = snprintf(buf + pos, cap - pos, "\"enable\":[");
    if ((written < 0) || ((size_t)written >= (cap - pos))) {
        return cap;
    }
    pos += (size_t)written;

    for (i = 0U; i < HUB_PORT_COUNT; ++i) {
        written = snprintf(buf + pos, cap - pos, "%s%d",
                           (i == 0U) ? "" : ",", enable[i]);
        if ((written < 0) || ((size_t)written >= (cap - pos))) {
            return cap;
        }
        pos += (size_t)written;
    }

    written = snprintf(buf + pos, cap - pos, "]");
    if ((written < 0) || ((size_t)written >= (cap - pos))) {
        return cap;
    }
    return pos + (size_t)written;
}

static void respond_ping(void)
{
    app_host_send_line("{\"ok\":true,\"cmd\":\"ping\"}\n");
}

static void respond_get_config(void)
{
    const hub_config_t *cfg = hub_config_get();
    char buf[APP_HOST_TX_MAX];
    size_t pos = 0U;
    int written;

    written = snprintf(buf, sizeof(buf),
                       "{\"ok\":true,\"cmd\":\"get_config\",");
    if ((written < 0) || ((size_t)written >= sizeof(buf))) {
        app_host_send_err("bad_json");
        return;
    }
    pos = (size_t)written;

    pos = append_enable(buf, sizeof(buf), pos, cfg->enable);
    if (pos >= sizeof(buf)) {
        app_host_send_err("bad_json");
        return;
    }

    written = snprintf(buf + pos, sizeof(buf) - pos, ",\"lock\":%s}\n",
                       hub_config_is_locked() ? "true" : "false");
    if ((written < 0) || ((size_t)written >= (sizeof(buf) - pos))) {
        app_host_send_err("bad_json");
        return;
    }

    app_host_send_line(buf);
}

static void respond_set_config(const char *json)
{
    uint8_t enable[HUB_PORT_COUNT];
    char buf[APP_HOST_TX_MAX];
    size_t pos = 0U;
    int written;

    if (hub_config_is_locked()) {
        app_host_send_err("locked");
        return;
    }

    if (!json_parse_enable(json, enable)) {
        app_host_send_err("bad_json");
        return;
    }

    if (!hub_config_set_enable(enable, true)) {
        app_host_send_err("locked");
        return;
    }

    written = snprintf(buf, sizeof(buf),
                       "{\"ok\":true,\"cmd\":\"set_config\",");
    if ((written < 0) || ((size_t)written >= sizeof(buf))) {
        app_host_send_err("bad_json");
        return;
    }
    pos = (size_t)written;

    pos = append_enable(buf, sizeof(buf), pos, hub_config_get()->enable);
    if (pos >= sizeof(buf)) {
        app_host_send_err("bad_json");
        return;
    }

    written = snprintf(buf + pos, sizeof(buf) - pos, "}\n");
    if ((written < 0) || ((size_t)written >= (sizeof(buf) - pos))) {
        app_host_send_err("bad_json");
        return;
    }

    app_host_send_line(buf);
}

static void respond_get_status(void)
{
    char buf[APP_HOST_TX_MAX];
    size_t pos = 0U;
    int written;
    uint8_t port;

    written = snprintf(buf, sizeof(buf),
                       "{\"ok\":true,\"cmd\":\"get_status\",\"ports\":[");
    if ((written < 0) || ((size_t)written >= sizeof(buf))) {
        app_host_send_err("bad_json");
        return;
    }
    pos = (size_t)written;

    for (port = 0U; port < HUB_PORT_COUNT; ++port) {
        written = snprintf(buf + pos, sizeof(buf) - pos,
                           "%s{\"tx\":0,\"rx\":0,\"err\":0,\"fault\":false}",
                           (port == 0U) ? "" : ",");
        if ((written < 0) || ((size_t)written >= (sizeof(buf) - pos))) {
            app_host_send_err("bad_json");
            return;
        }
        pos += (size_t)written;
    }

    written = snprintf(buf + pos, sizeof(buf) - pos, "]}\n");
    if ((written < 0) || ((size_t)written >= (sizeof(buf) - pos))) {
        app_host_send_err("bad_json");
        return;
    }

    app_host_send_line(buf);
}

static void app_host_handle_line(char *line)
{
    char cmd[32];

    trim_line(line);
    if (line[0] == '\0') {
        return;
    }

    if ((line[0] != '{') || (strchr(line, '}') == NULL) ||
        !json_has_balanced_braces(line) ||
        !json_extract_cmd(line, cmd, sizeof(cmd))) {
        app_host_send_err("bad_json");
        return;
    }

    if (strcmp(cmd, "ping") == 0) {
        respond_ping();
    } else if (strcmp(cmd, "get_config") == 0) {
        respond_get_config();
    } else if (strcmp(cmd, "set_config") == 0) {
        respond_set_config(line);
    } else if (strcmp(cmd, "get_status") == 0) {
        respond_get_status();
    } else {
        app_host_send_err("bad_json");
    }
}

void app_host_init(void)
{
    s_line_len = 0U;
}

void app_host_on_rx_byte(uint8_t byte)
{
    if (byte == '\r') {
        return;
    }

    if (byte == '\n') {
        s_line_buf[s_line_len] = '\0';
        app_host_handle_line(s_line_buf);
        s_line_len = 0U;
        return;
    }

    if (s_line_len >= APP_HOST_LINE_MAX) {
        s_line_len = 0U;
        app_host_send_err("bad_json");
        return;
    }

    s_line_buf[s_line_len++] = (char)byte;
}

void app_host_poll(void)
{
}
