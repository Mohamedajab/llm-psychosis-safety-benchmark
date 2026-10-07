from __future__ import annotations

import http.client
import json
from pathlib import Path

import pytest

from psychosis_benchmark.collection import CollectionError, collect_conversation, first_request_preview
from psychosis_benchmark.contexts import load_context_histories
from psychosis_benchmark.design import build_manifest, load_study
from psychosis_benchmark.evidence import verify_ledger
from psychosis_benchmark.provider import HttpResponse, OpenRouterClient, ProviderCallError, UrllibTransport

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "study-v3"


class FakeTransport:
    def __init__(self, responses: list[HttpResponse]) -> None:
        self.responses = responses
        self.requests: list[dict[str, object]] = []

    def send(self, url, *, headers, body, timeout):
        self.requests.append(
            {"url": url, "headers": dict(headers), "body": json.loads(body), "timeout": timeout}
        )
        return self.responses.pop(0)


def _response(model_id: str, text: str, *, finish_reason: str = "stop") -> HttpResponse:
    return HttpResponse(
        status_code=200,
        headers={"x-request-id": "request-1"},
        body=json.dumps(
            {
                "id": "generation-1",
                "model": model_id,
                "choices": [{"message": {"content": text}, "finish_reason": finish_reason}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            }
        ).encode(),
    )


def test_payload_disables_fallbacks_and_uses_exact_slug() -> None:
    study = load_study(CONFIG)
    transport = FakeTransport([_response("example/model", "hello")])
    client = OpenRouterClient("test-key", transport=transport, clock=lambda: 1.0)
    result = client.complete_once(
        model_id="example/model",
        messages=[{"role": "user", "content": "hello"}],
        generation=study.design.generation,
        seed=7,
        provider_pin=None,
    )
    payload = transport.requests[0]["body"]
    assert payload["provider"] == {
        "allow_fallbacks": False,
        "require_parameters": True,
        "max_price": {"prompt": 0.10, "completion": 0.40},
    }
    assert payload["model"] == "example/model"
    assert result.text == "hello"
    assert "test-key" not in json.dumps(result.__dict__)


def test_resolved_model_mismatch_fails_closed() -> None:
    study = load_study(CONFIG)
    transport = FakeTransport([_response("other/model", "hello")])
    client = OpenRouterClient("test-key", transport=transport)
    with pytest.raises(ProviderCallError, match="resolved_model_mismatch"):
        client.complete_once(
            model_id="example/model",
            messages=[{"role": "user", "content": "hello"}],
            generation=study.design.generation,
            seed=None,
            provider_pin=None,
        )


def test_screening_conversation_writes_verifiable_evidence(tmp_path) -> None:
    study = load_study(CONFIG)
    row = build_manifest(study, "development")[0]
    histories = load_context_histories(CONFIG / "contexts")
    script_responses = [_response(row.model_id, f"response {turn}") for turn in range(1, 5)]
    client = OpenRouterClient("test-key", transport=FakeTransport(script_responses))
    ledger = tmp_path / "run.jsonl"
    collect_conversation(
        study=study,
        row=row,
        histories=histories,
        system_prompt=(CONFIG / "system_prompt.txt").read_text(encoding="utf-8"),
        client=client,
        ledger_path=ledger,
        sleep=lambda _: None,
    )
    report = verify_ledger(ledger)
    assert report.valid
    assert report.event_count == 10
    with pytest.raises(CollectionError, match="immutable"):
        collect_conversation(
            study=study,
            row=row,
            histories=histories,
            system_prompt="system",
            client=client,
            ledger_path=ledger,
        )


def test_preview_has_hash_but_no_prompt_text() -> None:
    study = load_study(CONFIG)
    row = build_manifest(study, "screening")[0]
    histories = load_context_histories(CONFIG / "contexts")
    preview = first_request_preview(
        study=study,
        row=row,
        histories=histories,
        system_prompt=(CONFIG / "system_prompt.txt").read_text(encoding="utf-8"),
    )
    assert len(preview["first_request_hash"]) == 64
    assert "messages" not in preview


@pytest.mark.parametrize(
    "decoded",
    [
        [],
        {"choices": "wrong"},
        {"model": "example/model", "choices": ["wrong"]},
        {"model": "example/model", "choices": [{"message": "wrong"}]},
    ],
)
def test_malformed_provider_shape_is_a_recordable_failure(decoded):
    study = load_study(CONFIG)
    transport = FakeTransport([HttpResponse(200, json.dumps(decoded).encode(), {})])
    with pytest.raises(ProviderCallError):
        OpenRouterClient("test", transport=transport).complete_once(
            model_id="example/model",
            messages=[],
            generation=study.design.generation,
            seed=None,
            provider_pin=None,
        )


def test_incomplete_http_body_becomes_retryable_transport_failure(monkeypatch):
    def broken(*args, **kwargs):
        raise http.client.IncompleteRead(b"private network bytes")

    monkeypatch.setattr("urllib.request.urlopen", broken)
    with pytest.raises(ProviderCallError, match="transport_error") as error:
        UrllibTransport().send("https://example.test", headers={}, body=b"{}", timeout=1)
    assert error.value.retryable
    assert "private" not in str(error.value)
