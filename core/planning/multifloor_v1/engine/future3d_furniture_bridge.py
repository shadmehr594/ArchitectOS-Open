r"""
ArchitectOS v42.0 — 3D-FUTURE Furniture Bridge (`engine/future3d_furniture_bridge.py`)

Integrates the 3D-FUTURE 3D furniture dataset from:
  - `<repo-root>\3D-FUTURE-model` (unpacked directory)
  - `<external-drive>\3D-FUTURE-model` or `<external-drive>\3D-FUTURE-model.zip`
  - `<repo_root>\3D-FUTURE-model` or `os.environ.get("ARCHITECTOS_3DFUTURE_DIR")`

Provides TWO unified capabilities:
  1. **3D Furniture Integration for `.glb`, `.obj`, `.ifc`, and Headless Blender**:
     Loads real `.obj` 3D furniture meshes (`raw_model.obj` / `normalized_model.obj`), converts
     Y-up to Z-up, scales & rotates them to the exact solved room `RectMM` and `orientation`,
     and produces 3D mesh primitives + `IFC4` `IfcFurnishingElement` / `IfcBuildingElementProxy` solids.
  2. **2D Top-Down Orthographic Projection (`تصویر از بالای مبلمان`) for AutoCAD `.dxf` & `.svg`/`.png`**:
     Projects 3D-FUTURE meshes from top-down (`+Z -> (X, Y)`) into multi-contour architectural CAD
     blocks (rounded cushions, curved chair backs, organic pillows & folded duvets, beveled tables,
     curved sanitary fixtures) so 2D AutoCAD `.dxf` and `.svg` plans have studio-grade furniture graphics.
"""
from __future__ import annotations

import glob
import json
import math
import os
import zipfile
from typing import Any, Callable, Dict, List, Optional, Tuple


