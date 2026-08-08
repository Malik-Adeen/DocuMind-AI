from __future__ import annotations

import json

from app.pipeline.llm.prompt_builder import TEMPLATE_PATH, build_prompt
from app.pipeline.ocr.paddle import TextRegion
from app.schemas.extraction import model_output_schema


def region(text: str) -> TextRegion:
    return TextRegion(text=text, confidence=0.9, bbox=(0.1, 0.1, 0.5, 0.2), page=1)


def test_template_is_a_real_file_not_an_inline_string() -> None:
    assert TEMPLATE_PATH.exists()
    assert TEMPLATE_PATH.suffix == ".txt"
    assert TEMPLATE_PATH.read_text().strip(), "template file must not be empty"


def test_build_prompt_is_deterministic() -> None:
    regions = [region("PO Number: PO-2291"), region("Total: 11700.00")]

    assert build_prompt(regions) == build_prompt(regions)


def test_build_prompt_embeds_the_ocr_text() -> None:
    prompt = build_prompt([region("PO Number: PO-2291")])

    assert "PO Number: PO-2291" in prompt


def test_build_prompt_skips_blank_regions() -> None:
    prompt = build_prompt([region("   "), region("Total: 11700.00")])

    assert "Total: 11700.00" in prompt


def test_build_prompt_embeds_the_live_extraction_schema() -> None:
    prompt = build_prompt([region("PO Number: PO-2291")])
    schema_json = json.dumps(model_output_schema(), indent=2)

    assert schema_json in prompt


def test_build_prompt_requires_confidence_and_source() -> None:
    prompt = build_prompt([region("PO Number: PO-2291")])

    assert "confidence" in prompt
    assert "source" in prompt
    assert "raw_text" in prompt


def test_build_prompt_forbids_prose_and_markdown_fences() -> None:
    prompt = build_prompt([region("PO Number: PO-2291")])

    assert "no markdown" in prompt.lower()
    assert "no prose" in prompt.lower() or "only" in prompt.lower()


def test_build_prompt_forbids_inventing_values() -> None:
    prompt = build_prompt([region("PO Number: PO-2291")])

    assert "never invent" in prompt.lower() or "do not invent" in prompt.lower()
