"""CODER-07C.2 trusted-consent bridge tests (offline only).

The Python artifacts are inert bytes.  This suite never imports or executes
them and uses only synthetic TEST-ONLY identities, secrets, and consent.
"""

import concurrent.futures
import hashlib
import inspect
import json
import os

import pytest

from core.runtime.local_authorization_v1 import (
    LocalRequestNonceLedger,
    sign_proxy_request,
)
from core.chat.execution_approval_foundation_v1 import DEFAULT_RESOURCE_LIMITS
from core.chat.trusted_execution_consent_bridge_v1 import (
    CONSENT_PATH,
    CONSUME_PATH,
    PREVIEW_PATH,
    TrustedExecutionConsentBridge,
)


SECRET = "synthetic-c07c2-secret-" + "s" * 40
ACTOR = "lsa_c07c2_actor"
SESSION = "lss_c07c2_session"
PROJECT = "project_c07c2"
SOURCE = b'def add(a, b):\n    return a + b\n'


def _signed(payload, path, nonce, *, actor=ACTOR, session=SESSION, now=1000):
    return sign_proxy_request(
        SECRET,
        actor_id=actor,
        session_id=session,
        payload=payload,
        path=path,
        nonce="nonce_" + str(nonce).zfill(32),
        now=now,
    )


def _saved(tmp_path):
    root = tmp_path / "code"
    root.mkdir(parents=True)
    artifact = root / "calculator.py"
    artifact.write_bytes(SOURCE)
    digest = hashlib.sha256(SOURCE).hexdigest()
    save = {
        "status": "created",
        "verified_on_disk": True,
        "writes_performed": 1,
        "project_id": PROJECT,
        "filename": artifact.name,
        "digest": digest,
    }
    return root, artifact, digest, save


def _preview_payload(digest, **updates):
    payload = {
        "operation": "prepare_execution_preview",
        "project_id": PROJECT,
        "filename": "calculator.py",
        "source_sha256": digest,
        "action": "run_python",
        "scope": "execute",
        "resource_limits": dict(DEFAULT_RESOURCE_LIMITS),
    }
    payload.update(updates)
    return payload


def _prepare(tmp_path, *, now=1000):
    root, artifact, digest, save = _saved(tmp_path)
    bridge = TrustedExecutionConsentBridge(test_mode=True)
    nonce_ledger = LocalRequestNonceLedger()
    payload = _preview_payload(digest)
    result = bridge.prepare_preview(
        proxy_secret=SECRET,
        headers=_signed(payload, PREVIEW_PATH, 1, now=now),
        payload=payload,
        path=PREVIEW_PATH,
        remote_addr="127.0.0.1",
        nonce_ledger=nonce_ledger,
        project_id=PROJECT,
        authorized_code_root=str(root),
        artifact_path=str(artifact),
        verified_save=save,
        now=now,
    )
    assert result["ok"] is True
    return bridge, nonce_ledger, root, artifact, digest, result


def _consent_payload(preview, digest, **updates):
    payload = {
        "operation": "record_execution_consent",
        "proposal_id": preview["proposal_id"],
        "project_id": PROJECT,
        "filename": "calculator.py",
        "source_sha256": digest,
        "action": "run_python",
        "scope": "execute",
        "consent": True,
    }
    payload.update(updates)
    return payload


def _consent(bridge, nonce_ledger, preview, digest, *, nonce=2, now=1001,
             actor=ACTOR, session=SESSION, **updates):
    payload = _consent_payload(preview, digest, **updates)
    return bridge.record_test_only_consent(
        proxy_secret=SECRET,
        headers=_signed(
            payload, CONSENT_PATH, nonce, actor=actor, session=session, now=now),
        payload=payload,
        path=CONSENT_PATH,
        remote_addr="127.0.0.1",
        nonce_ledger=nonce_ledger,
        project_id=PROJECT,
        now=now,
        label="TEST-ONLY synthetic signed consent",
    )


def _consume_payload(grant, digest, **updates):
    payload = {
        "operation": "consume_execution_capability",
        "capability_id": grant["capability_id"],
        "project_id": PROJECT,
        "filename": "calculator.py",
        "source_sha256": digest,
        "action": "run_python",
        "scope": "execute",
        "resource_limits": dict(DEFAULT_RESOURCE_LIMITS),
    }
    payload.update(updates)
    return payload


