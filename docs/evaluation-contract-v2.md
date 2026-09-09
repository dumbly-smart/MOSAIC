# Verification evaluation contract v2

Status: implemented locally in the benchmark scorer (step 2 complete).
Policy identifier: `tender-evidence-quota-v2`.

This contract supersedes benchmark v1 in the current scorer and synthetic-tender-v3
criteria fixture. New reports carry the v2 policy identifier. Historical reports under
outputs/benchmark-v1 retain their original results; they are not v2 evaluations.
All examples here are synthetic, not official tender requirements.

## Outcome rules

| Evidence situation | Status | Reason code | Earned quota | Review required |
|---|---|---|---|---|
| Reliable evidence meets the primary requirement, including its normal allowed range | passed | requirement_met | 100% | No |
| Reliable evidence violates the primary requirement and is outside any valid fallback range | failed | requirement_not_met | 0% | No |
| Required information was not found in the submitted evidence | unsure | missing_information | 0% | Yes: awaiting clarification |
| Reliable evidence is outside the primary requirement but inside an explicitly supplied fallback/review range | unsure | explicit_fallback_range | 50% | Yes |
| Evidence is unreadable, conflicting, provisional, ungrounded, or has incompatible units | manual_review | evidence_unreliable | 0% | Yes |
| Extraction/model/retrieval is unavailable or incomplete, or the criterion itself is ambiguous | manual_review | processing_or_rule_error | 0% | Yes |

Missing information is not proof that the bidder fails the requirement. A retrieval
miss means information was not found, not that its absence from the whole document
has been proven. Do not report missing_information when processing itself failed.
The model's uncertainty flag never earns half credit by itself.

## Authority for ranges

- The primary requirement, units, comparison boundaries, and any fallback must come
  from structured tender criteria supplied by the teammate's adapter.
- Preserve the tender ID, criterion ID, rule version, exact source clause, and source
  reference (document/page or website URL and captured version/time where available).
- Each fallback must carry its own supporting clause/reference and explicit bounds,
  including whether endpoints are inclusive or exclusive. Do not infer a fallback
  from rounding, numerical closeness, model confidence, or a general website statement.
- No fallback clause means no fallback credit. A normal permitted range is a full-pass
  condition, not an uncertainty range. An explicit unconditional relaxation belongs
  in the primary acceptance rule rather than being mislabeled as a review range.
- Ambiguous or contradictory source rules require review; the model must not invent
  the missing interpretation. Fixture clauses must be clearly marked synthetic.

The invented 5% turnover tolerance has been removed from the active criteria fixture.
The updated expected baseline is 35/100. Historical
v1 reports remain historical records; do not silently relabel or overwrite them.

## Evaluation order and totals

1. Validate the criterion, its version and provenance, quota, units, and boundaries.
2. Check that processing completed and the evidence is usable and traceable.
3. If required information was not found, return unsure with zero points and clarification.
4. Check the primary requirement; if met, award full quota.
5. Otherwise check only an explicitly sourced fallback/review range; if met, award half.
6. Otherwise return failed with zero points.

Unreliable evidence cannot earn points merely because its proposed value falls inside
a primary or fallback range. Comparisons and scores are computed by code, not Qwen.
Use decimal arithmetic and explicit units; unsupported conversions require review.
Quotas total 100. Sum earned points without dropping unresolved criteria or rescaling
the denominator. Report the unresolved criteria alongside the total. The score is not
a compliance probability and never replaces the officer's final decision.

## Required finding fields

Each finding must retain policy version, tender/rule version, criterion ID, clause,
clause source, primary and fallback boundaries, quota, status, reason code, explanation,
earned points, and review/clarification requirement. Evidence must include the extracted
value and unit, exact quote, document ID, and available line/page/bounding-box location.
For missing evidence use null evidence, not a fabricated quote or location. Keep
processing failures distinguishable from absence of information. Preserve existing
core severity reporting; do not infer legal severity from the score alone.

## Acceptance examples for step 2

| Synthetic rule and evidence | Expected outcome |
|---|---|
| Turnover >= INR 1000000; evidence INR 970000; no fallback | failed, 0/25 |
| Same rule; no turnover evidence found after successful processing | unsure/missing_information, 0/25 |
| Same rule; explicit review interval [950000, 1000000); evidence INR 970000 | unsure/explicit_fallback_range, 12.5/25 |
| Same primary rule; evidence exactly INR 1000000 | passed, 25/25 |
| Engineers allowed in [10, 15]; reliable evidence 12 | passed, full quota |
| Engineers >= 10; evidence 12 but roster is provisional | manual_review, zero points |
| OCR/model failed, or two current values conflict | manual_review, zero points |

The range example is illustrative only and must not be added to the turnover fixture
as a replacement invented fallback. This contract is now covered by unit and CLI tests.
Next step: run live model evaluations under these rules.
