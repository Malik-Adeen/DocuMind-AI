from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from app.db.documents import DataClassification, DocumentRecord


class DeploymentProfile(StrEnum):
    PROTOTYPE = "prototype"
    PRODUCTION = "production"


class Endpoint(StrEnum):
    LOCAL = "local"
    HOSTED = "hosted"


RELEASABLE_TO_HOSTED = frozenset({DataClassification.PUBLIC, DataClassification.SYNTHETIC})


class HostedEndpointRefusedError(RuntimeError):
    def __init__(self, document_id: str, classification: DataClassification) -> None:
        allowed = ", ".join(sorted(item.value for item in RELEASABLE_TO_HOSTED))
        super().__init__(
            f"INV-6: refusing to send document {document_id} to a hosted LLM endpoint. "
            f"data_classification is {classification.value}; only {allowed} may leave this machine."
        )
        self.document_id = document_id
        self.classification = classification


class ProfileMisconfiguredError(RuntimeError):
    pass


def assert_releasable(endpoint: Endpoint, document: DocumentRecord) -> None:
    if endpoint is Endpoint.LOCAL:
        return
    if document.data_classification in RELEASABLE_TO_HOSTED:
        return
    raise HostedEndpointRefusedError(document.document_id, document.data_classification)


@dataclass(frozen=True, slots=True)
class LLMClient:
    profile: DeploymentProfile
    endpoint: Endpoint
    model: str
    transport: Callable[[str], str]

    def __post_init__(self) -> None:
        if self.profile is DeploymentProfile.PRODUCTION and self.endpoint is Endpoint.HOSTED:
            raise ProfileMisconfiguredError(
                "INV-6: the production profile handles real PTCL documents and may not be "
                "configured with a hosted endpoint."
            )

    def complete(self, prompt: str, *, document: DocumentRecord) -> str:
        assert_releasable(self.endpoint, document)
        return self.transport(prompt)
