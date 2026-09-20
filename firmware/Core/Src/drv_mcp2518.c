#include "drv_mcp2518.h"

#include <string.h>

#define MCP2518_INSTR_RESET 0x0U
#define MCP2518_INSTR_WRITE 0x2U
#define MCP2518_INSTR_READ  0x3U

#define MCP2518_REG_CICON      0x000U
#define MCP2518_REG_CINBTCFG   0x004U
#define MCP2518_REG_CITREC     0x034U
#define MCP2518_REG_FIFO_BASE  0x050U
#define MCP2518_REG_FIFO_STRIDE 0x00CU
#define MCP2518_REG_FLTCON0    0x1D0U
#define MCP2518_REG_FLTOBJ0    0x1F0U
#define MCP2518_REG_MASK0      0x1F4U
#define MCP2518_REG_OSC        0xE00U

#define MCP2518_RAM_BASE       0x400U

#define MCP2518_CICON_REQOP_MASK (7UL << 24)
#define MCP2518_CICON_OPMOD_MASK (7UL << 21)
#define MCP2518_MODE_CONFIG      4UL
#define MCP2518_MODE_CLASSIC     6UL

#define MCP2518_FIFO_TXEN      (1UL << 7)
#define MCP2518_FIFO_UINC      (1UL << 8)
#define MCP2518_FIFO_TXREQ     (1UL << 9)
#define MCP2518_FIFO_FRESET    (1UL << 10)
#define MCP2518_FIFO_TXAT_UNLIMITED (0UL << 21)
#define MCP2518_FIFO_SIZE_8    (7UL << 24)
#define MCP2518_FIFO_PLSIZE_8  (0UL << 29)
#define MCP2518_FIFO_TXNFIF    (1UL << 0)
#define MCP2518_FIFO_RXNEMPTYIF (1UL << 0)

#define MCP2518_OBJ_IDE        (1UL << 29)
#define MCP2518_OBJ_RTR        (1UL << 30)

#define MCP2518_TREC_EPASS     (1UL << 20)
#define MCP2518_TREC_TXBO      (1UL << 21)

#define MCP2518_DEFAULT_OSC_HZ 40000000UL
#define MCP2518_SPI_BUFFER_MAX 80U
#define MCP2518_MODE_RETRIES   100U

static uint32_t get_u32_le(const uint8_t *data)
{
    return ((uint32_t)data[0]) |
           ((uint32_t)data[1] << 8) |
           ((uint32_t)data[2] << 16) |
           ((uint32_t)data[3] << 24);
}

static void put_u32_le(uint8_t *data, uint32_t value)
{
    data[0] = (uint8_t)value;
    data[1] = (uint8_t)(value >> 8);
    data[2] = (uint8_t)(value >> 16);
    data[3] = (uint8_t)(value >> 24);
}

static bool spi_command(mcp2518_t *dev, uint8_t instruction,
                        uint16_t address, const uint8_t *write_data,
                        uint8_t *read_data, size_t data_len)
{
    uint8_t tx[MCP2518_SPI_BUFFER_MAX] = {0};
    uint8_t rx[MCP2518_SPI_BUFFER_MAX] = {0};
    const size_t transfer_len = data_len + 2U;

    if ((dev == NULL) || (dev->spi_transfer == NULL) ||
        (transfer_len > sizeof(tx))) {
        return false;
    }

    tx[0] = (uint8_t)((instruction << 4) | ((address >> 8) & 0x0FU));
    tx[1] = (uint8_t)address;
    if ((write_data != NULL) && (data_len != 0U)) {
        memcpy(&tx[2], write_data, data_len);
    }

    if (!dev->spi_transfer(dev->user, tx, rx, transfer_len)) {
        return false;
    }
    if ((read_data != NULL) && (data_len != 0U)) {
        memcpy(read_data, &rx[2], data_len);
    }
    return true;
}

static bool read_bytes(mcp2518_t *dev, uint16_t address,
                       uint8_t *data, size_t len)
{
    return spi_command(dev, MCP2518_INSTR_READ, address, NULL, data, len);
}

static bool write_bytes(mcp2518_t *dev, uint16_t address,
                        const uint8_t *data, size_t len)
{
    return spi_command(dev, MCP2518_INSTR_WRITE, address, data, NULL, len);
}

static bool read_reg(mcp2518_t *dev, uint16_t address, uint32_t *value)
{
    uint8_t data[4];
    if ((value == NULL) || !read_bytes(dev, address, data, sizeof(data))) {
        return false;
    }
    *value = get_u32_le(data);
    return true;
}

static bool write_reg(mcp2518_t *dev, uint16_t address, uint32_t value)
{
    uint8_t data[4];
    put_u32_le(data, value);
    return write_bytes(dev, address, data, sizeof(data));
}

static uint16_t fifo_con_address(uint8_t fifo)
{
    return (uint16_t)(MCP2518_REG_FIFO_BASE +
                      ((uint16_t)fifo * MCP2518_REG_FIFO_STRIDE));
}

