# Psychosis Safety Benchmark

Prospective, multi-turn evaluation of how language models respond to unsupported beliefs,
dependence cues, escalating risk, and opportunities for proportionate support.

This repository is an independent successor to
[`Mohamedajab/msc-llm-psychosis-benchmark`](https://github.com/Mohamedajab/msc-llm-psychosis-benchmark).
The completed MSc repository remains unchanged and is referenced as the read-only `upstream`
remote. New work follows the Study V3 protocol in this repository.

## Current status

**Live technical and exploratory pilots exist; no human-rated confirmatory findings exist.**

The repository is not paper-ready. Confirmatory collection is blocked until the protocol, scenario set,
model/provider pins, sample-size analysis, ethics position, and human-rater plan pass the
readiness checks in [`docs/PAPER_READINESS_GATE.md`](docs/PAPER_READINESS_GATE.md).

Do not cite the model list as a result or infer that a larger model panel makes the benchmark
clinically valid. This is a synthetic behavioural audit, not a diagnostic instrument and not a
test of outcomes in people.

The 7 October technical audit covers 16 candidates, including ten paid endpoints. Nine paid
endpoints returned responses. Of 66 planned conversations, 39 completed; 167 responses were stored,
including partial outputs. These are availability records, not safety scores. See
[`outputs/live_screening_2026-10-07.json`](outputs/live_screening_2026-10-07.json).

The requested larger collection has been sized down to **5,184 new exploratory responses**:
six models (five inexpensive paid, one free), ten families in a 12-turn core, and a
two-family 24-turn extension. This is 90% smaller than the full two-horizon grid.
The independent-scenario and annotation limits behind this decision are in
[`docs/SIZED_EXPLORATION_2026_10_07.md`](docs/SIZED_EXPLORATION_2026_10_07.md).
It is not a claim of adequate confirmatory power. The local viewer shows actual collection
progress; a planned target is not a completed dataset.
An early non-mutating audit verified 414 stored responses and 31 completed conversations,
with no truncation in that snapshot. See
[`outputs/live_sized_exploration_checked_2026-10-07.json`](outputs/live_sized_exploration_checked_2026-10-07.json).
Collection can continue beyond the snapshot timestamp; these counts are not final findings.

## Open the research viewer

```text
python -m pip install -e .[dev,dashboard]
python -m streamlit run streamlit_app.py
```

Open [http://127.0.0.1:8501](http://127.0.0.1:8501). The read-only viewer shows recorded evidence,
prices, design controls, draft scenarios, and publication blockers. Local dialogues are opt-in;
API keys and blinding maps are never displayed. The default viewer makes no model calls.
In VS Code, **Terminal → Run Task → Research: Streamlit viewer** starts the same local app.

For local collection controls, launch:

```text
python scripts/serve_research_lab.py --enable-collection-controls
```

On **Evidence**, use **Resume collection** to continue the saved sized exploration, or **Pause
collection** to checkpoint before the next call. Supply a key in the password field if the server
session has none. Keys are held in memory, not written to files. The launcher binds to loopback;
controls are disabled unless explicitly enabled on a loopback-bound server. Do not expose this
control-enabled app through a public tunnel or hosted deployment.

Status checks the collector's OS lock and process, not just an old `collecting` label. A separate
heartbeat and per-model turn, attempt, retry reason, last response, and budget details refresh every
five seconds. Resume retains recorded inputs and the persisted $5 cap, prevents duplicate launches,
and never regenerates accepted replies or terminal failed outputs. It is disabled after completion.
See [local controls](docs/LOCAL_COLLECTION_CONTROLS.md) for recovery and credential handling.

## Expanded research draft

[`config/research-expansion`](config/research-expansion) proposes eight models, at least five paid
anchors, ten scenario families, two contexts, and three repetitions. The 12-turn core would contain
1,440 conversations and 17,280 responses. A separate 24-turn exploratory track adds recurrence and
sustained recovery; it must not be pooled with primary estimates. Neither design is approved.
This larger proposal is retained for comparison, not currently selected for full collection.

The selected exploratory plan is
[`config/research-expansion/sized-exploration.yaml`](config/research-expansion/sized-exploration.yaml).
Preview without making API calls:

```text
python scripts/run_sized_exploration.py --output-dir data/raw/NEW_BATCH
```

Live collection additionally requires `--live --api-key-stdin --budget-usd 5` and a key
provided securely through stdin. A checkpoint can resume with `--resume` and the same
batch path and budget. Do not put keys in command-line arguments or commit them.
The runner retains failures, records exact inputs, caps routing prices, and reserves
conservative costs before calls. Unknown deliveries stay budgeted, not silently retried
as though they were free. See the sizing amendment for operational limits.

The original six-family configuration is retained for reproducibility. Longer conversations do not
create independent samples: the six-block draft cannot pass the first of four Holm tests. The
expanded planning comparison is in [`outputs/design_sensitivity.json`](outputs/design_sensitivity.json).
See [`docs/LONGITUDINAL_EXPANSION.md`](docs/LONGITUDINAL_EXPANSION.md) for limits and review requirements.

## What V3 changes

Study V2 compared two free endpoints across nine six-turn scripts. V3 adds:

- an original 11-endpoint frame, plus five explicitly recorded cheap paid candidates;
- separate screening and confirmatory stages;
- six scenario families and matched control, ambiguous, and fixed-belief variants;
- 12-turn trajectories with explicit escalation and recovery phases;
- context-depth and prompt re-anchoring factors;
- two independent human raters for confirmatory data, with adjudication and agreement gates;
- measures for over-pathologising, proportionality, autonomy support, and unhelpful refusal;
- provider pinning, catalogue snapshots, cost estimates, immutable manifests, and drift sentinels;
- a distinct interface-validation track, because an API is not a consumer chat product;
- a paper-readiness gate that prevents prose from outrunning the evidence.
- an OSF-ready preregistration record with four named primary estimands and a multiplicity family;
- HMAC-blinded annotation packets, private linkage keys, strict rating records, and leakage checks;
- reference implementations for weighted agreement, family-block sign-flip tests, crossed bootstrap
  intervals, and Holm adjustment;
- a construct-validation gate that cannot be self-approved by the repository author.

The audit behind these changes is in
[`docs/BENCHMARK_GAP_ANALYSIS.md`](docs/BENCHMARK_GAP_ANALYSIS.md). The prospective design is in
[`docs/PROSPECTIVE_PROTOCOL_V3.md`](docs/PROSPECTIVE_PROTOCOL_V3.md).

## Model panel

The catalogue snapshot dated 2026-09-30 contains six zero-price endpoints and five low-cost
anchors. Exact prices and eligibility notes are recorded in
[`config/study-v3/models.yaml`](config/study-v3/models.yaml); the panel is not frozen merely
because a slug appears in that file.

Five additional paid candidates, checked on 2026-10-07, are in
[`config/study-v3/paid_expansion.yaml`](config/study-v3/paid_expansion.yaml). Free price describes an
endpoint, not an open-weights licence. Paid candidates include both hosted open-weight and proprietary
models; no licence category is inferred from price.

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
  analysis_plan.yaml       Estimands, multiplicity, missingness, and frozen seeds
  scenarios/               Six paired scenario families
docs/
  BENCHMARK_GAP_ANALYSIS.md
  PROSPECTIVE_PROTOCOL_V3.md
  ANNOTATION_PROTOCOL_V3.md
  MODEL_SELECTION.md
  PAPER_READINESS_GATE.md
  PREREGISTRATION.md
  CONSTRUCT_VALIDATION.md
  PUBLICATION_REPORTING.md
  WRITING_STANDARD.md
src/psychosis_benchmark/
  schema.py                Strict configuration contracts
  design.py                Validation and deterministic manifest generation
  costing.py               Transparent upper-bound cost estimates
  annotation.py            Blinding and strict human-rating contracts
  statistics.py            Auditable agreement and sensitivity-analysis primitives
  analysis.py              Matched estimates, missingness bounds, trajectories
  expansion.py             Explicit scenario and long-horizon draft overlays
streamlit_app.py            Default read-only viewer; optional local collection controls
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
python scripts/check_live_catalogue.py
python scripts/simulate_power.py --output outputs/power_simulation.json
python scripts/run_validation.py --output-dir outputs/validation-new
python scripts/freeze_protocol.py
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
5. **Paper drafting** currently covers introduction, related work, implemented methods, and
   explicitly planned annotation and analysis. Empirical results and interpretation still require
   audited evidence, validated measurement, and completed ratings.

The current configuration is still blocked. In particular, the analysis plan is a draft, the
construct review and rater calibration have not happened, and no preregistration exists. Those
records are safeguards, not boxes that software can legitimately mark complete.

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

See [`CITATION.cff`](CITATION.cff) for software citation metadata. No completed-paper citation is
supplied; the partial working manuscript is not a published study.

## Working manuscript

The [standalone LaTeX draft](paper/manuscript.tex) contains a provisional methods-only abstract,
introduction, related work, methods, and limitations. It reports no behavioural results or model
rankings. [Research positioning and remaining requirements](paper/RESEARCH_POSITION.md) compare
the design with the closest benchmarks and explain why the contribution is a replication and
extension, not the first multi-turn psychosis evaluation. The native PDF compiler is currently
unavailable; source checks do not establish that the rendered layout is correct.

## Operational documentation

The executable collection, evidence-ledger, power-planning, and protocol-freeze workflow is
documented in [`docs/OPERATOR_GUIDE.md`](docs/OPERATOR_GUIDE.md).
