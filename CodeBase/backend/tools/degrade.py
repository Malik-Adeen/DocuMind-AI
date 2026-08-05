from __future__ import annotations

import argparse
import io
import random
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter

WORST_LEVEL = 5
SOURCE_DPI = 300
PAPER = (255, 255, 255)

LADDER: dict[int, tuple[int, float, float, float, int]] = {
    0: (SOURCE_DPI, 0.0, 0.0, 1.00, 100),
    1: (300, 0.30, 0.30, 0.95, 85),
    2: (240, 0.70, 0.50, 0.88, 70),
    3: (200, 1.20, 0.80, 0.80, 55),
    4: (150, 1.80, 1.10, 0.72, 42),
    5: (110, 2.50, 1.50, 0.62, 30),
}

SKEW_SPREAD = 0.15
BLUR_SPREAD = 0.10
CONTRAST_SPREAD = 0.02
QUALITY_SPREAD = 4


@dataclass(frozen=True, slots=True)
class Degradation:
    level: int
    dpi: int
    skew_degrees: float
    blur_radius: float
    contrast: float
    jpeg_quality: int


def plan(level: int, *, seed: int) -> Degradation:
    if level not in LADDER:
        raise ValueError(f"level must be 0..{WORST_LEVEL}, got {level}")

    dpi, skew, blur, contrast, quality = LADDER[level]
    if level == 0:
        return Degradation(0, dpi, 0.0, 0.0, 1.0, 100)

    rng = random.Random(f"{seed}:{level}")
    sign = 1.0 if rng.random() < 0.5 else -1.0
    return Degradation(
        level=level,
        dpi=dpi,
        skew_degrees=sign * skew * (1.0 + rng.uniform(-SKEW_SPREAD, SKEW_SPREAD)),
        blur_radius=blur * (1.0 + rng.uniform(-BLUR_SPREAD, BLUR_SPREAD)),
        contrast=contrast * (1.0 + rng.uniform(-CONTRAST_SPREAD, CONTRAST_SPREAD)),
        jpeg_quality=quality + rng.randint(-QUALITY_SPREAD, QUALITY_SPREAD),
    )


def apply(image: Image.Image, spec: Degradation, *, source_dpi: int = SOURCE_DPI) -> Image.Image:
    if spec.level == 0:
        return image.copy()

    working = image.convert("RGB")

    if spec.skew_degrees:
        working = working.rotate(
            spec.skew_degrees,
            resample=Image.Resampling.BICUBIC,
            expand=False,
            fillcolor=PAPER,
        )

    if spec.contrast != 1.0:
        working = ImageEnhance.Contrast(working).enhance(spec.contrast)

    if spec.blur_radius:
        working = working.filter(ImageFilter.GaussianBlur(spec.blur_radius))

    if spec.dpi < source_dpi:
        scale = spec.dpi / source_dpi
        width = max(1, round(working.width * scale))
        height = max(1, round(working.height * scale))
        working = working.resize((width, height), Image.Resampling.LANCZOS)

    buffer = io.BytesIO()
    working.save(buffer, format="JPEG", quality=spec.jpeg_quality, subsampling=2)
    buffer.seek(0)
    with Image.open(buffer) as encoded:
        return encoded.convert("RGB")


def ladder(
    image: Image.Image,
    *,
    seed: int,
    source_dpi: int = SOURCE_DPI,
) -> list[tuple[Degradation, Image.Image]]:
    return [
        (spec, apply(image, spec, source_dpi=source_dpi))
        for spec in (plan(level, seed=seed) for level in sorted(LADDER))
    ]


def write_ladder(
    image_path: Path,
    out_dir: Path,
    *,
    seed: int,
    source_dpi: int = SOURCE_DPI,
) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    with Image.open(image_path) as original:
        for spec, degraded in ladder(original, seed=seed, source_dpi=source_dpi):
            target = out_dir / f"{image_path.stem}.L{spec.level}.png"
            degraded.save(target, format="PNG", dpi=(spec.dpi, spec.dpi))
            written.append(target)
    return written


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Synthesise a 6-step degradation ladder (L0 original .. L5 worst realistic scan) "
            "from one clean image. Deterministic given --seed."
        )
    )
    parser.add_argument("image", type=Path)
    parser.add_argument("out_dir", type=Path)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--source-dpi", type=int, default=SOURCE_DPI)
    args = parser.parse_args()

    for level in sorted(LADDER):
        spec = plan(level, seed=args.seed)
        print(
            f"L{spec.level}  dpi={spec.dpi:>3}  skew={spec.skew_degrees:+.2f}deg  "
            f"blur={spec.blur_radius:.2f}px  contrast={spec.contrast:.3f}  "
            f"jpeg_q={spec.jpeg_quality}"
        )

    for path in write_ladder(args.image, args.out_dir, seed=args.seed, source_dpi=args.source_dpi):
        print(path)


if __name__ == "__main__":
    main()
