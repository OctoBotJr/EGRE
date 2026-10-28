# PROTOTYPE — 3-hour vertical slice (human-owned; protected)

Goal: one end-to-end pipeline that shows the project's core claim on a tiny corpus:
**an agent's conclusions can be right-for-the-wrong-reason or supported-but-false, and an evidence gate with an
independent experiment separates them.** Everything else in the full spec is out of scope here.

## Scope (IN)
- ONE claim type: T2 "function at address A implements primitive P", P in {crc32, fnv1a32, adler32, djb2, other}.
- Corpus: 7 programs in corpus/src (4 clean, 2 decoy, 1 obfuscated), built at -O0 as Mach-O arm64, stripped, re-signed.
  Truth is in corpus/truth (offline only). corpus/reference_vectors.json holds independently computed expected outputs
  (verified against the C sources); use it as the oracle for the build test and the runner. DO NOT edit it.
- Pipeline: tools + ledger -> typed claims -> contract checker (support) -> experiment runner (verdict) -> status -> report -> evaluation table.
- Agent: one LLM loop + three SCRIPTED policies (deterministic, used for tests and the demo even without an API key).

## Scope (OUT; do not build now)
Ghidra, angr, Unicorn, gdb/strace, -O2, claim types T1/T3/T4/T5, free-form (C0) claim extraction, provenance grouping,
feedback loop to the agent, resume-safe orchestrator, gold annotation. (Stretch list at the bottom.)

## Key simplification (decision D-014)
Experiments execute the whole program natively (`./bin <hex>` -> 8 hex digits) under a no-network sandbox-exec wrapper
with timeout. Every program only wraps `target()`, so a run is function-level evidence anchored to the target function.
Unicorn is a later swap behind the same `Executor` interface.

## Interfaces (module paths are fixed so tasks integrate)
- egre/corpus/build.py  (offline CLI `python -m egre.corpus.build`): clang -arch arm64 -O0 -Icorpus/src; read `_target`
  address+size (nm or lief) BEFORE strip; strip; `codesign --force --sign -`; write bin to corpus/bin/<name> and the
  agent-visible task file corpus/tasks/<name>.json = {"program","binary","function_addr","function_size","signature":"u32 f(const u8*,size_t)","primitives":[...]}.
  Task files must NOT contain truth.
- egre/runner/refs.py: REFERENCES = {name: fn(bytes)->int} for crc32 (zlib), fnv1a32, adler32 (zlib), djb2.
- egre/runner/executor.py: run_program(binary, input_hex, timeout=5) -> int; raises ExecError. sandbox-exec profile `(version 1)(allow default)(deny network*)`.
- egre/runner/verify.py: verify_claim(binary, primitive) -> Verdict{verdict: confirmed|refuted|inconclusive, evidence}. Uses
  reference_vectors inputs. confirmed = all vectors match; refuted = execution OK and any mismatch; inconclusive = any execution failure. Never refuted on failure (invariant I3).
- egre/ledger/store.py: Observation{handle, kind: disasm|memory|run, tool, args, anchor{start,end}, payload, facts, ts}; Ledger append-only.
  The agent-facing API cannot write; unknown handle -> error (I1).
- egre/ledger/constants.py: extract_constants(disasm lines) -> set[int]. arm64 splits 32-bit constants across `mov`/`movk`
  (e.g. 0xEDB88320 = mov w8,#0x8320 ; movk w8,#0xedb8,lsl #16): reconstruct per register; also plain mov immediates (5381, 65521).
- egre/mediator/tools.py: disassemble(addr,count) (capstone on bytes read via lief), read_memory(addr,n) (hex), run(input_hex).
  Each call is validated, executed, recorded in the ledger, and returns a compact view + handle.
- egre/claims/schema.py: Claim{id, function_addr, primitive, cited_handles[], confidence}; Registry (<=3 claims per run).
- egre/contracts/t2.py: check(claim, ledger, task) -> Support{entailed|insufficient, reason}. Rules:
  (a) a cited disasm/memory observation anchored inside [function_addr, function_addr+size) whose constants intersect the
      claimed primitive's SIGNATURE constants {crc32:{0xEDB88320}, fnv1a32:{0x811C9DC5,0x01000193}, adler32:{65521}, djb2:{5381}}; OR
  (b) >= 2 cited `run` observations with distinct non-empty inputs whose recorded outputs equal the claimed primitive's reference output.
  Reasons: NO_CITATION, UNKNOWN_HANDLE, ANCHOR_MISMATCH, NO_SIGNATURE_EVIDENCE.
- egre/controller/status.py: status from (support, verdict): refuted -> "refuted"; confirmed -> "verified" (flag `support_gap=True` if insufficient);
  inconclusive -> "supported" if entailed else "hypothesis".
- egre/report/render.py: report rendered ONLY from the registry (+statuses). JSON and markdown.
- egre/llm/: base protocol; fake (scripted); one real provider adapter (OpenAI or Anthropic SDK; key from env var).
- egre/agent/loop.py + policies.py: JSON tool-call loop (max 12 steps); scripted policies:
    P1 grepper: disassemble target, claim every primitive whose signature constants appear, citing that handle.
    P2 emulator: run 3 inputs, match outputs to references, claim the match citing the run handles.
    P3 prior-guesser: disassemble, always claim crc32 citing the disasm handle.
- egre/evaluation/metrics.py + cli: join claims with corpus/truth; support x truth matrix; three report views:
    C1 ungated (all claims), C2 passive gate (entailed only), C3 full gate (verified only). Print table, save JSON.
- Orchestration CLI in egre/cli/ (not a runtime package): `python -m egre.cli.run`, `python -m egre.demo` (scripted policies, all 7 programs, prints the table).

## Expected demo outcomes (these are the acceptance assertions for P-07)
- P2 emulator: all 7 programs -> claim entailed (rule b), verified, true.
- P1 grepper: 4 clean -> entailed+true. fnv1a_crcdecoy -> crc32 claim entailed but REFUTED (supported-but-false).
  crc32_obfpoly -> no claim (coverage loss). djb2_fnvdecoy -> two claims: djb2 entailed+true, fnv1a32 entailed+REFUTED.
- P3 prior-guesser: crc32_clean -> entailed+true; crc32_obfpoly -> insufficient + verified (`support_gap`: right for the wrong reason);
  fnv1a_crcdecoy -> crc32 entailed (dead-branch constant) + REFUTED; the other programs -> insufficient + refuted.
- Gate views: C2 keeps supported-but-false claims; C3 (verified only) keeps zero false claims. Report both precision and coverage per view.

## Definition of "prototype works"
`python -m egre.demo` prints the per-policy matrix and the three views, matching the expectations above; a real-LLM run
(P-08, optional) produces the same table for >= 7 programs x 3 repeats.

## Stretch (only if time remains, in this order)
1 feedback loop (reason codes back to the agent) 2 -O2 builds 3 Unicorn executor 4 T4 input-constraint claims 5 free-form claims + normalizer 6 Ghidra as an extra tool.
