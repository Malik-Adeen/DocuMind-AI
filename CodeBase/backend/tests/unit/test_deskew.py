from __future__ import annotations

from app.pipeline.ocr.deskew import (
    MIN_QUALIFYING_LINES,
    estimate_skew_degrees,
    map_bbox_to_original,
    rotate_image,
)

WIDTH, HEIGHT = 800, 600


def ruled_image(angle_degrees: float = 0.0):
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (WIDTH, HEIGHT), "white")
    draw = ImageDraw.Draw(image)
    for y in range(80, HEIGHT - 80, 60):
        draw.line([(60, y), (WIDTH - 60, y)], fill="black", width=3)
    for x in range(120, WIDTH - 120, 140):
        draw.line([(x, 60), (x, HEIGHT - 60)], fill="black", width=2)
    if angle_degrees:
        image = image.rotate(angle_degrees, resample=Image.Resampling.BICUBIC, fillcolor="white")
    return image


def blank_image():
    from PIL import Image

    return Image.new("RGB", (WIDTH, HEIGHT), "white")


def test_blank_page_is_a_noop() -> None:
    assert estimate_skew_degrees(blank_image()) == 0.0


def test_straight_ruled_page_is_a_noop() -> None:
    assert estimate_skew_degrees(ruled_image(0.0)) == 0.0


def test_a_known_rotation_is_detected_with_the_correcting_sign() -> None:
    skewed = ruled_image(3.0)
    angle = estimate_skew_degrees(skewed)
    assert angle != 0.0
    # rotate_image(angle) must level the page again — verified by re-estimating the residual.
    corrected = rotate_image(skewed, angle)
    residual = estimate_skew_degrees(corrected)
    assert abs(residual) < abs(angle)


def test_estimate_is_symmetric_in_rotation_direction() -> None:
    positive = estimate_skew_degrees(ruled_image(2.0))
    negative = estimate_skew_degrees(ruled_image(-2.0))
    assert positive != 0.0
    assert negative != 0.0
    assert (positive > 0) != (negative > 0)


def test_too_few_lines_is_a_noop() -> None:
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (WIDTH, HEIGHT), "white")
    draw = ImageDraw.Draw(image)
    draw.line([(100, 100), (150, 108)], fill="black", width=2)
    assert MIN_QUALIFYING_LINES > 1
    assert estimate_skew_degrees(image) == 0.0


def test_rotate_image_is_a_true_noop_at_zero_degrees() -> None:
    image = ruled_image(0.0)
    assert rotate_image(image, 0.0) is image


def test_rotate_image_actually_rotates_at_a_nonzero_angle() -> None:
    image = ruled_image(0.0)
    rotated = rotate_image(image, 5.0)
    assert rotated is not image
    assert rotated.size == image.size


def test_map_bbox_to_original_is_identity_at_zero_degrees() -> None:
    bbox = (0.1, 0.2, 0.4, 0.5)
    assert map_bbox_to_original(bbox, 0.0, WIDTH, HEIGHT) == bbox


def test_map_bbox_to_original_inverts_the_forward_rotation_at_point_level() -> None:
    # A degenerate (zero-area) bbox is a single point, so bbox-of-corners looseness cannot
    # contaminate this check — it isolates the inverse transform's own correctness.
    import cv2

    angle = 4.0
    px, py = 0.35 * WIDTH, 0.42 * HEIGHT
    center = (WIDTH / 2.0, HEIGHT / 2.0)
    forward = cv2.getRotationMatrix2D(center, angle, 1.0)
    fx, fy = forward @ (px, py, 1.0)
    deskewed_point_bbox = (fx / WIDTH, fy / HEIGHT, fx / WIDTH, fy / HEIGHT)

    recovered = map_bbox_to_original(deskewed_point_bbox, angle, WIDTH, HEIGHT)

    assert abs(recovered[0] - px / WIDTH) < 1e-6
    assert abs(recovered[1] - py / HEIGHT) < 1e-6
    assert recovered[0] == recovered[2]
    assert recovered[1] == recovered[3]


def test_map_bbox_to_original_recovers_a_whole_bbox_within_its_rotation_inflation() -> None:
    # Round-tripping a whole (non-degenerate) bbox through two "axis-aligned box around the
    # rotated corners" steps inflates it slightly — bounded by the box's own diagonal overhang
    # at this angle, not by an unrelated tolerance pulled out of the air.
    import math

    import cv2
    import numpy as np

    angle = 4.0
    original_bbox = (0.3, 0.2, 0.5, 0.3)
    x0, y0, x1, y1 = original_bbox
    corners = np.array(
        [
            [x0 * WIDTH, y0 * HEIGHT, 1.0],
            [x1 * WIDTH, y0 * HEIGHT, 1.0],
            [x1 * WIDTH, y1 * HEIGHT, 1.0],
            [x0 * WIDTH, y1 * HEIGHT, 1.0],
        ]
    )
    center = (WIDTH / 2.0, HEIGHT / 2.0)
    forward = cv2.getRotationMatrix2D(center, angle, 1.0)
    mapped = corners @ forward.T
    deskewed_bbox = (
        float(mapped[:, 0].min()) / WIDTH,
        float(mapped[:, 1].min()) / HEIGHT,
        float(mapped[:, 0].max()) / WIDTH,
        float(mapped[:, 1].max()) / HEIGHT,
    )

    recovered = map_bbox_to_original(deskewed_bbox, angle, WIDTH, HEIGHT)

    box_w_px = (x1 - x0) * WIDTH
    box_h_px = (y1 - y0) * HEIGHT
    theta = math.radians(angle)
    max_overhang_px = box_w_px * abs(math.sin(theta)) + box_h_px * abs(math.sin(theta))
    tolerance = (max_overhang_px + 1.0) / min(WIDTH, HEIGHT)

    for original, got in zip(original_bbox, recovered, strict=True):
        assert abs(original - got) < tolerance


def test_map_bbox_to_original_stays_within_bounds() -> None:
    bbox = (0.0, 0.0, 1.0, 1.0)
    mapped = map_bbox_to_original(bbox, 8.0, WIDTH, HEIGHT)
    assert all(0.0 <= value <= 1.0 for value in mapped)
