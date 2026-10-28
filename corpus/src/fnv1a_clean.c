#include <stdint.h>
#include <stddef.h>
__attribute__((noinline)) uint32_t target(const uint8_t *buf, size_t len) {
  uint32_t h = 0x811C9DC5u;
  for (size_t i = 0; i < len; i++) { h ^= buf[i]; h *= 0x01000193u; }
  return h;
}
#include "common.h"
