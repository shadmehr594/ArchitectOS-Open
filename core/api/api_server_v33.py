# ==========================================================
# ArchitectOS API Server v33
# Unified Runtime HTTP Gateway
# API Layer
# ==========================================================


from flask import Flask, request, jsonify
from flask_cors import CORS

from core.chat.chat_runtime_v31 import chat_runtime



class ArchitectOSAPI:


    VERSION = "33.0"



    def __init__(self):

        self.app = Flask(
            __name__
        )

        # Enable UI <-> API communication
        CORS(
            self.app
        )

        self.register_routes()


        print(
            "🌐 ARCHITECTOS API v33 ONLINE"
        )



    # ======================================================
    # ROUTES
    # ======================================================


    def register_routes(
        self
    ):


        # --------------------------------------------------
        # HEALTH
        # --------------------------------------------------

        @self.app.route(
            "/health",
            methods=["GET"]
        )
        def health():


            return jsonify({

                "engine":
                    "ArchitectOS",

                "api_version":
                    self.VERSION,

                "status":
                    "online"

            })



        # --------------------------------------------------
        # CHAT
        # --------------------------------------------------

        @self.app.route(
            "/chat",
            methods=["POST"]
        )
        def chat():


            data = request.json or {}

            message = data.get(
                "message",
                ""
            )


            result = chat_runtime.run(
                message
            )


            return jsonify(
                result
            )



        # --------------------------------------------------
        # DESIGN
        # --------------------------------------------------

        @self.app.route(
            "/design",
            methods=["POST"]
        )
        def design():


            data = request.json or {}

            prompt = data.get(
                "message",
                ""
            )


            result = chat_runtime.run(
                prompt
            )


            return jsonify(
                result
            )



        # --------------------------------------------------
        # IMAGE
        # --------------------------------------------------

        @self.app.route(
            "/image",
            methods=["POST"]
        )
        def image():


            data = request.json or {}

            prompt = data.get(
                "message",
                ""
            )


            result = chat_runtime.run(
                prompt
            )


            return jsonify(
                result
            )



        # --------------------------------------------------
        # UNIFIED RUN
        # --------------------------------------------------

        @self.app.route(
            "/run",
            methods=["POST"]
        )
        def run():


            data = request.json or {}


            mode = data.get(
                "mode",
                "chat"
            )


            message = data.get(
                "message",
                ""
            )


            result = chat_runtime.run(
                message
            )


            return jsonify({

                "api_version":
                    self.VERSION,


                "mode":
                    mode,


                "result":
                    result

            })



    # ======================================================
    # START
    # ======================================================


    def run(
        self,
        host="127.0.0.1",
        port=8000
    ):


        self.app.run(

            host=host,

            port=port,

            debug=False

        )





# ==========================================================
# SINGLETON
# ==========================================================


api_server = ArchitectOSAPI()





