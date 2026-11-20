# ==========================================================
# ArchitectOS Image Preview Source v1
#
# IMAGE_TO_IMAGE_05 — TEST-RENDER BUDGET POLICY (CODE ENFORCED)
#
# Why this exists
#   The instruction "use preview" was not enough. Functional
#   acceptance renders kept running at the FULL production source
#   resolution (768x704) with raised step counts, which made an
#   AMD/ZLUDA run take ~13 minutes. A written policy that lives only
#   in a document cannot prevent that; this module makes it code.
#
# What it does
#   Creates a TEMPORARY, downscaled working copy of a source image
#   for functional/test renders:
#     - the ORIGINAL asset is opened read-only and never modified
#     - aspect ratio is preserved
#     - the long edge is clamped to the approved preview band
#       (384 - 512 px)
#     - the image is never upscaled
#     - there is no upscale pass and no second quality pass
#     - the preview lives beside the ComfyUI input copy, outside the
#       canonical workflow JSON (LoadImage only ever reads a filename)
#
# Implementation notes
#   - No new dependency: uses numpy (already in requirements.txt)
#     plus the standard library (zlib) for PNG encode/decode.
#   - Pillow is used automatically when present, for speed and for
#     non-PNG formats.
#   - Decoding is deliberately narrow and truthful: 8/16-bit
#     non-interlaced PNG in grey / grey+alpha / palette / RGB / RGBA.
#     Anything else raises, and the caller must fall back to the
#     original source and record `preview_available: false`.
# ==========================================================


from __future__ import annotations


import os
import struct
import zlib


try:

    import numpy as _np

except Exception:  # pragma: no cover - numpy is a declared dependency

    _np = None


CONTRACT = "ImagePreviewV1"
VERSION = "1.0"


# Approved preview long-edge band.
PREVIEW_LONG_EDGE_MIN = 384
PREVIEW_LONG_EDGE_MAX = 512
PREVIEW_LONG_EDGE_DEFAULT = 448


# VAE stride safety: derived edges are rounded to a multiple of this.
LATENT_ALIGNMENT = 8


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


# I2I_JPEG_PREVIEW_SAFE_STAGING_V1 — JPEG sources are decoded with the
# already-installed Pillow and re-emitted through the SAME area-resize and
# PNG writer used for PNG sources. No new engine, no extra formats.
JPEG_SIGNATURE = b"\xff\xd8\xff"


# Preview outcomes where the ORIGINAL is already safe to send, so the
# absence of a working copy is not a staging failure.
PREVIEW_NOT_REQUIRED = ("source_already_at_or_below_preview_size",)


# ==========================================================
# SIZE HELPERS
# ==========================================================

def clamp_long_edge(value):

    try:

        value = int(value)

    except (TypeError, ValueError):

        return PREVIEW_LONG_EDGE_DEFAULT

    if value < PREVIEW_LONG_EDGE_MIN:

        return PREVIEW_LONG_EDGE_MIN

    if value > PREVIEW_LONG_EDGE_MAX:

        return PREVIEW_LONG_EDGE_MAX

    return value


def _align(value):

    """Round to the nearest latent-safe multiple (minimum one block)."""

    aligned = int(round(float(value) / LATENT_ALIGNMENT)) * LATENT_ALIGNMENT

    return max(LATENT_ALIGNMENT, aligned)


def plan_preview_size(width, height, long_edge=None):

    """Deterministic preview geometry. Never upscales."""

    width = int(width)
    height = int(height)

    if width <= 0 or height <= 0:

        raise ValueError("invalid source dimensions")

    target = clamp_long_edge(long_edge)

    if width >= height:

        out_w = target

        out_h = _align(height * target / float(width))

    else:

        out_h = target

        out_w = _align(width * target / float(height))

    out_w = max(LATENT_ALIGNMENT, min(out_w, width))
    out_h = max(LATENT_ALIGNMENT, min(out_h, height))

    return {

        "contract": CONTRACT,
        "version": VERSION,

        "original_width": width,
        "original_height": height,

        "preview_width": out_w,
        "preview_height": out_h,

        "long_edge": target,

        "aspect_ratio_preserved": (
            abs(
                (out_w / float(out_h))
                - (width / float(height))
            )
            < 0.05
        ),

        "downscaled": (out_w < width or out_h < height),

        "upscaled": False,

        "latent_alignment": LATENT_ALIGNMENT,

    }


# ==========================================================
# PNG DECODE  (stdlib + numpy)
# ==========================================================

def _channels_for_color_type(color_type):

    return {
        0: 1,   # greyscale
        2: 3,   # RGB
        3: 1,   # palette index
        4: 2,   # greyscale + alpha
        6: 4,   # RGBA
    }.get(color_type)


