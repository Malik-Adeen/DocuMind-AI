from __future__ import annotations

import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

ENGINE_VERSION = "paddleocr-pp-ocrv5"
ORIGIN = "ocr_latin"

POLY_KEYS = ("rec_polys", "dt_polys")
BOX_KEYS = ("rec_boxes",)


class OCREngineError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class TextRegion:
    text: str
    confidence: float
    bbox: tuple[float, float, float, float]
    page: int = 1

    def as_source(self) -> dict[str, Any]:
        return {
            "origin": ORIGIN,
            "page": self.page,
            "bbox": [self.bbox[0], self.bbox[1], self.bbox[2], self.bbox[3]],
            "raw_text": self.text,
        }


class OCREngine(Protocol):
    def predict(self, input: str) -> Sequence[Mapping[str, Any]]: ...


EngineLoader = Callable[[], OCREngine]


def load_pp_ocrv5() -> OCREngine:
    from paddleocr import PaddleOCR

    engine: OCREngine = PaddleOCR(
        lang=os.environ.get("PADDLEOCR_LANG", "en"),
        ocr_version="PP-OCRv5",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
    )
    return engine


def _clamp(value: float) -> float:
    return min(1.0, max(0.0, value))


def _corners(shape: Any) -> tuple[list[float], list[float]]:
    points = list(shape)
    if len(points) == 4 and all(isinstance(p, int | float) for p in points):
        x0, y0, x1, y1 = (float(p) for p in points)
        return [x0, x1], [y0, y1]
    return [float(p[0]) for p in points], [float(p[1]) for p in points]


def _bbox(shape: Any, width: int, height: int) -> tuple[float, float, float, float]:
    xs, ys = _corners(shape)
    if not xs or not ys:
        raise OCREngineError("a text region carried no geometry; INV-2 needs a source span")
    return (
        _clamp(min(xs) / width),
        _clamp(min(ys) / height),
        _clamp(max(xs) / width),
        _clamp(max(ys) / height),
    )


def _shapes(result: Mapping[str, Any]) -> Sequence[Any]:
    for key in (*POLY_KEYS, *BOX_KEYS):
        shapes = result.get(key)
        if shapes is not None and len(shapes) > 0:
            return list(shapes)
    raise OCREngineError(
        f"engine result carried none of {(*POLY_KEYS, *BOX_KEYS)}; cannot build a source span"
    )


def _regions(
    result: Mapping[str, Any],
    width: int,
    height: int,
    page: int,
) -> list[TextRegion]:
    texts = list(result.get("rec_texts") or [])
    if not texts:
        return []
    scores = [float(score) for score in result.get("rec_scores") or []]
    shapes = _shapes(result)
    try:
        rows = list(zip(texts, scores, shapes, strict=True))
    except ValueError as exc:
        raise OCREngineError(
            f"engine returned {len(texts)} texts, {len(scores)} scores and "
            f"{len(shapes)} regions; they must correspond"
        ) from exc
    return [
        TextRegion(
            text=str(text),
            confidence=_clamp(score),
            bbox=_bbox(shape, width, height),
            page=page,
        )
        for text, score, shape in rows
    ]


def image_size(image_path: Path) -> tuple[int, int]:
    from PIL import Image

    with Image.open(image_path) as image:
        return image.width, image.height


@dataclass(slots=True)
class PaddleLatinOCR:
    loader: EngineLoader = load_pp_ocrv5
    _engine: OCREngine | None = field(default=None, repr=False)

    @property
    def engine(self) -> OCREngine:
        if self._engine is None:
            self._engine = self.loader()
        return self._engine

    def read(
        self,
        image_path: str | Path,
        *,
        page: int = 1,
        size: tuple[int, int] | None = None,
    ) -> list[TextRegion]:
        path = Path(image_path)
        width, height = size if size is not None else image_size(path)
        if width <= 0 or height <= 0:
            raise OCREngineError(f"image {path} reports a {width}x{height} page")

        regions: list[TextRegion] = []
        for result in self.engine.predict(str(path)):
            regions.extend(_regions(result, width, height, page))
        return regions
