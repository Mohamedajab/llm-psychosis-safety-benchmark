# Benchmark gap analysis

This note records the design audit used to define Study V3. It is not a literature review and it
does not claim that repository documentation has the evidential status of a peer-reviewed paper.
Sources were checked on 2026-09-30. Repository commit hashes make the comparison repeatable.

## Starting point: Study V2

The MSc repository has several strengths worth preserving: a balanced factorial design, fixed
multi-turn scripts, exact endpoint slugs, immutable manifests, append-only recovery records,
blinded annotation, explicit N/A handling, conversation-level inference, and strong offline
validation. It also reports its limitations plainly.

The main constraints are:

- two target endpoints from two model families;
- three scenario themes and six turns per conversation;
- one primary human annotator;
- two repetitions;
- one standardised context prefix rather than a context-depth experiment;
- API-only collection;
- private evidence required to reproduce the reported numerical results;
- no prospective control for model drift across collection dates;
- no primary measure of over-pathologising or unhelpful over-refusal.

These are limits on inference, not defects that can be repaired after seeing the results. Study V3
therefore starts a new prospective protocol.

## External comparison

| Project | Useful contribution | What it does not replace | V3 response |
|---|---|---|---|
| [Psychosis-Bench](https://github.com/w-is-h/psychosis-bench) at `73966f9` | Sixteen twelve-turn cases, explicit/implicit variants, eight models, DCS/HES/SIS outcomes | Its public runner is lighter on immutable provider provenance, paired controls, and human reliability | Retain stronger provenance; expand turns, themes, and model coverage |
| [Spiral-Bench](https://github.com/sam-paech/spiral-bench) at `35411a0` | Generated roleplay, protective/risky labels, temporal trajectories, and interface auditing in the accompanying work | A generated user adds another model to the causal chain; automated judging is not blinded human scoring | Keep the confirmatory track scripted; isolate adaptive stress testing and interface validation |
| [DelusionEval](https://github.com/jlcmoore/llm-delusion-eval) at `8be51db` and [preprint](https://arxiv.org/abs/2608.05004) | 589 unique real-world histories, long-context windows, controlled-access data, and evidence that prior context changes failure rates | Window replay does not test a target model's own accumulating replies, and controlled data cannot provide a public synthetic core | Add context depth while retaining a public synthetic confirmatory set; leave real-world validation to a separate protocol |
| [MHSafeEval](https://github.com/suhyun565/MHSafeEval) at `9889223` and [preprint](https://arxiv.org/abs/2604.17730) | Adaptive attacks, a role-aware harm taxonomy, and clinician-reviewed severity ladders | Adaptive search estimates attack susceptibility, not behaviour under a fixed comparable stimulus | Split fixed and adaptive estimands; do not let a judge steer the primary track |
| [Conversation-depth benchmark](https://github.com/markkalinich/conversation-trajectory-multiturn-benchmark) at `9e886f5` | Preregistration, 49 models, eight licensed clinicians, depth to 1,500 turns, re-anchoring, and a dialogue-free reproduction bundle | It studies suicidal-ideation classification rather than supportive conversation | Add depth and re-anchoring factors, rater blocks, broader models, and a public analysis-ready release plan |
| [LLM Spirals of Delusion](https://arxiv.org/abs/2604.06188) | API/interface differences, trajectory heterogeneity, and drift at the same endpoint | A small interface audit cannot support broad model-family claims | Treat interface validity and drift as named secondary studies |
| [MentalBench-100k analysis](https://aclanthology.org/2026.eacl-long.180/) | Shows that LLM-judge reliability in mental-health evaluation is construct-specific | More judges do not remove shared bias or establish clinical validity | Keep human ratings primary and report judge agreement by axis |

## Missing estimands

Existing work often collapses different questions into one score. V3 keeps four apart:

1. **Fixed-stimulus behaviour:** what does an endpoint do under the same scripted trajectory?
2. **Context susceptibility:** what changes when prior conversational material is added or the task
   is re-anchored?
3. **Adaptive attack susceptibility:** how easily can a user simulator find a harmful trajectory?
4. **Deployment-surface validity:** does the API resemble a consumer interface with the same model
   label?

Only the first is confirmatory by default. The others need separate manifests and claims.

## Design changes justified by the audit

### Broader but controlled model comparison

Eleven exact endpoints form the screening panel without an opaque free-model router. The smaller
confirmatory panel is selected by a frozen rule based on availability, provider stability, model
family, and budget. Observed safety scores cannot select confirmatory models.

### Longer, phased trajectories

Each scenario has 12 turns divided into disclosure, interpretation, action pressure, and recovery
phases. Phase labels are metadata and are never sent to the model. This supports onset,
persistence, escalation, and recovery measures without replacing scripts with a user simulator.

### Paired controls and over-refusal

Controls use the same practical setting and emotional stakes without an unsupported belief.
Responses can fail through confirmation and enablement, but also through pathologising an ordinary
concern, refusing benign help, or escalating to crisis language without evidence.

### Human reliability before model ranking

Two blinded raters score all confirmatory material. A third reviewer adjudicates primary-axis
disagreements after agreement is calculated. Failure to meet calibration thresholds delays the
freeze instead of being hidden by consensus labels.

### Reproducible evidence without sensitive dialogue

The release target is an analysis-ready table with blinded response IDs, factors, raw and
adjudicated ratings, technical metadata, and hashes. If dialogue is withheld, every reported number
must still rebuild from the public table.

## What V3 does not claim

The project does not estimate incidence of harm in users, diagnose psychosis, certify a model as
safe, or determine whether an LLM caused a person's symptoms. It measures response behaviour under
specified synthetic conditions. External validity must be tested, not implied.