def read_png(path):

    """Decode a non-interlaced PNG into (array HxWxC uint8, mode)."""

    if _np is None:  # pragma: no cover

        raise RuntimeError("numpy_required")

    with open(path, "rb") as handle:

        data = handle.read()

    if data[:8] != PNG_SIGNATURE:

        raise ValueError("not_a_png")

    pos = 8

    header = None
    palette = None
    idat = []

    while pos + 8 <= len(data):

        (length,) = struct.unpack(">I", data[pos:pos + 4])

        chunk_type = data[pos + 4:pos + 8]

        body = data[pos + 8:pos + 8 + length]

        pos += 12 + length  # length + type + body + crc

        if chunk_type == b"IHDR":

            header = struct.unpack(">IIBBBBB", body[:13])

        elif chunk_type == b"PLTE":

            palette = _np.frombuffer(body, dtype=_np.uint8).reshape(-1, 3)

        elif chunk_type == b"IDAT":

            idat.append(body)

        elif chunk_type == b"IEND":

            break

    if header is None:

        raise ValueError("png_missing_ihdr")

    width, height, bit_depth, color_type, compression, filter_method, interlace = header

    if interlace != 0:

        raise ValueError("interlaced_png_unsupported")

    if compression != 0 or filter_method != 0:

        raise ValueError("png_compression_unsupported")

    channels = _channels_for_color_type(color_type)

    if channels is None:

        raise ValueError("png_color_type_unsupported")

    if bit_depth not in (8, 16):

        raise ValueError("png_bit_depth_unsupported")

    sample_bytes = bit_depth // 8

    bytes_per_pixel = channels * sample_bytes

    raw = zlib.decompress(b"".join(idat))

    stride = width * bytes_per_pixel

    expected = (stride + 1) * height

    if len(raw) < expected:

        raise ValueError("png_truncated")

    out = _np.zeros((height, stride), dtype=_np.uint8)

    previous = _np.zeros(stride, dtype=_np.uint8)

    offset = 0

    for row in range(height):

        filter_type = raw[offset]

        offset += 1

        line = _np.frombuffer(
            raw[offset:offset + stride], dtype=_np.uint8
        ).astype(_np.int16)

        offset += stride

        recon = _unfilter(filter_type, line, previous, bytes_per_pixel, stride)

        out[row] = recon.astype(_np.uint8)

        previous = out[row]

    array = out.reshape(height, width, bytes_per_pixel)

    if bit_depth == 16:

        array = array.reshape(height, width, channels, 2)[:, :, :, 0]

    if color_type == 3:

        if palette is None:

            raise ValueError("png_palette_missing")

        array = palette[array.reshape(height, width)]

        mode = "RGB"

    else:

        mode = {1: "L", 2: "LA", 3: "RGB", 4: "RGBA"}[channels]

    return array, mode


def _unfilter(filter_type, line, previous, bpp, stride):

    if filter_type == 0:

        return line

    if filter_type == 1:  # Sub

        out = line.copy()

        for i in range(bpp, stride):

            out[i] = (out[i] + out[i - bpp]) & 0xFF

        return out

    if filter_type == 2:  # Up

        return (line + previous.astype(_np.int16)) & 0xFF

    if filter_type == 3:  # Average

        out = line.copy()

        for i in range(stride):

            left = int(out[i - bpp]) if i >= bpp else 0

            out[i] = (out[i] + ((left + int(previous[i])) >> 1)) & 0xFF

        return out

    if filter_type == 4:  # Paeth

        out = line.copy()

        prev = previous.astype(_np.int16)

        for i in range(stride):

            a = int(out[i - bpp]) if i >= bpp else 0

            b = int(prev[i])

            c = int(prev[i - bpp]) if i >= bpp else 0

            p = a + b - c

            pa = abs(p - a)
            pb = abs(p - b)
            pc = abs(p - c)

            if pa <= pb and pa <= pc:

                pr = a

            elif pb <= pc:

                pr = b

            else:

                pr = c

            out[i] = (out[i] + pr) & 0xFF

        return out

    raise ValueError("png_filter_unsupported")


# ==========================================================
# PNG ENCODE
# ==========================================================

def write_png(path, array, mode):

    if _np is None:  # pragma: no cover

        raise RuntimeError("numpy_required")

    array = _np.ascontiguousarray(array, dtype=_np.uint8)

    height, width = array.shape[0], array.shape[1]

    color_type = {"L": 0, "LA": 4, "RGB": 2, "RGBA": 6}[mode]

    channels = {"L": 1, "LA": 2, "RGB": 3, "RGBA": 4}[mode]

    flat = array.reshape(height, width * channels)

    raw = bytearray()

    for row in range(height):

        raw.append(0)  # filter type 0 (None)

        raw.extend(flat[row].tobytes())

    def chunk(tag, payload):

        return (
            struct.pack(">I", len(payload))
            + tag
            + payload
            + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(
        ">IIBBBBB", width, height, 8, color_type, 0, 0, 0
    )

    body = (
        PNG_SIGNATURE
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 6))
        + chunk(b"IEND", b"")
    )

    with open(path, "wb") as handle:

        handle.write(body)

    return {"width": width, "height": height, "mode": mode}


# ==========================================================
# RESIZE
# ==========================================================

