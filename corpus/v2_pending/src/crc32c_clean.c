#include <stdint.h>
#include <stddef.h>
__attribute__((noinline)) uint32_t target(const uint8_t *buf, size_t len) {
  uint32_t crc = 0xFFFFFFFFu;
  for (size_t i = 0; i < len; i++) {
    crc ^= buf[i];
    for (int k = 0; k < 8; k++) crc = (crc >> 1) ^ (0x82F63B78u & (0u - (crc & 1u)));
  }
  return ~crc;
}
#include "common.h"
