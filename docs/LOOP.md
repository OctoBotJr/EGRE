# LOOP — iteration protocol

State lives on disk (STATUS, TASKS, PROGRESS, DECISIONS), not in the model's context. Each
iteration starts fresh and rebuilds context from these files.

## One iteration
1. ORIENT   Read AGENTS.md, docs/STATUS.md, docs/TASKS.md. Select the first `todo` task with all
            dependencies `done`. If it is `owner: human` or a human gate: set `loop_signal: STOP_HUMAN`, stop.
2. PLAN     Append a short plan to docs/PROGRESS.md: task id, files to touch, test-first outline.
3. BUILD    Test-first where possible. Implement only this task. Touch no protected file.
4. VERIFY   Run the task's `acceptance` command, then `./scripts/verify.sh`. Fix and retry (max 3 attempts).
5. REVIEW   Follow docs/playbooks/review-task.md on your own diff in a fresh pass: weakened tests?
            circular truth? LLM verdict leakage? scope creep? spec drift?
6. RECORD   Set the task `done` (or `blocked`). Update docs/STATUS.md (overwrite) and append the result to
            docs/PROGRESS.md. Add any spec question to docs/DECISIONS.md as `proposed`.
7. SIGNAL   Set `loop_signal` in docs/STATUS.md: CONTINUE | STOP_HUMAN | STOP_BLOCKED | STOP_DONE.
Do not commit; scripts/loop.sh commits only after verify and protected-path checks pass.

## Stop conditions
STOP_HUMAN (human gate or spec ambiguity) | STOP_BLOCKED (3 failed attempts) | STOP_DONE (no todo tasks) |
loop.sh limits (MAX_ITERS) | verify failure | protected-path violation.

## Roles (use separate sessions/agents if your Codex setup supports it)
- implementer: follows playbooks/implement-task.md
- reviewer:    follows playbooks/review-task.md with fresh context and different instructions
The loop is only as good as its verifier: when a failure pattern repeats, add a test or a
mechanical check, rather than adding prose to the prompt.