def _reduce_axis(array, out_len, axis):

    """Area-average resize along one axis."""

    length = array.shape[axis]

    edges = _np.linspace(0.0, float(length), out_len + 1)

    starts = _np.clip(_np.floor(edges[:-1]).astype(int), 0, length - 1)

    ends = _np.clip(_np.ceil(edges[1:]).astype(int), 1, length)

    ends = _np.maximum(ends, starts + 1)

    out_shape = list(array.shape)
    out_shape[axis] = out_len

    out = _np.zeros(out_shape, dtype=_np.float64)

    work = array.astype(_np.float64)

    for index in range(out_len):

        selector = [slice(None)] * array.ndim
        selector[axis] = slice(int(starts[index]), int(ends[index]))

        averaged = work[tuple(selector)].mean(axis=axis)

        target = [slice(None)] * array.ndim
        target[axis] = index

        out[tuple(target)] = averaged

    return out


def resize_area(array, out_width, out_height):

    reduced = _reduce_axis(array, out_height, 0)

    reduced = _reduce_axis(reduced, out_width, 1)

    return _np.clip(_np.rint(reduced), 0, 255).astype(_np.uint8)


# ==========================================================
# PUBLIC ENTRY POINT
# ==========================================================

def _jpeg_display_size(path):

    """Displayed (width, height) of a JPEG, honouring EXIF orientation.

    Header-only: does not decode the pixel data.
    """

    from PIL import Image

    with Image.open(path) as image:

        width, height = image.size

        try:

            orientation = image.getexif().get(274)

        except Exception:

            orientation = None

    # Orientations 5-8 rotate by 90/270 degrees, swapping the axes.
    if orientation in (5, 6, 7, 8):

        width, height = height, width

    return width, height


def _read_jpeg_rgb(path):

    """Decode a JPEG to an HxWx3 uint8 RGB array, EXIF-upright."""

    if _np is None:  # pragma: no cover

        raise RuntimeError("numpy_required")

    from PIL import Image, ImageOps

    with Image.open(path) as image:

        upright = ImageOps.exif_transpose(image)

        rgb = upright.convert("RGB")

        array = _np.asarray(rgb, dtype=_np.uint8)

    if array.ndim != 3 or array.shape[2] != 3:

        raise ValueError("jpeg_decode_failed")

    return array, "RGB"


def make_preview(
    source_path,
    target_dir,
    long_edge=None,
    filename=None,
):

    """Create a downscaled working copy. The original is never touched.

    Returns a contract dict. On any failure the caller must fall back
    to the original source and record `preview_available: false`.
    """

    result = {

        "contract": CONTRACT,
        "version": VERSION,

        "preview_available": False,
        "preview_reason": None,

        "original_source_path": source_path,
        "working_preview_path": None,

        "original_dimensions": None,
        "working_dimensions": None,

        "long_edge": clamp_long_edge(long_edge),

        "downscaled": False,
        "upscaled": False,

        "aspect_ratio_preserved": None,

        "original_preserved": False,
    }

    if not source_path or not os.path.isfile(source_path):

        result["preview_reason"] = "source_missing"

        return result

    try:

        with open(source_path, "rb") as handle:

            head = handle.read(24)

        is_png = head[:8] == PNG_SIGNATURE
        is_jpeg = head[:3] == JPEG_SIGNATURE

        if not is_png and not is_jpeg:

            result["preview_reason"] = "unsupported_format"

            return result

        if is_png:

            width = int.from_bytes(head[16:20], "big")
            height = int.from_bytes(head[20:24], "big")

        else:

            # JPEG dimensions come from the decoder, and EXIF orientation
            # may swap them: plan against the DISPLAYED aspect ratio.
            width, height = _jpeg_display_size(source_path)

        result["original_dimensions"] = [width, height]

        plan = plan_preview_size(width, height, long_edge)

        if not plan["downscaled"]:

            result["preview_reason"] = "source_already_at_or_below_preview_size"

            result["working_dimensions"] = [width, height]

            result["aspect_ratio_preserved"] = True

            return result

        if is_png:

            array, mode = read_png(source_path)

        else:

            array, mode = _read_jpeg_rgb(source_path)

        resized = resize_area(
            array, plan["preview_width"], plan["preview_height"]
        )

        os.makedirs(target_dir, exist_ok=True)

        if not filename:

            stem = os.path.splitext(os.path.basename(source_path))[0]

            filename = (
                stem
                + "_preview_"
                + str(plan["preview_width"])
                + "x"
                + str(plan["preview_height"])
                + ".png"
            )

        target = os.path.join(target_dir, filename)

        write_png(target, resized, mode)

        result.update({

            "preview_available": True,
            "preview_reason": "downscaled_working_copy",

            "working_preview_path": target,

            "working_dimensions": [
                plan["preview_width"], plan["preview_height"]
            ],

            "downscaled": True,

            "aspect_ratio_preserved": plan["aspect_ratio_preserved"],

            "original_preserved": True,
        })

        return result

    except Exception as error:

        result["preview_reason"] = type(error).__name__ + ": " + str(error)

        return result


def is_preview_usable(preview):

    return bool(
        isinstance(preview, dict)
        and preview.get("preview_available")
        and preview.get("working_preview_path")
        and os.path.isfile(preview["working_preview_path"])
    )
