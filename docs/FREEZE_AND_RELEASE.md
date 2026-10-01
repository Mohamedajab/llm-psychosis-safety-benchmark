# Protocol freeze and evidence release

`scripts/freeze_protocol.py` converts the readiness checklist into an executable gate. It hashes
the result-changing configuration, scenarios, context histories, system prompt, governance
records, protocol documents, collection code, analysis-planning code, and generated power output.

The command is expected to fail in the draft repository:

```text
python scripts/freeze_protocol.py
```

Use `--preview` to inspect the proposed file manifest and bundle hash without claiming a freeze.
`--write protocol/study-v3.0.0/bundle.json` is allowed only when every blocker is resolved.

Pending governance YAML files are templates, not evidence of approval. Their status changes require
the corresponding external review or determination. The repository must never set them to approved
merely to make the command pass.

Each live conversation writes a separate hash-linked JSONL ledger. The ledger records the manifest
row, study and prompt hashes, request hashes, attempt outcomes, visible response text, resolved model
and provider metadata, finish reasons, usage, latency, and terminal status. It refuses secret-like
fields and rejects appends after a terminal event.

Verify a ledger with:

```text
python scripts/verify_ledger.py data/raw/screening/<run-id>.jsonl
```

Before public release, build an analysis-ready table from verified ledgers. Preserve raw ledgers in
controlled storage, publish their final hashes, and keep blinding maps and rater identities outside
Git. A table or figure that cannot be rebuilt from the release bundle must not appear in the paper.
