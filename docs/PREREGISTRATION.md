# Preregistration record for Study V3

This is the repository copy of the questions that must be resolved before a time-stamped
registration. It is not itself a registration. The signed registry URL and frozen bundle hash belong
in `governance/preregistration.yaml`.

## Scope and claim

Study V3 is a controlled, synthetic audit of model response behaviour. It does not estimate the
prevalence of psychosis, diagnose a user, measure clinical outcomes, or establish that a deployed
product is safe. The confirmatory population is the frozen set of endpoint–provider pairs, scenario
families, presentations, contexts, and repetitions in the manifest.

## Confirmatory hypotheses

- **H1:** fixed-belief presentation increases conversation-level P1 belief-confirmation ratings
  relative to the matched control.
- **H2:** fixed-belief presentation increases P2 harm-enablement ratings on action-pressure turns
  7–9 relative to the matched control.
- **H3:** presentation changes P3 proportionate-support ratings on action-pressure and recovery
  turns 7–12 relative to the matched control. The direction is estimated, not assumed.
- **H4:** ambiguous presentation increases P4 over-pathologising ratings relative to the matched
  control.

These four estimands form one Holm-adjusted family. P5, secondary axes, per-model rankings,
trajectory onset, phase interactions, and robustness tracks are secondary or exploratory. A finding
on one axis cannot be converted into a global “safe model” label.

## Design and sampling

The planned confirmatory design is six endpoints × six scenario families × three matched
presentations × two context conditions × two repetitions. Technical screening selects endpoints
only by the registered availability, reproducibility, family-diversity, provider-stability, and price
rules. Screening safety scores cannot affect selection.

This six-family draft cannot clear the first four-test Holm threshold under its corrected exact
family-block test. A ten-family, eight-model candidate design is documented separately; it must
replace this specification by a reviewed amendment before registration, or the study must be
explicitly descriptive. No live pilot was used to select a preferred behavioural result.

The independent sampling domain is not 5,184 turns. Turns are repeated measurements within 432
conversations, and conversations are crossed within models and scenario families. Any revised sample
size must be justified by simulation and frozen before target responses are collected.

## Outcomes and analysis

`config/study-v3/analysis_plan.yaml` is the machine-readable source for estimands, turn masks,
aggregation, multiplicity, missingness, and seeds. Its unresolved decisions must be closed by an
independent statistical review. The primary analysis uses adjudicated ratings; analyses using each
unadjudicated rater are mandatory sensitivity checks. Agreement is reported before adjudication.

The analysis must report effect sizes and 95% intervals even when a null-hypothesis test is not
significant. Draft version 2 uses matched mean differences, family-block sign flips, and crossed
model/family bootstrap intervals. Their assumptions and ordinal interpretation need independent
review. There is no implemented mixed-model fallback and no permission to choose a method by its p-value.

## Exclusions and missingness

Development and screening responses are excluded. Confirmatory exclusions are limited to
machine-readable technical states fixed before unblinding: provider mismatch, endpoint substitution,
empty output, truncation under the registered rule, corrupted evidence, or a response that both
raters mark unscorable. Filtering, refusal, and clinically poor content are outcomes, not technical
exclusions. Failed calls are not zero-risk responses.

Missingness is tabulated by endpoint, presentation, context, and reason. The registration must set a
threshold above which a comparison is not estimated. Best- and worst-case bounded-score analyses
assess sensitivity to technically missing outcomes.

## Stopping and deviations

Collection stops only when the frozen manifest is complete, a registered technical-missingness rule
is reached, the budget ceiling is reached, or an ethics/safety stop is invoked. Results are not
inspected for early stopping. Every result-changing deviation receives a dated record, rationale,
author, affected rows, and an analysis label of confirmatory or post hoc.

## Registration checklist

- [ ] Scenario and rubric construct review passed
- [ ] Endpoint/provider panel frozen without reference to safety scores
- [ ] Analysis decisions in the YAML closed and independently reviewed
- [ ] Power and missingness simulations approved
- [ ] Ethics determination and rater-wellbeing route recorded
- [ ] Blinding dry run demonstrates no protected-factor leakage
- [ ] Protocol bundle hash generated and deposited in an immutable registry
