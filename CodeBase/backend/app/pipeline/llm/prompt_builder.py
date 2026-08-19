from __future__ import annotations

import json
from collections.abc import Sequence
from functools import lru_cache
from itertools import groupby
from pathlib import Path

from app.pipeline.ocr.paddle import TextRegion
from app.schemas.extraction import model_output_schema

TEMPLATE_PATH = Path(__file__).resolve().parent / "prompts" / "extract_v1.txt"

_SCHEMA_TOKEN = "__SCHEMA_JSON__"
_OCR_TOKEN = "__OCR_TEXT__"


@lru_cache
def load_template() -> str:
    return TEMPLATE_PATH.read_text()


def _joined_ocr_text(regions: Sequence[TextRegion]) -> str:
    usable = [region for region in regions if region.text.strip()]
    groups = [
        (page, list(page_regions)) for page, page_regions in groupby(usable, key=lambda r: r.page)
    ]
    if len(groups) <= 1:
        return "\n".join(region.text for region in usable)
    blocks = [
        f"--- Page {page} ---\n" + "\n".join(region.text for region in page_regions)
        for page, page_regions in groups
    ]
    return "\n".join(blocks)


def build_prompt(regions: Sequence[TextRegion]) -> str:
    lines = _joined_ocr_text(regions)
    schema_json = json.dumps(model_output_schema(), indent=2)
    return load_template().replace(_SCHEMA_TOKEN, schema_json).replace(_OCR_TOKEN, lines)
