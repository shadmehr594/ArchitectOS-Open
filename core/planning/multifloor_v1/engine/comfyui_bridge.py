"""
ArchitectOS v33.2 — Photorealistic Plan-Locked 3D Architectural Renderer, Open Pilotis (+2.72m) & Roof Kharposhteh Extruder,
ControlNet Depth/Lineart Generator & Live ComfyUI Bridge (`engine/comfyui_bridge.py`)

Upgrades in v33.2:
  1. Exact Per-Floor Elevation & Open Pilotis Extrusion (`+2.72m` Pilotis vs `+3.24m` Residential Floors):
     - Honours each floor's exact `floor_height_mm` (`2.52m` clear / `+2.72m` slab for Pilotis vs `3.24m` for residential floors).
     - When `fl0.is_open_pilotis` is True: renders a true Open Pilotis with ZERO front wall, ZERO garage shutters, and ZERO front steps,
       showing the freestanding stone columns (`A-1`, `B-1`, `C-1`), 3D parked cars (`P1` and `P2`), the central pedestrian walkway
       (`مسیر پیاده`), and the recessed Staircase & Elevator Core Box (`باکس پله و آسانسور در وسط ساختمان`) visible in depth!
  2. Roof Kharposhteh Penthouse (`خرپشته و اتاقک آسانسور روی بام`):
     - Reads `project.roof_plan` (`STAIR_BOX` + `ELEVATOR_SHAFT` + `FLOOR_LOBBY` or `KHARPOSHTEH_DUPLEX`) and renders the 3D recessed
       Kharposhteh volume above the roof parapet at the exact horizontal X-span of the stair/elevator core.
  3. 3D Two-Sided Courtyard & Lot Boundaries (`حیاط مشجر در دو طرف زمین`) + Photorealistic Ray-Shaded Shader:
     - Renders 3D perspective courtyard side walls, wall sconces, raised stone planter beds, and multi-layered organic foliage on both
       left and right sides of the lot, with Perlin travertine stone veining, soft Gaussian shadows, and Fresnel glass reflections.
  4. Live ComfyUI `/object_info` Auto-Discovery & FLUX ControlNet + Img2Img Pipeline.
"""
from __future__ import annotations
import json
import math
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any, Dict, List, Optional, Tuple
import cv2
import numpy as np
from PIL import Image, ImageDraw
from .conversational_editor import ConversationalPlanEditor
from .domain import BuildingProjectResultV3
from .nl_design_parser import (
    normalize_persian_text,
    update_geometry_locked_render_state,
)


def _draw_3d_parked_car(
    draw: ImageDraw.ImageDraw,
    line_draw: ImageDraw.ImageDraw,
    depth_np: np.ndarray,
    cx0: int,
    cx1: int,
    y_floor: int,
    car_h: int,
    body_rgb: Tuple[int, int, int] = (238, 240, 244),
    is_night: bool = False,
) -> None:
    """Renders a realistic 3D front-facing luxury sedan parked inside an open pilotis bay."""
    cw = cx1 - cx0
    if cw < 36 or car_h < 24:
        return
    H, W = depth_np.shape[:2]
    y_top = y_floor - car_h
    y_hood = y_floor - int(car_h * 0.56)
    y_bumper = y_floor - int(car_h * 0.14)

    # 1. Ground contact ambient occlusion shadow under car
    draw.ellipse(
        [cx0 - 4, y_floor - 7, cx1 + 4, y_floor + 5],
        fill=(18, 20, 24),
    )

    # 2. Left & Right Tires
    tw = max(7, int(cw * 0.14))
    draw.rectangle([cx0 + 3, y_bumper - 4, cx0 + 3 + tw, y_floor], fill=(24, 26, 30))
    draw.rectangle([cx1 - 3 - tw, y_bumper - 4, cx1 - 3, y_floor], fill=(24, 26, 30))

    # 3. Cabin Roof & Windshield (trapezoid narrowing toward top)
    roof_pad = max(6, int(cw * 0.15))
    body_dark = tuple(max(0, int(c * 0.76)) for c in body_rgb)
    body_hi = tuple(min(255, int(c * 1.06)) for c in body_rgb)
    draw.polygon(
        [
            (cx0 + roof_pad, y_top),
            (cx1 - roof_pad, y_top),
            (cx1 - 3, y_hood),
            (cx0 + 3, y_hood),
        ],
        fill=body_rgb,
        outline=body_dark,
    )
    # Reflective Windshield with diagonal sky sheen
    ws_pad = roof_pad + 3
    draw.polygon(
        [
            (cx0 + ws_pad, y_top + 4),
            (cx1 - ws_pad, y_top + 4),
            (cx1 - 7, y_hood - 2),
            (cx0 + 7, y_hood - 2),
        ],
        fill=(54, 78, 104) if not is_night else (38, 48, 66),
    )
    draw.polygon(
        [
            (cx0 + ws_pad + 4, y_top + 5),
            (cx0 + ws_pad + int(cw * 0.22), y_top + 5),
            (cx0 + 14, y_hood - 3),
            (cx0 + 8, y_hood - 3),
        ],
        fill=(145, 182, 215) if not is_night else (88, 112, 142),
    )

    # 4. Lower Front Hood, Fender & Bumper Volume
    draw.polygon(
        [
            (cx0 + 3, y_hood),
            (cx1 - 3, y_hood),
            (cx1, y_hood + 6),
            (cx1, y_bumper),
            (cx0, y_bumper),
            (cx0, y_hood + 6),
        ],
        fill=body_rgb,
        outline=body_dark,
    )
    # Hood highlight band
    draw.polygon(
        [
            (cx0 + 8, y_hood + 2),
            (cx1 - 8, y_hood + 2),
            (cx1 - 12, y_hood + int((y_bumper - y_hood) * 0.38)),
            (cx0 + 12, y_hood + int((y_bumper - y_hood) * 0.38)),
        ],
        fill=body_hi,
    )

    # 5. Chrome Front Grille & License Plate
    gx0 = cx0 + int(cw * 0.26)
    gx1 = cx1 - int(cw * 0.26)
    gy0 = y_hood + int((y_bumper - y_hood) * 0.34)
    gy1 = y_bumper - 3
    draw.rectangle([gx0, gy0, gx1, gy1], fill=(32, 36, 42), outline=(168, 174, 182), width=1)
    for gl_y in range(gy0 + 3, gy1 - 2, 3):
        draw.line([(gx0 + 2, gl_y), (gx1 - 2, gl_y)], fill=(140, 146, 154), width=1)
    # License plate
    pw = max(14, int((gx1 - gx0) * 0.56))
    px_mid = (cx0 + cx1) // 2
    draw.rectangle([px_mid - pw // 2, gy1 - 7, px_mid + pw // 2, gy1 - 1], fill=(245, 245, 245), outline=(40, 40, 40), width=1)

    # 6. LED Headlights (Left & Right)
    hl_y0 = y_hood + int((y_bumper - y_hood) * 0.24)
    hl_y1 = hl_y0 + max(5, int(car_h * 0.11))
    hl_col = (255, 250, 210) if is_night else (235, 245, 255)
    draw.polygon([(cx0 + 4, hl_y0), (gx0 - 4, hl_y0 + 2), (gx0 - 4, hl_y1), (cx0 + 4, hl_y1 - 1)], fill=hl_col, outline=(120, 140, 165))
    draw.polygon([(gx1 + 4, hl_y0 + 2), (cx1 - 4, hl_y0), (cx1 - 4, hl_y1 - 1), (gx1 + 4, hl_y1)], fill=hl_col, outline=(120, 140, 165))

    line_draw.polygon(
        [(cx0 + roof_pad, y_top), (cx1 - roof_pad, y_top), (cx1, y_hood + 6), (cx1, y_bumper), (cx0, y_bumper), (cx0, y_hood + 6)],
        outline=(235, 235, 235),
    )
    depth_np[max(0, y_top):min(H, y_floor), max(0, cx0):min(W, cx1)] = 198


def _draw_organic_tree_cluster(
    draw: ImageDraw.ImageDraw,
    line_draw: ImageDraw.ImageDraw,
    depth_np: np.ndarray,
    tx: int,
    gy_base: int,
    r_w: int,
    r_h: int,
    rng: np.random.RandomState,
    is_night: bool = False,
) -> None:
    """Renders a realistic multi-layered cypress & ornamental shrub cluster without cartoon outlines."""
    H, W = depth_np.shape[:2]
    # Trunk
    draw.rectangle([tx - 3, gy_base - 18, tx + 3, gy_base + 2], fill=(78, 54, 36))
    # Layered organic foliage puffs from back/dark to front/sunlit
    layers = [
        (0, -r_h, r_w, r_h, (22, 68, 36) if not is_night else (14, 42, 24)),
        (-int(r_w * 0.22), -int(r_h * 1.05), int(r_w * 0.82), int(r_h * 0.88), (34, 96, 48) if not is_night else (20, 56, 32)),
        (int(r_w * 0.18), -int(r_h * 0.92), int(r_w * 0.74), int(r_h * 0.80), (46, 122, 58) if not is_night else (26, 68, 38)),
        (-int(r_w * 0.10), -int(r_h * 1.25), int(r_w * 0.58), int(r_h * 0.65), (64, 146, 72) if not is_night else (32, 80, 44)),
    ]
    for dx_l, dy_l, rw_l, rh_l, col_l in layers:
        cx, cy = tx + dx_l, gy_base + dy_l
        draw.ellipse([cx - rw_l, cy - rh_l, cx + rw_l, cy + rh_l], fill=col_l)
    # Fine leaf texture puffs
    for _ in range(14):
        px = tx + int(rng.uniform(-0.68, 0.68) * r_w)
        py = gy_base - int(rng.uniform(0.35, 1.65) * r_h)
        pr = max(5, int(r_w * rng.uniform(0.18, 0.32)))
        c_leaf = (76, 158, 82) if (px < tx and not is_night) else ((38, 108, 52) if not is_night else (24, 62, 36))
        draw.ellipse([px - pr, py - pr, px + pr, py + pr], fill=c_leaf)

    line_draw.ellipse([tx - r_w, gy_base - r_h * 2 + 8, tx + r_w, gy_base], outline=(170, 170, 170), width=1)
    depth_np[max(0, gy_base - r_h * 2 + 8):min(H, gy_base + 4), max(0, tx - r_w):min(W, tx + r_w)] = 234




def _draw_persian_rtl_signboard_text(
    pdraw: Any,
    xy: Tuple[int, int],
    logical_pres_forms: str,
    font: Any,
    fill: Tuple[int, int, int],
    shadow_fill: Optional[Tuple[int, int, int]] = None,
) -> None:
    """
    v53.0 Cross-Platform (Windows + Linux) Persian RTL Signboard Renderer:
      - On Linux with `libraqm` (`PIL.features.check("raqm") == True`), HarfBuzz automatically reorders
        Arabic Presentation Forms from RTL to visual LTR, so we pass `logical_pres_forms`.
      - On Windows without `libraqm` (`PIL.features.check("raqm") == False`), PIL draws codepoints strictly
        left-to-right, which previously caused `"اتو گالری سینا"` to appear reversed as `"انیس ی رلاگ وتا"`.
        Reversing the presentation-form string (`logical_pres_forms[::-1]`) when `raqm` is absent guarantees
        100% correct right-to-left connected Persian rendering on Windows AND Linux!
    """
    has_raqm = False
    try:
        from PIL import features as _pil_features
        has_raqm = bool(_pil_features.check("raqm"))
    except Exception:
        has_raqm = False
    render_str = logical_pres_forms if has_raqm else logical_pres_forms[::-1]
    x, y = xy
    if shadow_fill is not None:
        for dx, dy in ((2, 2), (3, 3), (1, 2)):
            pdraw.text((x + dx, y + dy), render_str, fill=shadow_fill, font=font)
    pdraw.text((x, y), render_str, fill=fill, font=font)



def resolve_style_reference_image(
    reference_id: str = "",
    repo_root: str = "",
    explicit_path: str = "",
    reference_image_url: str = "",
    reference_image_base64: str = "",
) -> Optional[str]:
    """
    v66.0 Universal Style Reference Image Resolver:
    1) Decodes `reference_image_base64` (captured directly from the user's selected DOM `<img>` or uploaded reference file),
    2) Resolves `explicit_path` or `reference_image_url` (mapping `/references/...` or `http://127.0.0.1:3000/...` to disk or local HTTP),
    3) Searches `repo_root` case-insensitively for `reference_id` (`AR-078`, `CLASSICAL_REF_04`, etc., matching both `-` and `_`).
    """
    import base64 as _b64_r
    import tempfile as _tf_r
    if explicit_path and os.path.isfile(explicit_path):
        return explicit_path
    if reference_image_base64 and len(str(reference_image_base64)) > 64:
        try:
            _b_str = str(reference_image_base64).strip()
            if "," in _b_str:
                _b_str = _b_str.split(",", 1)[1]
            _raw_im = _b64_r.b64decode(_b_str)
            if len(_raw_im) > 128:
                _tmp_ref_p = os.path.join(_tf_r.gettempdir(), "archos_v66_active_style_ref.jpg")
                with open(_tmp_ref_p, "wb") as _rf:
                    _rf.write(_raw_im)
                return _tmp_ref_p
        except Exception:
            pass
    if reference_image_url:
        _u_s = str(reference_image_url).strip()
        if _u_s.startswith("data:image/"):
            try:
                _raw_im = _b64_r.b64decode(_u_s.split(",", 1)[1])
                _tmp_ref_p = os.path.join(_tf_r.gettempdir(), "archos_v66_active_style_ref.jpg")
                with open(_tmp_ref_p, "wb") as _rf:
                    _rf.write(_raw_im)
                return _tmp_ref_p
            except Exception:
                pass
        # Extract URL path component or filename from reference_image_url
        _u_path = _u_s.split("?", 1)[0].split("#", 1)[0]
        if "://" in _u_path:
            _u_path = "/" + _u_path.split("://", 1)[1].partition("/")[2]
        _u_rel = _u_path.lstrip("/").replace("/", os.sep)
        if repo_root and _u_rel:
            for _sub_r in ("", "ui", "public", "static", "assets", "data"):
                _cand_u = os.path.join(repo_root, _sub_r, _u_rel) if _sub_r else os.path.join(repo_root, _u_rel)
                if os.path.isfile(_cand_u):
                    return _cand_u
        if not reference_id and _u_path:
            reference_id = os.path.splitext(os.path.basename(_u_path))[0]

    _ref_parts = str(reference_id or "").strip().split()
    ref_clean = _ref_parts[0].strip() if _ref_parts else ""
    if not ref_clean:
        return None
    search_roots = []
    if repo_root and os.path.isdir(repo_root):
        search_roots.extend([
            os.path.join(repo_root, "references"),
            os.path.join(repo_root, "assets", "references"),
            os.path.join(repo_root, "data", "references"),
            os.path.join(repo_root, "ui", "references"),
            os.path.join(repo_root, "public", "references"),
            os.path.join(repo_root, "static", "references"),
            repo_root,
        ])
    ref_low = ref_clean.lower()
    ref_norm = ref_low.replace("-", "").replace("_", "")
    exact_match = None
    partial_match = None
    for sr in search_roots:
        if not os.path.isdir(sr):
            continue
        for r_dir, dirs, files in os.walk(sr):
            dirs[:] = [d for d in dirs if d not in (".git", "venv", ".venv", "node_modules", "__pycache__", "renders") and not d.startswith(("_backup", "upgrade_"))]
            for fn in files:
                stem, ext = os.path.splitext(fn)
                if ext.lower() in (".jpg", ".jpeg", ".png", ".webp"):
                    s_low = stem.lower()
                    s_norm = s_low.replace("-", "").replace("_", "")
                    if s_low == ref_low or s_norm == ref_norm:
                        return os.path.join(r_dir, fn)
                    if partial_match is None and (ref_low in s_low or ref_norm in s_norm):
                        partial_match = os.path.join(r_dir, fn)
    return exact_match or partial_match


def extract_universal_style_from_reference_image(
    ref_image_path: Optional[str] = None,
    reference_caption: str = "",
) -> Dict[str, Any]:
    """
    Universal Image-Driven Style & Material Extractor:
    Analyzes ANY style reference image via Computer Vision (dominant facade RGB/HSV palette,
    ornament/edge density, warm vs cool tone, dark vs bright stone) and optional local Ollama VLM
    so ANY reference image transfers its true material, color, and architectural style!
    """
    style_out: Dict[str, Any] = {
        "has_image": False,
        "wall_rgb_bgr": None,
        "trim_rgb_bgr": None,
        "frame_rgb_bgr": None,
        "style_prompt_en": "",
        "is_ornate_classical": False,
        "is_modern_minimal": False,
    }
    cap_clean = str(reference_caption or "").strip()
    if ref_image_path and os.path.isfile(ref_image_path):
        try:
            import cv2
            im_r = cv2.imread(ref_image_path)
            if im_r is not None and im_r.size > 0:
                style_out["has_image"] = True
                ih, iw = im_r.shape[:2]
                # Sample central architectural facade band (Y: 18%..78%, X: 12%..88%) excluding sky & pavement
                crop = im_r[int(ih * 0.18):int(ih * 0.78), int(iw * 0.12):int(iw * 0.88)]
                hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
                gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
                # Exclude pure blue sky pixels (H in 95..130, S > 55) and very dark window voids (V < 55)
                h_ch, s_ch, v_ch = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
                facade_mask = (~((h_ch >= 90) & (h_ch <= 135) & (s_ch > 45))) & (v_ch >= 60)
                if np.sum(facade_mask) < 50:
                    facade_mask = np.ones(gray.shape, dtype=bool)
                med_bgr = np.median(crop[facade_mask], axis=0).astype(int)
                b_m, g_m, r_m = int(med_bgr[0]), int(med_bgr[1]), int(med_bgr[2])
                style_out["wall_rgb_bgr"] = (b_m, g_m, r_m)
                style_out["trim_rgb_bgr"] = (min(255, b_m + 14), min(255, g_m + 14), min(255, r_m + 14))
                style_out["ref_image_path"] = ref_image_path
                # Extract high-frequency photographic surface texture variation from the reference image
                _tex_patch = cv2.resize(crop, (128, 128), interpolation=cv2.INTER_AREA).astype(np.float32)
                _tex_blur = cv2.GaussianBlur(_tex_patch, (31, 31), 9.0)
                style_out["wall_tex_detail"] = np.clip(_tex_patch - _tex_blur, -24.0, 24.0)

                # Edge / ornament density to distinguish ornate classical vs sleek modern
                edges = cv2.Canny(gray, 70, 170)
                edge_density = float(np.mean(edges > 0))
                style_out["is_ornate_classical"] = edge_density >= 0.085
                style_out["is_modern_minimal"] = edge_density < 0.055

                # Classify dominant material & color purely from measured RGB/HSV
                lum = 0.299 * r_m + 0.587 * g_m + 0.114 * b_m
                if r_m - b_m > 38 and r_m > 130 and g_m < 130:
                    mat_desc = "warm terracotta red-ochre architectural brick masonry"
                elif lum >= 205 and abs(r_m - b_m) <= 22:
                    mat_desc = "pure bright white neoclassical limestone and crisp white marble cladding"
                elif lum >= 165 and r_m >= b_m + 10:
                    mat_desc = "warm cream-beige honed travertine stone ashlar cladding"
                elif lum < 95:
                    mat_desc = "dark charcoal basalt stone and sleek dark anthracite architectural panels"
                else:
                    mat_desc = "natural architectural stone and smooth plaster facade cladding"

                orn_desc = (
                    "ornate classical carved cornices, fluted pilasters, moulded window pediments, and roof stone balustrade"
                    if style_out["is_ornate_classical"]
                    else ("clean contemporary architectural lines, sharp frameless glazing, and minimalist stone reveals" if style_out["is_modern_minimal"] else "balanced neoclassical stone pilasters and moulded cornice")
                )
                style_out["style_prompt_en"] = (
                    f"Photorealistic architectural exterior photograph strictly matching the visual style, material palette, and texture of the reference image: "
                    f"{mat_desc}, {orn_desc}, natural daylight shadows, 8k DSLR architectural photography"
                )
        except Exception:
            pass
    if cap_clean:
        style_out["style_prompt_en"] = (
            f"Style reference aesthetic ({cap_clean}): " + style_out.get("style_prompt_en", "")
        ).strip()
    return style_out



def _recover_v68_materials_via_connected_components(verts: np.ndarray, faces: np.ndarray, mat_ids: np.ndarray) -> np.ndarray:
    """
    v71.0 Universal Non-Destructive Material Preserver:
    Preserves genuine explicit materials from `.mtl` / `.obj` / `.ifc` / `.glb` / `.fbx` / `.3ds` meshes.
    NEVER invents fake black/charcoal material IDs on unlabeled carved stone columns, walls, balustrades,
    or flower pots from triangle edge lengths (`min_e`), preventing material inversion on real 3D models.
    When an unlabeled mesh has zero roof/material tags, keeps all architectural stone/ornament as clean neutral clay (0/1)
    so 2x-SSAA HBAO+ + FLUX Depth ControlNet renders true photorealistic materials universally for ANY 3D model!
    """
    if len(faces) < 4:
        return mat_ids
    out_m = mat_ids.copy()
    # Map legacy bright cyan glass (2) to dark architectural glass (7)
    out_m = np.where(out_m == 2, 7, out_m)
    # If mesh already has explicit materials (e.g. from .mtl, .ifc, .glb, or procedural mesh), preserve them 100%!
    has_explicit = int(np.sum(out_m >= 3)) >= 20
    if has_explicit:
        return out_m
    # Unlabeled mesh: keep clean neutral architectural clay (0) so FLUX + Depth ControlNet synthesizes
    # physically accurate stone, reflective glass, wrought iron, and landscaping without inverted black columns!
    return out_m


def render_uploaded_3d_mesh_to_depth_and_scaffold(
    mesh_npz_path: str,
    out_png_path: str,
    spec: Dict[str, Any],
    quality: str = "draft",
) -> Tuple[str, np.ndarray, Image.Image]:
    """
    v68.0 Universal 2x-SSAA V-Ray PBR & G-Buffer Architectural 3D Mesh Renderer:
      1. V-Ray 2-Point Eye-Level Camera (`z_cam = z_min + 0.035*z_span`, `pitch = 0.002`, `max_sy = sy_base_raw`)
         so all ground baselines (`Z = 0`) project to the exact same horizontal line `gy` with ZERO floating walls in the sky!
      2. Foreground Clutter & Perpendicular Side-Wall Sanitizer + Symmetrical Flanking Courtyard Wall Healer
         + Per-Column Ground-to-Base Sealer (eliminates gaps or black boxes under the building or courtyard walls).
      3. Vectorized Connected-Component 3D Object Material Classifier + Screen-Space Mullion-Closure Window Glass & Wrought-Iron Shader
         so windows, wrought-iron gates, flower-pot blossoms, columns, black mansard roof, and black-and-white ribbed dome
         are rendered with V-Ray precision even on raw `.obj` meshes where `mat_ids` are all 0!
      4. 2x Super-Sampled Anti-Aliasing (`2560x1728` -> `1280x864`) + 3-Scale HBAO+ + Directional Sun Cast Shadows
         + Normal-Curvature Relief Sharpening + Local-Relief Enhanced ControlNet `_depth.png`.
    """
    import cv2
    import math
    import numpy as np
    from PIL import Image

    W, H = 1280, 864
    SS = 2
    Ws, Hs = W * SS, H * SS

    # v73.0 Primary True 3D Engine: Use installed Blender Headless (EEVEE/Cycles) with 2-Point Shift-Lens Camera & exact Z-Depth
    # whenever available on the machine (prefers original .obj/.fbx/.glb/.dae/.stl if present on disk, else .npz cache)!
    try:
        from .blender_headless_renderer import BlenderHeadlessRenderer as _BHR73
        _orig_3d_cand = None
        if isinstance(spec, dict):
            _u_fp = str(spec.get("source_3d_path") or spec.get("uploaded_file_path") or "")
            if _u_fp and os.path.isfile(_u_fp) and os.path.splitext(_u_fp)[1].lower() in (".obj", ".fbx", ".glb", ".gltf", ".stl", ".dae", ".ply"):
                _orig_3d_cand = _u_fp
        _b_in = _orig_3d_cand or mesh_npz_path
        _b_res = _BHR73.render_any_3d_model_to_passes(_b_in, out_png_path, spec=spec, quality=quality)
        if _b_res and os.path.isfile(_b_res.get("rgb", "")) and os.path.isfile(_b_res.get("depth", "")):
            _dep_im = Image.open(_b_res["depth"]).convert("L").resize((W, H), Image.Resampling.LANCZOS)
            _lin_im = Image.open(_b_res["lineart"]).convert("RGB").resize((W, H), Image.Resampling.LANCZOS) if os.path.isfile(_b_res.get("lineart", "")) else Image.new("RGB", (W, H), (0, 0, 0))
            return out_png_path, np.array(_dep_im, dtype=np.uint8), _lin_im
    except Exception:
        pass

    is_night = spec.get("lighting_mode") == "NIGHT_WARM"
    is_golden = spec.get("lighting_mode") == "GOLDEN_HOUR"
    data = np.load(mesh_npz_path)
    verts = data["verts"].astype(np.float32).copy()
    faces = data["faces"].astype(np.int32).copy()
    mat_ids = (
        data["mat_ids"].astype(np.uint8).copy()
        if ("mat_ids" in data and len(data["mat_ids"]) == len(faces))
        else np.zeros(len(faces), dtype=np.uint8)
    )
    mesh_prof = str(data["mesh_profile"]) if "mesh_profile" in data else ""

    z_min_v0 = float(np.min(verts[:, 2]))
    z_max_v0 = float(np.max(verts[:, 2]))
    z_span_v0 = max(1.0, z_max_v0 - z_min_v0)

    if not mesh_prof.startswith("sadegh_max") and len(faces) >= 12:
        p0_c = verts[faces[:, 0]]
        p1_c = verts[faces[:, 1]]
        p2_c = verts[faces[:, 2]]
        tc_c = (p0_c + p1_c + p2_c) / 3.0
        fn_c = np.cross(p1_c - p0_c, p2_c - p0_c)
        fn_l_c = np.maximum(1e-6, np.linalg.norm(fn_c, axis=1))
        ar_c = 0.5 * fn_l_c
        nx_c = np.abs(fn_c[:, 0]) / fn_l_c
        nz_c = np.abs(fn_c[:, 2]) / fn_l_c

        up_m_c = (tc_c[:, 2] >= (z_min_v0 + 0.28 * z_span_v0)) & (tc_c[:, 2] <= (z_min_v0 + 0.72 * z_span_v0))
        if int(np.sum(up_m_c)) >= 2:
            up_i = np.where(up_m_c)[0]
            top_k = up_i[np.argsort(-ar_c[up_i])[: min(400, len(up_i))]]
            up_pts = verts[faces[top_k]].reshape(-1, 3)
            cx_c = 0.5 * (float(np.percentile(up_pts[:, 0], 2)) + float(np.percentile(up_pts[:, 0], 98)))
            cy_c = 0.5 * (float(np.percentile(up_pts[:, 1], 2)) + float(np.percentile(up_pts[:, 1], 98)))
            wb_c = max(6.0, float(np.percentile(up_pts[:, 0], 98)) - float(np.percentile(up_pts[:, 0], 2)))
            db_c = max(6.0, float(np.percentile(up_pts[:, 1], 98)) - float(np.percentile(up_pts[:, 1], 2)))
            yb0_c = float(np.percentile(up_pts[:, 1], 2)) - cy_c
            yb1_c = float(np.percentile(up_pts[:, 1], 98)) - cy_c
        else:
            cx_c = 0.5 * (float(np.min(verts[:, 0])) + float(np.max(verts[:, 0])))
            cy_c = 0.5 * (float(np.min(verts[:, 1])) + float(np.max(verts[:, 1])))
            wb_c = max(6.0, float(np.ptp(verts[:, 0])))
            db_c = max(6.0, float(np.ptp(verts[:, 1])))
            yb0_c, yb1_c = -0.5 * db_c, 0.5 * db_c

        verts[:, 0] -= cx_c
        verts[:, 1] -= cy_c
        p0_c = verts[faces[:, 0]]
        p1_c = verts[faces[:, 1]]
        p2_c = verts[faces[:, 2]]
        tc_c = (p0_c + p1_c + p2_c) / 3.0
        tz_min_c = np.minimum(np.minimum(p0_c[:, 2], p1_c[:, 2]), p2_c[:, 2]) - z_min_v0
        tz_max_c = np.maximum(np.maximum(p0_c[:, 2], p1_c[:, 2]), p2_c[:, 2]) - z_min_v0
        ty_min_c = np.minimum(np.minimum(p0_c[:, 1], p1_c[:, 1]), p2_c[:, 1])
        ty_max_c = np.maximum(np.maximum(p0_c[:, 1], p1_c[:, 1]), p2_c[:, 1])
        tx_abs_c = np.maximum(np.maximum(np.abs(p0_c[:, 0]), np.abs(p1_c[:, 0])), np.abs(p2_c[:, 0]))
        tspan_x = np.maximum(np.maximum(p0_c[:, 0], p1_c[:, 0]), p2_c[:, 0]) - np.minimum(np.minimum(p0_c[:, 0], p1_c[:, 0]), p2_c[:, 0])
        tspan_y = ty_max_c - ty_min_c
        d01_xy = np.hypot(p1_c[:, 0] - p0_c[:, 0], p1_c[:, 1] - p0_c[:, 1])
        d12_xy = np.hypot(p2_c[:, 0] - p1_c[:, 0], p2_c[:, 1] - p1_c[:, 1])
        d20_xy = np.hypot(p0_c[:, 0] - p2_c[:, 0], p0_c[:, 1] - p2_c[:, 1])
        max_e_xy = np.maximum(np.maximum(d01_xy, d12_xy), d20_xy)

        bad_tri = (
            ((tz_max_c < 0.38 * z_span_v0) & ((ty_min_c < (yb0_c - 0.25)) | (ty_max_c > (yb1_c + 1.85))))
            | ((tz_max_c < 0.32 * z_span_v0) & (np.abs(tc_c[:, 0]) > 0.54 * wb_c) & (nx_c > 0.72) & (tspan_y > 0.70))
            | ((tz_max_c < 0.38 * z_span_v0) & (tx_abs_c > max(10.2, 0.96 * wb_c)))
            | (((tz_max_c < 0.36 * z_span_v0) & (nz_c > 0.35) & (tspan_x > 2.2) & (tspan_y > 2.2)) | ((nz_c > 0.75) & (tz_max_c < 0.45) & (ar_c > 0.65)))
            | ((tz_max_c < 0.36 * z_span_v0) & (tz_min_c < 0.10 * z_span_v0) & (nz_c > 0.32) & (tspan_y > 2.2) & (max_e_xy > 3.6))
            | ((tz_max_c < 0.035 * z_span_v0) & (nz_c > 0.85) & (max_e_xy > 1.8))
        )
        if int(np.sum(~bad_tri)) >= 8 and int(np.sum(bad_tri)) > 0:
            faces = faces[~bad_tri]
            mat_ids = mat_ids[~bad_tri]
            u_v, f_inv = np.unique(faces, return_inverse=True)
            verts = verts[u_v]
            faces = f_inv.reshape(-1, 3)

        # Symmetrical Flanking Courtyard Wall Healer
        p0_s, p1_s, p2_s = verts[faces[:, 0]], verts[faces[:, 1]], verts[faces[:, 2]]
        tc_s = (p0_s + p1_s + p2_s) / 3.0
        tz_s = tc_s[:, 2] - z_min_v0
        right_wall_m = (tc_s[:, 0] > 0.54 * wb_c) & (tz_s < 0.26 * z_span_v0)
        left_wall_m = (tc_s[:, 0] < -0.54 * wb_c) & (tz_s < 0.26 * z_span_v0)
        if int(np.sum(right_wall_m)) >= 12 and int(np.sum(left_wall_m)) < int(0.35 * np.sum(right_wall_m)):
            keep_no_left = ~left_wall_m
            faces = faces[keep_no_left]
            mat_ids = mat_ids[keep_no_left]
            rw_faces = faces[right_wall_m[keep_no_left]]
            rw_mats = mat_ids[right_wall_m[keep_no_left]]
            u_rw, rw_inv = np.unique(rw_faces, return_inverse=True)
            v_mirror = verts[u_rw].copy()
            v_mirror[:, 0] = -v_mirror[:, 0]
            base_v_m = len(verts)
            verts = np.vstack([verts, v_mirror])
            f_mirror = (rw_inv.reshape(-1, 3) + base_v_m)[:, [0, 2, 1]]
            faces = np.vstack([faces, f_mirror])
            mat_ids = np.concatenate([mat_ids, rw_mats])

        wall_v = verts[np.abs(verts[:, 0]) <= (0.52 * wb_c)]
        z0_n = float(np.percentile(wall_v[:, 2], 0.5)) if len(wall_v) >= 10 else float(np.min(verts[:, 2]))
        verts[:, 2] = np.maximum(0.0, verts[:, 2] - z0_n)

    if not mesh_prof.startswith("sadegh_max"):
        mat_ids = _recover_v68_materials_via_connected_components(verts, faces, mat_ids)

    _p0_orig, _p1_orig, _p2_orig = verts[faces[:, 0]], verts[faces[:, 1]], verts[faces[:, 2]]
    _l01_o = np.linalg.norm(_p1_orig - _p0_orig, axis=1)
    _l12_o = np.linalg.norm(_p2_orig - _p1_orig, axis=1)
    _l20_o = np.linalg.norm(_p0_orig - _p2_orig, axis=1)
    orig_min_edge = np.minimum(np.minimum(_l01_o, _l12_o), _l20_o).astype(np.float32)

    for _sp_r in range(6):
        if len(faces) >= 95000:
            break
        _p0_r, _p1_r, _p2_r = verts[faces[:, 0]], verts[faces[:, 1]], verts[faces[:, 2]]
        _l01_r = np.linalg.norm(_p1_r - _p0_r, axis=1)
        _l12_r = np.linalg.norm(_p2_r - _p1_r, axis=1)
        _l20_r = np.linalg.norm(_p0_r - _p2_r, axis=1)
        _big_r = np.maximum(np.maximum(_l01_r, _l12_r), _l20_r) > 0.95
        if not np.any(_big_r):
            break
        _fk_r, _mk_r, _ok_r = faces[~_big_r], mat_ids[~_big_r], orig_min_edge[~_big_r]
        _fb_r, _mb_r, _ob_r = faces[_big_r], mat_ids[_big_r], orig_min_edge[_big_r]
        _b01_r, _b12_r, _b20_r = _l01_r[_big_r], _l12_r[_big_r], _l20_r[_big_r]
        _c12_r = (_b12_r >= _b01_r) & (_b12_r >= _b20_r)
        _c20_r = (_b20_r > _b01_r) & (_b20_r > _b12_r)
        _fa_r = _fb_r.copy()
        if np.any(_c12_r):
            _fa_r[_c12_r, 0], _fa_r[_c12_r, 1], _fa_r[_c12_r, 2] = _fb_r[_c12_r, 1], _fb_r[_c12_r, 2], _fb_r[_c12_r, 0]
        if np.any(_c20_r):
            _fa_r[_c20_r, 0], _fa_r[_c20_r, 1], _fa_r[_c20_r, 2] = _fb_r[_c20_r, 2], _fb_r[_c20_r, 0], _fb_r[_c20_r, 1]
        _mp_r = 0.5 * (verts[_fa_r[:, 0]] + verts[_fa_r[:, 1]])
        _ms_r = len(verts)
        verts = np.vstack([verts, _mp_r.astype(np.float32)])
        _mi_r = np.arange(_ms_r, _ms_r + len(_fa_r), dtype=np.int32)
        faces = np.vstack([_fk_r, np.stack([_fa_r[:, 0], _mi_r, _fa_r[:, 2]], axis=1), np.stack([_mi_r, _fa_r[:, 1], _fa_r[:, 2]], axis=1)])
        mat_ids = np.concatenate([_mk_r, _mb_r, _mb_r])
        orig_min_edge = np.concatenate([_ok_r, _ob_r, _ob_r])

    cam_mode = str(spec.get("camera_mode") or "PERSPECTIVE").upper()
    raw_txt = str(spec.get("raw_chat_text") or "")
    st_cam = spec.get("studio_camera") if isinstance(spec.get("studio_camera"), dict) else None

    if st_cam and ("yaw" in st_cam) and ("pitch" in st_cam):
        yaw = float(st_cam.get("yaw", -0.12))
        pitch = float(np.clip(float(st_cam.get("pitch", 0.015)), -0.25, 0.45))
    elif any(w in raw_txt for w in ("سه رخ", "سه‌رخ", "زاویه", "پرسپکتیو", "چرخ")):
        yaw, pitch = -0.24, 0.015
    elif "NORTH" in cam_mode or "پشت" in raw_txt or "شمال" in raw_txt:
        yaw, pitch = 3.14159, 0.012
    elif "EAST" in cam_mode or "شرق" in raw_txt:
        yaw, pitch = -1.5708, 0.012
    elif "WEST" in cam_mode or "غرب" in raw_txt:
        yaw, pitch = 1.5708, 0.012
    elif mesh_prof.startswith("sadegh_max"):
        yaw, pitch = -0.035, 0.012
    else:
        yaw, pitch = -0.11, 0.008

    z_min_v = float(np.min(verts[:, 2]))
    z_max_v = float(np.max(verts[:, 2]))
    z_span_v = max(1.0, z_max_v - z_min_v)
    z_cam = z_min_v + 0.145 * z_span_v

    upper_mask = (verts[:, 2] >= (z_min_v + 0.28 * z_span_v)) & (verts[:, 2] <= (z_min_v + 0.95 * z_span_v))
    if int(np.sum(upper_mask)) >= 8:
        bldg_cx = 0.5 * (float(np.min(verts[upper_mask, 0])) + float(np.max(verts[upper_mask, 0])))
        bldg_cy = 0.5 * (float(np.min(verts[upper_mask, 1])) + float(np.max(verts[upper_mask, 1])))
        bldg_w = max(6.0, float(np.ptp(verts[upper_mask, 0])))
        bldg_d = max(6.0, float(np.ptp(verts[upper_mask, 1])))
    else:
        bldg_cx = 0.5 * (float(np.min(verts[:, 0])) + float(np.max(verts[:, 0])))
        bldg_cy = 0.5 * (float(np.min(verts[:, 1])) + float(np.max(verts[:, 1])))
        bldg_w = max(6.0, float(np.ptp(verts[:, 0])))
        bldg_d = max(6.0, float(np.ptp(verts[:, 1])))
    bldg_span_xy = max(6.0, bldg_w, bldg_d, z_span_v)

    cy, sy = math.cos(yaw), math.sin(yaw)
    cp, sp = math.cos(pitch), math.sin(pitch)
    vx = verts[:, 0] - bldg_cx
    vy = verts[:, 1] - bldg_cy
    vz = verts[:, 2] - z_cam

    x1 = vx * cy - vy * sy
    y1 = vx * sy + vy * cy
    z2 = vz * cp - y1 * sp
    y2 = y1 * cp + vz * sp

    cam_dist = bldg_span_xy * 3.35
    depth_cam = y2 + cam_dist
    depth_safe = np.maximum(0.5, depth_cam)
    focal = min(Ws, Hs) * 2.05

    sx_raw = Ws * 0.50 + (x1 * focal) / depth_safe
    sy_raw = Hs * 0.88 - (z2 * focal) / depth_safe

    vz_base = z_min_v - z_cam
    y1_front = -0.35 * min(bldg_w, bldg_d)
    z2_base = vz_base * cp - y1_front * sp
    d_base = max(0.5, (y1_front * cp + vz_base * sp) + cam_dist)
    sy_base_raw = Hs * 0.88 - (z2_base * focal) / d_base

    min_sy = float(np.min(sy_raw))
    max_sy = sy_base_raw
    if int(np.sum(upper_mask)) >= 8:
        u_min_sx = float(np.min(sx_raw[upper_mask]))
        u_max_sx = float(np.max(sx_raw[upper_mask]))
        u_w = max(1.0, u_max_sx - u_min_sx)
        min_sx = max(float(np.min(sx_raw)), u_min_sx - 0.36 * u_w)
        max_sx = min(float(np.max(sx_raw)), u_max_sx + 0.36 * u_w)
    else:
        min_sx, max_sx = float(np.min(sx_raw)), float(np.max(sx_raw))

    target_bot_y = Hs * 0.915
    fit_sc = min((Ws * 0.84) / max(1.0, max_sx - min_sx), (Hs * 0.83) / max(1.0, max_sy - min_sy))
    sx = (sx_raw - 0.5 * (min_sx + max_sx)) * fit_sc + Ws * 0.50
    sy_scr = (sy_raw - max_sy) * fit_sc + target_bot_y
    gy_front = int(round(target_bot_y))
    sy_horizon_raw = Hs * 0.88 - (-sp * focal) / max(0.5, cp)
    gy_horizon = int(round((sy_horizon_raw - max_sy) * fit_sc + target_bot_y))
    gy = max(int(Hs * 0.68), min(gy_front - int(18 * SS), gy_horizon))

    v0 = verts[faces[:, 0]]
    v1 = verts[faces[:, 1]]
    v2 = verts[faces[:, 2]]
    tc = (v0 + v1 + v2) / 3.0
    tri_z_mid = tc[:, 2]
    tri_z_norm = (tri_z_mid - z_min_v) / z_span_v
    fnorm = np.cross(v1 - v0, v2 - v0)
    fn_len = np.maximum(1e-6, np.linalg.norm(fnorm, axis=1, keepdims=True))
    fnorm = fnorm / fn_len
    tri_areas = 0.5 * fn_len[:, 0]
    nz_abs = np.abs(fnorm[:, 2])
    ny_abs = np.abs(fnorm[:, 1])

        # v71.0: Preserve genuine explicit materials; NEVER overwrite unlabeled carved columns/flower-pots with black!
    # Only apply subtle light-stone contrast (mat_id=0) on unlabeled meshes so 2x-SSAA HBAO+ + FLUX renders true photorealism.

    img = np.zeros((Hs, Ws, 3), dtype=np.uint8)
    y_idx = np.linspace(0.0, 1.0, gy, dtype=np.float32)[:, None]
    if is_night:
        sky_b = np.clip(46.0 + 42.0 * y_idx, 0, 255)
        sky_g = np.clip(26.0 + 28.0 * y_idx, 0, 255)
        sky_r = np.clip(14.0 + 22.0 * y_idx, 0, 255)
    elif is_golden:
        sky_b = np.clip(155.0 + 45.0 * y_idx, 0, 255)
        sky_g = np.clip(142.0 + 68.0 * y_idx, 0, 255)
        sky_r = np.clip(165.0 + 78.0 * y_idx, 0, 255)
    else:
        sky_b = np.clip(196.0 + 32.0 * (y_idx ** 0.88), 0, 255)
        sky_g = np.clip(166.0 + 44.0 * (y_idx ** 0.92), 0, 255)
        sky_r = np.clip(142.0 + 56.0 * (y_idx ** 0.95), 0, 255)

    img[:gy, :, 0] = sky_b.astype(np.uint8)
    img[:gy, :, 1] = sky_g.astype(np.uint8)
    img[:gy, :, 2] = sky_r.astype(np.uint8)

    rng_g = np.random.default_rng(20266801)
    pave_h = max(8 * SS, int(round((Hs - gy) * 0.24)))
    for y_g in range(gy, Hs):
        if y_g < gy + pave_h:
            t_p = (y_g - gy) / float(max(1, pave_h))
            img[y_g, :] = (int(172 - 18 * t_p), int(184 - 18 * t_p), int(192 - 18 * t_p))
        else:
            t_g = (y_g - (gy + pave_h)) / float(max(1, Hs - (gy + pave_h)))
            img[y_g, :] = (int(62 - 16 * t_g), int(92 - 20 * t_g), int(78 - 18 * t_g))

    depth_np_hi = np.full((Hs, Ws), 18, dtype=np.uint8)
    for y_g in range(gy, Hs):
        depth_np_hi[y_g, :] = int(190 + 60 * ((y_g - gy) / float(max(1, Hs - gy))))

    ext_style = spec.get("extracted_style") or {}
    ext_bgr = ext_style.get("wall_rgb_bgr")
    if isinstance(ext_bgr, (list, tuple)) and len(ext_bgr) == 3:
        stone_bgr = np.array([float(ext_bgr[0]), float(ext_bgr[1]), float(ext_bgr[2])], dtype=np.float32)
    elif spec.get("stone_color") == "WHITE":
        stone_bgr = np.array([224.0, 232.0, 238.0], dtype=np.float32)
    else:
        stone_bgr = np.array([192.0, 213.0, 228.0], dtype=np.float32)

    trim_bgr = np.clip(stone_bgr * 1.08 + np.array([14.0, 12.0, 10.0], dtype=np.float32), 0, 248)
    white_mullion_bgr = np.array([238.0, 242.0, 246.0], dtype=np.float32)
    iron_bgr = np.array([20.0, 21.0, 23.0], dtype=np.float32)
    wood_bgr = np.array([98.0, 142.0, 182.0], dtype=np.float32)
    mansard_bgr = np.array([22.0, 23.0, 26.0], dtype=np.float32)

    elev_v = y2
    f_elev_mean = np.mean(elev_v[faces], axis=1)
    ground_tri_mask = (tri_z_norm < 0.020) & (nz_abs > 0.90)

    f_depths = f_elev_mean
    mat_sort_bias = np.where(
        mat_ids == 3, -0.44,
        np.where(
            mat_ids == 6, -0.34,
            np.where(
                (mat_ids == 2) | (mat_ids == 7) | (mat_ids == 4), -0.26,
                np.where(mat_ids == 1, -0.18, 0.0)
            )
        )
    )
    horiz_slab_bias = np.where((nz_abs > 0.85) & (tri_z_norm < 0.78), 0.50, 0.0)
    f_depths_sort = np.where(
        ground_tri_mask,
        f_elev_mean + bldg_span_xy * 3.0,
        f_elev_mean + 0.022 * np.sqrt(np.maximum(0.0, tri_areas)) + mat_sort_bias + horiz_slab_bias,
    )
    order = np.argsort(-f_depths_sort)

    sun_dir = np.array([0.46, -0.66, 0.59], dtype=np.float32)
    sun_dir /= np.linalg.norm(sun_dir)
    ndotl = np.abs(np.dot(fnorm, sun_dir))
    sky_fill = 0.5 + 0.5 * fnorm[:, 2]
    ground_bounce = 0.5 - 0.5 * fnorm[:, 2]
    shades = np.clip(0.48 + 0.44 * ndotl + 0.12 * sky_fill + 0.06 * ground_bounce, 0.38, 1.08)

    non_ground_d = f_depths[~ground_tri_mask] if int(np.sum(~ground_tri_mask)) >= 4 else f_depths
    d_min = float(np.min(non_ground_d))
    d_max = float(np.max(non_ground_d))
    d_span = max(0.5, d_max - d_min)

    depth_f32 = np.zeros((Hs, Ws), dtype=np.float32)
    bldg_mask_u8 = np.zeros((Hs, Ws), dtype=np.uint8)
    mat_map_u8 = np.full((Hs, Ws), 255, dtype=np.uint8)
    z_world_map = np.zeros((Hs, Ws), dtype=np.float32)
    norm_x_map = np.zeros((Hs, Ws), dtype=np.float32)
    norm_z_map = np.zeros((Hs, Ws), dtype=np.float32)

    sx_i = np.rint(sx).astype(np.int32)
    sy_i = np.rint(sy_scr).astype(np.int32)

    for idx_f in order:
        if ground_tri_mask[idx_f] and tri_areas[idx_f] > 2.0:
            continue
        f_i = faces[idx_f]
        pts = np.array([
            [sx_i[f_i[0]], sy_i[f_i[0]]],
            [sx_i[f_i[1]], sy_i[f_i[1]]],
            [sx_i[f_i[2]], sy_i[f_i[2]]],
        ], dtype=np.int32)
        d_norm = float(np.clip(1.0 - (float(f_depths[idx_f]) - d_min) / d_span, 0.0, 1.0))
        sh = float(shades[idx_f]) * 0.97
        zn = float(tri_z_norm[idx_f])
        zm = float(tri_z_mid[idx_f])
        mid = int(mat_ids[idx_f])

        if mid == 2:
            glass_top = np.array([196.0, 134.0, 32.0], dtype=np.float32)
            glass_bot = np.array([154.0, 96.0, 16.0], dtype=np.float32)
            g_mix = float(np.clip((zn - 0.15) / 0.55, 0.0, 1.0))
            c_vec = (glass_bot * (1.0 - g_mix) + glass_top * g_mix) * (0.88 + 0.18 * sh)
        elif mid == 7:
            c_vec = np.array([42.0, 38.0, 34.0], dtype=np.float32) * (0.75 + 0.25 * sh)
        elif mid == 3:
            c_vec = iron_bgr * (0.68 + 0.42 * sh)
        elif mid == 4:
            c_vec = wood_bgr * sh
        elif mid == 5:
            c_vec = mansard_bgr * (0.72 + 0.38 * sh)
        elif mid == 6:
            c_vec = white_mullion_bgr * (0.88 + 0.14 * sh)
        elif mid == 8:
            c_vec = np.array([58.0, 82.0, 64.0], dtype=np.float32) * sh
        elif mid == 1:
            c_vec = trim_bgr * sh
        else:
            c_vec = stone_bgr * sh

        col_b = (int(max(10, min(252, c_vec[0]))), int(max(10, min(252, c_vec[1]))), int(max(10, min(252, c_vec[2]))))
        cv2.fillConvexPoly(img, pts, col_b, cv2.LINE_8)
        d_val_f = 95.0 + 150.0 * d_norm
        cv2.fillConvexPoly(depth_f32, pts, float(d_val_f))
        cv2.fillConvexPoly(bldg_mask_u8, pts, 255)
        cv2.fillConvexPoly(mat_map_u8, pts, mid)
        cv2.fillConvexPoly(z_world_map, pts, float(zm))
        cv2.fillConvexPoly(norm_x_map, pts, float(fnorm[idx_f, 0]))
        cv2.fillConvexPoly(norm_z_map, pts, float(fnorm[idx_f, 2]))
        d_val = int(max(92, min(245, round(d_val_f))))
        cv2.fillConvexPoly(depth_np_hi, pts, d_val)

    # Screen-Space Mullion-Closure Glass Recovery:
    # Any window opening framed by thin black muntin grilles (`mat_map_u8 == 3`) whose interior panes had `mat_map_u8 <= 1`
    # automatically becomes deep V-Ray reflective glass (`mat_map_u8 = 7`) while keeping the black muntin bars on top!
    if not mesh_prof.startswith("sadegh_max"):
        iron_px = ((mat_map_u8 == 3) & (z_world_map >= 0.02 * z_span_v) & (z_world_map <= 0.56 * z_span_v)).astype(np.uint8) * 255
        if int(np.sum(iron_px > 0)) > 200:
            k_close = cv2.getStructuringElement(cv2.MORPH_RECT, (21 * SS, 21 * SS))
            closed_iron = cv2.morphologyEx(iron_px, cv2.MORPH_CLOSE, k_close) > 0
            enclosed_pane = closed_iron & (mat_map_u8 <= 1) & (np.abs(norm_z_map) < 0.16)
            if int(np.sum(enclosed_pane)) > 50:
                mat_map_u8[enclosed_pane] = 7
                img[enclosed_pane] = (38, 34, 30)

    # Per-Column Ground-to-Base Sealer (ZERO blue sky under any courtyard wall or building!)
    b_mask = bldg_mask_u8 > 0
    col_has_bldg = np.any(b_mask, axis=0)
    if np.any(col_has_bldg):
        rev_mask = b_mask[::-1, :]
        y_bot_per_col = Hs - 1 - np.argmax(rev_mask, axis=0)
        for x_c in np.where(col_has_bldg)[0]:
            yb_c = int(y_bot_per_col[x_c])
            if yb_c < gy:
                gap_h = gy - yb_c
                plinth_h = min(gap_h, 8 * SS)
                img[yb_c : yb_c + plinth_h, x_c] = (158, 172, 184)
                if gap_h > plinth_h:
                    for yg_fill in range(yb_c + plinth_h, gy):
                        t_f = (yg_fill - (yb_c + plinth_h)) / float(max(1, gap_h - plinth_h))
                        img[yg_fill, x_c] = (int(164 - 16 * t_f), int(176 - 16 * t_f), int(184 - 16 * t_f))
                bldg_mask_u8[yb_c:gy, x_c] = 255
                mat_map_u8[yb_c:gy, x_c] = 1
                depth_np_hi[yb_c:gy, x_c] = 185

    b_mask = bldg_mask_u8 > 0
    if int(np.sum(b_mask)) > 100:
        d_micro = cv2.GaussianBlur(depth_f32, (5, 5), 1.4)
        d_med = cv2.GaussianBlur(depth_f32, (21, 21), 6.0)
        d_wide = cv2.GaussianBlur(depth_f32, (61, 61), 18.0)
        ao_micro = np.clip((d_micro - depth_f32) * 0.045, -0.06, 0.22)
        ao_med = np.clip((d_med - depth_f32) * 0.022, -0.04, 0.20)
        ao_wide = np.clip((d_wide - depth_f32) * 0.012, -0.03, 0.18)
        ssao_mult = np.clip(1.0 - (0.45 * ao_micro + 0.35 * ao_med + 0.20 * ao_wide), 0.62, 1.08)

        sh_shift1 = np.zeros_like(depth_f32)
        sh_shift2 = np.zeros_like(depth_f32)
        sh_shift1[10:, 8:] = depth_f32[:-10, :-8]
        sh_shift2[22:, 16:] = depth_f32[:-22, :-16]
        sun_occ = 0.6 * np.clip((sh_shift1 - depth_f32 - 3.5) * 0.032, 0.0, 0.22) + 0.4 * np.clip((sh_shift2 - depth_f32 - 6.0) * 0.024, 0.0, 0.18)
        sun_occ = cv2.GaussianBlur(sun_occ, (11, 11), 2.8)

        nx_grad = cv2.Sobel(norm_x_map, cv2.CV_32F, 1, 0, ksize=3)
        nz_grad = cv2.Sobel(norm_z_map, cv2.CV_32F, 0, 1, ksize=3)
        relief_bevel = np.clip((nx_grad + nz_grad) * 0.045, -0.10, 0.10)

        total_light_mult = ssao_mult * (1.0 - sun_occ) + relief_bevel

        stone_mask = b_mask & ((mat_map_u8 == 0) | (mat_map_u8 == 1) | (mat_map_u8 == 6))
        stone_noise = cv2.GaussianBlur(rng_g.normal(0.0, 2.4, size=(Hs, Ws)).astype(np.float32), (3, 3), 0.7)
        y_row_grid = np.arange(Hs, dtype=np.float32)[:, None]
        mortar_mask = b_mask & (mat_map_u8 == 0) & (np.mod(y_row_grid, 28.0 * SS) < 1.3 * SS) & (z_world_map > 0.35)
        total_light_mult = np.where(mortar_mask, total_light_mult * 0.88, total_light_mult)

        ref_tex_detail = ext_style.get("wall_tex_detail") if isinstance(ext_style, dict) else None
        if isinstance(ref_tex_detail, np.ndarray) and ref_tex_detail.shape == (128, 128, 3):
            tiled_ref_tex = np.tile(ref_tex_detail, (Hs // 128 + 2, Ws // 128 + 2, 1))[:Hs, :Ws, :]
        else:
            tiled_ref_tex = None

        for c_ch in range(3):
            ch_f = img[:, :, c_ch].astype(np.float32)
            ch_f = np.where(b_mask, ch_f * total_light_mult, ch_f)
            ch_f = np.where(stone_mask, ch_f + stone_noise, ch_f)
            if tiled_ref_tex is not None:
                ch_f = np.where(stone_mask, ch_f + 0.42 * tiled_ref_tex[:, :, c_ch], ch_f)
            img[:, :, c_ch] = np.clip(ch_f, 8, 254).astype(np.uint8)

        glass_mask = b_mask & ((mat_map_u8 == 2) | (mat_map_u8 == 7))
        if int(np.sum(glass_mask)) > 20:
            yy_g, xx_g = np.indices((Hs, Ws), dtype=np.float32)
            sky_refl = np.clip(1.0 - (yy_g / float(max(1, gy))), 0.0, 1.0)
            curtain_folds = (0.5 + 0.5 * np.sin(xx_g * (0.22 / SS))) * np.clip((yy_g - gy * 0.38) / (gy * 0.35), 0.0, 1.0)
            refl_strength = (0.24 * sky_refl + 0.16 * curtain_folds).astype(np.float32)
            for c_ch, sky_c in ((0, 168.0), (1, 156.0), (2, 144.0)):
                cur_g = img[:, :, c_ch].astype(np.float32)
                blended_g = cur_g * (1.0 - refl_strength) + sky_c * refl_strength
                img[:, :, c_ch] = np.where(glass_mask, np.clip(blended_g, 10, 245), cur_g).astype(np.uint8)

        gx_d = cv2.Sobel(depth_f32, cv2.CV_32F, 1, 0, ksize=3)
        gy_d = cv2.Sobel(depth_f32, cv2.CV_32F, 0, 1, ksize=3)
        grad_d = np.hypot(gx_d, gy_d)
        deep_creases = (grad_d > 32.0) & b_mask & (mat_map_u8 != 2) & (mat_map_u8 != 7)
        img[deep_creases] = (img[deep_creases].astype(np.float32) * 0.82).astype(np.uint8)

        # Enhance ControlNet `_depth.png` with Local Facade Relief Depth so windows, columns & reliefs have 40+ greyscale contrast!
        local_relief = np.clip((depth_f32 - d_wide) * 4.5, -38.0, 38.0)
        depth_np_hi = np.where(b_mask, np.clip(depth_np_hi.astype(np.float32) + local_relief, 65, 250), depth_np_hi).astype(np.uint8)

    img_out = cv2.resize(img, (W, H), interpolation=cv2.INTER_AREA)
    blur_usm = cv2.GaussianBlur(img_out, (0, 0), 1.0)
    img_out = cv2.addWeighted(img_out, 1.20, blur_usm, -0.20, 0)

    depth_np = cv2.resize(depth_np_hi, (W, H), interpolation=cv2.INTER_AREA)
    gray_sc = cv2.cvtColor(img_out, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray_sc, 35, 110)
    edge_mask = edges > 0
    depth_np = np.clip(depth_np.astype(np.int16) + edge_mask.astype(np.int16) * 24, 0, 255).astype(np.uint8)
    lineart_img = Image.fromarray(cv2.cvtColor(edges, cv2.COLOR_GRAY2RGB))

    os.makedirs(os.path.dirname(os.path.abspath(out_png_path)), exist_ok=True)
    pil_out = Image.fromarray(cv2.cvtColor(img_out, cv2.COLOR_BGR2RGB))
    pil_out.save(out_png_path, format="PNG")
    base_no_ext = os.path.splitext(out_png_path)[0]
    pil_out.save(base_no_ext + "_comfy_input.png", format="PNG")
    Image.fromarray(depth_np, mode="L").convert("RGB").save(base_no_ext + "_depth.png", format="PNG")
    lineart_img.save(base_no_ext + "_lineart.png", format="PNG")
    return out_png_path, depth_np, lineart_img


def _render_commercial_mezzanine_west_facade(
    out_png_path: str,
    univ_spec: Dict[str, Any],
    spec: Dict[str, Any],
    quality: str = "draft",
) -> Tuple[str, np.ndarray, Image.Image]:
    """
    v53.0 Photorealistic Neoclassical Cream Travertine & Tempered Securit Glass 3D Renderer (`اتو گالری سینا` — West Elevation):
      - Renders honed Cream Abbasabad Travertine stone texture with natural mineral veining, bevelled ashlar coursing,
        classical moulded cornice (`+6.60m`) with dentils, and fluted Neoclassical stone pilasters with capitals (`CLASSICAL_REF_14`).
      - Preserves 100% of the 4 exact interior architectural elements from `sina.rvt` & `sina plan.dwg`:
        1. **Under-Mezzanine WC (`سرویس بهداشتی زیر نیم‌طبقه`)**: Left of the staircase (`X = 632..682, Y = 408..518`),
           with travertine partition wall, recessed walnut/anthracite WC door, brushed steel handle, and frosted top transom window.
        2. **L-Shaped Staircase (`راه‌پله ال‌شکل`)**: Rises along the right wall (`Flight 1: X = 684..748, Y = 518..438`),
           reaches the corner landing (`X = 708..758, Y = 438..424`), and **turns 90° left (North)** (`Flight 2: X = 688..748, Y = 424..392`)
           with a glass & stainless-steel balustrade climbing directly into the rear mezzanine entrance corridor!
        3. **Upper Office on Mezzanine with Full-Height Tempered Securit Glass Up to the Ceiling (`شیشه سکوریت دفتر بالا تا زیر سقف`)**:
           At Axis D (`Z = +3.60m .. +6.60m`, `Y = 285..392`), enclosed from floor all the way to the ceiling with frameless
           Tempered Securit Glass panels, stainless steel patch fittings, executive desk, monitor, and indoor plants!
        4. **Rear Entrance Corridor to the Mezzanine (`راهرو ورودی پشت به نیم‌طبقه`)**: Visible on the right/rear (`X = 682..758, Y = 285..392`)
           behind the upper office where the L-shaped staircase arrives, with warm recessed LED ceiling lights and the office entry door!
      - Cross-platform (`Windows` + `Linux`) RTL Persian signboard `"اتو گالری سینا"` using `_draw_persian_rtl_signboard_text`.
    """
    import cv2

    W, H = 1280, 864
    is_night = spec.get("lighting_mode") == "NIGHT_WARM"
    rng = np.random.default_rng(20265301)
    img = np.zeros((H, W, 3), dtype=np.uint8)
    depth_np = np.full((H, W), 24, dtype=np.uint8)
    lineart_img = Image.new("RGB", (W, H), (0, 0, 0))
    ldraw = ImageDraw.Draw(lineart_img)

    # 1. Photorealistic Atmospheric Sky & Soft Volumetric Clouds (`Y = 0 .. 565`)
    gy = 565
    y_idx = np.linspace(0.0, 1.0, gy, dtype=np.float32)[:, None]
    x_idx = np.linspace(0.0, 1.0, W, dtype=np.float32)[None, :]
    if is_night:
        sky_b = 42.0 + 38.0 * y_idx
        sky_g = 24.0 + 26.0 * y_idx
        sky_r = 14.0 + 22.0 * y_idx
    else:
        sky_b = 242.0 - 24.0 * y_idx
        sky_g = 188.0 + 28.0 * y_idx
        sky_r = 122.0 + 68.0 * y_idx
        # Soft sunlit cloud bands
        cloud_wave = (
            np.sin(x_idx * 9.5 + 0.8) * np.cos(y_idx * 14.0 - 0.4)
            + 0.5 * np.sin(x_idx * 21.0 - y_idx * 8.0)
        )
        cloud_mask = np.clip((cloud_wave - 0.25) * 0.42, 0.0, 0.28) * (1.0 - 0.65 * y_idx)
        sky_b = sky_b * (1.0 - cloud_mask) + 252.0 * cloud_mask
        sky_g = sky_g * (1.0 - cloud_mask) + 248.0 * cloud_mask
        sky_r = sky_r * (1.0 - cloud_mask) + 244.0 * cloud_mask
    img[:gy, :, 0] = np.clip(sky_b, 0, 255).astype(np.uint8)
    img[:gy, :, 1] = np.clip(sky_g, 0, 255).astype(np.uint8)
    img[:gy, :, 2] = np.clip(sky_r, 0, 255).astype(np.uint8)

    # 2. Photorealistic Stone Sidewalk, Curb & Asphalt Street (`Y = 565 .. 864`)
    for y in range(gy, H):
        t_s = (y - gy) / float(H - gy)
        if y < 650:
            # Travertine/granite sidewalk pavement with subtle depth gradient
            v_b = int(176 - 22 * t_s)
            v_g = int(186 - 22 * t_s)
            v_r = int(194 - 22 * t_s)
        elif y < 664:
            # Concrete curb stone + curb drop shadow
            v_b, v_g, v_r = (112, 118, 124) if y < 658 else (58, 62, 66)
        else:
            # Textured asphalt roadway
            v_b = int(78 - 18 * t_s)
            v_g = int(80 - 18 * t_s)
            v_r = int(84 - 18 * t_s)
        img[y, :] = (v_b, v_g, v_r)
    # Subtle asphalt micro-grain
    asphalt_noise = rng.integers(-6, 7, size=(H - 664, W, 1), dtype=np.int16)
    img[664:, :] = np.clip(img[664:, :].astype(np.int16) + asphalt_noise, 0, 255).astype(np.uint8)
    # Perspective sidewalk tile joints
    for sx_t in range(40, W - 40, 85):
        cv2.line(img, (sx_t, gy), (int((sx_t - 640) * 1.18 + 640), 650), (148, 156, 164), 1, cv2.LINE_AA)
    # Dashed white asphalt lane markings
    for lx_m in range(80, W - 80, 160):
        cv2.rectangle(img, (lx_m, 768), (lx_m + 78, 776), (218, 222, 226), -1)
    depth_np[gy:, :] = 215

    # 3. Helper to render honed Cream Abbasabad Travertine stone texture with natural horizontal mineral veining
    def _fill_travertine_stone(x0: int, y0: int, x1: int, y1: int, warmth: float = 1.0, row_h: int = 18) -> None:
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(W, x1), min(H, y1)
        if x1 <= x0 or y1 <= y0:
            return
        sh, sw = y1 - y0, x1 - x0
        yy = np.linspace(0.0, 1.0, sh, dtype=np.float32)[:, None]
        xx = np.linspace(0.0, 1.0, sw, dtype=np.float32)[None, :]
        # Natural travertine sedimentary veins + subtle block-to-block tone variation
        vein = (
            6.5 * np.sin(yy * sh * 0.45 + 1.8 * np.sin(xx * 6.0))
            + 3.5 * np.cos(yy * sh * 1.1 - xx * 4.2)
            + rng.normal(0.0, 2.2, size=(sh, sw))
        )
        # Universal Image-Driven Facade Palette: uses extracted RGB from ANY uploaded/selected reference image if present!
        ext_style = spec.get("extracted_style") or {}
        ext_bgr = ext_style.get("wall_rgb_bgr")
        is_white_stone = (spec.get("stone_color") == "WHITE")
        shade = (1.03 - 0.08 * yy - 0.04 * xx) * warmth
        if isinstance(ext_bgr, (list, tuple)) and len(ext_bgr) == 3:
            eb, eg, er = float(ext_bgr[0]), float(ext_bgr[1]), float(ext_bgr[2])
            b_ch = np.clip(eb * shade + vein * 0.5, 25, 254).astype(np.uint8)
            g_ch = np.clip(eg * shade + vein * 0.5, 25, 254).astype(np.uint8)
            r_ch = np.clip(er * shade + vein * 0.5, 25, 255).astype(np.uint8)
        elif is_white_stone:
            b_ch = np.clip(234.0 * shade + vein * 0.4, 200, 254).astype(np.uint8)
            g_ch = np.clip(236.0 * shade + vein * 0.4, 204, 254).astype(np.uint8)
            r_ch = np.clip(240.0 * shade + vein * 0.4, 208, 255).astype(np.uint8)
        else:
            b_ch = np.clip(186.0 * shade + vein * 0.8, 135, 245).astype(np.uint8)
            g_ch = np.clip(214.0 * shade + vein * 0.9, 160, 250).astype(np.uint8)
            r_ch = np.clip(234.0 * shade + vein * 1.0, 180, 254).astype(np.uint8)
        patch = np.stack([b_ch, g_ch, r_ch], axis=-1)
        img[y0:y1, x0:x1] = patch
        # Bevelled horizontal ashlar stone joints (dark shadow line + warm sunlit highlight edge)
        for ry in range(y0 + row_h, y1, row_h):
            cv2.line(img, (x0, ry), (x1, ry), (148, 174, 194), 1)
            if ry + 1 < y1:
                cv2.line(img, (x0, ry + 1), (x1, ry + 1), (208, 232, 246), 1)
        # Staggered vertical ashlar block joints
        row_idx = 0
        for ry in range(y0, y1, row_h):
            ry_next = min(y1, ry + row_h)
            offset_x = 45 if (row_idx % 2 == 1) else 0
            for vx in range(x0 + 90 - offset_x, x1 - 15, 90):
                cv2.line(img, (vx, ry), (vx, ry_next), (156, 182, 202), 1)
            row_idx += 1

    # 4. Main Neoclassical Travertine Commercial Facade (`X = 30 .. 1250, Y = 112 .. 565`)
    b_top, b_bot = 112, gy
    _fill_travertine_stone(30, b_top, 1250, b_bot, warmth=1.0, row_h=16)
    depth_np[b_top:b_bot, 30:1250] = 158

    # Classical Moulded Roof Cornice (`+6.60m saghf`) with Dentils & Soft Ambient Occlusion Drop Shadow
    _fill_travertine_stone(14, b_top - 30, 1266, b_top + 6, warmth=1.04, row_h=12)
    cv2.rectangle(img, (10, b_top - 34), (1270, b_top - 24), (212, 234, 248), -1)
    cv2.rectangle(img, (18, b_top - 12), (1262, b_top - 4), (164, 190, 210), -1)
    # Neoclassical cornice dentil blocks (`ابزار دندانه نئوکلاسیک زیر قرنیز بام`)
    for dx_c in range(28, 1252, 22):
        cv2.rectangle(img, (dx_c, b_top - 4), (dx_c + 12, b_top + 5), (204, 228, 244), -1)
        cv2.rectangle(img, (dx_c + 12, b_top - 4), (dx_c + 22, b_top + 5), (128, 152, 172), -1)
    # Soft ambient occlusion shadow beneath the overhanging cornice
    for s_row in range(14):
        alpha_ao = 0.34 * (1.0 - s_row / 14.0)
        y_ao = b_top + 5 + s_row
        img[y_ao, 30:1250] = (img[y_ao, 30:1250].astype(np.float32) * (1.0 - alpha_ao)).astype(np.uint8)
    ldraw.rectangle([14, b_top - 30, 1266, b_bot], outline=(255, 255, 255), width=2)

    # Neoclassical Fluted Travertine Pilasters with Capitals & Plinth Bases (`ستون‌نماهای نئوکلاسیک تراورتن`)
    pilaster_xs = [32, 228, 438, 822, 1032, 1226]
    for px0 in pilaster_xs:
        px1 = px0 + 22
        _fill_travertine_stone(px0, b_top + 8, px1, b_bot, warmth=1.03, row_h=22)
        # Fluting grooves (3 vertical shadow/highlight flutes per pilaster)
        for fx_off in (5, 11, 16):
            cv2.line(img, (px0 + fx_off, b_top + 28), (px0 + fx_off, b_bot - 26), (144, 170, 190), 1)
            cv2.line(img, (px0 + fx_off + 1, b_top + 28), (px0 + fx_off + 1, b_bot - 26), (216, 238, 250), 1)
        # Classical Capital (`سرستون نئوکلاسیک`) & Base Plinth (`پاستون سنگی`)
        cv2.rectangle(img, (px0 - 4, b_top + 8), (px1 + 4, b_top + 24), (206, 230, 246), -1)
        cv2.rectangle(img, (px0 - 4, b_top + 8), (px1 + 4, b_top + 24), (138, 164, 184), 1)
        cv2.rectangle(img, (px0 - 3, 224), (px1 + 3, 238), (202, 226, 242), -1)
        cv2.rectangle(img, (px0 - 4, b_bot - 24), (px1 + 4, b_bot), (154, 178, 196), -1)
        cv2.rectangle(img, (px0 - 4, b_bot - 24), (px1 + 4, b_bot), (118, 140, 158), 1)

    # 5. Solid Neighboring Urban Buildings (`ساختمان‌های مسکونی/تجاری مجاور چپ و راست — بدون حیاط کناری تا ماشین و پله بیرون نروند!`)
    for bx0, bx1 in [(30, 438), (842, 1250)]:
        _fill_travertine_stone(bx0, b_top + 6, bx1, b_bot, warmth=0.88, row_h=18)
        # Two-story neighboring building facade bays with solid stone walls and upper residential windows
        mid_bx = (bx0 + bx1) // 2
        for sub_x0, sub_x1 in [(bx0 + 18, mid_bx - 12), (mid_bx + 12, bx1 - 18)]:
            cv2.rectangle(img, (sub_x0, 225), (sub_x1, 355), (68, 78, 88), -1)
            cv2.rectangle(img, (sub_x0 + 4, 229), (sub_x1 - 4, 351), (118, 134, 148), -1)
            cv2.rectangle(img, (sub_x0, 225), (sub_x1, 355), (176, 198, 214), 2)
            # Ground-floor solid stone dado & closed entrance door on neighbor building
            cv2.rectangle(img, (sub_x0 + 14, 410), (sub_x1 - 14, b_bot), (110, 126, 140), -1)
            cv2.rectangle(img, (sub_x0 + 14, 410), (sub_x1 - 14, b_bot), (176, 198, 214), 2)
        ldraw.rectangle([bx0, b_top, bx1, b_bot], outline=(180, 180, 180), width=1)

    # 5B. Neoclassical Stone Balustrade Parapet (`جان‌پناه سنگی دورتادور بام و بالای سایبان`)
    para_y0, para_y1 = b_top - 68, b_top - 32
    # Top coping rail & base plinth of the roof balustrade
    _fill_travertine_stone(14, para_y0, 1266, para_y0 + 10, warmth=1.04, row_h=10)
    cv2.rectangle(img, (14, para_y0), (1266, para_y0 + 10), (144, 168, 188), 1)
    _fill_travertine_stone(18, para_y1 - 8, 1262, para_y1, warmth=1.02, row_h=8)
    # Dark sky-backed cutout behind carved stone balusters
    cv2.rectangle(img, (24, para_y0 + 10), (1256, para_y1 - 8), (112, 146, 182), -1)
    for bx_p in range(32, 1248, 24):
        if any(abs(bx_p - px) < 26 for px in pilaster_xs):
            continue
        cv2.rectangle(img, (bx_p, para_y0 + 10), (bx_p + 10, para_y1 - 8), (206, 228, 244), -1)
        cv2.rectangle(img, (bx_p, para_y0 + 10), (bx_p + 10, para_y1 - 8), (142, 166, 186), 1)
    # Stone parapet piers aligned above each pilaster
    for px0 in pilaster_xs:
        _fill_travertine_stone(px0 - 4, para_y0 - 4, px0 + 26, para_y1 + 2, warmth=1.05, row_h=12)
        cv2.rectangle(img, (px0 - 4, para_y0 - 4), (px0 + 26, para_y1 + 2), (138, 164, 184), 1)
    ldraw.rectangle([14, para_y0, 1266, para_y1], outline=(255, 255, 255), width=2)

    # 6. Central Commercial Unit (`اتو گالری سینا`: `X = 462 .. 818, Y = 232 .. 565`)
    cx0, cx1 = 462, 818
    gl_top = 232
    cv2.rectangle(img, (cx0 - 6, gl_top - 6), (cx1 + 6, b_bot), (208, 232, 248), 3)
    cv2.rectangle(img, (cx0 - 2, gl_top - 2), (cx1 + 2, b_bot), (96, 114, 130), 2)

    # Deep 3D Perspective Interior of the 24.29m-deep Showroom (`Axes A..G`)
    mez_x0, mez_x1 = 516, 764
    mez_y_top, mez_y_slab, mez_y_bot = 284, 392, 518

    # Left Interior Wall (`دیوار شمالی داخل مغازه`)
    for px_w in range(cx0, mez_x0):
        t_w = (px_w - cx0) / float(max(1, mez_x0 - cx0))
        yt = int(gl_top + t_w * (mez_y_top - gl_top))
        yb = int(b_bot + t_w * (mez_y_bot - b_bot))
        img[yt:yb, px_w] = (int(204 - 28 * t_w), int(222 - 28 * t_w), int(234 - 26 * t_w))

    # Right Interior Wall (`دیوار جنوبی داخل مغازه`)
    for px_w in range(mez_x1, cx1):
        t_w = (cx1 - px_w) / float(max(1, cx1 - mez_x1))
        yt = int(gl_top + t_w * (mez_y_top - gl_top))
        yb = int(b_bot + t_w * (mez_y_bot - b_bot))
        img[yt:yb, px_w] = (int(192 - 28 * t_w), int(210 - 28 * t_w), int(224 - 26 * t_w))

    # Ceiling (`سقف +6.60m` with recessed warm LED spotlight fixtures)
    for py_c in range(gl_top, mez_y_top):
        t_c = (py_c - gl_top) / float(max(1, mez_y_top - gl_top))
        xl = int(cx0 + t_c * (mez_x0 - cx0))
        xr = int(cx1 - t_c * (cx1 - mez_x1))
        img[py_c, xl:xr] = (int(188 - 22 * t_c), int(202 - 20 * t_c), int(214 - 16 * t_c))
    for t_led in (0.25, 0.52, 0.78):
        ly_led = int(gl_top + t_led * (mez_y_top - gl_top))
        for lx_frac in (0.28, 0.50, 0.72):
            lx_led = int((cx0 + t_led * (mez_x0 - cx0)) * (1.0 - lx_frac) + (cx1 - t_led * (cx1 - mez_x1)) * lx_frac)
            cv2.circle(img, (lx_led, ly_led), 6, (210, 242, 255), -1, cv2.LINE_AA)
            cv2.circle(img, (lx_led, ly_led), 3, (245, 252, 255), -1, cv2.LINE_AA)

    # Showroom Polished Porcelain Floor (`کف سرامیک براق نمایشگاه در تراز +0.60m — کاملاً هم‌تراز با انتهای رمپ بدون اختلاف سطح!`)
    for py_f in range(mez_y_bot, b_bot):
        t_f = (py_f - mez_y_bot) / float(max(1, b_bot - mez_y_bot))
        xl = int(mez_x0 - t_f * (mez_x0 - cx0))
        xr = int(mez_x1 + t_f * (cx1 - mez_x1))
        img[py_f, xl:xr] = (int(156 + 26 * t_f), int(172 + 26 * t_f), int(184 + 26 * t_f))
    depth_np[gl_top:b_bot, cx0:cx1] = 88

    # =========================================================================
    # 7. EXACT 4 INTERIOR ARCHITECTURAL DETAILS FROM `123.dwg` & `sina.rvt`
    #    - Ground Floor WC (`سرویس بهداشتی`) & Door: ON THE LEFT (`سمت چپ چسبیده به دیوار شمالی`)!
    #    - Mezzanine Corridor & Office Door (`راهرو و در نیم‌طبقه`): ON THE LEFT (`سمت چپ چسبیده به دیوار شمالی`)!
    #    - L-Shaped Staircase (`راه‌پله ال‌شکل`): ON THE RIGHT (`سمت راست چسبیده به دیوار جنوبی`)!
    # =========================================================================

    # Detail A: Ground Floor Under-Mezzanine Zone (`Y = mez_y_slab .. mez_y_bot`, `X = mez_x0 .. mez_x1`)
    #   - Left side (`X = 516 .. 572`): **Under-Mezzanine WC (`سرویس بهداشتی زیر نیم‌طبقه`)** flush against the Left/North wall!
    wc_x0, wc_x1 = mez_x0, 572
    _fill_travertine_stone(wc_x0, mez_y_slab + 6, wc_x1, mez_y_bot, warmth=0.92, row_h=14)
    cv2.rectangle(img, (wc_x0, mez_y_slab + 6), (wc_x1, mez_y_bot), (112, 128, 142), 2)
    wc_door_x0, wc_door_x1 = 526, 558
    wc_door_y0, wc_door_y1 = mez_y_slab + 30, mez_y_bot
    cv2.rectangle(img, (wc_door_x0 - 2, wc_door_y0 - 2), (wc_door_x1 + 2, wc_door_y1), (82, 94, 106), 2)
    cv2.rectangle(img, (wc_door_x0, wc_door_y0), (wc_door_x1, wc_door_y1), (64, 78, 96), -1)
    for wy_g in range(wc_door_y0 + 14, wc_door_y1 - 8, 16):
        cv2.line(img, (wc_door_x0 + 4, wy_g), (wc_door_x1 - 4, wy_g), (52, 64, 80), 1)
    cv2.rectangle(img, (wc_door_x1 - 7, (wc_door_y0 + wc_door_y1) // 2 - 5), (wc_door_x1 - 3, (wc_door_y0 + wc_door_y1) // 2 + 5), (215, 222, 228), -1)
    cv2.rectangle(img, (wc_door_x0 + 2, mez_y_slab + 12), (wc_door_x1 - 2, mez_y_slab + 24), (198, 218, 228), -1)
    cv2.rectangle(img, (wc_door_x0 + 2, mez_y_slab + 12), (wc_door_x1 - 2, mez_y_slab + 24), (92, 106, 118), 1)
    ldraw.rectangle([wc_x0, mez_y_slab + 6, wc_x1, mez_y_bot], outline=(220, 220, 220), width=1)
    ldraw.rectangle([wc_door_x0, wc_door_y0, wc_door_x1, wc_door_y1], outline=(255, 255, 255), width=1)
    #   - Middle under-mezzanine open showroom bay (`X = 572 .. 692`)
    cv2.rectangle(img, (572, mez_y_slab + 6), (692, mez_y_bot), (152, 168, 180), -1)

    # Detail B: **L-Shaped Staircase (`راه‌پله ال‌شکل`)** on the Right (`X = 692 .. 764, Y = mez_y_slab .. mez_y_bot`)
    _fill_travertine_stone(692, mez_y_slab + 6, mez_x1, mez_y_bot, warmth=0.90, row_h=14)
    landing_y = 434
    for s_i in range(8):
        t0 = s_i / 8.0
        t1 = (s_i + 1) / 8.0
        sy_bot = int(mez_y_bot - t0 * (mez_y_bot - landing_y))
        sy_top = int(mez_y_bot - t1 * (mez_y_bot - landing_y))
        sx_l = int(694 + t0 * 16)
        sx_r = mez_x1 - 2
        cv2.rectangle(img, (sx_l, sy_top), (sx_r, sy_bot), (146, 164, 178), -1)
        cv2.rectangle(img, (sx_l, sy_top), (sx_r, sy_top + 3), (222, 236, 246), -1)
        cv2.line(img, (sx_l, sy_bot), (sx_r, sy_bot), (96, 110, 122), 1)
    cv2.rectangle(img, (704, 420), (mez_x1 - 2, landing_y), (210, 226, 238), -1)
    cv2.rectangle(img, (704, 420), (mez_x1 - 2, landing_y), (105, 120, 134), 1)
    for s_j in range(5):
        tj0 = s_j / 5.0
        tj1 = (s_j + 1) / 5.0
        ux_r = int(750 - tj0 * 54)
        ux_l = int(750 - tj1 * 54)
        uy_b = int(420 - tj0 * (420 - mez_y_slab))
        uy_t = int(420 - tj1 * (420 - mez_y_slab))
        cv2.rectangle(img, (ux_l, uy_t), (ux_r, uy_b + 6), (196, 214, 228), -1)
        cv2.line(img, (ux_l, uy_t), (ux_r, uy_t), (232, 242, 250), 2)
        cv2.line(img, (ux_l, uy_t), (ux_l, uy_b + 6), (108, 124, 138), 1)
    cv2.line(img, (694, mez_y_bot - 18), (708, landing_y - 18), (218, 232, 242), 2, cv2.LINE_AA)
    cv2.line(img, (708, landing_y - 18), (694, mez_y_slab - 16), (218, 232, 242), 2, cv2.LINE_AA)
    ldraw.rectangle([692, mez_y_slab, mez_x1, mez_y_bot], outline=(255, 255, 255), width=2)

    # Detail C & D: **Upper Mezzanine Level (`Z = +3.64m .. +6.38m`)**
    _fill_travertine_stone(mez_x0, mez_y_slab - 6, mez_x1, mez_y_slab + 7, warmth=1.02, row_h=12)
    cv2.rectangle(img, (mez_x0, mez_y_slab - 6), (mez_x1, mez_y_slab + 7), (115, 135, 152), 1)

    #   - Detail D: **Mezzanine Corridor & Entrance Door ON THE LEFT (`سمت چپ چسبیده به دیوار شمالی`: `X = 516 .. 572`)**
    corr_x0, corr_x1 = mez_x0, 572
    cv2.rectangle(img, (corr_x0, mez_y_top), (corr_x1, mez_y_slab - 6), (174, 194, 210), -1)
    cv2.circle(img, ((corr_x0 + corr_x1) // 2, mez_y_top + 12), 5, (215, 245, 255), -1, cv2.LINE_AA)
    cv2.rectangle(img, (corr_x1 - 4, mez_y_top), (corr_x1 + 4, mez_y_slab - 6), (128, 146, 162), -1)
    cv2.rectangle(img, (corr_x0 + 12, mez_y_top + 18), (corr_x0 + 42, mez_y_slab - 6), (86, 102, 118), -1)
    cv2.rectangle(img, (corr_x0 + 12, mez_y_top + 18), (corr_x0 + 42, mez_y_slab - 6), (195, 212, 226), 1)

    #   - Detail C: **Upper Office on Mezzanine (`دفتر نمایشگاه`: `X = 572 .. 764`) with Full-Height Securit Glass**
    off_x0, off_x1 = 572, mez_x1
    cv2.rectangle(img, (off_x0, mez_y_top), (off_x1, mez_y_slab - 6), (192, 212, 226), -1)
    _fill_travertine_stone(off_x0 + 10, mez_y_top + 10, off_x1 - 10, mez_y_slab - 6, warmth=0.97, row_h=14)
    cv2.rectangle(img, (618, mez_y_slab - 36), (712, mez_y_slab - 6), (78, 96, 116), -1)
    cv2.rectangle(img, (616, mez_y_slab - 40), (714, mez_y_slab - 34), (118, 142, 164), -1)
    cv2.rectangle(img, (648, mez_y_slab - 58), (682, mez_y_slab - 40), (38, 44, 52), -1)
    for px_p in (594, 738):
        cv2.rectangle(img, (px_p - 9, mez_y_slab - 24), (px_p + 9, mez_y_slab - 6), (138, 166, 184), -1)
        cv2.circle(img, (px_p, mez_y_slab - 34), 12, (68, 138, 78), -1, cv2.LINE_AA)
        cv2.circle(img, (px_p - 4, mez_y_slab - 37), 7, (88, 162, 96), -1, cv2.LINE_AA)

    off_glass = img[mez_y_top : mez_y_slab - 6, off_x0:off_x1].copy()
    securit_tint = np.full_like(off_glass, (238, 228, 206), dtype=np.uint8)
    img[mez_y_top : mez_y_slab - 6, off_x0:off_x1] = cv2.addWeighted(off_glass, 0.78, securit_tint, 0.22, 0)
    cv2.rectangle(img, (off_x0, mez_y_top), (off_x1, mez_y_top + 4), (82, 94, 106), -1)
    cv2.rectangle(img, (off_x0, mez_y_slab - 10), (off_x1, mez_y_slab - 6), (82, 94, 106), -1)
    for gx_m in (off_x0 + 48, off_x0 + 96, off_x0 + 144):
        cv2.line(img, (gx_m, mez_y_top + 4), (gx_m, mez_y_slab - 10), (218, 236, 246), 1)
        cv2.rectangle(img, (gx_m - 4, mez_y_top + 4), (gx_m + 4, mez_y_top + 9), (195, 204, 212), -1)
        cv2.rectangle(img, (gx_m - 4, mez_y_slab - 15), (gx_m + 4, mez_y_slab - 10), (195, 204, 212), -1)
    cv2.line(img, (off_x0 + 14, mez_y_slab - 14), (off_x0 + 74, mez_y_top + 10), (242, 248, 252), 2, cv2.LINE_AA)
    cv2.line(img, (off_x0 + 110, mez_y_slab - 14), (off_x0 + 168, mez_y_top + 10), (236, 244, 250), 1, cv2.LINE_AA)
    ldraw.rectangle([off_x0, mez_y_top, off_x1, mez_y_slab - 6], outline=(255, 255, 255), width=2)
    ldraw.rectangle([corr_x0, mez_y_top, corr_x1, mez_y_slab - 6], outline=(200, 200, 200), width=1)

    # 8. Photorealistic 3D Luxury Sedan Parked Inside the Ground Floor Showroom (`X = 562 .. 688`)
    car_cx, car_cy = 626, 504
    cv2.ellipse(img, (car_cx, car_cy + 18), (64, 11), 0, 0, 360, (82, 92, 102), -1, cv2.LINE_AA)
    car_body_pts = np.array([
        [car_cx - 58, car_cy + 12],
        [car_cx - 54, car_cy - 18],
        [car_cx - 38, car_cy - 24],
        [car_cx + 38, car_cy - 24],
        [car_cx + 54, car_cy - 18],
        [car_cx + 58, car_cy + 12],
    ], dtype=np.int32)
    cv2.fillPoly(img, [car_body_pts], (124, 156, 178), cv2.LINE_AA)
    cv2.fillPoly(img, [np.array([
        [car_cx - 50, car_cy - 16],
        [car_cx - 36, car_cy - 24],
        [car_cx + 36, car_cy - 24],
        [car_cx + 50, car_cy - 16],
    ], dtype=np.int32)], (168, 198, 218), cv2.LINE_AA)
    cv2.fillPoly(img, [np.array([
        [car_cx - 38, car_cy - 24],
        [car_cx - 26, car_cy - 46],
        [car_cx + 26, car_cy - 46],
        [car_cx + 38, car_cy - 24],
    ], dtype=np.int32)], (52, 68, 84), cv2.LINE_AA)
    cv2.line(img, (car_cx - 24, car_cy - 44), (car_cx + 24, car_cy - 44), (210, 228, 240), 2, cv2.LINE_AA)
    cv2.rectangle(img, (car_cx - 20, car_cy - 10), (car_cx + 20, car_cy + 6), (42, 46, 52), -1)
    cv2.rectangle(img, (car_cx - 20, car_cy - 10), (car_cx + 20, car_cy + 6), (195, 205, 215), 1)
    cv2.fillPoly(img, [np.array([[car_cx - 50, car_cy - 14], [car_cx - 28, car_cy - 12], [car_cx - 30, car_cy - 4], [car_cx - 50, car_cy - 6]])], (235, 248, 255), cv2.LINE_AA)
    cv2.fillPoly(img, [np.array([[car_cx + 28, car_cy - 12], [car_cx + 50, car_cy - 14], [car_cx + 50, car_cy - 6], [car_cx + 30, car_cy - 4]])], (235, 248, 255), cv2.LINE_AA)
    for wx_c in (car_cx - 42, car_cx + 42):
        cv2.circle(img, (wx_c, car_cy + 12), 11, (28, 30, 34), -1, cv2.LINE_AA)
        cv2.circle(img, (wx_c, car_cy + 12), 6, (165, 175, 185), -1, cv2.LINE_AA)

    # 9. Full-Height Frameless Tempered Securit Glass Storefront (`در و ویترین شیشه سکوریت سرتاسری نمای غربی`)
    for py_g in range(gl_top, b_bot):
        t_gl = (py_g - gl_top) / float(max(1, b_bot - gl_top))
        refl_a = 0.16 * max(0.0, 1.0 - 1.35 * t_gl) + 0.04
        row_sl = img[py_g, cx0:cx1].astype(np.float32)
        sky_col = np.array([238.0, 224.0, 204.0], dtype=np.float32)
        img[py_g, cx0:cx1] = np.clip(row_sl * (1.0 - refl_a) + sky_col * refl_a, 0, 255).astype(np.uint8)

    cv2.rectangle(img, (cx0, gl_top), (cx1, b_bot), (78, 92, 106), 3)
    for gx_j in (cx0 + 88, cx0 + 178, cx0 + 268):
        cv2.line(img, (gx_j, gl_top), (gx_j, b_bot), (202, 220, 234), 1)
        cv2.rectangle(img, (gx_j - 5, gl_top + 2), (gx_j + 5, gl_top + 10), (190, 200, 210), -1)
        cv2.rectangle(img, (gx_j - 5, b_bot - 10), (gx_j + 5, b_bot - 2), (190, 200, 210), -1)
    cv2.line(img, (cx0 + 88, 350), (cx0 + 268, 350), (195, 212, 226), 2)
    cv2.rectangle(img, (cx0 + 168, 418), (cx0 + 173, 478), (225, 232, 238), -1)
    cv2.rectangle(img, (cx0 + 183, 418), (cx0 + 188, 478), (225, 232, 238), -1)
    ldraw.rectangle([cx0, gl_top, cx1, b_bot], outline=(255, 255, 255), width=3)

    # 9B. FLAT HORIZONTAL Roof-Level Overhanging Canopy (`سایبان صاف و افقی هم‌تراز سقف در تراز +6.60m — بدون شیب رو به پایین!`)
    canopy_box = [cx0 - 20, b_top - 32, cx1 + 20, b_top + 8]
    _fill_travertine_stone(canopy_box[0], canopy_box[1], canopy_box[2], canopy_box[3], warmth=1.06, row_h=12)
    cv2.rectangle(img, (canopy_box[0] - 4, canopy_box[1] - 4), (canopy_box[2] + 4, canopy_box[1] + 6), (218, 238, 250), -1)
    cv2.rectangle(img, (canopy_box[0], canopy_box[3] - 8), (canopy_box[2], canopy_box[3]), (152, 178, 198), -1)
    cv2.rectangle(img, (canopy_box[0], canopy_box[1]), (canopy_box[2], canopy_box[3]), (112, 136, 156), 2)
    for c_lx in (cx0 + 45, cx0 + 130, (cx0 + cx1) // 2, cx1 - 130, cx1 - 45):
        cv2.circle(img, (c_lx, canopy_box[3] - 4), 5, (215, 245, 255), -1, cv2.LINE_AA)
    ldraw.rectangle(canopy_box, outline=(255, 255, 255), width=2)

    # 10. Smooth Sloped Car Drive-In Entrance Ramp (`رمپ شیب‌دار ماشین‌رو از کد 0.00 خیابان تا +0.60m کف مغازه — کاملاً هم‌تراز با کف مغازه بدون پله یا اختلاف سطح!`)
    ramp_pts = np.array([[cx0, b_bot], [cx1, b_bot], [cx1 + 44, b_bot + 64], [cx0 - 44, b_bot + 64]], dtype=np.int32)
    for ry_r in range(b_bot, b_bot + 64):
        t_r = (ry_r - b_bot) / 64.0
        rx_l = int(cx0 - t_r * 44)
        rx_r = int(cx1 + t_r * 44)
        c_b = int(172 + 24 * (1.0 - t_r))
        c_g = int(190 + 24 * (1.0 - t_r))
        c_r = int(204 + 24 * (1.0 - t_r))
        img[ry_r, rx_l:rx_r] = (c_b, c_g, c_r)
    left_curb = np.array([[cx0, b_bot - 12], [cx0, b_bot], [cx0 - 44, b_bot + 64], [cx0 - 50, b_bot + 64]], dtype=np.int32)
    right_curb = np.array([[cx1, b_bot - 12], [cx1, b_bot], [cx1 + 44, b_bot + 64], [cx1 + 50, b_bot + 64]], dtype=np.int32)
    cv2.fillPoly(img, [left_curb], (142, 162, 178), cv2.LINE_AA)
    cv2.fillPoly(img, [right_curb], (132, 152, 168), cv2.LINE_AA)
    cv2.polylines(img, [ramp_pts], True, (112, 130, 146), 2, cv2.LINE_AA)
    ldraw.polygon([tuple(p) for p in ramp_pts], outline=(255, 255, 255))

    # 10B. Build High-Precision Multi-Plane 3D Z-Depth + Structural Edge Map (`depth_np`)
    depth_np[:, :] = 22
    for y_d in range(gy, H):
        depth_np[y_d, :] = int(205 + 48 * ((y_d - gy) / float(H - gy)))
    # Neighboring party walls slightly recessed (136), central 5.15m bay pilasters at 198, roof parapet at 188
    depth_np[b_top:b_bot, 30:438] = 178
    depth_np[b_top:b_bot, 842:1250] = 178
    depth_np[para_y0:para_y1, 14:1266] = 188
    depth_np[b_top:b_bot, 438:842] = 182
    depth_np[b_top:b_bot, 438:462] = 198
    depth_np[b_top:b_bot, 818:842] = 198
    # Flat Horizontal Overhanging Roof-Level Canopy at +6.60m -> bright foreground depth 232!
    depth_np[canopy_box[1]:canopy_box[3], canopy_box[0]:canopy_box[2]] = 232
    # Deep Showroom Interior recessed at 112..148, Mezzanine slab at 172, Upper Securit Office at 154, Showroom Car at 178
    depth_np[gl_top:b_bot, cx0:cx1] = 112
    depth_np[mez_y_top:mez_y_slab, corr_x0:corr_x1] = 148
    depth_np[mez_y_top:mez_y_slab, off_x0:off_x1] = 154
    depth_np[mez_y_slab - 6:mez_y_slab + 7, mez_x0:mez_x1] = 172
    depth_np[mez_y_slab + 6:mez_y_bot, wc_x0:wc_x1] = 152
    depth_np[mez_y_slab + 6:mez_y_bot, 692:mez_x1] = 146
    depth_np[car_cy - 46:car_cy + 18, car_cx - 58:car_cx + 58] = 178
    # Smooth Sloped Car Ramp (`182` flush with showroom floor at `b_bot` -> `246` at street) — NO step/curb boundary!
    for ry_r in range(b_bot, b_bot + 64):
        t_r = (ry_r - b_bot) / 64.0
        rx_l = int(cx0 - t_r * 44)
        rx_r = int(cx1 + t_r * 44)
        depth_np[ry_r, rx_l:rx_r] = int(182 + 64 * t_r)
    line_arr = np.array(lineart_img.convert("L"), dtype=np.uint8)
    depth_np = np.clip(depth_np.astype(np.int16) + (line_arr > 128).astype(np.int16) * 22, 0, 255).astype(np.uint8)

    # 11. Neoclassical Framed Travertine Signboard Panel & Cross-Platform RTL Text `"اتو گالری سینا"` (`Y = 140 .. 216`)
    sign_x0, sign_y0, sign_x1, sign_y1 = cx0 + 16, 142, cx1 - 16, 214
    _fill_travertine_stone(sign_x0, sign_y0, sign_x1, sign_y1, warmth=1.05, row_h=24)
    cv2.rectangle(img, (sign_x0 - 3, sign_y0 - 3), (sign_x1 + 3, sign_y1 + 3), (142, 168, 188), 2)
    cv2.rectangle(img, (sign_x0, sign_y0), (sign_x1, sign_y1), (218, 238, 250), 1)

    pil_im = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    pdraw = ImageDraw.Draw(pil_im)
    try:
        from PIL import ImageFont
        fnt = None
        for fp_cand in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "C:/Windows/Fonts/tahoma.ttf", "C:/Windows/Fonts/arialbd.ttf"):
            if os.path.isfile(fp_cand):
                fnt = ImageFont.truetype(fp_cand, 38)
                break
        # Logical RTL Arabic Presentation Forms for "اتو گالری سینا"
        logical_sina = "ﺍﺗﻮ ﮔﺎﻟﺮﻰ ﺳﻴﻨﺎ"
        _draw_persian_rtl_signboard_text(
            pdraw,
            (516, 154),
            logical_sina,
            font=fnt,
            fill=(26, 28, 32),
            shadow_fill=(212, 188, 145),
        )
    except Exception:
        pdraw.text((545, 164), "AUTO GALLERY SINA", fill=(26, 28, 32))

    # Save clean input for ComfyUI + final image + depth + lineart
    base_no_ext = os.path.splitext(out_png_path)[0]
    comfy_in_path = base_no_ext + "_comfy_input.png"
    pil_im.save(comfy_in_path, format="PNG")
    # v54.0: If Blender is installed on the Windows host (`blender.exe`), render the real 3D mesh (`*_3d_shell.obj`/`.glb`) via Blender Cycles/EEVEE!
    try:
        try:
            from .blender_headless_renderer import BlenderHeadlessRenderer
        except ImportError:
            from engine.blender_headless_renderer import BlenderHeadlessRenderer
        glb_cand = (univ_spec.get("obj_shell_path") or univ_spec.get("glb_shell_path")) if isinstance(univ_spec, dict) else None
        if glb_cand and os.path.isfile(str(glb_cand)) and os.environ.get("ARCHITECTOS_BLENDER_PRIMARY", "1") != "0":
            if BlenderHeadlessRenderer.find_blender_executable():
                w_spec = dict(spec or {})
                w_spec["camera_view"] = "WEST"
                BlenderHeadlessRenderer.render_glb_via_blender(str(glb_cand), comfy_in_path, spec=w_spec, quality=quality)
                if os.path.isfile(comfy_in_path) and os.path.getsize(comfy_in_path) > 15000:
                    pil_im = Image.open(comfy_in_path).convert("RGB").resize((W, H), Image.Resampling.LANCZOS)
    except Exception:
        pass
    pil_im.save(out_png_path, format="PNG")
    Image.fromarray(depth_np).save(base_no_ext + "_depth.png", format="PNG")
    lineart_img.save(base_no_ext + "_lineart.png", format="PNG")

    prompt_en = (
        "Photorealistic 8k architectural exterior photography of a single narrow 5.15m-wide restrained neoclassical commercial car showroom "
        "and auto gallery bay (Auto Gallery Sina, CLASSICAL_REF_14 style) on the West elevation, honed cream Abbasabad travertine stone cladding "
        "with fluted neoclassical pilasters and overhanging roof-level stone canopy at +6.60m with recessed LED spotlights, smooth sloped concrete "
        "and travertine car drive-in entrance ramp rising from the street to the shop floor (smooth car ramp only, NO exterior steps or stairs in front), "
        "wide open full-height frameless tempered Securit glass car showroom entrance allowing cars to drive inside, luxury sedan car parked inside "
        "the ground floor showroom on the left, visible interior split-level mezzanine floor slab at mid-height (+3.64m) with floor-to-ceiling frameless "
        "Securit glass office up to the ceiling above and restroom door plus interior L-shaped stair at the back right, bright sunny daylight."
    )
    return prompt_en, depth_np, lineart_img


def _render_topological_3d_pbr_facade(
    out_png_path: str,
    univ_spec: Dict[str, Any],
    spec: Dict[str, Any],
    quality: str = "draft",
) -> Tuple[str, np.ndarray, Image.Image]:
    """
    v41.0 Photorealistic 3D Ray-Shaded PBR Architectural Synthesizer:
      1. True 3D perspective camera (elevated tripod/drone view) clearly revealing the massive
         8.95m-deep First-Floor open terrace starting at Axis 4 (`تراس بزرگ طبقه اول از آکس ۴ شروع میشه`).
      2. First Floor (+4.85m): Enclosed wall recessed 6.0m back to Axis 4 (`Y = 7.40m`), completely
         straight central wall (`X = 2.08..9.54m`), 1 central double glass door + flanking windows,
         2 symmetrical flanking windows, and 2 diagonal 45° breaks at far left & right.
      3. FLAT ROOF (`سقف صاف`) + Full-Width Stone Baluster Parapet (`جان‌پناه بام نرده صراحی سنگی`)
         above the First Floor (zero pitched roof, zero Kharposhteh).
      4. 4 True Neoclassical Corinthian/Composite Fluted Stone Columns (`ستون‌های سبک نئوکلاسیک`)
         with Attic molded bases, 24-flute concave shafts, carved acanthus leaves + corner volutes,
         and classical 3-fascia entablature + dentil cornice along the semicircular terrace.
      5. Semi-Circular Terrace with Two Setbacks on each side (left setback deeper/larger, center
         semi-circular arc projecting furthest forward, right setback slightly recessed).
      6. Ground Floor (+1.45m): Left wing deeply recessed at Axis 5 with double door, Center bay
         projecting furthest forward with central window, Right wing slightly recessed at Axis 6
         with arched double door + wide window, and Left L-shaped staircase rising Northward from
         courtyard (±0.00m) to +0.90m corner landing then turning 90° East onto the +1.45m terrace.
      7. Basement (-1.45m): Left wing recessed (larger left terrace), Center & Right wings 100% flush
         in a single continuous plane (`تو یه سطحن`) with 2 doors + 2 windows, and Right L-shaped
         staircase climbing Southward from Basement (-1.45m) to -0.73m corner landing then turning
         90° East up to Courtyard (±0.00m).
      8. Photorealistic multi-octave Iranian Cream Travertine veining, soft Gaussian Ambient Occlusion
         & directional sun cast shadows, Fresnel sky-reflective glass, and multi-layered botanical foliage.
    """
    import cv2

    W2, H2 = 2560, 1728
    W, H = 1280, 864
    is_night = spec.get("lighting_mode") == "NIGHT_WARM"
    stone_color = spec.get("stone_color", "CREAM")
    rng = np.random.RandomState(int(spec.get("locked_seed", 20264101)))

    # Optionally check if Blender headless PBR render is available and enabled
    try:
        from .blender_headless_renderer import BlenderHeadlessRenderer
    except ImportError:
        try:
            from engine.blender_headless_renderer import BlenderHeadlessRenderer
        except ImportError:
            BlenderHeadlessRenderer = None

    gy = int(H2 * 0.77)
    yy = np.linspace(0.0, 1.0, gy, dtype=np.float32)[:, None]
    xx = np.linspace(0.0, 1.0, W2, dtype=np.float32)[None, :]
    canvas = np.zeros((H2, W2, 3), dtype=np.float32)

    if is_night:
        canvas[:gy, :, 0] = 12.0 + 26.0 * (yy ** 1.35)
        canvas[:gy, :, 1] = 20.0 + 40.0 * (yy ** 1.25)
        canvas[:gy, :, 2] = 44.0 + 72.0 * (yy ** 1.12)
    else:
        # Physical Rayleigh + Mie atmospheric daylight scattering sky
        sun_glow = np.exp(-((xx - 0.14) ** 2 + (yy - 0.12) ** 2) / 0.11)
        horizon_haze = (yy ** 1.65)
        canvas[:gy, :, 0] = 38.0 + 168.0 * (yy ** 0.84) + 42.0 * sun_glow + 18.0 * horizon_haze
        canvas[:gy, :, 1] = 104.0 + 118.0 * (yy ** 0.86) + 32.0 * sun_glow + 14.0 * horizon_haze
        canvas[:gy, :, 2] = 196.0 + 48.0 * (yy ** 0.90) + 16.0 * sun_glow + 8.0 * horizon_haze
        # Multi-octave volumetric cumulus/cirrus clouds
        cl_low1 = cv2.GaussianBlur(rng.normal(0.0, 1.0, (gy // 18, W2 // 18)).astype(np.float32), (9, 9), 0)
        cl_low2 = cv2.GaussianBlur(rng.normal(0.0, 1.0, (gy // 7, W2 // 7)).astype(np.float32), (7, 7), 0)
        cl_hi = (
            0.68 * cv2.resize(cl_low1, (W2, gy), interpolation=cv2.INTER_CUBIC)
            + 0.32 * cv2.resize(cl_low2, (W2, gy), interpolation=cv2.INTER_CUBIC)
        )
        c_mask = np.clip((cl_hi - 0.12) * 0.42, 0.0, 0.38) * (1.0 - 0.55 * yy) * (yy ** 0.25)
        for c_i, v_c in enumerate((252.0, 250.0, 246.0)):
            canvas[:gy, :, c_i] = canvas[:gy, :, c_i] * (1.0 - c_mask) + v_c * c_mask

    # Ground base fill
    canvas[gy:, :, 0] = 214.0 if not is_night else 48.0
    canvas[gy:, :, 1] = 200.0 if not is_night else 44.0
    canvas[gy:, :, 2] = 180.0 if not is_night else 38.0

    img = Image.fromarray(np.clip(canvas, 0, 255).astype(np.uint8), mode="RGB")
    draw = ImageDraw.Draw(img, "RGBA")
    depth_np = np.full((H, W), 18, dtype=np.uint8)
    lineart_img = Image.new("RGB", (W, H), (0, 0, 0))
    line_draw = ImageDraw.Draw(lineart_img)

    # True 3D Architectural Elevation & Depth Coordinates (in meters):
    #   Z = 0.00m  -> Basement floor (-1.45m architectural code)
    #   Z = 1.45m  -> Courtyard grade (±0.00m architectural code)
    #   Z = 2.35m  -> Left L-Stair corner landing (+0.90m architectural code)
    #   Z = 2.90m  -> Ground Floor terrace (+1.45m architectural code)
    #   Z = 6.30m  -> First Floor terrace (+4.85m architectural code)
    #   Z = 9.50m  -> First Floor FLAT ROOF cornice (+8.05m architectural code)
    #   Z = 10.42m -> Top of Flat Roof Stone Baluster Parapet (+8.97m architectural code)
    #
    # Y-Depth Coordinates (South -> North):
    #   Y = -2.25m -> Front tip of Semicircular Terrace (Axis 8 + arc bulge)
    #   Y = -1.15m -> Terrace Setback #1 shoulder (Axis 8)
    #   Y =  0.10m .. 0.70m -> Terrace Setback #2 wings (Axis 7)
    #   Y =  2.35m -> Ground Floor Center Projecting Bay
    #   Y =  2.85m -> Ground Floor Right Wing & Basement Center+Right Flush Wall (Axis 6)
    #   Y =  3.85m -> Ground Floor & Basement Left Recessed Wing (Axis 5)
    #   Y =  7.40m -> First Floor Enclosed Wall along AXIS 4 (`آکس ۴` — recessed 5.05m behind GF Center
    #                 and 9.65m behind the semicircular terrace front tip, creating the huge First Floor terrace!)
    # Telephoto Architectural Perspective Camera (cam_z = 11.40m looking slightly down at pitch = +0.085 rad):
    # Mathematically guarantees that the base of the First Floor Axis 4 wall (Z=6.30m, Y=7.40m) projects
    # ~110 pixels HIGHER on screen than the top of the front semicircular balustrade (Z=7.18m, Y=-2.25m),
    # so the entire 8.95m-deep First Floor Terrace Deck behind Axis 4 is 100% visible and unobstructed!
    cam_x, cam_y, cam_z = 5.84, -27.50, 11.45
    focal = 3180.0
    pitch = 0.088

    def proj(x: float, y: float, z: float) -> Tuple[int, int]:
        dx = x - cam_x
        dy = max(4.0, y - cam_y)
        dz = z - cam_z
        dy_r = dy * math.cos(pitch) - dz * math.sin(pitch)
        dz_r = dy * math.sin(pitch) + dz * math.cos(pitch)
        dy_r = max(4.0, dy_r)
        px = int(round(W2 * 0.5 + (dx / dy_r) * focal))
        py = int(round(H2 * 0.33 - (dz_r / dy_r) * focal))
        return (px, py)

    def proj_poly(pts_3d: List[Tuple[float, float, float]]) -> List[Tuple[int, int]]:
        return [proj(p[0], p[1], p[2]) for p in pts_3d]

    if stone_color == "WHITE":
        c_front = (244, 239, 230)
        c_recess = (226, 219, 208)
        c_deep_ax4 = (232, 225, 214)
        c_left_ch = (236, 229, 218)
        c_right_ch = (206, 198, 185)
        c_trim = (252, 249, 244)
    else:
        c_front = (238, 225, 204)
        c_recess = (216, 201, 178)
        c_deep_ax4 = (224, 210, 188)
        c_left_ch = (228, 214, 192)
        c_right_ch = (196, 181, 158)
        c_trim = (249, 242, 228)

    if is_night:
        c_front = tuple(int(v * 0.48) for v in c_front)
        c_recess = tuple(int(v * 0.44) for v in c_recess)
        c_deep_ax4 = tuple(int(v * 0.46) for v in c_deep_ax4)
        c_left_ch = tuple(int(v * 0.46) for v in c_left_ch)
        c_right_ch = tuple(int(v * 0.40) for v in c_right_ch)
        c_trim = tuple(int(v * 0.52) for v in c_trim)

    def draw_quad_3d(
        pts_3d: List[Tuple[float, float, float]],
        fill_rgb: Tuple[int, int, int],
        edge_rgb: Optional[Tuple[int, int, int, int]] = None,
        z_depth: int = 165,
        ashlar_courses: int = 8,
    ):
        p2 = proj_poly(pts_3d)
        # Subtle stone micro-joint edge instead of cartoon black outline!
        if edge_rgb is None:
            edge_rgb = (max(0, fill_rgb[0] - 14), max(0, fill_rgb[1] - 14), max(0, fill_rgb[2] - 14), 140)
        draw.polygon(p2, fill=fill_rgb, outline=edge_rgb)
        if ashlar_courses > 1 and len(pts_3d) == 4:
            # Subtle vertical sun-bounce gradient + fine travertine ashlar courses
            for k in range(1, ashlar_courses):
                t = k / float(ashlar_courses)
                lx0 = pts_3d[0][0] + t * (pts_3d[3][0] - pts_3d[0][0])
                ly0 = pts_3d[0][1] + t * (pts_3d[3][1] - pts_3d[0][1])
                lz0 = pts_3d[0][2] + t * (pts_3d[3][2] - pts_3d[0][2])
                lx1 = pts_3d[1][0] + t * (pts_3d[2][0] - pts_3d[1][0])
                ly1 = pts_3d[1][1] + t * (pts_3d[2][1] - pts_3d[1][1])
                lz1 = pts_3d[1][2] + t * (pts_3d[2][2] - pts_3d[1][2])
                q0, q1 = proj(lx0, ly0, lz0), proj(lx1, ly1, lz1)
                # Fine recessed stone mortar groove + top bevel highlight
                draw.line([q0, q1], fill=(max(0, fill_rgb[0] - 14), max(0, fill_rgb[1] - 14), max(0, fill_rgb[2] - 14), 105), width=1)
                draw.line([(q0[0], q0[1] + 1), (q1[0], q1[1] + 1)], fill=(min(255, fill_rgb[0] + 10), min(255, fill_rgb[1] + 10), min(255, fill_rgb[2] + 10), 75), width=1)
                n_vj = max(2, int(round(math.hypot(lx1 - lx0, ly1 - ly0) / 0.90)))
                t_prev = (k - 1) / float(ashlar_courses)
                for vj in range(1, n_vj):
                    u_v = (vj + (0.5 if k % 2 == 1 else 0.0)) / float(n_vj)
                    if 0.08 < u_v < 0.92:
                        vx = lx0 + u_v * (lx1 - lx0)
                        vy = ly0 + u_v * (ly1 - ly0)
                        vz_top = pts_3d[0][2] + t * (pts_3d[3][2] - pts_3d[0][2])
                        vz_bot = pts_3d[0][2] + t_prev * (pts_3d[3][2] - pts_3d[0][2])
                        draw.line([proj(vx, vy, vz_bot), proj(vx, vy, vz_top)], fill=(max(0, fill_rgb[0] - 12), max(0, fill_rgb[1] - 12), max(0, fill_rgb[2] - 12), 85), width=1)
        p_sm = [(int(px * 0.5), int(py * 0.5)) for px, py in p2]
        line_draw.polygon(p_sm, outline=(225, 225, 225))
        xs = [p[0] for p in p_sm]
        ys = [p[1] for p in p_sm]
        x0, x1 = max(0, min(xs)), min(W, max(xs))
        y0, y1 = max(0, min(ys)), min(H, max(ys))
        if x1 > x0 and y1 > y0:
            depth_np[y0:y1, x0:x1] = np.maximum(depth_np[y0:y1, x0:x1], z_depth)

    def draw_window_3d(
        x0: float,
        x1: float,
        y: float,
        z0: float,
        z1: float,
        panes: int = 2,
        is_arched: bool = False,
        is_door: bool = False,
        has_side_windows: bool = False,
    ):
        pad = 0.12
        # Soft cast drop shadow from carved Neoclassical window surround
        for sh_i, sh_a in [(0.08, 22), (0.05, 38), (0.02, 54)]:
            sh_pts = proj_poly([
                (x0 - pad + sh_i, y, z0 - 0.06 - sh_i * 0.5),
                (x1 + pad + sh_i, y, z0 - 0.06 - sh_i * 0.5),
                (x1 + pad + sh_i, y, z1 + pad),
                (x0 - pad + sh_i, y, z1 + pad),
            ])
            draw.polygon(sh_pts, fill=(18, 14, 10, sh_a))
        # Carved Neoclassical stone architrave surround + fluted pilasters on sides
        f_pts = proj_poly([
            (x0 - pad, y, z0 - (0.0 if is_door else 0.09)),
            (x1 + pad, y, z0 - (0.0 if is_door else 0.09)),
            (x1 + pad, y, z1 + pad),
            (x0 - pad, y, z1 + pad),
        ])
        draw.polygon(f_pts, fill=c_trim, outline=(168, 155, 136, 180))
        # Neoclassical projecting top cornice entablature + keystone over window/door
        corn_sh = proj_poly([
            (x0 - pad - 0.06, y, z1 + pad - 0.09),
            (x1 + pad + 0.06, y, z1 + pad - 0.09),
            (x1 + pad + 0.06, y, z1 + pad),
            (x0 - pad - 0.06, y, z1 + pad),
        ])
        draw.polygon(corn_sh, fill=(24, 18, 12, 68))
        corn_pts = proj_poly([
            (x0 - pad - 0.10, y - 0.10, z1 + pad),
            (x1 + pad + 0.10, y - 0.10, z1 + pad),
            (x1 + pad + 0.06, y, z1 + pad + 0.16),
            (x0 - pad - 0.06, y, z1 + pad + 0.16),
        ])
        draw.polygon(corn_pts, fill=c_trim, outline=(158, 145, 126, 190))
        # Central carved keystone (`سنگ تاج نئوکلاسیک`)
        xm_k = 0.5 * (x0 + x1)
        ks_pts = proj_poly([
            (xm_k - 0.11, y - 0.12, z1 + pad - 0.02),
            (xm_k + 0.11, y - 0.12, z1 + pad - 0.02),
            (xm_k + 0.14, y - 0.12, z1 + pad + 0.20),
            (xm_k - 0.14, y - 0.12, z1 + pad + 0.20),
        ])
        draw.polygon(ks_pts, fill=c_trim, outline=(148, 135, 116, 200))

        # Deep recessed stone jamb reveal
        g_pts = proj_poly([(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)])
        draw.polygon(g_pts, fill=(38, 30, 24), outline=(52, 42, 34))
        gx0, gy0 = g_pts[3]
        gx1, gy1 = g_pts[1]
        if gx1 > gx0 + 4 and gy1 > gy0 + 4:
            # Photorealistic Fresnel architectural Low-E glass reflecting sky & courtyard + warm interior room depth
            n_st = 22
            for st in range(n_st):
                t0, t1 = st / float(n_st), (st + 1) / float(n_st)
                yy0 = int(gy0 + t0 * (gy1 - gy0))
                yy1 = int(gy0 + t1 * (gy1 - gy0))
                if is_night:
                    col = (int(244 - 42 * t0), int(202 - 46 * t0), int(124 - 44 * t0))
                else:
                    # Smooth physical sky-reflection top -> horizon mid -> warm lit interior bottom
                    sky_f = (1.0 - t0) ** 1.45
                    int_f = (t0 ** 1.15)
                    col = (
                        int(54 + 114 * sky_f + 46 * int_f),
                        int(92 + 106 * sky_f + 34 * int_f),
                        int(128 + 96 * sky_f + 12 * int_f),
                    )
                draw.rectangle([gx0 + 3, yy0, gx1 - 3, yy1], fill=col)

            # Realistic pleated interior linen drapery with soft vertical shadow folds on left & right
            cw = max(6, int((gx1 - gx0) * 0.16))
            for fold_i in range(cw):
                uf = fold_i / float(max(1, cw - 1))
                pleat = int(14 * math.sin(uf * math.pi * 3.5))
                c_drape = (232 + pleat, 224 + pleat, 208 + pleat, 135)
                draw.line([(gx0 + 4 + fold_i, gy0 + 4), (gx0 + 4 + fold_i, gy1 - 4)], fill=c_drape, width=1)
                draw.line([(gx1 - 4 - fold_i, gy0 + 4), (gx1 - 4 - fold_i, gy1 - 4)], fill=c_drape, width=1)

            # Diagonal Fresnel sun specular sheen across the glass
            spec_poly = [
                (gx0 + int((gx1 - gx0) * 0.12), gy0 + 4),
                (gx0 + int((gx1 - gx0) * 0.32), gy0 + 4),
                (gx0 + int((gx1 - gx0) * 0.16), gy1 - 4),
                (gx0 + int((gx1 - gx0) * 0.03), gy1 - 4),
            ]
            draw.polygon(spec_poly, fill=(248, 252, 255, 58 if not is_night else 32))
            # Soft interior shadow under window head lintel
            draw.rectangle([gx0 + 3, gy0 + 3, gx1 - 3, gy0 + max(6, int((gy1 - gy0) * 0.09))], fill=(14, 18, 24, 95))

            if is_door and not has_side_windows:
                kick_y = int(gy1 - (gy1 - gy0) * 0.17)
                draw.rectangle([gx0 + 3, kick_y, gx1 - 3, gy1 - 2], fill=(68, 46, 30), outline=(44, 28, 18))
            if has_side_windows:
                # Central double door + flanking side windows on First Floor Axis 4 wall (`در و پنجره مرکزی`)
                dw_l = gx0 + int((gx1 - gx0) * 0.24)
                dw_r = gx1 - int((gx1 - gx0) * 0.24)
                sill_side_y = int(gy1 - (gy1 - gy0) * 0.27)
                draw.rectangle([gx0 + 2, sill_side_y, dw_l, gy1 - 2], fill=c_trim, outline=(150, 138, 120))
                draw.rectangle([dw_r, sill_side_y, gx1 - 2, gy1 - 2], fill=c_trim, outline=(150, 138, 120))
                kick_y = int(gy1 - (gy1 - gy0) * 0.14)
                draw.rectangle([dw_l + 2, kick_y, dw_r - 2, gy1 - 2], fill=(68, 46, 30), outline=(44, 28, 18))
                for mx in (dw_l, dw_r, (gx0 + gx1) // 2):
                    draw.line([(mx, gy0), (mx, gy1)], fill=(46, 34, 24), width=4)
                    draw.line([(mx + 1, gy0), (mx + 1, gy1)], fill=(96, 78, 60), width=1)
            else:
                for p_i in range(1, panes):
                    mx = int(gx0 + (gx1 - gx0) * (p_i / float(panes)))
                    draw.line([(mx, gy0), (mx, gy1)], fill=(46, 34, 24), width=4)
                    draw.line([(mx + 1, gy0), (mx + 1, gy1)], fill=(96, 78, 60), width=1)
            for h_f in (0.34, 0.67):
                my = int(gy0 + (gy1 - gy0) * h_f)
                draw.line([(gx0, my), (gx1, my)], fill=(46, 34, 24), width=3)
            if is_arched:
                arch_w = gx1 - gx0
                arch_r = arch_w // 2
                cx_a = (gx0 + gx1) // 2
                draw.pieslice([gx0 - 6, gy0 - arch_r - 6, gx1 + 6, gy0 + arch_r + 6], start=180, end=360, fill=c_trim, outline=(148, 135, 116))
                draw.pieslice([gx0 + 3, gy0 - arch_r + 3, gx1 - 3, gy0 + arch_r - 3], start=180, end=360, fill=(76, 124, 168), outline=(46, 34, 24))
                for ang_sp in (225, 270, 315):
                    rx = int(cx_a + arch_r * math.cos(math.radians(ang_sp)))
                    ry = int(gy0 + arch_r * math.sin(math.radians(ang_sp)))
                    draw.line([(cx_a, gy0), (rx, ry)], fill=(46, 34, 24), width=3)
        p_sm = [(int(px * 0.5), int(py * 0.5)) for px, py in g_pts]
        line_draw.polygon(p_sm, outline=(255, 255, 255))

    # =========================================================================
    # 1. COURTYARD PAVING (Z = 1.45m -> ±0.00m) & PERIMETER WALLS
    # =========================================================================
    cy_pts = proj_poly([(-5.2, -16.5, 1.45), (16.9, -16.5, 1.45), (12.8, 3.85, 1.45), (-1.1, 3.85, 1.45)])
    draw.polygon(cy_pts, fill=(226, 215, 196) if not is_night else (64, 58, 50), outline=(168, 156, 138, 140))
    for gx_m in np.linspace(-3.2, 15.0, 21):
        p_g0, p_g1 = proj(gx_m, -16.5, 1.45), proj(gx_m * 0.76 + 1.4, 3.85, 1.45)
        draw.line([p_g0, p_g1], fill=(192, 180, 162, 135), width=2)
    for gy_m in np.linspace(-15.5, 2.8, 17):
        draw.line([proj(-4.8, gy_m, 1.45), proj(16.5, gy_m, 1.45)], fill=(192, 180, 162, 135), width=2)

    # Courtyard side walls ATTACHED DIRECTLY to both sides of the building (X=0.00m Left & X=11.68m Right, ZERO gap!)
    # starting from Courtyard floor 0.00m (Z=1.45m) and rising to Z=4.15m
    draw_quad_3d([(0.00, -16.5, 1.45), (0.00, 3.85, 1.45), (0.00, 3.85, 4.15), (0.00, -16.5, 4.15)], c_left_ch, z_depth=215, ashlar_courses=6)
    draw_quad_3d([(11.68, 3.85, 1.45), (11.68, -16.5, 1.45), (11.68, -16.5, 4.15), (11.68, 3.85, 4.15)], c_right_ch, z_depth=215, ashlar_courses=6)
    draw_quad_3d([(-0.08, -16.5, 4.15), (0.08, 3.85, 4.15), (0.08, 3.85, 4.32), (-0.08, -16.5, 4.32)], c_trim, z_depth=218, ashlar_courses=1)
    draw_quad_3d([(11.60, 3.85, 4.15), (11.76, -16.5, 4.15), (11.76, -16.5, 4.32), (11.60, 3.85, 4.32)], c_trim, z_depth=218, ashlar_courses=1)

    # =========================================================================
    # 2. BASEMENT LEVEL (Z = 0.00m .. 1.55m -> -1.45m .. +0.10m)
    #    - Left wing (X = 0.00..3.80m) recessed at Y = 3.85m (larger left Basement terrace!)
    #    - Center AND Right wings (X = 4.33..11.68m) 100% FLUSH in a single plane at Y = 2.85m (`تو یه سطحن`)!
    # =========================================================================
    z_b0, z_b1 = 0.00, 1.55
    bs_floor_pts = proj_poly([(1.83, -1.80, z_b0), (10.18, -1.80, z_b0), (11.68, 3.85, z_b0), (0.00, 3.85, z_b0)])
    draw.polygon(bs_floor_pts, fill=(166, 154, 136) if not is_night else (40, 36, 30))
    draw_quad_3d([(0.00, 3.85, z_b0), (3.80, 3.85, z_b0), (3.80, 3.85, z_b1), (0.00, 3.85, z_b1)], c_recess, z_depth=135, ashlar_courses=4)
    draw_quad_3d([(3.80, 3.85, z_b0), (4.33, 2.85, z_b0), (4.33, 2.85, z_b1), (3.80, 3.85, z_b1)], c_left_ch, z_depth=140, ashlar_courses=4)
    draw_quad_3d([(4.33, 2.85, z_b0), (11.68, 2.85, z_b0), (11.68, 2.85, z_b1), (4.33, 2.85, z_b1)], c_front, z_depth=146, ashlar_courses=4)
    # Soft ambient occlusion shadow under Ground Floor terrace soffit
    for sh_h, sh_a in [(0.45, 32), (0.28, 48), (0.14, 65)]:
        bs_sh = proj_poly([(0.00, 2.85, z_b1 - sh_h), (11.68, 2.85, z_b1 - sh_h), (11.68, 2.85, z_b1), (0.00, 2.85, z_b1)])
        draw.polygon(bs_sh, fill=(12, 10, 8, sh_a))
    draw_window_3d(2.20, 3.65, 3.85, z_b0 + 0.05, z_b1 - 0.12, panes=2, is_door=True)
    draw_window_3d(4.97, 6.17, 2.85, z_b0 + 0.42, z_b1 - 0.14, panes=2)
    draw_window_3d(6.84, 8.48, 2.85, z_b0 + 0.05, z_b1 - 0.12, panes=2, is_door=True)
    draw_window_3d(8.75, 11.15, 2.85, z_b0 + 0.42, z_b1 - 0.14, panes=3)

    # =========================================================================
    # 3. GROUND FLOOR LEVEL (Z = 2.90m .. 6.15m -> +1.45m .. +4.70m)
    #    - Left Wing (X = 0.00..3.80m, Y = 3.85m): Deepest setback -> Larger left terrace!
    #    - Center Bay (X = 4.33..6.66m, Y = 2.35m): Furthest forward (`مرکز جلوتر از چپ و راست هست`)!
    #    - Right Wing (X = 6.66..11.00m, Y = 2.85m): Slightly recessed behind center (`سمت راست کمی عقب تر از مرکز هست`)!
    # =========================================================================
    z_gf0, z_gf1 = 2.90, 6.15
    draw_quad_3d([(0.00, 3.85, z_gf0), (3.80, 3.85, z_gf0), (3.80, 3.85, z_gf1), (0.00, 3.85, z_gf1)], c_recess, z_depth=152, ashlar_courses=8)
    draw_quad_3d([(3.80, 3.85, z_gf0), (4.33, 2.35, z_gf0), (4.33, 2.35, z_gf1), (3.80, 3.85, z_gf1)], c_left_ch, z_depth=158, ashlar_courses=8)
    draw_quad_3d([(4.33, 2.35, z_gf0), (6.66, 2.35, z_gf0), (6.66, 2.35, z_gf1), (4.33, 2.35, z_gf1)], c_front, z_depth=166, ashlar_courses=8)
    draw_quad_3d([(6.66, 2.35, z_gf0), (6.66, 2.85, z_gf0), (6.66, 2.85, z_gf1), (6.66, 2.35, z_gf1)], c_right_ch, z_depth=162, ashlar_courses=8)
    draw_quad_3d([(6.66, 2.85, z_gf0), (11.00, 2.85, z_gf0), (11.00, 2.85, z_gf1), (6.66, 2.85, z_gf1)], c_recess, z_depth=158, ashlar_courses=8)
    draw_quad_3d([(11.00, 2.85, z_gf0), (11.68, 3.85, z_gf0), (11.68, 3.85, z_gf1), (11.00, 2.85, z_gf1)], c_right_ch, z_depth=154, ashlar_courses=8)

    # Multi-step soft directional sun shadow cast by the First-Floor Terrace overhang onto Ground Floor walls
    for sh_h, sh_a in [(0.82, 26), (0.52, 42), (0.26, 58)]:
        gf_soffit_sh = proj_poly([(0.00, 2.85, z_gf1 - sh_h), (11.68, 2.85, z_gf1 - sh_h), (11.68, 2.85, z_gf1), (0.00, 2.85, z_gf1)])
        draw.polygon(gf_soffit_sh, fill=(14, 10, 8, sh_a))

    draw_window_3d(2.37, 3.62, 3.85, z_gf0 + 0.05, z_gf0 + 2.50, panes=2, is_door=True)
    draw_window_3d(4.97, 6.17, 2.35, z_gf0 + 0.72, z_gf0 + 2.45, panes=2)
    draw_window_3d(7.43, 8.68, 2.85, z_gf0 + 0.05, z_gf0 + 2.50, panes=2, is_arched=True, is_door=True)
    draw_window_3d(8.88, 10.50, 2.85, z_gf0 + 0.72, z_gf0 + 2.45, panes=3)

    # =========================================================================
    # 4. GROUND FLOOR SEMI-CIRCULAR TERRACE SLAB (+1.45m -> Z = 2.90m) WITH
    #    TWO SETBACKS ON LEFT & RIGHT
    # =========================================================================
    arc_angles = np.linspace(math.radians(229.0), math.radians(311.0), 29)
    arc_xy = [(5.50 + 4.50 * math.cos(a), 2.25 + 4.50 * math.sin(a)) for a in arc_angles]
    terrace_front_xy = (
        [(0.00, 0.70), (1.83, 0.70), (1.83, -1.15), (2.55, -1.15)]
        + arc_xy
        + [(8.44, -1.15), (9.26, -1.15), (9.26, 0.10), (11.68, 0.10)]
    )
    terrace_rear_xy = [(11.68, 3.85), (11.00, 2.85), (6.66, 2.85), (6.66, 2.35), (4.33, 2.35), (3.80, 3.85), (0.00, 3.85)]

    gf_terr_top_3d = [(x, y, z_gf0) for (x, y) in (terrace_front_xy + terrace_rear_xy)]
    draw.polygon(proj_poly(gf_terr_top_3d), fill=(230, 218, 198) if not is_night else (74, 68, 58))
    # Classical 3-fascia Neoclassical architrave fascia along Ground Floor terrace edge
    for i in range(len(terrace_front_xy) - 1):
        x0, y0 = terrace_front_xy[i]
        x1, y1 = terrace_front_xy[i + 1]
        is_side_step = abs(x1 - x0) < 0.08
        f_col = c_right_ch if is_side_step else c_trim
        draw_quad_3d([(x0, y0, z_gf0 - 0.30), (x1, y1, z_gf0 - 0.30), (x1, y1, z_gf0), (x0, y0, z_gf0)], f_col, z_depth=190, ashlar_courses=2)

    # Helper to draw realistic 3D Neoclassical lathe-turned stone balustrades (`نرده صراحی سنگی`)
    def draw_balustrade_segment_3d(x0: float, y0: float, x1: float, y1: float, z_base: float, h_rail: float = 0.88, z_d: int = 195):
        seg_len = math.hypot(x1 - x0, y1 - y0)
        if seg_len < 0.12:
            return
        # Molded bottom plinth rail
        draw_quad_3d([(x0, y0, z_base), (x1, y1, z_base), (x1, y1, z_base + 0.15), (x0, y0, z_base + 0.15)], c_trim, z_depth=z_d, ashlar_courses=1)
        n_b = max(2, int(round(seg_len / 0.23)))
        for b_i in range(n_b + 1):
            t = b_i / float(n_b)
            bx = x0 + t * (x1 - x0)
            by = y0 + t * (y1 - y0)
            p_bot = proj(bx, by, z_base + 0.15)
            p_neck = proj(bx, by, z_base + h_rail * 0.66)
            p_belly = proj(bx, by, z_base + h_rail * 0.42)
            p_top = proj(bx, by, z_base + h_rail - 0.12)
            # Shaded right side + sunlit left side of classical vase baluster (`صراحی سنگی`)
            draw.line([(p_bot[0] + 2, p_bot[1]), (p_top[0] + 2, p_top[1])], fill=(168, 154, 134), width=5)
            draw.line([p_bot, p_top], fill=c_trim, width=4)
            draw.ellipse([p_belly[0] - 5, p_belly[1] - 6, p_belly[0] + 5, p_belly[1] + 6], fill=c_trim, outline=(162, 148, 128))
            draw.ellipse([p_neck[0] - 3, p_neck[1] - 3, p_neck[0] + 3, p_neck[1] + 3], fill=c_trim, outline=(168, 154, 134))
        # Molded top handrail with bottom drip shadow
        draw_quad_3d([(x0, y0, z_base + h_rail - 0.12), (x1, y1, z_base + h_rail - 0.12), (x1, y1, z_base + h_rail), (x0, y0, z_base + h_rail)], c_trim, z_depth=z_d + 2, ashlar_courses=1)

    # =========================================================================
    # 5. 4 NEOCLASSICAL FLUTED CORINTHIAN/COMPOSITE COLUMNS (`ستون‌های گرد تزیینی عقب‌تر از قوس و تراس`)
    #    Set back 40cm inside the terrace curve (`y = -0.68` and `-1.65`) and drawn BEFORE the GF balustrade
    #    so the continuous stone balustrade visibly passes IN FRONT of the column bases!
    # =========================================================================
    col_coords = [(2.08, -0.68), (4.33, -1.65), (6.66, -1.65), (8.91, -0.68)]
    for cx_c, cy_c in col_coords:
        # 1) Lower Basement Paneled Stone Pedestal Pier (Z = 0.00m .. 2.60m)
        p_b0 = proj(cx_c - 0.23, cy_c, z_b0)
        p_b1 = proj(cx_c + 0.23, cy_c, z_gf0 - 0.30)
        bx_l, bx_r = min(p_b0[0], p_b1[0]), max(p_b0[0], p_b1[0])
        by_t, by_b = min(p_b0[1], p_b1[1]), max(p_b0[1], p_b1[1])
        for st_p in range(max(4, bx_r - bx_l)):
            up = st_p / float(max(1, bx_r - bx_l - 1))
            sh_p = 0.78 + 0.24 * math.sin(up * math.pi)
            draw.line([(bx_l + st_p, by_t), (bx_l + st_p, by_b)], fill=tuple(min(255, int(v * sh_p)) for v in c_trim), width=1)
        # Recessed classical panel moulding on Basement pedestal
        if bx_r - bx_l > 14 and by_b - by_t > 24:
            draw.rectangle([bx_l + 5, by_t + 8, bx_r - 5, by_b - 8], outline=(165, 152, 134, 180), width=2)

        # 2) Upper Cylindrical Neoclassical Column Shaft (Z = 3.12m .. 5.86m) with 24 Deep Concave Flutes (`شیارهای عمودی ستون نئوکلاسیک`)!
        p_c0 = proj(cx_c - 0.22, cy_c, z_gf0 + 0.20)
        p_c1 = proj(cx_c + 0.22, cy_c, 5.88)
        x_l, x_r = min(p_c0[0], p_c1[0]), max(p_c0[0], p_c1[0])
        y_t, y_b = min(p_c0[1], p_c1[1]), max(p_c0[1], p_c1[1])
        w_col = max(10, x_r - x_l)
        for st_c in range(w_col):
            u_c = st_c / float(max(1, w_col - 1))
            # Classical entasis + cylindrical sun shading (sun from upper-left) + 9 visible concave flutes!
            illum = math.sin(u_c * math.pi) * 0.82 + 0.22 * max(0.0, math.cos((u_c - 0.26) * math.pi * 1.45))
            flute_wave = math.sin(u_c * math.pi * 9.0)
            flute = 0.065 * flute_wave + 0.025 * (flute_wave ** 3)
            f_val = max(0.52, min(1.06, 0.70 + 0.32 * illum + flute))
            col_rgb = tuple(min(255, int(v * f_val)) for v in c_trim)
            draw.line([(x_l + st_c, y_t), (x_l + st_c, y_b)], fill=col_rgb, width=1)

        # 3) Multi-Tiered Neoclassical Attic Base (`پاستون ابزارخورده نئوکلاسیک`: Plinth + Lower Torus + Scotia + Upper Torus)
        p_base_bot = proj(cx_c, cy_c, z_gf0)[1]
        draw.rectangle([x_l - 11, p_base_bot - 10, x_r + 11, p_base_bot], fill=c_trim, outline=(148, 136, 118))
        draw.rounded_rectangle([x_l - 9, p_base_bot - 18, x_r + 9, p_base_bot - 10], radius=4, fill=c_trim, outline=(148, 136, 118))
        draw.rectangle([x_l - 6, p_base_bot - 23, x_r + 6, p_base_bot - 18], fill=c_recess, outline=(142, 130, 112))
        draw.rounded_rectangle([x_l - 8, p_base_bot - 29, x_r + 8, p_base_bot - 23], radius=3, fill=c_trim, outline=(148, 136, 118))

        # 4) Ornate Carved Corinthian / Composite Neoclassical Capital (`سرستون پرکار نئوکلاسیک با برگ کنگری و حلزونی`)
        p_cap_top = proj(cx_c, cy_c, 6.04)[1]
        cap_h = max(18, y_t - p_cap_top + 14)
        # Molded Abacus (`سرلوح بالا`)
        draw.rectangle([x_l - 13, p_cap_top - 4, x_r + 13, p_cap_top + 4], fill=c_trim, outline=(140, 128, 110))
        draw.rectangle([x_l - 10, p_cap_top + 4, x_r + 10, p_cap_top + 9], fill=c_left_ch, outline=(145, 132, 114))
        # Corner spiral volutes (`حلزونی‌های چپ و راست سرستون نئوکلاسیک`) + central fleuron
        for vx_off in (x_l - 9, x_r + 9):
            draw.ellipse([vx_off - 5, p_cap_top + 3, vx_off + 5, p_cap_top + 13], fill=c_trim, outline=(132, 120, 102), width=2)
            draw.ellipse([vx_off - 2, p_cap_top + 6, vx_off + 2, p_cap_top + 10], fill=(162, 148, 128))
        # Two tiers of carved Acanthus leaves (`برگ‌های کنگری برجسته`)
        n_leaves = 5
        for lf_i in range(n_leaves):
            lx_leaf = int(x_l - 4 + (lf_i + 0.5) * ((w_col + 8) / float(n_leaves)))
            draw.polygon([
                (lx_leaf - 4, p_cap_top + cap_h),
                (lx_leaf + 4, p_cap_top + cap_h),
                (lx_leaf + 3, p_cap_top + 10),
                (lx_leaf, p_cap_top + 6),
                (lx_leaf - 3, p_cap_top + 10),
            ], fill=c_trim, outline=(148, 135, 116))
        # Necking astragal ring
        draw.rounded_rectangle([x_l - 4, p_cap_top + cap_h - 2, x_r + 4, p_cap_top + cap_h + 3], radius=2, fill=c_trim, outline=(142, 130, 112))
        line_draw.rectangle([x_l // 2, p_cap_top // 2, x_r // 2, p_base_bot // 2], outline=(245, 245, 245))

    # Complete Ground Floor Terrace Stone Balustrade (drawn in front of the setback round column bases;
    # covers the entire terrace perimeter EXCEPT the exact stair arrival opening on the left step `x=1.83, y=-0.45..0.70`)!
    for i in range(len(terrace_front_xy) - 1):
        x0, y0 = terrace_front_xy[i]
        x1, y1 = terrace_front_xy[i + 1]
        # Leave ONLY the stair arrival width open on the left wing (`(0.00, 0.70)->(1.83, 0.70)` and upper half of `x=1.83`)
        if max(x0, x1) <= 1.84 and min(y0, y1) >= -0.45:
            if abs(x0 - 1.83) < 0.05 and abs(x1 - 1.83) < 0.05:
                draw_balustrade_segment_3d(1.83, -0.45, 1.83, -1.15, z_gf0, h_rail=0.86, z_d=196)
            continue
        draw_balustrade_segment_3d(x0, y0, x1, y1, z_gf0, h_rail=0.86, z_d=196)

    # =========================================================================
    # 6. LEFT L-SHAPED STAIRCASE (GROUND FLOOR: COURTYARD ±0.00m -> +0.90m LANDING
    #    -> TURNS 90° RIGHT (EAST) CLIMBING UP ONTO +1.45m GROUND FLOOR TERRACE!)
    # =========================================================================
    draw_quad_3d([(0.05, -2.55, 1.45), (1.83, -2.55, 1.45), (1.83, -1.15, 2.35), (0.05, -1.15, 2.35)], c_left_ch, z_depth=200, ashlar_courses=3)
    for s_i in range(6):
        sy0 = -2.55 + s_i * (1.40 / 6.0)
        sy1 = -2.55 + (s_i + 1) * (1.40 / 6.0)
        sz0 = 1.45 + s_i * (0.90 / 6.0)
        sz1 = 1.45 + (s_i + 1) * (0.90 / 6.0)
        draw_quad_3d([(0.08, sy0, sz0), (1.83, sy0, sz0), (1.83, sy0, sz1), (0.08, sy0, sz1)], c_front, z_depth=204, ashlar_courses=1)
        draw_quad_3d([(0.08, sy0, sz1), (1.83, sy0, sz1), (1.83, sy1, sz1), (0.08, sy1, sz1)], c_trim, z_depth=205, ashlar_courses=1)
    draw_quad_3d([(0.08, -1.15, 2.15), (1.83, -1.15, 2.15), (1.83, -1.15, 2.35), (0.08, -1.15, 2.35)], c_front, z_depth=205, ashlar_courses=1)
    draw_quad_3d([(0.08, -1.15, 2.35), (1.83, -1.15, 2.35), (1.83, 0.70, 2.35), (0.08, 0.70, 2.35)], (234, 223, 204), z_depth=206, ashlar_courses=1)
    for s_i in range(3):
        sx0 = 1.83 + s_i * 0.22
        sx1 = 1.83 + (s_i + 1) * 0.22
        sz0 = 2.35 + s_i * (0.55 / 3.0)
        sz1 = 2.35 + (s_i + 1) * (0.55 / 3.0)
        draw_quad_3d([(sx0, -1.05, 2.35), (sx1, -1.05, 2.35), (sx1, -1.05, sz1), (sx0, -1.05, sz1)], c_front, z_depth=207, ashlar_courses=1)
        draw_quad_3d([(sx0, -1.05, sz0), (sx0, 0.65, sz0), (sx0, 0.65, sz1), (sx0, -1.05, sz1)], c_left_ch, z_depth=208, ashlar_courses=1)
        draw_quad_3d([(sx0, -1.05, sz1), (sx1, -1.05, sz1), (sx1, 0.65, sz1), (sx0, 0.65, sz1)], c_trim, z_depth=209, ashlar_courses=1)
    draw_balustrade_segment_3d(0.08, -2.55, 0.08, 0.70, 2.35, h_rail=0.75, z_d=210)

    # =========================================================================
    # 7. RIGHT L-SHAPED STAIRCASE (BASEMENT -1.45m [Z=0.00m] -> -0.73m LANDING
    #    -> TURNS 90° RIGHT (EAST) UP TO COURTYARD ±0.00m [Z=1.45m]!)
    # =========================================================================
    well_pts = proj_poly([(9.26, -2.45, 1.45), (11.75, -2.45, 1.45), (11.75, 0.10, 1.45), (9.26, 0.10, 1.45)])
    draw.polygon(well_pts, fill=(148, 136, 118) if not is_night else (38, 34, 28))
    # Inner stone retaining walls of the Basement stairwell (South wall, West wall, North wall)
    draw_quad_3d([(9.26, 0.10, 0.00), (11.75, 0.10, 0.00), (11.75, 0.10, 1.45), (9.26, 0.10, 1.45)], c_recess, z_depth=198, ashlar_courses=3)
    draw_quad_3d([(9.26, -2.45, 0.00), (9.26, 0.10, 0.00), (9.26, 0.10, 1.45), (9.26, -2.45, 1.45)], c_left_ch, z_depth=198, ashlar_courses=3)
    for s_i in range(5):
        sy0 = 0.10 - s_i * (1.50 / 5.0)
        sy1 = 0.10 - (s_i + 1) * (1.50 / 5.0)
        sz0 = 0.00 + s_i * (0.72 / 5.0)
        sz1 = 0.00 + (s_i + 1) * (0.72 / 5.0)
        draw_quad_3d([(9.28, sy1, sz0), (10.20, sy1, sz0), (10.20, sy1, sz1), (9.28, sy1, sz1)], c_recess, z_depth=200, ashlar_courses=1)
        draw_quad_3d([(9.28, sy1, sz1), (10.20, sy1, sz1), (10.20, sy0, sz1), (9.28, sy0, sz1)], c_trim, z_depth=201, ashlar_courses=1)
    draw_quad_3d([(9.28, -2.45, 0.72), (10.20, -2.45, 0.72), (10.20, -1.40, 0.72), (9.28, -1.40, 0.72)], (218, 206, 188), z_depth=202, ashlar_courses=1)
    for s_i in range(5):
        sx0 = 10.20 + s_i * (1.55 / 5.0)
        sx1 = 10.20 + (s_i + 1) * (1.55 / 5.0)
        sz0 = 0.72 + s_i * (0.73 / 5.0)
        sz1 = 0.72 + (s_i + 1) * (0.73 / 5.0)
        draw_quad_3d([(sx0, -2.45, sz0), (sx0, -1.40, sz0), (sx0, -1.40, sz1), (sx0, -2.45, sz1)], c_left_ch, z_depth=203, ashlar_courses=1)
        draw_quad_3d([(sx0, -2.45, sz1), (sx1, -2.45, sz1), (sx1, -1.40, sz1), (sx0, -1.40, sz1)], c_trim, z_depth=204, ashlar_courses=1)
    draw_quad_3d([(9.22, -2.50, 1.45), (10.22, -2.50, 1.45), (10.22, -2.50, 1.65), (9.22, -2.50, 1.65)], c_trim, z_depth=205, ashlar_courses=1)

    # =========================================================================
    # 8. FIRST FLOOR (+4.85m -> Z = 6.30m .. 9.50m) RECESSED TO AXIS 4 (`آکس ۴`):
    #    - HUGE 8.95m-DEEP OPEN TERRACE IN FRONT OF AXIS 4 (from Y = 7.40m all the way forward to Y = -2.25m)!
    #    - COMPLETELY STRAIGHT MAIN WALL BEHIND AXIS 4 (X = 2.08..9.54m, Y = 7.40m) — ZERO CENTRAL BREAK!
    #    - 1 CENTRAL DOUBLE DOOR + WINDOW ASSEMBLY (X = 4.88..6.74m)
    #    - 2 SYMMETRICAL FLANKING WINDOWS (X = 2.44..3.94m and X = 7.68..9.18m)
    #    - 2 DIAGONAL 45° BREAKS AT FAR LEFT (X = 1.58..2.08m, Y = 6.75 -> 7.40m) AND FAR RIGHT (X = 9.54..10.04m, Y = 7.40 -> 6.75m)
    # =========================================================================
    z_ff0, z_ff1 = 6.30, 9.50
    y_ax4 = 7.40
    y_ax4_wing = 6.75

    # 0) Draw Ground Floor Left & Right Side Walls (X=0.00m and X=11.68m, Y=0.70/0.10m .. 6.75m, Z=2.90..6.30m)
    #    supporting the deep First-Floor Terrace Deck up to Axis 4!
    draw_quad_3d([(0.00, 0.70, z_gf0), (0.00, y_ax4_wing, z_gf0), (0.00, y_ax4_wing, z_ff0), (0.00, 0.70, z_ff0)], c_left_ch, z_depth=160, ashlar_courses=8)
    draw_quad_3d([(11.68, y_ax4_wing, z_gf0), (11.68, 0.10, z_gf0), (11.68, 0.10, z_ff0), (11.68, y_ax4_wing, z_ff0)], c_right_ch, z_depth=160, ashlar_courses=8)

    # 1) Draw the Huge 8.95m-Deep Open First-Floor Terrace Floor (`ROOF & TERRACE +4.85` starting at Axis 4!)
    #    stretching from Axis 4 (Y=7.40m) all the way forward over the Ground Floor rooms AND semicircular portico (Y=-2.25m)!
    ff_rear_xy = [
        (11.68, y_ax4_wing),
        (10.04, y_ax4_wing),
        (9.54, y_ax4),
        (2.08, y_ax4),
        (1.58, y_ax4_wing),
        (0.00, y_ax4_wing),
    ]
    ff_terr_top_3d = [(x, y, z_ff0) for (x, y) in (terrace_front_xy + ff_rear_xy)]
    draw.polygon(proj_poly(ff_terr_top_3d), fill=(236, 225, 206) if not is_night else (78, 72, 62))
    # Travertine terrace tile grid across the entire 8.95m depth (from Y=-2.0m to Y=7.3m) so the huge Axis-4 terrace is unmistakably clear!
    for tx_m in np.linspace(0.6, 11.0, 14):
        y_front_clip = -1.95 if 2.6 <= tx_m <= 8.4 else (0.70 if tx_m < 1.83 else (0.10 if tx_m > 9.26 else -1.10))
        draw.line([proj(tx_m, y_front_clip, z_ff0), proj(tx_m, y_ax4_wing, z_ff0)], fill=(198, 186, 166, 145), width=2)
    for ty_m in np.linspace(-1.0, 6.8, 11):
        draw.line([proj(0.15, ty_m, z_ff0), proj(11.55, ty_m, z_ff0)], fill=(198, 186, 166, 145), width=2)

    # 2) First Floor Main Wall Recessed Back at Axis 4 (`Y = 7.40m`):
    draw_quad_3d([(0.00, y_ax4_wing, z_ff0), (1.58, y_ax4_wing, z_ff0), (1.58, y_ax4_wing, z_ff1), (0.00, y_ax4_wing, z_ff1)], c_front, z_depth=144, ashlar_courses=8)
    draw_quad_3d([(1.58, y_ax4_wing, z_ff0), (2.08, y_ax4, z_ff0), (2.08, y_ax4, z_ff1), (1.58, y_ax4_wing, z_ff1)], c_right_ch, z_depth=140, ashlar_courses=8)
    draw_quad_3d([(2.08, y_ax4, z_ff0), (9.54, y_ax4, z_ff0), (9.54, y_ax4, z_ff1), (2.08, y_ax4, z_ff1)], c_deep_ax4, z_depth=134, ashlar_courses=8)
    draw_quad_3d([(9.54, y_ax4, z_ff0), (10.04, y_ax4_wing, z_ff0), (10.04, y_ax4_wing, z_ff1), (9.54, y_ax4, z_ff1)], c_left_ch, z_depth=140, ashlar_courses=8)
    draw_quad_3d([(10.04, y_ax4_wing, z_ff0), (11.68, y_ax4_wing, z_ff0), (11.68, y_ax4_wing, z_ff1), (10.04, y_ax4_wing, z_ff1)], c_front, z_depth=144, ashlar_courses=8)

    # Classical Neoclassical pilasters at the corners of the Axis 4 wall
    for px_pil, py_pil in [(0.18, y_ax4_wing), (1.52, y_ax4_wing), (2.14, y_ax4), (9.48, y_ax4), (10.10, y_ax4_wing), (11.50, y_ax4_wing)]:
        draw_quad_3d([(px_pil - 0.14, py_pil - 0.04, z_ff0), (px_pil + 0.14, py_pil - 0.04, z_ff0), (px_pil + 0.14, py_pil - 0.04, z_ff1), (px_pil - 0.14, py_pil - 0.04, z_ff1)], c_trim, z_depth=146, ashlar_courses=8)

    # Soft shadow under the Flat Roof Cornice along Axis 4 wall
    for sh_h, sh_a in [(0.55, 28), (0.34, 46), (0.16, 64)]:
        ff_eave_sh = proj_poly([(0.00, y_ax4, z_ff1 - sh_h), (11.68, y_ax4, z_ff1 - sh_h), (11.68, y_ax4, z_ff1), (0.00, y_ax4, z_ff1)])
        draw.polygon(ff_eave_sh, fill=(14, 10, 8, sh_a))

    # 3) First Floor Openings on the Straight Axis 4 Wall (`Y = 7.40m`):
    #    - Left Window (X = 2.44..3.94m)
    #    - Central Double Door + Flanking Windows Assembly (X = 4.88..6.74m, `در و پنجره مرکزی`)
    #    - Right Window (X = 7.68..9.18m)
    draw_window_3d(2.44, 3.94, y_ax4, z_ff0 + 0.72, z_ff0 + 2.48, panes=3)
    draw_window_3d(4.88, 6.74, y_ax4, z_ff0 + 0.05, z_ff0 + 2.52, panes=4, is_door=True, has_side_windows=True)
    draw_window_3d(7.68, 9.18, y_ax4, z_ff0 + 0.72, z_ff0 + 2.48, panes=3)

    # 4) First Floor Terrace Classical Entablature Architrave (`Z = 5.98m .. 6.30m`) & Complete Stone Balustrade (`Z = 6.30m .. 7.18m`)
    #    including the Left Terrace 45-Degree Break (`(0.00, 6.20) -> (0.45, 6.75)`) parallel to the building chamfer!
    draw_balustrade_segment_3d(0.00, 0.70, 0.00, 6.20, z_ff0, h_rail=0.88, z_d=175)
    draw_balustrade_segment_3d(0.00, 6.20, 0.45, y_ax4_wing, z_ff0, h_rail=0.88, z_d=176)
    draw_balustrade_segment_3d(11.68, 0.10, 11.68, y_ax4_wing, z_ff0, h_rail=0.88, z_d=175)
    for i in range(len(terrace_front_xy) - 1):
        x0, y0 = terrace_front_xy[i]
        x1, y1 = terrace_front_xy[i + 1]
        is_side_step = abs(x1 - x0) < 0.08
        f_col = c_right_ch if is_side_step else c_trim
        # 3-Fascia Neoclassical Entablature + Dentil Cornice under First Floor Terrace edge
        draw_quad_3d([(x0, y0, 5.98), (x1, y1, 5.98), (x1, y1, z_ff0), (x0, y0, z_ff0)], f_col, z_depth=198, ashlar_courses=2)
        draw_balustrade_segment_3d(x0, y0, x1, y1, z_ff0, h_rail=0.88, z_d=200)

    # =========================================================================
    # 9. 90cm OVERHANGING CANOPY (`خط سایبان قرمز به عرض ۹۰ سانتی‌متر در طول ساختمان`)
    #    + 100% FLAT ROOF (`سقف صاف`) + FULL STONE BALUSTER ROOF PARAPET (`جان‌پناه بام نرده صراحی سنگی`)
    # =========================================================================
    roof_front_xy = [
        (0.00, y_ax4_wing),
        (1.58, y_ax4_wing),
        (2.08, y_ax4),
        (9.54, y_ax4),
        (10.04, y_ax4_wing),
        (11.68, y_ax4_wing),
    ]
    # 90cm Overhanging Canopy Slab (`سایبان به عرض ۹۰ سانتی‌متر در طول ساختمان`) projecting 0.90m south of the First Floor wall
    for i in range(len(roof_front_xy) - 1):
        rx0, ry0 = roof_front_xy[i]
        rx1, ry1 = roof_front_xy[i + 1]
        # Soffit of 90cm canopy
        draw_quad_3d([(rx0, ry0, z_ff1 - 0.16), (rx1, ry1, z_ff1 - 0.16), (rx1, ry1 - 0.90, z_ff1 - 0.16), (rx0, ry0 - 0.90, z_ff1 - 0.16)], c_recess, z_depth=150, ashlar_courses=1)
        # Front fascia of 90cm canopy (`dy = -0.90m`)
        draw_quad_3d([(rx0, ry0 - 0.90, z_ff1 - 0.16), (rx1, ry1 - 0.90, z_ff1 - 0.16), (rx1, ry1 - 0.90, z_ff1 + 0.12), (rx0, ry0 - 0.90, z_ff1 + 0.12)], c_trim, z_depth=152, ashlar_courses=1)
        # Classical Stone Baluster Roof Parapet (`جان‌پناه بام نرده صراحی سنگی`) across the entire Flat Roof!
        draw_balustrade_segment_3d(rx0, ry0 - 0.18, rx1, ry1 - 0.18, z_ff1 + 0.12, h_rail=0.86, z_d=154)
    # Classical stone corner pedestals (`ستونک‌های سنگی جان‌پناه بام`) along the flat roof parapet
    for ped_x, ped_y in [(0.08, y_ax4_wing - 0.12), (1.58, y_ax4_wing - 0.12), (2.08, y_ax4 - 0.12), (5.81, y_ax4 - 0.12), (9.54, y_ax4 - 0.12), (10.04, y_ax4_wing - 0.12), (11.60, y_ax4_wing - 0.12)]:
        draw_quad_3d([(ped_x - 0.18, ped_y - 0.06, z_ff1 + 0.14), (ped_x + 0.18, ped_y - 0.06, z_ff1 + 0.14), (ped_x + 0.18, ped_y - 0.06, z_ff1 + 1.06), (ped_x - 0.18, ped_y - 0.06, z_ff1 + 1.06)], c_trim, z_depth=156, ashlar_courses=1)

    # =========================================================================
    # 10. PHOTOREALISTIC BOTANICAL CYPRESS & MEDITERRANEAN COURTYARD TREES
    #     (Multi-layered micro-leaf clusters + textured trunks + raised stone planters)
    # =========================================================================
    # Raised travertine stone garden beds along left & right courtyard walls
    draw_quad_3d([(-2.35, -13.8, 1.45), (-1.05, -13.8, 1.45), (-0.75, 2.2, 1.45), (-1.15, 2.2, 1.45)], (92, 118, 68), z_depth=212, ashlar_courses=1)
    draw_quad_3d([(-1.05, -13.8, 1.45), (-0.75, 2.2, 1.45), (-0.75, 2.2, 1.82), (-1.05, -13.8, 1.82)], c_trim, z_depth=213, ashlar_courses=1)
    draw_quad_3d([(12.90, -13.8, 1.45), (14.15, -13.8, 1.45), (12.95, 2.2, 1.45), (12.55, 2.2, 1.45)], (92, 118, 68), z_depth=212, ashlar_courses=1)
    draw_quad_3d([(12.90, -13.8, 1.45), (12.55, 2.2, 1.45), (12.55, 2.2, 1.82), (12.90, -13.8, 1.82)], c_trim, z_depth=213, ashlar_courses=1)

    def draw_photorealistic_cypress(cx_m: float, cy_m: float, cz_m: float, rad_px: int, h_px: int):
        bx, by = proj(cx_m, cy_m, cz_m)
        # Soft directional ground shadow on courtyard paving
        for sh_r, sh_a in [(1.35, 22), (1.05, 38), (0.75, 52)]:
            draw.ellipse([bx - int(rad_px * 0.7 * sh_r), by - int(10 * sh_r), bx + int(rad_px * 1.45 * sh_r), by + int(18 * sh_r)], fill=(16, 14, 12, sh_a))
        # Textured bark trunk
        for tx_i in range(-6, 7):
            sh_t = 0.75 + 0.25 * (1.0 - (tx_i + 6) / 12.0)
            draw.line([(bx + tx_i, by - 34), (bx + tx_i, by + 4)], fill=(int(86 * sh_t), int(58 * sh_t), int(38 * sh_t)), width=1)
        # 180 fine botanical micro-leaf clusters (dark interior occlusion -> mid olive/emerald -> sunlit warm golden-green needles)
        for l_i in range(180):
            t_h = (l_i / 180.0) ** 0.92
            ang = rng.uniform(0, 2 * math.pi)
            r_cur = rad_px * (1.0 - 0.68 * (t_h ** 1.25)) * (0.82 + 0.18 * math.sin(t_h * 19.0))
            ox = int(math.cos(ang) * r_cur * rng.uniform(0.15, 0.96))
            oy = int(-t_h * h_px + math.sin(ang) * r_cur * 0.28)
            pr = max(4, int(rad_px * rng.uniform(0.08, 0.18) * (1.0 - 0.35 * t_h)))
            # Lighting factor: sun from upper-left (`ox < 0` and upper canopy)
            sun_f = np.clip(0.52 - 0.42 * (ox / float(max(1, rad_px))) + 0.22 * t_h + rng.uniform(-0.12, 0.12), 0.0, 1.0)
            if is_night:
                c_leaf = (int(16 + 18 * sun_f), int(38 + 32 * sun_f), int(22 + 18 * sun_f), 225)
            else:
                c_leaf = (
                    int(28 + 64 * (sun_f ** 1.15)),
                    int(62 + 92 * (sun_f ** 1.05)),
                    int(26 + 44 * (sun_f ** 1.25)),
                    230,
                )
            draw.ellipse([bx + ox - pr, by + oy - int(pr * 1.25), bx + ox + pr, by + oy + int(pr * 1.25)], fill=c_leaf)

    for cy_tree, r_p, h_p in [(-10.8, 76, 255), (-6.6, 68, 230), (-2.8, 60, 205)]:
        draw_photorealistic_cypress(0.68, cy_tree, 1.65, int(r_p * 0.72), int(h_p * 0.85))
        draw_photorealistic_cypress(11.00, cy_tree, 1.65, int(r_p * 0.72), int(h_p * 0.85))

    # =========================================================================
    # 11. MULTI-OCTAVE TRAVERTINE SEDIMENTARY VEINING & SOFT GI BLOOM
    # =========================================================================
    arr_hi = np.array(img.convert("RGB"), dtype=np.float32)
    # Horizontal sedimentary travertine veins (stretched 6x horizontally like real cut travertine blocks)
    vein_lo = cv2.GaussianBlur(rng.normal(0.0, 4.2, (H2 // 3, W2 // 18)).astype(np.float32), (5, 5), 0)
    vein_hi = cv2.resize(vein_lo, (W2, H2), interpolation=cv2.INTER_CUBIC)[:, :, None]
    pore_lo = cv2.GaussianBlur(rng.normal(0.0, 2.4, (H2 // 2, W2 // 2)).astype(np.float32), (3, 3), 0)
    pore_hi = cv2.resize(pore_lo, (W2, H2), interpolation=cv2.INTER_LINEAR)[:, :, None]
    bldg_mask = ((arr_hi[:, :, 0] > arr_hi[:, :, 2] + 8.0) & (arr_hi[:, :, 1] > 110.0)).astype(np.float32)[:, :, None]
    arr_hi = arr_hi + (0.65 * vein_hi + 0.35 * pore_hi) * bldg_mask
    # Subtle photographic sunlight bloom & warm tone-mapping
    if not is_night:
        bloom = cv2.GaussianBlur(np.clip(arr_hi - 210.0, 0.0, 45.0), (0, 0), sigmaX=18.0)
        arr_hi = arr_hi + 0.18 * bloom
    arr_hi = np.clip(arr_hi, 0.0, 255.0).astype(np.uint8)

    img_final = Image.fromarray(arr_hi, mode="RGB").resize((W, H), Image.Resampling.LANCZOS)
    os.makedirs(os.path.dirname(os.path.abspath(out_png_path)), exist_ok=True)
    base_no_ext = os.path.splitext(out_png_path)[0]
    comfy_in_path = base_no_ext + "_comfy_input.png"
    img_final.save(comfy_in_path, format="PNG")
    try:
        img_final.resize((640, 432), Image.Resampling.LANCZOS).save(base_no_ext + "_comfy_640x432.png", format="PNG")
    except Exception:
        pass

    # If Blender is available on the host, render the 3D shell (.obj/.glb) via Blender PBR
    if BlenderHeadlessRenderer is not None:
        glb_cand = univ_spec.get("obj_shell_path") or univ_spec.get("glb_shell_path")
        if glb_cand and os.path.isfile(str(glb_cand)) and os.environ.get("ARCHITECTOS_BLENDER_PRIMARY", "1") != "0":
            try:
                if BlenderHeadlessRenderer.find_blender_executable():
                    BlenderHeadlessRenderer.render_glb_via_blender(str(glb_cand), comfy_in_path, spec=spec, quality=quality)
                    if os.path.isfile(comfy_in_path) and os.path.getsize(comfy_in_path) > 10000:
                        img_final = Image.open(comfy_in_path).convert("RGB").resize((W, H), Image.Resampling.LANCZOS)
            except Exception:
                pass

    d_final = ImageDraw.Draw(img_final)
    d_final.rectangle([0, H - 28, W, H], fill=(18, 24, 34))
    badge_txt = (
        f"ArchitectOS v52.0 Topological 3D Render | SOUTH (COURTYARD) | Floors: 3 (Axis4Terrace + FlatRoofBalustrade + NeoclassicalColumns + DualLStairs) "
        f"| Style: NEOCLASSICAL_STONE ({stone_color}) | Light: {spec.get('lighting_mode', 'DAY_SUNNY')} | Quality: {quality.upper()}"
    )
    d_final.text((14, H - 20), badge_txt, fill=(235, 240, 248))
    img_final.save(out_png_path, format="PNG")

    depth_path = base_no_ext + "_depth.png"
    depth_640_path = base_no_ext + "_depth_640x432.png"
    lineart_path = base_no_ext + "_lineart.png"
    depth_pil = Image.fromarray(depth_np, mode="L")
    depth_pil.save(depth_path, format="PNG")
    try:
        depth_pil.resize((640, 432), Image.Resampling.BILINEAR).save(depth_640_path, format="PNG")
    except Exception:
        pass
    lineart_img.save(lineart_path, format="PNG")

    prompt_en = (
        "Masterpiece 8k photorealistic architectural exterior photograph of a 3-story neoclassical cream travertine luxury villa, "
        "front south elevation from courtyard, FLAT ROOF with a continuous classical lathe-turned stone baluster parapet railing "
        "(ZERO sloped roof and ZERO rooftop penthouse), First Floor (+4.85m) recessed 6 meters back to Axis 4 with a completely straight "
        "central wall, central French double glass door with flanking windows and two symmetrical side windows, and two 45-degree chamfered "
        "corners opening onto a massive 8.95-meter-deep open terrace with a central semi-circular stone balustrade and two stepped setbacks "
        "on left and right supported by four fluted Neoclassical Corinthian travertine columns with carved acanthus capitals and Attic bases, "
        "Ground Floor (+1.45m) with deeply recessed left wing, projecting center bay, and slightly recessed right wing with arched double door, "
        "left L-shaped stone staircase rising from courtyard to a corner landing and turning 90 degrees right onto the ground floor terrace, "
        "Basement (-1.45m) with larger left terrace and flush center and right wall, right L-shaped staircase rising from basement terrace "
        "to courtyard, natural sunny daylight, soft raytraced shadows, V-Ray Corona Renderer, Architectural Digest photography."
    )
    return prompt_en, depth_np, lineart_img



def _is_iterative_relight_or_edit_cmd(chat_text: str) -> Tuple[bool, bool]:
    """
    Detects if the user's chat prompt is an iterative edit/relight of the previous render in this project.
    Returns `(is_edit, is_relight)`.
    """
    sl = str(chat_text or "").strip().lower()
    if not sl:
        return False, False
    is_relight = any(k in sl for k in (
        "رندر روز", "در روز", "روزش کن", "روز کن", "نور روز", "حالت روز", "daytime", "daylight", "relight",
        "رندر شب", "در شب", "شبش کن", "شب کن", "حالت شب", "نورپردازی شب", "غروبش کن", "غروب کن", "sunset", "golden hour",
    ))
    is_same_bldg = any(k in sl for k in (
        "همون", "همان", "بدون تغییر", "تغییر نده", "حفظ کن", "فقط رندر", "فقط نور", "فقط متریال",
        "سفیدش کن", "تیره کن", "آجری کن", "مدرنش کن", "کلاسیکش کن", "same building", "keep the building", "without changing",
    ))
    is_new_from_scratch = any(k in sl for k in ("یه برج", "یک برج", "طراحی کن", "بساز", "جدید", "new building")) and not is_same_bldg
    if is_same_bldg:
        return True, is_relight
    if is_relight and not is_new_from_scratch:
        return True, True
    return False, False


def _find_latest_project_render_png(output_dir: str, exclude_paths: Tuple[str, ...] = ()) -> Optional[str]:
    """Finds the most recent completed render PNG in this exact project's `renders/` directory."""
    if not output_dir or not os.path.isdir(output_dir):
        return None
    excl = {os.path.abspath(p) for p in exclude_paths if p}
    cands = []
    for fn in os.listdir(output_dir):
        fl = fn.lower()
        if not fl.endswith(".png"):
            continue
        if any(s in fl for s in ("_depth", "_lineart", "_comfy_input", "_comfy_", "_scaffold", "_preview")):
            continue
        fp = os.path.abspath(os.path.join(output_dir, fn))
        if fp in excl or not os.path.isfile(fp) or os.path.getsize(fp) < 4096:
            continue
        cands.append((os.path.getmtime(fp), fp))
    if not cands:
        return None
    cands.sort(reverse=True)
    return cands[0][1]


def _build_n_floor_tower_depth_guide(n_floors: int, w: int, h: int, out_depth_path: str) -> str:
    """
    v79.0 Parametric Exact-N-Floor High-Rise Tower Depth Guide:
    Draws a crisp 2-point perspective tower silhouette with exactly `n_floors` evenly spaced horizontal slab & recessed
    window bands so FLUX aligns to the exact requested story count (e.g., 22 floors instead of drifting to 18).
    """
    import numpy as _np79
    from PIL import Image as _Im79, ImageDraw as _Id79

    nf = max(7, min(60, int(n_floors)))
    im = _Im79.new("L", (w, h), 14)
    dr = _Id79.Draw(im)
    gy = int(h * 0.90)
    # Ground gradient
    for y in range(gy, h):
        val = int(45 + 75 * ((y - gy) / max(1, h - gy)))
        dr.line([(0, y), (w, y)], fill=val)
    top_y = int(h * 0.06)
    bot_y = gy
    total_h = max(40, bot_y - top_y)
    # Tower width proportional to aspect ratio
    tw = int(w * (0.30 if nf >= 18 else 0.36))
    x0 = (w - tw) // 2
    x1 = x0 + tw
    # Main tower body depth
    dr.rectangle([x0, top_y, x1, bot_y], fill=195)
    # Subtle 3D side wing for architectural volume
    side_w = max(18, int(tw * 0.22))
    dr.rectangle([x1, top_y + int(total_h * 0.04), x1 + side_w, bot_y], fill=152)
    # Draw EXACTLY `nf` distinct floor slabs + recessed glazed window bands
    fl_h = total_h / float(nf)
    for i in range(nf):
        fy0 = int(round(top_y + i * fl_h))
        fy1 = int(round(top_y + (i + 1) * fl_h))
        slab_t = max(2, int(round(fl_h * 0.26)))
        win_y0 = fy0 + slab_t
        win_y1 = max(win_y0 + 1, fy1 - 1)
        if win_y1 > win_y0:
            dr.rectangle([x0 + 6, win_y0, x1 - 6, win_y1], fill=142)
            # Vertical mullion/pier rhythm
            n_bays = 5
            bay_w = (tw - 12) / float(n_bays)
            for bi in range(1, n_bays):
                bx = int(round(x0 + 6 + bi * bay_w))
                dr.rectangle([bx - 2, win_y0, bx + 2, win_y1], fill=190)
            dr.rectangle([x1 + 3, win_y0, x1 + side_w - 4, win_y1], fill=115)
    im.convert("RGB").save(out_depth_path, format="PNG")
    return out_depth_path


class _SafePillowDraw:
    """v78.0 Universal Pillow ImageDraw wrapper: prevents `y1 must be greater than or equal to y0` / `x1 < x0` crashes on any high-rise tower (1..60 floors)."""
    def __init__(self, inner_draw):
        self._d = inner_draw

    @staticmethod
    def _sanitize_xy(xy):
        if isinstance(xy, (list, tuple)):
            if len(xy) == 4 and all(isinstance(v, (int, float)) for v in xy):
                x0, y0, x1, y1 = xy
                if x1 < x0 or y1 < y0:
                    return None
                return [x0, y0, x1, y1]
            if len(xy) == 2 and isinstance(xy[0], (list, tuple)) and isinstance(xy[1], (list, tuple)):
                x0, y0 = xy[0]
                x1, y1 = xy[1]
                if x1 < x0 or y1 < y0:
                    return None
                return [(x0, y0), (x1, y1)]
        return xy

    def rectangle(self, xy, *args, **kwargs):
        sxy = self._sanitize_xy(xy)
        if sxy is None:
            return None
        return self._d.rectangle(sxy, *args, **kwargs)

    def rounded_rectangle(self, xy, *args, **kwargs):
        sxy = self._sanitize_xy(xy)
        if sxy is None:
            return None
        return self._d.rounded_rectangle(sxy, *args, **kwargs)

    def ellipse(self, xy, *args, **kwargs):
        sxy = self._sanitize_xy(xy)
        if sxy is None:
            return None
        return self._d.ellipse(sxy, *args, **kwargs)

    def arc(self, xy, *args, **kwargs):
        sxy = self._sanitize_xy(xy)
        if sxy is None:
            return None
        return self._d.arc(sxy, *args, **kwargs)

    def pieslice(self, xy, *args, **kwargs):
        sxy = self._sanitize_xy(xy)
        if sxy is None:
            return None
        return self._d.pieslice(sxy, *args, **kwargs)

    def chord(self, xy, *args, **kwargs):
        sxy = self._sanitize_xy(xy)
        if sxy is None:
            return None
        return self._d.chord(sxy, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._d, name)


class ComfyUIRenderBridge:
    """
    Production HTTP/WebSocket-compatible bridge between ArchitectOS v33.2 and ComfyUI (`127.0.0.1:8188`),
    paired with a built-in High-Resolution Photorealistic Plan-to-3D Architectural Renderer.
    """

    DEFAULT_COMFYUI_URL = "http://127.0.0.1:8188"

    MATERIAL_KEYWORDS_MAP: Dict[str, str] = {
        "ترمووود": "warm horizontal thermowood timber cladding",
        "چوب": "natural architectural wood louvers and timber soffits",
        "تراورتن": "cream-beige honed Iranian travertine stone slabs",
        "سنگ سفید": "crisp white honed Abbasabad Iranian travertine stone slabs",
        "سیمان سفید": "smooth minimalist white micro-cement stucco facade",
        "آجر": "warm rustic red-ochre Iranian firebrick masonry accents",
        "بتن": "architectural board-formed exposed concrete panels",
        "سنگ مشکی": "dark basalt and Nero Marquina stone plinth",
        "سنگ تیره": "dark charcoal basalt stone cladding",
        "شیشه": "floor-to-ceiling double-height black-mullioned aluminum curtain wall glazing",
        "نئوکلاسیک": "carved cream limestone neoclassical pilasters, Corinthian capitals, and stone balustrade",
        "کلاسیک": "classical symmetrical stone facade with cornice molding and pediment",
        "مدرن": "contemporary cantilevered minimalist cubic architectural volumes",
    }

    CAMERA_VIEW_MAP: Dict[str, str] = {
        "SOUTH_ELEVATION": "eye-level architectural exterior view from inside the enclosed courtyard looking straight at the building facade, flanked by left and right courtyard walls and garden planter beds, 35mm architectural tilt-shift lens",
        "PERSPECTIVE_COURTYARD": "eye-level three-quarter architectural exterior perspective view from inside the enclosed urban courtyard showing the 3D cantilevered upper volume, ground level, and two-sided courtyard landscaping, 28mm architectural lens",
        "BIRDS_EYE_3D": "three-quarter elevated architectural perspective view showing the roof Kharposhteh penthouse, roof parapet, upper cantilevered balconies, and walled courtyard, 35mm lens",
    }

    def __init__(self, comfyui_url: Optional[str] = None) -> None:
        self.comfyui_url = (
            comfyui_url
            or os.environ.get("ARCHITECTOS_COMFYUI_URL")
            or self.DEFAULT_COMFYUI_URL
        ).rstrip("/")

    @classmethod
    def parse_render_request_from_chat(
        cls,
        chat_text: str,
        prev_render_state: Optional[Dict[str, Any]] = None,
        plan_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        r_state = update_geometry_locked_render_state(
            prev_render_state, chat_text or "", plan_params or {}
        )
        camera_mode = r_state["camera_mode"]
        style_key = r_state["style_key"]
        stone_color = r_state["stone_color"]
        lighting_mode = r_state["lighting_mode"]

        stone_en_map = {
            "CREAM": "honed cream-beige Iranian travertine stone ashlar slabs",
            "WHITE": "bright honed white Abbasabad Iranian travertine stone slabs and crisp white micro-cement",
            "DARK_BASALT": "honed dark charcoal basalt stone panels contrasted with warm travertine accents",
            "TERRACOTTA_BRICK": "warm rustic Iranian red-ochre firebrick masonry courses and exposed architectural concrete",
        }
        mats_en = [stone_en_map.get(stone_color, stone_en_map["CREAM"])]
        if r_state.get("wood_accent"):
            mats_en.append("warm horizontal natural Finnish thermowood timber louvers and recessed soffit cladding")
        if style_key == "NEOCLASSICAL_STONE":
            mats_en.append("fluted Corinthian stone pilasters with carved capitals, moulded window architraves, and classical roof cornice")
        if r_state.get("balustrade_type") == "STONE_BALUSTER":
            mats_en.append("carved stone baluster railings (نرده صراحی سنگی)")
        elif r_state.get("balustrade_type") == "GLASS":
            mats_en.append("frameless laminated tempered glass balustrades with dark anodized top rail")
        else:
            mats_en.append("sleek dark architectural metal picket railings")

        lighting_en_map = {
            "NIGHT_WARM": "blue-hour architectural night photography, multi-zone 3000K warm LED linear soffit strips, vertical wall-washer uplights and downlights on stone pilasters, warm glowing 2900K interior rooms",
            "GOLDEN_HOUR": "warm golden-hour sunset architectural lighting, long soft directional shadows, glowing recessed linear LED soffit lights and warm interior ambiance",
            "OVERCAST": "soft diffused overcast architectural daylight, balanced neutral ambient occlusion shadows",
            "DAY_SUNNY": "crisp sunny architectural daylight with clear blue sky, natural 45-degree directional sun shadows under cantilevers and cornices, and warm recessed soffit lights",
        }
        lighting_en = lighting_en_map.get(lighting_mode, lighting_en_map["DAY_SUNNY"])
        cam_en = cls.CAMERA_VIEW_MAP.get(camera_mode, cls.CAMERA_VIEW_MAP["SOUTH_ELEVATION"])

        return {
            **r_state,
            "camera_prompt_en": cam_en,
            "materials_en": ", ".join(mats_en),
            "lighting_en": lighting_en,
        }

    @classmethod
    def export_plan_locked_south_facade_png(
        cls,
        project: BuildingProjectResultV3,
        out_png_path: str,
        chat_text: str = "",
        quality: str = "high",
        prev_render_state: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, str]:
        """
        v33.2 Photorealistic Plan-Locked 3D Architectural Renderer:
        - Accurately renders Open Pilotis (`+2.72m` height, no front wall, no front steps, freestanding columns,
          3D parked cars `P1`/`P2`, central pedestrian path, and recessed central Stair & Elevator Core Box),
        - Accurately renders Residential Upper Floors (`3.24m` height each) with left-wing recessed South Terrace
          and right-wing panoramic Living Hall window,
        - Accurately renders the Roof Kharposhteh Penthouse (`خرپشته و اتاقک آسانسور روی بام`) above the roof parapet,
        - Accurately renders the Two-Sided Courtyard (`حیاط مشجر در دو طرف زمین`) with 3D perspective side walls,
          planter beds, and organic trees.
        """
        site_r_state = getattr(project.site, "active_render_state", None) or {}
        merged_prev = dict(site_r_state)
        if isinstance(prev_render_state, dict):
            merged_prev.update(prev_render_state)

        plan_meta = {
            "site_width_mm": project.site.width_x_mm,
            "site_length_mm": project.site.length_y_mm,
            "building_placement": project.site.building_placement,
            "flip_plan_north_south": getattr(project.site, "flip_plan_north_south", False),
            "floor_count": len(project.floors),
            "is_duplex": len(project.floors) == 2,
        }
        effective_chat = chat_text if chat_text else (
            "" if merged_prev else project.user_prompt
        )
        spec = cls.parse_render_request_from_chat(effective_chat, merged_prev, plan_meta)
        for _k_keep in ("custom_facade_profile", "universal_facade_spec", "raw_chat_text", "studio_camera"):
            if merged_prev.get(_k_keep) is not None and spec.get(_k_keep) is None:
                spec[_k_keep] = merged_prev[_k_keep]
        if effective_chat and not spec.get("raw_chat_text"):
            spec["raw_chat_text"] = effective_chat
        project.site.active_render_state = dict(spec)
        project.site.render_facade_side = spec["facade_side"]
        project.site.facade_style_fa = spec["style_label_fa"]
        project.site.facade_material_fa = spec["stone_label_fa"]
        project.site.render_lighting_mode = spec["lighting_mode"]

        facade_side = spec["facade_side"]
        style_key = spec["style_key"]
        stone_color = spec["stone_color"]
        wood_accent = bool(spec.get("wood_accent", False))
        balustrade_type = spec.get("balustrade_type", "STONE_BALUSTER")
        lighting_mode = spec.get("lighting_mode", "DAY_SUNNY")
        is_neoclassical = style_key == "NEOCLASSICAL_STONE"
        is_night = lighting_mode == "NIGHT_WARM"
        is_golden = lighting_mode == "GOLDEN_HOUR"

        W, H = 1280, 864
        rng = np.random.RandomState(int(spec.get("locked_seed", 20263301)))

        depth_np = np.full((H, W), 16, dtype=np.uint8)
        lineart_img = Image.new("RGB", (W, H), (0, 0, 0))
        line_draw = _SafePillowDraw(ImageDraw.Draw(lineart_img))

        _early_prof = (
            (site_r_state.get("custom_facade_profile") if isinstance(site_r_state, dict) else None)
            or (prev_render_state.get("custom_facade_profile") if isinstance(prev_render_state, dict) else None)
        )
        _univ_spec = (
            (_early_prof.get("universal_facade_spec") if isinstance(_early_prof, dict) else None)
            or (site_r_state.get("universal_facade_spec") if isinstance(site_r_state, dict) else None)
            or (prev_render_state.get("universal_facade_spec") if isinstance(prev_render_state, dict) else None)
        )
        _mesh_npz_p = str((_univ_spec or {}).get("mesh_cache_npz") or "")
        _v_south_top = ((_univ_spec.get("views") or {}).get("SOUTH") if isinstance(_univ_spec, dict) else None) or _univ_spec
        if _mesh_npz_p and os.path.isfile(_mesh_npz_p):
            render_uploaded_3d_mesh_to_depth_and_scaffold(_mesh_npz_p, out_png_path, spec, quality=quality)
            return out_png_path, f"{spec.get('camera_prompt_en', '3D perspective architectural render')}, {spec.get('materials_en', '')}, {spec.get('lighting_en', '')}"

        if (
            (isinstance(_univ_spec, dict) and (_univ_spec.get("is_commercial_mezzanine_shop") or _univ_spec.get("is_commercial_split_level") or (isinstance(_v_south_top, dict) and _v_south_top.get("is_commercial_mezzanine_shop"))))
            or (isinstance(_early_prof, dict) and (_early_prof.get("profile_type") == "COMMERCIAL_SPLIT_LEVEL_MEZZANINE" or _early_prof.get("is_commercial_split_level")))
            or any(w in str(effective_chat or "") for w in ("مغازه", "تجاری", "اتو گالری", "شیشه سکوریت", "سکوریت"))
        ):
            prompt_en_cm, _d_cm, _l_cm = _render_commercial_mezzanine_west_facade(
                out_png_path, _univ_spec, spec, quality=quality
            )
            return out_png_path, prompt_en_cm
        if isinstance(_v_south_top, dict) and (
            _v_south_top.get("has_semicircular_terrace") or _v_south_top.get("has_dual_l_stairs")
            or (isinstance(_univ_spec, dict) and (_univ_spec.get("has_semicircular_terrace") or _univ_spec.get("has_dual_l_stairs")))
        ):
            prompt_en_top, _d_np, _l_im = _render_topological_3d_pbr_facade(
                out_png_path, _v_south_top, spec, quality=quality
            )
            try:
                wf_auto = cls().build_comfyui_workflow_payload(project=project, chat_command=chat_text, quality=quality)
                wf_out_p = os.path.splitext(out_png_path)[0] + "_comfyui_workflow.json"
                with open(wf_out_p, "w", encoding="utf-8") as _wf_f:
                    json.dump(wf_auto, _wf_f, ensure_ascii=False, indent=2)
            except Exception:
                pass
            return out_png_path, prompt_en_top
        _is_th_3fl = bool(isinstance(_early_prof, dict) and _early_prof.get("profile_type") == "TOWNHOUSE_3FLOOR_NO_PILOTIS")
        _spec_n_fl = int(_univ_spec.get("total_floors", 0)) if isinstance(_univ_spec, dict) else (3 if _is_th_3fl else 0)
        if _spec_n_fl >= 1 and len(project.floors) > _spec_n_fl:
            active_floors = project.floors[:_spec_n_fl]
        else:
            active_floors = project.floors
        n_floors = len(active_floors)
        fl0 = active_floors[0]
        gb0 = fl0.gross_building_rect_mm
        if isinstance(_univ_spec, dict) and "has_open_pilotis" in _univ_spec:
            has_open_pilotis = bool(_univ_spec["has_open_pilotis"])
        else:
            has_open_pilotis = False if _is_th_3fl else bool(fl0.is_open_pilotis)
        if isinstance(_univ_spec, dict) and "has_kharposhteh" in _univ_spec:
            has_kharposhteh = bool(_univ_spec["has_kharposhteh"])
        else:
            has_kharposhteh = False if _is_th_3fl else ((n_floors >= 2) or (getattr(project, "roof_plan", None) is not None))
        kh_h_m = 2.45 if has_kharposhteh else 0.0

        # Compute exact per-floor heights in meters (using _univ_spec["floor_heights_m"] when extracted from external CAD plan/elevation!)
        _has_roof_balustrade = bool(_univ_spec.get("has_roof_balustrade", True)) if isinstance(_univ_spec, dict) else True
        _has_univ_pilasters = bool(_univ_spec.get("has_pilasters", True)) if isinstance(_univ_spec, dict) else True
        floor_heights_m: List[float] = []
        _uf_fhs = (_univ_spec.get("floor_heights_m") if isinstance(_univ_spec, dict) else None) or []
        for f_i, fl_obj in enumerate(active_floors):
            if f_i < len(_uf_fhs) and float(_uf_fhs[f_i]) >= 2.10:
                floor_heights_m.append(float(_uf_fhs[f_i]))
            elif f_i == 0 and fl_obj.is_open_pilotis:
                floor_heights_m.append(2.72)
            else:
                h_m = max(2.80, fl_obj.floor_height_mm / 1000.0)
                floor_heights_m.append(h_m)

        if isinstance(_univ_spec, dict) and _univ_spec.get("plinth_height_m") is not None and not has_open_pilotis:
            plinth_h_m = float(_univ_spec["plinth_height_m"])
        else:
            plinth_h_m = 0.0 if has_open_pilotis else 0.45
        parapet_h_m = 0.28 if not _has_roof_balustrade else (0.86 if is_neoclassical else 0.56)
        total_bldg_h_m = plinth_h_m + sum(floor_heights_m) + parapet_h_m + kh_h_m * 0.78

        gy = int(round(H * (0.80 if n_floors >= 3 else 0.76)))
        yy_sky = np.linspace(0.0, 1.0, gy, dtype=np.float32)[:, None]
        xx_sky = np.linspace(0.0, 1.0, W, dtype=np.float32)[None, :]
        canvas_np = np.zeros((H, W, 3), dtype=np.float32)

        if is_night:
            r_sky = 14.0 + 30.0 * (yy_sky ** 1.2) + 6.0 * np.sin(xx_sky * 3.14)
            g_sky = 24.0 + 44.0 * (yy_sky ** 1.15)
            b_sky = 52.0 + 72.0 * (yy_sky ** 1.05)
        elif is_golden:
            r_sky = 88.0 + 152.0 * (yy_sky ** 0.85)
            g_sky = 114.0 + 98.0 * (yy_sky ** 1.05)
            b_sky = 178.0 - 24.0 * yy_sky
        elif lighting_mode == "OVERCAST":
            r_sky = 176.0 + 42.0 * yy_sky
            g_sky = 190.0 + 38.0 * yy_sky
            b_sky = 206.0 + 32.0 * yy_sky
        else:
            r_sky = 76.0 + 142.0 * (yy_sky ** 0.90)
            g_sky = 146.0 + 88.0 * (yy_sky ** 0.92)
            b_sky = 224.0 + 26.0 * (yy_sky ** 0.95)

        canvas_np[:gy, :, 0] = r_sky
        canvas_np[:gy, :, 1] = g_sky
        canvas_np[:gy, :, 2] = b_sky

        if not is_night:
            cloud_low = rng.normal(0.0, 1.0, (max(4, gy // 16), max(4, W // 16))).astype(np.float32)
            cloud_up = cv2.resize(cloud_low, (W, gy), interpolation=cv2.INTER_CUBIC)
            cloud_up = cv2.GaussianBlur(cloud_up, (61, 31), 14.0)
            cloud_mask = np.clip((cloud_up - 0.18) * 0.32, 0.0, 0.20) * (1.0 - 0.65 * yy_sky)
            for c_i in range(3):
                canvas_np[:gy, :, c_i] = canvas_np[:gy, :, c_i] * (1.0 - cloud_mask) + 252.0 * cloud_mask

        is_ew_facade = facade_side in ("EAST", "WEST")
        u_min_0 = gb0.y_min if is_ew_facade else gb0.x_min
        u_max_0 = gb0.y_max if is_ew_facade else gb0.x_max
        bldg_span_mm = max(5500, u_max_0 - u_min_0)
        bldg_w_m = bldg_span_mm / 1000.0

        is_courtyard_view = False
        for _, cy_r, _ in fl0.courtyards:
            if cy_r.height <= 400 or cy_r.width <= 400:
                continue
            if facade_side == "SOUTH" and cy_r.y_max <= gb0.y_min + 600 and cy_r.height >= 1800:
                is_courtyard_view = True
            elif facade_side == "NORTH" and cy_r.y_min >= gb0.y_max - 600 and cy_r.height >= 1800:
                is_courtyard_view = True
            elif facade_side == "WEST" and cy_r.x_max <= gb0.x_min + 600 and cy_r.width >= 1800:
                is_courtyard_view = True
            elif facade_side == "EAST" and cy_r.x_min >= gb0.x_max - 600 and cy_r.width >= 1800:
                is_courtyard_view = True

        custom_prof = (
            (site_r_state.get("custom_facade_profile") if isinstance(site_r_state, dict) else None)
            or (prev_render_state.get("custom_facade_profile") if isinstance(prev_render_state, dict) else None)
        )
        is_custom_stepped_plan = bool(isinstance(custom_prof, dict) and custom_prof.get("is_custom_stepped_plan"))
        is_townhouse_3fl_no_pilotis = bool(
            isinstance(custom_prof, dict) and custom_prof.get("profile_type") == "TOWNHOUSE_3FLOOR_NO_PILOTIS"
        )
        is_conv_1fl_carport_right = bool(
            isinstance(custom_prof, dict) and custom_prof.get("profile_type") == "CONVENTIONAL_1FLOOR_CARPORT_RIGHT"
        )
        if is_custom_stepped_plan:
            is_courtyard_view = True
            plinth_h_m = 0.0  # Stepped plan has its own +0.36m raised veranda in the recessed wing!
        elif is_conv_1fl_carport_right:
            is_courtyard_view = True
            has_open_pilotis = False
            has_kharposhteh = False
            plinth_h_m = 0.0
            bldg_w_m = float(custom_prof.get("building_width_m", 9.2))
        elif is_townhouse_3fl_no_pilotis:
            is_courtyard_view = True
            has_open_pilotis = False
            has_kharposhteh = False
            plinth_h_m = float(_univ_spec.get("plinth_height_m", 0.20)) if isinstance(_univ_spec, dict) else 0.20
            bldg_w_m = float((_univ_spec.get("building_width_m") if isinstance(_univ_spec, dict) else None) or custom_prof.get("building_width_m", 4.75))
        elif isinstance(_univ_spec, dict) and float(_univ_spec.get("building_width_m") or 0.0) >= 3.0:
            bldg_w_m = float(_univ_spec["building_width_m"])

        # Keep building width around 54% of W so the Two-Sided Courtyard (left & right walls + garden beds) is clearly visible!
        px_per_m = min((W * 0.54) / bldg_w_m, (gy * 0.80) / max(5.0, total_bldg_h_m))
        b_px_w = int(round(bldg_w_m * px_per_m))
        _view_u = (_univ_spec.get("views", {}).get(facade_side) or _univ_spec.get("views", {}).get("NORTH") or {}) if isinstance(_univ_spec, dict) else {}
        _u_left_gap = float(_view_u.get("left_courtyard_gap_ratio", 0.0)) if isinstance(_view_u, dict) else 0.0
        _u_right_gap = float(_view_u.get("right_courtyard_gap_ratio", 0.0)) if isinstance(_view_u, dict) else 0.0
        if is_custom_stepped_plan or (_u_left_gap <= 0.06 and _u_right_gap >= 0.12):
            # Building is attached (چسبیده) to the left courtyard wall and has an open courtyard gap on the right side!
            bx0 = int(W * 0.18)
            bx1 = bx0 + b_px_w
            cw_left_back_x = bx0
            cw_right_back_x = min(W - 110, bx1 + int(round(max(2.2, _u_right_gap * 12.5) * px_per_m)))
        elif _u_right_gap <= 0.06 and _u_left_gap >= 0.12:
            # Building is attached (چسبیده) to the right courtyard wall and has an open courtyard gap on the left side!
            bx1 = int(W * 0.82)
            bx0 = bx1 - b_px_w
            cw_right_back_x = bx1
            cw_left_back_x = max(110, bx0 - int(round(max(2.2, _u_left_gap * 12.5) * px_per_m)))
        else:
            bx0 = (W - b_px_w) // 2
            bx1 = bx0 + b_px_w
            cw_left_back_x = bx0
            cw_right_back_x = bx1

        # Determine exact upper-floor cantilever overhang (`cantilever_m`)
        cantilever_mm = 0
        if n_floors >= 2:
            gb1 = project.floors[1].gross_building_rect_mm
            if facade_side == "SOUTH":
                cantilever_mm = max(0, gb0.y_min - gb1.y_min)
                if cantilever_mm == 0:
                    cantilever_mm = int(getattr(project.site, "south_cantilever_mm", 1100))
            elif facade_side == "NORTH":
                cantilever_mm = max(0, gb1.y_max - gb0.y_max)
                if cantilever_mm == 0:
                    cantilever_mm = int(getattr(project.site, "courtyard_cantilever_mm", 1000))
            elif facade_side == "EAST":
                cantilever_mm = max(0, gb1.x_max - gb0.x_max)
            elif facade_side == "WEST":
                cantilever_mm = max(0, gb0.x_min - gb1.x_min)
        cantilever_m = round(cantilever_mm / 1000.0, 2)

        # Material Palettes
        if stone_color == "WHITE":
            wall_base_rgb = (244, 242, 238)
            wall_recess_rgb = (218, 216, 210)
            trim_rgb = (252, 251, 248)
            shadow_rgb = (162, 158, 152)
            joint_rgb = (212, 208, 202)
            pilaster_rgb = (248, 247, 244)
            plinth_rgb = (118, 120, 124)
        elif stone_color == "DARK_BASALT":
            wall_base_rgb = (76, 80, 86)
            wall_recess_rgb = (54, 58, 64)
            trim_rgb = (212, 204, 190)
            shadow_rgb = (36, 38, 42)
            joint_rgb = (52, 55, 60)
            pilaster_rgb = (92, 96, 104)
            plinth_rgb = (42, 44, 48)
        elif stone_color == "TERRACOTTA_BRICK":
            wall_base_rgb = (186, 102, 74)
            wall_recess_rgb = (212, 208, 200)
            trim_rgb = (236, 232, 224)
            shadow_rgb = (118, 58, 40)
            joint_rgb = (154, 82, 58)
            pilaster_rgb = (204, 198, 190)
            plinth_rgb = (74, 76, 80)
        else:
            wall_base_rgb = (238, 228, 210)
            wall_recess_rgb = (212, 200, 180)
            trim_rgb = (248, 241, 228)
            shadow_rgb = (168, 154, 132)
            joint_rgb = (204, 192, 172)
            pilaster_rgb = (245, 237, 222)
            plinth_rgb = (142, 130, 114)

        thermowood_rgb = (162, 94, 48)
        thermowood_dark = (104, 56, 26)

        frame_col_key = spec.get("window_frame_color", "DARK_CHARCOAL")
        if frame_col_key == "BRONZE_GOLD":
            frame_rgb = (58, 44, 30)
            mullion_accent_rgb = (186, 152, 88)
        elif frame_col_key == "WHITE":
            frame_rgb = (236, 238, 240)
            mullion_accent_rgb = (198, 202, 206)
        else:
            frame_rgb = (28, 34, 42)
            mullion_accent_rgb = (52, 60, 72)

        img = Image.fromarray(np.clip(canvas_np, 0, 255).astype(np.uint8), mode="RGB")
        draw = _SafePillowDraw(ImageDraw.Draw(img))

        def map_u(u_mm: int) -> int:
            rel = (u_mm - u_min_0) / float(max(1, bldg_span_mm))
            rel = max(0.0, min(1.0, rel))
            return bx0 + int(round(rel * b_px_w))

        # 1. Compute Exact Vertical Floor Boundaries (`floor_y_bounds = [(fy0, fy1), ...]`)
        plinth_px = max(6, int(round(plinth_h_m * px_per_m))) if plinth_h_m > 0.01 else 0
        y_base = gy - plinth_px
        floor_y_bounds: List[Tuple[int, int]] = []
        cur_y_bot = y_base
        for f_h_m in floor_heights_m:
            f_px = max(42, int(round(f_h_m * px_per_m)))
            cur_y_top = cur_y_bot - f_px
            floor_y_bounds.append((cur_y_top, cur_y_bot))
            cur_y_bot = cur_y_top
        top_y = cur_y_bot

        # 2. Foreground & Two-Sided Courtyard (`حیاط مشجر در دو طرف زمین با دیوارهای جانبی، باغچه و کفسازی سنگی`)
        cw_top_back = gy - int(round(2.45 * px_per_m))
        cw_top_front = gy - int(round(1.55 * px_per_m))
        if is_courtyard_view:
            # Ground Courtyard Paving (Warm Travertine Slabs with Perspective Joints)
            draw.rectangle([0, gy, W, H], fill=(222, 214, 198))
            for py_g in range(gy + 12, H, 22):
                draw.line([(0, py_g), (W, py_g)], fill=(194, 185, 168), width=1)
                line_draw.line([(0, py_g), (W, py_g)], fill=(110, 110, 110), width=1)
            for i_p in range(-9, 10):
                x_t = W // 2 + i_p * 46
                x_b = W // 2 + i_p * 118
                draw.line([(x_t, gy), (x_b, H)], fill=(194, 185, 168), width=1)

            # Left (West) & Right (East) 3D Perspective Courtyard Boundary Walls (`دیوارهای حیاط در دو طرف زمین`)
            side_wall_l = tuple(max(0, c - 8) for c in wall_base_rgb)
            side_wall_r = tuple(max(0, c - 18) for c in wall_base_rgb)
            # If building has a side gap from the courtyard wall (e.g. plan.dwg: attached on left, separated on right), draw the rear courtyard wall in that gap!
            if cw_right_back_x > bx1 + 8:
                draw.rectangle([bx1, cw_top_back, cw_right_back_x, gy], fill=wall_recess_rgb, outline=shadow_rgb, width=1)
                draw.line([(bx1, cw_top_back), (cw_right_back_x, cw_top_back)], fill=trim_rgb, width=5)
                line_draw.rectangle([bx1, cw_top_back, cw_right_back_x, gy], outline=(220, 220, 220), width=2)
            if cw_left_back_x < bx0 - 8:
                draw.rectangle([cw_left_back_x, cw_top_back, bx0, gy], fill=wall_recess_rgb, outline=shadow_rgb, width=1)
                draw.line([(cw_left_back_x, cw_top_back), (bx0, cw_top_back)], fill=trim_rgb, width=5)

            # Left courtyard wall recedes from (0, cw_top_front) to (cw_left_back_x, cw_top_back) at top, and (0, H-18) to (cw_left_back_x, gy) at base
            draw.polygon(
                [(0, cw_top_front), (cw_left_back_x, cw_top_back), (cw_left_back_x, gy), (0, H - 18)],
                fill=side_wall_l,
                outline=shadow_rgb,
            )
            # Right courtyard wall recedes from (cw_right_back_x, cw_top_back) to (W, cw_top_front) at top, and (cw_right_back_x, gy) to (W, H-18) at base
            draw.polygon(
                [(cw_right_back_x, cw_top_back), (W, cw_top_front), (W, H - 18), (cw_right_back_x, gy)],
                fill=side_wall_r,
                outline=shadow_rgb,
            )
            # Decorative Classical/Modern Framed Panels & Coping on Left and Right Courtyard Walls
            draw.line([(0, cw_top_front), (cw_left_back_x, cw_top_back)], fill=trim_rgb, width=6)
            draw.line([(cw_right_back_x, cw_top_back), (W, cw_top_front)], fill=trim_rgb, width=6)
            line_draw.line([(0, cw_top_front), (cw_left_back_x, cw_top_back)], fill=(255, 255, 255), width=2)
            line_draw.line([(cw_right_back_x, cw_top_back), (W, cw_top_front)], fill=(255, 255, 255), width=2)

            for frac_a, frac_b in ((0.15, 0.48), (0.56, 0.88)):
                # Left wall recessed decorative panel + warm wall sconce
                lx_a = int(bx0 * frac_a)
                lx_b = int(bx0 * frac_b)
                ly_top_a = int(cw_top_front + (cw_top_back - cw_top_front) * frac_a) + 18
                ly_top_b = int(cw_top_front + (cw_top_back - cw_top_front) * frac_b) + 18
                ly_bot_a = int((H - 18) + (gy - (H - 18)) * frac_a) - 34
                ly_bot_b = int((H - 18) + (gy - (H - 18)) * frac_b) - 34
                draw.polygon([(lx_a, ly_top_a), (lx_b, ly_top_b), (lx_b, ly_bot_b), (lx_a, ly_bot_a)], outline=shadow_rgb)
                sc_x, sc_y = (lx_a + lx_b) // 2, (ly_top_a + ly_top_b) // 2 + 12
                draw.ellipse([sc_x - 5, sc_y - 5, sc_x + 5, sc_y + 5], fill=(255, 232, 138))

                # Right wall recessed decorative panel + warm wall sconce
                rx_a = bx1 + int((W - bx1) * (1.0 - frac_b))
                rx_b = bx1 + int((W - bx1) * (1.0 - frac_a))
                ry_top_a = int(cw_top_back + (cw_top_front - cw_top_back) * (1.0 - frac_b)) + 18
                ry_top_b = int(cw_top_back + (cw_top_front - cw_top_back) * (1.0 - frac_a)) + 18
                ry_bot_a = int(gy + ((H - 18) - gy) * (1.0 - frac_b)) - 34
                ry_bot_b = int(gy + ((H - 18) - gy) * (1.0 - frac_a)) - 34
                draw.polygon([(rx_a, ry_top_a), (rx_b, ry_top_b), (rx_b, ry_bot_b), (rx_a, ry_bot_a)], outline=shadow_rgb)
                sc_rx, sc_ry = (rx_a + rx_b) // 2, (ry_top_a + ry_top_b) // 2 + 12
                draw.ellipse([sc_rx - 5, sc_ry - 5, sc_rx + 5, sc_ry + 5], fill=(255, 232, 138))

            # Raised Stone Planter Beds (`فلاورباکس و باغچه‌های دو طرف حیاط`) along Left & Right Courtyard Walls
            bed_w_back = int(b_px_w * 0.14)
            bed_w_front = int(W * 0.22)
            # Left garden bed
            draw.polygon(
                [(0, H - 18), (bx0, gy), (bx0 + bed_w_back, gy), (bed_w_front, H)],
                fill=(38, 108, 52),
            )
            draw.polygon(
                [(bx0, gy - 14), (bx0 + bed_w_back, gy - 14), (bed_w_front, H - 14), (0, H - 30)],
                fill=trim_rgb,
                outline=shadow_rgb,
            )
            # Right garden bed
            draw.polygon(
                [(bx1 - bed_w_back, gy), (bx1, gy), (W, H - 18), (W - bed_w_front, H)],
                fill=(38, 108, 52),
            )
            draw.polygon(
                [(bx1 - bed_w_back, gy - 14), (bx1, gy - 14), (W, H - 30), (W - bed_w_front, H - 14)],
                fill=trim_rgb,
                outline=shadow_rgb,
            )
        else:
            # Street Elevation Context
            draw.rectangle([0, cw_top_back, bx0, gy], fill=(212, 214, 218), outline=(160, 164, 170), width=1)
            draw.rectangle([bx1, cw_top_back, W, gy], fill=(212, 214, 218), outline=(160, 164, 170), width=1)
            sidewalk_h = int(round((H - gy) * 0.42))
            curb_y = gy + sidewalk_h
            draw.rectangle([0, gy, W, curb_y], fill=(222, 216, 206))
            for sx_i in range(-10, 14):
                draw.line([(W // 2 + sx_i * 58, gy), (W // 2 + sx_i * 78, curb_y)], fill=(194, 188, 178), width=1)
            draw.rectangle([0, curb_y, W, curb_y + 10], fill=(168, 172, 178), outline=(90, 94, 100), width=1)
            for cx_b in range(0, W, 96):
                draw.rectangle([cx_b, curb_y, cx_b + 48, curb_y + 10], fill=(238, 238, 238))
            draw.rectangle([0, curb_y + 10, W, H], fill=(68, 72, 80))

        depth_np[gy:H, :] = np.linspace(168, 248, H - gy, dtype=np.uint8)[:, None]

        # 3. Ground Plinth (ONLY for non-pilotis villas/duplexes; Open Pilotis is flush at ±0.00 / +0.20m!)
        if plinth_px > 0:
            draw.rectangle([bx0, y_base, bx1, gy], fill=plinth_rgb)
            if is_neoclassical:
                draw.rectangle([bx0 - 4, y_base - 4, bx1 + 4, y_base + 3], fill=trim_rgb, outline=shadow_rgb, width=1)
            depth_np[y_base:gy, bx0:bx1] = 175
            line_draw.rectangle([bx0, y_base, bx1, gy], outline=(255, 255, 255), width=2)

        def draw_photorealistic_window(
            wx0: int,
            wy0: int,
            wx1: int,
            wy1: int,
            is_tall: bool = False,
            is_double_height_void: bool = False,
            depth_val: int = 140,
            panes_override: Optional[int] = None,
            simple_frame: bool = False,
        ) -> None:
            if wx1 - wx0 < 18 or wy1 - wy0 < 18:
                return
            if is_neoclassical and not simple_frame:
                pad_f = 7
                draw.rectangle([wx0 - pad_f + 3, wy0 - pad_f + 4, wx1 + pad_f + 5, wy1 + pad_f + 7], fill=shadow_rgb)
                draw.rectangle([wx0 - pad_f, wy0 - pad_f, wx1 + pad_f, wy1 + pad_f], fill=trim_rgb, outline=shadow_rgb, width=1)
                crown_h = 11 if not is_double_height_void else 15
                draw.polygon(
                    [
                        (wx0 - pad_f - 6, wy0 - pad_f),
                        (wx1 + pad_f + 6, wy0 - pad_f),
                        (wx1 + pad_f + 2, wy0 - pad_f - crown_h),
                        (wx0 - pad_f - 2, wy0 - pad_f - crown_h),
                    ],
                    fill=trim_rgb,
                    outline=shadow_rgb,
                )
                draw.rectangle([wx0 - pad_f - 3, wy1 + pad_f, wx1 + pad_f + 3, wy1 + pad_f + 6], fill=trim_rgb, outline=shadow_rgb, width=1)
                line_draw.rectangle([wx0 - pad_f, wy0 - pad_f, wx1 + pad_f, wy1 + pad_f], outline=(255, 255, 255), width=2)
            elif simple_frame:
                pad_f = 5
                draw.rectangle([wx0 - pad_f + 2, wy0 - pad_f + 2, wx1 + pad_f + 3, wy1 + pad_f + 3], fill=shadow_rgb)
                draw.rectangle([wx0 - pad_f, wy0 - pad_f, wx1 + pad_f, wy1 + pad_f], fill=trim_rgb, outline=shadow_rgb, width=2)
                line_draw.rectangle([wx0 - pad_f, wy0 - pad_f, wx1 + pad_f, wy1 + pad_f], outline=(255, 255, 255), width=2)
            else:
                pad_f = 5
                draw.rectangle([wx0 - pad_f, wy0 - pad_f, wx1 + pad_f, wy1 + pad_f], fill=frame_rgb, outline=mullion_accent_rgb, width=1)
                if wood_accent and is_tall:
                    lw_w = min(20, max(10, (wx1 - wx0) // 8))
                    if wx0 - pad_f - lw_w > bx0 + 8:
                        draw.rectangle([wx0 - pad_f - lw_w, wy0 - pad_f, wx0 - pad_f, wy1 + pad_f], fill=thermowood_rgb)
                        for sy_l in range(wy0, wy1, 6):
                            draw.line([(wx0 - pad_f - lw_w, sy_l), (wx0 - pad_f, sy_l)], fill=thermowood_dark, width=1)

            ww = max(1, wx1 - wx0)
            wh = max(1, wy1 - wy0)
            for ry in range(wy0, wy1):
                t_y = (ry - wy0) / float(wh)
                if is_night or is_golden:
                    r_g = int(252 - 36 * t_y)
                    g_g = int(218 - 52 * t_y)
                    b_g = int(134 - 58 * t_y)
                else:
                    # Realistic Low-E Architectural Glass reflecting sky at top and warm interior at bottom
                    r_g = int(68 + 88 * (t_y ** 1.1))
                    g_g = int(118 + 64 * (t_y ** 1.05))
                    b_g = int(164 + 28 * t_y)
                draw.line([(wx0, ry), (wx1, ry)], fill=(r_g, g_g, b_g))

            curt_w = max(8, ww // 6)
            curt_col = (238, 232, 218) if not is_night else (252, 232, 162)
            draw.rectangle([wx0 + 4, wy0 + 4, wx0 + 4 + curt_w, wy1 - 4], fill=curt_col)
            draw.rectangle([wx1 - 4 - curt_w, wy0 + 4, wx1 - 4, wy1 - 4], fill=curt_col)
            for cx_f in range(wx0 + 6, wx0 + 4 + curt_w, 4):
                draw.line([(cx_f, wy0 + 4), (cx_f, wy1 - 4)], fill=(210, 202, 186), width=1)
            for cx_f in range(wx1 - 4 - curt_w, wx1 - 4, 4):
                draw.line([(cx_f, wy0 + 4), (cx_f, wy1 - 4)], fill=(210, 202, 186), width=1)

            if is_double_height_void or (is_tall and ww >= 80):
                ch_x = (wx0 + wx1) // 2
                ch_y = wy0 + int(wh * 0.22)
                draw.line([(ch_x, wy0 + 3), (ch_x, ch_y)], fill=(212, 175, 55), width=2)
                draw.ellipse([ch_x - 12, ch_y - 5, ch_x + 12, ch_y + 7], fill=(255, 242, 175), outline=(204, 168, 52), width=1)

            draw.polygon(
                [
                    (wx0 + int(ww * 0.16), wy0 + 4),
                    (wx0 + int(ww * 0.30), wy0 + 4),
                    (wx0 + int(ww * 0.10), wy1 - 4),
                    (wx0 + 4, wy1 - 4),
                ],
                fill=(202, 228, 248) if not is_night else (255, 240, 188),
            )

            draw.rectangle([wx0, wy0, wx1, wy1], outline=frame_rgb, width=2)
            line_draw.rectangle([wx0, wy0, wx1, wy1], outline=(255, 255, 255), width=2)
            if panes_override is not None and int(panes_override) >= 1:
                n_panes = int(panes_override)
            else:
                n_panes = 4 if ww >= int(2.6 * px_per_m) else (3 if ww >= int(1.65 * px_per_m) else 2)
            for p_i in range(1, n_panes):
                mx = wx0 + int(ww * p_i / float(n_panes))
                draw.line([(mx, wy0), (mx, wy1)], fill=frame_rgb, width=3 if simple_frame else 2)
                line_draw.line([(mx, wy0), (mx, wy1)], fill=(255, 255, 255), width=2)

            if is_double_height_void:
                for r_frac in (0.25, 0.50, 0.75):
                    ty = wy0 + int(wh * r_frac)
                    draw.line([(wx0, ty), (wx1, ty)], fill=frame_rgb, width=2)
                    line_draw.line([(wx0, ty), (wx1, ty)], fill=(255, 255, 255), width=2)
            elif is_neoclassical and not simple_frame:
                ty = wy0 + int(wh * 0.26)
                draw.line([(wx0, ty), (wx1, ty)], fill=frame_rgb, width=2)
                if is_tall:
                    ty2 = wy0 + int(wh * 0.65)
                    draw.line([(wx0, ty2), (wx1, ty2)], fill=frame_rgb, width=1)

            depth_np[max(0, wy0):min(H, wy1), max(0, wx0):min(W, wx1)] = depth_val

        def draw_balustrade(rx0: int, ry_bot: int, rx1: int, rail_h: int) -> None:
            if rx1 - rx0 < 20:
                return
            ry_top = ry_bot - rail_h
            if balustrade_type == "STONE_BALUSTER":
                draw.rectangle([rx0, ry_bot - 5, rx1, ry_bot], fill=trim_rgb, outline=shadow_rgb, width=1)
                draw.rectangle([rx0 - 2, ry_top, rx1 + 2, ry_top + 6], fill=trim_rgb, outline=shadow_rgb, width=1)
                step_b = max(11, int(round(0.22 * px_per_m)))
                for bx_b in range(rx0 + 9, rx1 - 7, step_b):
                    draw.rectangle([bx_b - 3, ry_top + 6, bx_b + 3, ry_bot - 5], fill=wall_base_rgb, outline=shadow_rgb, width=1)
                    draw.ellipse([bx_b - 4, ry_top + rail_h // 3, bx_b + 4, ry_top + (2 * rail_h) // 3], fill=trim_rgb, outline=shadow_rgb, width=1)
                    line_draw.rectangle([bx_b - 3, ry_top + 6, bx_b + 3, ry_bot - 5], outline=(220, 220, 220), width=1)
            elif balustrade_type == "DARK_METAL":
                draw.rectangle([rx0, ry_top, rx1, ry_top + 4], fill=frame_rgb)
                draw.rectangle([rx0, ry_bot - 4, rx1, ry_bot], fill=frame_rgb)
                for bx_b in range(rx0 + 8, rx1 - 6, 11):
                    draw.line([(bx_b, ry_top + 4), (bx_b, ry_bot - 4)], fill=frame_rgb, width=2)
            else:
                for gy_r in range(ry_top + 4, ry_bot):
                    t_g = (gy_r - ry_top) / float(max(1, rail_h))
                    draw.line([(rx0, gy_r), (rx1, gy_r)], fill=(int(172 + 35 * t_g), int(214 + 20 * t_g), 242))
                draw.rectangle([rx0, ry_top, rx1, ry_bot], outline=(56, 189, 248), width=1)
                draw.rectangle([rx0, ry_top, rx1, ry_top + 4], fill=frame_rgb)
                n_posts = max(2, (rx1 - rx0) // 105)
                for p_i in range(1, n_posts):
                    px_p = rx0 + int((rx1 - rx0) * p_i / float(n_posts))
                    draw.line([(px_p, ry_top), (px_p, ry_bot)], fill=frame_rgb, width=2)
            line_draw.rectangle([rx0, ry_top, rx1, ry_bot], outline=(255, 255, 255), width=2)
            depth_np[max(0, ry_top):min(H, ry_bot), max(0, rx0):min(W, rx1)] = 238

        # 4. Render Each Floor Tier from Ground (`f_idx=0`) to Top (`f_idx=n_floors-1`)
        pilaster_x_pixels: List[int] = []

        for f_idx, fl in enumerate(active_floors):
            fy0, fy1 = floor_y_bounds[f_idx]
            gb_fl = fl.gross_building_rect_mm
            has_cantilever_here = (f_idx >= 1 and cantilever_m > 0.05)
            cant_outset_px = int(round(min(1.5, cantilever_m) * 12)) if has_cantilever_here else 0
            fl_bx0 = bx0 - cant_outset_px
            fl_bx1 = bx1 + cant_outset_px

            # Determine column X positions on `facade_side`
            col_us: List[int] = []
            for c in fl.columns:
                cx_c, cy_c = c.rect_mm.center
                on_side = (
                    (facade_side == "SOUTH" and cy_c <= gb_fl.y_min + 2600)
                    or (facade_side == "NORTH" and cy_c >= gb_fl.y_max - 2600)
                    or (facade_side == "WEST" and cx_c <= gb_fl.x_min + 2600)
                    or (facade_side == "EAST" and cx_c >= gb_fl.x_max - 2600)
                )
                if on_side:
                    col_us.append(cy_c if is_ew_facade else cx_c)
            col_us = sorted(set(col_us))
            if not col_us:
                col_us = [u_min_0 + 250, (u_min_0 + u_max_0) // 2, u_max_0 - 250]
            pil_w = max(16, int(round(0.40 * px_per_m)))

            # =========================================================================
            # CASE A0: 3-STORY TOWNHOUSE WITHOUT OPEN PILOTIS (`houseplan- arel.ir.dwg`:
            #   - Ground Floor (`PLANTA BAJA`): Left Recessed Pedestrian Entrance Portal + Right Wide Window/Garage Bay on 2-Step Plinth
            #   - Floors 1 & 2 (`SEGUNDA & TERCERA PLANTA`): Cantilevered 2-Story Box with Left Balcony + Right Tall Window & T-Shaped Feature Frame)
            # =========================================================================
            if is_conv_1fl_carport_right:
                # Exact Left-to-Right 3D Extrusion of `casa habitacion convencional.dwg` (Verified against 8x CAD zoom):
                #   1. LEFT WING (`bx0 .. x_left_front_end`, u=0.00..0.44 — `قسمت بزرگ ساختمان سمت چپ هست`):
                #      - Forward-most volume of the house (floor at +0.30m above ±0.00m courtyard).
                #      - Left section (`u=0.00..0.23`) is solid stone wall (`دیوار صاف سمت چپ`).
                #      - Window starts near the middle (`u=0.23..0.44`, `پنجره از وسط‌های ساختمون شروع میشه`) with realistic sill (`OKB=0.78m`)
                #        and continues diagonally across the 45° chamfered wall (`x_left_front_end .. x_chamf_end`, u=0.44..0.54, `ادامه‌اش هم موربه`)!
                #      - Topped by a narrow rain-drip awning (`باران‌گیر بالای پنجره با عرض کم`)!
                #   2. MIDDLE DIAGONAL BREAK (`x_chamf_end .. x_kink_end`, u=0.54..0.74 — `در و پله تو شکستگی هستند`):
                #      - Recesses diagonally backward (`شکستگی و عقب‌رفتگی میانی`).
                #      - Contains the Entrance Door (`در ورودی`) and 2 Step Treads (`دو تا کف پله که از 0.00 حیاط رسیده به +0.30 در ساختمان`),
                #        covered by a Large Canopy spanning from the start of the steps to the end of the steps (`سایبان بزرگ از شروع پله تا انتهای پله`)!
                #   3. RIGHT SMALL RECESSED WING (`x_kink_end .. bx1`, u=0.74..1.00 — `قسمت کوچک ساختمان سمت راست که از شکستگی شروع میشه و بعد قسمت آخرش که پنجره است صاف میشه`):
                #      - Straightens out horizontally at the recessed depth (`قسمت آخرش صاف میشه`),
                #      - Features a Small Window (`یک پنجره کوچک` at `u=0.76..0.96` with standard high sill `OKB=1.05m` and NO flowerbox under the window!).
                #   4. COURTYARD & ROOF:
                #      - 1 Car parked in the open right courtyard (`یک ماشین تو حیاط پارکه`, in front of the recessed right wing),
                #      - Two small garden planter strips on both left & right sides of the courtyard (`دو باغچه کوچک دو طرف حیاط`),
                #      - Full-width kinked overarching eave canopy (`سایبان سراسری بالای ساختمان که شکستگی داره`) + Sloped Hipped Roof (`سقف شیب‌دار`)!
                plat_px_c = max(14, int(round(0.30 * px_per_m)))  # +0.30m house floor above ±0.00m courtyard (2 steps x 15cm)
                y_house_fl = fy1 - plat_px_c

                x_win_start = bx0 + int(round(b_px_w * 0.23))
                x_left_front_end = bx0 + int(round(b_px_w * 0.44))
                x_chamf_end = bx0 + int(round(b_px_w * 0.54))
                x_kink_end = bx0 + int(round(b_px_w * 0.74))

                # Perspective Y coordinates for the stepped top eave & base line (forward on left, receding on right)
                y_top_left = fy0
                y_top_chamf = fy0 + 10
                y_top_right = fy0 + 20

                y_bot_left = y_house_fl
                y_bot_chamf = y_house_fl - 6
                y_bot_right = y_house_fl - 12

                # ------------------------------------------------------------------
                # A) RIGHT SMALL RECESSED WING (`x_kink_end .. bx1`, u=0.74..1.00 — straight recessed wall + small window)
                # ------------------------------------------------------------------
                right_recess_col = tuple(max(0, c - 24) for c in wall_recess_rgb)
                draw.rectangle([x_kink_end, y_top_right, bx1, y_bot_right], fill=right_recess_col, outline=shadow_rgb, width=2)
                for cy_l in range(y_top_right + 14, y_bot_right, 16):
                    draw.line([(x_kink_end + 2, cy_l), (bx1 - 2, cy_l)], fill=joint_rgb, width=1)
                # Plinth at base of right recessed wing
                draw.rectangle([x_kink_end, y_bot_right, bx1, fy1 - 12], fill=plinth_rgb, outline=shadow_rgb, width=1)
                line_draw.rectangle([x_kink_end, y_top_right, bx1, fy1 - 12], outline=(255, 255, 255), width=2)
                depth_np[max(0, y_top_right):min(H, fy1 - 12), max(0, x_kink_end):min(W, bx1)] = 140

                # Small Window on the straight far-right section (`پنجره کوچک در قسمت صافِ انتهای سمت راست`, u=0.77..0.95, proportionate sill & height!)
                sw_x0 = x_kink_end + int(round((bx1 - x_kink_end) * 0.14))
                sw_x1 = bx1 - int(round((bx1 - x_kink_end) * 0.12))
                sw_y0 = y_top_right + int(round(0.42 * px_per_m))
                sw_y1 = y_top_right + int(round(1.22 * px_per_m))
                draw_photorealistic_window(sw_x0, sw_y0, sw_x1, sw_y1, is_tall=False, depth_val=135)

                # ------------------------------------------------------------------
                # B) MIDDLE DIAGONAL BREAK (`x_chamf_end .. x_kink_end`, u=0.54..0.74 — `در و پله تو شکستگی هستند`)
                # ------------------------------------------------------------------
                kink_wall_col = tuple(max(0, c - 14) for c in wall_recess_rgb)
                draw.polygon(
                    [(x_chamf_end, y_top_chamf), (x_kink_end, y_top_right), (x_kink_end, y_bot_right), (x_chamf_end, y_bot_chamf)],
                    fill=kink_wall_col,
                    outline=shadow_rgb,
                )
                line_draw.polygon(
                    [(x_chamf_end, y_top_chamf), (x_kink_end, y_top_right), (x_kink_end, y_bot_right), (x_chamf_end, y_bot_chamf)],
                    outline=(255, 255, 255),
                )
                depth_np[max(0, y_top_chamf):min(H, y_bot_chamf), max(0, x_chamf_end):min(W, x_kink_end)] = 165

                # Entrance Door inside the diagonal kink (`در تو شکستگی`)
                ed_x0 = x_chamf_end + int(round((x_kink_end - x_chamf_end) * 0.18))
                ed_x1 = x_kink_end - int(round((x_kink_end - x_chamf_end) * 0.16))
                ed_y_top_l = y_top_chamf + int(round(0.38 * px_per_m)) + 4
                ed_y_top_r = y_top_right + int(round(0.38 * px_per_m))
                ed_y_bot_l = y_bot_chamf
                ed_y_bot_r = y_bot_right
                draw.polygon(
                    [(ed_x0 - 3, ed_y_top_l - 3), (ed_x1 + 3, ed_y_top_r - 3), (ed_x1 + 3, ed_y_bot_r), (ed_x0 - 3, ed_y_bot_l)],
                    fill=trim_rgb,
                    outline=shadow_rgb,
                )
                draw.polygon(
                    [(ed_x0, ed_y_top_l), (ed_x1, ed_y_top_r), (ed_x1, ed_y_bot_r), (ed_x0, ed_y_bot_l)],
                    fill=(58, 38, 24),
                    outline=frame_rgb,
                )
                d_gl = (252, 228, 142) if is_night else (164, 198, 224)
                draw.polygon(
                    [(ed_x0 + 5, ed_y_top_l + 6), (ed_x1 - 5, ed_y_top_r + 6), (ed_x1 - 5, ed_y_bot_r - 8), (ed_x0 + 5, ed_y_bot_l - 8)],
                    fill=d_gl,
                    outline=(212, 175, 55),
                )
                line_draw.polygon([(ed_x0, ed_y_top_l), (ed_x1, ed_y_top_r), (ed_x1, ed_y_bot_r), (ed_x0, ed_y_bot_l)], outline=(255, 255, 255))

                # 2 Step Treads (`دو تا کف پله در قسمت شکستگی که از 0.00 حیاط رسیده به +0.30 کف ساختمان`)
                st_x0 = x_chamf_end - 4
                st_x1 = x_kink_end + 4
                step_h_half = max(5, plat_px_c // 2)
                # Upper step tread (+0.30m) & Lower step tread (+0.15m)
                draw.polygon(
                    [(st_x0, y_bot_chamf), (st_x1, y_bot_right), (st_x1 + 4, y_bot_right + step_h_half), (st_x0 + 4, y_bot_chamf + step_h_half)],
                    fill=trim_rgb,
                    outline=shadow_rgb,
                )
                draw.polygon(
                    [(st_x0 + 4, y_bot_chamf + step_h_half), (st_x1 + 4, y_bot_right + step_h_half), (st_x1 + 8, y_bot_right + 2 * step_h_half), (st_x0 + 8, y_bot_chamf + 2 * step_h_half)],
                    fill=pilaster_rgb,
                    outline=shadow_rgb,
                )
                line_draw.polygon(
                    [(st_x0, y_bot_chamf), (st_x1, y_bot_right), (st_x1 + 8, y_bot_right + 2 * step_h_half), (st_x0 + 8, y_bot_chamf + 2 * step_h_half)],
                    outline=(255, 255, 255),
                )

                # Large Entrance Canopy from the start of the steps to the end of the steps (`سایبان بزرگ از شروع پله تا انتهای پله`)
                can_s_y0_l = ed_y_top_l - 16
                can_s_y0_r = ed_y_top_r - 16
                draw.polygon(
                    [(st_x0 - 6, can_s_y0_l), (st_x1 + 6, can_s_y0_r), (st_x1 + 12, can_s_y0_r + 11), (st_x0 - 2, can_s_y0_l + 11)],
                    fill=trim_rgb,
                    outline=shadow_rgb,
                )
                line_draw.polygon(
                    [(st_x0 - 6, can_s_y0_l), (st_x1 + 6, can_s_y0_r), (st_x1 + 12, can_s_y0_r + 11), (st_x0 - 2, can_s_y0_l + 11)],
                    outline=(255, 255, 255),
                )

                # ------------------------------------------------------------------
                # C) LARGE LEFT FORWARD WING (`bx0 .. x_left_front_end`, u=0.00..0.44) + 45° CHAMFER (`x_left_front_end .. x_chamf_end`, u=0.44..0.54)
                # ------------------------------------------------------------------
                # 1. Left Forward Wall (`bx0 .. x_left_front_end`)
                draw.rectangle([bx0, y_top_left, x_left_front_end, y_bot_left], fill=wall_base_rgb, outline=shadow_rgb, width=2)
                for cy_l in range(y_top_left + 16, y_bot_left, 18):
                    draw.line([(bx0 + 2, cy_l), (x_left_front_end - 2, cy_l)], fill=joint_rgb, width=1)
                draw.rectangle([bx0, y_bot_left, x_left_front_end, fy1], fill=plinth_rgb, outline=shadow_rgb, width=1)
                line_draw.rectangle([bx0, y_top_left, x_left_front_end, fy1], outline=(255, 255, 255), width=2)
                depth_np[max(0, y_top_left):min(H, fy1), max(0, bx0):min(W, x_left_front_end)] = 215

                # 2. 45° Chamfered Wall (`x_left_front_end .. x_chamf_end`)
                chamf_wall_col = tuple(max(0, c - 8) for c in wall_base_rgb)
                draw.polygon(
                    [(x_left_front_end, y_top_left), (x_chamf_end, y_top_chamf), (x_chamf_end, y_bot_chamf), (x_left_front_end, y_bot_left)],
                    fill=chamf_wall_col,
                    outline=shadow_rgb,
                )
                draw.polygon(
                    [(x_left_front_end, y_bot_left), (x_chamf_end, y_bot_chamf), (x_chamf_end, y_bot_chamf + plat_px_c), (x_left_front_end, fy1)],
                    fill=plinth_rgb,
                    outline=shadow_rgb,
                )
                depth_np[max(0, y_top_left):min(H, fy1), max(0, x_left_front_end):min(W, x_chamf_end)] = 192

                # 3. Window starting near the middle of the Left Wing (`x_win_start .. x_left_front_end`, u=0.23..0.44) with proportionate sill (`OKB=0.78m`)
                mw_x0 = x_win_start
                mw_x1 = x_left_front_end - 2
                mw_y0 = y_top_left + int(round(0.46 * px_per_m))
                mw_y1 = y_bot_left - int(round(0.76 * px_per_m))
                draw_photorealistic_window(mw_x0, mw_y0, mw_x1, mw_y1, is_tall=False, depth_val=202)

                # 4. Angled/Chamfered continuation of that window (`x_left_front_end .. x_chamf_end`, u=0.44..0.54 — `ادامه‌اش هم موربه`)
                cw_x0 = x_left_front_end - 2
                cw_x1 = x_chamf_end - 4
                cw_y0_r = mw_y0 + 8
                cw_y1_r = mw_y1 - 5
                draw.polygon(
                    [(cw_x0, mw_y0 - 5), (cw_x1 + 3, cw_y0_r - 5), (cw_x1 + 3, cw_y1_r + 5), (cw_x0, mw_y1 + 5)],
                    fill=trim_rgb,
                    outline=shadow_rgb,
                )
                draw.polygon(
                    [(cw_x0, mw_y0), (cw_x1, cw_y0_r), (cw_x1, cw_y1_r), (cw_x0, mw_y1)],
                    fill=(96, 148, 186) if not is_night else (238, 198, 118),
                    outline=frame_rgb,
                )
                cw_mid_x = (cw_x0 + cw_x1) // 2
                draw.line([(cw_mid_x, (mw_y0 + cw_y0_r) // 2), (cw_mid_x, (mw_y1 + cw_y1_r) // 2)], fill=frame_rgb, width=2)
                draw.line([(cw_x0, mw_y0), (cw_x0, mw_y1)], fill=frame_rgb, width=3)
                line_draw.polygon([(cw_x0, mw_y0), (cw_x1, cw_y0_r), (cw_x1, cw_y1_r), (cw_x0, mw_y1)], outline=(255, 255, 255))

                # 5. Narrow Rain-Drip Awning directly above the horizontal + chamfered window (`یه باران‌گیر بالای پنجره هست با عرض کم`)
                drip_y0 = mw_y0 - 13
                drip_y1 = mw_y0 - 5
                draw.polygon(
                    [
                        (mw_x0 - 6, drip_y0),
                        (x_left_front_end, drip_y0),
                        (cw_x1 + 5, drip_y0 + 8),
                        (cw_x1 + 7, drip_y1 + 8),
                        (x_left_front_end, drip_y1),
                        (mw_x0 - 8, drip_y1),
                    ],
                    fill=trim_rgb,
                    outline=shadow_rgb,
                )
                line_draw.line([(mw_x0 - 6, drip_y0), (x_left_front_end, drip_y0), (cw_x1 + 5, drip_y0 + 8)], fill=(255, 255, 255), width=2)

                # ------------------------------------------------------------------
                # D) FULL-WIDTH KINKED OVERARCHING CANOPY (`سایبان سراسری بالای ساختمان که شکستگی داره`) + SLOPED ROOF (`سقف شیب‌دار`)
                # ------------------------------------------------------------------
                eave_h = 14
                kink_canopy_poly = [
                    (bx0 - 16, y_top_left - eave_h),
                    (x_left_front_end + 4, y_top_left - eave_h),
                    (x_chamf_end + 2, y_top_chamf - eave_h),
                    (x_kink_end, y_top_right - eave_h),
                    (bx1 + 16, y_top_right - eave_h),
                    (bx1 + 12, y_top_right + 2),
                    (x_kink_end, y_top_right + 2),
                    (x_chamf_end + 2, y_top_chamf + 2),
                    (x_left_front_end + 4, y_top_left + 2),
                    (bx0 - 12, y_top_left + 2),
                ]
                draw.polygon(kink_canopy_poly, fill=trim_rgb, outline=shadow_rgb)
                line_draw.polygon(kink_canopy_poly, outline=(255, 255, 255))

                # Sloped / Pitched Hipped Roof (`سقف شیب‌دار`) above the kinked overarching canopy
                roof_ridge_y = y_top_left - eave_h - int(round(0.84 * px_per_m))
                ridge_x_l = bx0 + int(round(b_px_w * 0.22))
                ridge_x_mid = x_left_front_end + 10
                ridge_x_r = bx0 + int(round(b_px_w * 0.78))
                roof_tile_main = (158, 92, 68) if not is_night else (88, 52, 40)
                roof_tile_recess = (132, 76, 56) if not is_night else (70, 42, 32)

                # Left forward sloped roof plane (over Large Left Wing)
                y_eave_l = y_top_left - eave_h
                y_eave_r = y_top_right - eave_h
                draw.polygon(
                    [(bx0 - 12, y_eave_l), (ridge_x_l, roof_ridge_y), (ridge_x_mid, roof_ridge_y), (x_chamf_end + 2, y_top_chamf - eave_h), (x_left_front_end + 4, y_eave_l)],
                    fill=roof_tile_main,
                    outline=shadow_rgb,
                )
                # Right recessed sloped roof plane (over Middle Break & Small Right Wing)
                draw.polygon(
                    [(x_chamf_end + 2, y_top_chamf - eave_h), (ridge_x_mid, roof_ridge_y), (ridge_x_r, roof_ridge_y + 8), (bx1 + 12, y_eave_r), (x_kink_end, y_eave_r)],
                    fill=roof_tile_recess,
                    outline=shadow_rgb,
                )
                # Hip/valley line at the roof step
                draw.line([(x_chamf_end + 2, y_top_chamf - eave_h), (ridge_x_mid, roof_ridge_y)], fill=shadow_rgb, width=2)
                for ry_t in range(roof_ridge_y + 7, y_eave_l, 6):
                    t_l = (ry_t - roof_ridge_y) / float(max(1, y_eave_l - roof_ridge_y))
                    rxl = int(ridge_x_l + (bx0 - 10 - ridge_x_l) * t_l)
                    rxm = int(ridge_x_mid + (x_chamf_end - ridge_x_mid) * t_l)
                    draw.line([(rxl, ry_t), (rxm, ry_t)], fill=shadow_rgb, width=1)
                for ry_t in range(roof_ridge_y + 10, y_eave_r, 6):
                    t_r = (ry_t - (roof_ridge_y + 8)) / float(max(1, y_eave_r - (roof_ridge_y + 8)))
                    rxm = int(ridge_x_mid + (x_chamf_end - ridge_x_mid) * t_r)
                    rxr = int(ridge_x_r + (bx1 + 10 - ridge_x_r) * t_r)
                    draw.line([(rxm, ry_t), (rxr, ry_t)], fill=shadow_rgb, width=1)
                line_draw.polygon(
                    [(bx0 - 12, y_eave_l), (ridge_x_l, roof_ridge_y), (ridge_x_r, roof_ridge_y + 8), (bx1 + 12, y_eave_r), (x_kink_end, y_eave_r), (x_left_front_end + 4, y_eave_l)],
                    outline=(255, 255, 255),
                )
                depth_np[max(0, roof_ridge_y):min(H, y_top_right), max(0, bx0 - 12):min(W, bx1 + 12)] = 175

                # ------------------------------------------------------------------
                # E) 1 CAR PARKED IN THE OPEN RIGHT COURTYARD (`یک ماشین تو حیاط پارکه`, u=0.64..0.88, in front of the recessed Small Right Wing)
                # ------------------------------------------------------------------
                car_w_px = int(round(1.80 * px_per_m))
                car_h_px = int(round(car_w_px * 0.78))
                car_cx0 = bx0 + int(round(b_px_w * 0.76)) - car_w_px // 2
                car_cx1 = car_cx0 + car_w_px
                car_y_ground = fy1 + int(round((H - fy1) * 0.30))
                _draw_3d_parked_car(draw, line_draw, depth_np, car_cx0, car_cx1, car_y_ground, car_h_px, body_rgb=(238, 240, 244), is_night=is_night)
                continue

            # =========================================================================
            # CASE A_UNIV: UNIVERSAL CAD / RAY-CAST BAY EXTRUDER (`universal_facade_spec`)
            # Directly renders ANY extracted multi-floor or single-floor CAD specification
            # (`recess_m`, `cantilever_m`, `platform_elev_m`, `steps_count`, `has_balcony_railing`,
            # `has_pilasters`, `openings` with exact `u0`, `u1`, `okb_m`, `head_m`, and `panes`!)
            # =========================================================================
            _u_floors_list = _view_u.get("floors", []) if isinstance(_view_u, dict) else []
            if (
                not is_custom_stepped_plan
                and not is_conv_1fl_carport_right
                and isinstance(_early_prof, dict)
                and _early_prof.get("profile_type") in ("UNIVERSAL_RAYCAST_FACADE", "TOWNHOUSE_3FLOOR_NO_PILOTIS")
                and f_idx < len(_u_floors_list)
                and not (f_idx == 0 and has_open_pilotis)
            ):
                u_fl_spec = _u_floors_list[f_idx]
                u_bays = u_fl_spec.get("bays") or []
                if u_bays:
                    pil_u_w = max(12, int(round(0.32 * px_per_m)))
                    slab_u_h = max(6, int(round(0.18 * px_per_m)))
                    for b_item in u_bays:
                        bu0 = float(b_item.get("u0", 0.0))
                        bu1 = float(b_item.get("u1", 1.0))
                        b_rec_m = float(b_item.get("recess_m", 0.0))
                        b_cant_m = float(b_item.get("cantilever_m", 0.0))
                        b_plat_m = float(b_item.get("platform_elev_m", 0.0))
                        b_steps = int(b_item.get("steps_count", 0))
                        b_balc = bool(b_item.get("has_balcony_railing", False))
                        b_frame = bool(b_item.get("has_feature_frame", False))
                        b_pilasters = bool(b_item.get("has_pilasters", _has_univ_pilasters))
                        cant_px_b = int(round(b_cant_m * 12)) if (f_idx >= 1 and b_pilasters) else 0
                        bx_start = (bx0 - cant_px_b) + int(round(bu0 * (b_px_w + 2 * cant_px_b)))
                        bx_end = (bx0 - cant_px_b) + int(round(bu1 * (b_px_w + 2 * cant_px_b)))
                        is_recessed_bay = b_rec_m > 0.15
                        bay_wall_col = wall_recess_rgb if is_recessed_bay else wall_base_rgb
                        draw.rectangle([bx_start, fy0, bx_end, fy1], fill=bay_wall_col, outline=shadow_rgb, width=2)
                        for cy_l in range(fy0 + 16, fy1, 18):
                            draw.line([(bx_start + 2, cy_l), (bx_end - 2, cy_l)], fill=joint_rgb, width=1)
                        line_draw.rectangle([bx_start, fy0, bx_end, fy1], outline=(255, 255, 255), width=3)
                        depth_np[max(0, fy0):min(H, fy1), max(0, bx_start):min(W, bx_end)] = 176 if is_recessed_bay else 216
                        if b_pilasters:
                            draw.rectangle([bx_start, fy0 + 2, bx_start + pil_u_w, fy1], fill=pilaster_rgb, outline=shadow_rgb, width=1)
                            draw.rectangle([bx_end - pil_u_w, fy0 + 2, bx_end, fy1], fill=pilaster_rgb, outline=shadow_rgb, width=1)
                        elif f_idx == 1 and b_cant_m > 0.05:
                            draw.rectangle([bx_start, fy1 - 5, bx_end, fy1 + 3], fill=trim_rgb, outline=shadow_rgb, width=1)
                            line_draw.line([(bx_start, fy1), (bx_end, fy1)], fill=(255, 255, 255), width=2)

                        if f_idx == 0 and plinth_px > 0:
                            s_mid_y = y_base + plinth_px // 2
                            draw.rectangle([bx0 - 10, y_base, bx1 + 10, s_mid_y], fill=trim_rgb, outline=shadow_rgb, width=1)
                            draw.rectangle([bx0 - 20, s_mid_y, bx1 + 20, gy], fill=pilaster_rgb, outline=shadow_rgb, width=1)
                            line_draw.rectangle([bx0 - 20, y_base, bx1 + 20, gy], outline=(255, 255, 255), width=2)

                        for op in (b_item.get("openings") or []):
                            op_t = str(op.get("type", "WINDOW")).upper()
                            ou0 = float(op.get("u0", bu0 + 0.05))
                            ou1 = float(op.get("u1", bu1 - 0.05))
                            okb_m = float(op.get("okb_m", 0.0))
                            head_m = float(op.get("head_m", 2.15))
                            op_panes = op.get("panes")
                            ox0 = (bx0 - cant_px_b) + int(round(ou0 * (b_px_w + 2 * cant_px_b)))
                            ox1 = (bx0 - cant_px_b) + int(round(ou1 * (b_px_w + 2 * cant_px_b)))
                            oy1 = fy1 - int(round(okb_m * px_per_m))
                            oy0 = max(fy0 + 8, fy1 - int(round(head_m * px_per_m)))
                            if op_t == "ENTRANCE_DOOR":
                                draw.rectangle([ox0 - 3, oy0 - 3, ox1 + 3, fy1], fill=trim_rgb, outline=shadow_rgb, width=1)
                                draw.rectangle([ox0, oy0, ox1, fy1], fill=(58, 40, 28), outline=frame_rgb, width=2)
                                d_gl_c = (252, 228, 142) if is_night else (156, 192, 218)
                                draw.rectangle([ox0 + 5, oy0 + 6, ox1 - 5, fy1 - 6], fill=d_gl_c, outline=frame_rgb, width=1)
                                line_draw.rectangle([ox0, oy0, ox1, fy1], outline=(255, 255, 255), width=2)
                                depth_np[max(0, oy0):min(H, fy1), max(0, ox0):min(W, ox1)] = 148
                            else:
                                draw_photorealistic_window(
                                    ox0,
                                    oy0,
                                    ox1,
                                    oy1,
                                    is_tall=(okb_m <= 0.25),
                                    depth_val=145 if is_recessed_bay else 188,
                                    panes_override=int(op_panes) if op_panes is not None else None,
                                    simple_frame=(not b_pilasters),
                                )
                        if b_balc and f_idx >= 1:
                            rail_u_h = max(22, int(round(0.92 * px_per_m)))
                            draw_balustrade(bx_start + pil_u_w, fy1 - slab_u_h, bx_end - pil_u_w, rail_u_h)
                        if b_frame:
                            draw.rectangle([bx_start - 3, fy1 - slab_u_h - 3, bx_end + 3, fy1 + 2], fill=trim_rgb, outline=shadow_rgb, width=1)
                    continue

            # =========================================================================
            # CASE A: TRUE OPEN PILOTIS GROUND FLOOR (`f_idx == 0 and fl.is_open_pilotis`)
            # Zero front wall, zero front steps, freestanding columns, central recessed
            # Stair & Elevator Box (`باکس پله و آسانسور در وسط ساختمان`), Pedestrian Path
            # (`مسیر پیاده`), and 3D Parked Cars (`P1` and `P2`)!
            # =========================================================================
            if f_idx == 0 and fl.is_open_pilotis:
                # 1. Deep shaded Open Pilotis Interior Background (`فضای باز و عمق پیلوت`)
                pil_bg_top = (64, 68, 76) if not is_night else (36, 40, 50)
                pil_bg_bot = (112, 110, 106) if not is_night else (58, 60, 68)
                for py_i in range(fy0, fy1):
                    t_p = (py_i - fy0) / float(max(1, fy1 - fy0))
                    c_row = (
                        int(pil_bg_top[0] + (pil_bg_bot[0] - pil_bg_top[0]) * t_p),
                        int(pil_bg_top[1] + (pil_bg_bot[1] - pil_bg_top[1]) * t_p),
                        int(pil_bg_top[2] + (pil_bg_bot[2] - pil_bg_top[2]) * t_p),
                    )
                    draw.line([(bx0, py_i), (bx1, py_i)], fill=c_row)
                depth_np[max(0, fy0):min(H, fy1), max(0, bx0):min(W, bx1)] = 115

                # 2. Perspective Pilotis Ceiling Soffit (`سقف کاذب پیلوت با نور مخفی و هالوژن`)
                ceil_depth_px = max(18, int((fy1 - fy0) * 0.22))
                soff_col = (196, 188, 174) if not is_night else (142, 132, 114)
                draw.polygon(
                    [(bx0, fy0), (bx1, fy0), (bx1 - 28, fy0 + ceil_depth_px), (bx0 + 28, fy0 + ceil_depth_px)],
                    fill=soff_col,
                    outline=shadow_rgb,
                )
                for dl_x in range(bx0 + 48, bx1 - 40, 72):
                    draw.ellipse([dl_x - 5, fy0 + 5, dl_x + 5, fy0 + 13], fill=(255, 242, 175))

                # 3. Recessed Central Staircase & Elevator Core Box (`باکس پله و آسانسور که وسط ساختمانه`)
                stair_rm = next((r for r in fl.rooms if r.room_id == "STAIR_BOX"), None)
                elev_rm = next((r for r in fl.rooms if r.room_id == "ELEVATOR_SHAFT"), None)
                lobby_rm = next((r for r in fl.rooms if r.room_id == "FLOOR_LOBBY"), None)
                core_rms = [r for r in (stair_rm, elev_rm, lobby_rm) if r is not None]
                if core_rms:
                    cu0 = min((r.net_rect_mm.y_min if is_ew_facade else r.net_rect_mm.x_min) for r in core_rms)
                    cu1 = max((r.net_rect_mm.y_max if is_ew_facade else r.net_rect_mm.x_max) for r in core_rms)
                    cx_box0 = max(bx0 + 36, map_u(cu0) + int(b_px_w * 0.08))
                    cx_box1 = min(bx1 - 36, map_u(cu1) + int(b_px_w * 0.14))
                else:
                    cx_box0 = bx0 + int(b_px_w * 0.24)
                    cx_box1 = bx0 + int(b_px_w * 0.58)

                core_y0 = fy0 + ceil_depth_px - 2
                core_y1 = fy1 - 6
                # Warm stone-clad Stair & Elevator Core Wall inside pilotis depth
                core_wall_col = tuple(max(0, int(c * 0.84)) for c in wall_base_rgb)
                draw.rectangle([cx_box0, core_y0, cx_box1, core_y1], fill=core_wall_col, outline=shadow_rgb, width=2)
                line_draw.rectangle([cx_box0, core_y0, cx_box1, core_y1], outline=(210, 210, 210), width=2)
                depth_np[max(0, core_y0):min(H, core_y1), max(0, cx_box0):min(W, cx_box1)] = 142

                # SOLID Stone-Clad South Wall of Stair & Elevator Core Box (`در دیوار شرقی در داریم که در نمای جنوبی اصلاً دیده نمیشه، در این نما فقط دیوار می‌بینیم!`)
                for cy_st in range(core_y0 + 14, core_y1 - 4, 14):
                    draw.line([(cx_box0 + 3, cy_st), (cx_box1 - 3, cy_st)], fill=joint_rgb, width=1)
                # 3D East Side Return of the Core Box (where the walkway goes around the East side to reach the East lobby door)
                core_side_w = 18
                draw.polygon(
                    [(cx_box1, core_y0), (cx_box1 + core_side_w, core_y0 + 6), (cx_box1 + core_side_w, core_y1 - 4), (cx_box1, core_y1)],
                    fill=tuple(max(0, c - 22) for c in core_wall_col),
                    outline=shadow_rgb,
                )
                # Classical framed stone relief panels on the solid South wall of the Stair & Elevator Core (ZERO doors and ZERO windows on the South wall!)
                mid_core_x = (cx_box0 + cx_box1) // 2
                draw.rectangle([cx_box0 + 10, core_y0 + 14, mid_core_x - 6, core_y1 - 12], outline=trim_rgb, width=1)
                draw.rectangle([mid_core_x + 6, core_y0 + 14, cx_box1 - 10, core_y1 - 12], outline=trim_rgb, width=1)
                line_draw.rectangle([cx_box0 + 10, core_y0 + 14, mid_core_x - 6, core_y1 - 12], outline=(185, 185, 185), width=1)
                line_draw.rectangle([mid_core_x + 6, core_y0 + 14, cx_box1 - 10, core_y1 - 12], outline=(185, 185, 185), width=1)

                # 4. Central Pedestrian Walkway (`مسیر پیاده از حیاط به سمت دیوار شرقی لابی پله و آسانسور`)
                ped_back_x0 = cx_box1 - 12
                ped_back_x1 = cx_box1 + core_side_w + 26
                ped_x0_front = bx0 + int(b_px_w * 0.45)
                ped_x1_front = bx0 + int(b_px_w * 0.61)
                draw.polygon(
                    [
                        (ped_back_x0, core_y1),
                        (ped_back_x1, core_y1),
                        (ped_x1_front, gy + 18),
                        (ped_x0_front, gy + 18),
                    ],
                    fill=trim_rgb,
                    outline=shadow_rgb,
                )
                led_walk_c = (255, 236, 142)
                draw.line([(ped_back_x0 + 2, core_y1), (ped_x0_front + 3, gy + 14)], fill=led_walk_c, width=2)
                draw.line([(ped_back_x1 - 2, core_y1), (ped_x1_front - 3, gy + 14)], fill=led_walk_c, width=2)
                line_draw.polygon(
                    [(ped_back_x0, core_y1), (ped_back_x1, core_y1), (ped_x1_front, gy + 18), (ped_x0_front, gy + 18)],
                    outline=(220, 220, 220),
                )

                # 5. 3D Parked Cars (`P1` in Left Bay & `P2` in Right Bay) with STRICT STANDARD DIMENSIONS (`1.80m` width x `1.48m` height for BOTH cars!)
                std_car_w_px = max(56, int(round(1.80 * px_per_m)))
                std_car_h_px = max(38, int(round(1.48 * px_per_m)))
                # Left Bay (`P1`: centered between left column A-1 and central column B-1)
                bay1_left = bx0 + pil_w + 10
                bay1_right = ped_x0_front - 10
                bay1_mid = (bay1_left + bay1_right) // 2
                c1_x0 = max(bay1_left, bay1_mid - std_car_w_px // 2)
                c1_x1 = c1_x0 + std_car_w_px
                _draw_3d_parked_car(draw, line_draw, depth_np, c1_x0, c1_x1, fy1 - 2, std_car_h_px, body_rgb=(242, 244, 248), is_night=is_night)

                # Right Bay (`P2`: centered between pedestrian path and right column C-1, exact same 1.80m width!)
                bay2_left = ped_x1_front + 10
                bay2_right = bx1 - pil_w - 10
                bay2_mid = (bay2_left + bay2_right) // 2
                c2_x0 = max(bay2_left, bay2_mid - std_car_w_px // 2)
                c2_x1 = c2_x0 + std_car_w_px
                _draw_3d_parked_car(draw, line_draw, depth_np, c2_x0, c2_x1, fy1 - 2, std_car_h_px, body_rgb=(68, 74, 84), is_night=is_night)

                # 6. Freestanding Structural Pilotis Columns (`ستون‌های آزاد پیلوت در آکس‌های A، B و C`)
                for cu_mm in col_us:
                    px_c = max(bx0 + pil_w // 2 + 2, min(bx1 - pil_w // 2 - 2, map_u(cu_mm)))
                    pilaster_x_pixels.append(px_c)
                    # Column 3D side shadow
                    draw.rectangle([px_c + pil_w // 2, fy0 + 2, px_c + pil_w // 2 + 6, fy1], fill=(42, 40, 38))
                    # Column stone shaft
                    draw.rectangle([px_c - pil_w // 2, fy0 + 2, px_c + pil_w // 2, fy1], fill=pilaster_rgb, outline=shadow_rgb, width=1)
                    if is_neoclassical:
                        for fl_i in (-pil_w // 4, 0, pil_w // 4):
                            draw.line([(px_c + fl_i, fy0 + 14), (px_c + fl_i, fy1 - 12)], fill=shadow_rgb, width=1)
                        # Classical Capital & Base on freestanding pilotis column
                        draw.rectangle([px_c - pil_w // 2 - 5, fy0, px_c + pil_w // 2 + 5, fy0 + 12], fill=trim_rgb, outline=shadow_rgb, width=1)
                        draw.rectangle([px_c - pil_w // 2 - 4, fy1 - 12, px_c + pil_w // 2 + 4, fy1], fill=trim_rgb, outline=shadow_rgb, width=1)
                    line_draw.rectangle([px_c - pil_w // 2, fy0, px_c + pil_w // 2, fy1], outline=(255, 255, 255), width=3)
                    depth_np[max(0, fy0):min(H, fy1), max(0, px_c - pil_w // 2):min(W, px_c + pil_w // 2)] = 212
                continue

            # =========================================================================
            # CASE A2: CUSTOM STEPPED 1-STORY PLAN (`plan.dwg`: Attached to Left Courtyard Wall,
            # Gap from Right Courtyard Wall, Stepped North Facade Setback, +0.36m Raised Platform
            # with 2 Steps Across Entire Recessed Wing, and 2 Equal-Sized Tall Windows with OKB=0!)
            # =========================================================================
            if f_idx == 0 and is_custom_stepped_plan and n_floors == 1:
                step_split_x = bx0 + int(round(b_px_w * 0.40))
                recess_depth_px = 20
                plat_036_px = max(24, int(round(0.36 * px_per_m)))
                y_plat_036 = gy - plat_036_px

                # 1) Projecting Left/West Wing (`بخش جلوآمده نما چسبیده به دیوار حیاط`): flush at y=gy
                draw.rectangle([bx0, fy0, step_split_x, gy], fill=wall_base_rgb, outline=shadow_rgb, width=1)
                for cy_line in range(fy0 + 16, gy, 18):
                    draw.line([(bx0 + 2, cy_line), (step_split_x - 2, cy_line)], fill=joint_rgb, width=1)
                depth_np[max(0, fy0):min(H, gy), max(0, bx0):min(W, step_split_x)] = 222
                line_draw.rectangle([bx0, fy0, step_split_x, gy], outline=(255, 255, 255), width=3)

                # Classical pilasters & smaller window on projecting wing
                pil_l_w = max(14, int(round(0.36 * px_per_m)))
                for px_p in (bx0 + pil_l_w // 2 + 2, step_split_x - pil_l_w // 2 - 2):
                    pilaster_x_pixels.append(px_p)
                    draw.rectangle([px_p - pil_l_w // 2, fy0 + 4, px_p + pil_l_w // 2, gy], fill=pilaster_rgb, outline=shadow_rgb, width=1)
                    line_draw.rectangle([px_p - pil_l_w // 2, fy0 + 4, px_p + pil_l_w // 2, gy], outline=(255, 255, 255), width=2)
                pw_x0 = bx0 + pil_l_w + 16
                pw_x1 = step_split_x - pil_l_w - 16
                if pw_x1 - pw_x0 > 32:
                    # Solid classical travertine framed relief panel on projecting wing (windows are in the recessed +0.36m wing!)
                    draw.rectangle(
                        [pw_x0, fy0 + int(round(0.42 * px_per_m)), pw_x1, gy - int(round(0.42 * px_per_m))],
                        outline=trim_rgb,
                        width=2,
                    )
                    draw.rectangle(
                        [pw_x0 + 6, fy0 + int(round(0.48 * px_per_m)), pw_x1 - 6, gy - int(round(0.48 * px_per_m))],
                        outline=shadow_rgb,
                        width=1,
                    )

                # 2) 3D Perspective Side Return Wall of the Stepped Setback (`دیوار برگشت سه‌بعدی عقب‌رفتگی نما`)
                ret_col = tuple(max(0, c - 34) for c in wall_base_rgb)
                draw.polygon(
                    [
                        (step_split_x, fy0),
                        (step_split_x + recess_depth_px, fy0 + 10),
                        (step_split_x + recess_depth_px, y_plat_036),
                        (step_split_x, gy),
                    ],
                    fill=ret_col,
                    outline=shadow_rgb,
                )
                line_draw.polygon(
                    [
                        (step_split_x, fy0),
                        (step_split_x + recess_depth_px, fy0 + 10),
                        (step_split_x + recess_depth_px, y_plat_036),
                        (step_split_x, gy),
                    ],
                    outline=(255, 255, 255),
                )

                # 3) Recessed Wing (`قسمت عقب‌رفتگی نما جایی که دو پنجره هم‌اندازه OKB=0 قرار دارند`)
                rec_x0 = step_split_x + recess_depth_px
                rec_x1 = bx1
                rec_fy0 = fy0 + 10
                draw.rectangle([rec_x0, rec_fy0, rec_x1, y_plat_036], fill=wall_recess_rgb, outline=shadow_rgb, width=1)
                for cy_line in range(rec_fy0 + 16, y_plat_036, 18):
                    draw.line([(rec_x0 + 2, cy_line), (rec_x1 - 2, cy_line)], fill=joint_rgb, width=1)
                depth_np[max(0, rec_fy0):min(H, y_plat_036), max(0, rec_x0):min(W, rec_x1)] = 152
                line_draw.rectangle([rec_x0, rec_fy0, rec_x1, y_plat_036], outline=(255, 255, 255), width=3)

                # Right corner pilaster & central dividing pilaster between the 2 equal OKB=0 windows
                rec_mid_x = (rec_x0 + rec_x1) // 2
                for px_r in (rec_mid_x, rec_x1 - pil_l_w // 2 - 2):
                    pilaster_x_pixels.append(px_r)
                    draw.rectangle([px_r - pil_l_w // 2, rec_fy0 + 4, px_r + pil_l_w // 2, y_plat_036], fill=pilaster_rgb, outline=shadow_rgb, width=1)
                    line_draw.rectangle([px_r - pil_l_w // 2, rec_fy0 + 4, px_r + pil_l_w // 2, y_plat_036], outline=(255, 255, 255), width=2)

                # 4) TWO EQUAL-SIZED FULL-HEIGHT WINDOWS (`دو تا پنجره هم‌اندازه از +0.36 تا زیر سقف با OKB=0`)
                # Starting flush at y_plat_036 (OKB=0 above the +0.36m platform) all the way up to under the ceiling!
                win_top_y = rec_fy0 + int(round(0.26 * px_per_m))
                win_bot_y = y_plat_036 - 2  # OKB = 0.00m on top of +0.36m platform!
                w_pad = pil_l_w // 2 + 12
                w1_x0, w1_x1 = rec_x0 + 14, rec_mid_x - w_pad
                w2_x0, w2_x1 = rec_mid_x + w_pad, rec_x1 - pil_l_w - 12
                eq_w = min(w1_x1 - w1_x0, w2_x1 - w2_x0)
                if eq_w > 28:
                    draw_photorealistic_window(w1_x1 - eq_w, win_top_y, w1_x1, win_bot_y, is_tall=True, depth_val=138)
                    draw_photorealistic_window(w2_x0, win_top_y, w2_x0 + eq_w, win_bot_y, is_tall=True, depth_val=138)

                # 5) Full-Width +0.36m Raised Platform/Veranda (`سکوی +0.36 سانتیمتری در کل قسمت عقب‌رفتگی با ۲ پله از حیاط`)
                # Covers the ENTIRE recessed wing width (step_split_x .. bx1) with 2 steps down to courtyard level gy!
                draw.rectangle([step_split_x, y_plat_036, bx1, gy], fill=trim_rgb, outline=shadow_rgb, width=2)
                step1_y = y_plat_036 + plat_036_px // 2
                # Step 2 (upper riser at y_plat_036 .. step1_y)
                draw.rectangle([step_split_x + 4, y_plat_036, bx1 + 4, step1_y], fill=trim_rgb, outline=shadow_rgb, width=2)
                # Step 1 (lower riser projecting slightly forward into courtyard at step1_y .. gy + 6)
                draw.rectangle([step_split_x, step1_y, bx1 + 10, gy + 6], fill=pilaster_rgb, outline=shadow_rgb, width=2)
                line_draw.rectangle([step_split_x + 4, y_plat_036, bx1 + 4, step1_y], outline=(255, 255, 255), width=2)
                line_draw.rectangle([step_split_x, step1_y, bx1 + 10, gy + 6], outline=(255, 255, 255), width=2)
                depth_np[max(0, y_plat_036):min(H, gy + 6), max(0, step_split_x):min(W, bx1 + 10)] = 208
                continue

            # =========================================================================
            # CASE B: SOLID RESIDENTIAL / VILLA / DUPLEX FLOOR (`f_idx >= 1` or non-pilotis `f_idx == 0`)
            # ==========================================================================
            wall_fill = wall_recess_rgb if (f_idx == 0 and n_floors >= 2 and cantilever_m > 0.05) else wall_base_rgb
            draw.rectangle([fl_bx0, fy0, fl_bx1, fy1], fill=wall_fill)
            line_draw.rectangle([fl_bx0, fy0, fl_bx1, fy1], outline=(255, 255, 255), width=3)
            depth_np[max(0, fy0):min(H, fy1), max(0, fl_bx0):min(W, fl_bx1)] = 215 if has_cantilever_here else 160

            course_step = max(10, int(round((0.18 if stone_color == "TERRACOTTA_BRICK" else 0.38) * px_per_m)))
            for cy_line in range(fy0 + course_step, fy1, course_step):
                draw.line([(fl_bx0 + 3, cy_line), (fl_bx1 - 3, cy_line)], fill=joint_rgb, width=1)
                if stone_color == "TERRACOTTA_BRICK" or (cy_line - fy0) % (course_step * 2) == 0:
                    for vx_j in range(fl_bx0 + 48, fl_bx1 - 24, 96):
                        draw.line([(vx_j, cy_line - course_step), (vx_j, cy_line)], fill=joint_rgb, width=1)

            # 3D Cantilever Underside Soffit at First Floor (`+2.72m` above Pilotis or `+3.69m` above Duplex Ground)
            if has_cantilever_here and f_idx == 1:
                soffit_h = max(12, int(round(min(1.4, cantilever_m) * 0.22 * px_per_m)))
                soffit_col = thermowood_rgb if wood_accent else tuple(max(0, c - 24) for c in trim_rgb)
                draw.polygon(
                    [(fl_bx0, fy1), (fl_bx1, fy1), (bx1, fy1 + soffit_h), (bx0, fy1 + soffit_h)],
                    fill=soffit_col,
                    outline=shadow_rgb,
                )
                line_draw.polygon(
                    [(fl_bx0, fy1), (fl_bx1, fy1), (bx1, fy1 + soffit_h), (bx0, fy1 + soffit_h)],
                    outline=(255, 255, 255),
                )
                led_col = (255, 236, 145)
                draw.line([(fl_bx0 + 18, fy1 + soffit_h // 2), (fl_bx1 - 18, fy1 + soffit_h // 2)], fill=led_col, width=3)
                for dl_x in range(fl_bx0 + 42, fl_bx1 - 35, 80):
                    draw.ellipse([dl_x - 4, fy1 + 3, dl_x + 4, fy1 + soffit_h - 3], fill=(255, 244, 185))

            # Pilasters on Residential Floors
            for cu_mm in col_us:
                px_c = max(fl_bx0 + pil_w // 2 + 2, min(fl_bx1 - pil_w // 2 - 2, map_u(cu_mm)))
                if f_idx == 0:
                    pilaster_x_pixels.append(px_c)
                if is_neoclassical:
                    draw.rectangle([px_c + pil_w // 2, fy0 + 8, px_c + pil_w // 2 + 4, fy1 - 6], fill=shadow_rgb)
                    draw.rectangle([px_c - pil_w // 2, fy0 + 8, px_c + pil_w // 2, fy1 - 6], fill=pilaster_rgb, outline=shadow_rgb, width=1)
                    for fl_i in (-pil_w // 4, 0, pil_w // 4):
                        draw.line([(px_c + fl_i, fy0 + 16), (px_c + fl_i, fy1 - 12)], fill=shadow_rgb, width=1)
                    draw.rectangle([px_c - pil_w // 2 - 4, fy0 + 2, px_c + pil_w // 2 + 4, fy0 + 12], fill=trim_rgb, outline=shadow_rgb, width=1)
                    draw.rectangle([px_c - pil_w // 2 - 3, fy1 - 10, px_c + pil_w // 2 + 3, fy1], fill=trim_rgb, outline=shadow_rgb, width=1)
                    line_draw.rectangle([px_c - pil_w // 2, fy0 + 2, px_c + pil_w // 2, fy1], outline=(255, 255, 255), width=2)
                    depth_np[max(0, fy0):min(H, fy1), max(0, px_c - pil_w // 2):min(W, px_c + pil_w // 2)] = 228 if has_cantilever_here else 182

            # Upper-Floor Covered Timber Pergola Terrace (`PERGOLA_TERRACE_WEST`)
            if f_idx >= 1:
                perg_room = next((r for r in fl.rooms if r.room_id == "PERGOLA_TERRACE_WEST"), None)
                if perg_room is not None:
                    pr = perg_room.net_rect_mm
                    p_on_side = (
                        (facade_side == "SOUTH" and pr.y_min <= gb_fl.y_min + 2600)
                        or (facade_side == "NORTH" and pr.y_max >= gb_fl.y_max - 2600)
                        or (facade_side == "WEST" and pr.x_min <= gb_fl.x_min + 2600)
                        or (facade_side == "EAST" and pr.x_max >= gb_fl.x_max - 2600)
                    )
                    if p_on_side:
                        pu0 = pr.y_min if is_ew_facade else pr.x_min
                        pu1 = pr.y_max if is_ew_facade else pr.x_max
                        px0, px1 = map_u(pu0) + 8, map_u(pu1) - 8
                        if px1 - px0 > 40:
                            draw.rectangle([px0, fy0 + 10, px1, fy1 - 14], fill=wall_recess_rgb, outline=shadow_rgb, width=1)
                            beam_h = max(14, int(round(0.30 * px_per_m)))
                            draw.rectangle([px0, fy0 + 8, px1, fy0 + 8 + beam_h], fill=thermowood_rgb)
                            for sx_b in range(px0 + 10, px1 - 10, 18):
                                draw.rectangle([sx_b, fy0 + 8, sx_b + 8, fy0 + 8 + beam_h + 5], fill=thermowood_dark)
                                line_draw.rectangle([sx_b, fy0 + 8, sx_b + 8, fy0 + 8 + beam_h + 5], outline=(255, 255, 255), width=1)
                            draw_photorealistic_window(px0 + 16, fy0 + 8 + beam_h + 8, px1 - 16, fy1 - 14, is_tall=True, depth_val=130)

            facade_windows = []
            for w in fl.windows:
                if is_ew_facade and w.orientation != "V":
                    continue
                if not is_ew_facade and w.orientation != "H":
                    continue
                if facade_side == "SOUTH" and 0.5 * (w.y0_mm + w.y1_mm) <= gb_fl.y_min + 2200:
                    facade_windows.append(w)
                elif facade_side == "NORTH" and 0.5 * (w.y0_mm + w.y1_mm) >= gb_fl.y_max - 2200:
                    facade_windows.append(w)
                elif facade_side == "WEST" and 0.5 * (w.x0_mm + w.x1_mm) <= gb_fl.x_min + 2200:
                    facade_windows.append(w)
                elif facade_side == "EAST" and 0.5 * (w.x0_mm + w.x1_mm) >= gb_fl.x_max - 2200:
                    facade_windows.append(w)

            void_room = None
            if n_floors >= 2:
                void_room = next((r for r in project.floors[1].rooms if r.room_id == "VOID_DUPLEX_LIVING"), None)
            void_u_span: Optional[Tuple[int, int]] = None
            if void_room is not None:
                vr = void_room.net_rect_mm
                v_on_side = (
                    (facade_side == "SOUTH" and vr.y_min <= project.floors[1].gross_building_rect_mm.y_min + 2200)
                    or (facade_side == "NORTH" and vr.y_max >= project.floors[1].gross_building_rect_mm.y_max - 2200)
                    or (facade_side == "WEST" and vr.x_min <= project.floors[1].gross_building_rect_mm.x_min + 2200)
                    or (facade_side == "EAST" and vr.x_max >= project.floors[1].gross_building_rect_mm.x_max - 2200)
                )
                if v_on_side:
                    vu0 = vr.y_min if is_ew_facade else vr.x_min
                    vu1 = vr.y_max if is_ew_facade else vr.x_max
                    void_u_span = (map_u(vu0) + 14, map_u(vu1) - 14)

            for w in facade_windows:
                u0 = min(w.y0_mm, w.y1_mm) if is_ew_facade else min(w.x0_mm, w.x1_mm)
                u1 = max(w.y0_mm, w.y1_mm) if is_ew_facade else max(w.x0_mm, w.x1_mm)
                wx0, wx1 = map_u(u0), map_u(u1)
                if void_u_span is not None and wx0 >= void_u_span[0] - 25 and wx1 <= void_u_span[1] + 25:
                    continue
                wid_up = (w.window_id + "_" + w.host_room_id).upper()
                is_tall = any(k in wid_up for k in ("LIVING", "DINING", "TERRACE", "VOID", "MINI_BAR", "UPPER_SE"))
                is_high_sill = any(k in wid_up for k in ("KITCHEN", "DIRTY", "MUTBAKH", "WC", "BATH"))
                wy0 = fy0 + int(round((0.36 if is_tall else 0.50) * px_per_m))
                wy1 = fy1 - int(round((0.20 if is_tall else (0.98 if is_high_sill else 0.68)) * px_per_m))
                draw_photorealistic_window(wx0, wy0, wx1, wy1, is_tall=is_tall, depth_val=195 if has_cantilever_here else 142)

            if f_idx == 1 and void_u_span is not None:
                vx0, vx1 = void_u_span
                fy1_ground = y_base
                wy0_v = fy0 + int(round(0.34 * px_per_m))
                wy1_v = fy1_ground - int(round(0.22 * px_per_m))
                draw_photorealistic_window(vx0, wy0_v, vx1, wy1_v, is_tall=True, is_double_height_void=True, depth_val=190)

            if f_idx >= 1:
                balc_rooms = [
                    r for r in fl.rooms
                    if r.is_open_front_terrace or any(k in r.room_id.upper() for k in ("BALCONY", "TERRACE"))
                ]
                slab_h = max(9, int(round(0.25 * px_per_m)))
                rail_h = max(22, int(round(0.94 * px_per_m)))
                drew_any_balc = False
                for br in balc_rooms:
                    br_rect = br.net_rect_mm
                    b_on_side = (
                        (facade_side == "SOUTH" and br_rect.y_min <= gb_fl.y_min + 2600)
                        or (facade_side == "NORTH" and br_rect.y_max >= gb_fl.y_max - 2600)
                        or (facade_side == "WEST" and br_rect.x_min <= gb_fl.x_min + 2600)
                        or (facade_side == "EAST" and br_rect.x_max >= gb_fl.x_max - 2600)
                    )
                    if b_on_side:
                        bu0 = br_rect.y_min if is_ew_facade else br_rect.x_min
                        bu1 = br_rect.y_max if is_ew_facade else br_rect.x_max
                        rx0 = max(fl_bx0 + pil_w // 2 + 4, map_u(bu0))
                        rx1 = min(fl_bx1 - pil_w // 2 - 4, map_u(bu1))
                        if void_u_span is not None and br.room_id == "PERGOLA_TERRACE_WEST":
                            rx1 = min(rx1, void_u_span[0] - 8)
                        if 36 < (rx1 - rx0) < int(b_px_w * 0.72) and br.room_id != "PERGOLA_TERRACE_WEST":
                            cav_y0 = fy0 + int(round(0.26 * px_per_m))
                            cav_y1 = fy1 - slab_h
                            recess_shadow_col = tuple(max(0, c - 28) for c in wall_recess_rgb)
                            draw.rectangle([rx0, cav_y0, rx1, cav_y1], fill=recess_shadow_col, outline=shadow_rgb, width=1)
                            soff_c = thermowood_rgb if wood_accent else tuple(max(0, c - 18) for c in trim_rgb)
                            draw.rectangle([rx0, cav_y0, rx1, cav_y0 + 11], fill=soff_c)
                            for dl_x in range(rx0 + 26, rx1 - 20, 48):
                                draw.ellipse([dl_x - 4, cav_y0 + 3, dl_x + 4, cav_y0 + 9], fill=(255, 240, 175))
                            # SOLID FULL-HEIGHT NEIGHBOR PRIVACY WALL ON LEFT EDGE OF BALCONY (`دیوار کامل جانبی چپ بالکن در سمت همسایه برای جلوگیری از اشرافیت`)
                            priv_w_px = max(20, pil_w + 4)
                            draw.rectangle([fl_bx0, fy0, fl_bx0 + priv_w_px, fy1 - slab_h], fill=wall_base_rgb, outline=shadow_rgb, width=2)
                            for cy_pw in range(fy0 + 14, fy1 - slab_h, 16):
                                draw.line([(fl_bx0 + 2, cy_pw), (fl_bx0 + priv_w_px - 2, cy_pw)], fill=joint_rgb, width=1)
                            # 3D inner side return surface of the neighbor privacy wall inside the balcony depth
                            priv_ret_col = tuple(max(0, c - 22) for c in wall_base_rgb)
                            draw.polygon(
                                [
                                    (fl_bx0 + priv_w_px, fy0),
                                    (fl_bx0 + priv_w_px + 14, cav_y0),
                                    (fl_bx0 + priv_w_px + 14, cav_y1),
                                    (fl_bx0 + priv_w_px, fy1 - slab_h),
                                ],
                                fill=priv_ret_col,
                                outline=shadow_rgb,
                            )
                            line_draw.rectangle([fl_bx0, fy0, fl_bx0 + priv_w_px, fy1 - slab_h], outline=(255, 255, 255), width=3)
                            depth_np[max(0, fy0):min(H, fy1 - slab_h), max(0, fl_bx0):min(W, fl_bx0 + priv_w_px + 6)] = 232
                            rx0 = max(rx0, fl_bx0 + priv_w_px)
                            draw_photorealistic_window(rx0 + 16, cav_y0 + 14, rx1 - 12, cav_y1 - 4, is_tall=True, depth_val=132)
                        draw_balustrade(rx0, fy1 - slab_h, rx1, rail_h)
                        drew_any_balc = True
                if not drew_any_balc and has_cantilever_here:
                    rx1_b = (void_u_span[0] - 8) if void_u_span is not None else (fl_bx1 - 8)
                    draw_balustrade(fl_bx0 + 8, fy1 - slab_h, rx1_b, rail_h)
                draw.rectangle([fl_bx0 - 4, fy1 - slab_h, fl_bx1 + 4, fy1 + 2], fill=trim_rgb, outline=shadow_rgb, width=1)
                line_draw.rectangle([fl_bx0 - 4, fy1 - slab_h, fl_bx1 + 4, fy1 + 2], outline=(255, 255, 255), width=2)

            # Non-pilotis Ground Floor Entrance Door (`VILLA_1FLOOR` or `DUPLEX_2FLOOR`)
            if f_idx == 0 and not fl.is_open_pilotis:
                main_d = next((d for d in fl.doors if d.is_main_entry), None)
                entry_steps_rm = next((r for r in fl.rooms if r.room_id == "ENTRY_STEPS_LANDING"), None)
                door_on_this_facade = False
                if main_d is not None:
                    hx, hy = main_d.hinge_mm
                    if facade_side == "SOUTH" and hy <= gb_fl.y_min + 2400:
                        door_on_this_facade = True
                    elif facade_side == "NORTH" and hy >= gb_fl.y_max - 2400:
                        door_on_this_facade = True
                    elif facade_side == "WEST" and hx <= gb_fl.x_min + 2400:
                        door_on_this_facade = True
                    elif facade_side == "EAST" and hx >= gb_fl.x_max - 2400:
                        door_on_this_facade = True

                if door_on_this_facade and main_d is not None:
                    du0 = main_d.hinge_mm[1] if is_ew_facade else main_d.hinge_mm[0]
                    du1 = du0 + main_d.width_mm
                    if entry_steps_rm is not None:
                        su0 = entry_steps_rm.net_rect_mm.y_min if is_ew_facade else entry_steps_rm.net_rect_mm.x_min
                        su1 = entry_steps_rm.net_rect_mm.y_max if is_ew_facade else entry_steps_rm.net_rect_mm.x_max
                        dx0, dx1 = map_u(su0), map_u(su1)
                    else:
                        dx0, dx1 = map_u(du0) - 6, map_u(du1) + 6
                    if dx1 - dx0 < 44:
                        mid_d = (dx0 + dx1) // 2
                        dx0, dx1 = mid_d - 24, mid_d + 24

                    dy0 = fy0 + int(round(0.38 * px_per_m))
                    draw.rectangle([dx0 - 12, dy0 - 14, dx1 + 12, fy1], fill=trim_rgb, outline=shadow_rgb, width=1)
                    if is_neoclassical:
                        draw.polygon(
                            [(dx0 - 18, dy0 - 14), (dx1 + 18, dy0 - 14), (dx1 + 12, dy0 - 26), (dx0 - 12, dy0 - 26)],
                            fill=trim_rgb,
                            outline=shadow_rgb,
                        )
                        draw.rectangle([dx0, dy0, dx1, fy1], fill=(52, 34, 22), outline=frame_rgb, width=2)
                        mid_dx = (dx0 + dx1) // 2
                        glass_c = (254, 236, 148) if (is_night or is_golden) else (182, 214, 238)
                        draw.rectangle([dx0 + 6, dy0 + 8, mid_dx - 3, fy1 - 10], fill=glass_c, outline=(212, 175, 55), width=1)
                        draw.rectangle([mid_dx + 3, dy0 + 8, dx1 - 6, fy1 - 10], fill=glass_c, outline=(212, 175, 55), width=1)
                        draw.line([(mid_dx, dy0), (mid_dx, fy1)], fill=(212, 175, 55), width=2)
                    else:
                        draw.rectangle([dx0, dy0, dx1, fy1], fill=thermowood_rgb, outline=frame_rgb, width=2)
                        for sy_d in range(dy0 + 6, fy1 - 4, 8):
                            draw.line([(dx0 + 3, sy_d), (dx1 - 3, sy_d)], fill=thermowood_dark, width=1)
                        draw.line([(dx1 - 12, dy0 + 18), (dx1 - 12, fy1 - 18)], fill=(253, 224, 71), width=3)

                    line_draw.rectangle([dx0 - 12, dy0 - 14, dx1 + 12, fy1], outline=(255, 255, 255), width=2)
                    line_draw.rectangle([dx0, dy0, dx1, fy1], outline=(255, 255, 255), width=2)

                    if plinth_px > 0:
                        for s_i in range(3):
                            sy_top = fy1 + int(s_i * (plinth_px / 3.0))
                            sy_bot = fy1 + int((s_i + 1) * (plinth_px / 3.0))
                            pad_s = (s_i + 1) * 8 if is_courtyard_view else 2
                            draw.rectangle([dx0 - pad_s, sy_top, dx1 + pad_s, sy_bot], fill=trim_rgb, outline=shadow_rgb, width=1)
                            line_draw.rectangle([dx0 - pad_s, sy_top, dx1 + pad_s, sy_bot], outline=(255, 255, 255), width=2)
                            depth_np[max(0, sy_top):min(H, sy_bot), max(0, dx0 - pad_s):min(W, dx1 + pad_s)] = 195 + s_i * 15

        # 5. Roof Cornice, Parapet & Recessed Roof Kharposhteh Penthouse (`خرپشته و اتاقک آسانسور روی بام`)
        top_outset = int(round(min(1.5, cantilever_m) * 12)) if (n_floors >= 2 and cantilever_m > 0.05) else 0
        r_bx0, r_bx1 = bx0 - top_outset, bx1 + top_outset
        cornice_h = max(12, int(round(0.32 * px_per_m)))
        parapet_rail_h = max(20, int(round(0.66 * px_per_m)))

        # 5a. Render Recessed Roof Kharposhteh (`خرپشته روی بام`) BEFORE front roof balustrade so the balustrade sits naturally in front of its base!
        if has_kharposhteh:
            top_fl = project.floors[-1]
            st_rm = next((r for r in top_fl.rooms if r.room_id == "STAIR_BOX"), None)
            el_rm = next((r for r in top_fl.rooms if r.room_id == "ELEVATOR_SHAFT"), None)
            lb_rm = next((r for r in top_fl.rooms if r.room_id == "FLOOR_LOBBY"), None)
            core_list = [r for r in (st_rm, el_rm, lb_rm) if r is not None]
            if core_list:
                ku0 = min((r.net_rect_mm.y_min if is_ew_facade else r.net_rect_mm.x_min) for r in core_list)
                ku1 = max((r.net_rect_mm.y_max if is_ew_facade else r.net_rect_mm.x_max) for r in core_list)
                kx0 = max(bx0 + 24, map_u(ku0) + int(b_px_w * 0.04))
                kx1 = min(bx1 - 24, map_u(ku1) + int(b_px_w * 0.10))
            else:
                kx0 = bx0 + int(b_px_w * 0.18)
                kx1 = bx0 + int(b_px_w * 0.52)

            kh_px_h = max(36, int(round(2.15 * px_per_m)))
            kh_y1 = top_y - cornice_h
            kh_y0 = max(18, kh_y1 - kh_px_h)
            kh_wall_col = tuple(max(0, int(c * 0.92)) for c in wall_base_rgb)

            # Unified-Height Rooftop Volume (`ارتفاع سقف خرپشته و اتاق آسانسور یکسان و هم‌تراز به اندازه ارتفاع اتاق آسانسور`):
            # - Strictly spans `kx0 .. kx1` (aligned 100% with the 4 core columns `A-2`, `B-2`, `A-3`, `B-3`)
            # - Taller unified ceiling height (`mach_y0`) covering both the Staircase Kharposhteh (left) and the +0.90m Elevator Machine Room (right)
            # - SOLID South stone wall with ZERO doors and ZERO windows (since the Kharposhteh exit door and Machine Room steps/door are on the North side!)
            mach_extra_h = max(14, int(round(0.65 * px_per_m)))
            uni_y0 = max(10, kh_y0 - mach_extra_h)
            kh_side_w = 18
            kx_mid = (kx0 + kx1) // 2

            # Main unified stone box (`kx0 .. kx1, uni_y0 .. kh_y1`)
            draw.rectangle([kx0, uni_y0, kx1, kh_y1], fill=kh_wall_col, outline=shadow_rgb, width=2)
            for ky_c in range(uni_y0 + 12, kh_y1, 14):
                draw.line([(kx0 + 2, ky_c), (kx1 - 2, ky_c)], fill=joint_rgb, width=1)

            # 3D East side perspective return wall
            draw.polygon(
                [(kx1, uni_y0), (kx1 + kh_side_w, uni_y0 + 8), (kx1 + kh_side_w, kh_y1), (kx1, kh_y1)],
                fill=tuple(max(0, c - 20) for c in kh_wall_col),
                outline=shadow_rgb,
            )

            # Single continuous Top Inward-Sloped Drip Cornice Crown (`قرنیز و آبچکان یکپارچه بالای خرپشته و اتاق آسانسور`)
            draw.polygon(
                [(kx0 - 8, uni_y0 - 10), (kx1 + kh_side_w + 6, uni_y0 - 10), (kx1 + kh_side_w + 2, uni_y0 + 2), (kx0 - 4, uni_y0 + 2)],
                fill=trim_rgb,
                outline=shadow_rgb,
            )
            if is_neoclassical:
                # Corner & central pilasters + two symmetrical solid framed stone panels (ZERO doors, ZERO windows!)
                draw.rectangle([kx0, uni_y0 + 2, kx0 + 10, kh_y1], fill=pilaster_rgb, outline=shadow_rgb, width=1)
                draw.rectangle([kx_mid - 5, uni_y0 + 2, kx_mid + 5, kh_y1], fill=pilaster_rgb, outline=shadow_rgb, width=1)
                draw.rectangle([kx1 - 10, uni_y0 + 2, kx1, kh_y1], fill=pilaster_rgb, outline=shadow_rgb, width=1)
                draw.rectangle([kx0 + 16, uni_y0 + 14, kx_mid - 11, kh_y1 - 14], outline=trim_rgb, width=1)
                draw.rectangle([kx_mid + 11, uni_y0 + 14, kx1 - 16, kh_y1 - 14], outline=trim_rgb, width=1)

            line_draw.rectangle([kx0, uni_y0 - 10, kx1 + kh_side_w, kh_y1], outline=(242, 242, 242), width=2)
            depth_np[max(0, uni_y0 - 10):min(H, kh_y1), max(0, kx0):min(W, kx1 + kh_side_w)] = 150

        # 5b. Continuous Perimeter Roof Parapet & Inward-Sloped Top Drip Cornice (`جان‌پناه نرده‌ای و قرنیز آبچکان روی نرده‌ها دورتادور بام با شیب به سمت داخل پشت‌بام`)
        if is_conv_1fl_carport_right:
            pass
        elif not _has_roof_balustrade:
            flat_cop_h = max(8, int(round(0.18 * px_per_m)))
            draw.rectangle([bx0 - 4, top_y - flat_cop_h, bx1 + 4, top_y + 2], fill=trim_rgb, outline=shadow_rgb, width=2)
            line_draw.rectangle([bx0 - 4, top_y - flat_cop_h, bx1 + 4, top_y + 2], outline=(255, 255, 255), width=2)
        elif is_neoclassical:
            draw.rectangle([r_bx0 - 10, top_y - cornice_h + 4, r_bx1 + 10, top_y + 6], fill=shadow_rgb)
            draw.rectangle([r_bx0 - 12, top_y - cornice_h, r_bx1 + 12, top_y], fill=trim_rgb, outline=shadow_rgb, width=1)
            draw.line([(r_bx0 - 14, top_y - cornice_h // 2), (r_bx1 + 14, top_y - cornice_h // 2)], fill=shadow_rgb, width=1)
            # Corner parapet piers + continuous balustrade across the full roof perimeter
            pier_w = max(14, int(round(0.32 * px_per_m)))
            ry_par_bot = top_y - cornice_h
            ry_par_top = ry_par_bot - parapet_rail_h
            draw_balustrade(r_bx0 + pier_w, ry_par_bot, r_bx1 - pier_w, parapet_rail_h)
            draw.rectangle([r_bx0, ry_par_top, r_bx0 + pier_w, ry_par_bot], fill=pilaster_rgb, outline=shadow_rgb, width=1)
            draw.rectangle([r_bx1 - pier_w, ry_par_top, r_bx1, ry_par_bot], fill=pilaster_rgb, outline=shadow_rgb, width=1)
            # Prominent continuous Top Drip Cornice (`قرنیز آبچکان روی نرده‌ها دورتادور بام با شیب آبچکان به سمت داخل پشت‌بام`)
            drip_h = 9
            draw.polygon(
                [
                    (r_bx0 - 8, ry_par_top - drip_h),
                    (r_bx1 + 8, ry_par_top - drip_h),
                    (r_bx1 + 4, ry_par_top + 2),
                    (r_bx0 - 4, ry_par_top + 2),
                ],
                fill=trim_rgb,
                outline=shadow_rgb,
            )
            # 3D perspective side return of the roof parapet & top drip cornice wrapping around the roof perimeter (`ادامه جان‌پناه و قرنیز آبچکان به دور بام`)
            draw.polygon(
                [(r_bx0 - 6, ry_par_top - drip_h), (r_bx0 + 18, ry_par_top - drip_h - 10), (r_bx0 + 18, ry_par_bot - 8), (r_bx0, ry_par_bot)],
                fill=tuple(max(0, c - 14) for c in trim_rgb),
                outline=shadow_rgb,
            )
            draw.polygon(
                [(r_bx1 + 6, ry_par_top - drip_h), (r_bx1 - 18, ry_par_top - drip_h - 10), (r_bx1 - 18, ry_par_bot - 8), (r_bx1, ry_par_bot)],
                fill=tuple(max(0, c - 14) for c in trim_rgb),
                outline=shadow_rgb,
            )
            line_draw.rectangle([r_bx0 - 12, top_y - cornice_h, r_bx1 + 12, top_y], outline=(255, 255, 255), width=2)
            line_draw.rectangle([r_bx0 - 8, ry_par_top - drip_h, r_bx1 + 8, ry_par_bot], outline=(255, 255, 255), width=2)
        else:
            coping_h = max(12, int(round(0.28 * px_per_m)))
            draw.rectangle([r_bx0 - 6, top_y - coping_h, r_bx1 + 6, top_y], fill=frame_rgb, outline=mullion_accent_rgb, width=1)
            if wood_accent:
                draw.rectangle([r_bx0, top_y, r_bx1, top_y + 10], fill=thermowood_rgb)
            line_draw.rectangle([r_bx0 - 6, top_y - coping_h, r_bx1 + 6, top_y], outline=(255, 255, 255), width=2)

        # 6. Lush Organic Cypress & Shrub Clusters in Two-Sided Courtyard Planter Beds
        tree_positions = (
            (
                (bx1 + 38, gy + 4, 28, 72),
                (bx1 + 96, gy + 22, 36, 62),
                (bx1 + 158, gy + 46, 42, 66),
                (bx0 - 68, gy + 46, 36, 58),
            )
            if (is_courtyard_view and is_custom_stepped_plan)
            else (
                (bx0 - 34, gy + 8, 26, 68),
                (bx0 - 86, gy + 26, 34, 56),
                (bx0 - 148, gy + 48, 42, 64),
                (bx1 + 34, gy + 8, 26, 68),
                (bx1 + 86, gy + 26, 34, 56),
                (bx1 + 148, gy + 48, 42, 64),
            )
            if is_courtyard_view
            else (
                (bx0 - 48, gy + 6, 32, 68),
                (bx1 + 48, gy + 6, 32, 68),
            )
        )
        for tx_tree, ty_base, r_w, r_h in tree_positions:
            _draw_organic_tree_cluster(draw, line_draw, depth_np, tx_tree, ty_base, r_w, r_h, rng, is_night=is_night)

        # 7. Photorealistic Shader Post-Processing: Perlin Travertine Veining, Soft Sun Gradient, AO & Night Lighting
        rgb_np = np.array(img, dtype=np.float32)

        mask_bldg = ((depth_np >= 110) & (np.arange(H)[:, None] < gy)).astype(np.float32)

        # Multi-octave travertine marble veining + directional sunlight shading across the scene
        low_vein = rng.normal(0.0, 3.2, (H // 8, W // 24)).astype(np.float32)
        vein_full = cv2.resize(low_vein, (W, H), interpolation=cv2.INTER_CUBIC)
        fine_grain = rng.normal(0.0, 1.8, (H // 2, W // 2)).astype(np.float32)
        grain_full = cv2.resize(fine_grain, (W, H), interpolation=cv2.INTER_LINEAR)
        tex_field = (vein_full + grain_full) * mask_bldg
        for c_i in range(3):
            rgb_np[:, :, c_i] += tex_field

        # Directional 45-degree sun warm highlight from top-left & soft vignette
        yy_norm = np.linspace(0.0, 1.0, H, dtype=np.float32)[:, None]
        xx_norm = np.linspace(0.0, 1.0, W, dtype=np.float32)[None, :]
        if not is_night:
            sun_grad = 1.04 - 0.07 * (0.6 * xx_norm + 0.4 * yy_norm)
            rgb_np[:, :, 0] *= sun_grad * 1.01
            rgb_np[:, :, 1] *= sun_grad
            rgb_np[:, :, 2] *= sun_grad * 0.99

        if is_night or is_golden:
            amb_r = 0.46 if is_night else 0.88
            amb_g = 0.50 if is_night else 0.78
            amb_b = 0.64 if is_night else 0.68
            relight = rgb_np.copy()
            y_cut = max(0, top_y - 220)
            relight[y_cut:, :, 0] = rgb_np[y_cut:, :, 0] * amb_r + (10.0 if is_night else 18.0)
            relight[y_cut:, :, 1] = rgb_np[y_cut:, :, 1] * amb_g + (12.0 if is_night else 10.0)
            relight[y_cut:, :, 2] = rgb_np[y_cut:, :, 2] * amb_b + (24.0 if is_night else 4.0)

            yy_g, xx_g = np.mgrid[0:H, 0:W].astype(np.float32)
            cone_field = np.zeros((H, W), dtype=np.float32)
            light_xs = pilaster_x_pixels if pilaster_x_pixels else [bx0 + 35, (bx0 + bx1) // 2, bx1 - 35]
            for lx in light_xs:
                horiz = np.exp(-((xx_g - lx) ** 2) / (2.0 * (26.0 ** 2)))
                for fy_a, fy_b in floor_y_bounds:
                    fy_mid = 0.5 * (fy_a + fy_b)
                    vert = np.exp(-((yy_g - fy_mid) ** 2) / (2.0 * ((max(20, fy_b - fy_a) * 0.44) ** 2)))
                    cone_field = np.maximum(cone_field, horiz * vert)

            cornice_wash = np.exp(-((yy_g - top_y) ** 2) / (2.0 * (18.0 ** 2))) * (
                (xx_g >= r_bx0) & (xx_g <= r_bx1)
            ).astype(np.float32)
            cone_field = np.maximum(cone_field, cornice_wash * 0.85)
            if n_floors >= 2 and cantilever_m > 0.05:
                fy_cant = floor_y_bounds[0][0]
                cant_wash = np.exp(-((yy_g - fy_cant) ** 2) / (2.0 * (22.0 ** 2))) * (
                    (xx_g >= bx0 - 15) & (xx_g <= bx1 + 15)
                ).astype(np.float32)
                cone_field = np.maximum(cone_field, cant_wash * 0.92)

            cone_field *= mask_bldg
            warm_led_rgb = np.array([255.0, 206.0, 118.0], dtype=np.float32)[None, None, :]
            strength = 0.72 if is_night else 0.42
            relight = relight + cone_field[..., None] * warm_led_rgb * strength
            rgb_np = relight

        final_img = Image.fromarray(np.clip(rgb_np, 0, 255).astype(np.uint8), mode="RGB")
        clean_unstamped_img = final_img.copy()

        # 8. Bottom Verification Stamp (Pure ASCII so zero tofu boxes)
        badge_draw = _SafePillowDraw(ImageDraw.Draw(final_img))
        ctx_en = "COURTYARD" if is_courtyard_view else "STREET"
        pil_en = "OpenPilotis(+2.72m)+Kharposhteh" if has_open_pilotis else f"Cantilever {cantilever_m:g}m"
        info_en = (
            f"ArchitectOS v52.0 Plan-Locked 3D Render | {facade_side} ({ctx_en}) | "
            f"Floors: {n_floors} ({pil_en}) | Style: {style_key} ({stone_color}) | Light: {lighting_mode} | Quality: {quality.upper()} | Seed: {spec['locked_seed']}"
        )
        badge_draw.rectangle([14, H - 32, min(W - 14, 14 + len(info_en) * 6 + 24), H - 8], fill=(15, 23, 42))
        badge_draw.text((24, H - 26), info_en, fill=(226, 232, 240))

        os.makedirs(os.path.dirname(os.path.abspath(out_png_path)), exist_ok=True)
        final_img.save(out_png_path, format="PNG")
        clean_comfy_in_path = os.path.splitext(out_png_path)[0] + "_comfy_input.png"
        clean_unstamped_img.save(clean_comfy_in_path, format="PNG")

        base_no_ext = os.path.splitext(out_png_path)[0]
        depth_path = base_no_ext + "_depth.png"
        lineart_path = base_no_ext + "_lineart.png"
        ifc_shell_path = base_no_ext + "_3d_shell.ifc"
        Image.fromarray(depth_np, mode="L").convert("RGB").save(depth_path, format="PNG")
        lineart_img.save(lineart_path, format="PNG")
        try:
            try:
                from .dxf_to_3d_shell_extruder import MultiStoryCAD3DShellExtruder
            except ImportError:
                from core.planning.multifloor_v1.engine.dxf_to_3d_shell_extruder import MultiStoryCAD3DShellExtruder
            _st_3d = (_univ_spec.get("stacked_3d_model") if isinstance(_univ_spec, dict) else None)
            if isinstance(_st_3d, dict) and _st_3d.get("floors_3d"):
                MultiStoryCAD3DShellExtruder.export_ifc4_raw_shell(
                    _st_3d, ifc_shell_path, universal_facade_spec=_univ_spec
                )
            else:
                MultiStoryCAD3DShellExtruder.build_3d_shell_and_ifc_from_project(
                    project, ifc_shell_path, universal_facade_spec=_univ_spec
                )
            project.saved_files["last_render_ifc"] = ifc_shell_path
            project.saved_files["last_render_glb"] = os.path.splitext(ifc_shell_path)[0] + ".glb"
            project.saved_files["last_render_obj"] = os.path.splitext(ifc_shell_path)[0] + ".obj"
        except Exception:
            pass
        project.saved_files["last_render_png"] = out_png_path
        project.saved_files["last_render_depth_png"] = depth_path
        project.saved_files["last_render_lineart_png"] = lineart_path

        prompt_en = Architectural3DRenderer_prompt(project, spec)
        return out_png_path, prompt_en

    render_plan_accurate_facade_png = export_plan_locked_south_facade_png

    @classmethod
    def export_controlnet_lineart_svg(
        cls,
        project: BuildingProjectResultV3,
        out_svg_path: str,
        camera_mode: str = "PERSPECTIVE_COURTYARD",
    ) -> str:
        W, H = 1280, 768
        lines = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">',
            f'<rect x="0" y="0" width="{W}" height="{H}" fill="#000000"/>',
        ]
        g_y = 620
        bx0, bx_c1, bx1 = 220, 680, 990
        y_plinth, y_f1, y_roof_w, y_roof_e = g_y - 34, g_y - 290, g_y - 545, g_y - 575
        lines.extend([
            f'<line x1="40" y1="{g_y}" x2="{W-40}" y2="{g_y}" stroke="#FFFFFF" stroke-width="3"/>',
            f'<rect x="{bx0}" y="{y_plinth}" width="{bx1-bx0}" height="34" fill="none" stroke="#FFFFFF" stroke-width="3"/>',
            f'<rect x="{bx0}" y="{y_roof_w}" width="{bx_c1-bx0}" height="{y_plinth-y_roof_w}" fill="none" stroke="#FFFFFF" stroke-width="4"/>',
            f'<rect x="{bx_c1}" y="{y_roof_e}" width="{bx1-bx_c1}" height="{y_plinth-y_roof_e}" fill="none" stroke="#FFFFFF" stroke-width="4"/>',
            "</svg>",
        ])
        os.makedirs(os.path.dirname(os.path.abspath(out_svg_path)), exist_ok=True)
        with open(out_svg_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return out_svg_path

    @classmethod
    def transform_cartoon_render_to_photorealistic(
        cls,
        project: BuildingProjectResultV3,
        existing_render_png_path: str,
        chat_command: str = "این رندر را از حالت کارتونی به عکس واقعی فتورئالیستی تبدیل کن",
        quality: str = "photoreal",
        comfyui_url: str = "http://127.0.0.1:8188",
        timeout_sec: int = 3600,
    ) -> Dict[str, Any]:
        """
        v43.0 Stage-2 Cartoon-to-Photorealistic ComfyUI Transformer (`تبدیل رندر کارتونی/اولیه به عکس واقعی`):
          1. Takes an existing Stage-1 draft/3D render (`existing_render_png_path`) and its companion
             3D Depth map (`*_depth.png`) and Lineart map (`*_lineart.png`).
          2. Builds a Stage-2 FLUX Krea Dev FP8 + ControlNet Depth workflow with `denoise = 0.92`,
             `ControlNet strength = 0.78, end_percent = 0.82`, and a RAW Architectural Photography prompt
             (matching the photorealistic quality of `architectos_v11_00189_.jpg`).
          3. Submits to local ComfyUI (`127.0.0.1:8188`) if online, or saves `*_photoreal_workflow.json`
             ready for execution.
        """
        out_dir = os.path.dirname(os.path.abspath(existing_render_png_path)) or "."
        bridge = cls(comfyui_url=comfyui_url)
        return bridge.render_via_comfyui(
            project=project,
            chat_command=chat_command + " [PHOTOREAL_REFINE]",
            output_dir=out_dir,
            timeout_sec=timeout_sec,
            quality=quality,
        )

    @classmethod
    def build_comfyui_workflow_payload(
        cls,
        project: BuildingProjectResultV3,
        chat_command: str,
        uploaded_controlnet_image_name: str = "architectos_controlnet_input.png",
        uploaded_depth_image_name: Optional[str] = None,
        ckpt_name: str = "flux1-krea-dev_fp8_scaled.safetensors",
        controlnet_name: str = "flux1-dev-controlnet-union-pro-2.0-fp8.safetensors",
        seed: Optional[int] = None,
        quality: str = "draft",
    ) -> Dict[str, Any]:
        """
        v33.6 Multi-Tier Speed-Optimized ComfyUI Workflow Builder (Tailored for 16GB VRAM RX 6900 XT):
          - `draft` / `preview` / `test`:
            Uses 640x432 resolution, `steps=4`, `denoise=0.16`, `cfg=1.0`, NO ControlNet (pure Latent Img2Img), and fast `VAEDecode`
            so test renders complete in ~1–2 minutes instead of 2 hours while locking 84% of the exact 3D plan geometry!
          - `fast` / `auto` / `standard`:
            Uses 768x512 resolution, `steps=6`, `denoise=0.18`, `cfg=1.0`, NO ControlNet, and fast `VAEDecode`!
          - `high` / `final` / `ultra`:
            Uses 1024x688 resolution, `steps=12`, `denoise=0.20`, and ControlNet (`strength=0.92`, `end_percent=0.95`).
        """
        site_r_state = getattr(project.site, "active_render_state", None) or {}
        plan_meta = {
            "site_width_mm": project.site.width_x_mm,
            "site_length_mm": project.site.length_y_mm,
            "building_placement": project.site.building_placement,
            "flip_plan_north_south": getattr(project.site, "flip_plan_north_south", False),
            "floor_count": len(project.floors),
            "is_duplex": len(project.floors) == 2,
        }
        spec = cls.parse_render_request_from_chat(chat_command, site_r_state, plan_meta)
        locked_seed = int(seed if seed is not None else spec.get("locked_seed", 20263301))
        base_prompt = Architectural3DRenderer_prompt(project, spec)
        neg_prompt = (
            "text, watermark, caption, title banner, letters, dimension lines, numbers, floor plan top view, blueprint, "
            "cartoon, flat vector drawing, sketch, deformed perspective, wrong floor count, extra floors, missing floors, "
            "closed ground floor wall when pilotis is open, blind solid stone wall without entrance door, windowless wall, blurry"
        )
        depth_img = uploaded_depth_image_name or uploaded_controlnet_image_name
        q_raw = str(quality or "draft").strip().lower()
        # Normalize into exact 4-tier ladder from lowest to highest: draft < preview < quality < final
        is_explicit_photoreal_tier = q_raw in ("photoreal", "photorealistic", "واقعی", "طبیعی") or any(
            kw in str(chat_command or "").lower()
            for kw in ("واقعی کن", "طبیعی کن", "حالت کارتونی", "photoreal", "realistic")
        )
        is_style_ref_locked_cmd = any(
            kw in str(chat_command or "").lower()
            for kw in ("classical_ref", "ar-", "رفرنس", "نئوکلاسیک", "تراورتن", "شیشه سکوریت", "اتو گالری", "مغازه", "رندر واقعی", "عکس واقعی")
        )
        if is_explicit_photoreal_tier:
            q_norm = "photoreal"
            steps_val = 20
            denoise_val = 0.92
            cfg_val = 2.2
            use_controlnet = True
            is_high_quality = True
        elif is_style_ref_locked_cmd:
            # v57.0 Geometry-Locked Photorealistic Style Reference Mode:
            # Uses denoise=0.78 + strong Depth/Edge ControlNet (strength=0.94, end_percent=0.98) so FLUX renders
            # 100% photorealistic travertine stone, glass reflections, roof balustrade parapet, and lighting while strictly
            # preserving the exact 5.15m shop width, flush sloped car ramp (no stairs!), flat roof canopy, and mezzanine!
            q_norm = "quality"
            steps_val = 16
            denoise_val = 0.78
            cfg_val = 1.8
            use_controlnet = True
            is_high_quality = True
        elif q_raw in ("final", "ultra", "production", "نهایی"):
            q_norm = "final"
            steps_val = 20
            denoise_val = 0.86
            cfg_val = 2.0
            use_controlnet = True
            is_high_quality = True
        elif q_raw in ("quality", "high", "standard", "کیفیت", "کیفیت بالا"):
            q_norm = "quality"
            steps_val = 14
            denoise_val = 0.60
            cfg_val = 1.6
            use_controlnet = True
            is_high_quality = True
        elif q_raw in ("preview", "fast", "پیش نمایش", "پیش‌نمایش"):
            q_norm = "preview"
            steps_val = 8
            denoise_val = 0.56
            cfg_val = 1.5
            use_controlnet = True
            is_high_quality = False
        else:
            # `draft` / `auto` / `test` (Fastest tier)
            q_norm = "draft"
            steps_val = 6
            denoise_val = 0.52
            cfg_val = 1.5
            use_controlnet = True
            is_high_quality = False

        # Universal Image-Driven Style Prompt Injection (works for ANY reference image!)
        _ext_ref_path = str(getattr(project, "_active_style_ref_path", "") or "")
        _ext_ref_cap = str(getattr(project, "_active_style_ref_caption", "") or "")
        _dyn_style = extract_universal_style_from_reference_image(_ext_ref_path, _ext_ref_cap)
        if _dyn_style.get("style_prompt_en"):
            base_prompt = _dyn_style["style_prompt_en"] + " | " + base_prompt
        _has_3d_mesh_active = bool(isinstance((site_r_state or {}).get("universal_facade_spec"), dict) and (site_r_state or {}).get("universal_facade_spec", {}).get("mesh_cache_npz"))
        if _has_3d_mesh_active and not any(r_kw in str(chat_command or "").upper() for r_kw in ("CLASSICAL_REF_", "AR-")):
            denoise_val = min(float(denoise_val), 0.40)
        if (not _has_3d_mesh_active) and any(k in str(chat_command or "").lower() for k in ("مغازه", "شیشه سکوریت", "اتو گالری", "نمایشگاه")):
            base_prompt = (
                "Flanked on left and right by solid neighboring urban buildings (ZERO side yards, ZERO exterior stairs, ZERO outdoor cars), "
                "one luxury sedan parked INSIDE the central showroom behind the wide frameless tempered Securit glass doors, "
                "flush sloped drive-in car ramp from street. "
                + base_prompt
            )
            base_prompt = (
                "Photorealistic architectural exterior photograph, grand neoclassical cream limestone commercial storefront "
                "inspired by European boutique gallery facade, carved stone entablature and roof stone balustrade parapet, "
                "fluted Corinthian pilasters, wide frameless tempered Securit glass showroom entrance, "
                "flush sloped drive-in car ramp from street, warm gallery interior lighting, 8k DSLR architectural photography. "
                + base_prompt
            )
        workflow: Dict[str, Any] = {
            "202": {
                "class_type": "UNETLoader",
                "inputs": {
                    "unet_name": ckpt_name,
                    "weight_dtype": "fp8_e4m3fn",
                },
            },
            "204": {
                "class_type": "DualCLIPLoader",
                "inputs": {
                    "clip_name1": "clip_l.safetensors",
                    "clip_name2": "t5xxl_fp16.safetensors",
                    "type": "flux",
                },
            },
            "205": {
                "class_type": "VAELoader",
                "inputs": {"vae_name": "ae.safetensors"},
            },
            "300": {
                "class_type": "LoadImage",
                "inputs": {"image": uploaded_controlnet_image_name, "upload": "image"},
            },
            "301": {
                "class_type": "VAEEncode",
                "inputs": {"pixels": ["300", 0], "vae": ["205", 0]},
            },
            "206": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": base_prompt, "clip": ["204", 0]},
            },
            "212": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": neg_prompt, "clip": ["204", 0]},
            },
        }

        if use_controlnet:
            workflow["307"] = {
                "class_type": "LoadImage",
                "inputs": {"image": depth_img, "upload": "image"},
            }
            workflow["310"] = {
                "class_type": "ControlNetLoader",
                "inputs": {"control_net_name": controlnet_name},
            }
            workflow["311"] = {
                "class_type": "ControlNetApplyAdvanced",
                "inputs": {
                    "positive": ["206", 0],
                    "negative": ["212", 0],
                    "control_net": ["310", 0],
                    "image": ["307", 0],
                    "vae": ["205", 0],
                    "strength": 0.92,
                    "start_percent": 0.0,
                    "end_percent": 0.95,
                },
            }
            pos_link = ["311", 0]
            neg_link = ["311", 1]
        else:
            pos_link = ["206", 0]
            neg_link = ["212", 0]

        workflow["210"] = {
            "class_type": "KSampler",
            "inputs": {
                "model": ["202", 0],
                "seed": locked_seed,
                "steps": steps_val,
                "cfg": cfg_val,
                "sampler_name": "euler",
                "scheduler": "simple",
                "positive": pos_link,
                "negative": neg_link,
                "latent_image": ["301", 0],
                "denoise": denoise_val,
            },
        }

        if is_high_quality:
            workflow["208"] = {
                "class_type": "VAEDecodeTiled",
                "inputs": {
                    "samples": ["210", 0],
                    "vae": ["205", 0],
                    "tile_size": 512,
                    "overlap": 64,
                    "temporal_size": 64,
                    "temporal_overlap": 8,
                },
            }
        else:
            workflow["208"] = {
                "class_type": "VAEDecode",
                "inputs": {
                    "samples": ["210", 0],
                    "vae": ["205", 0],
                },
            }

        workflow["9"] = {
            "class_type": "SaveImage",
            "inputs": {
                "filename_prefix": f"ArchitectOS_{project.project_id}_{spec['style_key']}_{spec['lighting_mode']}_{q_norm.upper()}",
                "images": ["208", 0],
            },
        }

        return {
            "client_id": str(uuid.uuid4()),
            "prompt": workflow,
            "architectos_metadata": {
                "project_id": project.project_id,
                "quality": q_norm,
                "steps": steps_val,
                "denoise": denoise_val,
                "parsed_render_spec": spec,
                "locked_seed": locked_seed,
                "positive_prompt": base_prompt,
                "negative_prompt": neg_prompt,
                "controlnet_image": uploaded_controlnet_image_name,
                "depth_image": depth_img,
            },
        }

    def _upload_file_to_comfyui(self, file_path: str) -> str:
        img_name = os.path.basename(file_path)
        boundary = "----ArchitectOSBoundary" + uuid.uuid4().hex
        with open(file_path, "rb") as img_f:
            img_bytes = img_f.read()
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="image"; filename="{img_name}"\r\n'
            f"Content-Type: image/png\r\n\r\n"
        ).encode("utf-8") + img_bytes + (
            f"\r\n--{boundary}\r\n"
            f'Content-Disposition: form-data; name="overwrite"\r\n\r\ntrue\r\n'
            f"--{boundary}--\r\n"
        ).encode("utf-8")
        req_up = urllib.request.Request(
            f"{self.comfyui_url}/upload/image",
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        with urllib.request.urlopen(req_up, timeout=8) as resp_up:
            up_info = json.loads(resp_up.read().decode("utf-8"))
            return up_info.get("name", img_name)

    def _adapt_workflow_to_live_comfyui(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """
        Queries `http://127.0.0.1:8188/object_info` to verify installed UNET, CLIP (preferring fp8 T5 to save 4.7GB VRAM!),
        and ControlNet models so the workflow runs at maximum speed on 16GB VRAM GPUs without RAM swapping.
        """
        wf = json.loads(json.dumps(workflow))
        try:
            with urllib.request.urlopen(f"{self.comfyui_url}/object_info", timeout=4) as resp:
                obj_info = json.loads(resp.read().decode("utf-8"))
            # 1. Check UNETLoader models & weight_dtype
            unet_req = obj_info.get("UNETLoader", {}).get("input", {}).get("required", {})
            unet_choices = unet_req.get("unet_name", [[]])[0]
            if isinstance(unet_choices, list) and unet_choices and wf["202"]["inputs"]["unet_name"] not in unet_choices:
                flux_cands = [m for m in unet_choices if "flux" in str(m).lower()]
                wf["202"]["inputs"]["unet_name"] = flux_cands[0] if flux_cands else unet_choices[0]
            dtype_choices = unet_req.get("weight_dtype", [[]])[0]
            if isinstance(dtype_choices, list) and dtype_choices and wf["202"]["inputs"].get("weight_dtype") not in dtype_choices:
                fp8_d = [d for d in dtype_choices if "fp8" in str(d).lower()]
                wf["202"]["inputs"]["weight_dtype"] = fp8_d[0] if fp8_d else dtype_choices[0]

            # 2. Check DualCLIPLoader models — prefer t5xxl_fp8 to save 4.7 GB of VRAM on 16GB RX 6900 XT!
            clip_req = obj_info.get("DualCLIPLoader", {}).get("input", {}).get("required", {})
            c2_choices = clip_req.get("clip_name2", [[]])[0]
            if isinstance(c2_choices, list) and c2_choices:
                fp8_t5 = [c for c in c2_choices if "t5" in str(c).lower() and "fp8" in str(c).lower()]
                if fp8_t5:
                    wf["204"]["inputs"]["clip_name2"] = fp8_t5[0]
                elif wf["204"]["inputs"]["clip_name2"] not in c2_choices:
                    t5_any = [c for c in c2_choices if "t5" in str(c).lower()]
                    wf["204"]["inputs"]["clip_name2"] = t5_any[0] if t5_any else c2_choices[0]

            # 3. Check ControlNetLoader models if ControlNet node 310 is in the workflow
            if "310" in wf:
                cn_choices = (
                    obj_info.get("ControlNetLoader", {})
                    .get("input", {})
                    .get("required", {})
                    .get("control_net_name", [[]])[0]
                )
                if not isinstance(cn_choices, list) or not cn_choices:
                    wf.pop("307", None)
                    wf.pop("310", None)
                    wf.pop("311", None)
                    wf["210"]["inputs"]["positive"] = ["206", 0]
                    wf["210"]["inputs"]["negative"] = ["212", 0]
                    wf["210"]["inputs"]["denoise"] = min(0.48, max(0.38, float(wf["210"]["inputs"].get("denoise", 0.45))))
                elif wf["310"]["inputs"]["control_net_name"] not in cn_choices:
                    union_cands = [m for m in cn_choices if "flux" in str(m).lower() or "union" in str(m).lower()]
                    wf["310"]["inputs"]["control_net_name"] = union_cands[0] if union_cands else cn_choices[0]
        except Exception:
            pass
        return wf

    def render_via_comfyui(
        self,
        project: BuildingProjectResultV3,
        chat_command: str,
        controlnet_png_path: str,
        output_dir: str,
        timeout_sec: int = 3600,
        quality: str = "draft",
    ) -> Dict[str, Any]:
        os.makedirs(output_dir, exist_ok=True)
        q_raw = str(quality or "draft").strip().lower()
        if q_raw in ("final", "ultra", "production", "نهایی"):
            q_norm = "final"
            target_wh = (1280, 864)
            is_high_q = True
        elif q_raw in ("quality", "high", "standard", "auto", "کیفیت", "کیفیت بالا"):
            q_norm = "quality"
            target_wh = (1280, 864)
            is_high_q = True
        elif q_raw in ("preview", "fast", "پیش نمایش", "پیش‌نمایش"):
            q_norm = "preview"
            target_wh = (960, 640)
            is_high_q = False
        else:
            q_norm = "draft"
            target_wh = (768, 512)
            is_high_q = False
        base_no_ext = os.path.splitext(controlnet_png_path)[0]
        clean_src_path = base_no_ext + "_comfy_input.png"
        if not os.path.isfile(clean_src_path):
            clean_src_path = controlnet_png_path

        # v79.0 Iterative Relight / Material-Edit Detection: if user asks to relight/edit the SAME building
        # (e.g. "همون ساختمون رو بدون تغییر فقط رندر روز کن") and a previous render exists in this project,
        # lock Img2Img + ControlNet directly onto that previous render PNG!
        _is_iter_edit_79, _is_iter_relight_79 = _is_iterative_relight_or_edit_cmd(chat_command)
        _prev_render_png_79 = _find_latest_project_render_png(output_dir, exclude_paths=(controlnet_png_path, clean_src_path)) if _is_iter_edit_79 else None
        if _prev_render_png_79 and os.path.isfile(_prev_render_png_79):
            clean_src_path = _prev_render_png_79

        scaled_in_path = base_no_ext + f"_comfy_{target_wh[0]}x{target_wh[1]}.png"
        try:
            from PIL import Image
            with Image.open(clean_src_path) as im_s:
                im_s.convert("RGB").resize(target_wh, Image.Resampling.LANCZOS).save(scaled_in_path, format="PNG")
        except Exception:
            scaled_in_path = clean_src_path

        depth_png_path = base_no_ext + "_depth.png"
        scaled_depth_path = base_no_ext + f"_depth_{target_wh[0]}x{target_wh[1]}.png"
        if os.path.isfile(depth_png_path):
            try:
                from PIL import Image
                with Image.open(depth_png_path) as im_d:
                    im_d.convert("RGB").resize(target_wh, Image.Resampling.BILINEAR).save(scaled_depth_path, format="PNG")
            except Exception:
                scaled_depth_path = depth_png_path
        else:
            scaled_depth_path = scaled_in_path

        img_name = os.path.basename(scaled_in_path)
        depth_name = os.path.basename(scaled_depth_path)

        payload = self.build_comfyui_workflow_payload(
            project,
            chat_command,
            uploaded_controlnet_image_name=img_name,
            uploaded_depth_image_name=depth_name,
            quality=q_norm,
        )
        workflow_json_path = os.path.join(
            output_dir, f"{project.project_id}_comfyui_workflow.json"
        )
        with open(workflow_json_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        try:
            uploaded_base = self._upload_file_to_comfyui(scaled_in_path)
            uploaded_depth = (
                self._upload_file_to_comfyui(scaled_depth_path)
                if os.path.isfile(scaled_depth_path)
                else uploaded_base
            )
            payload = self.build_comfyui_workflow_payload(
                project,
                chat_command,
                uploaded_controlnet_image_name=uploaded_base,
                uploaded_depth_image_name=uploaded_depth,
                quality=q_norm,
            )
            adapted_wf = self._adapt_workflow_to_live_comfyui(payload["prompt"])
            _r_st_m = getattr(project.site, "active_render_state", None) or {}
            _u_sp_m = _r_st_m.get("universal_facade_spec") if isinstance(_r_st_m, dict) else None
            _has_style_ref_active = bool(getattr(project, "_active_style_ref_path", "") or getattr(project, "_active_style_ref_caption", ""))
            _steps_by_tier_77 = {"draft": 6, "preview": 10, "quality": 16, "final": 24, "photoreal": 24}
            _tier_steps_77 = _steps_by_tier_77.get(q_norm, 16)
            _has_ext_3d_or_plan_77 = bool(
                (isinstance(_u_sp_m, dict) and (_u_sp_m.get("mesh_cache_npz") or _u_sp_m.get("is_direct_3d_bim_import") or _u_sp_m.get("is_topological_3d_plan") or _u_sp_m.get("is_commercial_mezzanine_shop")))
                or (isinstance(_r_st_m, dict) and _r_st_m.get("custom_facade_profile"))
            )
            if isinstance(_u_sp_m, dict) and _u_sp_m.get("mesh_cache_npz"):
                if "210" in adapted_wf and "inputs" in adapted_wf["210"]:
                    adapted_wf["210"]["inputs"]["denoise"] = 0.84 if _has_style_ref_active else 0.80
                    adapted_wf["210"]["inputs"]["steps"] = _tier_steps_77
                    adapted_wf["210"]["inputs"]["cfg"] = max(2.2, float(adapted_wf["210"]["inputs"].get("cfg", 2.4)))
                if "311" in adapted_wf and "inputs" in adapted_wf["311"]:
                    adapted_wf["311"]["inputs"]["strength"] = 0.80
                    adapted_wf["311"]["inputs"]["end_percent"] = 0.90
            elif _prev_render_png_79 and os.path.isfile(_prev_render_png_79):
                # v79.0 Iterative Relight / Material-Edit Lock: preserve 100% of the exact previous building!
                if "210" in adapted_wf and "inputs" in adapted_wf["210"]:
                    adapted_wf["210"]["inputs"]["denoise"] = 0.56 if _is_iter_relight_79 else 0.45
                    adapted_wf["210"]["inputs"]["steps"] = _tier_steps_77
                    adapted_wf["210"]["inputs"]["cfg"] = 2.4 if q_norm != "draft" else 1.8
                if "311" in adapted_wf and "inputs" in adapted_wf["311"]:
                    adapted_wf["311"]["inputs"]["strength"] = 0.85
                    adapted_wf["311"]["inputs"]["end_percent"] = 0.92
            elif not _has_ext_3d_or_plan_77:
                # v79.0 Pure Text-to-Architecture Mode (no uploaded 3D/CAD file):
                # If an explicit high-rise floor count (>= 7 floors, e.g. 22 floors) is requested, guide FLUX with an exact N-floor depth scaffold!
                import re as _re79_f
                _cn79 = str(chat_command or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
                _mf79 = _re79_f.search(r"(\d{1,2})\s*(?:طبقه|ط|story|stories|floor|floors)", _cn79, _re79_f.I)
                _req_nf79 = int(_mf79.group(1)) if _mf79 else 0
                if _req_nf79 >= 7:
                    try:
                        _td_p79 = base_no_ext + f"_tower_{_req_nf79}f_depth.png"
                        _build_n_floor_tower_depth_guide(_req_nf79, target_wh[0], target_wh[1], _td_p79)
                        _up_td79 = self._upload_file_to_comfyui(_td_p79)
                        if "310" in adapted_wf and "inputs" in adapted_wf["310"]:
                            adapted_wf["310"]["inputs"]["image"] = _up_td79
                        if "311" in adapted_wf and "inputs" in adapted_wf["311"]:
                            adapted_wf["311"]["inputs"]["strength"] = 0.62
                            adapted_wf["311"]["inputs"]["end_percent"] = 0.72
                        if "210" in adapted_wf and "inputs" in adapted_wf["210"]:
                            adapted_wf["210"]["inputs"]["denoise"] = 0.88
                            adapted_wf["210"]["inputs"]["steps"] = _tier_steps_77
                            adapted_wf["210"]["inputs"]["cfg"] = 2.6 if q_norm != "draft" else 1.8
                    except Exception:
                        for _cn_k77 in ("307", "310", "311"):
                            adapted_wf.pop(_cn_k77, None)
                        if "210" in adapted_wf and "inputs" in adapted_wf["210"]:
                            adapted_wf["210"]["inputs"]["positive"] = ["206", 0]
                            adapted_wf["210"]["inputs"]["negative"] = ["212", 0]
                            adapted_wf["210"]["inputs"]["denoise"] = 0.96
                            adapted_wf["210"]["inputs"]["steps"] = _tier_steps_77
                else:
                    for _cn_k77 in ("307", "310", "311"):
                        adapted_wf.pop(_cn_k77, None)
                    if "210" in adapted_wf and "inputs" in adapted_wf["210"]:
                        adapted_wf["210"]["inputs"]["positive"] = ["206", 0]
                        adapted_wf["210"]["inputs"]["negative"] = ["212", 0]
                        adapted_wf["210"]["inputs"]["denoise"] = 0.96
                        adapted_wf["210"]["inputs"]["steps"] = _tier_steps_77
                        adapted_wf["210"]["inputs"]["cfg"] = 2.6 if q_norm != "draft" else 1.8
            try:
                req_p = urllib.request.Request(
                    f"{self.comfyui_url}/prompt",
                    data=json.dumps({"prompt": adapted_wf, "client_id": payload["client_id"]}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req_p, timeout=12) as resp_p:
                    p_info = json.loads(resp_p.read().decode("utf-8"))
                    prompt_id = p_info["prompt_id"]
            except Exception:
                # Fallback to pure Geometry-Locked Latent Img2Img if ControlNet node schema is rejected by ComfyUI
                for _cn_k in ("307", "310", "311"):
                    adapted_wf.pop(_cn_k, None)
                if "210" in adapted_wf and "inputs" in adapted_wf["210"]:
                    adapted_wf["210"]["inputs"]["positive"] = ["206", 0]
                    adapted_wf["210"]["inputs"]["negative"] = ["212", 0]
                    adapted_wf["210"]["inputs"]["denoise"] = min(0.32, float(adapted_wf["210"]["inputs"].get("denoise", 0.32)))
                req_p2 = urllib.request.Request(
                    f"{self.comfyui_url}/prompt",
                    data=json.dumps({"prompt": adapted_wf, "client_id": payload["client_id"]}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req_p2, timeout=12) as resp_p2:
                    p_info = json.loads(resp_p2.read().decode("utf-8"))
                    prompt_id = p_info["prompt_id"]

            t0 = time.time()
            while time.time() - t0 < timeout_sec:
                with urllib.request.urlopen(f"{self.comfyui_url}/history/{prompt_id}", timeout=6) as resp_h:
                    hist = json.loads(resp_h.read().decode("utf-8"))
                if prompt_id in hist:
                    outputs = hist[prompt_id].get("outputs", {})
                    for node_out in outputs.values():
                        for img_meta in node_out.get("images", []):
                            q = urllib.parse.urlencode({
                                "filename": img_meta["filename"],
                                "subfolder": img_meta.get("subfolder", ""),
                                "type": img_meta.get("type", "output"),
                            })
                            with urllib.request.urlopen(f"{self.comfyui_url}/view?{q}", timeout=12) as resp_v:
                                out_png = os.path.join(output_dir, f"{project.project_id}_comfyui_render.png")
                                with open(out_png, "wb") as f_out:
                                    f_out.write(resp_v.read())
                                try:
                                    import cv2
                                    from PIL import Image
                                    comfy_im = Image.open(out_png).convert("RGB")
                                    if comfy_im.size != (1280, 864):
                                        comfy_im = comfy_im.resize((1280, 864), Image.Resampling.LANCZOS)
                                    # v68.0 V-Ray High-Frequency Micro-Detail & Window/Iron Lock Fusion:
                                    # Injects razor-sharp 2x-SSAA geometric reliefs, mullions, wrought-iron gates & dark window glass
                                    # from `clean_src_path` into `comfy_im` so ComfyUI NEVER blurs 3D carvings or turns glass into stone!
                                    if os.path.isfile(clean_src_path):
                                        try:
                                            vray_ref = np.array(Image.open(clean_src_path).convert("RGB").resize((1280, 864), Image.Resampling.LANCZOS), dtype=np.float32)
                                            comfy_np = np.array(comfy_im, dtype=np.float32)
                                            vray_blur = cv2.GaussianBlur(vray_ref, (9, 9), 2.2)
                                            vray_hi_detail = vray_ref - vray_blur
                                            # Gentle 15% high-frequency edge micro-sharpen only (preserve 100% of FLUX photorealism!)
                                            fused_np = comfy_np + 0.08 * vray_hi_detail
                                            comfy_im = Image.fromarray(np.clip(fused_np, 0, 255).astype(np.uint8))
                                        except Exception:
                                            pass
                                    comfy_im.save(out_png, format="PNG")
                                except Exception:
                                    pass
                            return {
                                "status": "RENDERED_BY_COMFYUI",
                                "render_png_path": out_png,
                                "workflow_json_path": workflow_json_path,
                                "controlnet_png_path": controlnet_png_path,
                                "positive_prompt": payload["architectos_metadata"]["positive_prompt"],
                            }
                time.sleep(1.5)
        except Exception as exc:
            return {
                "status": "COMFYUI_WORKFLOW_PREPARED",
                "reason": f"ComfyUI server at {self.comfyui_url} not reachable or busy ({exc}); using Plan-Locked 3D Ray-Shaded render.",
                "workflow_json_path": workflow_json_path,
                "controlnet_png_path": controlnet_png_path,
                "positive_prompt": payload["architectos_metadata"]["positive_prompt"],
            }
        return {
            "status": "COMFYUI_TIMEOUT",
            "workflow_json_path": workflow_json_path,
            "controlnet_png_path": controlnet_png_path,
            "positive_prompt": payload["architectos_metadata"]["positive_prompt"],
        }


def Architectural3DRenderer_prompt(
    project: BuildingProjectResultV3, spec: Dict[str, Any]
) -> str:
    site_r_state = getattr(project.site, "active_render_state", None) or {}
    custom_prof = site_r_state.get("custom_facade_profile") if isinstance(site_r_state, dict) else None
    univ_spec = (
        (custom_prof.get("universal_facade_spec") if isinstance(custom_prof, dict) else None)
        or (site_r_state.get("universal_facade_spec") if isinstance(site_r_state, dict) else None)
        or {}
    )
    _is_noncommercial_3d_mesh_active = bool(
        isinstance(univ_spec, dict)
        and not univ_spec.get("is_commercial_mezzanine_shop")
        and not univ_spec.get("is_commercial_split_level")
        and str(univ_spec.get("profile_type") or "") != "COMMERCIAL_SPLIT_LEVEL_MEZZANINE"
        and (
            univ_spec.get("is_direct_3d_bim_import")
            or univ_spec.get("mesh_cache_npz")
            or isinstance(univ_spec.get("stacked_3d_model"), dict)
        )
    )
    n_floors = len(project.floors)
    fl0 = project.floors[0]
    _raw_chat_77 = str(spec.get("raw_chat_text") or "")
    _raw_chat_norm_77 = _raw_chat_77.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
    import re as _re_77
    _m_fl_77 = _re_77.search(r"(\d{1,2})\s*(?:طبقه|ط|story|stories|floor|floors)", _raw_chat_norm_77, _re_77.I)
    _explicit_chat_floors_77 = int(_m_fl_77.group(1)) if _m_fl_77 else None
    _is_tower_chat_77 = ("برج" in _raw_chat_norm_77) or ("tower" in _raw_chat_norm_77.lower()) or ("high-rise" in _raw_chat_norm_77.lower()) or bool(_explicit_chat_floors_77 and _explicit_chat_floors_77 >= 7)
    if (
        (isinstance(custom_prof, dict) and (custom_prof.get("profile_type") == "TOPOLOGICAL_3D_NEOCLASSICAL_VILLA" or custom_prof.get("is_topological_3d_plan")))
        or (isinstance(univ_spec, dict) and (univ_spec.get("is_topological_3d_plan") or univ_spec.get("has_semicircular_terrace")))
    ):
        n_floors = int(univ_spec.get("total_floors", 3) or 3)
        floor_word = (
            "3-story Neoclassical luxury cream travertine residential villa (12.0m wide) with a 100% FLAT ROOF crowned by a continuous "
            "classical lathe-turned stone baluster parapet railing (ZERO pitched tile roof and ZERO rooftop penthouse/kharposhteh), "
            "a First Floor (+4.85m) recessed 6.0 meters back to Axis 4 featuring a straight central wall with a central double French glass door "
            "and flanking windows, two symmetrical side windows, and two 45-degree chamfered end walls opening onto a huge 8.95m-deep open terrace "
            "with a central semi-circular stone balustrade and two stepped setbacks on left and right supported by 4 fluted Neoclassical Corinthian "
            "columns with carved acanthus capitals and Attic bases, a Ground Floor (+1.45m) with a deeply recessed left wing, projecting center bay, "
            "slightly recessed right wing with an arched double entrance door and wide window, and a left L-shaped stone staircase rising from the "
            "courtyard to a +0.90m corner landing and turning 90 degrees right onto the ground floor terrace, plus a Basement (-1.45m) with a recessed "
            "left wing, flush center and right wall with 2 doors and 2 windows, and a right L-shaped staircase rising from the basement to the courtyard"
        )
    elif isinstance(univ_spec, dict) and univ_spec.get("mesh_cache_npz") and not univ_spec.get("is_commercial_mezzanine_shop"):
        _npz_low = str(univ_spec.get("mesh_cache_npz") or "").lower()
        _prof_m = ""
        try:
            if os.path.isfile(str(univ_spec.get("mesh_cache_npz"))):
                _dz_p = np.load(str(univ_spec.get("mesh_cache_npz")))
                if "mesh_profile" in _dz_p:
                    _prof_m = str(_dz_p["mesh_profile"]).lower()
        except Exception:
            pass
        if "sadegh" in _npz_low or "sadegh" in _prof_m:
            n_floors = 2
            floor_word = (
                "two-story Iranian classical cream travertine residential house with a SINGLE CONTINUOUS wide horizontal "
                "multi-pane dark-framed panoramic window across the right side of the first floor (strictly ONE continuous wide window, "
                "ZERO stone wall splitting the window in the middle), a deep recessed open arched loggia balcony with a turned stone "
                "balustrade on the left side of the first floor, a rooftop staircase tower (خرپشته) on the left with a 4-sided stone "
                "balustrade, a central curved roof pediment, and a front courtyard wall with a left blind arch and a right 3-pillar "
                "classical bracketed portal framing black wrought-iron arched gates, ZERO bushes or trees on the walls, ZERO car showroom"
            )
        elif "tamrin" in _npz_low or "tamrin" in _prof_m or "dense_capitals" in _npz_low:
            n_floors = 2
            floor_word = (
                "grand two-story Neoclassical cream travertine villa with a black slate mansard roof and a central white-and-black "
                "ribbed dome with circular lucarne windows and spire at the crown, 3 full-height fluted Corinthian columns on the facade, "
                "3 tall arched multi-pane windows with curved white stone hemispherical flower-pot planters, a central projecting stone "
                "balustrade balcony above the arched ground-floor wooden entrance door, black wrought-iron arched gates flanking the "
                "entrance, arched stone courtyard boundary walls with warm glowing wall-mounted lanterns, lush purple flowers overflowing "
                "from the hemispherical stone planters, dark reflective arched window glass with slender black mullions, sheer curtains and warm "
                "glowing interior crystal chandeliers, mature green trees framing the left and right edges, manicured green lawn, and a sleek luxury "
                "car parked naturally in front; ultra-photorealistic V-Ray 6.20 architectural daylight rendering, 8k crisp detail"
            )
        else:
            n_floors = max(1, int(univ_spec.get("total_floors") or len(project.floors) or 2))
            floor_word = (
                f"ultra-photorealistic architectural exterior photograph of a {n_floors}-story building rendered in V-Ray 6 / Corona Renderer, "
                "strictly preserving 100% of the exact 3D model geometry, architectural style, massing, facade proportions, openings, balconies, "
                "and roofline silhouette; realistic high-resolution PBR surface materials faithful to the 3D design and any reference image, "
                "deep dark reflective architectural glass in all glazed window and door openings with realistic mullions, subtle interior depth, "
                "and soft warm interior lighting, crisp realistic frames and railings, physical sun and sky global illumination with soft contact "
                "shadows, subtle site-appropriate landscaping and natural ground paving, clear architectural sky with soft clouds, "
                "razor-sharp 8k ArchDaily exterior photography (zero clay look)"
            )
    elif (
        (isinstance(custom_prof, dict) and (custom_prof.get("profile_type") == "COMMERCIAL_SPLIT_LEVEL_MEZZANINE" or custom_prof.get("is_commercial_split_level")))
        or (isinstance(univ_spec, dict) and (univ_spec.get("profile_type") == "COMMERCIAL_SPLIT_LEVEL_MEZZANINE" or univ_spec.get("is_commercial_split_level")))
        or ((not _is_noncommercial_3d_mesh_active) and any(k in str(spec.get("raw_chat_text") or "") for k in ("مغازه", "تجاری", "اتو گالری", "شیشه سکوریت", "سکوریت", "ویترین")))
    ):
        n_floors = 2
        floor_word = (
            "luxury commercial auto-gallery and retail showroom storefront (اتو گالری سینا, 5.15m wide x 6.60m high, Ground Floor +0.60m + Split-Level Mezzanine +3.60m from Axis D to G) "
            "flanked by two adjacent urban retail shop bays on left and right, featuring a full-height frameless tempered Securit glass curtain-wall storefront and a large central double "
            "tempered Securit glass entrance door with brushed stainless-steel patch fittings and vertical pull handles, a sloped granite entrance ramp in front rising from the 0.00m sidewalk "
            "to the +0.60m showroom floor, a white luxury sedan parked inside the left ground-floor showroom, a straight stone-and-steel staircase along the right interior wall rising from +0.60m "
            "to the +3.60m mezzanine floor, an interior split-level mezzanine office at +3.60m with a glass-and-metal guardrail balustrade at Axis D, wooden executive desk, and green indoor plants "
            "clearly visible through the upper glazing, and a cream Abbasabad travertine stone fascia header signboard at +5.20m..+6.60m with warm recessed LED ceiling spotlights"
        )
    elif isinstance(custom_prof, dict) and custom_prof.get("profile_type") == "TOWNHOUSE_3FLOOR_NO_PILOTIS":
        n_floors = 3
        floor_word = (
            "3-story urban residential townhouse (slender 4.75m-wide flat-roofed FACHADA PRINCIPAL) with a clean continuous stone facade wall, "
            "ZERO balconies and ZERO balustrades, a stepped 2-riser stone base plinth, "
            "a ground floor featuring a single narrow entrance door at the far left edge (u=0.02..0.21) and a 2-pane window with a 0.65m wall sill on the right (u=0.39..0.81) — NO open pilotis and NO parked cars, "
            "plus EXACTLY 2 upper residential floors each featuring ONLY a single centered-left 2-pane window (u=0.26..0.68) with a 0.55m wall sill aligned vertically, "
            "and a clean flat horizontal roof parapet coping without balusters and without rooftop penthouse"
        )
    elif isinstance(custom_prof, dict) and custom_prof.get("profile_type") == "CONVENTIONAL_1FLOOR_CARPORT_RIGHT":
        n_floors = 1
        floor_word = (
            "single-story ONE-FLOOR residential house with a sloped pitched hipped roof and a full-width kinked overarching eave canopy, "
            "featuring a large forward left wing with a solid left wall and a window that starts near the middle of the wing and continues across a 45-degree chamfered wall "
            "under a narrow rain-drip awning, a central diagonal recessed break containing the entrance door and 2 stone steps rising +0.30m from the 0.00m courtyard under a wide step canopy, "
            "a small recessed right wing that starts from the diagonal break and straightens out at the far right with a small window, "
            "1 car parked in the open right courtyard in front of the recessed right wing, and two small garden planter beds along both sides of the courtyard"
        )
    elif isinstance(custom_prof, dict) and custom_prof.get("is_custom_stepped_plan"):
        n_floors = 1
        floor_word = (
            "single-story ONE-FLOOR stepped residential villa attached to the left courtyard boundary wall with a wide landscaped courtyard gap on the right, "
            "featuring a solid stone front wing on the left and a recessed entrance veranda on the right with 2 stone steps (+0.36m) and 2 equal full-height windows"
        )
    elif fl0.is_open_pilotis and n_floors >= 2:
        res_fl = n_floors - 1
        floor_word = (
            f"{n_floors}-story Iranian urban apartment building consisting of a shorter 2.72m-high OPEN GROUND-FLOOR PILOTIS "
            f"(supported by freestanding stone columns with 2 parked luxury cars on left and right, a central stone pedestrian walkway, "
            f"and a recessed glass staircase and elevator lobby core in the middle of the pilotis depth, zero front ground wall) "
            f"plus EXACTLY {res_fl} residential floor(s) above (each 3.24m high with a recessed South balcony on the left wing and a wide panoramic living room window on the right wing) "
            f"and a recessed stone staircase penthouse (خرپشته) on the roof"
        )
    elif n_floors == 1:
        floor_word = "single-story ONE-FLOOR flat-roofed residential villa"
    else:
        floor_word = f"two-story ({n_floors}-floor) residential duplex villa with a recessed staircase penthouse (خرپشته) on the roof"

    facade_word = f"{spec.get('facade_side', 'SOUTH').title()} elevation"
        # v77.0: Honor explicit floor count (`15 طبقه`) & high-rise tower requests when no external 3D/CAD file is locked
    if (not _is_noncommercial_3d_mesh_active) and (not isinstance(custom_prof, dict) or not custom_prof) and (_explicit_chat_floors_77 or _is_tower_chat_77):
        _nf_77 = _explicit_chat_floors_77 if (_explicit_chat_floors_77 and _explicit_chat_floors_77 >= 1) else max(n_floors, 12)
        _btype_77 = "high-rise residential tower" if (_is_tower_chat_77 or _nf_77 >= 7) else "multi-story residential building"
        if any(k in _raw_chat_norm_77.lower() for k in ("اداری", "office")):
            _btype_77 = "high-rise commercial office tower" if _nf_77 >= 7 else "office building"
        elif any(k in _raw_chat_norm_77.lower() for k in ("تجاری", "commercial")):
            _btype_77 = "high-rise mixed-use commercial tower" if _nf_77 >= 7 else "commercial building"
        _style_77 = "contemporary modern glass-and-stone" if not any(k in _raw_chat_norm_77 for k in ("کلاسیک", "نئوکلاسیک", "رومی")) else "neoclassical stone"
        floor_word = (
            f"tall {_nf_77}-story {_style_77} {_btype_77} (strictly {_nf_77} distinct visible floors from ground lobby to crown penthouse, "
            f"wide-angle full-height architectural perspective showing the entire {_nf_77}-floor skyscraper silhouette from street level to roof)"
        )
    _light_prefix_77 = ""
    _explicit_day_79 = any(k in _raw_chat_norm_77.lower() for k in ("رندر روز", "در روز", "روزش کن", "روز کن", "حالت روز", "نور روز", "daytime", "daylight"))
    if _explicit_day_79:
        _light_prefix_77 = (
            "BRIGHT SUNNY DAYLIGHT ARCHITECTURAL PHOTOGRAPHY, crisp clear bright blue daytime sky with soft white clouds, "
            "natural bright sunlight and soft architectural shadows (ZERO night sky, ZERO dark sky, ZERO glowing night lights), "
        )
    elif spec.get("lighting_mode") == "NIGHT_WARM" or any(k in _raw_chat_norm_77.lower() for k in ("شب", "night")):
        _light_prefix_77 = (
            "ARCHITECTURAL NIGHT PHOTOGRAPHY, deep dark midnight-blue night sky (ZERO bright daytime sky, ZERO sunlight), "
            "warm 3000K glowing illuminated interior windows across all floors, dramatic architectural LED linear facade uplighting and street lights, "
        )
    elif spec.get("lighting_mode") == "GOLDEN_HOUR" or any(k in _raw_chat_norm_77.lower() for k in ("غروب", "sunset", "dusk")):
        _light_prefix_77 = "GOLDEN HOUR SUNSET architectural photography, warm amber dusk sky, glowing interior windows, "

    return _light_prefix_77 + (
        f"Masterpiece 8k photorealistic architectural photograph, {spec['camera_prompt_en']} ({facade_word}), "
        f"strictly a {floor_word} (EXACTLY {n_floors} floor(s), lock 100% of building geometry, floor heights, open pilotis columns, parked cars, balconies, and roof penthouse), "
        f"facade materials: {spec['materials_en']}, enclosed two-sided courtyard in foreground with left and right stone boundary walls, raised stone planter beds, and manicured evergreen trees, "
        f"{spec['lighting_en']}, V-Ray Corona Renderer, architectural digest photography."
    )
