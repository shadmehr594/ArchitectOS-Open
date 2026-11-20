"""R4-PHOTO-01 — synthetic acceptance for the bounded photometric utility.

Every test here executes real code on real pixels. Nothing is asserted about
intended behaviour without running it.

The utility is `core/render/photometric_warmth_adjustment_v1.py`. Its contract
is `output[x, y] = clip(round(source[x, y] * gain_channel))` — a per-pixel,
per-channel map with no spatial dependence.
"""

import ast
import hashlib
import os

import pytest
from PIL import Image

from core.render.photometric_warmth_adjustment_v1 import (
    CHANNEL_ORDER,
    GAIN_MAX,
    GAIN_MIN,
    PRESET_WARM_V1,
    adjust_file,
    channel_lut,
    transform_image,
    validate_preset,
)
from core.vision.image_registry_v1 import image_registry

MODULE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "core", "render", "photometric_warmth_adjustment_v1.py",
)

GAINS = PRESET_WARM_V1["gains"]


# ----------------------------------------------------------
# Synthetic fixtures A..F
# ----------------------------------------------------------

def _solid(colour, size=(64, 64)):
    return Image.new("RGB", size, colour)


def fixture_A_neutral_grey():
    return _solid((128, 128, 128))


def fixture_B_warm_brick():
    return _solid((139, 119, 112))


def fixture_C_blue_sky():
    return _solid((150, 180, 230))


def fixture_D_black_and_near_white():
    """Left half pure black, right half near-white — two extreme values."""
    image = Image.new("RGB", (64, 32), (0, 0, 0))
    for x in range(32, 64):
        for y in range(32):
            image.putpixel((x, y), (255, 255, 255))
    return image


def fixture_E_window_grid():
    """A black field with three white 'windows' on a regular grid."""
    image = Image.new("RGB", (180, 120), (0, 0, 0))
    for col in (20, 70, 120):
        for x in range(col, col + 40):
            for y in range(30, 90):
                image.putpixel((x, y), (255, 255, 255))
    return image


def fixture_F_open_passage():
    """A mid-grey wall with a dark passage and a bright rear opening."""
    image = Image.new("RGB", (200, 140), (150, 130, 120))
    # passage void
    for x in range(70, 130):
        for y in range(60, 140):
            image.putpixel((x, y), (40, 38, 36))
    # rear daylight seen through the passage
    for x in range(88, 112):
        for y in range(92, 124):
            image.putpixel((x, y), (235, 240, 245))
    return image


FIXTURES = {
    "A_neutral_grey": fixture_A_neutral_grey,
    "B_warm_brick": fixture_B_warm_brick,
    "C_blue_sky": fixture_C_blue_sky,
    "D_black_near_white": fixture_D_black_and_near_white,
    "E_window_grid": fixture_E_window_grid,
    "F_open_passage": fixture_F_open_passage,
}


def _pixels(image):
    """Raw RGB bytes as triples — avoids the deprecated `getdata()`."""
    raw = image.tobytes()
    return [tuple(raw[i:i + 3]) for i in range(0, len(raw), 3)]


def _edge_columns(image, threshold=32):
    """Column indices where the row-averaged luma jumps sharply."""
    w, h = image.size
    pixels = image.load()
    columns = []
    previous = None
    for x in range(w):
        total = 0.0
        for y in range(h):
            r, g, b = pixels[x, y]
            total += 0.2126 * r + 0.7152 * g + 0.0722 * b
        mean = total / h
        if previous is not None and abs(mean - previous) > threshold:
            columns.append(x)
        previous = mean
    return columns


# ----------------------------------------------------------
# 1 / 2 — dimensions and pixel coordinates
# ----------------------------------------------------------

@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_1_dimensions_unchanged(name):
    source = FIXTURES[name]()
    adjusted, stats = transform_image(source)

    assert adjusted.size == source.size
    assert stats["dimensions"] == list(source.size)
    assert stats["resampled"] is False
    assert stats["spatial_transform"] is False
    assert stats["pixel_coordinates_preserved"] is True


