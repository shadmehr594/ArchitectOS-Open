# ==========================================================
# ArchitectOS Photometric Warmth Adjustment v1
#
# R4_PHOTO_01 — BOUNDED NON-GENERATIVE PHOTOMETRIC EDIT
#
# What this is
#   ONE small, deterministic photographic colour operation. It applies a
#   fixed per-channel gain to an already-rendered image using standard
#   Pillow primitives. Nothing else.
#
# What this is NOT
#   Not a renderer, not a diffusion sampler, not a computer-vision engine,
#   not a compositor, not a segmentation or masking system, not a photo
#   editor, and not an alternative to the existing ComfyUI pipeline. It
#   performs no sampling, no inference, no model load and no I/O beyond
#   opening one file and writing one file.
#
# Why the contract is per-pixel
#   The essential difference from diffusion img2img is stated as a
#   mathematical property, not as a promise:
#
#       output[x, y] = clip(round(source[x, y] * gain_channel))
#
#   for EVERY pixel coordinate, with `gain` depending only on the channel.
#   No output pixel depends on any spatially adjacent pixel, so no window
#   mullion can move, no passage can close, and no fixture can be invented.
#   That is guaranteed by construction, not by prompt wording or denoise.
#
# Honest limitation
#   A warmth adjustment deliberately changes RGB values. It does not keep
#   material colour identical, and it is NOT a physically calibrated white
#   balance — no Kelvin value is claimed. It recolours the existing
#   photograph; it does not simulate new light.
# ==========================================================

from __future__ import annotations

import hashlib
import math
import os
import time

from PIL import Image


CONTRACT = "PhotometricWarmthAdjustmentV1"
VERSION = "1.0"

OPERATION = "photometric_warmth_adjustment_v1"

#: Only 8-bit RGB is accepted. Any other mode is refused explicitly rather
#: than silently converted, because a silent conversion changes the source
#: pixel values before the adjustment is even applied.
SUPPORTED_MODES = ("RGB",)

#: Declared gain bounds. A preset outside these bounds is rejected: the point
#: of this capability is a MODEST cast, and an unbounded gain would turn it
#: into a colour replacement.
GAIN_MIN = 0.90
GAIN_MAX = 1.10

#: The single approved preset. These are an initial photographic warm-cast
#: candidate, NOT a calibrated white balance. They are deliberately small.
PRESET_WARM_V1 = {
    "name": "warm_v1",
    "gains": {"R": 1.02, "G": 1.00, "B": 0.98},
}


# ==========================================================
# R4-PHOTO-02 — BLUE-RESTRAINED WARMTH (experimental)
#
# R4-PHOTO-01 measured the problem with a flat warm cast: the facade moved by
# ΔE76 1.67 (below the 2.3 just-noticeable threshold) while the SKY moved by
# 2.53 (98.8 % of sky pixels above it). The cast was weakest where it was
# wanted and strongest where it was not.
#
# The cause is structural, not a tuning error: a global gain cannot tell a
# brick from a sky. This candidate adds ONE per-pixel correction that can:
# it attenuates the warm push on pixels whose blue channel exceeds red, and
# leaves it at full strength everywhere else.
#
# The attenuation reads ONLY the pixel's own R and B. There is no sky model,
# no mask, no region, no neighbour sampling and no inference. A blue-dominant
# pixel is simply a pixel, and the decision is a subtraction.
#
# This is ONE proposed experimental formula, not a calibrated white balance.
# `PRESET_WARM_V1` and `transform_image()` are untouched.
# ==========================================================

PRESET_WARM_BLUE_RESTRAINED_V1 = {
    "name": "warm_blue_restrained_v1",
    "gains": {"R": 1.04, "G": 1.00, "B": 0.96},
    "blue_excess_threshold": 12.0,
    "max_blue_attenuation": 0.90,
}

OPERATION_BLUE_RESTRAINED = "photometric_warmth_blue_restrained_v1"

BLUE_THRESHOLD_MIN = 1.0
BLUE_THRESHOLD_MAX = 255.0

CHANNEL_ORDER = ("R", "G", "B")


# ==========================================================
# PRESET VALIDATION
# ==========================================================

