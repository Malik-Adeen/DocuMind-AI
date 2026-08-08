from __future__ import annotations

import io

import pytest
from PIL import Image, ImageDraw, ImageFilter, ImageStat

from tools.degrade import (
    LADDER,
    SOURCE_DPI,
    WORST_LEVEL,
    Degradation,
    apply,
    ladder,
    plan,
    write_ladder,
)

LEVELS = tuple(range(WORST_LEVEL + 1))
SEEDS = (0, 1, 7, 42, 1234)


@pytest.fixture
def clean_page() -> Image.Image:
    page = Image.new("RGB", (600, 400), (255, 255, 255))
    draw = ImageDraw.Draw(page)
    for row in range(8):
        top = 20 + row * 45
        draw.rectangle((40, top, 560, top + 6), fill=(0, 0, 0))
        draw.rectangle((40, top + 16, 300, top + 22), fill=(0, 0, 0))
    draw.rectangle((40, 20, 560, 380), outline=(0, 0, 0), width=3)
    return page


def png_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def edge_energy(image: Image.Image, size: tuple[int, int]) -> float:
    resized = image.convert("L").resize(size, Image.Resampling.LANCZOS)
    return ImageStat.Stat(resized.filter(ImageFilter.FIND_EDGES)).stddev[0]


def test_ladder_has_six_steps_zero_to_five(clean_page: Image.Image) -> None:
    steps = ladder(clean_page, seed=0)
    assert [spec.level for spec, _ in steps] == list(LEVELS)


def test_level_zero_is_the_original_untouched(clean_page: Image.Image) -> None:
    spec, image = ladder(clean_page, seed=0)[0]
    assert spec == Degradation(0, SOURCE_DPI, 0.0, 0.0, 1.0, 100)
    assert image.size == clean_page.size
    assert png_bytes(image) == png_bytes(clean_page)


@pytest.mark.parametrize("seed", SEEDS)
def test_same_seed_reproduces_the_ladder_byte_for_byte(clean_page: Image.Image, seed: int) -> None:
    first = [png_bytes(image) for _, image in ladder(clean_page, seed=seed)]
    second = [png_bytes(image) for _, image in ladder(clean_page, seed=seed)]
    assert first == second


@pytest.mark.parametrize("seed", SEEDS)
def test_same_seed_reproduces_the_parameters(seed: int) -> None:
    assert [plan(level, seed=seed) for level in LEVELS] == [
        plan(level, seed=seed) for level in LEVELS
    ]


def test_different_seeds_produce_different_degradations(clean_page: Image.Image) -> None:
    a = [png_bytes(image) for _, image in ladder(clean_page, seed=0)]
    b = [png_bytes(image) for _, image in ladder(clean_page, seed=99)]
    assert a[0] == b[0], "level 0 is the original and must not depend on the seed"
    assert a[1:] != b[1:], "two seeds produced an identical ladder"


@pytest.mark.parametrize("seed", SEEDS)
def test_severity_is_monotonic_across_levels(seed: int) -> None:
    specs = [plan(level, seed=seed) for level in LEVELS]
    for worse, better in zip(specs[1:], specs[:-1], strict=True):
        assert worse.dpi <= better.dpi
        assert worse.blur_radius >= better.blur_radius
        assert worse.contrast <= better.contrast
        assert worse.jpeg_quality <= better.jpeg_quality
        assert abs(worse.skew_degrees) >= abs(better.skew_degrees)


@pytest.mark.parametrize("seed", SEEDS)
def test_the_worst_levels_land_in_the_100_to_150_dpi_band(seed: int) -> None:
    assert 100 <= plan(4, seed=seed).dpi <= 150
    assert 100 <= plan(5, seed=seed).dpi <= 150


@pytest.mark.parametrize("seed", SEEDS)
def test_skew_takes_both_directions_but_never_at_level_zero(seed: int) -> None:
    assert plan(0, seed=seed).skew_degrees == 0.0
    assert all(plan(level, seed=seed).skew_degrees != 0.0 for level in LEVELS[1:])
    signs = {plan(level, seed=s).skew_degrees > 0 for level in LEVELS[1:] for s in SEEDS}
    assert signs == {True, False}, "skew never changes direction across seeds"


def test_downsampling_shrinks_the_page(clean_page: Image.Image) -> None:
    sizes = [image.size for _, image in ladder(clean_page, seed=0)]
    assert sizes[0] == clean_page.size
    assert sizes[1] == clean_page.size, "level 1 stays at source dpi"
    for worse, better in zip(sizes[2:], sizes[1:], strict=False):
        assert worse[0] < better[0] and worse[1] < better[1]


def test_the_worst_level_is_measurably_less_sharp_than_the_original(
    clean_page: Image.Image,
) -> None:
    steps = ladder(clean_page, seed=0)
    reference = clean_page.size
    original = edge_energy(steps[0][1], reference)
    worst = edge_energy(steps[WORST_LEVEL][1], reference)
    assert worst < original * 0.9, f"level 5 edge energy {worst} vs original {original}"


def test_degradation_accumulates_once_blur_dominates(clean_page: Image.Image) -> None:
    reference = clean_page.size
    energies = [edge_energy(image, reference) for _, image in ladder(clean_page, seed=0)]
    assert energies[WORST_LEVEL] == min(energies)
    for worse, better in zip(energies[3:], energies[2:], strict=False):
        assert worse < better


def test_jpeg_ringing_can_raise_edge_energy_at_the_gentlest_levels(
    clean_page: Image.Image,
) -> None:
    reference = clean_page.size
    energies = [edge_energy(image, reference) for _, image in ladder(clean_page, seed=0)]
    assert max(energies) in energies[:3], (
        "edge energy is no longer non-monotonic at the top of the ladder; "
        "if that is intentional, the CER measurement can assume monotone sharpness loss"
    )


def test_mode_and_geometry_survive(clean_page: Image.Image) -> None:
    for _, image in ladder(clean_page, seed=0):
        assert image.mode == "RGB"
        assert image.width > 0 and image.height > 0


def test_source_dpi_drives_the_downsample_ratio(clean_page: Image.Image) -> None:
    spec = plan(WORST_LEVEL, seed=0)
    at_300 = apply(clean_page, spec, source_dpi=300)
    at_600 = apply(clean_page, spec, source_dpi=600)
    assert at_600.width < at_300.width


def test_an_already_low_dpi_source_is_not_upsampled(clean_page: Image.Image) -> None:
    spec = plan(1, seed=0)
    result = apply(clean_page, spec, source_dpi=100)
    assert result.size == clean_page.size


@pytest.mark.parametrize("level", [-1, 6, 100])
def test_a_level_outside_the_ladder_is_rejected(level: int) -> None:
    with pytest.raises(ValueError, match=f"level must be 0..{WORST_LEVEL}"):
        plan(level, seed=0)


def test_every_declared_level_has_a_full_parameter_row() -> None:
    assert sorted(LADDER) == list(LEVELS)
    assert all(len(row) == 5 for row in LADDER.values())


def test_write_ladder_emits_one_png_per_level(clean_page: Image.Image, tmp_path) -> None:  # type: ignore[no-untyped-def]
    source = tmp_path / "invoice.png"
    clean_page.save(source, format="PNG")

    written = write_ladder(source, tmp_path / "out", seed=0)

    assert [path.name for path in written] == [f"invoice.L{level}.png" for level in LEVELS]
    assert all(path.exists() for path in written)
    with Image.open(written[WORST_LEVEL]) as worst:
        assert (
            tuple(round(value) for value in worst.info["dpi"])
            == (plan(WORST_LEVEL, seed=0).dpi,) * 2
        )