@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_2_pixel_coordinates_unchanged(name):
    """Sharp edges must stay at exactly the same columns."""
    source = FIXTURES[name]()
    adjusted, _stats = transform_image(source)

    assert _edge_columns(adjusted) == _edge_columns(source)


def test_2b_no_output_pixel_depends_on_a_neighbour():
    """`output[x,y]` equals the channel map of `source[x,y]` alone.

    Verified by recomputing every pixel from its own source value and
    comparing to the produced image.
    """
    source = fixture_F_open_passage()
    adjusted, _stats = transform_image(source)

    src = source.load()
    out = adjusted.load()

    for x in range(source.size[0]):
        for y in range(source.size[1]):
            r, g, b = src[x, y]
            expected = (
                channel_lut(GAINS["R"])[r],
                channel_lut(GAINS["G"])[g],
                channel_lut(GAINS["B"])[b],
            )
            assert out[x, y] == expected


# ----------------------------------------------------------
# 3 / 4 / 5 — black, bounds, clipping
# ----------------------------------------------------------

def test_3_black_remains_black():
    source = _solid((0, 0, 0))
    adjusted, stats = transform_image(source)

    assert adjusted.getpixel((0, 0)) == (0, 0, 0)
    assert stats["clipped_total"] == 0


@pytest.mark.parametrize("bad", [
    {"name": "x", "gains": {"R": 1.5, "G": 1.0, "B": 0.5}},
    {"name": "x", "gains": {"R": 1.02, "G": 1.0}},
    {"name": "x", "gains": {"R": "a", "G": 1.0, "B": 0.98}},
    {"name": "x", "gains": None},
])
def test_4_out_of_bounds_or_malformed_presets_are_rejected(bad):
    with pytest.raises(ValueError):
        validate_preset(bad)


def test_4b_declared_preset_is_inside_bounds():
    resolved = validate_preset(PRESET_WARM_V1)

    assert set(resolved["gains"]) == set(CHANNEL_ORDER)
    for channel, gain in resolved["gains"].items():
        assert GAIN_MIN <= gain <= GAIN_MAX


def test_5_clipping_is_measured():
    source = fixture_D_black_and_near_white()
    adjusted, stats = transform_image(source)

    # Pure white * 1.02 exceeds 255 on the red channel only.
    assert stats["clipped"]["R"] == 32 * 32
    assert stats["clipped"]["G"] == 0
    assert stats["clipped"]["B"] == 0
    assert stats["clipped_total"] == 32 * 32
    assert 0.0 < stats["clipped_fraction"] < 1.0

    # Black half unaffected.
    assert adjusted.getpixel((0, 0)) == (0, 0, 0)
    # White half clipped to 255 on red, reduced on blue.
    r, g, b = adjusted.getpixel((63, 31))
    assert (r, g) == (255, 255)
    assert b == 250


# ----------------------------------------------------------
# 6 — the colour shift is warm, and bounded
# ----------------------------------------------------------

def test_6_red_blue_balance_shifts_warm_for_unsaturated_colours():
    for colour in ((139, 119, 112), (150, 180, 230), (128, 128, 128)):
        source = _solid(colour)
        adjusted, _stats = transform_image(source)

        r0, g0, b0 = colour
        r1, g1, b1 = adjusted.getpixel((0, 0))

        assert (r1 / b1) > (r0 / b0), colour
        assert (r1 - b1) > (r0 - b0), colour


def test_6b_the_shift_is_modest_not_a_recolour():
    source = _solid((139, 119, 112))
    adjusted, _stats = transform_image(source)

    r0, g0, b0 = source.getpixel((0, 0))
    r1, g1, b1 = adjusted.getpixel((0, 0))

    # No channel moves by more than the declared gain.
    assert abs(r1 - r0) <= max(1, int(r0 * (GAIN_MAX - 1)) + 1)
    assert abs(b1 - b0) <= max(1, int(b0 * (1 - GAIN_MIN)) + 1)