def validate_preset(preset=None):

    """Return a normalised preset, or raise ValueError.

    A preset is exactly a name plus three channel gains inside the declared
    bounds. Nothing else is accepted, so no caller can smuggle in a curve,
    a histogram match or a spatial filter.
    """

    preset = dict(preset or PRESET_WARM_V1)

    gains = preset.get("gains")

    if not isinstance(gains, dict):

        raise ValueError("preset_missing_gains")

    if set(gains) != set(CHANNEL_ORDER):

        raise ValueError("preset_channel_set_mismatch")

    normalised = {}

    for channel in CHANNEL_ORDER:

        try:

            value = float(gains[channel])

        except (TypeError, ValueError):

            raise ValueError("preset_gain_not_numeric:%s" % channel)

        # R4_PHOTO_SOURCE_SAFETY_V1 — DEFECT C.
        #
        # Ordinary range comparisons do NOT reject NaN: `nan < GAIN_MIN` and
        # `nan > GAIN_MAX` are both False, so a NaN gain passed validation and
        # only failed much later inside `round()`, with a misleading error and
        # after the source had already been opened. Finiteness is now checked
        # explicitly and FIRST, which also gives +inf / -inf an accurate reason
        # instead of an out-of-bounds one.
        if not math.isfinite(value):

            raise ValueError("preset_gain_not_finite:%s=%s" % (channel, value))

        if value < GAIN_MIN or value > GAIN_MAX:

            raise ValueError(
                "preset_gain_out_of_bounds:%s=%s" % (channel, value)
            )

        normalised[channel] = round(value, 6)

    return {
        "name": str(preset.get("name") or "custom"),
        "gains": normalised,
    }


# ==========================================================
# THE TRANSFORM
# ==========================================================

def channel_lut(gain):

    """A 256-entry lookup table for one channel.

    This is the whole operation: `out = clip(round(in * gain))`. Building it
    as a table is what makes the transform exactly per-pixel and provably
    free of spatial dependence.
    """

    table = []

    for value in range(256):

        mapped = int(round(value * float(gain)))

        table.append(255 if mapped > 255 else (0 if mapped < 0 else mapped))

    return table


def _clipped_counts(histogram, gain):

    """Count channel values that the gain pushes out of [0, 255].

    Measured from the source histogram, so the figure is exact rather than
    sampled, and no second pass over the pixels is needed.
    """

    clipped = 0

    for value, count in enumerate(histogram):

        if not count:

            continue

        mapped = value * float(gain)

        if mapped > 255.0 or mapped < 0.0:

            clipped += count

    return clipped


def transform_image(image, preset=None):

    """Apply the bounded per-channel gain to one image.

    Returns (adjusted_image, stats). The input image object is never
    modified; a new image is returned.
    """

    if image is None:

        raise ValueError("image_missing")

    if image.mode not in SUPPORTED_MODES:

        raise ValueError("unsupported_mode:%s" % image.mode)

    resolved = validate_preset(preset)

    gains = resolved["gains"]

    bands = image.split()

    adjusted_bands = []

    clipping = {}

    total_pixels = image.size[0] * image.size[1]

    for channel, band in zip(CHANNEL_ORDER, bands):

        gain = gains[channel]

        adjusted_bands.append(band.point(channel_lut(gain)))

        clipping[channel] = _clipped_counts(band.histogram(), gain)

    adjusted = Image.merge(image.mode, tuple(adjusted_bands))

    clipped_total = sum(clipping.values())

    stats = {
        "contract": CONTRACT,
        "version": VERSION,
        "operation": OPERATION,
        "preset": resolved,
        "dimensions": list(image.size),
        "mode": image.mode,
        "pixels": total_pixels,
        "clipped": clipping,
        "clipped_total": clipped_total,
        "clipped_fraction": (
            round(clipped_total / float(total_pixels * len(CHANNEL_ORDER)), 8)
            if total_pixels
            else 0.0
        ),
        "spatial_transform": False,
        "resampled": False,
        "pixel_coordinates_preserved": True,
    }

    return adjusted, stats


# ==========================================================
# R4-PHOTO-02 — BLUE-RESTRAINED TRANSFORM
# ==========================================================

