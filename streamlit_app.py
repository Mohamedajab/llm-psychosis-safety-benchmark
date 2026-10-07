"""Read-only research viewer. No API calls, scoring automation, or secret entry fields."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from psychosis_benchmark.collection import find_script  # noqa: E402
from psychosis_benchmark.design import load_study  # noqa: E402
from psychosis_benchmark.evidence import read_verified_events  # noqa: E402
from psychosis_benchmark.expansion import load_expanded_study  # noqa: E402
from psychosis_benchmark.protocol import freeze_blockers  # noqa: E402
from psychosis_benchmark.schema import StudyBundle  # noqa: E402


def read_report(name: str) -> dict:
    path = ROOT / "outputs" / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


st.set_page_config(page_title="Psychosis Safety · Research Lab", page_icon="◷", layout="wide")
st.title("Psychosis Safety · Research Lab")
st.caption("Study V3 successor · Mohamed Ajab · Evidence before conclusions")
st.warning(
    "Research prototype. No human-rated safety findings, clinical validity, or safe-model ranking yet."
)
st.sidebar.title("Research workspace")
st.sidebar.markdown("[GitHub repository](https://github.com/Mohamedajab/llm-psychosis-safety-benchmark)")
st.sidebar.caption("Read-only local viewer. It never calls a model or accepts an API key.")
if st.sidebar.button("Refresh recorded evidence"):
    st.rerun()

study = load_expanded_study(ROOT)
screen = read_report("live_screening_2026-10-07.json")
long = read_report("live_longitudinal_2026-10-07.json")
tabs = st.tabs(["Evidence", "Model panel", "Design explorer", "Conversations", "Publication gates"])


@st.fragment(run_every="15s")
def collection_progress():
    path = ROOT / "data/raw/live-sized-exploration-2026-10-07/progress.json"
    st.subheader("Sized exploration · target 5,184 new responses")
    st.caption("Six models: five inexpensive paid and one free. Ten families, plus a narrow 24-turn track.")
    if path.exists():
        progress = json.loads(path.read_text(encoding="utf-8"))
        metrics = st.columns(3)
        metrics[0].metric("Stored / target", f"{progress['stored_responses']:,} / 5,184")
        metrics[1].metric("Completed conversations", f"{progress['completed_conversations']} / 396")
        metrics[2].metric("Recorded API cost / cap", f"${progress['budget']['recorded_cost_usd']:.3f} / $5")
        st.progress(min(progress["stored_responses"] / 5184, 1.0))
        st.caption(f"State: {progress['status']} · Updated UTC: {progress['updated_at_utc']}")
        st.dataframe(pd.DataFrame(progress["models"]), hide_index=True, width="stretch")
        st.caption("Stored does not mean complete or safe. No human labels. Refreshes every 15 seconds.")
        if progress["catalogue_errors"]:
            st.warning("Catalogue drift prevents some calls: " + "; ".join(progress["catalogue_errors"]))
    else:
        st.info("The reduced plan is prepared; live collection has not started on this checkout.")


with tabs[0]:
    collection_progress()
    st.subheader("Live technical pilot")
    st.caption(
        "Actual API records. Stored responses include partial or truncated outputs; they are not ratings."
    )
    if screen:
        metrics = st.columns(4)
        metrics[0].metric("Paid endpoints responding", screen["paid_models_with_accepted_responses"])
        metrics[1].metric("Candidate endpoints", screen["planned_models"])
        metrics[2].metric(
            "Completed / planned", f"{screen['completed_conversations']} / {screen['planned_conversations']}"
        )
        metrics[3].metric("Stored responses", screen["accepted_responses"])
        table = [
            {
                "Model": row["model_id"],
                "Tier": row["tier"],
                "Completed": row["completed_conversations"],
                "Planned": row["planned_conversations"],
                "Stored responses": row["accepted_responses"],
                "Failures": ", ".join(row["failure_reasons"]) or "—",
            }
            for row in screen["models"]
        ]
        st.dataframe(pd.DataFrame(table), hide_index=True, width="stretch")
        st.caption(
            "Completion is an availability measure, not a measure of safety. Free and paid coverage differs."
        )
    st.subheader("24-turn exploratory pilot")
    if long:
        st.write(
            f"{long['completed_conversations']} of {long['planned_conversations']} conversations completed; "
            f"{long['accepted_responses']} responses stored. No safety labels collected."
        )
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        k: row[k]
                        for k in (
                            "model_id",
                            "completed_conversations",
                            "planned_conversations",
                            "accepted_responses",
                        )
                    }
                    for row in long["models"]
                ]
            ),
            hide_index=True,
            width="stretch",
        )
    else:
        st.info("Collection or evidence audit is in progress. Refresh after the public audit is written.")
    st.subheader("Software validation — simulated, not model evidence")
    fixture = read_report("validation_summary.json")
    if fixture:
        st.write(
            f"{fixture['conversations']} simulated conversations / "
            f"{fixture['responses']} simulated responses "
            "passed collection, evidence verification, blinding, rating resolution, and analysis."
        )
    with st.expander("Inspect public technical audit"):
        st.json(screen)

with tabs[1]:
    st.subheader("Six free + ten inexpensive paid candidates")
    tier = st.radio("Endpoint tier", ["All", "Free", "Paid"], horizontal=True)
    panel = [
        {
            "Model": model.model_id,
            "Family": model.family,
            "Organisation": model.organisation,
            "Tier": model.tier.value,
            "Input $ / 1M": model.prompt_usd_per_million,
            "Output $ / 1M": model.completion_usd_per_million,
            "Provider frozen": bool(model.provider_pin),
        }
        for model in study.models.models
        if tier == "All" or (tier == "Free") == (model.tier.value == "free")
    ]
    st.dataframe(pd.DataFrame(panel), hide_index=True, width="stretch")
    st.caption(
        "Recorded catalogue prices, not invoices or guarantees. Live preflight can reject drifted endpoints."
    )

with tabs[2]:
    st.subheader("Prospective design explorer")
    st.caption("Planning only. Changing controls does not collect data, amend the protocol, or prove power.")
    col1, col2, col3 = st.columns(3)
    n_models = col1.slider("Models", 4, 16, 8)
    n_families = col2.slider("Scenario families", 6, 10, 10)
    repetitions = col3.slider("Repetitions", 1, 5, 3)
    horizon = st.radio("Trajectory horizon", [12, 24], horizontal=True)
    contexts = st.radio("Context conditions", [1, 2], index=1, horizontal=True)
    conversations = n_models * n_families * 3 * contexts * repetitions
    metrics = st.columns(3)
    metrics[0].metric("Conversations", f"{conversations:,}")
    metrics[1].metric("Responses", f"{conversations * horizon:,}")
    metrics[2].metric("Minimum two-sided block p", f"{2 / 2**n_families:.5f}")
    if 2 / 2**n_families > 0.05 / 4:
        st.error("Too few independent blocks to pass the first four-hypothesis Holm threshold (0.0125).")
    else:
        st.info(
            "The threshold is attainable, not guaranteed. "
            "Independence, effect size, and variance still need review."
        )
    st.write("Models × scenario families × three matched presentations × contexts × repetitions × turns")
    st.caption(
        "More turns track escalation and recovery; more repetitions reduce generation noise. "
        "Neither creates new scenario blocks."
    )
    st.caption(
        f"Rater workload: at one minute per response per rater, two raters would need about "
        f"{conversations * horizon * 2 / 60:,.0f} hours. This excludes training and adjudication."
    )
    draft = load_expanded_study(ROOT, horizon=horizon)
    family_id = st.selectbox("Inspect a draft scenario", [family.family_id for family in draft.scenarios])
    presentation = st.selectbox("Presentation", ["control", "ambiguous", "fixed_belief"])
    family = next(item for item in draft.scenarios if item.family_id == family_id)
    st.write(family.title)
    st.caption(f"Pending clinical and lived-experience review · {family.evaluation_construct}")
    st.dataframe(
        pd.DataFrame({"Turn": range(1, horizon + 1), "User prompt": family.variants[presentation].turns}),
        hide_index=True,
        width="stretch",
    )
    sensitivity = read_report("design_sensitivity.json")
    if sensitivity:
        st.subheader("Design-sensitivity simulation — assumptions, not observations")
        st.dataframe(pd.DataFrame(sensitivity["comparison"]), hide_index=True, width="stretch")
        st.caption(sensitivity["warning"])

with tabs[3]:
    st.subheader("Local conversation inspector")
    st.caption("Synthetic user scripts and actual model responses may contain distressing or unsafe content.")
    if st.checkbox("Show local pilot dialogues (not safety ratings)"):
        raw_root = ROOT / "data/raw"
        batches = [path for path in sorted(raw_root.glob("live-*")) if (path / "ledgers").is_dir()]
        if not batches:
            st.info("No local live ledgers are available. Public hosting does not include private dialogues.")
        else:
            batch_name = st.selectbox("Pilot batch", [path.name for path in batches])
            batch = next(path for path in batches if path.name == batch_name)
            records = []
            for path in sorted((batch / "ledgers").glob("*.jsonl")):
                # Only read the index header here; verify the selected complete
                # chain below. Hundreds of conversations need not all be loaded.
                with path.open(encoding="utf-8") as handle:
                    row = json.loads(handle.readline())["payload"]["manifest_row"]
                records.append(
                    (
                        f"{row['model_id']} · {row['scenario_family']} · {row['presentation']} · "
                        f"{row['context_condition']} · r{row['repetition']} · h{row['planned_turns']}",
                        path,
                        row,
                    )
                )
            label = st.selectbox("Conversation", [record[0] for record in records])
            _, path, row = next(record for record in records if record[0] == label)
            events = read_verified_events(path)
            st.caption(f"Verified hash chain · terminal state: {events[-1].event_type}")
            received = [event for event in events if event.event_type == "response_received"]
            if received:
                turn = st.select_slider("Response turn", options=[event.turn for event in received])
                response = next(event for event in received if event.turn == turn)
                snapshot = batch / "study_snapshot.json"
                if (batch / "inputs.json").exists():
                    inputs = json.loads((batch / "inputs.json").read_text(encoding="utf-8"))
                    track = next(
                        item["track"] for item in inputs["rows"] if item["row"]["run_id"] == row["run_id"]
                    )
                    recorded_study = StudyBundle.model_validate(inputs["studies"][track])
                else:
                    recorded_study = (
                        StudyBundle.model_validate_json(snapshot.read_text(encoding="utf-8"))
                        if snapshot.exists()
                        else load_study(ROOT / "config/study-v3")
                    )
                script = find_script(recorded_study, events[0].payload["manifest_row"]["script_id"])
                with st.chat_message("user"):
                    st.markdown(script.turns[turn - 1])
                st.caption(
                    f"Finish reason: {response.payload.get('finish_reason')} · "
                    f"provider: {response.payload.get('provider_name')}"
                )
                with st.chat_message("assistant"):
                    st.markdown(response.payload["text"])
                with st.expander("Response provenance"):
                    st.json(
                        {
                            key: response.payload.get(key)
                            for key in (
                                "requested_model_id",
                                "resolved_model_id",
                                "provider_name",
                                "finish_reason",
                                "generation_id",
                                "usage",
                                "latency_ms",
                                "request_hash",
                            )
                        }
                    )
                if response.payload.get("truncated"):
                    st.error(
                        "Truncated output retained as technical missingness; "
                        "not a complete safety observation."
                    )
            else:
                st.info("This run failed before returning a response. It is not counted as safe.")

with tabs[4]:
    st.subheader("What still prevents confirmatory claims")
    for blocker in freeze_blockers(ROOT):
        st.write("• " + blocker)
    st.info(
        "Independent construct review, ethics determination, statistical review, "
        "rater calibration, and preregistration cannot be supplied by this dashboard."
    )
    st.markdown(
        "[Research-methods audit](https://github.com/Mohamedajab/llm-psychosis-safety-benchmark/blob/main/docs/RESEARCH_METHODS_AUDIT_2026_10_07.md)"
    )
    st.caption("No manuscript has been drafted. The original MSc repository remains unchanged.")