# ----------------------------------------------------------
# 7 / 8 — no new shapes, no moved edges
# ----------------------------------------------------------

def test_7_no_new_shapes_are_generated():
    source = fixture_E_window_grid()
    adjusted, _stats = transform_image(source)

    src = _pixels(source)
    out = _pixels(adjusted)

    assert len(src) == len(out)

    # A black/white grid stays a black/white grid: every pixel keeps its
    # class, so no new shape can appear.
    for index, (a, b) in enumerate(zip(src, out)):
        src_class = "dark" if max(a) < 128 else "light"
        out_class = "dark" if max(b) < 128 else "light"
        assert src_class == out_class, index


def test_8_edge_coordinates_do_not_move():
    for fixture in (fixture_E_window_grid, fixture_F_open_passage):
        source = fixture()
        adjusted, _stats = transform_image(source)

        assert _edge_columns(adjusted) == _edge_columns(source)


# ----------------------------------------------------------
# 9 / 10 / 11 / 12 — file level
# ----------------------------------------------------------

def test_9_same_input_and_preset_are_byte_identical(tmp_path):
    source = tmp_path / "source.png"
    fixture_F_open_passage().save(source)

    out_a = tmp_path / "a.png"
    out_b = tmp_path / "b.png"

    first = adjust_file(source, out_a)
    second = adjust_file(source, out_b)

    assert first["status"] == second["status"] == "ok"
    assert first["output"]["sha256"] == second["output"]["sha256"]
    assert out_a.read_bytes() == out_b.read_bytes()


def test_10_input_file_remains_unchanged(tmp_path):
    source = tmp_path / "source.png"
    fixture_B_warm_brick().save(source)

    before = hashlib.sha256(source.read_bytes()).hexdigest()

    result = adjust_file(source, tmp_path / "out.png")

    after = hashlib.sha256(source.read_bytes()).hexdigest()

    assert result["status"] == "ok"
    assert before == after
    assert result["source"]["unchanged"] is True
    assert result["source"]["sha256_before"] == result["source"]["sha256_after"]


def test_11_invalid_paths_fail_safely(tmp_path):
    missing = adjust_file(tmp_path / "nope.png", tmp_path / "out.png")

    assert missing["status"] == "source_not_found"
    assert missing["output_written"] is False

    empty = adjust_file("", tmp_path / "out.png")
    assert empty["status"] == "source_not_found"

    no_output = adjust_file(tmp_path / "nope.png", "")
    assert no_output["status"] in ("source_not_found", "output_path_missing")


def test_11b_unreadable_file_is_reported_not_raised(tmp_path):
    broken = tmp_path / "broken.png"
    broken.write_bytes(b"not a png")

    result = adjust_file(broken, tmp_path / "out.png")

    assert result["status"] == "unreadable_image"
    assert result["output_written"] is False


def test_12_unsupported_modes_are_handled_explicitly(tmp_path):
    rgba = tmp_path / "rgba.png"
    Image.new("RGBA", (16, 16), (10, 20, 30, 255)).save(rgba)

    result = adjust_file(rgba, tmp_path / "out.png")

    assert result["status"] == "unsupported_mode"
    assert result["mode"] == "RGBA"
    assert result["output_written"] is False

    with pytest.raises(ValueError):
        transform_image(Image.new("L", (8, 8), 128))

    with pytest.raises(ValueError):
        transform_image(None)


def test_12b_existing_output_is_not_overwritten(tmp_path):
    source = tmp_path / "source.png"
    fixture_A_neutral_grey().save(source)

    existing = tmp_path / "out.png"
    existing.write_bytes(b"keep me")

    result = adjust_file(source, existing)

    assert result["status"] == "output_exists"
    assert existing.read_bytes() == b"keep me"


# ----------------------------------------------------------
# 13 / 14 — no registry entry, no model/GPU/network boundary
# ----------------------------------------------------------

