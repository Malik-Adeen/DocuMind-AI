from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from app.core.config import get_settings
from app.core.errors import envelope
from app.db.models import Document, Export
from app.db.session import get_sessionmaker
from app.export.xlsx import write_workbook
from app.pipeline.llm.client import (
    DeploymentProfile,
    Endpoint,
    HostedEndpointRefusedError,
    LLMClient,
)
from app.pipeline.llm.transport import HostedChatTransport
from app.pipeline.ocr.paddle import PaddleLatinOCR
from app.pipeline.orchestrator import OCRReader, OrchestratorError, run_and_persist
from app.workers.celery_app import celery_app

logger = logging.getLogger("app")

EXPORT_TTL_HOURS = 24


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
        except HostedEndpointRefusedError as exc:
            error_trace_id = uuid.uuid4()
            document.status = "failed"
            document.error = envelope("HOSTED_ENDPOINT_REFUSED", str(exc), str(error_trace_id))[
                "error"
            ]
            session.commit()
            logger.error(
                "extract_document: %s refused by INV-6 guard (trace_id=%s): %s",
                document_id,
                error_trace_id,
                exc,
            )
        except OrchestratorError as exc:
            document.status = "failed"
            session.commit()
            logger.error("extract_document: %s failed at stage %s: %s", document_id, exc.stage, exc)
        except Exception as exc:
            error_trace_id = uuid.uuid4()
            document.status = "failed"
            document.error = envelope(
                "INTERNAL",
                f"Extraction failed unexpectedly. Server logs have detail under trace_id "
                f"{error_trace_id}.",
                str(error_trace_id),
            )["error"]
            session.commit()
            logger.error(
                "extract_document: %s failed unexpectedly (trace_id=%s): %s",
                document_id,
                error_trace_id,
                exc,
            )
            raise


@celery_app.task(name="app.workers.generate_export")  # type: ignore[untyped-decorator]
def generate_export(export_id: str) -> None:
    with get_sessionmaker()() as session:
        export = session.get(Export, uuid.UUID(export_id))
        if export is None:
            logger.warning("generate_export: no such export %s", export_id)
            return
        if export.status != "queued":
            logger.info("generate_export: export %s already %s, skipping", export_id, export.status)
            return
        try:
            parsed_ids: list[uuid.UUID] = []
            for raw in export.document_ids:
                try:
                    parsed_ids.append(uuid.UUID(str(raw)))
                except ValueError:
                    continue

            settings = get_settings()
            target = Path(settings.export_dir) / f"export-{export.id}.xlsx"
            write_workbook(session, document_ids=parsed_ids, target=target)

            export.artifact_path = str(target)
            export.status = "complete"
            export.expires_at = datetime.now(UTC) + timedelta(hours=EXPORT_TTL_HOURS)
            session.commit()
        except Exception as exc:
            export.status = "failed"
            session.commit()
            logger.error("generate_export: %s failed unexpectedly: %s", export_id, exc)
            raise
