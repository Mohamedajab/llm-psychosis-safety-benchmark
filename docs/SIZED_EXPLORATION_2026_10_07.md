# Dataset-size amendment: a feasible exploratory collection

Decision date: 7 October 2026. Status: exploratory, not preregistered, not confirmatory.
This replaces the proposed *full collection*, not the earlier pilot evidence or the original MSc repository.
No manuscript or human-rated safety finding is produced by this amendment.

## Why reduce the grid?

There is no defensible universal number of LLM responses for this research question.
Turns from one conversation are dependent. Many presentations of a single authored family
do not create many independent families. Collection must also match the annotation capacity.
[TRIPOD-LLM](https://pmc.ncbi.nlm.nih.gov/articles/PMC12104976/) calls for transparent
evaluation design, outcomes, and assessor reporting; it does not supply a minimum turn count.
[Arnaout et al.](https://aclanthology.org/2026.acl-long.347/) argue for evaluation grounded
in relevant clinical constructs and stakeholder participation. More unreviewed synthetic
dialogue does not resolve those validity gaps. These sources motivate the decision;
they do **not** prescribe our chosen numbers.

The unreduced eight-model, ten-family, three-presentation, two-context, three-repetition
grid contains 17,280 twelve-turn responses and 34,560 twenty-four-turn responses: 51,840.
Double-rating each at an optimistic one minute per response would take 1,728 hours,
before training, transcript reading, adjudication, or breaks.

## Selected collection

| Track | Models | Families | Presentations | Prior contexts | Samples/cell | Turns | Conversations | Responses |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Core | 6 | 10 | 3 | 2 | 1 | 12 | 360 | 4,320 |
| Long extension | 6 | 2 | 3 | 1 | 1 | 24 | 36 | 864 |
| Total | | | | | | | 396 | 5,184 |

This is a 90% workload reduction. Full double annotation still implies about 172.8 hours
under the same optimistic assumption. Any further annotation subsampling must be
specified separately, blinded and balanced, before inspecting scored outcomes; it is
not silently assumed to cover the complete response set.

The panel contains GPT OSS 20B, Mistral Nemo, Gemini 2.5 Flash Lite, Amazon Nova Lite v1,
GPT 4.1 Nano, and free Nemotron 3.5 Lightning. The first five completed all six-family
four-turn technical pilots. The free general-purpose Lightning endpoint completed its
technical pilot. Selection uses technical completion and the existing cost limits,
not safety scores (none exist). This availability-conditioned panel is not representative
of all models, and it has two OpenAI families. Provider routing remains unpinned and is
recorded per request: these are exploratory endpoint comparisons.

All ten draft families enter the core. The long track is limited to `ai_attachment`
and `monitoring`, chosen to cover AI-specific dependence and a non-AI persecutory theme,
not because of observed safety effects. It uses no prior-history condition. Its first
twelve prompts match the corresponding core script, but conversations are independently
collected and must not be merged as if they were the same sampled trajectory.

## What the sensitivity experiment establishes—and does not

`python scripts/size_exploration.py --simulations 500 --output NEW_PATH.json` compares
five core designs under two assumed family-slope standard deviations. The saved result
is `outputs/sized_exploration_sensitivity.json`. The simulation is a binary proxy,
uses four effect settings and the first four-contrast Holm hurdle, and does not model
the joint ordinal outcomes, provider drift, annotation error, or missingness.

At a log-odds effect of 0.40, the selected core's detection estimate is 0.418 with
family-slope SD 0.25 and 0.198 with SD 0.50. At effect 0.60, it is 0.822 and 0.488.
These are assumed-variance planning outputs, **not a claim of 80% power**. The larger
17,280-response core also deteriorates from 0.794 to 0.310 at effect 0.40 when slope
variation increases. This is a reason to report sensitivity and effect uncertainty,
not to increase responses until a preferred significance threshold is crossed.

Six family blocks cannot attain the draft first Holm threshold: their minimum
two-sided sign-flip p is 0.03125, versus 0.0125. Ten blocks have finer resolution
(minimum 0.001953125), but independent, symmetric family differences remain unverified
assumptions. Authored thematic families may share language or structure. Statistical
resolution alone does not validate the inferential procedure. Treat tests as exploratory
and prefer descriptive paired contrasts, uncertainty, and failure denominators until
independent statistical and construct review is complete.

One sampled generation per cell cannot estimate within-cell stochastic variance or
justify stable fine-grained model rankings. A future confirmatory design will need an
empirically informed variance plan, external review, new samples, and preregistration.

## Collection safeguards

`scripts/run_sized_exploration.py` snapshots exact scripts, both study bundles, contexts,
system prompt, all 396 manifest rows, and the plan before requests. A recorded input
hash protects resumes. Existing pilots are neither overwritten nor pooled into this grid.
All endpoints share a 4,096-token output cap (including any model-internal reasoning
that consumes the provider's completion budget); the earlier pilots used 2,048, so they
are not interchangeable. Temperature, top-p, and declared seed support are preserved.

A local SQLite budget journal reserves a conservative per-request estimate before
sending, atomically across workers, and replaces it with returned cost when known.
Ambiguous transport deliveries retain the upper estimate. Unknown paid costs or costs
exceeding the reservation pause collection. The default cap is $5 and cannot be raised
by `--resume`. Byte-based token estimates are conservative estimates, not a formal
guarantee of external billing; discrepancies stop further requests. Paid routing caps
remain $0.10 input and $0.40 output per million tokens, with no fallback models.

Successful responses are immutable. Interrupted runs reconstruct and validate previous
request hashes and transcripts. A process interrupted after sending but before recording
the result may have an unknown remote delivery; retrying that turn could incur a second
charge. The first attempt remains explicitly documented and conservatively budgeted.
Terminal truncated/filtered/error outputs are retained, not regenerated until a favourable
answer appears. Transient failures use bounded backoff and
[honour Retry-After](https://openrouter.ai/docs/api_reference/limits); long delays or
exhausted session retries pause that endpoint rather than changing the model.

For an operator checkpoint, create a file named `STOP` in the batch directory. It is
checked before requests; remove it before resuming. Resume with the same output directory,
`--live --resume --api-key-stdin --budget-usd 5`, supplying the key securely through stdin.
Do not put keys in files committed to Git or in command-line arguments. A process-owner
lock prevents two collectors from using the same batch simultaneously.

The dashboard reads `progress.json` every 15 seconds and verifies a selected dialogue's
hash chain. Raw responses, budget journal, and full transcripts remain Git-ignored.
For a non-mutating audit of hash chains and every reconstructed request transcript:

```text
python scripts/audit_sized_exploration.py --batch-dir data/raw/BATCH --output outputs/NEW_AUDIT.json
```

An audit taken during collection is an explicitly time-stamped snapshot, not a final
completion report. Do not replace an earlier audit with later counts.
This collection is not clinical validation. Expert/lived-experience review, an ethics
determination, rater calibration and reliability, appropriately scoped inference, and
publication consent/data-release decisions still remain.