def _consume(bridge, nonce_ledger, artifact, grant, digest, *, nonce=3,
             now=1002, actor=ACTOR, session=SESSION, **updates):
    payload = _consume_payload(grant, digest, **updates)
    return bridge.consume_test_only_capability(
        proxy_secret=SECRET,
        headers=_signed(
            payload, CONSUME_PATH, nonce, actor=actor, session=session, now=now),
        payload=payload,
        path=CONSUME_PATH,
        remote_addr="127.0.0.1",
        nonce_ledger=nonce_ledger,
        project_id=PROJECT,
        artifact_path=str(artifact),
        now=now,
    )


def test_valid_signed_request_produces_safe_preview_not_capability(tmp_path):
    bridge, ledger, root, artifact, digest, result = _prepare(tmp_path)

    assert result["stage"] == "execution_proposal_available"
    assert result["preview"] == {
        "project_id": PROJECT,
        "filename": "calculator.py",
        "source_sha256": digest,
        "action": "run_python",
        "scope": "execute",
        "resource_limits": dict(DEFAULT_RESOURCE_LIMITS),
        "network_policy": "none",
        "host_mounts": [],
        "approval_expires_at": 1120.0,
        "save_and_run_require_separate_approvals": True,
    }
    assert result["capability_minted"] is False
    assert "token" not in json.dumps(result).lower()


@pytest.mark.parametrize("case,expected", [
    ("forged", "proxy_signature_invalid"),
    ("wrong_path", "proxy_signature_invalid"),
    ("wrong_payload", "proxy_signature_invalid"),
    ("expired", "proxy_signature_expired"),
    ("spoofed_actor", "proxy_signature_invalid"),
])
def test_invalid_trust_proofs_are_refused(tmp_path, case, expected):
    root, artifact, digest, save = _saved(tmp_path)
    bridge = TrustedExecutionConsentBridge(test_mode=True)
    ledger = LocalRequestNonceLedger()
    payload = _preview_payload(digest)
    headers = _signed(payload, PREVIEW_PATH, 10, now=1000)
    call_path = PREVIEW_PATH
    call_payload = payload
    call_now = 1000
    if case == "forged":
        headers["X-ArchitectOS-Signature"] = "0" * 64
    elif case == "wrong_path":
        call_path = "/wrong/path"
    elif case == "wrong_payload":
        call_payload = dict(payload, filename="other.py")
    elif case == "expired":
        call_now = 1061
    elif case == "spoofed_actor":
        headers["X-ArchitectOS-Actor"] = "lsa_spoofed"

    result = bridge.prepare_preview(
        proxy_secret=SECRET, headers=headers, payload=call_payload,
        path=call_path, remote_addr="127.0.0.1", nonce_ledger=ledger,
        project_id=PROJECT, authorized_code_root=str(root),
        artifact_path=str(artifact), verified_save=save, now=call_now,
    )
    assert result["ok"] is False
    assert result["reason"] == expected


def test_proxy_nonce_is_one_shot(tmp_path):
    root, artifact, digest, save = _saved(tmp_path)
    bridge = TrustedExecutionConsentBridge(test_mode=True)
    ledger = LocalRequestNonceLedger()
    payload = _preview_payload(digest)
    headers = _signed(payload, PREVIEW_PATH, 11)
    kwargs = dict(
        proxy_secret=SECRET, headers=headers, payload=payload,
        path=PREVIEW_PATH, remote_addr="127.0.0.1", nonce_ledger=ledger,
        project_id=PROJECT, authorized_code_root=str(root),
        artifact_path=str(artifact), verified_save=save, now=1000,
    )
    assert bridge.prepare_preview(**kwargs)["ok"] is True
    assert bridge.prepare_preview(**kwargs)["reason"] == "proxy_nonce_replayed"


def test_cross_project_and_caller_declared_identity_are_refused(tmp_path):
    root, artifact, digest, save = _saved(tmp_path)
    bridge = TrustedExecutionConsentBridge(test_mode=True)
    payload = _preview_payload(
        digest, project_id="project_other", actor_id=ACTOR,
        session_id=SESSION, trusted=True)
    result = bridge.prepare_preview(
        proxy_secret=SECRET,
        headers=_signed(payload, PREVIEW_PATH, 12), payload=payload,
        path=PREVIEW_PATH, remote_addr="127.0.0.1",
        nonce_ledger=LocalRequestNonceLedger(), project_id=PROJECT,
        authorized_code_root=str(root), artifact_path=str(artifact),
        verified_save=save, now=1000,
    )
    assert result["ok"] is False
    assert result["reason"] == "execution_preview_payload_invalid"