def validate_blue_restrained_preset(preset=None):

    """Normalise and bound-check the blue-restrained preset.

    Gain validation is delegated to `validate_preset()` so the finite-number
    and bounds rules are literally the same code, including the NaN fix from
    R4_PHOTO_SOURCE_SAFETY_V1. The two extra parameters get their own checks.
    """

    preset = dict(preset or PRESET_WARM_BLUE_RESTRAINED_V1)

    base = validate_preset(
        {"name": preset.get("name"), "gains": preset.get("gains")}
    )

    try:

        threshold = float(preset.get("blue_excess_threshold"))

    except (TypeError, ValueError):

        raise ValueError("blue_threshold_not_numeric")

    if not math.isfinite(threshold):

        raise ValueError("blue_threshold_not_finite:%s" % threshold)

    if threshold < BLUE_THRESHOLD_MIN or threshold > BLUE_THRESHOLD_MAX:

        raise ValueError("blue_threshold_out_of_bounds:%s" % threshold)

    try:

        attenuation = float(preset.get("max_blue_attenuation"))

    except (TypeError, ValueError):

        raise ValueError("blue_attenuation_not_numeric")

    if not math.isfinite(attenuation):

        raise ValueError("blue_attenuation_not_finite:%s" % attenuation)

    if attenuation < 0.0 or attenuation > 1.0:

        raise ValueError("blue_attenuation_out_of_bounds:%s" % attenuation)

    return {
        "name": base["name"],
        "gains": base["gains"],
        "blue_excess_threshold": round(threshold, 6),
        "max_blue_attenuation": round(attenuation, 6),
    }


def _strength_for_excess(excess, threshold, attenuation):

    """Warm strength in [1 - attenuation, 1] for one blue-excess value.

    `excess` is an integer 0..255, so the whole attenuation curve has only 256
    possible values and can be precomputed exactly.
    """

    if excess <= 0:

        return 1.0

    fraction = min(1.0, float(excess) / float(threshold))

    return 1.0 - float(attenuation) * fraction


def transform_image_blue_restrained(image, preset=None):

    """Blue-restrained warm adjustment. Per-pixel, no spatial dependence.

        blue_excess = max(0, B - R)
        strength    = 1 - max_blue_attenuation * min(1, blue_excess / threshold)
        R_out = clip(round(R * (1 + (gain_R - 1) * strength)))
        G_out = clip(round(G * gain_G))
        B_out = clip(round(B * (1 - (1 - gain_B) * strength)))

    Every output pixel is a function of the SAME pixel's R, G and B only.
    """

    if image is None:

        raise ValueError("image_missing")

    if image.mode not in SUPPORTED_MODES:

        raise ValueError("unsupported_mode:%s" % image.mode)

    resolved = validate_blue_restrained_preset(preset)

    gains = resolved["gains"]

    threshold = resolved["blue_excess_threshold"]

    attenuation = resolved["max_blue_attenuation"]

    red_delta = gains["R"] - 1.0

    blue_delta = 1.0 - gains["B"]

    green_gain = gains["G"]

    # 256 possible strengths, indexed by blue excess.
    strengths = [
        _strength_for_excess(excess, threshold, attenuation)
        for excess in range(256)
    ]

    raw = image.tobytes()

    out = bytearray(len(raw))

    clipped = {"R": 0, "G": 0, "B": 0}

    for index in range(0, len(raw), 3):

        red = raw[index]

        green = raw[index + 1]

        blue = raw[index + 2]

        excess = blue - red

        strength = strengths[excess] if excess > 0 else 1.0

        red_value = red * (1.0 + red_delta * strength)

        blue_value = blue * (1.0 - blue_delta * strength)

        if green_gain != 1.0:

            green_value = green * green_gain

        else:

            green_value = float(green)

        red_out = int(round(red_value))

        green_out = int(round(green_value))

        blue_out = int(round(blue_value))

        if red_out > 255:

            red_out, clipped["R"] = 255, clipped["R"] + 1

        elif red_out < 0:

            red_out, clipped["R"] = 0, clipped["R"] + 1

        if green_out > 255:

            green_out, clipped["G"] = 255, clipped["G"] + 1

        elif green_out < 0:

            green_out, clipped["G"] = 0, clipped["G"] + 1

        if blue_out > 255:

            blue_out, clipped["B"] = 255, clipped["B"] + 1

        elif blue_out < 0:

            blue_out, clipped["B"] = 0, clipped["B"] + 1

        out[index] = red_out

        out[index + 1] = green_out

        out[index + 2] = blue_out

    adjusted = Image.frombytes(image.mode, image.size, bytes(out))

    total_pixels = image.size[0] * image.size[1]

    clipped_total = sum(clipped.values())

    stats = {
        "contract": CONTRACT,
        "version": VERSION,
        "operation": OPERATION_BLUE_RESTRAINED,
        "preset": resolved,
        "dimensions": list(image.size),
        "mode": image.mode,
        "pixels": total_pixels,
        "clipped": clipped,
        "clipped_total": clipped_total,
        "clipped_fraction": (
            round(clipped_total / float(total_pixels * len(CHANNEL_ORDER)), 8)
            if total_pixels
            else 0.0
        ),
        "spatial_transform": False,
        "resampled": False,
        "pixel_coordinates_preserved": True,
        "blue_restrained": True,
    }

    return adjusted, stats


