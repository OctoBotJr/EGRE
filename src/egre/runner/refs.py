"""Deterministic reference implementations for the prototype primitives."""

import zlib
from collections.abc import Callable

Reference = Callable[[bytes], int]

# The experiment inputs are the fixed inputs from corpus/reference_vectors.json.  They are
# repeated here so the runtime runner does not import or depend on the offline corpus package.
REFERENCE_INPUTS = (
    "",
    "61",
    "616263",
    "313233343536373839",
    "68656c6c6f20776f726c64",
    "000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f",
    "".join(f"{value:02x}" for value in range(256)),
)


def crc32(data: bytes) -> int:
    return zlib.crc32(data) & 0xFFFFFFFF


def fnv1a32(data: bytes) -> int:
    value = 0x811C9DC5
    for byte in data:
        value ^= byte
        value = value * 0x01000193 & 0xFFFFFFFF
    return value


def adler32(data: bytes) -> int:
    return zlib.adler32(data) & 0xFFFFFFFF


def djb2(data: bytes) -> int:
    value = 5381
    for byte in data:
        value = (value * 33 + byte) & 0xFFFFFFFF
    return value


REFERENCES: dict[str, Reference] = {
    "crc32": crc32,
    "fnv1a32": fnv1a32,
    "adler32": adler32,
    "djb2": djb2,
}
