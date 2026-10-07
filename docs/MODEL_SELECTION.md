# Model selection and cost policy

The panel is a budget-aware sampling frame, not a league table. Prices and availability were read
from the OpenRouter catalogue on 2026-09-30. A fresh snapshot and provider preflight are mandatory
at freeze time.

## Construction

The 11 screening endpoints provide exact slugs, at least 131,072 context tokens, text output, a
completion-limit parameter, six zero-price endpoints, five anchors at or below $0.40 per million
completion tokens, nine model families from eight organisations, and continuity with Study V2
through Nemotron 3 Super.

The health-specialised endpoint is exploratory because domain tuning is a confound as well as an
object of interest. It cannot silently replace a general-purpose model.

The original frame is retained for pilot reproducibility. Five additional cheap paid candidates in
`config/study-v3/paid_expansion.yaml` bring the explicit overlay to sixteen candidates, ten paid.
The expanded draft proposes eight selected endpoints and at least five paid anchors.
Its rule is a candidate amendment requiring provider preflight and
registration; no candidate is automatically eligible for confirmation.

## Confirmation rule

The confirmatory panel contains six endpoints if six pass the gate:

1. retain at least four model families;
2. retain at least two paid anchors;
3. include no more than two endpoints from one family;
4. prefer a stable provider pin, seed support, and complete coverage;
5. break remaining ties by lower cost ceiling, then lexicographic slug.

Behavioural screening scores are prohibited as selection inputs.

The 7 October pilots include asymmetric technical coverage: free endpoints initially received one
four-turn script, while paid batches attempted six. Availability reports retain these denominators;
they do not justify free-versus-paid behavioural comparisons or claim that screening is complete.

## Prices and free endpoints

Catalogue prices are observations, not contracts. The estimator ignores discounts and future price
changes. Free endpoints can be retired or rerouted, so automatic fallback and post-freeze
replacement are forbidden. Failure is missing coverage, not a reason to choose a nearby name.

## Local models

A local checkpoint, quantisation, engine, chat template, and hardware stack define a different
evaluated system from a hosted endpoint. A future local track must freeze those fields and cannot
pool outputs with OpenRouter under one label.
