from __future__ import annotations

import os
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

ENGINE_VERSION = "paddleocr-pp-ocrv5"
ORIGIN = "ocr_latin"
PDF_RASTER_DPI = 200

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


def _rasterize_pdf_page(pdf_path: Path, page: int, dpi: int = PDF_RASTER_DPI) -> Path:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(pdf_path))
    try:
        pdf_page = pdf[page - 1]
        try:
            image = pdf_page.render(scale=dpi / 72).to_pil()
        finally:
            pdf_page.close()
    finally:
        pdf.close()

    fd, raster_path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    image.save(raster_path)
    return Path(raster_path)


def _save_temp_png(image: Any) -> Path:
    fd, deskew_path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    image.save(deskew_path)
    return Path(deskew_path)


@dataclass(slots=True)
class PaddleLatinOCR:
    loader: EngineLoader = load_pp_ocrv5
    _engine: OCREngine | None = field(default=None, repr=False)

    @property
    def engine(self) -> OCREngine:
        if self._engine is None:
            self._engine = self.loader()
        return self._engine

    def page_count(self, image_path: str | Path) -> int:
        path = Path(image_path)
        if path.suffix.lower() != ".pdf":
            return 1
        import pypdfium2 as pdfium

        pdf = pdfium.PdfDocument(str(path))
        try:
            return len(pdf)
        finally:
            pdf.close()

    def read(
        self,
        image_path: str | Path,
        *,
        page: int = 1,
        size: tuple[int, int] | None = None,
    ) -> list[TextRegion]:
        path = Path(image_path)
        raster_path: Path | None = None
        deskew_path: Path | None = None
        if path.suffix.lower() == ".pdf":
            raster_path = _rasterize_pdf_page(path, page)
        engine_path = raster_path if raster_path is not None else path
        try:
            angle = 0.0
            if size is not None:
                width, height = size
            else:
                from PIL import Image

                from app.pipeline.ocr.deskew import estimate_skew_degrees, rotate_image

                with Image.open(engine_path) as opened:
                    width, height = opened.width, opened.height
                    if width > 0 and height > 0:
                        angle = estimate_skew_degrees(opened)
                        if angle != 0.0:
                            deskew_path = _save_temp_png(rotate_image(opened, angle))

            if width <= 0 or height <= 0:
                raise OCREngineError(f"image {path} reports a {width}x{height} page")

            predict_path = deskew_path if deskew_path is not None else engine_path
            regions: list[TextRegion] = []
            for result in self.engine.predict(str(predict_path)):
                regions.extend(_regions(result, width, height, page))

            if angle != 0.0:
                from app.pipeline.ocr.deskew import map_bbox_to_original

                regions = [
                    TextRegion(
                        text=region.text,
                        confidence=region.confidence,
                        bbox=map_bbox_to_original(region.bbox, angle, width, height),
                        page=region.page,
                    )
                    for region in regions
                ]
            return regions
        finally:
            if raster_path is not None:
                raster_path.unlink(missing_ok=True)
            if deskew_path is not None:
                deskew_path.unlink(missing_ok=True)
