#include <stdint.h>
#include <stddef.h>
/* CRC-32 whose polynomial constant never appears literally (computed at runtime). */
__attribute__((noinline)) uint32_t target(const uint8_t *buf, size_t len) {
  volatile uint32_t k = 0x12477CDFu;
  uint32_t poly = ~k;
  uint32_t crc = 0xFFFFFFFFu;
  for (size_t i = 0; i < len; i++) {
    crc ^= buf[i];
    for (int j = 0; j < 8; j++)
      crc = (crc >> 1) ^ (poly & (0u - (crc & 1u)));
  }
  return ~crc;
}
#include "common.h"
