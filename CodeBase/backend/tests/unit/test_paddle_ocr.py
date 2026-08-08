from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import pytest

from app.pipeline.ocr.paddle import (
    ENGINE_VERSION,
    ORIGIN,
    OCREngineError,
    PaddleLatinOCR,
    TextRegion,
)

PAGE = (1000, 500)


def result(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "rec_texts": ["Invoice", "PO-2291"],
        "rec_scores": [0.98, 0.91],
        "rec_polys": [
            [[100, 50], [300, 50], [300, 100], [100, 100]],
            [[100, 150], [500, 150], [500, 200], [100, 200]],
        ],
    }
    base.update(overrides)
    return base


class FakeEngine:
    def __init__(self, results: Sequence[Mapping[str, Any]]) -> None:
        self.results = results
        self.calls: list[str] = []

    def predict(self, input: str) -> Sequence[Mapping[str, Any]]:
        self.calls.append(input)
        return self.results


class CountingLoader:
    def __init__(self, engine: FakeEngine) -> None:
        self.engine = engine
        self.loads = 0

    def __call__(self) -> FakeEngine:
        self.loads += 1
        return self.engine


def reader(*results: Mapping[str, Any]) -> tuple[PaddleLatinOCR, CountingLoader]:
    loader = CountingLoader(FakeEngine(list(results)))
    return PaddleLatinOCR(loader=loader), loader


def test_model_is_not_loaded_until_a_page_is_read() -> None:
    _, loader = reader(result())
    assert loader.loads == 0


def test_model_is_loaded_once_and_reused() -> None:
    ocr, loader = reader(result())
    ocr.read("scan.png", size=PAGE)
    ocr.read("scan.png", size=PAGE)
    assert loader.loads == 1
    assert loader.engine.calls == ["scan.png", "scan.png"]


def test_bboxes_are_normalised_to_zero_one() -> None:
    ocr, _ = reader(result())
    regions = ocr.read("scan.png", size=PAGE)

    assert [region.text for region in regions] == ["Invoice", "PO-2291"]
    assert regions[0].bbox == (0.1, 0.1, 0.3, 0.2)
    assert regions[1].bbox == (0.1, 0.3, 0.5, 0.4)
    for region in regions:
        assert all(0.0 <= value <= 1.0 for value in region.bbox)


def test_confidence_is_carried_per_region() -> None:
    ocr, _ = reader(result())
    assert [region.confidence for region in ocr.read("scan.png", size=PAGE)] == [0.98, 0.91]


def test_coordinates_outside_the_page_are_clamped() -> None:
    ocr, _ = reader(
        result(
            rec_texts=["edge"],
            rec_scores=[0.5],
            rec_polys=[[[-20, -8], [1200, -8], [1200, 640], [-20, 640]]],
        )
    )
    assert ocr.read("scan.png", size=PAGE)[0].bbox == (0.0, 0.0, 1.0, 1.0)


def test_confidence_outside_zero_one_is_clamped() -> None:
    ocr, _ = reader(result(rec_texts=["x"], rec_scores=[1.4], rec_polys=[[[0, 0], [10, 10]]]))
    assert ocr.read("scan.png", size=PAGE)[0].confidence == 1.0


def test_rotated_quadrilaterals_become_axis_aligned_bounds() -> None:
    ocr, _ = reader(
        result(
            rec_texts=["skewed"],
            rec_scores=[0.7],
            rec_polys=[[[100, 60], [300, 50], [305, 100], [105, 110]]],
        )
    )
    assert ocr.read("scan.png", size=PAGE)[0].bbox == (0.1, 0.1, 0.305, 0.22)


def test_flat_rec_boxes_are_accepted_when_polygons_are_absent() -> None:
    ocr, _ = reader(
        {
            "rec_texts": ["boxed"],
            "rec_scores": [0.8],
            "rec_polys": [],
            "rec_boxes": [[100, 50, 300, 100]],
        }
    )
    assert ocr.read("scan.png", size=PAGE)[0].bbox == (0.1, 0.1, 0.3, 0.2)


def test_detection_polygons_are_the_fallback() -> None:
    ocr, _ = reader(
        {
            "rec_texts": ["detected"],
            "rec_scores": [0.6],
            "dt_polys": [[[0, 0], [500, 0], [500, 250], [0, 250]]],
        }
    )
    assert ocr.read("scan.png", size=PAGE)[0].bbox == (0.0, 0.0, 0.5, 0.5)


def test_pages_are_stamped_on_every_region() -> None:
    ocr, _ = reader(result())
    assert {region.page for region in ocr.read("scan.png", page=4, size=PAGE)} == {4}


def test_multiple_engine_results_are_flattened() -> None:
    ocr, _ = reader(result(), result(rec_texts=["Total"], rec_scores=[0.77], rec_polys=[[[0, 0]]]))
    assert len(ocr.read("scan.png", size=PAGE)) == 3


def test_an_empty_page_yields_no_regions() -> None:
    ocr, _ = reader({"rec_texts": [], "rec_scores": [], "rec_polys": []})
    assert ocr.read("scan.png", size=PAGE) == []


def test_mismatched_texts_and_scores_are_an_error_not_a_truncation() -> None:
    ocr, _ = reader(result(rec_scores=[0.9]))
    with pytest.raises(OCREngineError, match="must correspond"):
        ocr.read("scan.png", size=PAGE)


def test_a_region_with_no_geometry_is_an_error() -> None:
    ocr, _ = reader({"rec_texts": ["orphan"], "rec_scores": [0.9]})
    with pytest.raises(OCREngineError, match="cannot build a source span"):
        ocr.read("scan.png", size=PAGE)


@pytest.mark.parametrize("size", [(0, 500), (1000, 0), (-1, 500)])
def test_a_degenerate_page_size_is_an_error(size: tuple[int, int]) -> None:
    ocr, _ = reader(result())
    with pytest.raises(OCREngineError, match="page"):
        ocr.read("scan.png", size=size)


def test_as_source_matches_the_extraction_schema_source_object() -> None:
    source = TextRegion(
        text="PO-2291", confidence=0.91, bbox=(0.1, 0.3, 0.5, 0.4), page=2
    ).as_source()

    assert set(source) == {"origin", "page", "bbox", "raw_text"}
    assert source["origin"] == ORIGIN
    assert source["page"] == 2
    assert source["bbox"] == [0.1, 0.3, 0.5, 0.4]
    assert source["raw_text"] == "PO-2291"


def test_regions_carry_provenance_for_every_field_inv_2() -> None:
    ocr, _ = reader(result())
    for region in ocr.read("scan.png", size=PAGE):
        source = region.as_source()
        assert source["bbox"] and source["page"], "a region reached the caller with no provenance"


def test_engine_version_matches_the_pipeline_version_stamp() -> None:
    assert ENGINE_VERSION == "paddleocr-pp-ocrv5"


def test_regions_are_immutable() -> None:
    import dataclasses

    region = TextRegion(text="x", confidence=0.5, bbox=(0.0, 0.0, 1.0, 1.0))
    with pytest.raises(dataclasses.FrozenInstanceError):
        region.confidence = 0.9  # type: ignore[misc]