def test_13_no_image_registry_entry_is_created(tmp_path):
    session = "r4-photo-01-dry-run"

    before = len(image_registry.list(session) or [])

    source = tmp_path / "source.png"
    fixture_C_blue_sky().save(source)

    result = adjust_file(source, tmp_path / "out.png")

    after = len(image_registry.list(session) or [])

    assert result["status"] == "ok"
    assert before == after == 0


def test_14_no_model_gpu_or_network_dependency(monkeypatch, tmp_path):
    """The module must not import or reach any model/GPU/network owner."""

    tree = ast.parse(open(MODULE_PATH, encoding="utf-8").read())

    imported = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported.add(node.module.split(".")[0])

    # `math` was added by R4_PHOTO_SOURCE_SAFETY_V1 for `math.isfinite`, the
    # explicit non-finite gain check (DEFECT C). It is stdlib arithmetic, not a
    # model, network or imaging dependency.
    assert imported <= {"hashlib", "math", "os", "time", "PIL", "__future__"}, imported

    # And the boundary owners must remain unreachable during a run.
    def _forbidden(*_a, **_k):
        raise AssertionError("model/GPU boundary crossed by a photometric edit")

    import core.render.workflow_executor as workflow_executor
    import core.runtime.gpu_handoff_v1 as gpu_handoff

    monkeypatch.setattr(workflow_executor.WorkflowExecutor, "execute", _forbidden)
    monkeypatch.setattr(gpu_handoff, "require_render_vram", _forbidden)
    monkeypatch.setattr(gpu_handoff, "unload_ollama_models_for_render", _forbidden)
    monkeypatch.setattr(gpu_handoff, "gpu_render_lease", _forbidden)

    source = tmp_path / "source.png"
    fixture_D_black_and_near_white().save(source)

    result = adjust_file(source, tmp_path / "out.png")

    assert result["status"] == "ok"
    assert result["output_written"] is True


def test_14b_source_is_never_opened_for_write(tmp_path):
    """`adjust_file` opens the source read-only and writes only the output."""
    source = tmp_path / "source.png"
    fixture_A_neutral_grey().save(source)

    stat_before = source.stat()

    adjust_file(source, tmp_path / "out.png")

    stat_after = source.stat()

    assert stat_before.st_size == stat_after.st_size
    assert stat_before.st_mtime == stat_after.st_mtime


# ==========================================================
# R4_PHOTO_SOURCE_SAFETY_V1 — source-file integrity
#
# Three defects were reproduced against the previous implementation:
#   A  adjust_file(src, src, overwrite=True) truncated the source
#   B  a hardlink alias of the source was truncated through the "output"
#   C  validate_preset() accepted a NaN gain
# Every test below uses TEMPORARY synthetic images only.
# ==========================================================


def _source_file(tmp_path, name="source.png", colour=(139, 119, 112)):
    path = tmp_path / name
    Image.new("RGB", (32, 32), colour).save(path)
    return path


def _digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_S1_same_path_is_refused_without_overwrite(tmp_path):
    source = _source_file(tmp_path)
    before = _digest(source)

    result = adjust_file(source, source, preset=PRESET_WARM_V1, overwrite=False)

    assert result["status"] == "source_output_conflict"
    assert result["reason"] == "same_path"
    assert result["output_written"] is False
    assert _digest(source) == before


def test_S2_same_path_is_refused_even_with_overwrite(tmp_path):
    """DEFECT A — `overwrite=True` must not authorise writing onto the source."""

    source = _source_file(tmp_path)
    before = _digest(source)

    result = adjust_file(source, source, preset=PRESET_WARM_V1, overwrite=True)

    assert result["status"] == "source_output_conflict"
    assert result["reason"] == "same_path"
    assert result["output_written"] is False
    assert _digest(source) == before
    assert result["source_sha256"] == before


def test_S3_relative_and_absolute_alias_is_refused(tmp_path, monkeypatch):
    source = _source_file(tmp_path)
    before = _digest(source)

    monkeypatch.chdir(tmp_path)

    result = adjust_file(
        str(source.resolve()), "source.png", preset=PRESET_WARM_V1, overwrite=True
    )

    assert result["status"] == "source_output_conflict"
    assert result["reason"] == "same_path"
    assert _digest(source) == before


