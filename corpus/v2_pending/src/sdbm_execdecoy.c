#include <stdint.h>
#include <stddef.h>
__attribute__((noinline)) uint32_t target(const uint8_t *buf, size_t len) {
  volatile uint32_t tag = 0xEDB88320u;   /* executed, never affects the result */
  (void)tag;
  uint32_t h = 0;
  for (size_t i = 0; i < len; i++) { h = buf[i] + (h << 6) + (h << 16) - h; }
  return h;
}
#include "common.h"
