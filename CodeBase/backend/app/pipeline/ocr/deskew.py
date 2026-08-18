from __future__ import annotations

from PIL import Image

ANGLE_BAND_DEGREES = 20.0
MAX_CORRECTION_DEGREES = 15.0
NOOP_THRESHOLD_DEGREES = 0.1
MIN_LINE_LENGTH_FRACTION = 0.25
MIN_QUALIFYING_LINES = 3
HOUGH_THRESHOLD = 80
MAX_LINE_GAP = 20
CANNY_LOW = 50
CANNY_HIGH = 150


def _clamp01(value: float) -> float:
    return min(1.0, max(0.0, value))


def estimate_skew_degrees(image: Image.Image) -> float:
    """Median angle of long near-horizontal edges, in the sense that ``rotate_image`` with this
    value levels the page. 0.0 (a no-op) if the page is already straight, or if too few reliable
    long edges were found to trust an estimate — this check is itself fallible (same reasoning as
    a `format_only` gate) and must default to doing nothing, not to guessing.
    """
    import cv2
    import numpy as np

    rgb = np.asarray(image.convert("RGB"))
    width = image.width
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, CANNY_LOW, CANNY_HIGH, apertureSize=3)
    min_length = max(1, int(width * MIN_LINE_LENGTH_FRACTION))
    segments = cv2.HoughLinesP(
        edges,
        1,
        np.pi / 720,
        threshold=HOUGH_THRESHOLD,
        minLineLength=min_length,
        maxLineGap=MAX_LINE_GAP,
    )

    angles: list[float] = []
    if segments is not None:
        for segment in segments:
            x1, y1, x2, y2 = segment[0]
            angle = float(np.degrees(np.arctan2(y2 - y1, x2 - x1)))
            while angle <= -90.0:
                angle += 180.0
            while angle > 90.0:
                angle -= 180.0
            if -ANGLE_BAND_DEGREES < angle <= ANGLE_BAND_DEGREES:
                angles.append(angle)

    if len(angles) < MIN_QUALIFYING_LINES:
        return 0.0

    median = float(np.median(angles))
    if abs(median) < NOOP_THRESHOLD_DEGREES or abs(median) > MAX_CORRECTION_DEGREES:
        return 0.0
    return median


def rotate_image(image: Image.Image, angle_degrees: float) -> Image.Image:
    """Level the page by ``angle_degrees`` (the value ``estimate_skew_degrees`` returns).
    A no-op — same object back, no resample, no re-encode — when the angle is exactly 0.0,
    so an already-straight page is untouched: no interpolation blur, no risk to OCR accuracy.
    """
    if angle_degrees == 0.0:
        return image
    return image.convert("RGB").rotate(
        angle_degrees,
        resample=Image.Resampling.BICUBIC,
        expand=False,
        fillcolor="white",
    )


def map_bbox_to_original(
    bbox: tuple[float, float, float, float],
    angle_degrees: float,
    width: int,
    height: int,
) -> tuple[float, float, float, float]:
    """Map a normalised bbox read off the deskewed image back onto the original (pre-rotation)
    image's coordinate space, so a highlight still lands on the right spot in the raw upload the
    frontend displays — `rotate_image` never touches that file (INV-3), only what OCR reads.

    Identity when ``angle_degrees`` is 0.0. Otherwise takes the bbox's four corners, applies the
    inverse of the rotation `rotate_image` applied, and returns the axis-aligned box around the
    four mapped corners — a slightly looser box than the true rotated quadrilateral, since
    EXTRACTION_SCHEMA.json's bbox is axis-aligned only, but tight for the small angles this stage
    ever produces.
    """
    if angle_degrees == 0.0:
        return bbox

    import cv2
    import numpy as np

    x0, y0, x1, y1 = bbox
    corners = np.array(
        [
            [x0 * width, y0 * height, 1.0],
            [x1 * width, y0 * height, 1.0],
            [x1 * width, y1 * height, 1.0],
            [x0 * width, y1 * height, 1.0],
        ]
    )
    center = (width / 2.0, height / 2.0)
    inverse = cv2.getRotationMatrix2D(center, -angle_degrees, 1.0)
    mapped = corners @ inverse.T

    xs = mapped[:, 0]
    ys = mapped[:, 1]
    return (
        _clamp01(float(xs.min()) / width),
        _clamp01(float(ys.min()) / height),
        _clamp01(float(xs.max()) / width),
        _clamp01(float(ys.max()) / height),
    )