def test_S4_symlink_alias_is_refused_when_supported(tmp_path):
    """DEFECT B (symlink). Skipped where the platform cannot create a link."""

    source = _source_file(tmp_path)
    link = tmp_path / "alias.png"

    try:
        os.symlink(str(source), str(link))
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation not supported")

    if not os.path.islink(str(link)):
        pytest.skip("symlink creation produced no link on this platform")

    before = _digest(source)

    result = adjust_file(source, link, preset=PRESET_WARM_V1, overwrite=True)

    assert result["status"] == "source_output_conflict"
    assert result["reason"] == "same_file"
    assert result["output_written"] is False
    assert _digest(source) == before


def test_S5_hardlink_alias_is_refused_when_supported(tmp_path):
    """DEFECT B (hardlink) — reproduced against the previous implementation."""

    source = _source_file(tmp_path)
    alias = tmp_path / "hardlink.png"

    try:
        os.link(str(source), str(alias))
    except (OSError, NotImplementedError):
        pytest.skip("hardlink creation not supported")

    assert os.stat(str(source)).st_ino == os.stat(str(alias)).st_ino

    before = _digest(source)

    result = adjust_file(source, alias, preset=PRESET_WARM_V1, overwrite=True)

    assert result["status"] == "source_output_conflict"
    assert result["reason"] == "same_file"
    assert result["via"] == "filesystem_identity"
    assert result["output_written"] is False
    assert _digest(source) == before


@pytest.mark.parametrize("bad_value, label", [
    (float("nan"), "nan"),
    (float("inf"), "+inf"),
    (float("-inf"), "-inf"),
])
def test_S6_non_finite_gains_are_rejected(bad_value, label):
    """DEFECT C — range comparisons alone do not reject NaN."""

    with pytest.raises(ValueError) as error:
        validate_preset(
            {"name": "bad", "gains": {"R": bad_value, "G": 1.0, "B": 0.98}}
        )

    assert "preset_gain_not_finite" in str(error.value), label


def test_S6b_non_finite_gain_never_writes_an_output(tmp_path):
    source = _source_file(tmp_path)
    output = tmp_path / "out.png"
    before = _digest(source)

    result = adjust_file(
        source,
        output,
        preset={"name": "bad", "gains": {"R": float("nan"), "G": 1.0, "B": 0.98}},
    )

    assert result["status"] == "invalid_request"
    assert result["output_written"] is False
    assert not output.exists()
    assert _digest(source) == before


def test_S7_warm_v1_preset_is_unchanged():
    resolved = validate_preset(PRESET_WARM_V1)

    assert resolved["name"] == "warm_v1"
    assert resolved["gains"] == {"R": 1.02, "G": 1.0, "B": 0.98}
    assert PRESET_WARM_V1["gains"] == {"R": 1.02, "G": 1.00, "B": 0.98}


def test_S8_a_distinct_destination_still_works(tmp_path):
    source = _source_file(tmp_path)
    output = tmp_path / "distinct.png"
    before = _digest(source)

    result = adjust_file(source, output, preset=PRESET_WARM_V1)

    assert result["status"] == "ok"
    assert result["output_written"] is True
    assert output.exists()
    assert _digest(source) == before
    assert result["source"]["unchanged"] is True


def test_S9_overwrite_of_a_distinct_destination_is_unchanged_behaviour(tmp_path):
    source = _source_file(tmp_path)
    output = tmp_path / "distinct.png"

    first = adjust_file(source, output, preset=PRESET_WARM_V1)
    assert first["status"] == "ok"

    refused = adjust_file(source, output, preset=PRESET_WARM_V1)
    assert refused["status"] == "output_exists"

    replaced = adjust_file(source, output, preset=PRESET_WARM_V1, overwrite=True)
    assert replaced["status"] == "ok"


