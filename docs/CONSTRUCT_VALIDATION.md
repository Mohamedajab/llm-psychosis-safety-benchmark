# Construct-validation plan

The benchmark currently has face-valid scenarios and a structured rubric. That is not enough to
claim clinical validity. Content validation must happen before the scripts or rubric are frozen.

## Review panels

Use three distinct perspectives where possible:

- clinicians with current experience of psychosis-spectrum presentations and risk assessment;
- people with relevant lived experience, supported and compensated under an approved process;
- measurement or human-computer-interaction researchers who did not author the items.

The repository author cannot approve their own constructs. Record reviewer roles and aggregate
decisions publicly, but keep names, contact details, and attributable feedback in controlled storage.

## Scenario review

Review every turn for plausibility, avoidable stigma, leading language, unsafe actionability,
reading burden, and whether the three presentations differ mainly in evidential certainty rather
than emotional intensity or requested help. Reviewers independently rate relevance and clarity on a
four-point scale before discussion. Report the item-level distribution, the prespecified retention
rule, revisions, and a second review of changed items.

The matched manipulation needs an empirical check. In a separate blinded task, reviewers classify
each script as control, ambiguous, or fixed-belief and rate emotional intensity and urgency. A script
does not pass merely because its intended label can be guessed: classification must be high while
unintended differences in intensity and urgency remain small under a frozen equivalence rule.

## Rubric review

Reviewers map each rubric axis to the claimed construct and test boundary cases. The calibration set
must include safe engagement, appropriate uncertainty, warranted urgent escalation, unwarranted
escalation, partial enablement, refusal, and legitimate practical advice. P2 and P3 applicability is
anchored to prespecified turns in the analysis plan rather than selected after observing responses.

Before the main ratings, conduct short cognitive interviews in which raters explain how they used
each anchor. Revise ambiguous anchors, version the rubric, then use a fresh calibration set. Do not
reuse main-study outputs for training.

## Evidence required to pass

The public record must show panel composition by role, number of items reviewed, initial and revised
ratings, retention thresholds, change log, blinded manipulation-check results, unresolved concerns,
and the exact scenario/rubric hashes approved. A binary “expert reviewed” statement is insufficient.

This plan follows the broader evidence that health-LLM human evaluations need explicit evaluator
selection, training, checklists, sample description, blinding, and agreement reporting; see the
[QUEST review and framework](https://www.nature.com/articles/s41746-024-01258-7). It does not imply
that an offline synthetic benchmark is a clinical evaluation.
