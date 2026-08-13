from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from app.pipeline.ocr.paddle import TextRegion

LINE_ITEM_FIELD_NAMES = ("description", "quantity", "unit_price", "line_total")


@dataclass(frozen=True, slots=True)
class ProvenanceReport:
    populated_fields: int
    claimed_fields: int
    resolved_fields: int
    unmatched_claims: tuple[str, ...]


def _joined_text_with_offsets(
    regions: Sequence[TextRegion],
) -> tuple[str, list[tuple[int, int, TextRegion]]]:
    usable = [region for region in regions if region.text.strip()]
    parts: list[str] = []
    spans: list[tuple[int, int, TextRegion]] = []
    cursor = 0
    for index, region in enumerate(usable):
        if index > 0:
            cursor += 1
        start = cursor
        parts.append(region.text)
        cursor += len(region.text)
        spans.append((start, cursor, region))
    return "\n".join(parts), spans


def _match_region_span(
    raw_text: str,
    joined_text: str,
    spans: Sequence[tuple[int, int, TextRegion]],
) -> tuple[int, tuple[float, float, float, float]] | None:
    index = joined_text.find(raw_text)
    if index == -1:
        return None
    end = index + len(raw_text)
    matched = [region for start, stop, region in spans if start < end and stop > index]
    if not matched:
        return None
    pages = {region.page for region in matched}
    if len(pages) != 1:
        return None
    x0 = min(region.bbox[0] for region in matched)
    y0 = min(region.bbox[1] for region in matched)
    x1 = max(region.bbox[2] for region in matched)
    y1 = max(region.bbox[3] for region in matched)
    return matched[0].page, (x0, y0, x1, y1)


def _attach_field(
    entry: dict[str, Any],
    joined_text: str,
    spans: Sequence[tuple[int, int, TextRegion]],
    unmatched: list[str],
    name: str,
    counts: dict[str, int],
) -> None:
    source: dict[str, Any] = entry["source"]
    if source.get("origin") != "llm_inferred":
        return
    raw_text = source.get("raw_text")
    if not raw_text:
        return
    counts["claimed"] += 1
    match = _match_region_span(raw_text, joined_text, spans)
    if match is None:
        unmatched.append(name)
        return
    page, bbox = match
    source["page"] = page
    source["bbox"] = list(bbox)
    counts["resolved"] += 1


def attach_provenance(
    fields: dict[str, Any],
    line_items: list[dict[str, Any]],
    regions: Sequence[TextRegion],
) -> ProvenanceReport:
    joined_text, spans = _joined_text_with_offsets(regions)
    unmatched: list[str] = []
    counts = {"populated": 0, "claimed": 0, "resolved": 0}

    for name, entry in fields.items():
        if entry.get("value") is not None:
            counts["populated"] += 1
        _attach_field(entry, joined_text, spans, unmatched, name, counts)

    for index, item in enumerate(line_items):
        for field_name in LINE_ITEM_FIELD_NAMES:
            entry = item.get(field_name)
            if not isinstance(entry, dict):
                continue
            if entry.get("value") is not None:
                counts["populated"] += 1
            _attach_field(
                entry, joined_text, spans, unmatched, f"line_items[{index}].{field_name}", counts
            )

    return ProvenanceReport(
        populated_fields=counts["populated"],
        claimed_fields=counts["claimed"],
        resolved_fields=counts["resolved"],
        unmatched_claims=tuple(unmatched),
    )
