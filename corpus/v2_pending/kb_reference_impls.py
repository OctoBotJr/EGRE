"""Draft reference implementations for all 13 kb/algorithms.json entries.

Staged for V-11/V-12 review. Proposed final home: src/egre/knowledge/refs.py
(mirrors egre.runner.refs.REFERENCES, but for the open-world KB rather than
the closed-world 4). crc32/adler32/fnv1a32/djb2 already live in
egre.runner.refs and are NOT duplicated here -- KB_REFERENCES re-exports
them so there is one implementation per algorithm, not two.

The 7 entries marked "validated": true in kb/algorithms.json have been
checked against either a published check value quoted in V2_SPEC.md section
5.2, or (crc32/adler32/fnv1a32/djb2) v1's existing cross-checks. The other 6
(fletcher32, djb2a, sdbm, murmur3_32, jenkins_one_at_a_time, elf_hash) are
implemented here but NOT validated -- see PHASE_D_HANDOFF.md for exactly
what each one still needs before kb/algorithms.json can mark it true.
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


def djb2a(data: bytes) -> int:
    h = 5381
    for byte in data:
        h = ((h * 33) ^ byte) & _MASK
    return h


def sdbm(data: bytes) -> int:
    h = 0
    for byte in data:
        h = (byte + (h << 6) + (h << 16) - h) & _MASK
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


def elf_hash(data: bytes) -> int:
    h = 0
    for byte in data:
        h = ((h << 4) + byte) & _MASK
        high = h & 0xF0000000
        if high:
            h ^= high >> 24
        h &= ~high & _MASK
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
    "djb2a": djb2a,
    "sdbm": sdbm,
    "murmur3_32": murmur3_32,
    "jenkins_one_at_a_time": jenkins_one_at_a_time,
    "elf_hash": elf_hash,
}
