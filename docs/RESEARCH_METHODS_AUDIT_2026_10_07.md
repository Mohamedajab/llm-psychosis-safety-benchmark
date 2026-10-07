# Methods audit, 7 October 2026

This is a protocol-development record. It does not report model safety results.

## Research question and contribution

The useful contribution is a matched, scripted comparison of response behaviours across belief
presentation and accumulated context, with a public path from evidence to human ratings and tables.
The benchmark's value depends on valid controls and reproducible measurement. Adding inexpensive
endpoints improves coverage of access tiers but does not resolve stimulus or rater validity.

Recent work motivates specific tests. [DelusionEval](https://arxiv.org/abs/2608.05004) evaluates
responses to real conversational histories and reports substantial context effects. Its replay
design and controlled-access histories address a different setting from a public scripted study in
which the target model's own replies accumulate. The planned external-validity claim must remain
limited to the latter setting. [MentalBench and MentalAlign](https://aclanthology.org/2026.eacl-long.180/)
find attribute-specific disagreement and inflation by automated judges. This supports retaining two
independent human ratings and reporting judge results separately if a judge study is later run.
[Clinician-informed psychosis judge validation](https://arxiv.org/abs/2604.02359) is further evidence
that automated labels require validation against expert consensus on the relevant constructs.

## Statistical defects corrected

The previous draft listed four primary estimands but simulated three contrasts. Its simulation
tested cell differences as independent even though models and scenario families were crossed. Its
proposed cumulative-link mixed model also lacked an implementation, and “repetition” with two levels
was listed as a random effect without an identified stochastic population. These choices did not
support the earlier detection-probability figures.

The revised draft defines the primary quantity as the equally weighted mean matched conversation
score difference. The four turn masks and contrast directions are unchanged. The executable test
flips signs jointly within a scenario-family block, preserving all model/context/repetition
differences in that block. It assumes independent, symmetric block differences under the null.
Presentation scripts were authored rather than randomly assigned treatments; p-values therefore
rely on that assumption and must not be described as causal randomisation inference.

The interval independently resamples model IDs and scenario-family IDs while retaining their crossed
cells, following the [pigeonhole bootstrap](https://arxiv.org/abs/0712.1111). It is a stability estimate
across this purposive panel, not evidence that the panel represents all models or users. Six models
and six families remain a small sample for interval coverage. [Permutation methods with dependence
blocks](https://ora.ox.ac.uk/objects/uuid%3Aff7332f0-89d1-4aa7-a23a-988e2d58442e) motivate specifying
the exchangeability assumption rather than permuting individual turns.

With six nonzero blocks, the smallest two-sided exact p-value is `2 / 2^6 = 0.03125`. The first
Holm threshold for four tests at alpha 0.05 is `0.05 / 4 = 0.0125`. The current design cannot reject
the first hypothesis under that test, even if every block points in the same direction. Eight
independent blocks merely make rejection attainable (`0.0078125`); they do not establish adequate
power. More repetitions reduce generation noise but do not create new independent scenario blocks.
The sample-size simulation now uses the same test and includes a null setting and family-specific
effect variation. Its binary proxy remains planning evidence only.

The required decision before registration is whether to expand independently authored and reviewed
scenario families, or register a descriptive study with effect estimates and no significance claims.
A statistician should review the mean-ordinal estimand and small-cluster interval procedure before
the protocol is frozen. The current four primary quantities require complete prespecified matched
cells; incomplete data are reason-coded and accompanied by bounded-score sensitivity intervals.

## Measurement and reporting

The implementation now preserves raw independent ratings, resolves disagreements only through a
separate adjudication record, and generates raw-rater sensitivity inputs. Constant ratings have
undefined weighted kappa; perfect raw agreement is reported without claiming perfect reliability.
Blinding removes explicit model and condition metadata. The original text remains visible and may
reveal identity or condition; model self-identification and obvious scenario cues limit blinding.

[TRIPOD-LLM](https://www.nature.com/articles/s41591-024-03425-5) and the
[QUEST human-evaluation framework](https://www.nature.com/articles/s41746-024-01258-7) support reporting
prompts, sampling, evaluator characteristics, training, blinding, agreement, missingness, and code.
The publication supplement should provide the completed reporting map and exact artifacts.

## What the present run establishes

The live run uses separate four-turn technical scripts and measures endpoint availability,
completion, truncation, provider identity, and provenance. It supplies no human safety labels and
cannot support behavioural rankings. The 432-conversation validation run uses marked placeholder
responses and programmatically generated ratings to test software. Its numerical contrasts must
never be presented as LLM findings or evidence of clinical safety.

All new endpoints are selected by price, context limits, text output, generation-parameter support,
and provider availability. GPT 5 Nano and Mercury were not added to this screen because the current
catalogue does not list the same temperature/top-p envelope as the comparison. No endpoint was
selected using an observed safety score. Catalogue metadata and exclusions are retained per batch.

## Expansion and longer trajectories

The candidate overlay now includes ten families, sixteen model endpoints, and a proposed eight-model
panel with at least five paid anchors. New families and shared continuation templates remain
unreviewed. Their labels do not establish independence. The 24-turn track preserves the original
first twelve prompts and adds recurrence and sustained recovery as exploratory phases.

[Sterna and colleagues](https://arxiv.org/abs/2608.13017) already used thirty-message trajectories
with fifteen models and four evaluators. This study therefore must not claim that longer dialogue
is new. The proposed contribution is matched scenario coverage, presentation controls, and
reproducible human measurement; a single-session trajectory is not a calendar-time experiment.

The four-design simulation found that adding turns alone left the six-block first-Holm rejection
probability at zero. The broader draft made rejection attainable under its assumptions, but weak
effects remained poorly detected. The results are a binary proxy and preliminary Monte Carlo
planning, not an approval of sample size or empirical evidence that one model is safer.

The software validation completed 432 simulated conversations and 5,184 responses. Separate live
audits preserve technical and long-track outcomes, including failed requests, without creating
human labels. External reviews and two independent raters remain necessary before a main study.
