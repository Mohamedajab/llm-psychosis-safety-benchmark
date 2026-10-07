# Research position and manuscript status

Checked 7 October 2026. This is a targeted source comparison, not a systematic review.
The [working manuscript](manuscript.tex) contains no model-safety results.

## The question worth answering

For a selected panel of inexpensive endpoints, does avoiding endorsement of an unsupported
belief coincide with proportionate responses to a matched ordinary concern? How does that
profile change during a scripted opportunity for recovery, with the model's own earlier
replies retained?

The potential contribution is a reproducible comparison of these behaviours across authored
presentations. It is a replication and extension. More models, more turns, low API prices,
and a working dashboard do not establish novelty or clinical validity.

## Closest existing work

| Study | Direct overlap | What our selected design changes |
| --- | --- | --- |
| [Psychosis-Bench](https://arxiv.org/abs/2509.10970v2) | Eight models, sixteen twelve-turn scenarios, explicit/implicit framing and three behaviour scores | Authored ordinary-concern controls, separate unjustified-escalation and refusal axes, broader thematic pairing |
| [DelusionEval](https://arxiv.org/abs/2608.05004v1) | Delusion-linked behaviours and context effects using recorded histories from eighteen participants | Synthetic fixed user scripts; each target's own earlier completions enter later requests; weaker grounding in lived experience |
| [Sterna et al.](https://arxiv.org/abs/2608.13017v1) | Fifteen models, thirty-message script, four evaluators; premature medicalisation and trajectory changes | Multiple families, paired presentation variants, authored recovery/recurrence; no novelty claim for length |
| [MHSafeEval](https://arxiv.org/abs/2604.17730v1) | Multi-turn harms including over-pathologising, dependency and dismissiveness | Fixed-stimulus comparisons instead of adaptive worst-case search; no novelty claim for those harm constructs |
| [MentalHealthBench](https://cdn.openai.com/ctf-cdn/MentalHealthBench_A_Comprehensive_Benchmark_of_AI_Capabilities_in_Realistic_Mental_Health_Conversations.pdf) | Expert criteria for 1,215 prefixes across acuities, including psychosis and urgency calibration | Repeated endpoint-generated continuation under shared user scripts; our rubric does not yet have comparable expert validation |
| [Kirgis et al.](https://arxiv.org/abs/2604.06188v1) | Multi-turn delusion audit, human scoring, interface/API differences and date drift | Broader inexpensive endpoint panel; our API-only unpinned routing leaves those deployment gaps unresolved |

All listed elements have precedents. The combined comparison is useful only if the controls and
rubric support interpretable measurements. This search cannot prove that the combination is unique.
Claims of being the first, longest, most comprehensive, or a clinical safety certificate are excluded.

## What could make this a publishable extension

The main remaining work is independent review of scenarios and anchors, a blinded manipulation
check of intended matching, ethics determination for human annotation, calibrated independent
ratings, and an achieved-data analysis with explicit missingness. Compare distributions rather
than manufacture a single safety leaderboard. Include disagreements and unestimable contrasts.
An external anchor using licensed held-out cases from an established benchmark would strengthen
comparability, but has not been run or added to the current manifest.

One issue already identified is structural applicability: proportionate support may be N/A on
ordinary controls, and harm enablement may be N/A without a harmful request. The draft P2/P3
matched contrasts can therefore fail. Calling N/A zero would change the construct. Finalise
applicability and the scope of valid comparisons before ratings are locked; report the limitation
if no pooled comparison is defensible. Existing responses retain their original version.

## What is written and what is held back

Written: a provisional methods-only abstract; introduction; checked related work; current design,
collection policy, provenance and cost handling; planned annotation and analysis; limitations;
ethics/data status; references. Implemented operations use present tense. Unperformed human
work is explicitly labelled planned.

Held back: behavioural results, model rankings, an empirical discussion and conclusion, final
achieved denominators and collection dates, expert-validation findings, agreement coefficients,
final author affiliation/contributions/funding/conflict declarations, and venue-specific format.
None of these may be filled from synthetic validation fixtures or inferred from endpoint availability.

## Editing standard

The requested [Wikipedia guide](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing)
is used as an editorial checklist, not a detector or a scientific source. The draft uses specific
subjects and measurable claims, checked references, ordinary verbs, and restrained typography.
It avoids promotional novelty claims, generic literature attributions, decorative slogans,
forced rhetorical lists, and invented findings. Necessary qualifications are tied to actual design
limits. There is no promise that a reader or detector will identify the text as human-written.
AI assistance is disclosed and human author review remains required.

The manuscript bibliography is embedded in the standalone LaTeX file; no extra project files
are needed. The native compiler failed with `Unable to find standard directories for platform`
on 7 October 2026. The source is preserved, but PDF compilation and visual layout are unverified.
Check the rendered pages when the compiler is available before sharing a PDF.
