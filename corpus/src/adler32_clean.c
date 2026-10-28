#include <stdint.h>
#include <stddef.h>
__attribute__((noinline)) uint32_t target(const uint8_t *buf, size_t len) {
  uint32_t a = 1, b = 0;
  for (size_t i = 0; i < len; i++) { a = (a + buf[i]) % 65521u; b = (b + a) % 65521u; }
  return (b << 16) | a;
}
#include "common.h"
