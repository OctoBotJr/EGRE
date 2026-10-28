# Playbook: review your own diff (fresh pass)
Run `git diff` and answer each, citing file:line:
- Did any test get deleted, skipped, loosened, or have its expectation changed to match the code?
- Does any assertion compare code output to output of the same code (circular)? Is truth independent?
- Does any LLM output decide a status, verdict or truth? (violates I2)
- Can harness failure become `refuted`? (violates I3)
- Can the agent write the ledger or cite an unknown handle successfully? (violates I1)
- Does runtime code import corpus/evaluation? (violates I5)
- Is anything outside the task's scope changed? New dependency without a DECISIONS entry?
- Are novelty claims in comments/docs consistent with RESEARCH_NOTES (no overclaiming)?
If any answer is bad: fix it or mark the task blocked and write a DECISIONS entry.
