# Operator guide

The default workflow is offline. No command calls a target model unless `scripts/collect.py` is
given `--live` and an API key is present.

## 1. Validate the design

```text
python scripts/benchmark.py validate
python scripts/check_live_catalogue.py
python -m pytest -q
python -m ruff check src scripts tests
```

The live catalogue check is diagnostic. It never rewrites the recorded snapshot. A changed price,
context limit, completion limit, modality, or missing endpoint requires a reviewed configuration
amendment rather than an automatic update.

## 2. Generate the screening manifest

```text
python scripts/benchmark.py manifest \
  --profile screening \
  --output outputs/screening.csv
```

The current screening profile has 66 conversations and 264 target responses. Execution order is
deterministic. Regenerating the same profile must produce the same rows.

## 3. Preview a run

Choose a `run_id` from the manifest and run:

```text
python scripts/collect.py \
  --profile screening \
  --manifest outputs/screening.csv \
  --run-id <run-id>
```

Preview prints the exact model, context, turn count, provider pin, message count, and first request
hash. It omits prompt text and creates no evidence file.

## 4. Live screening

Live calls require an explicit flag, an environment variable, and a unique ledger path:

```text
python scripts/collect.py \
  --profile screening \
  --manifest outputs/screening.csv \
  --run-id <run-id> \
  --ledger data/raw/screening/<run-id>.jsonl \
  --live
```

`OPENROUTER_API_KEY` is read from the environment and is never written to the ledger. The client
uses the exact slug, disables fallback, requires declared request parameters, records a request
hash for every attempt, and rejects resolved-model mismatches. Confirmatory calls additionally
require a frozen protocol and a provider-pinned eligible model.

One process owns one ledger. An existing ledger cannot be overwritten or resumed by the current
collector. A future resume implementation must verify the complete hash chain and reconstruct the
accepted transcript before making another request.

## 5. Verify evidence

```text
python scripts/verify_ledger.py data/raw/screening/<run-id>.jsonl
```

A failed request and a truncated response are retained. Neither becomes a behavioural zero. A
terminal ledger refuses further events.

## 6. Plan and freeze

```text
python scripts/simulate_power.py --output outputs/power_simulation.json
python scripts/freeze_protocol.py --preview
python scripts/freeze_protocol.py
```

The final command should fail during development. Resolve its blockers through the named reviews;
do not change status fields merely to make the check pass. Once all evidence exists, write the
bundle with:

```text
python scripts/freeze_protocol.py --write protocol/study-v3.0.0/bundle.json
```

## 7. Prepare blinded annotation

First transform verified ledgers into source-item JSONL that satisfies the strict
`SourceAnnotationItem` contract. Then set a secret of at least 32 bytes in
`BENCHMARK_BLINDING_SECRET` and run:

```text
python scripts/prepare_annotation.py \
  --input data/private/source-items.jsonl \
  --rater-packet data/annotation_packets/study-v3.jsonl \
  --private-key data/blinding_maps/study-v3-key.jsonl \
  --rubric-version psychosis-response-rubric-v3.0.0-alpha.1 \
  --seed 20261002
```

The command refuses to overwrite files. Give raters only the packet. Keep the secret and private
key from raters, version control, and anyone fitting the locked analysis before ratings close.

After both raters submit strict `RatingRecord` JSONL files, calculate agreement before adjudication:

```text
python scripts/report_agreement.py \
  data/private/ratings-rater-a.jsonl \
  data/private/ratings-rater-b.jsonl \
  --output outputs/pre-adjudication-agreement.json
```

This reports exact agreement, linearly weighted Cohen kappa, numeric-pair counts, and separate N/A
decision agreement for P2 and P3. It fails on duplicate or incomplete pairs.

## Current boundary

The collector is intentionally single-run and sequential. The repository can build annotation
blocks and agreement reports, but it does not yet schedule the whole manifest or fit the proposed
mixed-effects models. It will not publish a leaderboard: model ranking is secondary and cannot
replace the registered presentation and context estimands.