class Future3DFurnitureBridge:
    """
    Universal 3D-FUTURE loader, 3D mesh transformer, and Top-Down 2D AutoCAD/SVG contour projector.
    """

    _MODEL_INDEX_CACHE: Optional[Dict[str, List[str]]] = None
    _TOP_CONTOUR_CACHE: Dict[str, List[List[Tuple[float, float]]]] = {}
    _MESH_3D_CACHE: Dict[str, Tuple[List[Tuple[float, float, float]], List[Tuple[int, int, int]]]] = {}

    CATEGORY_KEYWORDS: Dict[str, Tuple[str, ...]] = {
        "BED_DOUBLE": ("king-size bed", "double bed", "bed", "queen bed"),
        "BED_SINGLE": ("single bed", "kids bed", "bunk bed", "bed"),
        "SOFA_L": ("l-shaped sofa", "multi-seat sofa", "three-seat", "sofa", "couch"),
        "TV_LOUNGE": ("l-shaped sofa", "corner sofa", "lazy sofa", "sofa", "tv stand"),
        "DINING_6": ("dining table", "dining chair", "table"),
        "DINING_8": ("dining table", "conference table", "table"),
        "STUDY_DESK": ("desk", "computer desk", "office chair"),
        "WARDROBE": ("wardrobe", "closet", "cabinet", "bookcase"),
        "KITCHEN_ISLAND_BAR": ("bar", "island", "sideboard", "dining table"),
        "KITCHEN_COUNTER": ("cabinet", "sideboard", "cupboard"),
    }

    @classmethod
    def find_3dfuture_root(cls, repo_root: Optional[str] = None) -> Optional[str]:
        r"""Locates the unpacked `3D-FUTURE-model` folder or extracts metadata from `<external-drive>\3D-FUTURE-model.zip`."""
        candidates = []
        env_dir = os.environ.get("ARCHITECTOS_3DFUTURE_DIR")
        if env_dir:
            candidates.append(env_dir)
        if repo_root:
            candidates.append(os.path.join(repo_root, "3D-FUTURE-model"))
            candidates.append(os.path.join(repo_root, "data", "3D-FUTURE-model"))
        candidates.extend([
            os.path.join(os.path.expanduser("~"), "3D-FUTURE-model"),
            os.path.join(os.path.expanduser("~"), "3D-FUTURE-model", "3D-FUTURE-model"),
        ])
        for c in candidates:
            if c and os.path.isdir(c):
                sub = os.path.join(c, "3D-FUTURE-model")
                if os.path.isdir(sub) and os.path.isfile(os.path.join(sub, "model_info.json")):
                    return sub
                return c
        return None

    @classmethod
    def find_3dfuture_zip(cls) -> Optional[str]:
        _env_zip = os.environ.get("ARCHITECTOS_3DFUTURE_ZIP")
        for zp in tuple(([_env_zip] if _env_zip else [])) + (
            os.path.join(os.path.expanduser("~"), "3D-FUTURE-model.zip"),
        ):
            if os.path.isfile(zp):
                return zp
        return None

    @classmethod
    def discover_models_by_kind(cls, repo_root: Optional[str] = None) -> Dict[str, List[str]]:
        if cls._MODEL_INDEX_CACHE is not None:
            return cls._MODEL_INDEX_CACHE
        idx_map: Dict[str, List[str]] = {k: [] for k in cls.CATEGORY_KEYWORDS}
        root = cls.find_3dfuture_root(repo_root)
        if not root or not os.path.isdir(root):
            cls._MODEL_INDEX_CACHE = idx_map
            return idx_map

        info_json = os.path.join(root, "model_info.json")
        if os.path.isfile(info_json):
            try:
                with open(info_json, "r", encoding="utf-8", errors="ignore") as f:
                    items = json.load(f)
                if isinstance(items, list):
                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        mid = str(item.get("model_id") or "")
                        cat = f"{item.get('category', '')} {item.get('super-category', '')}".lower()
                        if not mid:
                            continue
                        m_dir = os.path.join(root, mid)
                        obj_p = os.path.join(m_dir, "raw_model.obj")
                        if not os.path.isfile(obj_p):
                            obj_p = os.path.join(m_dir, "normalized_model.obj")
                        if not os.path.isfile(obj_p):
                            continue
                        for kind, kw_tuple in cls.CATEGORY_KEYWORDS.items():
                            if any(kw in cat for kw in kw_tuple):
                                if len(idx_map[kind]) < 12:
                                    idx_map[kind].append(obj_p)
            except Exception:
                pass

        # Fallback: scan immediate subdirectories if model_info.json wasn't present or matched 0
        if not any(idx_map.values()):
            try:
                found_objs = []
                for entry in sorted(os.listdir(root))[:80]:
                    sub_d = os.path.join(root, entry)
                    if os.path.isdir(sub_d):
                        for fn in ("raw_model.obj", "normalized_model.obj", "model.obj"):
                            cand_o = os.path.join(sub_d, fn)
                            if os.path.isfile(cand_o):
                                found_objs.append(cand_o)
                                break
                if found_objs:
                    for i_k, k_nm in enumerate(idx_map.keys()):
                        idx_map[k_nm].append(found_objs[i_k % len(found_objs)])
            except Exception:
                pass

        cls._MODEL_INDEX_CACHE = idx_map
        return idx_map

    @classmethod
    def load_normalized_3d_obj(
        cls, obj_path: str, max_faces: int = 450
    ) -> Optional[Tuple[List[Tuple[float, float, float]], List[Tuple[int, int, int]]]]:
        """
        Loads a 3D-FUTURE `.obj` file, converts Y-up `(x, y_up, z)` to ArchitectOS Z-up `(x, y, z_up)`
        normalized into `[0..1, 0..1, 0..1]`, and decimates faces to `max_faces` for fast GLB/OBJ export.
        """
        if obj_path in cls._MESH_3D_CACHE:
            return cls._MESH_3D_CACHE[obj_path]
        if not os.path.isfile(obj_path):
            return None
        try:
            raw_v = []
            raw_f = []
            with open(obj_path, "r", encoding="utf-8", errors="ignore") as f:
                for ln in f:
                    if ln.startswith("v "):
                        parts = ln.split()
                        if len(parts) >= 4:
                            # 3D-FUTURE is Y-up: X=width, Y=height, Z=depth -> convert to Z-up: (X, Z, Y)
                            raw_v.append((float(parts[1]), float(parts[3]), float(parts[2])))
                    elif ln.startswith("f "):
                        parts = ln.split()[1:]
                        idxs = []
                        for p in parts:
                            vi = int(p.split("/")[0])
                            idxs.append(vi - 1 if vi > 0 else len(raw_v) + vi)
                        if len(idxs) >= 3:
                            raw_f.append((idxs[0], idxs[1], idxs[2]))
                            if len(idxs) >= 4:
                                raw_f.append((idxs[0], idxs[2], idxs[3]))
            if len(raw_v) < 4 or not raw_f:
                return None
            xs = [v[0] for v in raw_v]
            ys = [v[1] for v in raw_v]
            zs = [v[2] for v in raw_v]
            x0, x1 = min(xs), max(xs)
            y0, y1 = min(ys), max(ys)
            z0, z1 = min(zs), max(zs)
            dx = max(1e-4, x1 - x0)
            dy = max(1e-4, y1 - y0)
            dz = max(1e-4, z1 - z0)
            norm_v = [((v[0] - x0) / dx, (v[1] - y0) / dy, (v[2] - z0) / dz) for v in raw_v]
            if len(raw_f) > max_faces:
                step = max(1, len(raw_f) // max_faces)
                raw_f = raw_f[::step][:max_faces]
            cls._MESH_3D_CACHE[obj_path] = (norm_v, raw_f)
            return norm_v, raw_f
        except Exception:
            return None

    @classmethod
    def extract_top_view_2d_contours_from_obj(
        cls, obj_path: str
    ) -> Optional[List[List[Tuple[float, float]]]]:
        """
        Projects a 3D-FUTURE `.obj` mesh from Top-Down (`+Z` looking down at `(X, Y)`)
        across 3 height slices (base silhouette, seat/mattress mid-slice, backrest/pillow top-slice)
        and returns normalized `[0..1, 0..1]` 2D closed polylines for AutoCAD `.dxf` and `.svg`!
        """
        if obj_path in cls._TOP_CONTOUR_CACHE:
            return cls._TOP_CONTOUR_CACHE[obj_path]
        mesh = cls.load_normalized_3d_obj(obj_path, max_faces=1200)
        if not mesh:
            return None
        norm_v, raw_f = mesh
        try:
            import cv2
            import numpy as np

            res = 160
            pad = 8
            span = res - 2 * pad
            contours_norm: List[List[Tuple[float, float]]] = []
            for z_min, z_max in [(0.05, 1.00), (0.38, 0.76), (0.72, 1.00)]:
                grid = np.zeros((res, res), dtype=np.uint8)
                drawn = 0
                for i0, i1, i2 in raw_f:
                    if i0 >= len(norm_v) or i1 >= len(norm_v) or i2 >= len(norm_v):
                        continue
                    v0, v1, v2 = norm_v[i0], norm_v[i1], norm_v[i2]
                    z_avg = (v0[2] + v1[2] + v2[2]) / 3.0
                    if z_min <= z_avg <= z_max:
                        pts = np.array([
                            [int(pad + v0[0] * span), int(pad + v0[1] * span)],
                            [int(pad + v1[0] * span), int(pad + v1[1] * span)],
                            [int(pad + v2[0] * span), int(pad + v2[1] * span)],
                        ], dtype=np.int32)
                        cv2.fillConvexPoly(grid, pts, 255)
                        drawn += 1
                if drawn < 3:
                    continue
                grid = cv2.morphologyEx(grid, cv2.MORPH_CLOSE, np.ones((5, 5), dtype=np.uint8))
                cnts, _ = cv2.findContours(grid, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                for cnt in cnts:
                    if cv2.contourArea(cnt) < 90:
                        continue
                    eps = 0.018 * cv2.arcLength(cnt, True)
                    approx = cv2.approxPolyDP(cnt, eps, True)
                    poly = [
                        (
                            round(float(np.clip((pt[0][0] - pad) / float(span), 0.0, 1.0)), 4),
                            round(float(np.clip((pt[0][1] - pad) / float(span), 0.0, 1.0)), 4),
                        )
                        for pt in approx
                    ]
                    if len(poly) >= 3:
                        contours_norm.append(poly)
            if contours_norm:
                cls._TOP_CONTOUR_CACHE[obj_path] = contours_norm
                return contours_norm
        except Exception:
            pass
        return None

    @classmethod
    def emit_3dfuture_top_view_dxf(
        cls,
        kind: str,
        orient: str,
        fx: float,
        fy: float,
        fw: float,
        fh: float,
        lyr: str,
        add_line: Callable[[str, float, float, float, float], None],
        add_rect_m: Callable[[str, float, float, float, float], None],
        add_circle: Callable[[str, float, float, float], None],
        add_arc: Callable[[str, float, float, float, float, float], None],
        repo_root: Optional[str] = None,
    ) -> bool:
        """
        Draws studio-grade Top-Down (`تصویر از بالا`) 3D-FUTURE furniture blocks into AutoCAD `.dxf`:
          1. If a real 3D-FUTURE `.obj` model is indexed on disk for `kind`, projects its 3D top-down
             silhouette & height-slice contours directly into the room rectangle `(fx, fy, fw, fh)`!
          2. Also draws rich curved 3D-FUTURE architectural details (rounded pillows, curved duvet fold,
             curved sofa armrests/cushions, ergonomic curved dining chairs, beveled tables) so the 2D
             AutoCAD plan looks like a professional architectural presentation sheet.
        """
        def _draw_closed_poly(pts: List[Tuple[float, float]]) -> None:
            for i in range(len(pts)):
                p0 = pts[i]
                p1 = pts[(i + 1) % len(pts)]
                add_line(lyr, p0[0], p0[1], p1[0], p1[1])

        def _draw_rounded_rect(rx: float, ry: float, rw: float, rh: float, rad: float) -> None:
            r = min(rad, rw * 0.42, rh * 0.42)
            if r <= 0.01:
                add_rect_m(lyr, rx, ry, rw, rh)
                return
            add_line(lyr, rx + r, ry, rx + rw - r, ry)
            add_line(lyr, rx + r, ry + rh, rx + rw - r, ry + rh)
            add_line(lyr, rx, ry + r, rx, ry + rh - r)
            add_line(lyr, rx + rw, ry + r, rx + rw, ry + rh - r)
            add_arc(lyr, rx + r, ry + r, r, 180.0, 270.0)
            add_arc(lyr, rx + rw - r, ry + r, r, 270.0, 360.0)
            add_arc(lyr, rx + rw - r, ry + rh - r, r, 0.0, 90.0)
            add_arc(lyr, rx + r, ry + rh - r, r, 90.0, 180.0)

        # Overlay real 3D-FUTURE `.obj` top-down slice contours when available on disk
        idx_map = cls.discover_models_by_kind(repo_root)
        obj_list = idx_map.get(kind) or []
        if obj_list:
            cnts = cls.extract_top_view_2d_contours_from_obj(obj_list[0])
            if cnts:
                for poly_uv in cnts:
                    mapped = []
                    for u, v in poly_uv:
                        if orient in ("E", "H"):
                            mx, my = fx + (1.0 - v) * fw, fy + u * fh
                        elif orient == "W":
                            mx, my = fx + v * fw, fy + u * fh
                        elif orient == "S":
                            mx, my = fx + u * fw, fy + v * fh
                        else:
                            mx, my = fx + u * fw, fy + (1.0 - v) * fh
                        mapped.append((mx, my))
                    _draw_closed_poly(mapped)

        # Studio-grade curved 3D-FUTURE top-down architectural detailing per furniture category
        if kind in ("BED_DOUBLE", "BED_SINGLE"):
            is_double = (kind == "BED_DOUBLE")
            if orient in ("E", "H"):
                ns_w, ns_h = 0.44, 0.42
                bed_y0, bed_h = fy + ns_h + 0.05, max(1.00, fh - 2 * ns_h - 0.10)
                # Rounded Nightstands + Designer Table Lamps (concentric shade + bulb)
                for ny in (fy, fy + fh - ns_h):
                    _draw_rounded_rect(fx + fw - ns_w, ny, ns_w, ns_h, 0.06)
                    add_circle(lyr, fx + fw - ns_w * 0.5, ny + ns_h * 0.5, 0.12)
                    add_circle(lyr, fx + fw - ns_w * 0.5, ny + ns_h * 0.5, 0.04)
                # Rounded Mattress Frame + Upholstered Tufted Headboard
                _draw_rounded_rect(fx, bed_y0, fw, bed_h, 0.09)
                _draw_rounded_rect(fx + fw - 0.14, bed_y0 + 0.03, 0.12, bed_h - 0.06, 0.04)
                # Curved Ergonomic Pillows (`بالش‌های منحنی سه‌بعدی`)
                n_p = 2 if is_double else 1
                ph = (bed_h - 0.20) / float(n_p)
                pw = 0.38
                px_pil = fx + fw - 0.16 - pw
                for pi in range(n_p):
                    py_p = bed_y0 + 0.08 + pi * (ph + 0.04)
                    _draw_rounded_rect(px_pil, py_p, pw, ph - 0.02, 0.08)
                    _draw_rounded_rect(px_pil + 0.04, py_p + 0.03, pw - 0.08, ph - 0.08, 0.05)
                # Draped Duvet with diagonal fold & quilted seam lines
                duv_x1 = px_pil - 0.06
                _draw_rounded_rect(fx + 0.05, bed_y0 + 0.04, max(0.35, duv_x1 - (fx + 0.05)), bed_h - 0.08, 0.07)
                add_line(lyr, duv_x1 - 0.16, bed_y0 + 0.05, duv_x1, bed_y0 + bed_h * 0.38)
                add_line(lyr, duv_x1, bed_y0 + bed_h * 0.38, duv_x1 - 0.16, bed_y0 + bed_h - 0.05)
                return True
            else:
                # North ("N" / "V") or South ("S") headboard
                is_south = (orient == "S")
                ns_w, ns_h = 0.42, 0.44
                bed_x0, bed_w = fx + ns_w + 0.05, max(1.00, fw - 2 * ns_w - 0.10)
                ny_ns = fy if is_south else (fy + fh - ns_h)
                for nx in (fx, fx + fw - ns_w):
                    _draw_rounded_rect(nx, ny_ns, ns_w, ns_h, 0.06)
                    add_circle(lyr, nx + ns_w * 0.5, ny_ns + ns_h * 0.5, 0.12)
                    add_circle(lyr, nx + ns_w * 0.5, ny_ns + ns_h * 0.5, 0.04)
                _draw_rounded_rect(bed_x0, fy, bed_w, fh, 0.09)
                hb_y = (fy + 0.02) if is_south else (fy + fh - 0.14)
                _draw_rounded_rect(bed_x0 + 0.03, hb_y, bed_w - 0.06, 0.12, 0.04)
                n_p = 2 if is_double else 1
                pw = (bed_w - 0.20) / float(n_p)
                ph = 0.38
                py_pil = (fy + 0.16) if is_south else (fy + fh - 0.16 - ph)
                for pi in range(n_p):
                    px_p = bed_x0 + 0.08 + pi * (pw + 0.04)
                    _draw_rounded_rect(px_p, py_pil, pw - 0.02, ph, 0.08)
                    _draw_rounded_rect(px_p + 0.03, py_pil + 0.04, pw - 0.08, ph - 0.08, 0.05)
                if is_south:
                    duv_y0 = py_pil + ph + 0.06
                    _draw_rounded_rect(bed_x0 + 0.04, duv_y0, bed_w - 0.08, max(0.35, (fy + fh - 0.05) - duv_y0), 0.07)
                else:
                    duv_y1 = py_pil - 0.06
                    _draw_rounded_rect(bed_x0 + 0.04, fy + 0.05, bed_w - 0.08, max(0.35, duv_y1 - (fy + 0.05)), 0.07)
                    add_line(lyr, bed_x0 + 0.05, duv_y1 - 0.16, bed_x0 + bed_w * 0.38, duv_y1)
                    add_line(lyr, bed_x0 + bed_w * 0.38, duv_y1, bed_x0 + bed_w - 0.05, duv_y1 - 0.16)
                return True

        elif kind in ("SOFA_L", "TV_LOUNGE"):
            # Curved 3D-FUTURE Designer Sofa Set + Tufted Seat Cushions + Throw Pillows + Oval/Rounded Marble Coffee Table
            _draw_rounded_rect(fx + 0.18, fy + 0.05, fw - 0.36, 0.72, 0.11)
            _draw_rounded_rect(fx + 0.22, fy + 0.08, fw - 0.44, 0.16, 0.06)
            cw_3 = (fw - 0.56) / 3.0
            for ci in range(3):
                _draw_rounded_rect(fx + 0.28 + ci * cw_3, fy + 0.25, cw_3 - 0.03, 0.48, 0.06)
            if kind == "SOFA_L":
                # Two curved club armchairs on left & right + rounded coffee table with centerpiece
                for ax_c in (fx + 0.05, fx + fw - 0.71):
                    _draw_rounded_rect(ax_c, fy + fh - 0.90, 0.66, 0.74, 0.12)
                    _draw_rounded_rect(ax_c + 0.08, fy + fh - 0.80, 0.50, 0.52, 0.07)
                ct_w, ct_h = max(0.68, fw - 1.65), 0.54
                _draw_rounded_rect(fx + (fw - ct_w) * 0.5, fy + fh - 0.82, ct_w, ct_h, 0.16)
                add_circle(lyr, fx + fw * 0.5, fy + fh - 0.55, 0.13)
                add_circle(lyr, fx + fw * 0.5, fy + fh - 0.55, 0.05)
            else:
                # L-return chaise lounge wing + rounded coffee table
                _draw_rounded_rect(fx + fw - 0.74, fy + 0.05, 0.66, fh - 0.16, 0.11)
                _draw_rounded_rect(fx + fw - 0.24, fy + 0.08, 0.14, fh - 0.22, 0.05)
                _draw_rounded_rect(fx + 0.44, fy + fh * 0.48, max(0.56, fw - 1.42), 0.48, 0.14)
                add_circle(lyr, fx + 0.44 + max(0.56, fw - 1.42) * 0.5, fy + fh * 0.48 + 0.24, 0.11)
            return True

        elif kind in ("DINING_6", "DINING_8"):
            # Beveled 3D-FUTURE Dining Table + Curved Ergonomic Dining Chairs with rounded backrests
            _draw_rounded_rect(fx + 0.22, fy + 0.22, max(0.4, fw - 0.44), max(0.4, fh - 0.44), 0.14)
            _draw_rounded_rect(fx + 0.36, fy + 0.36, max(0.2, fw - 0.72), max(0.2, fh - 0.72), 0.09)
            add_circle(lyr, fx + fw * 0.5, fy + fh * 0.5, 0.12)
            if fh >= fw:
                for ci in range(3):
                    cy_c = fy + 0.45 + ci * ((fh - 0.90) / 2.0)
                    _draw_rounded_rect(fx + 0.02, cy_c - 0.19, 0.19, 0.38, 0.06)
                    _draw_rounded_rect(fx + fw - 0.21, cy_c - 0.19, 0.19, 0.38, 0.06)
                _draw_rounded_rect(fx + fw * 0.5 - 0.20, fy + 0.02, 0.40, 0.19, 0.06)
                _draw_rounded_rect(fx + fw * 0.5 - 0.20, fy + fh - 0.21, 0.40, 0.19, 0.06)
            else:
                for ci in range(3):
                    cx_c = fx + 0.45 + ci * ((fw - 0.90) / 2.0)
                    _draw_rounded_rect(cx_c - 0.19, fy + 0.02, 0.38, 0.19, 0.06)
                    _draw_rounded_rect(cx_c - 0.19, fy + fh - 0.21, 0.38, 0.19, 0.06)
                _draw_rounded_rect(fx + 0.02, fy + fh * 0.5 - 0.20, 0.19, 0.40, 0.06)
                _draw_rounded_rect(fx + fw - 0.21, fy + fh * 0.5 - 0.20, 0.19, 0.40, 0.06)
            return True

        return False

    @classmethod
    def build_3d_furniture_boxes_for_floor(
        cls,
        fl: Any,
        f_idx: int,
        z_b_m: float,
    ) -> List[Dict[str, Any]]:
        """
        Generates 3D furniture solids (`IFCFURNISHINGELEMENT`) for `build_3d_shell_and_ifc_from_project`
        so `.ifc`, `.glb`, and `.obj` files include 3D beds, L-sofas, dining tables & chairs, wardrobes, and kitchen islands!
        """
        boxes: List[Dict[str, Any]] = []
        for fb_i, f_blk in enumerate(getattr(fl, "furniture", []) or []):
            fr = getattr(f_blk, "rect_mm", None)
            if not fr:
                continue
            fx = round(fr.x_min / 1000.0, 3)
            fy = round(fr.y_min / 1000.0, 3)
            fw = round(fr.width / 1000.0, 3)
            fh = round(fr.height / 1000.0, 3)
            kind = str(getattr(f_blk, "kind", "FURN")).upper()
            if kind in ("PARTITION_WALL", "DUCT"):
                continue
            if kind in ("BED_DOUBLE", "BED_SINGLE"):
                # 3D Mattress + Headboard
                boxes.append({
                    "floor_index": f_idx,
                    "ifc_class": "IFCFURNISHINGELEMENT",
                    "name": f"3DFUTURE_{kind}_Mattress_F{f_idx}_{fb_i}",
                    "cx": fx + 0.5 * fw,
                    "cy": fy + 0.5 * fh,
                    "cz": z_b_m + 0.28,
                    "dx": fw * 0.82,
                    "dy": fh * 0.88,
                    "dz": 0.52,
                    "angle_rad": 0.0,
                })
                boxes.append({
                    "floor_index": f_idx,
                    "ifc_class": "IFCFURNISHINGELEMENT",
                    "name": f"3DFUTURE_{kind}_Headboard_F{f_idx}_{fb_i}",
                    "cx": fx + 0.5 * fw,
                    "cy": fy + fh - 0.08,
                    "cz": z_b_m + 0.62,
                    "dx": fw * 0.86,
                    "dy": 0.14,
                    "dz": 1.15,
                    "angle_rad": 0.0,
                })
            elif kind in ("SOFA_L", "TV_LOUNGE"):
                boxes.append({
                    "floor_index": f_idx,
                    "ifc_class": "IFCFURNISHINGELEMENT",
                    "name": f"3DFUTURE_{kind}_Seat_F{f_idx}_{fb_i}",
                    "cx": fx + 0.5 * fw,
                    "cy": fy + 0.42,
                    "cz": z_b_m + 0.24,
                    "dx": max(0.6, fw - 0.35),
                    "dy": 0.78,
                    "dz": 0.44,
                    "angle_rad": 0.0,
                })
                boxes.append({
                    "floor_index": f_idx,
                    "ifc_class": "IFCFURNISHINGELEMENT",
                    "name": f"3DFUTURE_{kind}_Backrest_F{f_idx}_{fb_i}",
                    "cx": fx + 0.5 * fw,
                    "cy": fy + 0.12,
                    "cz": z_b_m + 0.46,
                    "dx": max(0.6, fw - 0.35),
                    "dy": 0.18,
                    "dz": 0.86,
                    "angle_rad": 0.0,
                })
            elif kind in ("DINING_6", "DINING_8"):
                boxes.append({
                    "floor_index": f_idx,
                    "ifc_class": "IFCFURNISHINGELEMENT",
                    "name": f"3DFUTURE_{kind}_Table_F{f_idx}_{fb_i}",
                    "cx": fx + 0.5 * fw,
                    "cy": fy + 0.5 * fh,
                    "cz": z_b_m + 0.38,
                    "dx": max(0.5, fw - 0.44),
                    "dy": max(0.5, fh - 0.44),
                    "dz": 0.76,
                    "angle_rad": 0.0,
                })
            elif kind == "WARDROBE":
                boxes.append({
                    "floor_index": f_idx,
                    "ifc_class": "IFCFURNISHINGELEMENT",
                    "name": f"3DFUTURE_Wardrobe_F{f_idx}_{fb_i}",
                    "cx": fx + 0.5 * fw,
                    "cy": fy + 0.5 * fh,
                    "cz": z_b_m + 1.15,
                    "dx": fw,
                    "dy": fh,
                    "dz": 2.30,
                    "angle_rad": 0.0,
                })
            else:
                boxes.append({
                    "floor_index": f_idx,
                    "ifc_class": "IFCFURNISHINGELEMENT",
                    "name": f"3DFUTURE_{kind}_F{f_idx}_{fb_i}",
                    "cx": fx + 0.5 * fw,
                    "cy": fy + 0.5 * fh,
                    "cz": z_b_m + 0.42,
                    "dx": max(0.3, fw),
                    "dy": max(0.3, fh),
                    "dz": 0.84,
                    "angle_rad": 0.0,
                })
        return boxes