# ==========================================================
# FILE LEVEL
# ==========================================================
def _sha256(path):

    digest = hashlib.sha256()

    with open(path, "rb") as handle:

        for block in iter(lambda: handle.read(1 << 20), b""):

            digest.update(block)

    return digest.hexdigest()


# ==========================================================
# SOURCE / OUTPUT IDENTITY GUARD
#
# R4_PHOTO_SOURCE_SAFETY_V1 — DEFECTS A and B.
#
# The operation must never write onto the image it is reading. Two distinct
# ways that can happen, and both were reproduced before this guard existed:
#
#   A  the caller passes the same path twice. `overwrite=True` skipped the
#      exists() refusal and Pillow truncated the source in place.
#
#   B  the output is a filesystem ALIAS of the source — a hardlink shares the
#      same inode, so writing "another file" truncated the original. A symlink
#      does the same wherever the platform can create one; symlink creation is
#      unavailable in this environment, so that variant is guarded but not
#      reproducible here.
#
# Three comparisons, cheapest first:
#   1. normalised absolute path  -> same path
#   2. resolved real path        -> symlink / relative alias
#   3. (st_dev, st_ino)          -> hardlink alias, where the platform reports
#                                   a usable inode
#
# Windows-compatible: `normcase` folds case and separators, `realpath` resolves
# links, and the inode pair comes from `os.stat`, which is populated on NTFS.
# ==========================================================

def _file_identity(path):

    """(device, inode) when the platform reports a usable inode, else None."""

    try:

        info = os.stat(path)

    except OSError:

        return None

    inode = getattr(info, "st_ino", 0)

    if not inode:

        return None

    return (getattr(info, "st_dev", 0), inode)


def path_identity_conflict(source_path, output_path):

    """None when the two paths are distinct files, else a conflict dict."""

    source_text = os.path.normcase(os.path.abspath(str(source_path)))

    output_text = os.path.normcase(os.path.abspath(str(output_path)))

    if source_text == output_text:

        return {"reason": "same_path", "via": "normalised_path"}

    source_real = os.path.normcase(os.path.realpath(source_text))

    output_real = os.path.normcase(os.path.realpath(output_text))

    if source_real == output_real:

        return {"reason": "same_file", "via": "resolved_path"}

    source_key = _file_identity(source_text)

    output_key = _file_identity(output_real)

    if source_key is not None and source_key == output_key:

        return {"reason": "same_file", "via": "filesystem_identity"}

    return None


