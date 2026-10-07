# Longer trajectories and broader scenario coverage

This draft responds to a request for a stronger publishable study, not for more favourable findings.
All scenarios are synthetic author-written candidates pending clinical and lived-experience review.
The expansion is an overlay so the earlier pilot retains its original configuration and hashes.

## What changed

The sampling frame contains six free and ten inexpensive paid candidates. The proposed main panel
contains eight endpoints, at least five paid, selected by technical availability and diversity.
Four new mechanisms broaden the original six families: unsupported responsibility for distant harm,
thought privacy, familiar-person substitution, and perceived external control. Related mechanisms
may remain dependent; ten files alone do not establish ten independent blocks.

The 12-turn core preserves the original disclosure, interpretation, action-pressure, and recovery
phases. A separate 24-turn track retains the first twelve prompts exactly, then adds recurrence
(13–18) and sustained recovery (19–24). Continuations are matched by presentation and share a draft
template with family-specific recurrence cues. They are not additional independent stimuli.

The long track asks whether a boundary persists when a concern returns, whether the response changes
under renewed confirmation pressure, and whether recovery remains proportionate. These constructs
need frozen human-rating masks and validation before inferential claims. Current primary analysis
deliberately rejects 24-turn manifests; the exploratory track is never pooled into the four core tests.

## Literature and scope

[Sterna and colleagues' longitudinal study](https://arxiv.org/abs/2608.13017) used a thirty-message
script, fifteen models, and four evaluators, emphasising recognition timing and stability. Longer
interaction is therefore not a novelty claim. This expansion instead proposes multiple matched
presentations and scenario mechanisms, accumulated target-model responses, reason-coded technical
missingness, and an auditable human-rating path. It runs in one session, not thirty calendar days;
turn count cannot substitute for elapsed time or clinical deterioration.

The long pilot runs five cheap paid candidates on one family and three presentations. Its planned
360 responses test transport, context accumulation, truncation, and evidence export. It is not a
complete crossed research sample and has no human safety scores. Failed or rate-limited endpoints
remain in the denominator. No response is regenerated because of its content.

## Commands

```text
python scripts/run_longitudinal.py --models amazon/nova-lite-v1 openai/gpt-4.1-nano --families ai_attachment --horizon 24 --output-dir data/raw/long-preview
python scripts/compare_designs.py --output outputs/design-sensitivity-new.json
python -m streamlit run streamlit_app.py
```

The first command previews. Live collection requires `--live` and a credential in the environment
or stdin. Routing caps input at $0.10 and output at $0.40 per million tokens, with fallback disabled.
Planning estimates are not invoices. Context histories, requests, complete study snapshots, model
metadata, and terminal evidence hashes remain available locally. Public audits contain metadata,
not dialogue or credentials.

Before a main study: review the scenarios and their pairing, validate the rubric and long-track
constructs, assess clustering and power, budget human annotation, pin providers, obtain an ethics
determination, calibrate raters, and register the final design. A subsequent
[introduction and methods draft](../paper/manuscript.tex) documents the exploratory work;
it contains no behavioural findings and does not satisfy those readiness requirements.
