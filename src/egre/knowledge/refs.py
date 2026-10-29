"""Reference implementations for every validated kb/algorithms.json entry.

Mirrors ``egre.runner.refs.REFERENCES``, but for the open-world knowledge
base (V-11/V-12) rather than the closed-world 4. ``crc32``/``adler32``/
``fnv1a32``/``djb2`` already live in ``egre.runner.refs`` and are re-exported
here rather than duplicated, so there is exactly one implementation per
algorithm.

Only algorithms with a validated kb/algorithms.json entry are implemented
here. ``elf_hash``, ``sdbm`` and ``djb2a`` were deliberately excluded
(docs/PHASE_D_HANDOFF.md): their formulas looked plausible but none had a
numeric check value that actually held up -- ``elf_hash`` in particular
disagreed with a secondary source on every multi-byte input tried. Per
V2_SPEC.md section 5.2, "entries that fail validation are excluded, not
guessed" -- they can be added back once genuinely validated.
"""

from __future__ import annotations

from collections.abc import Callable

from egre.runner.refs import adler32, crc32, djb2, fnv1a32

Reference = Callable[[bytes], int]
_MASK = 0xFFFFFFFF


def jamcrc(data: bytes) -> int:
    crc = 0xFFFFFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ (0xEDB88320 if crc & 1 else 0)
    return crc & _MASK


def crc32c(data: bytes) -> int:
    crc = 0xFFFFFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ (0x82F63B78 if crc & 1 else 0)
    return (~crc) & _MASK


def fnv1_32(data: bytes) -> int:
    h = 0x811C9DC5
    for byte in data:
        h = (h * 0x01000193) & _MASK
        h ^= byte
    return h


def fletcher32(data: bytes) -> int:
    if len(data) % 2:
        data = data + b"\x00"
    s1 = 0xFFFF
    s2 = 0xFFFF
    for i in range(0, len(data), 2):
        word = data[i] | (data[i + 1] << 8)
        s1 = (s1 + word) % 0xFFFF
        s2 = (s2 + s1) % 0xFFFF
    return ((s2 << 16) | s1) & _MASK


def murmur3_32(data: bytes, seed: int = 0) -> int:
    c1, c2 = 0xCC9E2D51, 0x1B873593
    length = len(data)
    h1 = seed
    rounded_end = (length // 4) * 4

    for i in range(0, rounded_end, 4):
        k1 = int.from_bytes(data[i : i + 4], "little")
        k1 = (k1 * c1) & _MASK
        k1 = ((k1 << 15) | (k1 >> 17)) & _MASK
        k1 = (k1 * c2) & _MASK
        h1 ^= k1
        h1 = ((h1 << 13) | (h1 >> 19)) & _MASK
        h1 = (h1 * 5 + 0xE6546B64) & _MASK

    k1 = 0
    tail = length & 0x03
    if tail == 3:
        k1 = data[rounded_end + 2] << 16
    if tail in (3, 2):
        k1 |= data[rounded_end + 1] << 8
    if tail in (3, 2, 1):
        k1 |= data[rounded_end]
        k1 = (k1 * c1) & _MASK
        k1 = ((k1 << 15) | (k1 >> 17)) & _MASK
        k1 = (k1 * c2) & _MASK
        h1 ^= k1

    h1 ^= length
    h1 ^= h1 >> 16
    h1 = (h1 * 0x85EBCA6B) & _MASK
    h1 ^= h1 >> 13
    h1 = (h1 * 0xC2B2AE35) & _MASK
    h1 ^= h1 >> 16
    return h1 & _MASK


def jenkins_one_at_a_time(data: bytes) -> int:
    h = 0
    for byte in data:
        h = (h + byte) & _MASK
        h = (h + (h << 10)) & _MASK
        h ^= h >> 6
    h = (h + (h << 3)) & _MASK
    h ^= h >> 11
    h = (h + (h << 15)) & _MASK
    return h & _MASK


KB_REFERENCES: dict[str, Reference] = {
    "crc32": crc32,
    "jamcrc": jamcrc,
    "crc32c": crc32c,
    "adler32": adler32,
    "fletcher32": fletcher32,
    "fnv1a32": fnv1a32,
    "fnv1_32": fnv1_32,
    "djb2": djb2,
    "murmur3_32": murmur3_32,
    "jenkins_one_at_a_time": jenkins_one_at_a_time,
}
