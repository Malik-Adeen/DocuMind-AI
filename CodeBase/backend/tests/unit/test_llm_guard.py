from __future__ import annotations

import inspect

import pytest

from app.db.documents import DataClassification, DocumentRecord
from app.pipeline.llm.client import (
    DeploymentProfile,
    Endpoint,
    HostedEndpointRefusedError,
    LLMClient,
    ProfileMisconfiguredError,
    assert_releasable,
)

DOC = "doc-4471"
SECRET_PROMPT = "Customer: Karachi Textile Mills, CNIC 42101-1234567-1, IBAN PK36SCBL..."


class Spy:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def __call__(self, prompt: str) -> str:
        self.calls.append(prompt)
        return "{}"


def document(classification: object) -> DocumentRecord:
    return DocumentRecord(
        document_id=DOC,
        filename="invoice-2291.pdf",
        data_classification=classification,  # type: ignore[arg-type]
    )


def unclassified() -> DocumentRecord:
    return DocumentRecord(document_id=DOC, filename="invoice-2291.pdf")


def hosted(transport: Spy) -> LLMClient:
    return LLMClient(
        profile=DeploymentProfile.PROTOTYPE,
        endpoint=Endpoint.HOSTED,
        model="hosted-model",
        transport=transport,
    )


def local(transport: Spy) -> LLMClient:
    return LLMClient(
        profile=DeploymentProfile.PRODUCTION,
        endpoint=Endpoint.LOCAL,
        model="qwen2.5-7b-instruct",
        transport=transport,
    )


@pytest.mark.parametrize("classification", ["public", "synthetic"])
def test_hosted_allows_releasable_data(classification: str) -> None:
    spy = Spy()
    result = hosted(spy).complete("extract", document=document(classification))
    assert result == "{}"
    assert spy.calls == ["extract"]


def test_hosted_refuses_restricted_data() -> None:
    spy = Spy()
    with pytest.raises(HostedEndpointRefusedError):
        hosted(spy).complete(SECRET_PROMPT, document=document("restricted"))


def test_transport_is_never_reached_when_refused() -> None:
    spy = Spy()
    with pytest.raises(HostedEndpointRefusedError):
        hosted(spy).complete(SECRET_PROMPT, document=document("restricted"))
    assert spy.calls == [], "the prompt reached the transport despite the guard raising"


def test_unclassified_document_is_refused_and_transport_never_reached() -> None:
    spy = Spy()
    with pytest.raises(HostedEndpointRefusedError):
        hosted(spy).complete(SECRET_PROMPT, document=unclassified())
    assert spy.calls == []


@pytest.mark.parametrize(
    "classification",
    [None, "", "   ", "customer", "unknown", "internal", 0, 1, True, object(), ["public"]],
)
def test_unrecognised_classification_is_refused_not_allowed(classification: object) -> None:
    spy = Spy()
    with pytest.raises(HostedEndpointRefusedError):
        hosted(spy).complete(SECRET_PROMPT, document=document(classification))
    assert spy.calls == []


@pytest.mark.parametrize("classification", ["PUBLIC", " public ", "Synthetic"])
def test_classification_is_case_and_whitespace_insensitive(classification: str) -> None:
    spy = Spy()
    hosted(spy).complete("extract", document=document(classification))
    assert spy.calls == ["extract"]


def test_local_endpoint_accepts_restricted_data() -> None:
    spy = Spy()
    result = local(spy).complete(SECRET_PROMPT, document=document("restricted"))
    assert result == "{}"
    assert spy.calls == [SECRET_PROMPT]


def test_production_profile_cannot_be_built_with_a_hosted_endpoint() -> None:
    with pytest.raises(ProfileMisconfiguredError):
        LLMClient(
            profile=DeploymentProfile.PRODUCTION,
            endpoint=Endpoint.HOSTED,
            model="hosted-model",
            transport=Spy(),
        )


def test_refusal_message_does_not_leak_document_content() -> None:
    spy = Spy()
    with pytest.raises(HostedEndpointRefusedError) as caught:
        hosted(spy).complete(SECRET_PROMPT, document=document("restricted"))

    message = str(caught.value)
    assert "INV-6" in message
    assert DOC in message
    assert "CNIC" not in message
    assert "42101-1234567-1" not in message
    assert "Karachi" not in message
    assert "PK36SCBL" not in message


def test_refusal_message_names_the_allowed_classifications() -> None:
    spy = Spy()
    with pytest.raises(HostedEndpointRefusedError) as caught:
        hosted(spy).complete("x", document=document("restricted"))
    message = str(caught.value)
    assert "public" in message
    assert "synthetic" in message


def test_guard_is_callable_directly_for_non_llm_egress() -> None:
    assert_releasable(Endpoint.LOCAL, document("restricted"))
    assert_releasable(Endpoint.HOSTED, document("synthetic"))
    with pytest.raises(HostedEndpointRefusedError):
        assert_releasable(Endpoint.HOSTED, document("restricted"))


def test_restricted_is_never_releasable_even_if_enum_is_extended() -> None:
    from app.pipeline.llm.client import RELEASABLE_TO_HOSTED

    assert DataClassification.RESTRICTED not in RELEASABLE_TO_HOSTED


def test_classification_cannot_be_passed_as_a_call_argument() -> None:
    parameters = set(inspect.signature(LLMClient.complete).parameters)
    assert "data_classification" not in parameters, (
        "data_classification is back as an argument; INV-6 would again depend on the caller"
    )
    assert parameters == {"self", "prompt", "document"}

    guard = set(inspect.signature(assert_releasable).parameters)
    assert guard == {"endpoint", "document"}
