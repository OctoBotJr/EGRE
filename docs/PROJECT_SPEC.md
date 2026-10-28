# PROJECT_SPEC (human-owned; protected)

## Central question
In LLM-agent reverse engineering, how often are the agent's conclusions entailed by the
observations it obtained, how does that differ from whether they are true, and can a
claim-type-specific evidence gate with active verification raise the share of conclusions that
are both supported and true without collapsing coverage?

## Hypotheses (each has a falsification outcome; see EVALUATION_PLAN.md)
- RQ1 Measurement: support and truth are only partially correlated at claim level.
- RQ2 Enforcement: gating cuts unsupported assertions with small recall cost and beats a
  coverage-matched random-abstention control.
- RQ3 Active verification: experiment-based verification adds precision beyond passive checking.

## Contributions
C1 support-vs-truth measurement protocol + RE claim taxonomy and evidence contracts.
C2 evidence-seeking gate (passive contract checking + executable verification + reason codes).
C3 benchmark with claim-level ground truth incl. benign misleading-evidence variants.
C4 empirical findings on the support/truth dissociation.
NOT claimed: novelty of provenance grouping / support ladders / claim gating as ideas (RARE has them).

## Scope
Input: one stripped Mach-O executable (arm64, macOS) + an analysis task.
Output: claim-structured report; each claim has status (verified | supported | hypothesis |
refuted), cited observation handles, experiment record; plus audit trail.
In scope claim types: T1 structure, T2 primitive identification, T3 data semantics,
T4 input/output relations and input constraints, T5 conditional reachability.
Out of scope: malware verdicts, family attribution, intent claims, exploit generation, live malware.

## Success thresholds (proposed, to be frozen before the main run)
S1 report P(true|unsupported) and P(false|supported) with intervals, whatever the sign.
S2 full gate cuts unsupported assertions >= 50% relative to ungated typed claims, loses <= 5 pts
   correct-claim recall, and beats the random-abstention control on the precision-coverage frontier.
S3 experiment runner agrees with the truth oracle on >= 95% of non-inconclusive verdicts; inconclusive <= 30%.
S4 contract checker vs human support labels: Cohen's kappa >= 0.7 on >= 300 double-annotated claims.
A null or negative result is a valid, reportable outcome.
