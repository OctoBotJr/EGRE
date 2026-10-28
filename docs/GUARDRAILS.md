# GUARDRAILS (human-owned; protected)

## Mechanically enforced (scripts/check_protected.sh, tests/test_boundaries.py, verify.sh)
- Protected files cannot change in a loop commit (scripts/protected_paths.txt).
- Runtime packages cannot import corpus/evaluation; contracts/runner/controller cannot import LLM SDKs or egre.llm.
- Nothing is committed unless verify.sh passes.

## Behavioral rules
1. Tests: never delete, skip, xfail or weaken a test to get green. `@pytest.mark.toolchain` is allowed
   only for tests that truly need external tools; they run via `verify.sh --full`.
2. Truth independence: corpus/reference_vectors.json and corpus/truth are human-owned oracles; never edit them to make a test pass. Do not
   derive the checker's expectations from the same code that produced the truth.
3. No LLM verdicts anywhere in contracts, runner, controller, or truth.
4. Spend: real API calls only when the task says `spend: approved`, with a hard token/cost cap
   from configs/. Log every call.
5. Safety: benign synthetic programs only; no malware samples, no exploit code, no credential material.
6. Secrets: env vars only; never write keys to files, logs or commits.
7. Network: none during tool execution (wrapped with sandbox-exec, `(deny network*)`). Package installs only via pinned dependencies.
   Network/install/missing-tool failures are environmental: STOP_HUMAN, not a failed attempt.
   No sudo, no system-wide installs, no edits outside the repo.
8. Scope: one task per iteration; no drive-by refactors; no new dependencies without a DECISIONS entry.
9. Honesty: never mark a task `done` without the acceptance command's passing output recorded in PROGRESS.md.
10. Spec questions: if the spec is ambiguous or a threshold looks wrong, stop and write a DECISIONS entry.

## Human gates (loop must stop with loop_signal: STOP_HUMAN)
P-00 environment, P-08 real-LLM spend, any task marked `owner: human`. (Full-project gates are in docs/TASKS_FULL.md.)
