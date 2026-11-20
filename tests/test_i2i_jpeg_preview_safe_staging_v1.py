"""I2I_JPEG_PREVIEW_SAFE_STAGING_V1 — focused regression.

Covers the JPEG working-copy support and the fail-closed staging rule.
No GPU, no ComfyUI POST, no model inference.
"""

import hashlib
import os

import pytest
from PIL import Image

from core.render.image_asset_bridge import ImageAssetBridge
from core.render.image_preview_v1 import PREVIEW_NOT_REQUIRED, make_preview
from core.render.render_draft_v1 import resolve_profile

PHOTO = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "uploads", "chat_media",
    "c4b77de5d388_Gemini_Generated_Image_2cc3us2cc3us2cc3.jpg",
)

pytestmark = pytest.mark.skipif(
    not os.path.isfile(PHOTO), reason="uploaded JPEG fixture not present"
)


def _sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


@pytest.fixture
def preview_profile():
    return resolve_profile(explicit="PREVIEW")


# ---------------------------------------------------------------- preview owner

def test_jpeg_preview_produces_aligned_png(tmp_path):
    result = make_preview(PHOTO, str(tmp_path), long_edge=448,
                          filename="jpeg_working.png")

    assert result["preview_available"] is True
    assert result["preview_reason"] == "downscaled_working_copy"
    assert result["original_dimensions"] == [1792, 2400]
    assert result["working_dimensions"] == [336, 448]
    assert result["downscaled"] is True
    assert result["original_preserved"] is True
    assert result["original_source_path"] == PHOTO

    working = result["working_preview_path"]
    assert os.path.isfile(working)

    with Image.open(working) as image:
        assert image.format == "PNG"
        assert image.size == (336, 448)
        assert image.mode == "RGB"


def test_jpeg_preview_leaves_source_untouched(tmp_path):
    before = _sha(PHOTO)
    before_size = os.path.getsize(PHOTO)

    make_preview(PHOTO, str(tmp_path), long_edge=448, filename="w.png")

    assert _sha(PHOTO) == before
    assert os.path.getsize(PHOTO) == before_size


def test_png_source_behaviour_unchanged(tmp_path):
    source = tmp_path / "source.png"
    Image.new("RGB", (900, 600), (120, 90, 60)).save(source)

    result = make_preview(str(source), str(tmp_path), long_edge=448,
                          filename="png_working.png")

    assert result["preview_available"] is True
    assert result["original_dimensions"] == [900, 600]
    # 448 * 600/900 = 298.67, aligned down to the 8px latent grid.
    assert result["working_dimensions"] == [448, 296]
    with Image.open(result["working_preview_path"]) as image:
        assert image.format == "PNG"
        assert image.size == (448, 296)


def test_unsupported_format_is_still_rejected(tmp_path):
    source = tmp_path / "source.bmp"
    Image.new("RGB", (900, 600), (10, 20, 30)).save(source)

    result = make_preview(str(source), str(tmp_path), long_edge=448,
                          filename="bmp.png")

    assert result["preview_available"] is False
    assert result["preview_reason"] == "unsupported_format"


# ---------------------------------------------------------------- staging owner

def test_staging_binds_preview_png_not_the_jpeg(tmp_path, preview_profile):
    bridge = ImageAssetBridge(comfy_input=str(tmp_path))
    staged = bridge.register("p1", PHOTO, preview=preview_profile)

    assert staged["status"] == "ready"
    assert staged["filename"].startswith("architectos_preview_")
    assert staged["filename"].endswith(".png")
    assert staged["working_dimensions"] == [336, 448]
    # Authoritative asset stays the original copy.
    assert staged["path"].endswith(".jpg")
    assert os.path.isfile(os.path.join(str(tmp_path), staged["filename"]))


def test_staging_accepts_a_profile_name(tmp_path):
    """The Chat route forwards "PREVIEW", not the contract dict."""
    bridge = ImageAssetBridge(comfy_input=str(tmp_path))
    staged = bridge.register("p1", PHOTO, preview="PREVIEW")

    assert staged["status"] == "ready"
    assert staged["filename"].endswith(".png")
    assert staged["working_dimensions"] == [336, 448]


def test_no_profile_means_no_preview_and_no_block(tmp_path):
    bridge = ImageAssetBridge(comfy_input=str(tmp_path))
    staged = bridge.register("p1", PHOTO)

    assert staged["status"] == "ready"
    assert staged["filename"].endswith(".jpg")


def test_small_source_needs_no_preview_and_is_not_blocked(tmp_path):
    source = tmp_path / "small.png"
    Image.new("RGB", (200, 100), (5, 5, 5)).save(source)

    bridge = ImageAssetBridge(comfy_input=str(tmp_path))
    staged = bridge.register("p1", str(source), preview="PREVIEW")

    assert staged["status"] == "ready"
    assert staged["preview"]["preview_reason"] in PREVIEW_NOT_REQUIRED


def test_malformed_image_fails_closed(tmp_path):
    bad = tmp_path / "broken.jpg"
    bad.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 64 + b"not a jpeg")

    bridge = ImageAssetBridge(comfy_input=str(tmp_path))
    staged = bridge.register("p1", str(bad), preview="PREVIEW")

    assert staged["status"] == "error"
    assert staged["message"] == "preview_source_unavailable"
    assert staged["preview_reason"]
    # Nothing a ComfyUI LoadImage could pick up.
    assert not staged["filename"]
    assert not staged["path"]