def test_wrong_signed_digest_and_artifact_are_refused(tmp_path):
    root, artifact, digest, save = _saved(tmp_path)
    bridge = TrustedExecutionConsentBridge(test_mode=True)
    payload = _preview_payload("0" * 64, filename="other.py")
    result = bridge.prepare_preview(
        proxy_secret=SECRET,
        headers=_signed(payload, PREVIEW_PATH, 13), payload=payload,
        path=PREVIEW_PATH, remote_addr="127.0.0.1",
        nonce_ledger=LocalRequestNonceLedger(), project_id=PROJECT,
        authorized_code_root=str(root), artifact_path=str(artifact),
        verified_save=save, now=1000,
    )
    assert result["ok"] is False
    assert result["reason"] == "execution_artifact_binding_mismatch"


def test_save_does_not_mint_and_text_is_not_consent(tmp_path):
    bridge, ledger, root, artifact, digest, preview = _prepare(tmp_path)
    status = bridge.inspect_status(preview["proposal_id"], now=1000)
    assert status["capability_minted"] is False

    payload = {"text": "yes, run it", "project_id": PROJECT}
    refused = bridge.record_test_only_consent(
        proxy_secret=SECRET,
        headers=_signed(payload, CONSENT_PATH, 14), payload=payload,
        path=CONSENT_PATH, remote_addr="127.0.0.1", nonce_ledger=ledger,
        project_id=PROJECT, now=1000,
        label="TEST-ONLY synthetic signed consent",
    )
    assert refused["reason"] == "execution_consent_payload_invalid"
    assert bridge.inspect_status(preview["proposal_id"], now=1000)["capability_minted"] is False


def test_test_only_consent_mints_server_custodied_token_without_disclosure(tmp_path):
    bridge, ledger, root, artifact, digest, preview = _prepare(tmp_path)
    grant = _consent(bridge, ledger, preview, digest)

    assert grant["ok"] is True
    assert grant["stage"] == "execution_capability_minted"
    assert grant["event_kind"] == "TEST-ONLY"
    rendered = json.dumps(grant)
    assert "exc_" not in rendered
    assert "token" not in rendered.lower()
    assert SECRET not in rendered
    assert str(artifact) not in rendered


def test_non_test_bridge_cannot_record_synthetic_consent(tmp_path):
    _bridge, ledger, root, artifact, digest, preview = _prepare(tmp_path)
    production_shaped = TrustedExecutionConsentBridge(test_mode=False)
    payload = _consent_payload(preview, digest)
    refused = production_shaped.record_test_only_consent(
        proxy_secret=SECRET,
        headers=_signed(payload, CONSENT_PATH, 18),
        payload=payload,
        path=CONSENT_PATH,
        remote_addr="127.0.0.1",
        nonce_ledger=ledger,
        project_id=PROJECT,
        now=1001,
        label="TEST-ONLY synthetic signed consent",
    )
    assert refused["reason"] == "test_only_execution_consent_refused"


def test_cross_session_cross_project_and_save_scope_consent_are_refused(tmp_path):
    bridge, ledger, root, artifact, digest, preview = _prepare(tmp_path)
    wrong_actor = _consent(
        bridge, ledger, preview, digest, nonce=19,
        actor="lsa_other_actor")
    assert wrong_actor["reason"] == "execution_approval_binding_mismatch"

    wrong_session = _consent(
        bridge, ledger, preview, digest, nonce=20,
        session="lss_other_session")
    assert wrong_session["reason"] == "execution_approval_binding_mismatch"

    cross_project = _consent(
        bridge, ledger, preview, digest, nonce=21,
        project_id="project_other")
    assert cross_project["reason"] == "execution_consent_project_mismatch"

    save_scope = _consent(
        bridge, ledger, preview, digest, nonce=22, scope="save")
    assert save_scope["reason"] == "execution_consent_payload_invalid"

    wrong_artifact = _consent(
        bridge, ledger, preview, digest, nonce=23, filename="other.py")
    assert wrong_artifact["reason"] == "execution_consent_binding_mismatch"


