from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from app.pipeline.llm.transport import HostedChatTransport, HostedLLMError

MODEL = "Qwen/Qwen2.5-7B-Instruct"


def client_with(handler: Any) -> httpx.Client:
    return httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://fake-hosted-llm.invalid/v1",
        headers={"Authorization": "Bearer secret-key"},
    )


def completion_response(content: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "id": "chatcmpl-1",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": content}}],
        },
    )


def test_posts_prompt_as_chat_completion_and_returns_content() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        captured["body"] = json.loads(request.content)
        return completion_response('{"fields": {}}')

    transport = HostedChatTransport(client=client_with(handler), model=MODEL)
    result = transport("extract this")

    assert result == '{"fields": {}}'
    assert captured["request"].url.path == "/v1/chat/completions"
    assert captured["body"]["model"] == MODEL
    assert captured["body"]["messages"] == [{"role": "user", "content": "extract this"}]


def test_caps_max_tokens_at_2000_by_default() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return completion_response("{}")

    HostedChatTransport(client=client_with(handler), model=MODEL)("x")

    assert captured["body"]["max_tokens"] == 2000


def test_max_tokens_is_configurable() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return completion_response("{}")

    HostedChatTransport(client=client_with(handler), model=MODEL, max_tokens=500)("x")

    assert captured["body"]["max_tokens"] == 500


def test_sends_the_clients_bearer_auth_header() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers.get("authorization")
        return completion_response("{}")

    HostedChatTransport(client=client_with(handler), model=MODEL)("x")

    assert captured["auth"] == "Bearer secret-key"


def test_raises_hosted_llm_error_on_http_error_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "internal"})

    transport = HostedChatTransport(client=client_with(handler), model=MODEL)

    with pytest.raises(HostedLLMError):
        transport("extract this")


def test_raises_hosted_llm_error_on_unexpected_response_shape() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "shape"})

    transport = HostedChatTransport(client=client_with(handler), model=MODEL)

    with pytest.raises(HostedLLMError):
        transport("extract this")


def test_transport_is_usable_as_an_llmclient_transport_callable() -> None:
    from app.db.documents import DataClassification, DocumentRecord
    from app.pipeline.llm.client import DeploymentProfile, Endpoint, LLMClient

    def handler(request: httpx.Request) -> httpx.Response:
        return completion_response('{"ok": true}')

    transport = HostedChatTransport(client=client_with(handler), model=MODEL)
    client = LLMClient(
        profile=DeploymentProfile.PROTOTYPE,
        endpoint=Endpoint.HOSTED,
        model=MODEL,
        transport=transport,
    )
    document = DocumentRecord(
        document_id="doc-1", filename="doc.pdf", data_classification=DataClassification.SYNTHETIC
    )

    assert client.complete("extract this", document=document) == '{"ok": true}'
