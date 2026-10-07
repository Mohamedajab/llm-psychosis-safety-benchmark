from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from psychosis_benchmark.batch import BatchPaused, SpendingBudget, checkpoint_conversation
from psychosis_benchmark.contexts import load_context_histories
from psychosis_benchmark.design import build_manifest, load_study
from psychosis_benchmark.evidence import read_verified_events, verify_ledger
from psychosis_benchmark.provider import HttpResponse, OpenRouterClient, retry_after_seconds

ROOT = Path(__file__).resolve().parents[1]


class Transport:
    def __init__(self, results):
        self.results = results
        self.requests = []

    def send(self, url, *, headers, body, timeout):
        request = json.loads(body)
        self.requests.append(request)
        result = self.results.pop(0)
        if isinstance(result, int):
            return HttpResponse(result, b"{}", {"Retry-After": "0"})
        text, reason, cost = result
        return HttpResponse(
            200,
            json.dumps(
                {
                    "model": request["model"],
                    "id": "test-generation",
                    "choices": [{"message": {"content": text}, "finish_reason": reason}],
                    "usage": {} if cost is None else {"cost": cost},
                }
            ).encode(),
            {},
        )


def fixture_args(tmp_path):
    study = load_study(ROOT / "config/study-v3")
    row = next(row for row in build_manifest(study, "screening") if row.model_id == "openai/gpt-oss-20b")
    return {
        "study": study,
        "row": row,
        "histories": load_context_histories(ROOT / "config/study-v3/contexts"),
        "system_prompt": "test system",
        "ledger": tmp_path / "run.jsonl",
        "budget": SpendingBudget(tmp_path / "budget.sqlite3", 1.0),
        "attempts_per_session": 1,
        "interval_seconds": 0,
        "sleep": lambda _: None,
    }


def test_resume_keeps_response_and_transcript(tmp_path):
    args = fixture_args(tmp_path)
    first = Transport([("first response", "stop", 0.00001), 429])
    with pytest.raises(BatchPaused, match="http_429"):
        checkpoint_conversation(**args, client=OpenRouterClient("never-record-key", transport=first))
    before = read_verified_events(args["ledger"])
    # Remove the wall-clock retry delay only in this synthetic fixture via an injected
    # sleep: five seconds is within the allowed wait and no network is used.
    second = Transport([(f"response {n}", "stop", 0.00001) for n in range(2, 5)])
    assert checkpoint_conversation(**args, client=OpenRouterClient("test", transport=second)) == "completed"
    after = read_verified_events(args["ledger"])
    assert after[: len(before)] == before
    assert len(second.requests) == 3
    assert second.requests[0]["messages"][-2] == {"role": "assistant", "content": "first response"}
    assert [event.turn for event in after if event.event_type == "response_received"] == [1, 2, 3, 4]
    assert verify_ledger(args["ledger"]).valid
    assert "never-record-key" not in args["ledger"].read_text()
    assert (
        checkpoint_conversation(**args, client=OpenRouterClient("test", transport=Transport([])))
        == "completed"
    )


def test_budget_is_atomic_and_resume_cannot_raise_cap(tmp_path):
    budget = SpendingBudget(tmp_path / "budget.sqlite3", 0.01)
    barrier = threading.Barrier(2)

    def reserve(index):
        barrier.wait()
        try:
            budget.reserve(str(index), 0.008)
            return True
        except BatchPaused:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(reserve, range(2))) == 1
    assert budget.snapshot()["conservative_committed_usd"] <= 0.01
    with pytest.raises(ValueError, match="original spending cap"):
        SpendingBudget(tmp_path / "budget.sqlite3", 2.0)


def test_drift_fails_before_another_request(tmp_path):
    args = fixture_args(tmp_path)
    with pytest.raises(BatchPaused):
        checkpoint_conversation(**args, client=OpenRouterClient("test", transport=Transport([429])))
    args["system_prompt"] = "changed system"
    transport = Transport([])
    with pytest.raises(ValueError, match="drift"):
        checkpoint_conversation(**args, client=OpenRouterClient("test", transport=transport))
    assert not transport.requests


def test_missing_cost_pauses_and_cannot_silently_resume(tmp_path):
    args = fixture_args(tmp_path)
    with pytest.raises(BatchPaused, match="cost_missing"):
        checkpoint_conversation(
            **args, client=OpenRouterClient("test", transport=Transport([("text", "stop", None)]))
        )
    assert args["budget"].snapshot()["unsettled_or_unknown_attempts"] == 1
    with pytest.raises(BatchPaused, match="cost_missing"):
        checkpoint_conversation(**args, client=OpenRouterClient("test", transport=Transport([])))


@pytest.mark.parametrize("reason", ["length", "error", "content_filter"])
def test_failed_output_retained_without_terminal_rewrite(tmp_path, reason):
    args = fixture_args(tmp_path)
    assert (
        checkpoint_conversation(
            **args, client=OpenRouterClient("test", transport=Transport([("partial", reason, 0.00001)]))
        )
        == "failed"
    )
    original = args["ledger"].read_bytes()
    assert (
        checkpoint_conversation(**args, client=OpenRouterClient("test", transport=Transport([]))) == "failed"
    )
    assert args["ledger"].read_bytes() == original


