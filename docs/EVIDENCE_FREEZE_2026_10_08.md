# Exploratory evidence freeze: 8 October 2026

The sized exploration is closed. Its final evidence was copied under an exclusive
collector lock and audited without replacing failed attempts or accepted replies.
The original batch was left unchanged. This is a post-collection integrity record,
not preregistration or approval of the study's constructs.

## What was retained

- All 396 terminal conversation ledgers: 359 completed and 37 failed.
- 4,895 stored replies out of 5,184 planned, including nine truncated outputs.
- 289 missing replies; 27 empty-response failures, nine truncation failures and one HTTP 424 failure.
- Frozen inputs, request/response evidence, progress records and budget evidence.
- Recorded response cost of $0.61345927 and conservative committed budget of $0.71758577.
- Thirty attempts with uncertain delivery costs. The recorded response cost is not a billing reconciliation.

No human ratings exist. Do not infer model safety rankings from completion rates.
Do not restart this batch to fill its missing cells: any new collection needs a
separate batch and an explicit amendment.

## Private snapshot and public receipt

The private snapshot is `data/private/frozen/sized-exploration-2026-10-08/`.
Its matching archive is `data/private/frozen/sized-exploration-2026-10-08.zip`.
Both remain excluded from Git. Neither raw model replies nor identity/linkage data
should be uploaded to the public repository or the scenario-review website.

The public receipt contains aggregates and hashes only:
[`outputs/evidence_freeze_2026-10-08.json`](../outputs/evidence_freeze_2026-10-08.json).

Content-root SHA-256:
`3c1e5e19c92323d3f0c2030b5655cf15f73bcfc5f8d5c1374e8f5d4a5e563158`

Archive SHA-256:
`d8e301e3f5d4c6723e90eb4ad0ad2ce8940ae3126e7638cc69b46467381ea064`

All 407 snapshot files and the archive contents passed verification. Files are
marked read-only to discourage accidental edits. This is not tamper-proof or
write-once storage; the separately retained receipt detects changes when verified.
Keep a second private backup before moving or removing any source evidence.

```text
python scripts/freeze_exploratory_evidence.py --snapshot-dir data/private/frozen/sized-exploration-2026-10-08 --public-receipt outputs/evidence_freeze_2026-10-08.json --verify
```

## Review stage

Independent review starts with the synthetic scenarios and draft scoring rubric,
not model-reply ratings. Reviewer classification must not reveal intended scenario
conditions. Keep reviewer contact records separate from pseudonymous review records.
Feedback is evidence for revision; submission does not automatically constitute
expert approval, ethical clearance or successful calibration.

Any edits to scenarios or rubric after review need new version identifiers and
re-review. The frozen exploratory data remains tied to the versions used at collection.
