from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

DEFAULT_REPS = 20
DEFAULT_INVOICE = BACKEND / "tests" / "fixtures" / "invoices" / "invoice_1_simple.txt"
HISTORY_DIR = Path(__file__).resolve().parent / "history"

ABSENT = object()
INVALID_RESPONSE = object()


@dataclass(frozen=True, slots=True)
class FieldSummary:
    field: str
    distinct_count: int
    modal_value: Any
    modal_rate: float


def _field_observations(responses: Sequence[dict[str, Any] | None], field: str) -> list[Any]:
    observations: list[Any] = []
    for parsed in responses:
        if not isinstance(parsed, dict):
            observations.append(INVALID_RESPONSE)
            continue
        fields = parsed.get("fields")
        if not isinstance(fields, dict) or field not in fields:
            observations.append(ABSENT)
            continue
        entry = fields[field]
        observations.append(entry.get("value") if isinstance(entry, dict) else INVALID_RESPONSE)
    return observations


def summarize_field(responses: Sequence[dict[str, Any] | None], field: str) -> FieldSummary:
    observations = _field_observations(responses, field)
    counts = Counter(observations)
    modal_value, modal_count = counts.most_common(1)[0]
    return FieldSummary(
        field=field,
        distinct_count=len(counts),
        modal_value=modal_value,
        modal_rate=modal_count / len(observations),
    )


def summarize_all(
    responses: Sequence[dict[str, Any] | None], fields: Sequence[str]
) -> list[FieldSummary]:
    return [summarize_field(responses, field) for field in fields]


def _display(value: Any) -> str:
    if value is ABSENT:
        return "<absent>"
    if value is INVALID_RESPONSE:
        return "<invalid>"
    if value is None:
        return "null"
    return str(value)


def render_table(summaries: Sequence[FieldSummary]) -> str:
    headers = ("field", "distinct", "modal_value", "modal_rate")
    rows = [
        (s.field, str(s.distinct_count), _display(s.modal_value), f"{s.modal_rate:.0%}")
        for s in summaries
    ]
    widths = [
        max(len(headers[i]), *(len(row[i]) for row in rows)) if rows else len(headers[i])
        for i in range(len(headers))
    ]

    def fmt_row(cols: Sequence[str]) -> str:
        return "  ".join(col.ljust(width) for col, width in zip(cols, widths, strict=True))

    lines = [fmt_row(headers), fmt_row(["-" * w for w in widths])]
    lines.extend(fmt_row(row) for row in rows)
    return "\n".join(lines)


def parse_response(raw: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _read_ocr_text(invoice_path: Path) -> str:
    return invoice_path.read_text()


def _build_llm_client(
    seed: int | None = None, provider_order: tuple[str, ...] | None = None
) -> Any:
    import httpx

    from app.core.config import get_settings
    from app.pipeline.llm.client import DeploymentProfile, Endpoint, LLMClient
    from app.pipeline.llm.transport import HostedChatTransport

    settings = get_settings()
    if not settings.hosted_llm_base_url or not settings.hosted_llm_api_key:
        raise SystemExit(
            "HOSTED_LLM_BASE_URL and HOSTED_LLM_API_KEY must be set (see .env.example)."
        )
    client = httpx.Client(
        base_url=settings.hosted_llm_base_url,
        headers={"Authorization": f"Bearer {settings.hosted_llm_api_key}"},
        timeout=60.0,
    )
    transport = HostedChatTransport(
        client=client,
        model=settings.hosted_llm_model,
        seed=seed,
        provider_order=provider_order,
    )
    return LLMClient(
        profile=DeploymentProfile.PROTOTYPE,
        endpoint=Endpoint.HOSTED,
        model=settings.hosted_llm_model,
        transport=transport,
    )


def run(
    invoice_path: Path,
    reps: int,
    seed: int | None = None,
    provider_order: tuple[str, ...] | None = None,
    tag: str = "run",
) -> tuple[list[FieldSummary], Path]:
    from app.db.documents import DataClassification, DocumentRecord
    from app.pipeline.llm.client import assert_releasable
    from app.pipeline.llm.prompt_builder import build_prompt
    from app.pipeline.ocr.paddle import TextRegion
    from app.schemas.extraction import field_names

    text = _read_ocr_text(invoice_path)
    region = TextRegion(text=text, confidence=1.0, bbox=(0.0, 0.0, 1.0, 1.0), page=1)
    prompt = build_prompt([region])

    document = DocumentRecord(
        document_id=invoice_path.stem,
        filename=invoice_path.name,
        data_classification=DataClassification.SYNTHETIC,
        storage_path=str(invoice_path),
    )
    llm = _build_llm_client(seed=seed, provider_order=provider_order)
    assert_releasable(llm.endpoint, document)

    HISTORY_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    history_path = HISTORY_DIR / f"{invoice_path.stem}_{tag}_{timestamp}.jsonl"

    responses: list[dict[str, Any] | None] = []
    with history_path.open("w") as history_file:
        for rep in range(reps):
            content, body = llm.transport.complete_full(prompt)
            record = {
                "rep": rep,
                "raw": content,
                "id": body.get("id"),
                "provider": body.get("provider"),
                "body": body,
            }
            history_file.write(json.dumps(record) + "\n")
            history_file.flush()
            responses.append(parse_response(content))

    return summarize_all(responses, field_names()), history_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run N reps of a fixed (prompt, document) pair through the hosted LLM transport "
            "and report per-field distinct value count, modal value, and modal rate. "
            "No golden labels, no scoring — output reproducibility only."
        )
    )
    parser.add_argument("--invoice", type=Path, default=DEFAULT_INVOICE)
    parser.add_argument("--reps", type=int, default=DEFAULT_REPS)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument(
        "--provider",
        type=str,
        default=None,
        help="comma-separated OpenRouter provider names, e.g. Together,Phala",
    )
    parser.add_argument("--tag", type=str, default="run")
    args = parser.parse_args()

    provider_order = tuple(args.provider.split(",")) if args.provider else None

    summaries, history_path = run(
        args.invoice, args.reps, seed=args.seed, provider_order=provider_order, tag=args.tag
    )
    print(f"{args.invoice.name}, N={args.reps}, seed={args.seed}, provider={provider_order}\n")
    print(render_table(summaries))
    print(f"\nraw responses: {history_path}")


if __name__ == "__main__":
    main()