static uint16_t fifo_sta_address(uint8_t fifo)
{
    return (uint16_t)(fifo_con_address(fifo) + 4U);
}

static uint16_t fifo_ua_address(uint8_t fifo)
{
    return (uint16_t)(fifo_con_address(fifo) + 8U);
}

static bool fifo_command(mcp2518_t *dev, uint8_t fifo, uint32_t command)
{
    uint32_t con;
    const uint16_t address = fifo_con_address(fifo);
    if (!read_reg(dev, address, &con)) {
        return false;
    }
    return write_reg(dev, address, con | command);
}

static bool request_mode(mcp2518_t *dev, uint32_t mode)
{
    uint32_t con;
    if (!read_reg(dev, MCP2518_REG_CICON, &con)) {
        return false;
    }
    con = (con & ~MCP2518_CICON_REQOP_MASK) | (mode << 24);
    if (!write_reg(dev, MCP2518_REG_CICON, con)) {
        return false;
    }

    for (uint32_t retry = 0; retry < MCP2518_MODE_RETRIES; ++retry) {
        if (!read_reg(dev, MCP2518_REG_CICON, &con)) {
            return false;
        }
        if (((con & MCP2518_CICON_OPMOD_MASK) >> 21) == mode) {
            return true;
        }
        if (dev->delay_us != NULL) {
            dev->delay_us(dev->user, 10U);
        }
    }
    return false;
}

static bool nominal_timing_1mbps(uint32_t oscillator_hz, uint32_t *nbtcfg)
{
    uint32_t total_tq;
    uint32_t brp = 1U;

    if ((nbtcfg == NULL) || (oscillator_hz < 8000000UL)) {
        return false;
    }

    total_tq = oscillator_hz / 1000000UL;
    while ((total_tq > 80U) && (brp < 256U)) {
        ++brp;
        if ((oscillator_hz % (1000000UL * brp)) == 0U) {
            total_tq = oscillator_hz / (1000000UL * brp);
        }
    }
    if ((oscillator_hz != (1000000UL * brp * total_tq)) ||
        (total_tq < 8U) || (total_tq > 80U)) {
        return false;
    }

    /* 80% sample point, with a legal minimum of two TQ after the sample. */
    uint32_t tseg2 = total_tq / 5U;
    if (tseg2 < 2U) {
        tseg2 = 2U;
    }
    const uint32_t tseg1 = total_tq - tseg2 - 1U;
    const uint32_t sjw = (tseg2 > 16U) ? 16U : tseg2;
    if ((tseg1 < 2U) || (tseg1 > 256U)) {
        return false;
    }

    *nbtcfg = ((brp - 1U) << 24) |
              ((tseg1 - 1U) << 16) |
              ((tseg2 - 1U) << 8) |
              (sjw - 1U);
    return true;
}

static uint32_t encode_id(const mcp2518_frame_t *frame)
{
    if (frame->ide) {
        return ((frame->id >> 18) & 0x7FFUL) |
               ((frame->id & 0x3FFFFUL) << 11) |
               MCP2518_OBJ_IDE;
    }
    return frame->id & 0x7FFUL;
}

static void decode_id(uint32_t object_id, mcp2518_frame_t *frame)
{
    frame->ide = (object_id & MCP2518_OBJ_IDE) != 0U;
    frame->rtr = (object_id & MCP2518_OBJ_RTR) != 0U;
    if (frame->ide) {
        frame->id = ((object_id & 0x7FFUL) << 18) |
                    ((object_id >> 11) & 0x3FFFFUL);
    } else {
        frame->id = object_id & 0x7FFUL;
    }
}

void mcp2518_bind(mcp2518_t *dev,
                  mcp2518_spi_transfer_fn spi_transfer,
                  mcp2518_delay_us_fn delay_us,
                  void *user,
                  uint32_t oscillator_hz)
{
    if (dev == NULL) {
        return;
    }
    memset(dev, 0, sizeof(*dev));
    dev->spi_transfer = spi_transfer;
    dev->delay_us = delay_us;
    dev->user = user;
    dev->oscillator_hz = (oscillator_hz == 0U) ?
                         MCP2518_DEFAULT_OSC_HZ : oscillator_hz;
    dev->tx_fifo = 2U;
    dev->rx_fifo = 1U;
}

bool mcp2518_reset(mcp2518_t *dev)
{
    if ((dev == NULL) || (dev->spi_transfer == NULL)) {
        return false;
    }
    if (!spi_command(dev, MCP2518_INSTR_RESET, 0U, NULL, NULL, 0U)) {
        return false;
    }
    if (dev->delay_us != NULL) {
        dev->delay_us(dev->user, 1000U);
    }
    return true;
}