def test_retry_after_and_budget_prevent_unpaid_request(tmp_path):
    assert retry_after_seconds({"Retry-After": "7"}) == 7
    assert retry_after_seconds({"retry-after": "nan"}) is None
    assert retry_after_seconds({"Retry-After": "garbage"}) is None
    args = fixture_args(tmp_path)
    args["budget"].reserve("previous", 1.0)
    transport = Transport([])
    with pytest.raises(BatchPaused, match="local_spending_cap"):
        checkpoint_conversation(**args, client=OpenRouterClient("test", transport=transport))
    assert not transport.requests


def test_plan_has_exact_balanced_size():
    import importlib.util

    spec = importlib.util.spec_from_file_location("sized_runner", ROOT / "scripts/run_sized_exploration.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    inputs = module.prepare_inputs()
    assert len(inputs["rows"]) == 396
    assert sum(item["row"]["planned_turns"] for item in inputs["rows"]) == 5184
    assert sum(model.endswith(":free") for model in inputs["plan"]["models"]) == 1
    assert (
        sum(
            item["row"]["planned_turns"]
            for item in inputs["rows"]
            if item["row"]["model_id"].endswith(":free")
        )
        == 864
    )
    assert len({item["row"]["scenario_family"] for item in inputs["rows"] if item["track"] == "core"}) == 10


def test_non_mutating_audit_checks_partial_and_complete_evidence(tmp_path):
    import importlib.util

    from psychosis_benchmark.evidence import payload_hash

    spec = importlib.util.spec_from_file_location("sized_audit", ROOT / "scripts/audit_sized_exploration.py")
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    args = fixture_args(tmp_path)
    directory = tmp_path / "batch"
    (directory / "ledgers").mkdir(parents=True)
    inputs = {
        "plan": {"models": [args["row"].model_id]},
        "studies": {"core": args["study"].model_dump(mode="json")},
        "histories": {key: value.model_dump(mode="json") for key, value in args["histories"].items()},
        "system_prompt": args["system_prompt"],
        "rows": [{"track": "core", "row": args["row"].model_dump(mode="json")}],
    }
    (directory / "inputs.json").write_text(json.dumps(inputs), encoding="utf-8")
    (directory / "input_hash.txt").write_text(payload_hash(inputs), encoding="utf-8")
    args["ledger"] = directory / "ledgers" / f"{args['row'].run_id}.jsonl"
    with pytest.raises(BatchPaused):
        checkpoint_conversation(
            **args,
            client=OpenRouterClient(
                "test",
                transport=Transport(
                    [
                        ("first", "stop", 0.00001),
                        429,
                    ]
                ),
            ),
        )
    before = args["ledger"].read_bytes()
    partial = audit.audit_batch(directory)
    assert partial["stored_responses"] == 1 and partial["completed_conversations"] == 0
    assert args["ledger"].read_bytes() == before
    checkpoint_conversation(
        **args,
        client=OpenRouterClient("test", transport=Transport([("later", "stop", 0.00001) for _ in range(3)])),
    )
    complete = audit.audit_batch(directory)
    assert complete["stored_responses"] == 4 and complete["completed_conversations"] == 1
    assert complete["recorded_response_cost_usd"] == pytest.approx(0.00004)
    assert complete["invalid_finish_responses"] == 0


def test_worker_exception_finishes_with_error_state_and_no_secret_traceback(tmp_path, monkeypatch, capsys):
    import importlib.util
    import io
    from types import SimpleNamespace

    from psychosis_benchmark.evidence import payload_hash
    from psychosis_benchmark.live_control import RuntimeMonitor

    spec = importlib.util.spec_from_file_location("sized_worker", ROOT / "scripts/run_sized_exploration.py")
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    args = fixture_args(tmp_path)
    directory = tmp_path / "batch"
    directory.mkdir()
    row = args["row"]
    inputs = {
        "plan": {
            "models": [row.model_id],
            "generation": {"max_attempts_per_turn_per_session": 1, "minimum_request_interval_seconds": 0},
        },
        "studies": {"core": args["study"].model_dump(mode="json")},
        "histories": {key: value.model_dump(mode="json") for key, value in args["histories"].items()},
        "system_prompt": args["system_prompt"],
        "rows": [{"track": "core", "row": row.model_dump(mode="json")}],
    }

    class BrokenClient(OpenRouterClient):
        def complete_once(self, **kwargs):
            raise ValueError("private-error-with-test-credential")

    monkeypatch.setattr(runner, "OpenRouterClient", BrokenClient)
    monkeypatch.setattr(runner, "verify_live_catalogue", lambda *args: [])
    monkeypatch.setattr(runner.urllib.request, "urlopen", lambda *args, **kwargs: io.BytesIO(b'{"data":[]}'))
    runtime = RuntimeMonitor(directory, [row.model_id])
    try:
        assert (
            runner.collect(
                SimpleNamespace(output_dir=directory, resume=False, budget_usd=1),
                inputs,
                {"input_hash": payload_hash(inputs)},
                "test-key",
                runtime,
            )
            == 1
        )
    finally:
        runtime.close()
    progress = json.loads((directory / "progress.json").read_text())
    assert progress["status"] == "paused_error"
    assert json.loads((directory / "runtime.json").read_text())["status"] == "paused_error"
    assert verify_ledger(directory / "ledgers" / f"{row.run_id}.jsonl").valid
    assert "private-error-with-test-credential" not in capsys.readouterr().out
    assert "private-error-with-test-credential" not in (directory / "runtime.json").read_text()