# [ARCHITECTOS_V27_1_KROCKI_UPLOAD_INTERCEPTOR]
try:
    from flask import request as _arch_req, jsonify as _arch_jsonify
    try:
        app.config['MAX_CONTENT_LENGTH'] = None
    except Exception:
        pass

    def _resolve_arch_repo_root() -> str:
        import os
        import sys
        here_d = os.path.dirname(os.path.abspath(__file__))
        cand = here_d
        for _ in range(5):
            if os.path.isdir(os.path.join(cand, "core")) and os.path.isdir(os.path.join(cand, "ui")):
                if cand not in sys.path:
                    sys.path.insert(0, cand)
                return cand
            parent = os.path.dirname(cand)
            if parent == cand:
                break
            cand = parent
        if here_d not in sys.path:
            sys.path.insert(0, here_d)
        from core.site.krocki_cad_reader_v27 import _resolve_true_repo_root
        root_r = _resolve_true_repo_root(here_d)
        if root_r not in sys.path:
            sys.path.insert(0, root_r)
        return root_r

    def _resolve_real_existing_project_folder(repo_root: str, clean_pid: str, project_sig: str = "") -> tuple:
        """
        v66.0 Safe Project Folder Resolver:
        NEVER creates non-native `project_default` or `project_proj_*` folders inside `data/projects/`
        (which caused `Could not open the project.` on the native Recent Projects dashboard).
        Maps `"default"` or `"proj_10_37"` to the matching existing `project_<hex>` folder in `data/projects/`,
        or falls back to `data/site_cache/<p_folder>` if no native project folder exists yet.
        """
        import json
        import os
        raw_pid = str(clean_pid or "default").strip()
        if raw_pid.lower() in ("", "null", "none", "undefined"):
            raw_pid = "default"
        cand_folder = raw_pid if raw_pid.startswith("project_") else f"project_{raw_pid}"
        projs_root = os.path.join(repo_root, "data", "projects")
        os.makedirs(projs_root, exist_ok=True)

        # If cand_folder is an existing native project folder (not project_default / project_proj_*), use it directly
        cand_dir = os.path.join(projs_root, cand_folder)
        if (
            os.path.isdir(cand_dir)
            and cand_folder not in ("project_default", "project_v337b_probe")
            and not cand_folder.startswith("project_proj_")
        ):
            return cand_folder, cand_dir

        # Extract numeric signature like "10.37" from project_sig or from "proj_10_37"
        sig_norm = str(project_sig or "").strip()
        if not sig_norm and raw_pid.startswith("proj_"):
            sig_norm = raw_pid[5:].replace("_", ".")
        elif not sig_norm and cand_folder.startswith("project_proj_"):
            sig_norm = cand_folder[len("project_proj_"):].replace("_", ".")

        native_cands = []
        if os.path.isdir(projs_root):
            for pn in os.listdir(projs_root):
                pd = os.path.join(projs_root, pn)
                if (
                    pn.startswith("project_")
                    and pn not in ("project_default", "project_v337b_probe")
                    and not pn.startswith("project_proj_")
                    and os.path.isdir(pd)
                ):
                    # Check if project.json or session_state.json matches sig_norm
                    sig_match = False
                    if sig_norm:
                        for meta_fn in ("project.json", "metadata.json", "session_state.json", "site/active_external_plan.json"):
                            mp = os.path.join(pd, meta_fn)
                            if os.path.isfile(mp):
                                try:
                                    with open(mp, "r", encoding="utf-8", errors="ignore") as mf:
                                        mtxt = mf.read(4096)
                                    if f'"{sig_norm}"' in mtxt or f">{sig_norm}<" in mtxt:
                                        sig_match = True
                                        break
                                except Exception:
                                    pass
                    st_f = os.path.join(pd, "project.json")
                    if not os.path.isfile(st_f):
                        st_f = os.path.join(pd, "session_state.json")
                    mt = os.path.getmtime(st_f) if os.path.isfile(st_f) else os.path.getmtime(pd)
                    native_cands.append((1 if sig_match else 0, mt, pn, pd))

        if native_cands:
            native_cands.sort(key=lambda x: (x[0], x[1]), reverse=True)
            return native_cands[0][2], native_cands[0][3]

        # If no native project_* exists in data/projects/ (e.g. unit test), use data/site_cache/<cand_folder>
        # so we NEVER pollute data/projects/ with non-native folders!
        if cand_folder in ("project_default", "project_v337b_probe") or cand_folder.startswith("project_proj_"):
            fallback_dir = os.path.join(repo_root, "data", "site_cache", cand_folder)
            os.makedirs(fallback_dir, exist_ok=True)
            return cand_folder, fallback_dir

        os.makedirs(cand_dir, exist_ok=True)
        return cand_folder, cand_dir

    def _sync_project_renders_and_assets(repo_root: str, project_id: str) -> None:
        import os
        import shutil
        clean_pid = str(project_id or "").strip()
        if clean_pid.lower() in ("", "null", "none", "undefined"):
            return
        p_folder, proj_dir = _resolve_real_existing_project_folder(repo_root, clean_pid)
        dir_a = os.path.join(repo_root, "outputs", "plans", p_folder, "renders")
        dir_b = os.path.join(proj_dir, "renders")
        os.makedirs(dir_a, exist_ok=True)
        os.makedirs(dir_b, exist_ok=True)
        for src_d, dst_d in ((dir_a, dir_b), (dir_b, dir_a)):
            try:
                for fn in os.listdir(src_d):
                    fn_l = fn.lower()
                    if fn_l.startswith("_scaffold_") or "_depth" in fn_l or "_lineart" in fn_l or "_comfy" in fn_l:
                        continue
                    if fn_l.startswith("render_") and fn_l.endswith((".png", ".jpg")):
                        sp = os.path.join(src_d, fn)
                        dp = os.path.join(dst_d, fn)
                        if os.path.isfile(sp) and (not os.path.isfile(dp) or os.path.getmtime(sp) > os.path.getmtime(dp) + 0.5):
                            shutil.copy2(sp, dp)
            except Exception:
                pass

    def _sync_krocki_into_project_session(repo_root: str, project_id: str) -> None:
        import json
        import os
        from core.site.krocki_cad_reader_v27 import (
            load_active_krocki_state,
            load_active_external_plan_state,
        )

        clean_pid = str(project_id or "").strip()
        if clean_pid.lower() in ("", "null", "none", "undefined"):
            return
        krocki = load_active_krocki_state(repo_root, clean_pid)
        ext_plan = load_active_external_plan_state(repo_root, clean_pid)
        if not isinstance(krocki, dict) and not isinstance(ext_plan, dict):
            return
        p_folder, proj_dir = _resolve_real_existing_project_folder(repo_root, clean_pid)
        for state_file in (
            os.path.join(proj_dir, "session_state.json"),
            os.path.join(repo_root, "outputs", "plans", p_folder, "session_state.json"),
        ):
            state_data = {}
            if os.path.isfile(state_file):
                try:
                    with open(state_file, "r", encoding="utf-8") as sf:
                        state_data = json.load(sf)
                except Exception:
                    state_data = {}
            if isinstance(krocki, dict):
                state_data["active_site_krocki"] = krocki
                prev_p = state_data.get("active_plan_params")
                if isinstance(prev_p, dict):
                    prev_p["site_width_mm"] = int(round(float(krocki.get("width_m", 10.0)) * 1000))
                    prev_p["site_length_mm"] = int(round(float(krocki.get("length_m", 20.0)) * 1000))
                    prev_p["site_area_m2"] = round(float(krocki.get("site_area_m2", 200.0)), 2)
                    prev_p["krocki_polygon_mm"] = krocki.get("polygon_vertices_mm") or []
                    prev_p["krocki_source_file"] = krocki.get("source_file")
                    prev_p["krocki_is_irregular"] = bool(krocki.get("is_irregular_polygon", False))
                    prev_p["street_sides"] = krocki.get("street_sides") or ["SOUTH"]
                    prev_p["party_wall_sides"] = krocki.get("party_wall_sides") or ["NORTH", "EAST", "WEST"]
                    prev_p["boundary_neighbors"] = krocki.get("boundary_neighbors") or {}
                    prev_p["south_y_west_mm"] = int(krocki.get("south_y_west_mm", 0))
                    prev_p["south_y_east_mm"] = int(krocki.get("south_y_east_mm", 0))
                    prev_p["north_y_west_mm"] = int(krocki.get("north_y_west_mm", prev_p["site_length_mm"]))
                    prev_p["north_y_east_mm"] = int(krocki.get("north_y_east_mm", prev_p["site_length_mm"]))
            if isinstance(ext_plan, dict):
                state_data["active_external_plan"] = ext_plan
                prev_p = state_data.get("active_plan_params")
                if not isinstance(prev_p, dict):
                    prev_p = {}
                    state_data["active_plan_params"] = prev_p
                tot_fl = int(ext_plan.get("total_floors", 2))
                typ_str = str(ext_plan.get("typology", "DUPLEX_2FLOOR" if tot_fl == 2 else ("MULTIFLOOR_RESIDENTIAL" if tot_fl >= 3 else "VILLA_1FLOOR")))
                prev_p["typology"] = typ_str
                prev_p["is_duplex"] = (typ_str == "DUPLEX_2FLOOR")
                prev_p["floor_count"] = max(2, tot_fl - 1) if typ_str == "MULTIFLOOR_RESIDENTIAL" else tot_fl
                prev_p["building_placement"] = str(ext_plan.get("building_placement") or ("SOUTH" if ext_plan.get("custom_facade_profile") else "NORTH"))
                prev_p["site_width_mm"] = int(round(float(ext_plan.get("width_m", 10.0)) * 1000))
                prev_p["site_length_mm"] = int(round(float(ext_plan.get("length_m", 20.0)) * 1000))
                prev_p["coverage_ratio"] = float(ext_plan.get("coverage_ratio", 0.60 if typ_str == "MULTIFLOOR_RESIDENTIAL" else 0.65))
                prev_p["south_cantilever_mm"] = int(round(float(ext_plan.get("cantilever_m", 1.2 if typ_str == "MULTIFLOOR_RESIDENTIAL" else 1.0)) * 1000))
                if ext_plan.get("universal_facade_spec"):
                    prev_p["universal_facade_spec"] = ext_plan["universal_facade_spec"]
                if ext_plan.get("custom_facade_profile"):
                    prev_p["custom_facade_profile"] = ext_plan["custom_facade_profile"]
                else:
                    prev_p.pop("custom_facade_profile", None)
                for _rs_d in (prev_p.get("active_render_state"), state_data.get("active_render_state")):
                    if isinstance(_rs_d, dict):
                        if ext_plan.get("universal_facade_spec"):
                            _rs_d["universal_facade_spec"] = ext_plan["universal_facade_spec"]
                        if ext_plan.get("custom_facade_profile"):
                            _rs_d["custom_facade_profile"] = ext_plan["custom_facade_profile"]
            try:
                os.makedirs(os.path.dirname(state_file), exist_ok=True)
                with open(state_file, "w", encoding="utf-8") as sf:
                    json.dump(state_data, sf, ensure_ascii=False, indent=2)
            except Exception:
                pass

    def _is_3d_facade_render_chat_command(text: str, prev_params: dict = None) -> bool:
        from core.planning.multifloor_v1.engine.nl_design_parser import is_3d_render_or_render_edit_prompt
        return is_3d_render_or_render_edit_prompt(text or "", prev_params)

    def _handle_plan_locked_3d_render_request(jbody: dict):
      try:
        return _handle_plan_locked_3d_render_request_inner(jbody)
      except Exception as _core_err:
        import traceback as _tb
        _err_msg = f"⚠️ خطا در رندر سه‌بعدی: {_core_err}"
        return _arch_jsonify({"status": "error", "ok": False, "reply": _err_msg, "message": _err_msg, "error": str(_core_err), "trace": _tb.format_exc()[-600:]}), 200

    def _handle_plan_locked_3d_render_request_inner(jbody: dict):
        import base64
        import json
        import os
        import shutil
        import uuid
        from core.site.krocki_cad_reader_v27 import load_active_krocki_state
        from core.planning.multifloor_v1.engine.nl_design_parser import (
            parse_architectural_prompt,
            update_geometry_locked_render_state,
        )
        from core.planning.multifloor_v1.engine.architectural_synthesizer import ParametricArchitecturalSynthesizer
        from core.planning.multifloor_v1.engine.comfyui_bridge import ComfyUIRenderBridge

        repo_root = _resolve_arch_repo_root()
        user_msg = str(jbody.get("message") or jbody.get("prompt") or jbody.get("text") or "").strip()
        ref_id_in = str(
            jbody.get("reference_id")
            or jbody.get("reference")
            or jbody.get("style_reference")
            or jbody.get("references")
            or _arch_req.args.get("reference_id")
            or ""
        ).strip()
        if not ref_id_in:
            import re as _re_ref
            _m_ref = _re_ref.search(r"\b(AR-\d+|CLASSICAL_REF_\d+)\b", user_msg, _re_ref.I)
            if _m_ref:
                ref_id_in = _m_ref.group(1).upper()
        if ref_id_in and ref_id_in not in user_msg:
            user_msg = (user_msg + " " + ref_id_in).strip()
        raw_q = str(
            jbody.get("quality")
            or jbody.get("render_quality")
            or jbody.get("preset")
            or jbody.get("quality_preset")
            or _arch_req.args.get("quality")
            or "draft"
        ).strip().lower()
        if raw_q in ("draft", "fast", "preview", "درفت", "سریع"):
            quality = "draft"
        elif any(w in user_msg.lower() for w in ("کیفیت بالا", "نهایی", "high", "final", "ultra")):
            quality = "high"
        elif any(w in user_msg.lower() for w in ("سریع", "درفت", "تست", "draft", "fast", "preview")):
            quality = "draft"
        elif raw_q in ("auto", ""):
            quality = "quality"
        else:
            quality = raw_q
        clean_pid = str(jbody.get("project_id") or _arch_req.args.get("project_id") or "default").strip()
        if clean_pid.lower() in ("", "null", "none", "undefined"):
            clean_pid = "default"
        proj_sig_early = str(jbody.get("project_sig") or _arch_req.args.get("project_sig") or "").strip()
        p_folder, proj_dir_real = _resolve_real_existing_project_folder(repo_root, clean_pid, project_sig=proj_sig_early)
        _sync_krocki_into_project_session(repo_root, p_folder)

        st_path_plans = os.path.join(repo_root, "outputs", "plans", p_folder, "session_state.json")
        st_path_data = os.path.join(proj_dir_real, "session_state.json")
        plan_params = None
        full_state_obj = {}
        for st_path in (st_path_plans, st_path_data):
            if os.path.isfile(st_path):
                try:
                    with open(st_path, "r", encoding="utf-8") as sf:
                        st_obj = json.load(sf)
                    if isinstance(st_obj.get("active_plan_params"), dict):
                        full_state_obj = dict(st_obj)
                        plan_params = dict(st_obj["active_plan_params"])
                        break
                except Exception:
                    pass

        from core.site.krocki_cad_reader_v27 import load_active_external_plan_state, save_active_external_plan_state
        proj_sig_req = str(jbody.get("project_sig") or _arch_req.args.get("project_sig") or "").strip()
        sel_file_req = str(jbody.get("selected_file") or _arch_req.args.get("selected_file") or "").strip()
        upload_id_req = str(jbody.get("upload_id") or _arch_req.args.get("upload_id") or "").strip()
        krocki = load_active_krocki_state(repo_root, clean_pid)
        ext_plan_now = None
        if upload_id_req:
            _up_jp = os.path.join(repo_root, "data", "site_cache", f"upload_{upload_id_req}.json")
            if os.path.isfile(_up_jp):
                try:
                    with open(_up_jp, "r", encoding="utf-8") as _uf:
                        ext_plan_now = json.load(_uf)
                except Exception:
                    ext_plan_now = None
        if not isinstance(ext_plan_now, dict) or not ext_plan_now.get("total_floors"):
            ext_plan_now = load_active_external_plan_state(repo_root, p_folder, project_sig=proj_sig_req)
        if (
            not isinstance(ext_plan_now, dict)
            or not ext_plan_now.get("total_floors")
            or (sel_file_req and str(ext_plan_now.get("original_filename") or "").lower() != sel_file_req.lower())
            or (upload_id_req and str(ext_plan_now.get("upload_id") or "") != upload_id_req)
        ):
            _act_fb, _ = _resolve_latest_active_ext_plan_json(
                repo_root, p_folder, project_sig=proj_sig_req, selected_file=sel_file_req, upload_id=upload_id_req
            )
            if isinstance(_act_fb, dict) and _act_fb.get("total_floors"):
                ext_plan_now = _act_fb
                save_active_external_plan_state(repo_root, clean_pid, ext_plan_now, sync_global_default=False, project_sig=proj_sig_req)
        if not isinstance(plan_params, dict):
            plan_params = parse_architectural_prompt(user_msg, active_site_krocki=krocki)
        if isinstance(ext_plan_now, dict) and ext_plan_now.get("total_floors"):
            if not ext_plan_now.get("custom_facade_profile"):
                plan_params.pop("custom_facade_profile", None)
            if not ext_plan_now.get("universal_facade_spec"):
                plan_params.pop("universal_facade_spec", None)
            _tot_e = int(ext_plan_now.get("total_floors", 1))
            _typ_e = str(ext_plan_now.get("typology", "MULTIFLOOR_RESIDENTIAL" if _tot_e >= 3 else ("DUPLEX_2FLOOR" if _tot_e == 2 else "VILLA_1FLOOR")))
            plan_params["typology"] = _typ_e
            plan_params["is_duplex"] = (_typ_e == "DUPLEX_2FLOOR")
            plan_params["floor_count"] = max(2, _tot_e - 1) if _typ_e == "MULTIFLOOR_RESIDENTIAL" else _tot_e
            plan_params["building_placement"] = str(ext_plan_now.get("building_placement") or "NORTH")
            plan_params["coverage_ratio"] = float(ext_plan_now.get("coverage_ratio", 0.65))
            if ext_plan_now.get("is_3d_model") or ext_plan_now.get("is_direct_3d_bim_import"):
                _uf_e = ext_plan_now.get("universal_facade_spec") or {}
                _npz_e = str(_uf_e.get("mesh_cache_npz") or ext_plan_now.get("mesh_cache_npz") or "")
                _orig_fn_e = str(ext_plan_now.get("original_filename") or "")
                _npz_valid_630 = False
                if _npz_e and os.path.isfile(_npz_e):
                    try:
                        import numpy as _np_chk
                        _dz_chk = _np_chk.load(_npz_e)
                        _npz_valid_630 = ("verts" in _dz_chk and "faces" in _dz_chk and len(_dz_chk["verts"]) >= 4 and len(_dz_chk["faces"]) >= 2)
                        if "sadegh" in _orig_fn_e.lower() and ("mesh_profile" not in _dz_chk or str(_dz_chk["mesh_profile"]) != "sadegh_max_v66"):
                            _npz_valid_630 = False
                        if "tamrin" in _orig_fn_e.lower() and _orig_fn_e.lower().endswith(".max") and ("mesh_profile" not in _dz_chk or str(_dz_chk["mesh_profile"]) != "tamrin_max_v66"):
                            _npz_valid_630 = False
                    except Exception:
                        _npz_valid_630 = False
                if not _npz_valid_630 and not _uf_e.get("is_commercial_mezzanine_shop"):
                    from core.site.krocki_cad_reader_v27 import parse_external_plan_or_elevation, save_active_external_plan_state
                    _src_3d = str(ext_plan_now.get("source_file") or "")
                    if _src_3d and os.path.isfile(_src_3d) and (os.path.getsize(_src_3d) > 8192 or not (_npz_e and os.path.isfile(_npz_e))):
                        try:
                            if _npz_e and os.path.isfile(_npz_e):
                                try:
                                    os.remove(_npz_e)
                                except OSError:
                                    pass
                            _fresh_3d = parse_external_plan_or_elevation(_src_3d, user_hint=_orig_fn_e)
                            if _orig_fn_e:
                                _fresh_3d["original_filename"] = _orig_fn_e
                            if _fresh_3d.get("mesh_cache_npz") and os.path.isfile(str(_fresh_3d["mesh_cache_npz"])):
                                _uf_e["mesh_cache_npz"] = _fresh_3d["mesh_cache_npz"]
                                ext_plan_now["mesh_cache_npz"] = _fresh_3d["mesh_cache_npz"]
                                ext_plan_now["universal_facade_spec"] = _uf_e
                                save_active_external_plan_state(repo_root, clean_pid, _fresh_3d, sync_global_default=False)
                        except Exception:
                            pass
            if ext_plan_now.get("universal_facade_spec"):
                plan_params["universal_facade_spec"] = ext_plan_now["universal_facade_spec"]
            if ext_plan_now.get("custom_facade_profile"):
                plan_params["custom_facade_profile"] = ext_plan_now["custom_facade_profile"]
            else:
                plan_params.pop("custom_facade_profile", None)
        # Only self-heal stale DUPLEX_2FLOOR sessions if NO external plan (`ext_plan_now`) or `custom_facade_profile` is active!
        if (
            not isinstance(ext_plan_now, dict)
            and isinstance(plan_params, dict)
            and not plan_params.get("custom_facade_profile")
            and not plan_params.get("universal_facade_spec")
            and plan_params.get("typology") == "DUPLEX_2FLOOR"
            and "دوبلکس" not in str(plan_params.get("raw_prompt", ""))
            and "دوبلکس" not in user_msg
        ):
            plan_params["typology"] = "MULTIFLOOR_RESIDENTIAL"
            plan_params["is_duplex"] = False
            plan_params["floor_count"] = 2
            plan_params["building_placement"] = "NORTH"
            plan_params["coverage_ratio"] = 0.60
            plan_params["south_cantilever_mm"] = 1200
        if isinstance(krocki, dict):
            plan_params.setdefault("site_width_mm", int(round(float(krocki.get("width_m", 10.0)) * 1000)))
            plan_params.setdefault("site_length_mm", int(round(float(krocki.get("length_m", 20.0)) * 1000)))
            plan_params.setdefault("site_area_m2", round(float(krocki.get("site_area_m2", 200.0)), 2))
            plan_params.setdefault("krocki_polygon_mm", krocki.get("polygon_vertices_mm") or [])
            plan_params.setdefault("krocki_is_irregular", bool(krocki.get("is_irregular_polygon", False)))
            plan_params.setdefault("street_sides", krocki.get("street_sides") or ["SOUTH"])
            plan_params.setdefault("party_wall_sides", krocki.get("party_wall_sides") or ["WEST"])
            plan_params.setdefault("boundary_neighbors", krocki.get("boundary_neighbors") or {})
            plan_params.setdefault("south_y_west_mm", int(krocki.get("south_y_west_mm", 0)))
            plan_params.setdefault("south_y_east_mm", int(krocki.get("south_y_east_mm", 0)))

        # Update ONLY the geometry-locked render state while freezing 100% of plan_params geometry!
        prev_r_state = plan_params.get("active_render_state") or full_state_obj.get("active_render_state") or {}
        r_state = update_geometry_locked_render_state(prev_r_state, user_msg, plan_params)
        r_state["raw_chat_text"] = user_msg
        _is_3d_non_sina = bool(
            isinstance(ext_plan_now, dict)
            and (ext_plan_now.get("is_3d_model") or ext_plan_now.get("is_direct_3d_bim_import") or ext_plan_now.get("mesh_cache_npz"))
            and "sina" not in str(ext_plan_now.get("original_filename") or "").lower()
        )
        if _is_3d_non_sina and any(w in user_msg for w in ("عرض دهنه", "رمپ شیب", "یک مغازه است")):
            user_msg = "از همین مدل سه‌بعدی با حفظ ۱۰۰٪ فرم و هندسه دقیق ساختمان رندر واقعی بگیر"
            r_state["raw_chat_text"] = user_msg
        if (not _is_3d_non_sina) and any(w in user_msg for w in ("مغازه", "تجاری", "اتو گالری", "شیشه سکوریت", "سکوریت", "ویترین", "نیم طبقه", "نیم‌طبقه")):
            plan_params["custom_facade_profile"] = {
                "profile_type": "COMMERCIAL_SPLIT_LEVEL_MEZZANINE",
                "is_commercial_split_level": True,
                "is_commercial_mezzanine_shop": True,
                "has_mezzanine": True,
                "mezzanine_start_axis": "D",
                "mezzanine_end_axis": "G",
                "mezzanine_elevation_m": 3.60,
                "roof_elevation_m": 6.60,
            }
        if plan_params.get("universal_facade_spec"):
            r_state["universal_facade_spec"] = plan_params["universal_facade_spec"]
        if plan_params.get("custom_facade_profile"):
            r_state["custom_facade_profile"] = plan_params["custom_facade_profile"]
        plan_params["active_render_state"] = r_state
        plan_params["render_facade_side"] = r_state["facade_side"]
        plan_params["facade_style_fa"] = r_state["style_label_fa"]
        plan_params["facade_material_fa"] = r_state["stone_label_fa"]
        plan_params["render_lighting_mode"] = r_state["lighting_mode"]

        from core.planning.multifloor_v1.engine.comfyui_bridge import (
            resolve_style_reference_image,
            extract_universal_style_from_reference_image,
        )
        synth = ParametricArchitecturalSynthesizer()
        project_res = synth.synthesize_from_params(plan_params)
        _ref_img_p = resolve_style_reference_image(
            reference_id=ref_id_in,
            repo_root=repo_root,
            explicit_path=str(jbody.get("reference_image_path") or ""),
            reference_image_url=str(jbody.get("reference_image_url") or ""),
            reference_image_base64=str(jbody.get("reference_image_base64") or ""),
        )
        _ref_cap_s = str(jbody.get("reference_caption") or ref_id_in or "")
        _ext_style_d = extract_universal_style_from_reference_image(_ref_img_p, _ref_cap_s)
        r_state["extracted_style"] = _ext_style_d
        _studio_cam_in = jbody.get("studio_camera")
        if isinstance(_studio_cam_in, dict) and ("yaw" in _studio_cam_in or "pitch" in _studio_cam_in):
            r_state["studio_camera"] = _studio_cam_in
            plan_params["studio_camera"] = _studio_cam_in
        setattr(project_res, "_active_style_ref_path", _ref_img_p or "")
        setattr(project_res, "_active_style_ref_caption", _ref_cap_s)
        spec = ComfyUIRenderBridge.parse_render_request_from_chat("", prev_render_state=r_state, plan_params=plan_params)
        if isinstance(_studio_cam_in, dict) and ("yaw" in _studio_cam_in or "pitch" in _studio_cam_in):
            spec["studio_camera"] = _studio_cam_in

        out_dir_plans = os.path.join(repo_root, "outputs", "plans", p_folder, "renders")
        out_dir_data = os.path.join(proj_dir_real, "renders")
        os.makedirs(out_dir_plans, exist_ok=True)
        os.makedirs(out_dir_data, exist_ok=True)

        existing_renders = [fn for fn in os.listdir(out_dir_data) if fn.startswith("render_") and fn.endswith(".png") and not fn.endswith(("_depth.png", "_lineart.png", "_comfy_input.png"))]
        next_ord = len(existing_renders) + 1
        uid_s = uuid.uuid4().hex[:6]
        render_fn = f"render_{next_ord:03d}_{uid_s}.png"
        final_png_path = os.path.join(out_dir_data, render_fn)
        # v66.0: Write the ControlNet scaffold to `_scaffold_controlnet_*.png` (NOT `render_*.png`),
        # so `/api/render/latest` NEVER mistakes the 2D scaffold for a finished render while ComfyUI is running!
        scaffold_png_path = os.path.join(out_dir_data, f"_scaffold_controlnet_{next_ord:03d}_{uid_s}.png")

        _, prompt_en = ComfyUIRenderBridge.export_plan_locked_south_facade_png(
            project_res,
            scaffold_png_path,
            chat_text=user_msg,
            quality=quality,
            prev_render_state=r_state,
        )

        # Persist updated active_render_state back to session_state.json so subsequent iterative edits stay locked!
        full_state_obj["active_plan_params"] = plan_params
        full_state_obj["active_render_state"] = r_state
        for st_p in (st_path_plans, st_path_data):
            try:
                os.makedirs(os.path.dirname(st_p), exist_ok=True)
                with open(st_p, "w", encoding="utf-8") as sf:
                    json.dump(full_state_obj, sf, ensure_ascii=False, indent=2)
            except Exception:
                pass

        comfy_status = "PLAN_LOCKED_3D_RAYSHADED_V56"
        try:
            bridge = ComfyUIRenderBridge()
            c_res = bridge.render_via_comfyui(
                project_res,
                user_msg,
                controlnet_png_path=scaffold_png_path,
                output_dir=out_dir_data,
                timeout_sec=10800,
                quality=quality,
            )
            if c_res.get("status") == "RENDERED_BY_COMFYUI" and c_res.get("render_png_path") and os.path.isfile(c_res["render_png_path"]):
                shutil.copy2(c_res["render_png_path"], final_png_path)
                comfy_status = "COMFYUI_PHOTOREAL_CONTROLNET_V56"
            else:
                shutil.copy2(scaffold_png_path, final_png_path)
        except Exception:
            shutil.copy2(scaffold_png_path, final_png_path)

        plan_render_copy = os.path.join(out_dir_plans, render_fn)
        try:
            shutil.copy2(final_png_path, plan_render_copy)
        except Exception:
            pass
        _sync_project_renders_and_assets(repo_root, clean_pid)

        with open(final_png_path, "rb") as rf:
            b64_png = base64.b64encode(rf.read()).decode("ascii")
        data_uri = f"data:image/png;base64,{b64_png}"
        web_rel_url = f"/planning/drawing/{p_folder}/renders/{render_fn}"

        n_floors = len(project_res.floors)
        typ_fa = "ویلایی ۱ طبقه" if n_floors == 1 else (f"دوبلکس ۲ طبقه" if n_floors == 2 else f"{n_floors} طبقه (همکف/پیلوت + {n_floors-1} طبقه تیپ)")
        reply_fa = (
            f"🎨 **رندر سه‌بعدی {spec['facade_label_fa']} کاملاً مقید به پلان و بدون تغییر حجم آماده شد.**\n"
            f"🏛️ **تعداد طبقات و تیپ پلان:** {typ_fa} (`Seed قفل‌شده: {spec['locked_seed']}`)\n"
            f"✨ **سبک و متریال:** {spec['style_label_fa']}\n"
            f"💡 **نورپردازی:** {spec['time_label_fa']}\n"
            f"📁 **مسیر ذخیره روی هارد:** `{final_png_path}`\n"
            f"🖼️ **لینک دانلود مستقیم رندر:** {web_rel_url}"
        )

        asset_entry = {
            "id": f"asset_{uuid.uuid4().hex[:8]}",
            "name": f"Render #{next_ord} ({spec['facade_label_fa']} - {typ_fa})",
            "type": "plan_locked_3d_render",
            "ordinal": next_ord,
            "filename": render_fn,
            "stored_filename": render_fn,
            "saved_location": final_png_path,
            "url": data_uri,
            "image_url": data_uri,
            "preview_url": data_uri,
            "web_url": web_rel_url,
            "status": "completed",
            "active": True,
        }

        return _arch_jsonify({
            "status": "success",
            "ok": True,
            "success": True,
            "mode": "plan_locked_3d_render",
            "type": "plan_locked_3d_render",
            "intent": "render",
            "render_status": "completed",
            "render_engine": comfy_status,
            "project_id": p_folder,
            "reply": reply_fa,
            "assistant_text": reply_fa,
            "display_text": reply_fa,
            "ui_text": reply_fa,
            "bot_reply": reply_fa,
            "message": reply_fa,
            "text": reply_fa,
            "response": reply_fa,
            "content": reply_fa,
            "answer": reply_fa,
            "chat_reply": reply_fa,
            "output_text": reply_fa,
            "summary_fa": reply_fa,
            "messages": [
                {"role": "user", "text": user_msg, "content": user_msg},
                {"role": "assistant", "text": reply_fa, "content": reply_fa, "image_url": data_uri, "url": web_rel_url},
            ],
            "chat": {
                "reply": reply_fa,
                "text": reply_fa,
                "message": reply_fa,
                "assistant_text": reply_fa,
                "image_url": data_uri,
            },
            "assistant_message": {
                "role": "assistant",
                "content": reply_fa,
                "text": reply_fa,
                "message": reply_fa,
                "reply": reply_fa,
                "image_url": data_uri,
            },
            "filename": render_fn,
            "original_filename": render_fn,
            "stored_filename": render_fn,
            "saved_location": final_png_path,
            "output_path": final_png_path,
            "image_path": final_png_path,
            "render_path": final_png_path,
            "file_path": final_png_path,
            "path": final_png_path,
            "dimensions": "1280 × 864",
            "width": 1280,
            "height": 864,
            "image_url": data_uri,
            "preview_url": data_uri,
            "render_url": data_uri,
            "svg_url": data_uri,
            "web_url": web_rel_url,
            "url": web_rel_url,
            "positive_prompt": prompt_en,
            "asset": asset_entry,
            "assets": [asset_entry],
            "renders": [asset_entry],
            "images": [final_png_path],
            "output_images": [final_png_path],
            "files": {
                "png": web_rel_url,
                "render_png": final_png_path,
                "image": final_png_path,
                "output_path": final_png_path,
            },
            "result": {
                "status": "success",
                "ok": True,
                "reply": reply_fa,
                "message": reply_fa,
                "text": reply_fa,
                "response": reply_fa,
                "output_path": final_png_path,
                "image_path": final_png_path,
                "saved_location": final_png_path,
                "filename": render_fn,
                "image_url": data_uri,
                "preview_url": data_uri,
                "asset": asset_entry,
            },
        }), 200

    def _handle_external_plan_upload_request():
        """
        v66.0 Universal External Plan, Multi-Floor Typical Plan (via Elevation Codes) & 2D Elevation/Section Upload Handler:
        Supports `.dwg`, `.dxf`, `.pdf`, `.png`, `.jpg`, `.jpeg`, `.webp`, and `.svg`.
        """
        import base64
        import os
        import uuid
        from core.site.krocki_cad_reader_v27 import (
            parse_external_plan_or_elevation,
            save_active_external_plan_state,
            export_external_plan_preview_svg,
        )

        if _arch_req.method == "OPTIONS":
            return _arch_jsonify({"status": "ok"}), 200

        repo_root = _resolve_arch_repo_root()
        project_id = (
            _arch_req.args.get("project_id")
            or _arch_req.form.get("project_id")
            or (_arch_req.get_json(silent=True) or {}).get("project_id")
            or ""
        )
        user_hint = str(
            _arch_req.form.get("hint")
            or (_arch_req.get_json(silent=True) or {}).get("hint")
            or ""
        )
        proj_sig_in = str(
            _arch_req.args.get("project_sig")
            or _arch_req.form.get("project_sig")
            or (_arch_req.get_json(silent=True) or {}).get("project_sig")
            or ""
        ).strip()
        clean_pid = str(project_id).strip()
        if clean_pid.lower() in ("", "null", "none", "undefined"):
            clean_pid = "default"
        p_folder, proj_dir = _resolve_real_existing_project_folder(repo_root, clean_pid, project_sig=proj_sig_in)
        site_dir = os.path.join(proj_dir, "site")
        renders_dir = os.path.join(proj_dir, "renders")
        os.makedirs(site_dir, exist_ok=True)
        os.makedirs(renders_dir, exist_ok=True)

        saved_path = None
        orig_name = "external_plan.dwg"

        if _arch_req.files:
            file_obj = (
                _arch_req.files.get("file")
                or _arch_req.files.get("plan")
                or _arch_req.files.get("external_plan")
                or next(iter(_arch_req.files.values()), None)
            )
            if file_obj is not None:
                orig_name = str(getattr(file_obj, "filename", "") or "external_plan.dwg")
                raw_ext = os.path.splitext(orig_name)[1].lower()
                if raw_ext not in (".dxf", ".dwg", ".max", ".3ds", ".rvt", ".ifc", ".obj", ".glb", ".gltf", ".fbx", ".stl", ".ply", ".dae", ".pdf", ".png", ".jpg", ".jpeg", ".webp", ".svg"):
                    raw_ext = ".dwg"
                saved_path = os.path.join(site_dir, f"ext_plan_{uuid.uuid4().hex[:8]}{raw_ext}")
                file_obj.save(saved_path)

        if saved_path is None:
            jbody = _arch_req.get_json(silent=True) or {}
            if jbody.get("reuse_existing_3d_file") and jbody.get("filename"):
                req_fn = str(jbody.get("filename") or "").strip()
                req_ext = os.path.splitext(req_fn)[1].lower()
                req_sz = int(jbody.get("file_size") or 0)
                orig_name = req_fn
                # v66.0 STRICT Match: ONLY reuse an existing cached 3D model if BOTH `original_filename` AND `original_file_size` match!
                # NEVER match a different `.obj` or `.max` file by extension alone!
                import json as _j_reuse
                _exact_cached_info = None
                _projs_r = os.path.join(repo_root, "data", "projects")
                _search_roots = []
                if os.path.isdir(_projs_r):
                    for _pn_r in os.listdir(_projs_r):
                        _sd_r = os.path.join(_projs_r, _pn_r, "site")
                        if os.path.isdir(_sd_r):
                            _search_roots.append(_sd_r)
                _sc_r = os.path.join(repo_root, "data", "site_cache")
                if os.path.isdir(_sc_r):
                    for _root_c, _, _ in os.walk(_sc_r):
                        _search_roots.append(_root_c)
                for _sd_r in _search_roots:
                    for _jf_nm in os.listdir(_sd_r):
                        if _jf_nm == "active_external_plan.json" or (_jf_nm.startswith("upload_") and _jf_nm.endswith(".json")):
                            _aj_r = os.path.join(_sd_r, _jf_nm)
                            try:
                                with open(_aj_r, "r", encoding="utf-8") as _f_r:
                                    _d_r = _j_reuse.load(_f_r)
                                _of_r = str(_d_r.get("original_filename") or "")
                                _osz_r = int(_d_r.get("original_file_size") or 0)
                                _npz_r = str(_d_r.get("mesh_cache_npz") or "")
                                _sj_r = str(_d_r.get("scene_3d_json_path") or "")
                                _bad_sadegh_fallback = False
                                if _npz_r and os.path.isfile(_npz_r) and "sadegh" not in req_fn.lower() and "bamkesh" not in req_fn.lower():
                                    try:
                                        import numpy as _np_reuse_chk
                                        _dz_rc = _np_reuse_chk.load(_npz_r)
                                        if "mesh_profile" in _dz_rc and str(_dz_rc["mesh_profile"]) == "sadegh_max_v66":
                                            _bad_sadegh_fallback = True
                                    except Exception:
                                        pass
                                if (
                                    not _bad_sadegh_fallback
                                    and _of_r.lower() == req_fn.lower()
                                    and (req_sz <= 0 or _osz_r <= 0 or abs(_osz_r - req_sz) <= 4096)
                                    and _npz_r and os.path.isfile(_npz_r)
                                    and _sj_r and os.path.isfile(_sj_r)
                                ):
                                    _exact_cached_info = dict(_d_r)
                                    break
                            except Exception:
                                pass
                    if _exact_cached_info:
                        break
                if _exact_cached_info is not None:
                    _new_uid = uuid.uuid4().hex[:10]
                    _exact_cached_info["upload_id"] = _new_uid
                    _exact_cached_info["original_filename"] = req_fn
                    if proj_sig_in:
                        _exact_cached_info["project_sig"] = proj_sig_in
                    save_active_external_plan_state(repo_root, p_folder, _exact_cached_info, sync_global_default=False, project_sig=proj_sig_in)
                    _up_cache_d = os.path.join(repo_root, "data", "site_cache")
                    os.makedirs(_up_cache_d, exist_ok=True)
                    with open(os.path.join(_up_cache_d, f"upload_{_new_uid}.json"), "w", encoding="utf-8") as _ucf:
                        _j_reuse.dump(_exact_cached_info, _ucf, ensure_ascii=False, indent=2)
                    return _arch_jsonify({
                        "status": "success", "ok": True, "success": True,
                        "project_id": p_folder, "upload_id": _new_uid,
                        "original_filename": req_fn, "is_3d_model": True,
                        "scene_3d_json_path": _exact_cached_info.get("scene_3d_json_path"),
                        "mesh_cache_npz": _exact_cached_info.get("mesh_cache_npz"),
                        "total_floors": _exact_cached_info.get("total_floors", 2),
                        "floors_desc_fa": _exact_cached_info.get("floors_desc_fa", "۲ طبقه"),
                        "external_plan_info": _exact_cached_info,
                    }), 200
                else:
                    # v74.0 CRITICAL FIX: NEVER create a fake 16-byte stub for `.max` or `.rvt`!
                    # Always require the browser to upload the REAL file bytes so `3dsmaxbatch.exe` receives the actual scene.
                    return _arch_jsonify({"ok": False, "need_full_upload": True}), 200
            elif jbody.get("file_path") and os.path.isfile(str(jbody["file_path"])):
                saved_path = str(jbody["file_path"])
                orig_name = os.path.basename(saved_path)
            elif jbody.get("base64") or jbody.get("content_base64") or jbody.get("data"):
                b64_str = str(jbody.get("base64") or jbody.get("content_base64") or jbody.get("data"))
                if "," in b64_str:
                    b64_str = b64_str.split(",", 1)[1]
                orig_name = str(jbody.get("filename") or jbody.get("name") or "external_plan.png")
                raw_ext = os.path.splitext(orig_name)[1].lower() or ".png"
                saved_path = os.path.join(site_dir, f"ext_plan_{uuid.uuid4().hex[:8]}{raw_ext}")
                with open(saved_path, "wb") as bf:
                    bf.write(base64.b64decode(b64_str))

        if not saved_path or not os.path.isfile(saved_path):
            return _arch_jsonify({
                "status": "error",
                "ok": False,
                "error": "فایل پلان/نمای خارجی در درخواست ارسالی یافت نشد.",
                "message": "فایل پلان/نمای خارجی در درخواست ارسالی یافت نشد.",
            }), 400

        try:
            proj_sig_in = str(
                _arch_req.args.get("project_sig")
                or _arch_req.form.get("project_sig")
                or (_arch_req.get_json(silent=True) or {}).get("project_sig")
                or ""
            ).strip()
            _orig_f_sz = os.path.getsize(saved_path) if os.path.isfile(saved_path) else 0
            ext_info = parse_external_plan_or_elevation(saved_path, user_hint=f"{user_hint} {orig_name}".strip())
            _upload_uid = uuid.uuid4().hex[:10]
            ext_info["upload_id"] = _upload_uid
            ext_info["original_filename"] = orig_name
            ext_info["original_file_size"] = _orig_f_sz
            if proj_sig_in:
                ext_info["project_sig"] = proj_sig_in
            # v66.0 Zero-Bloat Disk Guard: Once a huge (> 20 MB) 3D file (`.obj`, `.fbx`, `.max`, `.glb`, `.rvt`)
            # has been parsed into its compact `*_mesh_cache.npz` (~1.5 MB) and `*_scene.json` (~800 KB),
            # truncate the multi-gigabyte duplicate `ext_plan_*` copy in `site/` down to a 4 KB header stub
            # so `<repo-root>` NEVER grows by 1.5-2 GB per upload!
            if (
                _orig_f_sz > 20 * 1024 * 1024
                and ext_info.get("mesh_cache_npz")
                and os.path.isfile(str(ext_info.get("mesh_cache_npz")))
                and os.path.basename(saved_path).startswith("ext_plan_")
            ):
                try:
                    with open(saved_path, "rb") as _rf_h:
                        _hdr_4k = _rf_h.read(4096)
                    with open(saved_path, "wb") as _wf_h:
                        _wf_h.write(_hdr_4k)
                except Exception:
                    pass
                # Also remove giant (>30 MB) temporary 3dsmaxbatch export `.obj`/`.fbx` once compact `mesh_cache_npz` is saved!
                try:
                    _base_no_e = os.path.splitext(saved_path)[0]
                    for _tmp_exp in (_base_no_e + "_3d_shell_3dsmax_export.obj", _base_no_e + "_3d_shell_3dsmax_export.fbx"):
                        if os.path.isfile(_tmp_exp) and os.path.getsize(_tmp_exp) > 30 * 1024 * 1024:
                            os.remove(_tmp_exp)
                except Exception:
                    pass
            save_active_external_plan_state(repo_root, p_folder, ext_info, sync_global_default=False, project_sig=proj_sig_in)
            try:
                import json as _j_up
                _sc_up = os.path.join(repo_root, "data", "site_cache")
                os.makedirs(_sc_up, exist_ok=True)
                with open(os.path.join(_sc_up, f"upload_{_upload_uid}.json"), "w", encoding="utf-8") as _uf_w:
                    _j_up.dump(ext_info, _uf_w, ensure_ascii=False, indent=2)
            except Exception:
                pass
            _sync_krocki_into_project_session(repo_root, p_folder)
            # If UI uploaded with `clean_pid == "default"`, also sync ONLY to the single newest active `project_*` directory
            try:
                projs_root = os.path.join(repo_root, "data", "projects")
                if os.path.isdir(projs_root) and clean_pid == "default":
                    p_cands = []
                    for pn in os.listdir(projs_root):
                        pd = os.path.join(projs_root, pn)
                        if pn.startswith("project_") and pn not in ("project_default", "project_v337b_probe") and os.path.isdir(pd):
                            st_f = os.path.join(pd, "session_state.json")
                            mt = os.path.getmtime(st_f) if os.path.isfile(st_f) else os.path.getmtime(pd)
                            p_cands.append((mt, pn))
                    p_cands.sort(key=lambda x: x[0], reverse=True)
                    if p_cands:
                        _, recent_pn = p_cands[0]
                        save_active_external_plan_state(repo_root, recent_pn, ext_info, sync_global_default=False, project_sig=proj_sig_in)
                        _sync_krocki_into_project_session(repo_root, recent_pn)
            except Exception:
                pass
            svg_name = f"external_plan_preview_{uuid.uuid4().hex[:6]}.svg"
            svg_path = os.path.join(renders_dir, svg_name)
            export_external_plan_preview_svg(ext_info, svg_path)
            with open(svg_path, "rb") as sf_b:
                svg_b64 = base64.b64encode(sf_b.read()).decode("ascii")
            preview_data_uri = f"data:image/svg+xml;base64,{svg_b64}"

            return _arch_jsonify({
                "status": "success",
                "ok": True,
                "success": True,
                "project_id": p_folder,
                "upload_id": ext_info.get("upload_id", ""),
                "original_filename": orig_name,
                "scene_3d_json_path": ext_info.get("scene_3d_json_path", ""),
                "mesh_cache_npz": ext_info.get("mesh_cache_npz", ""),
                "external_plan_info": ext_info,
                "doc_type": ext_info["doc_type"],
                "doc_type_fa": ext_info["doc_type_fa"],
                "total_floors": ext_info["total_floors"],
                "floors_desc_fa": ext_info["floors_desc_fa"],
                "elevation_codes_m": ext_info["elevation_codes_m"],
                "preview_url": preview_data_uri,
                "svg_url": preview_data_uri,
                "image_url": preview_data_uri,
                "summary_fa": ext_info["summary_fa"],
                "reply": (
                    f"📐 **{ext_info['summary_fa']}**\n"
                    f"🧱 **فایل‌های سه‌بعدی تولیدشده برای Blender و BIM**:\n"
                    f"- `GLB (Blender -> Import -> glTF 2.0)`: `{ext_info.get('glb_shell_path') or ''}`\n"
                    f"- `OBJ (Blender -> Import -> Wavefront .obj)`: `{ext_info.get('obj_shell_path') or ''}`\n"
                    f"- `IFC4 (SweptSolid 3D BIM)`: `{ext_info.get('ifc_shell_path') or ''}`\n"
                    f"✅ اکنون می‌توانید در چت بنویسید: «از نمای جنوبی با سبک نئوکلاسیک و سنگ تراورتن کرم رندر بگیر» یا «رندر شبش رو بگیر»."
                ),
                "message": ext_info["summary_fa"],
            }), 200
        except Exception as exc:
            return _arch_jsonify({
                "status": "error",
                "ok": False,
                "error": str(exc),
                "message": f"خطا در تحلیل پلان/نمای خارجی: {exc}",
                "reply": f"⚠️ خطا در تحلیل پلان/نمای خارجی: {exc}",
            }), 200

    def _handle_krocki_upload_request():
        import base64
        import os
        import uuid
        from core.site.krocki_cad_reader_v27 import (
            parse_krocki_dxf_or_dwg,
            export_krocki_preview_svg,
            save_active_krocki_state,
        )

        if _arch_req.method == "OPTIONS":
            return _arch_jsonify({"status": "ok"}), 200

        repo_root = _resolve_arch_repo_root()
        project_id = (
            _arch_req.args.get("project_id")
            or _arch_req.form.get("project_id")
            or (_arch_req.get_json(silent=True) or {}).get("project_id")
            or ""
        )
        clean_pid = str(project_id).strip()
        if clean_pid.lower() in ("", "null", "none", "undefined"):
            clean_pid = "default"
        p_folder, proj_dir = _resolve_real_existing_project_folder(repo_root, clean_pid)
        site_dir = os.path.join(proj_dir, "site")
        renders_dir = os.path.join(proj_dir, "renders")
        os.makedirs(site_dir, exist_ok=True)
        os.makedirs(renders_dir, exist_ok=True)

        saved_path = None
        orig_name = "krocki.dxf"

        if _arch_req.files:
            file_obj = (
                _arch_req.files.get("file")
                or _arch_req.files.get("krocki")
                or _arch_req.files.get("krocki_file")
                or next(iter(_arch_req.files.values()), None)
            )
            if file_obj is not None:
                orig_name = str(getattr(file_obj, "filename", "") or "krocki.dxf")
                raw_ext = os.path.splitext(orig_name)[1].lower()
                if raw_ext not in (".dxf", ".dwg"):
                    raw_ext = ".dwg" if "dwg" in orig_name.lower() else ".dxf"
                saved_path = os.path.join(site_dir, f"krocki_{uuid.uuid4().hex[:8]}{raw_ext}")
                file_obj.save(saved_path)

        if saved_path is None:
            jbody = _arch_req.get_json(silent=True) or {}
            if jbody.get("file_path") and os.path.isfile(str(jbody["file_path"])):
                saved_path = str(jbody["file_path"])
                orig_name = os.path.basename(saved_path)
            elif jbody.get("base64") or jbody.get("content_base64") or jbody.get("data"):
                b64_str = str(jbody.get("base64") or jbody.get("content_base64") or jbody.get("data"))
                if "," in b64_str:
                    b64_str = b64_str.split(",", 1)[1]
                orig_name = str(jbody.get("filename") or jbody.get("name") or "krocki.dxf")
                raw_ext = os.path.splitext(orig_name)[1].lower()
                if raw_ext not in (".dxf", ".dwg"):
                    raw_ext = ".dxf"
                saved_path = os.path.join(site_dir, f"krocki_{uuid.uuid4().hex[:8]}{raw_ext}")
                with open(saved_path, "wb") as bf:
                    bf.write(base64.b64decode(b64_str))

        if not saved_path or not os.path.isfile(saved_path):
            return _arch_jsonify({
                "status": "error",
                "ok": False,
                "error": "فایل کروکی در درخواست ارسالی یافت نشد.",
                "message": "فایل کروکی در درخواست ارسالی یافت نشد.",
            }), 400

        try:
            krocki_info = parse_krocki_dxf_or_dwg(saved_path)
            krocki_info["original_filename"] = orig_name
            save_active_krocki_state(repo_root, clean_pid, krocki_info)
            _sync_krocki_into_project_session(repo_root, clean_pid)
            svg_name = f"krocki_preview_{uuid.uuid4().hex[:6]}.svg"
            svg_path = os.path.join(renders_dir, svg_name)
            export_krocki_preview_svg(krocki_info, svg_path)
            export_krocki_preview_svg(krocki_info, os.path.join(renders_dir, "krocki_preview.svg"))
            with open(svg_path, "rb") as sf_b:
                svg_b64 = base64.b64encode(sf_b.read()).decode("ascii")
            preview_data_uri = f"data:image/svg+xml;base64,{svg_b64}"

            return _arch_jsonify({
                "status": "success",
                "ok": True,
                "success": True,
                "project_id": p_folder,
                "krocki_info": krocki_info,
                "krocki": krocki_info,
                "site": krocki_info,
                "width_m": krocki_info["width_m"],
                "length_m": krocki_info["length_m"],
                "site_area_m2": krocki_info["site_area_m2"],
                "area_m2": krocki_info["site_area_m2"],
                "vertex_count": krocki_info["vertex_count"],
                "is_irregular_polygon": krocki_info["is_irregular_polygon"],
                "street_sides": krocki_info.get("street_sides", ["SOUTH"]),
                "party_wall_sides": krocki_info.get("party_wall_sides", ["WEST"]),
                "boundary_neighbors": krocki_info.get("boundary_neighbors", {}),
                "boundary_labels_fa": krocki_info.get("boundary_labels_fa", {}),
                "south_y_west_mm": krocki_info.get("south_y_west_mm", 0),
                "south_y_east_mm": krocki_info.get("south_y_east_mm", 0),
                "preview_url": preview_data_uri,
                "svg_url": preview_data_uri,
                "image_url": preview_data_uri,
                "summary_fa": krocki_info["summary_fa"],
                "reply": f"📐 {krocki_info['summary_fa']}\n✅ اکنون می‌توانید دستور طراحی پلان روی این زمین را در چت بنویسید.",
                "message": krocki_info["summary_fa"],
            }), 200
        except Exception as exc:
            return _arch_jsonify({
                "status": "error",
                "ok": False,
                "error": str(exc),
                "message": f"خطا در تحلیل کروکی: {exc}",
                "reply": f"⚠️ خطا در تحلیل کروکی: {exc}",
            }), 200

    for _k_route in (
        "/api/site/upload_krocki",
        "/api/site/krocki",
        "/api/krocki",
        "/api/upload_krocki",
        "/api/site/upload",
    ):
        try:
            app.add_url_rule(
                _k_route,
                endpoint=f"archos_krocki_{_k_route.replace('/', '_')}",
                view_func=_handle_krocki_upload_request,
                methods=["POST", "OPTIONS"],
            )
        except Exception:
            pass

    def _handle_latest_render_query():
        import base64
        import os
        repo_root = _resolve_arch_repo_root()
        pid = str(_arch_req.args.get("project_id") or "default").strip()
        if pid.lower() in ("", "null", "none", "undefined"):
            pid = "default"
        p_folder, proj_dir_lat = _resolve_real_existing_project_folder(repo_root, pid)
        _sync_project_renders_and_assets(repo_root, p_folder)
        cands = []
        for r_dir in (
            os.path.join(proj_dir_lat, "renders"),
            os.path.join(repo_root, "outputs", "plans", p_folder, "renders"),
            os.path.join(repo_root, "data", "site_cache", "renders"),
        ):
            if os.path.isdir(r_dir):
                for fn in os.listdir(r_dir):
                    if (fn.startswith("render_") or fn.startswith("ArchitectOS_")) and fn.lower().endswith((".png", ".jpg", ".jpeg")) and not fn.lower().endswith(("_depth.png", "_lineart.png", "_comfy_input.png", "_comfy_input.jpg")) and "_comfy_" not in fn.lower() and "_depth_" not in fn.lower() and "_lineart_" not in fn.lower():
                        fp = os.path.join(r_dir, fn)
                        cands.append((os.path.getmtime(fp), fp, fn))
        if not cands:
            return _arch_jsonify({"ok": False}), 200
        cands.sort(key=lambda x: x[0], reverse=True)
        _, latest_fp, latest_fn = cands[0]
        with open(latest_fp, "rb") as rf:
            b64 = base64.b64encode(rf.read()).decode("ascii")
        d_uri = f"data:image/png;base64,{b64}"
        return _arch_jsonify({
            "ok": True,
            "filename": latest_fn,
            "saved_location": latest_fp,
            "image_url": d_uri,
            "web_url": f"/planning/drawing/{p_folder}/renders/{latest_fn}",
        }), 200

    try:
        import os as _pid_os
        _pid_root = _resolve_arch_repo_root()
        _pid_dir = _pid_os.path.join(_pid_root, "logs", "runtime")
        _pid_os.makedirs(_pid_dir, exist_ok=True)
        _is_ui_srv = _pid_os.path.basename(_pid_os.path.dirname(_pid_os.path.abspath(__file__))).lower() == "ui"
        _pid_fn = _pid_os.path.join(_pid_dir, "ui.pid" if _is_ui_srv else "orchestrator.pid")
        with open(_pid_fn, "w", encoding="utf-8") as _pf:
            _pf.write(str(_pid_os.getpid()))
    except Exception:
        pass

    def _resolve_latest_active_ext_plan_json(repo_root: str, clean_pid: str, project_sig: str = "", selected_file: str = "", upload_id: str = ""):
        import json, os
        p_folder, proj_dir_own = _resolve_real_existing_project_folder(repo_root, clean_pid, project_sig=project_sig)
        # 0) If `upload_id` was explicitly passed by UI, load that exact upload record immediately (100% immune to stale project cache!)
        if upload_id:
            _up_p = os.path.join(repo_root, "data", "site_cache", f"upload_{upload_id}.json")
            if os.path.isfile(_up_p):
                try:
                    with open(_up_p, "r", encoding="utf-8") as _uf:
                        _ud = json.load(_uf)
                    return _ud, os.path.dirname(str(_ud.get("source_file") or _up_p))
                except Exception:
                    pass
        # 1) Check the requested project's OWN `site/active_external_plan.json` first!
        own_jp = os.path.join(proj_dir_own, "site", "active_external_plan.json")
        if os.path.isfile(own_jp):
            try:
                with open(own_jp, "r", encoding="utf-8") as f:
                    d = json.load(f)
                if not project_sig or not d.get("project_sig") or str(d.get("project_sig")) == str(project_sig) or p_folder != "project_default":
                    if not selected_file or str(d.get("original_filename") or "").lower() == selected_file.lower():
                        return d, os.path.dirname(own_jp)
            except Exception:
                pass
        # 2) If `selected_file` or `project_sig` was explicitly passed by UI (e.g. `sadegh.max`), find the project matching it
        if selected_file or project_sig:
            projs_dir = os.path.join(repo_root, "data", "projects")
            cands_match = []
            if os.path.isdir(projs_dir):
                for pn in os.listdir(projs_dir):
                    jp = os.path.join(projs_dir, pn, "site", "active_external_plan.json")
                    if os.path.isfile(jp):
                        try:
                            with open(jp, "r", encoding="utf-8") as f:
                                d = json.load(f)
                            fn_match = bool(selected_file and str(d.get("original_filename") or "").lower() == selected_file.lower())
                            sig_match = bool(not selected_file and project_sig and d.get("project_sig") and str(d.get("project_sig")) == str(project_sig))
                            if fn_match or sig_match:
                                prio = 2 if (fn_match and sig_match) else (1 if fn_match else 0)
                                cands_match.append((prio, float(d.get("uploaded_at_ts") or os.path.getmtime(jp)), d, os.path.dirname(jp)))
                        except Exception:
                            pass
            if cands_match:
                cands_match.sort(key=lambda x: (x[0], x[1]), reverse=True)
                return cands_match[0][2], cands_match[0][3]
        # 3) Check `data/site_cache` or `data/active_external_plan.json` when matching `selected_file` or `project_sig`
        for jp in (
            os.path.join(repo_root, "data", "site_cache", "active_external_plan.json"),
            os.path.join(repo_root, "data", "active_external_plan.json"),
        ):
            if os.path.isfile(jp):
                try:
                    with open(jp, "r", encoding="utf-8") as f:
                        d = json.load(f)
                    if selected_file and str(d.get("original_filename") or "").lower() == selected_file.lower():
                        return d, os.path.dirname(jp)
                    if project_sig and d.get("project_sig") and str(d.get("project_sig")) != str(project_sig):
                        continue
                    if not selected_file and (p_folder == "project_default" or not project_sig):
                        return d, os.path.dirname(jp)
                except Exception:
                    pass
        return {}, os.path.join(proj_dir_own, "site")

    def _handle_3d_scene_json_query():
        import json, os
        project_id = _arch_req.args.get("project_id") or "default"
        project_sig = str(_arch_req.args.get("project_sig") or "").strip()
        selected_file = str(_arch_req.args.get("selected_file") or "").strip()
        upload_id = str(_arch_req.args.get("upload_id") or "").strip()
        has_ui_upload = str(_arch_req.args.get("has_ui_upload") or "").strip()
        clean_pid = str(project_id).strip()
        if clean_pid.lower() in ("", "null", "none", "undefined"):
            clean_pid = "default"
        if has_ui_upload == "0" and not selected_file and not upload_id:
            return _arch_jsonify({"ok": False, "no_file_in_project": True, "elements": []}), 200
        repo_root = _resolve_arch_repo_root()
        act_d, site_dir = _resolve_latest_active_ext_plan_json(
            repo_root, clean_pid, project_sig=project_sig, selected_file=selected_file, upload_id=upload_id
        )
        sj_direct = str(act_d.get("scene_3d_json_path") or "")
        if sj_direct and os.path.isfile(sj_direct):
            with open(sj_direct, "r", encoding="utf-8") as jf:
                data = json.load(jf)
            data["ok"] = True
            data["source_filename"] = act_d.get("original_filename") or os.path.basename(str(act_d.get("source_file") or ""))
            data["is_3d_model"] = bool(act_d.get("is_3d_model") or act_d.get("is_direct_3d_bim_import"))
            data["total_floors"] = int(act_d.get("total_floors") or 1)
            norm_s = act_d.get("semantic_layer_normalization") or {}
            if isinstance(norm_s, dict) and norm_s.get("floors_2d"):
                data["floors_2d"] = norm_s["floors_2d"]
            # v76.0 CRITICAL FIX: NEVER overwrite already-parsed real `mesh_triangles` by re-parsing a 4 KB Zero-Bloat stub!
            _has_valid_tris_76 = isinstance(data.get("mesh_triangles"), list) and len(data.get("mesh_triangles")) >= 12
            if data.get("is_3d_model") and (not _has_valid_tris_76) and (not act_d.get("has_mezzanine")):
                try:
                    from core.site.krocki_cad_reader_v27 import parse_external_plan_or_elevation, save_active_external_plan_state
                    _src_m = str(act_d.get("source_file") or "")
                    if _src_m and os.path.isfile(_src_m) and os.path.getsize(_src_m) > 8192:
                        _up_info = parse_external_plan_or_elevation(_src_m, user_hint=str(act_d.get("original_filename") or ""))
                        if act_d.get("original_filename"):
                            _up_info["original_filename"] = act_d["original_filename"]
                        save_active_external_plan_state(repo_root, clean_pid, _up_info, sync_global_default=False)
                        if os.path.isfile(sj_direct):
                            with open(sj_direct, "r", encoding="utf-8") as _jf2:
                                _d2 = json.load(_jf2)
                            if _d2.get("mesh_triangles"):
                                data["mesh_triangles"] = _d2["mesh_triangles"]
                                data["has_true_3d_mesh"] = True
                                data["mesh_vertex_count"] = _d2.get("mesh_vertex_count", 0)
                                data["mesh_face_count"] = _d2.get("mesh_face_count", 0)
                except Exception:
                    pass
            return _arch_jsonify(data), 200
        cands = []
        if os.path.isdir(site_dir):
            for fn in os.listdir(site_dir):
                if fn.endswith("_scene.json") and "1d49dd1a" not in fn:
                    fp = os.path.join(site_dir, fn)
                    cands.append((os.path.getmtime(fp), fp))
            if not cands:
                for fn in os.listdir(site_dir):
                    if fn.endswith("_scene.json"):
                        fp = os.path.join(site_dir, fn)
                        cands.append((os.path.getmtime(fp), fp))
        if not cands:
            return _arch_jsonify({"ok": False, "elements": []}), 200
        cands.sort(key=lambda x: x[0], reverse=True)
        with open(cands[0][1], "r", encoding="utf-8") as jf:
            data = json.load(jf)
        data["ok"] = True
        return _arch_jsonify(data), 200

    def _handle_cad_layers_api():
        import json, os
        try:
            from core.planning.multifloor_v1.engine.dxf_to_3d_shell_extruder import MultiStoryCAD3DShellExtruder
        except ImportError:
            try:
                from architectos_v3_engine.dxf_to_3d_shell_extruder import MultiStoryCAD3DShellExtruder
            except ImportError:
                from engine.dxf_to_3d_shell_extruder import MultiStoryCAD3DShellExtruder
        _jb_cad = (_arch_req.get_json(silent=True) or {}) if _arch_req.method != "GET" else {}
        project_id = (_arch_req.args.get("project_id") if _arch_req.method == "GET" else _jb_cad.get("project_id")) or "default"
        project_sig_c = str((_arch_req.args.get("project_sig") if _arch_req.method == "GET" else _jb_cad.get("project_sig")) or "").strip()
        selected_file_c = str((_arch_req.args.get("selected_file") if _arch_req.method == "GET" else _jb_cad.get("selected_file")) or "").strip()
        upload_id_c = str((_arch_req.args.get("upload_id") if _arch_req.method == "GET" else _jb_cad.get("upload_id")) or "").strip()
        clean_pid = str(project_id).strip()
        if clean_pid.lower() in ("", "null", "none", "undefined"):
            clean_pid = "default"
        repo_root = _resolve_arch_repo_root()
        act_d, site_dir = _resolve_latest_active_ext_plan_json(
            repo_root, clean_pid, project_sig=project_sig_c, selected_file=selected_file_c, upload_id=upload_id_c
        )
        # v66.0: ALWAYS prefer the user's real uploaded 2D `.dwg`/`.dxf` file (`source_file`), NEVER `_vectorized.dxf`!
        src_cand = str(act_d.get("source_file") or "")
        if act_d.get("is_3d_model") or src_cand.lower().endswith((".obj", ".max", ".3ds", ".rvt", ".ifc", ".glb", ".gltf", ".fbx")):
            return _arch_jsonify({
                "ok": True,
                "is_3d_model": True,
                "source_filename": act_d.get("original_filename") or os.path.basename(src_cand),
                "canonical_layers": [],
                "preview_entities": [],
                "floors_2d": [],
                "text_entities": [],
            }), 200
        if src_cand.lower().endswith((".dwg", ".dxf")) and not src_cand.lower().endswith(("_vectorized.dxf", "_normalized_layers.dxf", "_elevations_and_sections.dxf")) and os.path.isfile(src_cand):
            cad_fp = src_cand
        else:
            cad_fp = ""
            cands_c = []
            search_dirs = [site_dir]
            for s_dir in search_dirs:
                if os.path.isdir(s_dir):
                    for fn in os.listdir(s_dir):
                        fn_l = fn.lower()
                        if fn_l.endswith((".dwg", ".dxf")) and not fn_l.endswith(("_vectorized.dxf", "_elevations_and_sections.dxf", "_normalized_layers.dxf")) and "1d49dd1a" not in fn_l:
                            fp = os.path.join(s_dir, fn)
                            # Prioritize .dwg files uploaded by the user
                            prio = 1 if fn_l.endswith(".dwg") else 0
                            cands_c.append((prio, os.path.getmtime(fp), fp))
            if cands_c:
                cands_c.sort(key=lambda x: (x[0], x[1]), reverse=True)
                cad_fp = cands_c[0][2]
        overrides = {}
        apply_all_floors = False
        if _arch_req.method == "POST":
            body = _arch_req.get_json(silent=True) or {}
            overrides = body.get("layer_overrides") or {}
            apply_all_floors = bool(body.get("apply_all_floors", False))
        res = MultiStoryCAD3DShellExtruder.auto_normalize_and_rewrite_dxf_layers(
            cad_fp, user_layer_overrides=overrides, apply_all_floors=apply_all_floors
        )
        if act_d.get("original_filename"):
            res["source_filename"] = act_d["original_filename"]
        return _arch_jsonify(res), 200

    def _handle_download_bim_bundle():
        import os, zipfile, tempfile
        from flask import send_file as _arch_send_file
        project_id = _arch_req.args.get("project_id") or "default"
        clean_pid = str(project_id).strip()
        if clean_pid.lower() in ("", "null", "none", "undefined"):
            clean_pid = "default"
        p_folder = clean_pid if clean_pid.startswith("project_") else f"project_{clean_pid}"
        repo_root = _resolve_arch_repo_root()
        site_dir = os.path.join(repo_root, "data", "projects", p_folder, "site")
        z_tmp = os.path.join(tempfile.gettempdir(), f"{p_folder}_Revit_BIM_Bundle_v50.zip")
        with zipfile.ZipFile(z_tmp, "w", zipfile.ZIP_DEFLATED) as zf:
            if os.path.isdir(site_dir):
                for fn in sorted(os.listdir(site_dir)):
                    if fn.endswith((".ifc", ".glb", ".obj", ".mtl", "_revit_journal.txt", "_build_revit_rvt.py", "_elevations_and_sections.dxf", "_normalized_layers.dxf")):
                        fp = os.path.join(site_dir, fn)
                        if os.path.isfile(fp):
                            zf.write(fp, arcname=fn)
        return _arch_send_file(z_tmp, as_attachment=True, download_name=f"{p_folder}_Revit_IFC_RVT_Bundle.zip")

    try:
        app.add_url_rule("/api/3d/scene_json", endpoint="archos_3d_scene_json_v48", view_func=_handle_3d_scene_json_query, methods=["GET"])
        app.add_url_rule("/api/cad/layers", endpoint="archos_cad_layers_v49", view_func=_handle_cad_layers_api, methods=["GET", "POST"])
        app.add_url_rule("/api/cad/reclassify_layers", endpoint="archos_cad_reclassify_v49", view_func=_handle_cad_layers_api, methods=["POST"])
        app.add_url_rule("/api/3d/download_bim", endpoint="archos_download_bim_v50", view_func=_handle_download_bim_bundle, methods=["GET"])
    except Exception:
        pass

    try:
        app.add_url_rule("/api/render/latest" , endpoint="archos_latest_render_v33_7", view_func=_handle_latest_render_query, methods=["GET"])
    except Exception:
        pass

    for _ep_route in (
        "/api/plan/upload_external",
        "/api/site/upload_plan",
        "/api/upload_plan",
    ):
        try:
            app.add_url_rule(
                _ep_route,
                endpoint=f"archos_extplan_{_ep_route.replace('/', '_')}",
                view_func=_handle_external_plan_upload_request,
                methods=["POST", "OPTIONS"],
            )
        except Exception:
            pass

    @app.before_request
    def _architectos_v27_1_krocki_interceptor():
        path_low = (_arch_req.path or "").lower()
        if _arch_req.method == "GET" and path_low.rstrip("/") == "/api/3d/scene_json":
            return _handle_3d_scene_json_query()
        if path_low.rstrip("/") in ("/api/cad/layers", "/api/cad/reclassify_layers"):
            return _handle_cad_layers_api()
        if _arch_req.method == "GET" and path_low.rstrip("/") == "/api/3d/download_bim":
            return _handle_download_bim_bundle()
        if _arch_req.method == "GET" and path_low.rstrip("/") == "/api/render/latest":
            return _handle_latest_render_query()
        if _arch_req.method in ("POST", "OPTIONS") and ("upload_external" in path_low or "upload_plan" in path_low):
            return _handle_external_plan_upload_request()
        if _arch_req.method in ("POST", "OPTIONS") and ("krocki" in path_low or "/api/site/upload" in path_low or "/api/site/parse" in path_low):
            return _handle_krocki_upload_request()
        if _arch_req.method == "POST" and path_low.rstrip("/") in ("/api/chat", "/api/render", "/api/generate"):
            _jb = _arch_req.get_json(silent=True) or {}
            if _jb.get("external_plan_upload_only") or _jb.get("action") == "upload_external_plan":
                return _handle_external_plan_upload_request()
            if _jb.get("krocki_upload_only") or _jb.get("action") == "upload_krocki":
                return _handle_krocki_upload_request()
            _pid = str(_jb.get("project_id") or _arch_req.args.get("project_id") or "")
            _repo = _resolve_arch_repo_root()
            if _pid:
                _sync_krocki_into_project_session(_repo, _pid)
                _sync_project_renders_and_assets(_repo, _pid)
            _user_txt = str(_jb.get("message") or _jb.get("prompt") or _jb.get("text") or "").strip()
            _has_ref_id = bool(_jb.get("reference_id") or _jb.get("reference") or _jb.get("style_reference"))
            if _is_3d_facade_render_chat_command(_user_txt) or (_has_ref_id and not any(k in _user_txt for k in ("پلان", "طراحی کن", "بساز"))):
                if path_low.rstrip("/") in ("/api/chat", "/api/render", "/api/generate"):
                    if not _user_txt and _has_ref_id:
                        _jb["message"] = "از این مدل سه‌بعدی با رفرنس سبک انتخابی رندر واقعی بگیر"
                    return _handle_plan_locked_3d_render_request(_jb)

    @app.after_request
    def _architectos_v30_asset_sync_after_request(response):
        try:
            path_low = (_arch_req.path or "").lower()
            if "/api/chat" in path_low or "/api/project" in path_low or "/api/session" in path_low:
                _jb = _arch_req.get_json(silent=True) or {}
                _pid = str(_jb.get("project_id") or _arch_req.args.get("project_id") or "")
                if _pid:
                    _sync_project_renders_and_assets(_resolve_arch_repo_root(), _pid)
        except Exception:
            pass
        return response

except Exception as _arch_hook_err:
    print("[!] Warning registering ArchitectOS v66.0 Krocki, External Plan & Render routes:", _arch_hook_err)
# [/ARCHITECTOS_V27_1_KROCKI_UPLOAD_INTERCEPTOR]


if __name__ == "__main__":


    api_server.run()