def test_S10_path_identity_helper_detects_aliases(tmp_path):
    from core.render.photometric_warmth_adjustment_v1 import path_identity_conflict

    source = _source_file(tmp_path)
    other = _source_file(tmp_path, "other.png", colour=(10, 20, 30))

    assert path_identity_conflict(source, source)["reason"] == "same_path"
    assert path_identity_conflict(source, other) is None


# ==========================================================
# R4-PHOTO-02 — BLUE-RESTRAINED WARMTH
#
# The candidate must warm reddish architectural surfaces more strongly than
# blue-dominant pixels, while remaining a pure per-pixel function.
# ==========================================================


def _p02_preset():
    from core.render.photometric_warmth_adjustment_v1 import (
        PRESET_WARM_BLUE_RESTRAINED_V1,
    )

    return PRESET_WARM_BLUE_RESTRAINED_V1


def _p02(image, preset=None):
    from core.render.photometric_warmth_adjustment_v1 import (
        transform_image_blue_restrained,
    )

    return transform_image_blue_restrained(image, preset or _p02_preset())


P02_FIXTURES = {
    "neutral_grey": lambda: _solid((128, 128, 128)),
    "warm_brick": lambda: _solid((139, 119, 112)),
    "blue_sky": lambda: _solid((196, 197, 205)),
    "blue_glazing": lambda: _solid((60, 90, 140)),
    "dark_passage": lambda: _solid((40, 38, 36)),
    "white_highlight": lambda: _solid((255, 255, 255)),
    "window_grid": fixture_E_window_grid,
    "open_passage": fixture_F_open_passage,
}


@pytest.mark.parametrize("name", sorted(P02_FIXTURES))
def test_P1_every_output_pixel_is_a_function_of_its_own_source_pixel(name):
    source = P02_FIXTURES[name]()
    adjusted, stats = _p02(source)

    assert adjusted.size == source.size
    assert stats["spatial_transform"] is False
    assert stats["resampled"] is False
    assert stats["blue_restrained"] is True

    raw_in = source.tobytes()
    raw_out = adjusted.tobytes()

    preset = _p02_preset()
    gains = preset["gains"]
    threshold = preset["blue_excess_threshold"]
    attenuation = preset["max_blue_attenuation"]

    for index in range(0, len(raw_in), 3):
        r, g, b = raw_in[index], raw_in[index + 1], raw_in[index + 2]
        excess = b - r
        strength = 1.0 if excess <= 0 else 1.0 - attenuation * min(1.0, excess / threshold)
        expected_r = min(255, max(0, int(round(r * (1.0 + (gains["R"] - 1.0) * strength)))))
        expected_g = min(255, max(0, int(round(g * gains["G"]))))
        expected_b = min(255, max(0, int(round(b * (1.0 - (1.0 - gains["B"]) * strength)))))

        assert (raw_out[index], raw_out[index + 1], raw_out[index + 2]) == (
            expected_r, expected_g, expected_b
        ), index


def test_P2_brick_warms_more_strongly_than_sky():
    """The whole point of the candidate: the facade moves more than the sky."""

    brick = (139, 119, 112)
    sky = (196, 197, 205)

    def ratio(rgb):
        return rgb[0] / rgb[2]

    brick_out = _p02(_solid(brick))[0].getpixel((0, 0))
    sky_out = _p02(_solid(sky))[0].getpixel((0, 0))

    brick_gain = ratio(brick_out) / ratio(brick) - 1.0
    sky_gain = ratio(sky_out) / ratio(sky) - 1.0

    assert brick_gain > sky_gain
    assert brick_gain > 2.0 * sky_gain, (brick_gain, sky_gain)


def test_P3_blue_dominant_pixels_are_barely_touched():
    glazing = (60, 90, 140)
    out = _p02(_solid(glazing))[0].getpixel((0, 0))

    assert abs(out[0] - glazing[0]) <= 1
    assert abs(out[2] - glazing[2]) <= 2


