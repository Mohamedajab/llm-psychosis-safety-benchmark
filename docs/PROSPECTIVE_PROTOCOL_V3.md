# Prospective protocol: Study V3

**Status:** draft, pre-collection  
**Protocol version:** `study-v3.0.0-alpha.1`  
**Behavioural data collected under this protocol:** none

Any result-changing amendment after the protocol freeze requires a numbered deviation record. No
main-study response may be regenerated because its content is inconvenient or difficult to score.

## Research questions

**RQ1. Presentation.** How do matched control, ambiguous, and fixed-belief presentations change
belief confirmation, harm enablement, proportionate support, and over-pathologising across 12 turns?

**RQ2. Model.** How do prespecified endpoints differ on the primary outcomes under the same scripts,
context condition, generation envelope, and collection window?

**RQ3. Context.** Does a standardised 24-message history alter response trajectories relative to
no preloaded history?

**RQ4. Time.** When do high-risk behaviours and protective responses first appear, persist,
escalate, and recover across the four trajectory phases?

**RQ5. Robustness.** In a secondary subset, how are results affected by deeper context, immediate
prompt re-anchoring, collection date, and API versus consumer-interface delivery?

RQ5 is not pooled into the primary RQ1–RQ4 estimates.

## Study stages

### Stage 0: development

Development uses mock responses and non-study prompts. It validates schemas, storage, blinding,
rater workflow, and failure recovery. Development records are permanently excluded from analysis.

### Stage 1: technical screening

All catalogue-eligible endpoints run six technical scripts, one per theme, under one context and
one repetition. Screening decides only whether an endpoint can be called reproducibly. The rule is:

1. exact endpoint remains listed;
2. text input/output and declared limits meet the protocol;
3. a stable provider can be pinned;
4. every screening slot completes without silent model substitution;
5. the endpoint meets the price ceiling;
6. the final panel retains four model families and two paid low-cost anchors.

Safety scores are not selection criteria. Screening prompts are not reused in confirmation.

### Stage 2: confirmatory study

The default profile includes six endpoints, 18 scenario cells, two contexts, and two repetitions.
This yields 432 conversations and 5,184 target responses before technical exclusions:

`6 models × 6 themes × 3 presentations × 2 contexts × 2 repetitions × 12 turns`.

If sample-size simulation supports a different design, the profile and rationale are frozen before
collection. Cost does not justify a post-outcome design change.

### Stage 3: robustness studies

Separate manifests cover:

- context depth at 0, 24, and 96 prior messages;
- immediate re-anchoring versus instructions only at conversation start;
- sentinel reruns on at least three dates;
- a manually captured interface subset using the same visible scripts;
- an adaptive stress-test track, if approved, with a logged user simulator and judge.

These studies answer different estimands and are not extra confirmatory replicates.

## Scenario design

Six families cover different mechanisms: monitoring, referential messages, AI attachment,
grandiose mission, somatic interpretation, and conspiracy-linked withdrawal. Each has control,
ambiguous, and fixed-belief variants. Within a family, setting, requested help, emotional intensity,
and length are matched; evidential certainty and belief framing are the intended manipulation.

Twelve turns form four phases: disclosure (1–3), interpretation (4–6), action pressure (7–9), and
recovery (10–12). Scripts require review for plausibility, stereotyping, leading language,
actionability, and matched-control validity before freeze.

## Model and provider policy

Confirmatory collection requires:

- an exact slug; no router or `latest` alias;
- provider pinning with fallback disabled;
- stored catalogue and endpoint snapshots;
- stored request hash, resolved ID, provider, time, finish reason, usage, latency, and response ID;
- a common visible completion envelope with field translation recorded;
- no research labels or desired behaviour in the target system prompt;
- reasoning traces excluded from behavioural data;
- fail-closed handling of mismatches, missing provider identity, truncation, and filtering.

Endpoint retirement after freeze is missing data, not authority to substitute another model.

## Outcomes

Primary axes remain separate: P1 belief confirmation, P2 harm enablement, P3 proportionate safety
support, P4 over-pathologising or unjustified crisis escalation, and P5 unhelpful refusal. Secondary
axes assess epistemic calibration, boundary integrity, autonomy, emotional attunement, and
constructive challenge. No total score is primary.

Trajectory outcomes include first onset, affected turns, longest run, phase-specific rate,
escalation after action pressure, and recovery after a corrective cue.

## Human annotation

Two raters independently score all confirmatory material in randomised blinded blocks. Agreement is
reported by axis before adjudication. A third reviewer adjudicates primary-axis disagreements. Raw
ratings and unadjudicated sensitivity analyses remain available. LLM judges are supplementary and
never overwrite human labels.

## Statistical analysis

The plan is frozen before collection. Primary analyses use cumulative-link or logistic mixed models
as appropriate, with declared fixed effects and scenario/script random effects. Observations are
clustered by conversation. Prespecified contrasts use Holm correction within each research-question
family and cluster bootstrap intervals.

If a model is singular or fails diagnostics, the registered fallback is a matched
conversation-level permutation or rank procedure. The method is not chosen by its p-value. Effect
sizes and confidence intervals are primary.

Transport errors, provider blocks, truncation, retirement, and unscorable content are distinct
states and are never safe zeroes. Sample size is set by simulation with clustering; turns are not
treated as independent.

## Release plan

The public release must rebuild every table and figure without model calls. It includes frozen
manifests, hashes, rubric and scenario versions, blinded analysis-ready rows, raw and adjudicated
ratings, technical exclusions, catalogue/provider snapshots, a locked environment, scripts, a data
dictionary, and provenance. If dialogue is withheld, the analysis table must still reproduce every
number.

## Ethics and scope

Synthetic prompts are not participants or care. The project still needs an ethics determination,
risk review, secure model-output handling, and rater-wellbeing procedure. Any future use of real
conversations requires a separate protocol, lawful data basis, privacy review, and access control.
