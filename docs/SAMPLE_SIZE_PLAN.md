# Sample-size and design-sensitivity plan

The repository now contains an executable planning simulation in `scripts/simulate_power.py`. It
does not claim that the study is powered, and it is not the final inferential model.

The simulation treats a model × scenario-family × context × repetition cell as the paired unit for
one presentation contrast. It generates binary turn outcomes with model, family, and conversation
random effects, aggregates within each 12-turn conversation, and applies a conservative familywise
threshold across the three planned presentation contrasts.

The assumptions are explicit in `config/study-v3/power.yaml`. In particular, the baseline event
rate and random-effect standard deviations are not estimates from Study V2. They are planning
values that require review by a statistician before freeze. The output is useful for identifying a
design that is plainly insensitive, not for certifying a final sample size.

Run:

```text
python scripts/simulate_power.py --output outputs/power_simulation.json
```

Before protocol freeze:

1. justify the baseline event rate and variance assumptions;
2. simulate ordinal P1 as well as a binary high-risk threshold;
3. examine differential technical missingness by model and condition;
4. check sensitivity to weaker within-family pairing;
5. have the final mixed-effects specification and fallback reviewed independently;
6. freeze the plan hash and generated output in the protocol bundle.

Turns are never counted as independent sample-size units.