def test_changed_bytes_and_expired_proposal_block_consent(tmp_path):
    bridge, ledger, root, artifact, digest, preview = _prepare(tmp_path)
    artifact.write_bytes(b'print("changed")\n')
    changed = _consent(bridge, ledger, preview, digest, nonce=30)
    assert changed["reason"] == "execution_source_changed_before_approval"

    root2 = tmp_path / "second" / "code"
    root2.mkdir(parents=True)
    artifact2 = root2 / "calculator.py"
    artifact2.write_bytes(SOURCE)
    save2 = {
        "status": "created", "verified_on_disk": True,
        "writes_performed": 1, "project_id": PROJECT,
        "filename": artifact2.name, "digest": digest,
    }
    payload2 = _preview_payload(digest)
    preview2 = bridge.prepare_preview(
        proxy_secret=SECRET, headers=_signed(payload2, PREVIEW_PATH, 31),
        payload=payload2, path=PREVIEW_PATH, remote_addr="127.0.0.1",
        nonce_ledger=ledger, project_id=PROJECT,
        authorized_code_root=str(root2), artifact_path=str(artifact2),
        verified_save=save2, now=1000,
    )
    expired = _consent(bridge, ledger, preview2, digest, nonce=32, now=1121)
    assert expired["reason"] == "execution_proposal_expired"


def test_expired_double_and_concurrent_capability_consumption(tmp_path):
    bridge, ledger, root, artifact, digest, preview = _prepare(tmp_path)
    grant = _consent(bridge, ledger, preview, digest)
    expired = _consume(
        bridge, ledger, artifact, grant, digest, nonce=40, now=1122)
    assert expired["reason"] == "execution_capability_expired"

    bridge2, ledger2, root2, artifact2, digest2, preview2 = _prepare(
        tmp_path / "fresh")
    grant2 = _consent(bridge2, ledger2, preview2, digest2)
    first = _consume(bridge2, ledger2, artifact2, grant2, digest2, nonce=41)
    replay = _consume(bridge2, ledger2, artifact2, grant2, digest2, nonce=42)
    assert first["ok"] is True and first["executed"] is False
    assert replay["ok"] is False

    bridge3, ledger3, root3, artifact3, digest3, preview3 = _prepare(
        tmp_path / "concurrent")
    grant3 = _consent(bridge3, ledger3, preview3, digest3)

    def claim(index):
        return _consume(
            bridge3, ledger3, artifact3, grant3, digest3,
            nonce=100 + index)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(claim, range(8)))
    assert sum(item["ok"] is True for item in outcomes) == 1
    assert all(item.get("executed") is not True for item in outcomes)


def test_restart_invalidation_discards_server_token_custody(tmp_path):
    bridge, ledger, root, artifact, digest, preview = _prepare(tmp_path)
    grant = _consent(bridge, ledger, preview, digest)
    bridge.invalidate_all(now=1002)

    refused = _consume(
        bridge, ledger, artifact, grant, digest, nonce=50, now=1003)
    assert refused["reason"] == "execution_capability_not_available"


def test_bridge_is_internal_and_not_reachable_from_live_chat_dispatch():
    import app
    import core.chat.chat_architect as chat_architect
    import core.chat.trusted_execution_consent_bridge_v1 as bridge_module
    import ui.routes.chat_routes as chat_routes

    bridge_name = "trusted_execution_consent_bridge_v1"
    for module in (app, chat_architect, chat_routes):
        source = open(module.__file__, "r", encoding="utf-8").read()
        assert bridge_name not in source

    bridge_source = inspect.getsource(bridge_module).lower()
    assert "@app.route" not in bridge_source
    assert "flask" not in bridge_source
    assert "subprocess" not in bridge_source
    assert "docker" not in bridge_source
    assert "execution_enabled = true" not in bridge_source
    assert "def execute" not in bridge_source