def adjust_file(
    source_path,
    output_path,
    preset=None,
    overwrite=False,
    transform=None,
):

    """Apply the operation to one file and write one new file.

    Never modifies the source. Refuses to overwrite an existing output unless
    `overwrite=True` is passed explicitly — but the source/output identity
    guard runs FIRST and is not overridable, so no value of `overwrite` can
    write onto the source or onto an alias of it.
    """

    started = time.time()

    if not source_path or not os.path.isfile(str(source_path)):

        return {
            "status": "source_not_found",
            "source_path": source_path,
            "output_written": False,
        }

    if not output_path:

        return {
            "status": "output_path_missing",
            "output_written": False,
        }

    # R4_PHOTO_SOURCE_SAFETY_V1 — identity is refused BEFORE the overwrite
    # decision, so `overwrite=True` can never authorise writing onto the
    # source. This is the one refusal that must not be overridable.
    conflict = path_identity_conflict(source_path, output_path)

    if conflict is not None:

        return {
            "status": "source_output_conflict",
            "reason": conflict["reason"],
            "via": conflict["via"],
            "source_path": str(source_path),
            "output_path": str(output_path),
            "output_written": False,
            "source_sha256": _sha256(source_path),
        }

    if os.path.exists(str(output_path)) and not overwrite:

        return {
            "status": "output_exists",
            "output_path": str(output_path),
            "output_written": False,
        }

    source_sha_before = _sha256(source_path)

    try:

        with Image.open(source_path) as opened:

            if opened.mode not in SUPPORTED_MODES:

                return {
                    "status": "unsupported_mode",
                    "mode": opened.mode,
                    "output_written": False,
                    "source_sha256": source_sha_before,
                }

            # Force a full decode before the source file is closed.
            image = opened.copy()

    except Exception as error:  # noqa: BLE001 - reported, never raised silently

        return {
            "status": "unreadable_image",
            "error": "%s: %s" % (type(error).__name__, error),
            "output_written": False,
        }

    try:

        adjusted, stats = (transform or transform_image)(image, preset)

    except ValueError as error:

        return {
            "status": "invalid_request",
            "error": str(error),
            "output_written": False,
            "source_sha256": source_sha_before,
        }

    os.makedirs(os.path.dirname(os.path.abspath(str(output_path))), exist_ok=True)

    adjusted.save(str(output_path), format="PNG", optimize=False)

    source_sha_after = _sha256(source_path)

    return {
        "status": "ok",
        "output_written": True,
        "operation": stats.get("operation", OPERATION),
        "contract": CONTRACT,
        "version": VERSION,
        "pillow_version": getattr(Image, "__version__", None),
        "source": {
            "path": str(source_path),
            "sha256_before": source_sha_before,
            "sha256_after": source_sha_after,
            "unchanged": source_sha_before == source_sha_after,
        },
        "output": {
            "path": str(output_path),
            "sha256": _sha256(output_path),
            "bytes": os.path.getsize(str(output_path)),
        },
        "transform": stats,
        "elapsed_seconds": round(time.time() - started, 4),
    }


# ==========================================================
# R4_PHOTO_SAFE_CHAT_BRIDGE_V1 — EXCLUSIVE PRODUCTION OUTPUT
#
# `adjust_file()` above is the EXPERIMENTAL entry point. It writes with
# Pillow's plain `save()`, which truncates whatever is already at the
# destination. That was acceptable for a supervised run into a fresh
# `runs/` directory, but it is NOT sufficient for a production chat turn
# whose destination lives inside an approved, HTTP-served storage root.
#
# This entry point adds ONLY what production needs, and nothing else:
#
#   * the caller supplies a ROOT, never a full destination path;
#   * the filename must be a bare name — no separators, no `..`, no drive
#     or alternate-data-stream colon, no empty value;
#   * the RESOLVED destination must stay inside the RESOLVED root, so a
#     symlinked parent directory cannot redirect the write elsewhere;
#   * creation is EXCLUSIVE (`"xb"` -> O_CREAT|O_EXCL). An existing
#     destination is refused by the filesystem itself, so a concurrent
#     creator cannot be overwritten and a pre-existing file is never
#     truncated. This is the property `adjust_file()` could not offer;
#   * the EXCLUSIVE handle is handed to Pillow, so the bytes are written
#     through the very descriptor that won the creation race — there is no
#     second open between the check and the write;
#   * the source/output identity guard runs FIRST (path, realpath, inode);
#   * the source digest is compared before and after;
#   * a partially written output is removed on failure.
#
# What it still does NOT do: it cannot prevent a third party from replacing
# the root directory between the containment check and the `open()`. That
# residual window is stated in the report rather than papered over.
# ==========================================================

def validate_output_filename(filename):

    """True only for a bare, relative, single-component file name."""

    name = str(filename or "").strip()

    if not name or name in (".", ".."):

        return False

    if "/" in name or "\\" in name:

        return False

    if ":" in name:

        return False

    if os.path.basename(name) != name:

        return False

    return True


def _resolved_root(root):

    """Absolute, link-resolved root that PRESERVES the on-disk case.

    `normcase` is deliberately NOT applied here: on Windows it lowercases the
    whole path, and this value is used to CONSTRUCT the output path. Writing
    through a lowercased path would create a differently-cased destination and
    would break the case-sensitive `relative_to()` the attachment service uses
    to derive the public URL. Case folding is applied only for COMPARISON, in
    `_inside_root()`.
    """

    return os.path.realpath(os.path.abspath(str(root)))


def _inside_root(path, root):

    """True when `path` is `root` or lives beneath it (case-insensitive)."""

    try:

        folded_root = os.path.normcase(root)

        return os.path.commonpath(
            [os.path.normcase(path), folded_root]
        ) == folded_root

    except ValueError:

        # Different drives on Windows — cannot share a root.
        return False


