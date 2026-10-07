# Sample-size and design-sensitivity plan

The corrected simulation in `scripts/simulate_power.py` uses matched conversation differences and
the same scenario-family block sign-flip test as the draft analysis. It preserves shared model and
family variation and includes family-specific effect variation. The first Holm threshold is
0.05 / 4, not a three-contrast rule.

Six nonzero blocks have a minimum two-sided p of 0.03125. Therefore the original six-family design
cannot reject the first hypothesis at 0.0125, regardless of extra turns or repetitions. Its
2,000-iteration output records zero detection under every tested effect. This is a test-resolution
constraint, not evidence that model behaviours are identical.

`scripts/compare_designs.py` compares the original draft, a longer-only version, a broader core,
and a long exploratory track. Its preliminary comparison uses 250 simulations per effect, a null
setting, and three nonzero effects. The broader core proposes eight models, ten families, two
contexts, three repetitions, and twelve turns. Results depend on assumed variance and a binary
proxy; they are not joint four-axis ordinal-outcome power.

The assumptions are explicit in `config/study-v3/power.yaml`. In particular, the baseline event
rate and random-effect standard deviations are not estimates from Study V2. They are planning
values that require review by a statistician before freeze. The output is useful for identifying a
design that is plainly insensitive, not for certifying a final sample size.

Run:

```text
python scripts/simulate_power.py --output outputs/power_simulation.json
python scripts/compare_designs.py --simulations 1000 --output outputs/design-sensitivity-new.json
```

Before protocol freeze:

1. justify the baseline event rate and variance assumptions;
2. simulate ordinal P1 as well as a binary high-risk threshold;
3. examine differential technical missingness by model and condition;
4. check sensitivity to weaker within-family pairing;
5. review the family-block assumptions, ordinal estimand, and crossed interval independently;
6. freeze the plan hash and generated output in the protocol bundle.

Turns are never counted as independent sample-size units.

If related families share a dependence block, count that block instead of treating new files as
independent samples. The proposed core has 17,280 responses: at one minute per response per rater,
two raters need 576 hours before training and adjudication. A full 24-turn factorial doubles that.
Human annotation capacity, not just API cost, must constrain the reviewed design before unblinding.
