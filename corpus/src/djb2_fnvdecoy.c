#include <stdint.h>
#include <stddef.h>
/* djb2 with a dead branch that mentions FNV-1a constants (misleading constants). */
__attribute__((noinline)) uint32_t target(const uint8_t *buf, size_t len) {
  uint32_t h = 5381u;
  if (len == (size_t)-1) { h ^= 0x811C9DC5u; h *= 0x01000193u; }
  for (size_t i = 0; i < len; i++) { h = ((h << 5) + h) + buf[i]; }
  return h;
}
#include "common.h"
