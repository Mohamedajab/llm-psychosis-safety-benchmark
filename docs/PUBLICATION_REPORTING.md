# Publication reporting map

This study is an offline synthetic model audit, not a trial, diagnostic-accuracy study, prediction
model, or live clinical evaluation. Reporting standards from those designs must not be claimed as if
they directly certify this work.

The manuscript should nevertheless map its methods and supplement to the applicable evaluation
items in [TRIPOD-LLM](https://www.nature.com/articles/s41591-024-03425-5): exact model and access
date, task and intended use, prompts and interface, sampling, evaluator characteristics, outcome
definitions, statistical methods, missing data, reproducibility, limitations, funding, conflicts,
and data/code availability. The completed checklist and page references belong in the supplement.

For the human evaluation, report evaluator recruitment and expertise, training material, calibration
examples, item allocation, blinding, workload, raw agreement, adjudication, and compensation. The
[QUEST framework](https://www.nature.com/articles/s41746-024-01258-7) is a useful methodological
cross-check, especially because its review found inconsistent reporting of blinding and evaluator
training in health-LLM studies.

[DECIDE-AI](https://www.bmj.com/content/377/bmj-2022-070904) is out of scope because no model is
being used in live care. It may inform the limitations and future-work section, but the paper must
not describe Study V3 as a clinical evaluation. Likewise, later external validation with real users
would require a separate protocol.

## Minimum manuscript evidence

| Claim area | Evidence that must exist before drafting results |
|---|---|
| Model identity | exact slug, provider pin, resolved ID, catalogue snapshot, access window |
| Experimental unit | frozen conversation manifest and explanation of within-conversation turns |
| Construct validity | independent clinical, lived-experience, and methods review record |
| Human ratings | blinded packets, two raw ratings, pre-adjudication agreement, adjudication log |
| Confirmatory inference | registered estimands, diagnostics, multiplicity, effect sizes, intervals |
| Missingness | reason-coded table and registered sensitivity analyses |
| Reproducibility | clean-clone rebuild of every table and figure without model calls |
| Scope | explicit separation of synthetic behaviour from clinical safety or patient outcomes |

## Writing controls

Every result paragraph should state the estimand, denominator, effect size, interval, and whether the
analysis was confirmatory. Avoid promotional adjectives, model “winner” language, unsupported causal
verbs, and conclusions based only on p-values. Report null and adverse findings with the same detail.
The paper should identify exploratory analyses at first mention and preserve the full model panel,
including failures and missing endpoints.
