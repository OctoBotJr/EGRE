#include <stdint.h>
#include <stddef.h>
__attribute__((noinline)) uint32_t target(const uint8_t *buf, size_t len) {
  uint32_t h = 5381u;
  for (size_t i = 0; i < len; i++) { h = ((h << 5) + h) + buf[i]; }
  return h;
}
#include "common.h"