# [ARCHITECTOS_V27_1_KROCKI_UPLOAD_INTERCEPTOR]
try:
    from flask import request as _arch_req, jsonify as _arch_jsonify

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

    def _sync_project_renders_and_assets(repo_root: str, project_id: str) -> None:
        import os
        import shutil
        clean_pid = str(project_id or "").strip()
        if clean_pid.lower() in ("", "null", "none", "undefined"):
            return
        p_folder = clean_pid if clean_pid.startswith("project_") else f"project_{clean_pid}"
        dir_a = os.path.join(repo_root, "outputs", "plans", p_folder, "renders")
        dir_b = os.path.join(repo_root, "data", "projects", p_folder, "renders")
        os.makedirs(dir_a, exist_ok=True)
        os.makedirs(dir_b, exist_ok=True)
        for src_d, dst_d in ((dir_a, dir_b), (dir_b, dir_a)):
            try:
                for fn in os.listdir(src_d):
                    if fn.endswith((".png", ".svg", ".dxf", ".json", ".jpg")):
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
        p_folder = clean_pid if clean_pid.startswith("project_") else f"project_{clean_pid}"
        for state_file in (
            os.path.join(repo_root, "data", "projects", p_folder, "session_state.json"),
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
        raw_q = str(
            jbody.get("quality")
            or jbody.get("render_quality")
            or jbody.get("preset")
            or jbody.get("quality_preset")
            or _arch_req.args.get("quality")
            or "draft"
        ).strip().lower()
        if any(w in user_msg.lower() for w in ("کیفیت بالا", "نهایی", "high", "final", "ultra")):
            quality = "high"
        elif any(w in user_msg.lower() for w in ("سریع", "درفت", "تست", "draft", "fast", "preview")):
            quality = "draft"
        elif raw_q in ("auto", ""):
            quality = "draft"
        else:
            quality = raw_q
        clean_pid = str(jbody.get("project_id") or _arch_req.args.get("project_id") or "default").strip()
        if clean_pid.lower() in ("", "null", "none", "undefined"):
            clean_pid = "default"
        p_folder = clean_pid if clean_pid.startswith("project_") else f"project_{clean_pid}"
        _sync_krocki_into_project_session(repo_root, clean_pid)

        st_path_plans = os.path.join(repo_root, "outputs", "plans", p_folder, "session_state.json")
        st_path_data = os.path.join(repo_root, "data", "projects", p_folder, "session_state.json")
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

        from core.site.krocki_cad_reader_v27 import load_active_external_plan_state
        krocki = load_active_krocki_state(repo_root, clean_pid)
        ext_plan_now = load_active_external_plan_state(repo_root, clean_pid)
        if not isinstance(plan_params, dict):
            plan_params = parse_architectural_prompt(user_msg, active_site_krocki=krocki)
        if isinstance(ext_plan_now, dict) and ext_plan_now.get("total_floors"):
            _tot_e = int(ext_plan_now.get("total_floors", 1))
            _typ_e = str(ext_plan_now.get("typology", "MULTIFLOOR_RESIDENTIAL" if _tot_e >= 3 else ("DUPLEX_2FLOOR" if _tot_e == 2 else "VILLA_1FLOOR")))
            plan_params["typology"] = _typ_e
            plan_params["is_duplex"] = (_typ_e == "DUPLEX_2FLOOR")
            plan_params["floor_count"] = max(2, _tot_e - 1) if _typ_e == "MULTIFLOOR_RESIDENTIAL" else _tot_e
            plan_params["building_placement"] = str(ext_plan_now.get("building_placement") or "NORTH")
            plan_params["coverage_ratio"] = float(ext_plan_now.get("coverage_ratio", 0.65))
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
        if plan_params.get("universal_facade_spec"):
            r_state["universal_facade_spec"] = plan_params["universal_facade_spec"]
        if plan_params.get("custom_facade_profile"):
            r_state["custom_facade_profile"] = plan_params["custom_facade_profile"]
        plan_params["active_render_state"] = r_state
        plan_params["render_facade_side"] = r_state["facade_side"]
        plan_params["facade_style_fa"] = r_state["style_label_fa"]
        plan_params["facade_material_fa"] = r_state["stone_label_fa"]
        plan_params["render_lighting_mode"] = r_state["lighting_mode"]

        synth = ParametricArchitecturalSynthesizer()
        project_res = synth.synthesize_from_params(plan_params)
        spec = ComfyUIRenderBridge.parse_render_request_from_chat("", prev_render_state=r_state, plan_params=plan_params)

        out_dir_plans = os.path.join(repo_root, "outputs", "plans", p_folder, "renders")
        out_dir_data = os.path.join(repo_root, "data", "projects", p_folder, "renders")
        os.makedirs(out_dir_plans, exist_ok=True)
        os.makedirs(out_dir_data, exist_ok=True)

        existing_renders = [fn for fn in os.listdir(out_dir_data) if fn.startswith("render_") and fn.endswith(".png") and not fn.endswith(("_depth.png", "_lineart.png"))]
        next_ord = len(existing_renders) + 1
        render_fn = f"render_{next_ord:03d}_{uuid.uuid4().hex[:6]}.png"
        scaffold_png_path = os.path.join(out_dir_data, render_fn)

        _, prompt_en = ComfyUIRenderBridge.export_plan_locked_south_facade_png(
            project_res,
            scaffold_png_path,
            chat_text="",
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

        final_png_path = scaffold_png_path
        comfy_status = "PLAN_LOCKED_3D_RAYSHADED_V33"
        try:
            bridge = ComfyUIRenderBridge()
            c_res = bridge.render_via_comfyui(
                project_res,
                user_msg,
                controlnet_png_path=scaffold_png_path,
                output_dir=out_dir_data,
                timeout_sec=240 if quality in ("draft", "preview", "fast", "auto") else 1200,
                quality=quality,
            )
            if c_res.get("status") == "RENDERED_BY_COMFYUI" and c_res.get("render_png_path") and os.path.isfile(c_res["render_png_path"]):
                shutil.copy2(c_res["render_png_path"], scaffold_png_path)
                comfy_status = "COMFYUI_IMG2IMG_PLAN_LOCKED_V33"
        except Exception:
            pass

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
        v51.0 Universal External Plan, Multi-Floor Typical Plan (via Elevation Codes) & 2D Elevation/Section Upload Handler:
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
        clean_pid = str(project_id).strip()
        if clean_pid.lower() in ("", "null", "none", "undefined"):
            clean_pid = "default"
        p_folder = clean_pid if clean_pid.startswith("project_") else f"project_{clean_pid}"
        proj_dir = os.path.join(repo_root, "data", "projects", p_folder)
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
                if raw_ext not in (".dxf", ".dwg", ".3ds", ".rvt", ".ifc", ".obj", ".glb", ".gltf", ".fbx", ".pdf", ".png", ".jpg", ".jpeg", ".webp", ".svg"):
                    raw_ext = ".dwg"
                saved_path = os.path.join(site_dir, f"ext_plan_{uuid.uuid4().hex[:8]}{raw_ext}")
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
            ext_info = parse_external_plan_or_elevation(saved_path, user_hint=user_hint)
            ext_info["original_filename"] = orig_name
            save_active_external_plan_state(repo_root, clean_pid, ext_info, sync_global_default=True)
            _sync_krocki_into_project_session(repo_root, clean_pid)
            # Also sync to the most recently active project_* directory so UI Chat and Studio always see the exact uploaded file!
            try:
                projs_root = os.path.join(repo_root, "data", "projects")
                if os.path.isdir(projs_root):
                    p_cands = []
                    for pn in os.listdir(projs_root):
                        pd = os.path.join(projs_root, pn)
                        if pn.startswith("project_") and pn not in ("project_default", "project_v337b_probe") and os.path.isdir(pd):
                            st_f = os.path.join(pd, "session_state.json")
                            mt = os.path.getmtime(st_f) if os.path.isfile(st_f) else os.path.getmtime(pd)
                            p_cands.append((mt, pn))
                    p_cands.sort(key=lambda x: x[0], reverse=True)
                    for _, recent_pn in p_cands[:2]:
                        save_active_external_plan_state(repo_root, recent_pn, ext_info, sync_global_default=False)
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
        p_folder = clean_pid if clean_pid.startswith("project_") else f"project_{clean_pid}"
        proj_dir = os.path.join(repo_root, "data", "projects", p_folder)
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
        p_folder = pid if pid.startswith("project_") else f"project_{pid}"
        _sync_project_renders_and_assets(repo_root, pid)
        cands = []
        for r_dir in (
            os.path.join(repo_root, "data", "projects", p_folder, "renders"),
            os.path.join(repo_root, "outputs", "plans", p_folder, "renders"),
            os.path.join(repo_root, "data", "projects", "project_default", "renders"),
        ):
            if os.path.isdir(r_dir):
                for fn in os.listdir(r_dir):
                    if fn.startswith("render_") and fn.endswith((".png", ".jpg")) and not fn.endswith(("_depth.png", "_lineart.png", "_comfy_input.png")) and "_comfy_" not in fn and "_depth_" not in fn:
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

    def _resolve_latest_active_ext_plan_json(repo_root: str, clean_pid: str):
        import json, os
        p_folder = clean_pid if clean_pid.startswith("project_") else f"project_{clean_pid}"
        cands_j = []
        for jp in (
            os.path.join(repo_root, "data", "projects", p_folder, "site", "active_external_plan.json"),
            os.path.join(repo_root, "data", "active_external_plan.json"),
            os.path.join(repo_root, "data", "projects", "project_default", "site", "active_external_plan.json"),
        ):
            if os.path.isfile(jp):
                try:
                    with open(jp, "r", encoding="utf-8") as f:
                        d = json.load(f)
                    cands_j.append((float(d.get("uploaded_at_ts") or os.path.getmtime(jp)), d, os.path.dirname(jp)))
                except Exception:
                    pass
        if cands_j:
            cands_j.sort(key=lambda x: x[0], reverse=True)
            return cands_j[0][1], cands_j[0][2]
        return {}, os.path.join(repo_root, "data", "projects", p_folder, "site")

    def _handle_3d_scene_json_query():
        import json, os
        project_id = _arch_req.args.get("project_id") or "default"
        clean_pid = str(project_id).strip()
        if clean_pid.lower() in ("", "null", "none", "undefined"):
            clean_pid = "default"
        repo_root = _resolve_arch_repo_root()
        act_d, site_dir = _resolve_latest_active_ext_plan_json(repo_root, clean_pid)
        sj_direct = str(act_d.get("scene_3d_json_path") or "")
        if sj_direct and os.path.isfile(sj_direct):
            with open(sj_direct, "r", encoding="utf-8") as jf:
                data = json.load(jf)
            data["ok"] = True
            data["source_filename"] = act_d.get("original_filename") or os.path.basename(str(act_d.get("source_file") or ""))
            data["is_3d_model"] = bool(act_d.get("is_3d_model") or act_d.get("is_direct_3d_bim_import"))
            data["total_floors"] = int(act_d.get("total_floors") or 1)
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
        from engine.dxf_to_3d_shell_extruder import MultiStoryCAD3DShellExtruder
        project_id = (_arch_req.args.get("project_id") if _arch_req.method == "GET" else (_arch_req.get_json(silent=True) or {}).get("project_id")) or "default"
        clean_pid = str(project_id).strip()
        if clean_pid.lower() in ("", "null", "none", "undefined"):
            clean_pid = "default"
        repo_root = _resolve_arch_repo_root()
        act_d, site_dir = _resolve_latest_active_ext_plan_json(repo_root, clean_pid)
        cad_fp = str(act_d.get("vectorized_dxf_path") or act_d.get("source_file") or "")
        if not cad_fp or not os.path.isfile(cad_fp):
            cands_c = []
            if os.path.isdir(site_dir):
                for fn in os.listdir(site_dir):
                    if fn.lower().endswith((".dwg", ".dxf")) and not fn.lower().endswith(("_elevations_and_sections.dxf", "_normalized_layers.dxf")) and "1d49dd1a" not in fn:
                        fp = os.path.join(site_dir, fn)
                        cands_c.append((os.path.getmtime(fp), fp))
            if cands_c:
                cands_c.sort(key=lambda x: x[0], reverse=True)
                cad_fp = cands_c[0][1]
        overrides = {}
        apply_all_floors = True
        if _arch_req.method == "POST":
            body = _arch_req.get_json(silent=True) or {}
            overrides = body.get("layer_overrides") or {}
            apply_all_floors = bool(body.get("apply_all_floors", True))
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
            _is_ui_proxy = os.path.basename(os.path.dirname(os.path.abspath(__file__))).lower() == "ui"
            if _is_3d_facade_render_chat_command(_user_txt):
                if path_low.rstrip("/") in ("/api/chat", "/api/render", "/api/generate"):
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
    print("[!] Warning registering ArchitectOS v51.0 Krocki, External Plan & Render routes:", _arch_hook_err)
# [/ARCHITECTOS_V27_1_KROCKI_UPLOAD_INTERCEPTOR]