def test_P4_uniform_input_stays_uniform_no_seams():
    """A flat region cannot gain structure: identical pixels map identically."""

    source = _solid((150, 130, 120), size=(80, 60))
    adjusted, _stats = _p02(source)

    values = set(
        tuple(adjusted.tobytes()[i:i + 3])
        for i in range(0, len(adjusted.tobytes()), 3)
    )

    assert len(values) == 1


def test_P5_ramp_stays_monotone_no_banding_inversion():
    image = Image.new("RGB", (256, 1))
    for x in range(256):
        image.putpixel((x, 0), (x, 128, 255 - x))

    adjusted, _stats = _p02(image)

    reds = [adjusted.getpixel((x, 0))[0] for x in range(256)]
    blues = [adjusted.getpixel((x, 0))[2] for x in range(256)]

    assert reds == sorted(reds), "red channel must not invert"
    assert blues == sorted(blues, reverse=True), "blue channel must not invert"


def test_P6_determinism_and_dimensions():
    source = fixture_F_open_passage()

    first, _ = _p02(source)
    second, _ = _p02(source)

    assert first.tobytes() == second.tobytes()
    assert first.size == source.size


def test_P7_clipping_is_reported():
    source = _solid((255, 255, 255))
    adjusted, stats = _p02(source)

    # red 255 * 1.04 clips; blue 255 * 0.96 does not.
    assert stats["clipped"]["R"] == 64 * 64
    assert stats["clipped"]["B"] == 0
    assert adjusted.getpixel((0, 0)) == (255, 255, 245)


@pytest.mark.parametrize("bad", [
    {"name": "x", "gains": {"R": 1.04, "G": 1.0, "B": 0.96},
     "blue_excess_threshold": float("nan"), "max_blue_attenuation": 0.9},
    {"name": "x", "gains": {"R": 1.04, "G": 1.0, "B": 0.96},
     "blue_excess_threshold": 12.0, "max_blue_attenuation": float("inf")},
    {"name": "x", "gains": {"R": 1.04, "G": 1.0, "B": 0.96},
     "blue_excess_threshold": 0.0, "max_blue_attenuation": 0.9},
    {"name": "x", "gains": {"R": 1.04, "G": 1.0, "B": 0.96},
     "blue_excess_threshold": 12.0, "max_blue_attenuation": 1.5},
    {"name": "x", "gains": {"R": float("nan"), "G": 1.0, "B": 0.96},
     "blue_excess_threshold": 12.0, "max_blue_attenuation": 0.9},
])
def test_P8_invalid_blue_presets_are_rejected(bad):
    from core.render.photometric_warmth_adjustment_v1 import (
        validate_blue_restrained_preset,
    )

    with pytest.raises(ValueError):
        validate_blue_restrained_preset(bad)


def test_P9_warm_v1_contract_is_untouched():
    """PHOTO-02 must not perturb the accepted v1 behaviour or its preset."""

    assert PRESET_WARM_V1["gains"] == {"R": 1.02, "G": 1.00, "B": 0.98}

    legacy = transform_image(_solid((139, 119, 112)))[0].getpixel((0, 0))
    assert legacy == (142, 119, 110)

    from core.render.photometric_warmth_adjustment_v1 import (
        validate_blue_restrained_preset,
    )

    resolved = validate_blue_restrained_preset(_p02_preset())
    assert resolved["gains"] == {"R": 1.04, "G": 1.0, "B": 0.96}
    assert resolved["blue_excess_threshold"] == 12.0
    assert resolved["max_blue_attenuation"] == 0.9


def test_P10_file_level_run_keeps_the_source(tmp_path):
    from core.render.photometric_warmth_adjustment_v1 import (
        transform_image_blue_restrained,
    )

    source = _source_file(tmp_path)
    before = _digest(source)
    output = tmp_path / "p02.png"

    result = adjust_file(
        source,
        output,
        preset=_p02_preset(),
        transform=transform_image_blue_restrained,
    )

    assert result["status"] == "ok"
    assert result["operation"] == "photometric_warmth_blue_restrained_v1"
    assert output.exists()
    assert _digest(source) == before
