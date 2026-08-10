from __future__ import annotations

import logging
import uuid
from collections.abc import Callable

import httpx

from app.core.config import get_settings
from app.db.models import Document
from app.db.session import get_sessionmaker
from app.pipeline.llm.client import DeploymentProfile, Endpoint, LLMClient
from app.pipeline.llm.transport import HostedChatTransport
from app.pipeline.ocr.paddle import PaddleLatinOCR
from app.pipeline.orchestrator import OCRReader, OrchestratorError, run_and_persist
from app.workers.celery_app import celery_app

logger = logging.getLogger("app")


def _default_ocr_reader() -> OCRReader:
    return PaddleLatinOCR()


def _default_llm_client() -> LLMClient:
    settings = get_settings()
    if not settings.hosted_llm_base_url or not settings.hosted_llm_api_key:
        raise RuntimeError(
            "HOSTED_LLM_BASE_URL and HOSTED_LLM_API_KEY must be set (see .env.example)."
        )
    client = httpx.Client(
        base_url=settings.hosted_llm_base_url,
        headers={"Authorization": f"Bearer {settings.hosted_llm_api_key}"},
        timeout=60.0,
    )
    transport = HostedChatTransport(client=client, model=settings.hosted_llm_model)
    return LLMClient(
        profile=DeploymentProfile.PROTOTYPE,
        endpoint=Endpoint.HOSTED,
        model=settings.hosted_llm_model,
        transport=transport,
    )


build_ocr_reader: Callable[[], OCRReader] = _default_ocr_reader
build_llm_client: Callable[[], LLMClient] = _default_llm_client


@celery_app.task(name="app.workers.extract_document")  # type: ignore[untyped-decorator]
def extract_document(document_id: str) -> None:
    with get_sessionmaker()() as session:
        document = session.get(Document, uuid.UUID(document_id))
        if document is None:
            logger.warning("extract_document: no such document %s", document_id)
            return
        if document.status != "queued":
            logger.info(
                "extract_document: document %s already %s, skipping",
                document_id,
                document.status,
            )
            return
        document.status = "extracting"
        session.commit()
        try:
            run_and_persist(
                session,
                document,
                ocr=build_ocr_reader(),
                llm=build_llm_client(),
            )
        except OrchestratorError as exc:
            document.status = "failed"
            session.commit()
            logger.error("extract_document: %s failed at stage %s: %s", document_id, exc.stage, exc)
        except Exception as exc:
            document.status = "failed"
            session.commit()
            logger.error("extract_document: %s failed unexpectedly: %s", document_id, exc)
            raise
