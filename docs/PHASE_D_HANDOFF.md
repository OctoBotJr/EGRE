# Phase D handoff: V-10 (new corpus) + V-11 (knowledge base)

Everything below is staged under `corpus/v2_pending/` (not protected, not
wired into anything) so nothing touches the protected oracle files
(`corpus/src/`, `corpus/truth/`, `corpus/catalog.json`,
`corpus/reference_vectors.json`) until you've reviewed it. This doc is the
checklist for moving it into place and finishing validation. Not protected
itself — delete or edit freely once Phase D is done.

## What's already done for you (mechanical, not oracle work)

- `src/egre/corpus/build.py` now supports an `"opt": "O2"` field per catalog
  entry (defaults to `"O0"` if omitted) — no catalog changes needed for the
  existing 7 entries. Unit-tested in `tests/corpus/test_build.py`
  (`test_opt_flag_*`, no toolchain needed).
- The 4 new `.c` sources (exact code from V2_SPEC.md section 5.1).
- Catalog entries for the 4 new programs + `-O2` variants of all 11
  (15 new catalog entries total).
- Truth files for the 4 new programs.
- Reference-vector additions (`jamcrc`, `crc32c`, `fnv1_32`, `sdbm`) for the
  existing 7 public inputs.
- A held-out vectors file (different inputs than the public ones) covering
  all 8 closed-world + new primitives.
- `kb/algorithms.json` draft: 10 of 13 entries now carry `"validated": true`
  with a cited check value; 3 are explicitly flagged as still needing you.
- `kb_reference_impls.py`: Python reference implementation for every KB
  algorithm (re-exports crc32/adler32/fnv1a32/djb2 from
  `egre.runner.refs` so there's one implementation per algorithm, not two).

## Step 1 — new corpus programs (V-10)

```bash
cp corpus/v2_pending/src/*.c corpus/src/
cp corpus/v2_pending/truth/*.json corpus/truth/
```

Merge `corpus/v2_pending/catalog_additions.json`'s 15 entries into
`corpus/catalog.json` (it's currently a flat JSON array — just append).

Merge `corpus/v2_pending/reference_vectors_additions.json`'s 4 keys
(`jamcrc`, `crc32c`, `fnv1_32`, `sdbm`) into `corpus/reference_vectors.json`'s
`"expected"` object.

Then:

```bash
source .venv/bin/activate
python -m egre.corpus.build
python -m pytest tests/corpus -m toolchain -q
```

That test suite already checks (no changes needed there): every catalog
program got a signed arm64 Mach-O binary with `_target` stripped, and every
binary's native output matches `reference_vectors.json` for its truth
primitive on every input. If `jamcrc`/`crc32c`/`fnv1_32`/`sdbm`'s added
expected values are wrong, this is exactly where it'll fail — they were
computed from the literal C semantics in the new sources and cross-checked
against the published check values V2_SPEC.md section 5.2 already states
(JAMCRC/CRC-32C/FNV-1_32 all matched exactly); `sdbm` has no published check
value anywhere, so its entry is self-consistent only, not independently
cross-checked — worth a second look.

**Extra things to actually look at, not just run:**
- `sdbm_execdecoy`'s `-O2` build: the spec flags this as a risk — check the
  compiler didn't optimize away the `volatile uint32_t tag = 0xEDB88320u`
  dead-code marker, and that V-03's CFG builder still sees it as a separate
  block (dump it the same way `tests/graph/test_cfg.py` does for the
  existing decoys).
- Move `corpus/v2_pending/held_out_vectors.json` to `corpus/held_out_vectors.json`
  once you're happy with it, and add that path to
  `scripts/protected_paths.txt` alongside the other oracle files. Nothing
  reads it yet (I10 wiring + the experiment designer are V-17); this just
  gets the file in place.

## Step 2 — knowledge base (V-11)

`corpus/v2_pending/kb/algorithms.json` has 13 entries. **10 are already
validated**, against sources found this session:

| id | status | source |
|---|---|---|
| crc32, adler32, fnv1a32, djb2 | validated | already checked in v1 |
| jamcrc, crc32c, fnv1_32 | validated | published check values quoted in V2_SPEC.md §5.2 |
| fletcher32 | validated | Wikipedia's Fletcher's checksum article ("abcde"→0xF04FC729, "abcdefgh"→0xEBE19591) |
| jenkins_one_at_a_time | validated | Wikipedia's Jenkins hash function article ("a"→0xca2e9442, pangram→0x519e91f5) |
| murmur3_32 (seed 0) | validated | a published MurmurHash3 x86_32 test vector set (different seed, 0x9747b28c — confirms the algorithm itself; seed only changes h1's starting value) |

**3 need you**, each with a specific, different problem:

1. **`elf_hash` — a real discrepancy, not just missing data.** The
   canonical SVR4/ELF ABI definition (shift-left-4, add byte, fold the top
   nibble back in with xor) matches one web source on empty-string and
   single-byte input but **disagrees on every multi-byte input tried**
   (`"example"`, `"hash"`, `"function"`). Either that secondary source has a
   bug/variant, or `kb_reference_impls.py`'s does. Check against something
   more authoritative than a hashing-guide site — glibc's `elf_hash`,
   binutils, or the actual SVR4 ABI spec — before trusting either number.
2. **`sdbm`** — the *formula* is confirmed against the original sdbm
   library's own source description, but no numeric check value exists
   anywhere I found. Needs either a published vector or a second
   from-scratch implementation that agrees.
3. **`djb2a`** — the xor-variant formula (`hash = hash*33 ^ byte`) is
   confirmed against a secondary source, but again no numeric test vector
   turned up. Same ask as `sdbm`.

Once you've resolved those three (or decided to exclude them — "excluded,
not guessed" is a completely valid outcome per the spec), move the file and
reference implementations into place:

```bash
cp corpus/v2_pending/kb/algorithms.json kb/algorithms.json
cp corpus/v2_pending/kb_reference_impls.py src/egre/knowledge/refs.py  # new package — V-12 will build on this
```

(`src/egre/knowledge/` doesn't exist yet — V-12 creates the `lookup_knowledge`
tool there; dropping `refs.py` in now just means it's ready when V-12 starts.)

Write the validation tests V-11 asks for: one per entry, checking
`kb_reference_impls.KB_REFERENCES[id](bytes.fromhex(vec["input_hex"]))`
against each `public_vectors` entry, asserting `"validated": true` only
where that actually holds. A failing or still-`false` entry should make the
test suite tell you clearly, not silently pass.

## What's explicitly NOT done here

- No wiring: nothing imports `kb/algorithms.json` or
  `src/egre/knowledge/refs.py` into the runtime yet — that's V-12
  (`lookup_knowledge` tool) and V-16 (open-world mode).
- No held-out-vector *usage* — I10 (never exposed) and the experiment
  designer are V-17.
- `-O2` builds aren't evaluated against anything yet (V-13+ agent runs);
  V-10 just needs them to exist and match native output.

Ping me (or just start a new task) once you've validated/placed these and
I'll pick up Phase E (V-13 schema output, V-14 `query_graph`, V-15
reason-code feedback loop) or whatever's next.
