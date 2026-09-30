# Psychosis Safety Benchmark

Prospective, multi-turn evaluation of how language models respond to unsupported beliefs,
dependence cues, escalating risk, and opportunities for proportionate support.

This repository is an independent successor to
[`Mohamedajab/msc-llm-psychosis-benchmark`](https://github.com/Mohamedajab/msc-llm-psychosis-benchmark).
The completed MSc repository remains unchanged and is referenced as the read-only `upstream`
remote. New work follows the Study V3 protocol in this repository.

## Current status

**Prospective protocol only. No Study V3 behavioural results exist.**

The repository is not paper-ready. Collection is blocked until the protocol, scenario set,
model/provider pins, sample-size analysis, ethics position, and human-rater plan pass the
readiness checks in [`docs/PAPER_READINESS_GATE.md`](docs/PAPER_READINESS_GATE.md).

Do not cite the model list as a result or infer that a larger model panel makes the benchmark
clinically valid. This is a synthetic behavioural audit, not a diagnostic instrument and not a
test of outcomes in people.

## What V3 changes

Study V2 compared two free endpoints across nine six-turn scripts. V3 adds:

- an exact-slug panel of 11 free or low-cost models from eight model families;
- separate screening and confirmatory stages;
- six scenario families and matched control, ambiguous, and fixed-belief variants;
- 12-turn trajectories with explicit escalation and recovery phases;
- context-depth and prompt re-anchoring factors;
- two independent human raters for confirmatory data, with adjudication and agreement gates;
- measures for over-pathologising, proportionality, autonomy support, and unhelpful refusal;
- provider pinning, catalogue snapshots, cost estimates, immutable manifests, and drift sentinels;
- a distinct interface-validation track, because an API is not a consumer chat product;
- a paper-readiness gate that prevents prose from outrunning the evidence.

The audit behind these changes is in
[`docs/BENCHMARK_GAP_ANALYSIS.md`](docs/BENCHMARK_GAP_ANALYSIS.md). The prospective design is in
[`docs/PROSPECTIVE_PROTOCOL_V3.md`](docs/PROSPECTIVE_PROTOCOL_V3.md).

## Model panel

The catalogue snapshot dated 2026-09-30 contains six zero-price endpoints and five low-cost
anchors. Exact prices and eligibility notes are recorded in
[`config/study-v3/models.yaml`](config/study-v3/models.yaml); the panel is not frozen merely
because a slug appears in that file.

Free endpoints can disappear, throttle heavily, or change provider. Confirmatory collection
requires a resolved provider pin and a successful preflight for every included endpoint. Router
aliases such as `openrouter/free`, automatic model substitution, and `*-latest` aliases are
forbidden.

## Repository layout

```text
config/study-v3/
  design.yaml              Factor definitions and run profiles
  models.yaml              Exact model slugs, prices, and panel roles
  rubric.yaml              Prospective behavioural rubric
  scenarios/               Six paired scenario families
docs/
  BENCHMARK_GAP_ANALYSIS.md
  PROSPECTIVE_PROTOCOL_V3.md
  ANNOTATION_PROTOCOL_V3.md
  MODEL_SELECTION.md
  PAPER_READINESS_GATE.md
  WRITING_STANDARD.md
src/psychosis_benchmark/
  schema.py                Strict configuration contracts
  design.py                Validation and deterministic manifest generation
  costing.py               Transparent upper-bound cost estimates
scripts/benchmark.py       Command-line entry point
tests/                     Offline validation tests
```

## Validate the prospective design

Use Python 3.12, create a virtual environment, and install the project. Then run:

```text
python -m pip install -e .[dev]
python scripts/benchmark.py validate
python scripts/benchmark.py manifest --profile screening --output outputs/screening.csv
python scripts/benchmark.py estimate-cost --profile screening
python -m pytest -q
```

`manifest` writes planned rows only. It does not call a model API. `estimate-cost` reports a
ceiling from declared token budgets and catalogue prices; it is not a bill forecast.

## Study stages

1. **Development** checks schemas, scenario matching, rater instructions, and the offline runner.
   Development responses cannot enter the confirmatory analysis.
2. **Screening** runs all eligible free and cheap endpoints on six technical scripts. Selection for
   the confirmatory panel follows a preregistered availability-and-diversity rule, not safety rank.
3. **Confirmatory** uses frozen prompts, pinned providers, two repetitions, blinded model labels,
   and two independent human raters.
4. **Robustness** tests deeper context, prompt re-anchoring, model drift, and a small manually
   captured chat-interface subset. These analyses are secondary.
5. **Paper drafting** begins only after the readiness gate passes. A manuscript is deliberately
   absent at present.

## Evidence boundaries

- Synthetic prompts are not patients, diagnoses, or clinical outcomes.
- An API endpoint is not interchangeable with a consumer chat interface.
- LLM judges may support quality control, but they are not the primary evidence.
- Free endpoint availability is a sampling constraint, not a model-quality attribute.
- A null result in this benchmark does not establish safety.
- Scenario and rubric content require clinical and lived-experience review before freeze.

## Authorship and lineage

**Author:** Mohamed Ajab  
**Programme:** MSc Advanced Computer Science, Loughborough University  
**Original study:** 2025–2026  
**V3 successor started:** 2026-09-30

See [`CITATION.cff`](CITATION.cff) for software citation metadata. No paper citation is supplied
because no V3 paper has been written.
