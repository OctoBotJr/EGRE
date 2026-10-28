/* Shared harness: wraps target() so each program can be run natively as `./prog <hex-bytes>` -> prints 8 hex digits. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
uint32_t target(const uint8_t *buf, size_t len);
int main(int argc, char **argv) {
  const char *hex = argc > 1 ? argv[1] : "";
  size_t n = strlen(hex) / 2;
  uint8_t *b = (uint8_t *)malloc(n ? n : 1);
  for (size_t i = 0; i < n; i++) { unsigned v = 0; sscanf(hex + 2 * i, "%2x", &v); b[i] = (uint8_t)v; }
  printf("%08x\n", target(b, n));
  free(b);
  return 0;
}
