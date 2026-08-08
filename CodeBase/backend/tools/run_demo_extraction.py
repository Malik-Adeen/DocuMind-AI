from __future__ import annotations

import contextlib
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import httpx  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.documents import DataClassification, DocumentRecord  # noqa: E402
from app.pipeline.llm.client import DeploymentProfile, Endpoint, LLMClient  # noqa: E402
from app.pipeline.llm.transport import HostedChatTransport  # noqa: E402
from app.pipeline.ocr.paddle import TextRegion  # noqa: E402
from app.pipeline.orchestrator import ExtractionOutcome, OrchestratorError, extract  # noqa: E402

INVOICES_DIR = BACKEND / "tests" / "fixtures" / "invoices"


class TextFileOCR:
    def read(self, image_path: str, *, page: int = 1) -> Sequence[TextRegion]:
        text = Path(image_path).read_text()
        return [TextRegion(text=text, confidence=1.0, bbox=(0.0, 0.0, 1.0, 1.0), page=page)]


class ResponseRecorder:
    """Pure instrumentation via an httpx response hook — records every raw
    hosted-LLM response (content + usage) without altering HostedChatTransport
    or LLMClient. Lives only in this dev script, never in shipped code."""

    def __init__(self) -> None:
        self.entries: list[dict[str, Any]] = []

    def __call__(self, response: httpx.Response) -> None:
        response.read()
        try:
            body = response.json()
        except ValueError:
            self.entries.append({"error": f"non-JSON response, status {response.status_code}"})
            return
        content = None
        with contextlib.suppress(KeyError, IndexError, TypeError):
            content = body["choices"][0]["message"]["content"]
        self.entries.append(
            {
                "status": response.status_code,
                "content": content,
                "usage": body.get("usage"),
                "raw_body": body if content is None else None,
            }
        )

    def since(self, mark: int) -> list[dict[str, Any]]:
        return self.entries[mark:]


def build_llm_client(recorder: ResponseRecorder) -> LLMClient:
    settings = get_settings()
    if not settings.hosted_llm_base_url or not settings.hosted_llm_api_key:
        raise SystemExit(
            "HOSTED_LLM_BASE_URL and HOSTED_LLM_API_KEY must be set (see .env.example). "
            "This calls a real hosted endpoint with real synthetic-invoice content."
        )
    client = httpx.Client(
        base_url=settings.hosted_llm_base_url,
        headers={"Authorization": f"Bearer {settings.hosted_llm_api_key}"},
        timeout=60.0,
        event_hooks={"response": [recorder]},
    )
    transport = HostedChatTransport(client=client, model=settings.hosted_llm_model)
    return LLMClient(
        profile=DeploymentProfile.PROTOTYPE,
        endpoint=Endpoint.HOSTED,
        model=settings.hosted_llm_model,
        transport=transport,
    )


def _print_calls(calls: list[dict[str, Any]]) -> None:
    for i, call in enumerate(calls, start=1):
        print(f"\n--- raw LLM response, call {i} of {len(calls)} ---")
        if call.get("content") is not None:
            print(call["content"])
        else:
            print(f"[no content field] {call.get('raw_body') or call.get('error')}")
        usage = call.get("usage")
        if usage:
            print(
                f"[usage] prompt_tokens={usage.get('prompt_tokens')} "
                f"completion_tokens={usage.get('completion_tokens')} "
                f"total_tokens={usage.get('total_tokens')} "
                f"cost=${usage.get('cost')}"
            )


def run_one(path: Path, llm: LLMClient, recorder: ResponseRecorder) -> None:
    document = DocumentRecord(
        document_id=path.stem,
        filename=path.name,
        data_classification=DataClassification.SYNTHETIC,
        storage_path=str(path),
    )
    print(f"\n{'=' * 80}\n{path.name}\n{'=' * 80}")

    mark = len(recorder.entries)
    try:
        outcome: ExtractionOutcome = extract(document, ocr=TextFileOCR(), llm=llm)
    except OrchestratorError as exc:
        _print_calls(recorder.since(mark))
        print(f"\nFAILED: {type(exc).__name__}: {exc}")
        return
    except Exception as exc:  # noqa: BLE001 - report and continue, don't crash the run
        _print_calls(recorder.since(mark))
        print(f"\nFAILED (unexpected): {type(exc).__name__}: {exc}")
        return

    _print_calls(recorder.since(mark))

    print("\n--- assembled extraction ---")
    print(json.dumps(outcome.result, indent=2))

    print(f"\n--- routing ---\nstatus: {outcome.status}")
    print(f"review.required: {outcome.result['review']['required']}")

    print("\n--- gates ---")
    for gate in outcome.result["gates"]:
        print(f"  {gate['name']}: {gate['result']} — {gate['detail']}")

    calls = recorder.since(mark)
    total_tokens = sum((c.get("usage") or {}).get("total_tokens", 0) for c in calls)
    total_cost = sum((c.get("usage") or {}).get("cost", 0) for c in calls)
    print(f"\n--- totals for this document ---\ncalls: {len(calls)}")
    print(f"total_tokens: {total_tokens}")
    print(f"total_cost: ${total_cost}")


def main() -> None:
    recorder = ResponseRecorder()
    llm = build_llm_client(recorder)
    invoices = sorted(INVOICES_DIR.glob("*.txt"))
    if not invoices:
        raise SystemExit(f"no invoice fixtures found under {INVOICES_DIR}")
    for path in invoices:
        run_one(path, llm, recorder)

    grand_total_tokens = sum(
        (e.get("usage") or {}).get("total_tokens", 0) for e in recorder.entries
    )
    grand_total_cost = sum((e.get("usage") or {}).get("cost", 0) for e in recorder.entries)
    print(
        f"\n{'=' * 80}\nGRAND TOTAL — {len(recorder.entries)} calls, "
        f"{grand_total_tokens} tokens, ${grand_total_cost}\n{'=' * 80}"
    )


if __name__ == "__main__":
    main()