def adjust_file_exclusive(
    source_path,
    output_root,
    preset=None,
    transform=None,
    filename=None,
):

    """Apply the operation and write ONE new file with exclusive creation.

    Returns a result dict; `status == "ok"` is the only success. The source
    is never modified, and no existing destination is ever overwritten.
    """

    started = time.time()

    if not source_path or not os.path.isfile(str(source_path)):

        return {
            "status": "source_not_found",
            "source_path": source_path,
            "output_written": False,
        }

    if not output_root:

        return {
            "status": "output_root_missing",
            "output_written": False,
        }

    root = _resolved_root(output_root)

    if not os.path.isdir(root):

        return {
            "status": "output_root_missing",
            "output_root": str(output_root),
            "output_written": False,
        }

    if not validate_output_filename(filename):

        return {
            "status": "invalid_filename",
            "filename": filename,
            "output_written": False,
        }

    target = os.path.join(root, str(filename))

    # The destination is re-resolved so a symlinked parent directory cannot
    # carry the write outside the approved root. Case is preserved for the
    # actual write; only the containment comparison folds case.
    resolved_target = os.path.realpath(os.path.abspath(target))

    if not _inside_root(resolved_target, root):

        return {
            "status": "output_outside_root",
            "output_path": target,
            "output_written": False,
        }

    # Identity is refused BEFORE creation, so no alias of the source can be
    # opened for writing even though the name looks new.
    conflict = path_identity_conflict(source_path, target)

    if conflict is not None:

        return {
            "status": "source_output_conflict",
            "reason": conflict["reason"],
            "via": conflict["via"],
            "source_path": str(source_path),
            "output_path": target,
            "output_written": False,
            "source_sha256": _sha256(source_path),
        }

    source_sha_before = _sha256(source_path)

    try:

        with Image.open(source_path) as opened:

            if opened.mode not in SUPPORTED_MODES:

                return {
                    "status": "unsupported_mode",
                    "mode": opened.mode,
                    "output_written": False,
                    "source_sha256": source_sha_before,
                }

            image = opened.copy()

    except Exception as error:  # noqa: BLE001 - reported, never raised silently

        return {
            "status": "unreadable_image",
            "error": "%s: %s" % (type(error).__name__, error),
            "output_written": False,
        }

    try:

        adjusted, stats = (
            transform or transform_image_blue_restrained
        )(image, preset)

    except ValueError as error:

        return {
            "status": "invalid_request",
            "error": str(error),
            "output_written": False,
            "source_sha256": source_sha_before,
        }

    created = False

    try:

        handle = open(target, "xb")

        created = True

        try:

            adjusted.save(handle, format="PNG", optimize=False)

            handle.flush()

            os.fsync(handle.fileno())

        finally:

            handle.close()

    except FileExistsError:

        return {
            "status": "output_exists",
            "output_path": target,
            "output_written": False,
        }

    except Exception as error:  # noqa: BLE001 - reported, never raised silently

        if created:

            try:

                if os.path.isfile(target):

                    os.unlink(target)

            except OSError:

                pass

        return {
            "status": "write_failed",
            "error": "%s: %s" % (type(error).__name__, error),
            "output_written": False,
        }

    source_sha_after = _sha256(source_path)

    if source_sha_before != source_sha_after:

        # The source changed under us. The output is not attributable, so it
        # is discarded rather than registered as a derived image.
        try:

            os.unlink(target)

        except OSError:

            pass

        return {
            "status": "source_modified",
            "output_written": False,
            "source_sha256_before": source_sha_before,
            "source_sha256_after": source_sha_after,
        }

    return {
        "status": "ok",
        "output_written": True,
        "operation": stats.get("operation", OPERATION_BLUE_RESTRAINED),
        "contract": CONTRACT,
        "version": VERSION,
        "pillow_version": getattr(Image, "__version__", None),
        "source": {
            "path": str(source_path),
            "sha256_before": source_sha_before,
            "sha256_after": source_sha_after,
            "unchanged": True,
        },
        "output": {
            "path": target,
            "sha256": _sha256(target),
            "bytes": os.path.getsize(target),
        },
        "transform": stats,
        "elapsed_seconds": round(time.time() - started, 4),
    }
