"""An end-to-end simulation of the experiment workflow, never empirical LLM data."""

from __future__ import annotations

import hashlib
import itertools
import json
import random
from pathlib import Path
from typing import Any

from psychosis_benchmark.adjudication import AdjudicationRecord, build_analysis_rows, raw_rater_rows
from psychosis_benchmark.analysis import analyse, trajectory_summary
from psychosis_benchmark.analysis_plan import load_analysis_plan
from psychosis_benchmark.annotation import RatingRecord, assert_packet_blinded, build_annotation_packet
from psychosis_benchmark.collection import collect_conversation
from psychosis_benchmark.contexts import load_context_histories
from psychosis_benchmark.design import load_study, write_manifest
from psychosis_benchmark.export import export_ledger
from psychosis_benchmark.provider import HttpResponse, OpenRouterClient
from psychosis_benchmark.ratings import PRIMARY_AXES, agreement_report
from psychosis_benchmark.schema import ManifestRow, Presentation


class SimulationTransport:
    """Return marked fixture text through the real provider parser and collector."""

    def __init__(self) -> None:
        self.calls = 0

    def send(self, url, *, headers, body, timeout) -> HttpResponse:
        payload = json.loads(body)
        self.calls += 1
        return HttpResponse(
            status_code=200,
            headers={"x-request-id": f"fixture-{self.calls}"},
            body=json.dumps(
                {
                    "id": f"fixture-{self.calls}",
                    "model": payload["model"],
                    "provider": "simulation",
                    "choices": [
                        {
                            "message": {
                                "content": "SIMULATION FIXTURE: this placeholder is not a model response."
                            },
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 100,
                        "completion_tokens": 12,
                        "total_tokens": 112,
                        "cost": 0.0,
                    },
                }
            ).encode(),
        )


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def _write_rows(path: Path, values) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        for value in values:
            handle.write(value.model_dump_json() + "\n")


def run_validation(root: Path, output: Path, *, models: int = 6, families: int = 6) -> dict[str, Any]:
    """Execute collection → evidence → blinding → ratings → analysis on marked fixtures."""

    if output.exists():
        raise ValueError("validation output already exists; use a new directory")
    output.mkdir(parents=True)
    config = root / "config" / "study-v3"
    study = load_study(config)
    plan = load_analysis_plan(config / "analysis_plan.yaml")
    histories = load_context_histories(config / "contexts")
    system = (config / "system_prompt.txt").read_text(encoding="utf-8")
    manifest = []
    selected_models = study.models.models[:models]
    selected_families = study.scenarios[:families]
    for model, family, presentation, context, repetition in itertools.product(
        selected_models,
        selected_families,
        ("control", "ambiguous", "fixed_belief"),
        ("no_history", "standard_history_24"),
        (1, 2),
    ):
        identity = f"{model.model_id}:{family.family_id}:{presentation}:{context}:{repetition}"
        manifest.append(
            ManifestRow(
                protocol_version=study.design.protocol_version,
                stage="development",
                run_id="simulation_" + hashlib.sha256(identity.encode()).hexdigest()[:24],
                scenario_family=family.family_id,
                script_id=family.variants[presentation].script_id,
                presentation=Presentation(presentation),
                model_id=model.model_id,
                model_tier=model.tier,
                context_condition=context,
                prior_message_count=study.design.contexts[context].prior_message_count,
                repetition=repetition,
                planned_turns=12,
                planned_seed=20261007 + repetition,
                execution_order=len(manifest) + 1,
            )
        )
    write_manifest(manifest, output / "manifest.csv")
    transport = SimulationTransport()
    client = OpenRouterClient("simulation-credential-not-a-real-key", transport=transport, clock=lambda: 0.0)
    source = []
    summaries = []
    for row in manifest:
        ledger = output / "ledgers" / f"{row.run_id}.jsonl"
        collect_conversation(
            study=study, row=row, histories=histories, system_prompt=system, client=client, ledger_path=ledger
        )
        items, summary = export_ledger(
            ledger, study=study, row=row, histories=histories, system_prompt=system
        )
        source.extend(items)
        summaries.append(summary)
    packet = build_annotation_packet(
        source,
        secret=b"SIMULATION_ONLY_NOT_A_SECRET_VALUE",
        rubric_version="simulation-rubric",
        seed=20261007,
    )
    assert_packet_blinded({"items": [item.model_dump() for item in packet.items]})
    _write_rows(output / "annotation_packet.jsonl", packet.items)
    _write_rows(output / "synthetic_blinding_key.jsonl", packet.key)
    ratings = []
    resolutions = []
    truth = {}
    generator = random.Random(20261007)
    # Draw a known presentation effect. These labels are fixture parameters,
    # unrelated to the placeholder text or performance of named endpoints.
    for key in packet.key:
        fixed = key.presentation == "fixed_belief"
        scores = {
            "P1": int(generator.random() < (0.65 if fixed else 0.15)),
            "P2": int(generator.random() < (0.45 if fixed else 0.10)) if 7 <= key.turn <= 9 else "NA",
            "P3": 1 + int(generator.random() < (0.55 if fixed else 0.30)) if key.turn >= 7 else "NA",
            "P4": int(generator.random() < (0.40 if key.presentation == "ambiguous" else 0.10)),
            "P5": int(generator.random() < 0.10),
            **{axis: 1 for axis in ("S1", "S2", "S3", "S4", "S5")},
        }
        truth[key.blind_item_id] = scores
        for rater in ("rater_simulation_a", "rater_simulation_b"):
            values = dict(scores)
            if rater.endswith("b"):
                for axis in PRIMARY_AXES:
                    if isinstance(values[axis], int) and generator.random() < 0.06:
                        values[axis] = (values[axis] + 1) % 3
                        resolutions.append(
                            AdjudicationRecord(
                                blind_item_id=key.blind_item_id,
                                axis=axis,
                                score=scores[axis],
                                reviewer_code="reviewer_simulation",
                                rationale="Simulation resolves to its known generating score; "
                                "no human adjudication occurred.",
                            )
                        )
            ratings.append(
                RatingRecord(
                    blind_item_id=key.blind_item_id,
                    rater_code=rater,
                    rubric_version="simulation-rubric",
                    rating_status="scored",
                    **values,
                )
            )
    _write_rows(output / "synthetic_raw_ratings.jsonl", ratings)
    _write_rows(output / "synthetic_adjudications.jsonl", resolutions)
    agreement = agreement_report(ratings)
    _write_json(output / "synthetic_agreement.json", agreement)
    rows = build_analysis_rows(list(packet.key), ratings, resolutions, provenance="synthetic_fixture")
    _write_rows(output / "analysis_rows.jsonl", rows)
    result = analyse(manifest, rows, plan, allow_synthetic=True)
    result["trajectories"] = trajectory_summary(rows)
    _write_json(output / "analysis.json", result)
    sensitivities = {}
    for rater in ("rater_simulation_a", "rater_simulation_b"):
        raw = raw_rater_rows(list(packet.key), ratings, rater)
        raw = [row.model_copy(update={"provenance": "synthetic_fixture"}) for row in raw]
        sensitivities[rater] = analyse(manifest, raw, plan, allow_synthetic=True)
    _write_json(output / "raw_rater_sensitivities.json", sensitivities)
    report = {
        "data_origin": "synthetic_fixture",
        "clinical_or_model_performance_claim": False,
        "conversations": len(manifest),
        "responses": len(rows),
        "verified_ledgers": len(summaries),
        "synthetic_raw_ratings": len(ratings),
        "synthetic_adjudications": len(resolutions),
        "annotation_blocks": len({item.block_id for item in packet.items}),
        "all_ledgers_complete": all(item["status"] == "completed" for item in summaries),
        "blinding_audit_passed": True,
        "analysis_input_sha256": hashlib.sha256((output / "analysis_rows.jsonl").read_bytes()).hexdigest(),
        "outcomes": result["outcomes"],
        "raw_rater_sensitivity_completed": True,
    }
    _write_json(output / "validation_report.json", report)
    return report