bool mcp2518_init_1mbps_classic(mcp2518_t *dev)
{
    uint32_t nbtcfg;
    uint32_t osc;
    if ((dev == NULL) || !mcp2518_reset(dev) ||
        !request_mode(dev, MCP2518_MODE_CONFIG) ||
        !nominal_timing_1mbps(dev->oscillator_hz, &nbtcfg)) {
        return false;
    }

    /* Disable PLL and select divide-by-one system clock from OSC. */
    if (!read_reg(dev, MCP2518_REG_OSC, &osc) ||
        !write_reg(dev, MCP2518_REG_OSC, osc & ~(1UL << 0)) ||
        !write_reg(dev, MCP2518_REG_CINBTCFG, nbtcfg)) {
        return false;
    }

    const uint32_t rx_con = MCP2518_FIFO_FRESET |
                            MCP2518_FIFO_SIZE_8 |
                            MCP2518_FIFO_PLSIZE_8;
    const uint32_t tx_con = MCP2518_FIFO_TXEN |
                            MCP2518_FIFO_FRESET |
                            MCP2518_FIFO_TXAT_UNLIMITED |
                            MCP2518_FIFO_SIZE_8 |
                            MCP2518_FIFO_PLSIZE_8;
    if (!write_reg(dev, fifo_con_address(dev->rx_fifo), rx_con) ||
        !write_reg(dev, fifo_con_address(dev->tx_fifo), tx_con) ||
        /* Filter 0 accepts every standard/extended identifier into RX FIFO. */
        !write_reg(dev, MCP2518_REG_FLTOBJ0, 0U) ||
        !write_reg(dev, MCP2518_REG_MASK0, 0U) ||
        !write_reg(dev, MCP2518_REG_FLTCON0,
                   (1UL << 7) | dev->rx_fifo)) {
        return false;
    }

    return request_mode(dev, MCP2518_MODE_CLASSIC);
}

bool mcp2518_send(mcp2518_t *dev, const mcp2518_frame_t *frame)
{
    uint32_t status;
    uint32_t ua;
    uint8_t object[16] = {0};
    if ((dev == NULL) || (frame == NULL) ||
        (frame->len > MCP2518_CLASSIC_MAX_DLEN) ||
        (!frame->ide && (frame->id > 0x7FFUL)) ||
        (frame->ide && (frame->id > 0x1FFFFFFFUL)) ||
        !read_reg(dev, fifo_sta_address(dev->tx_fifo), &status) ||
        ((status & MCP2518_FIFO_TXNFIF) == 0U) ||
        !read_reg(dev, fifo_ua_address(dev->tx_fifo), &ua)) {
        return false;
    }

    uint32_t object_id = encode_id(frame);
    if (frame->rtr) {
        object_id |= MCP2518_OBJ_RTR;
    }
    put_u32_le(&object[0], object_id);
    put_u32_le(&object[4], frame->len & 0x0FU);
    if (!frame->rtr && (frame->len != 0U)) {
        memcpy(&object[8], frame->data, frame->len);
    }

    if (!write_bytes(dev, (uint16_t)(MCP2518_RAM_BASE + (ua & 0x7FFU)),
                     object, sizeof(object))) {
        return false;
    }
    return fifo_command(dev, dev->tx_fifo,
                        MCP2518_FIFO_UINC | MCP2518_FIFO_TXREQ);
}

bool mcp2518_receive(mcp2518_t *dev, mcp2518_frame_t *frame)
{
    uint32_t status;
    uint32_t ua;
    uint8_t object[16] = {0};
    if ((dev == NULL) || (frame == NULL) ||
        !read_reg(dev, fifo_sta_address(dev->rx_fifo), &status) ||
        ((status & MCP2518_FIFO_RXNEMPTYIF) == 0U) ||
        !read_reg(dev, fifo_ua_address(dev->rx_fifo), &ua) ||
        !read_bytes(dev, (uint16_t)(MCP2518_RAM_BASE + (ua & 0x7FFU)),
                    object, sizeof(object))) {
        return false;
    }

    decode_id(get_u32_le(&object[0]), frame);
    frame->len = (uint8_t)(get_u32_le(&object[4]) & 0x0FU);
    if (frame->len > MCP2518_CLASSIC_MAX_DLEN) {
        frame->len = MCP2518_CLASSIC_MAX_DLEN;
    }
    memcpy(frame->data, &object[8], frame->len);
    return fifo_command(dev, dev->rx_fifo, MCP2518_FIFO_UINC);
}

bool mcp2518_get_error_status(mcp2518_t *dev,
                              mcp2518_error_status_t *status)
{
    uint32_t trec;
    if ((dev == NULL) || (status == NULL) ||
        !read_reg(dev, MCP2518_REG_CITREC, &trec)) {
        return false;
    }
    status->tx_errors = (uint8_t)trec;
    status->rx_errors = (uint8_t)(trec >> 8);
    status->error_passive = (trec & MCP2518_TREC_EPASS) != 0U;
    status->bus_off = (trec & MCP2518_TREC_TXBO) != 0U;
    return true;
}
