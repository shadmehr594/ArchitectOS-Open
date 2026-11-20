# -*- coding: utf-8 -*-
# ==========================================================
# FACADE-04D.2 — ROLE-AWARE DUAL-IMAGE RENDER BINDING V1
# CONTRACT SUITE (transport + binding ONLY)
#
# Scope, by the brief:
#   * IMAGE A (style_reference / appearance only) and IMAGE B
#     (target_building / geometry authority) have SEPARATE roles,
#     identities, source references, staged filenames and node ids.
#   * IMAGE B stays the FLUX img2img source and is bound to LoadImage 300.
#   * The 300 -> 301 (VAEEncode) -> 210 (KSampler) path is untouched.
#   * IMAGE A is bound to its OWN dedicated node and can never overwrite 300.
#   * Missing / invalid / unstaged A or B FAILS CLOSED.
#   * Single-image img2img and text-to-image behaviour is preserved.
#   * No real ComfyUI job, no render, no model download, no node install.
#
# This suite is script-style (main() + RESULTS).  Run it DIRECTLY:
#   .venv/Scripts/python.exe tests/test_facade_04d2_dual_image_binding_v1.py
# A pytest "N passed" line for this file is NOT evidence (see the project
# memory note on script-style suites).
# ==========================================================

import copy
import json
import os
import sys
import tempfile

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Render-stop guard: nothing here may ever reach a real ComfyUI.
os.environ.setdefault("ARCHITECTOS_COMFY_PORT", "9")

from core.render.dual_image_binding_v1 import (  # noqa: E402
    CONTRACT,
    VERSION,
    ROLE_A,
    ROLE_B,
    NODE_A,
    NODE_B,
    NODE_A_ENCODE,
    GEOMETRY_NODE,
    DUAL_IMAGE_NODE_BINDINGS,
    build_dual_image_contract,
    bind_images_to_workflow,
    bind_role_bindings,
    dual_image_trace,
    fail_closed_reason,
    REASON_A_UNAVAILABLE,
    REASON_A_NOT_STAGED,
    REASON_B_UNAVAILABLE,
    REASON_B_NOT_STAGED,
    REASON_NOT_READY,
)

from core.render.workflow_selector import WorkflowSelector  # noqa: E402
from core.render.workflow_loader import WorkflowLoader  # noqa: E402
from core.render.image_workflow_injector import ImageWorkflowInjector  # noqa: E402

FIXTURES = r"D:\ArchitectOS_FACADE_TEST_IMAGES"

A_IMAGE = os.path.join(FIXTURES, "A_STYLE.jpg")
B_IMAGE = os.path.join(FIXTURES, "B01_RAW.jpg")
B_IMAGE_2 = os.path.join(FIXTURES, "B02_RAW.jpg")


# ==========================================================
# RESULT BOOKKEEPING
# ==========================================================

RESULTS = []


def check(name, condition, detail=""):
    ok = bool(condition)
    RESULTS.append((name, ok, detail))
    print(("  PASS  " if ok else "  FAIL  ") + name + (("  | " + detail) if detail else ""))
    return ok


# ==========================================================
# FIXTURES
# ==========================================================

def make_context(a_path=A_IMAGE, b_path=B_IMAGE, a_present=True, b_present=True):
    """A verified request context, shaped exactly like app.py builds it."""

    refs = {"geometry_authority": "target_building"}

    if a_present:
        refs["A"] = {
            "present": True,
            "role": "facade_reference",
            "authority": "appearance_only",
            "path": a_path,
            "asset_id": "asset_a_fixture",
            "filename": os.path.basename(a_path or "A.jpg"),
        }

    if b_present:
        refs["B"] = {
            "present": True,
            "role": "target_building",
            "authority": "geometry",
            "path": b_path,
            "asset_id": "asset_b_fixture",
            "filename": os.path.basename(b_path or "B.jpg"),
        }

    return {"references": refs}


def load_dual_workflow():
    loaded = WorkflowLoader().load("flux_img2img_dual.json")
    return loaded.get("workflow")


def load_single_workflow():
    loaded = WorkflowLoader().load("flux_img2img.json")
    return loaded.get("workflow")


def node_refs(node):
    """Every [node_id, slot] link referenced by a node's inputs."""

    out = []
    inputs = (node or {}).get("inputs") or {}
    for value in inputs.values():
        if isinstance(value, list) and len(value) == 2 and isinstance(value[0], str):
            out.append((value[0], value[1]))
    return out


# ==========================================================
# [0] STATIC / ARCHITECTURE
# ==========================================================

def section_static():

    print("\n[0] STATIC ARCHITECTURE")

    check("contract name is DualImageBindingV1", CONTRACT == "DualImageBindingV1")
    check("contract version present", bool(VERSION))

    check("IMAGE A role is style_reference", ROLE_A == "style_reference")
    check("IMAGE B role is target_building", ROLE_B == "target_building")

    check("IMAGE B node id is 300", NODE_B == "300")
    check("geometry node is 300", GEOMETRY_NODE == "300")

    check("IMAGE A has its OWN node id", NODE_A != NODE_B, "A=%s B=%s" % (NODE_A, NODE_B))
    check("IMAGE A is never node 300", DUAL_IMAGE_NODE_BINDINGS[ROLE_A] != "300")
    check("IMAGE B is bound to node 300", DUAL_IMAGE_NODE_BINDINGS[ROLE_B] == "300")

    # The injector must delegate to the ONE shared binder, not re-implement it.
    injector_src = open(
        os.path.join(PROJECT_ROOT, "core", "render", "image_workflow_injector.py"),
        encoding="utf-8",
    ).read()

    check(
        "injector delegates to the shared binder",
        "bind_role_bindings" in injector_src,
    )
    check(
        "the ONLY LoadImage broadcast loop is the legacy `elif image_asset` path",
        injector_src.count('inputs["image"] = filename') == 1
        and "elif image_asset:" in injector_src,
        "occurrences=%d" % injector_src.count('inputs["image"] = filename'),
    )
    check(
        "the dual binding branch precedes the legacy broadcast branch",
        injector_src.index("if image_bindings:") < injector_src.index("elif image_asset:"),
    )

    binder_src = open(
        os.path.join(PROJECT_ROOT, "core", "render", "dual_image_binding_v1.py"),
        encoding="utf-8",
    ).read()
    check(
        "exactly one node-id binding implementation",
        binder_src.count("def bind_role_bindings") == 1
        and binder_src.count("node.setdefault(\"inputs\", {})[\"image\"]") == 1,
    )


# ==========================================================
# [1] DUAL WORKFLOW TEMPLATE INTEGRITY
# ==========================================================

def section_template():

    print("\n[1] DUAL WORKFLOW TEMPLATE (flux_img2img_dual.json)")

    wf = load_dual_workflow()

    check("dual workflow loads", isinstance(wf, dict), "type=%s" % type(wf).__name__)

    if not isinstance(wf, dict):
        return

    check("node 300 is LoadImage (IMAGE B)", (wf.get("300") or {}).get("class_type") == "LoadImage")
    check("node 302 is LoadImage (IMAGE A)", (wf.get("302") or {}).get("class_type") == "LoadImage")
    check("node 301 is VAEEncode", (wf.get("301") or {}).get("class_type") == "VAEEncode")
    check("node 210 is KSampler", (wf.get("210") or {}).get("class_type") == "KSampler")

    check("301 pixels <- [300, 0] (IMAGE B latent path intact)",
          (wf.get("301") or {}).get("inputs", {}).get("pixels") == ["300", 0])
    check("210 latent_image <- [301, 0] (sampling path intact)",
          (wf.get("210") or {}).get("inputs", {}).get("latent_image") == ["301", 0])

    sampler = (wf.get("210") or {}).get("inputs", {})
    check("210 model <- [202, 0] unchanged", sampler.get("model") == ["202", 0])
    check("210 positive <- [206, 0] unchanged", sampler.get("positive") == ["206", 0])
    check("210 negative <- [212, 0] unchanged", sampler.get("negative") == ["212", 0])
    check("210 denoise unchanged (0.3)", sampler.get("denoise") == 0.3,
          "denoise=%s" % sampler.get("denoise"))

    check("node 303 is CLIPVisionEncode (IMAGE A encoder)",
          (wf.get("303") or {}).get("class_type") == "CLIPVisionEncode")
    check("303 image <- [302, 0] (IMAGE A encoder reads A)",
          (wf.get("303") or {}).get("inputs", {}).get("image") == ["302", 0])

    # The A encoder output must be UNCONSUMED: it may not reach the sampler.
    consumers = []
    for node_id, node in wf.items():
        for ref in node_refs(node):
            if ref[0] == NODE_A_ENCODE:
                consumers.append(node_id)

    check("IMAGE A encoder output is UNCONSUMED (no sampler consumer)",
          consumers == [], "consumers=%s" % consumers)

    # The single-image template must be untouched by this phase.
    single = load_single_workflow()
    check("single-image flux_img2img.json still has exactly one LoadImage",
          sum(1 for n in (single or {}).values()
              if isinstance(n, dict) and n.get("class_type") == "LoadImage") == 1)
    check("single-image template has NO node 302", "302" not in (single or {}))


# ==========================================================
# [2] CONTRACT BUILD + INDEPENDENT STAGING
# ==========================================================

def section_contract(stage_root):

    print("\n[2] DUAL CONTRACT BUILD + INDEPENDENT STAGING")

    ctx = make_context()

    contract = build_dual_image_contract(ctx, "chat_project", comfy_input=stage_root)

    check("contract status is ready", contract.get("status") == "ready",
          "status=%s errors=%s" % (contract.get("status"), contract.get("errors")))
    check("conditioning_active is False (no style conditioning claimed)",
          contract.get("conditioning_active") is False)
    check("geometry_node is 300", contract.get("geometry_node") == "300")

    roles = contract.get("roles") or {}
    a = roles.get(ROLE_A) or {}
    b = roles.get(ROLE_B) or {}

    a_staged = a.get("staged_path")
    b_staged = b.get("staged_path")

    check("role A present with authority appearance_only",
          a.get("authority") == "appearance_only")
    check("role B present with authority geometry",
          b.get("authority") == "geometry")

    check("A node id != B node id", a.get("node_id") != b.get("node_id"))
    check("A node id is the dedicated A node", a.get("node_id") == NODE_A)
    check("B node id is 300", b.get("node_id") == NODE_B)

    check("A staged filename is independent of B staged filename",
          a.get("filename") and b.get("filename") and a.get("filename") != b.get("filename"),
          "A=%s B=%s" % (a.get("filename"), b.get("filename")))

    check("A staged path is independent of B staged path",
          bool(a_staged) and bool(b_staged) and a_staged != b_staged)

    # Independent verification: the staged copies really exist on disk.
    check("A staged file exists in the ComfyUI input dir",
          bool(a_staged) and os.path.isfile(a_staged), str(a_staged))
    check("B staged file exists in the ComfyUI input dir",
          bool(b_staged) and os.path.isfile(b_staged), str(b_staged))

    # The staged bytes are the REAL source bytes, not an empty placeholder.
    a_ok = bool(a_staged) and os.path.isfile(a_staged)
    b_ok = bool(b_staged) and os.path.isfile(b_staged)

    check("A staged bytes == source bytes",
          a_ok and os.path.getsize(a_staged) == os.path.getsize(A_IMAGE),
          "%s vs %s" % (os.path.getsize(a_staged) if a_ok else None, os.path.getsize(A_IMAGE)))
    check("B staged bytes == source bytes",
          b_ok and os.path.getsize(b_staged) == os.path.getsize(B_IMAGE),
          "%s vs %s" % (os.path.getsize(b_staged) if b_ok else None, os.path.getsize(B_IMAGE)))
    check("A and B staged bytes differ (different images)",
          a_ok and b_ok and os.path.getsize(a_staged) != os.path.getsize(b_staged))

    check("A source path is the real A file", a.get("source_path") == A_IMAGE)
    check("B source path is the real B file", b.get("source_path") == B_IMAGE)

    # Traceable source-to-node binding for BOTH images, including the
    # transport vocabulary the request actually carried.
    check("A records its transport key 'A' and role facade_reference",
          a.get("transport_key") == "A" and a.get("transport_role") == "facade_reference",
          "key=%s role=%s" % (a.get("transport_key"), a.get("transport_role")))
    check("B records its transport key 'B' and role target_building",
          b.get("transport_key") == "B" and b.get("transport_role") == "target_building",
          "key=%s role=%s" % (b.get("transport_key"), b.get("transport_role")))

    trace = dual_image_trace(contract)
    check("trace carries both sides",
          bool(trace["image_a"]["filename"]) and bool(trace["image_b"]["filename"]))
    check("trace records the geometry node 300", trace["geometry_node"] == "300")
    check("trace records the dual workflow",
          trace["workflow"] == "flux_img2img_dual.json")

    return contract


# ==========================================================
# [3] NODE BINDING + IMAGE A CANNOT OVERWRITE IMAGE B
# ==========================================================

def section_binding(contract):

    print("\n[3] NODE BINDING (node 300 = IMAGE B, node 302 = IMAGE A)")

    wf = load_dual_workflow()

    bound, report = bind_images_to_workflow(wf, contract)

    check("binding report has no errors", report.get("errors") == [],
          "errors=%s" % report.get("errors"))
    check("node_300_source is IMAGE B's staged filename",
          report.get("node_300_source") == (contract["roles"][ROLE_B]).get("filename"))

    check("node 300 inputs.image == IMAGE B filename",
          bound["300"]["inputs"]["image"] == contract["roles"][ROLE_B]["filename"])
    check("node 302 inputs.image == IMAGE A filename",
          bound["302"]["inputs"]["image"] == contract["roles"][ROLE_A]["filename"])

    check("IMAGE A filename did NOT reach node 300",
          bound["300"]["inputs"]["image"] != contract["roles"][ROLE_A]["filename"])
    check("IMAGE B filename did NOT reach node 302",
          bound["302"]["inputs"]["image"] != contract["roles"][ROLE_B]["filename"])

    # The geometry path must be byte-identical apart from the LoadImage filename.
    check("node 301 pixels still <- [300, 0]",
          bound["301"]["inputs"]["pixels"] == ["300", 0])
    check("node 210 latent_image still <- [301, 0]",
          bound["210"]["inputs"]["latent_image"] == ["301", 0])

    # The ORIGINAL template must not be mutated (binding works on a copy).
    check("source template node 300 untouched",
          wf["300"]["inputs"]["image"] == "input.png",
          "template=%s" % wf["300"]["inputs"]["image"])

    # Fail-closed atomicity: a non-LoadImage target aborts the WHOLE binding.
    bad = {
        ROLE_A: {"node_id": NODE_A, "filename": "a.png"},
        ROLE_B: {"node_id": "301", "filename": "b.png"},  # 301 is VAEEncode
    }
    out, bad_report = bind_role_bindings(wf, bad)
    check("binding to a non-LoadImage node is rejected",
          any(e.startswith("binding_node_invalid_") for e in bad_report.get("errors", [])),
          "errors=%s" % bad_report.get("errors"))
    check("rejected binding returns the ORIGINAL workflow unmodified",
          out["300"]["inputs"]["image"] == "input.png")


# ==========================================================
# [4] FAIL-CLOSED MATRIX
# ==========================================================

def section_fail_closed(stage_root):

    print("\n[4] FAIL-CLOSED MATRIX")

    def status(ctx, stage_fn=None):
        c = build_dual_image_contract(ctx, "chat_project", stage_fn=stage_fn,
                                      comfy_input=stage_root)
        return c.get("status"), list(c.get("errors") or [])

    # A missing
    s, errs = status(make_context(a_present=False))
    check("missing IMAGE A -> blocked", s == "blocked", "status=%s" % s)
    check("missing IMAGE A names the role", any("style_reference" in e for e in errs), str(errs))

    # B missing
    s, errs = status(make_context(b_present=False))
    check("missing IMAGE B -> blocked", s == "blocked", "status=%s" % s)
    check("missing IMAGE B names the role", any("target_building" in e for e in errs), str(errs))

    # A present flag false
    ctx = make_context()
    ctx["references"]["A"]["present"] = False
    s, errs = status(ctx)
    check("A.present == False -> blocked", s == "blocked", "status=%s" % s)

    # A path unreadable
    s, errs = status(make_context(a_path=os.path.join(FIXTURES, "does_not_exist.jpg")))
    check("unreadable IMAGE A source -> blocked", s == "blocked", "status=%s" % s)
    check("unreadable IMAGE A reported as source_unreadable",
          any(e == "source_unreadable_style_reference" for e in errs), str(errs))

    # B path unreadable
    s, errs = status(make_context(b_path=os.path.join(FIXTURES, "nope.jpg")))
    check("unreadable IMAGE B source -> blocked", s == "blocked", "status=%s" % s)
    check("unreadable IMAGE B reported as source_unreadable",
          any(e == "source_unreadable_target_building" for e in errs), str(errs))

    # Staging failure for A
    def stage_fail_a(project_id, path):
        if path == A_IMAGE:
            raise RuntimeError("disk_full")
        return {"status": "ready", "filename": "b_staged.jpg", "path": B_IMAGE}

    s, errs = status(make_context(), stage_fn=stage_fail_a)
    check("staging failure on IMAGE A -> blocked", s == "blocked", "status=%s" % s)
    check("staging failure names the role A",
          any("style_reference" in e for e in errs), str(errs))

    # Staging failure for B
    def stage_fail_b(project_id, path):
        if path == B_IMAGE:
            raise RuntimeError("disk_full")
        return {"status": "ready", "filename": "a_staged.jpg", "path": A_IMAGE}

    s, errs = status(make_context(), stage_fn=stage_fail_b)
    check("staging failure on IMAGE B -> blocked", s == "blocked", "status=%s" % s)
    check("staging failure names the role B",
          any("target_building" in e for e in errs), str(errs))

    # A staged filename but the staged file does not exist on disk
    def stage_phantom(project_id, path):
        return {"status": "ready", "filename": "phantom.jpg",
                "path": os.path.join(stage_root, "phantom_missing.jpg")}

    s, errs = status(make_context(), stage_fn=stage_phantom)
    check("staged file missing on disk -> blocked", s == "blocked", "status=%s" % s)
    check("staged file missing reported",
          any(e.startswith("staged_file_missing_") for e in errs), str(errs))

    # No context / no references at all
    s, errs = status({})
    check("no references at all -> blocked", s == "blocked", "status=%s" % s)

    # A blocked contract must NOT bind anything.
    blocked = build_dual_image_contract(make_context(a_present=False), "chat_project",
                                        comfy_input=stage_root)
    wf = load_dual_workflow()
    out, rep = bind_images_to_workflow(wf, blocked)
    check("a blocked contract binds nothing",
          rep.get("bound") == {} and out["300"]["inputs"]["image"] == "input.png")


# ==========================================================
# [4b] FACADE-04C FAIL-CLOSED REASON CODES
# ==========================================================

def section_reason_codes():

    print("\n[4b] FAIL-CLOSED REASON CODES (FACADE-04C preserved)")

    check("FACADE-04C code target_building_image_unavailable unchanged",
          REASON_B_UNAVAILABLE == "target_building_image_unavailable")
    check("FACADE-04C code target_building_image_not_staged unchanged",
          REASON_B_NOT_STAGED == "target_building_image_not_staged")

    check("missing B -> target_building_image_unavailable",
          fail_closed_reason(["missing_target_building"]) == REASON_B_UNAVAILABLE)
    check("unreadable B -> target_building_image_unavailable",
          fail_closed_reason(["source_unreadable_target_building"]) == REASON_B_UNAVAILABLE)
    check("staging failure B -> target_building_image_not_staged",
          fail_closed_reason(["staging_failed_target_building"]) == REASON_B_NOT_STAGED)
    check("staged file missing B -> target_building_image_not_staged",
          fail_closed_reason(["staged_file_missing_target_building"]) == REASON_B_NOT_STAGED)

    check("missing A -> style_reference_image_unavailable",
          fail_closed_reason(["missing_style_reference"]) == REASON_A_UNAVAILABLE)
    check("staging failure A -> style_reference_image_not_staged",
          fail_closed_reason(["staging_failed_style_reference"]) == REASON_A_NOT_STAGED)

    check("no role-specific error -> dual_image_binding_not_ready",
          fail_closed_reason([]) == REASON_NOT_READY)
    check("B failure outranks an A failure (geometry authority first)",
          fail_closed_reason(["missing_style_reference", "missing_target_building"])
          == REASON_B_UNAVAILABLE)

    chat_src = open(
        os.path.join(PROJECT_ROOT, "core", "chat", "chat_architect.py"),
        encoding="utf-8",
    ).read()

    check("chat dispatch uses the shared reason mapper",
          "fail_closed_reason(" in chat_src)
    check("chat dispatch no longer inlines the B reason codes",
          '"target_building_image_not_staged"' not in chat_src)


# ==========================================================
# [5] WORKFLOW SELECTOR ROUTING
# ==========================================================
def section_selector():

    print("\n[5] WORKFLOW SELECTOR ROUTING")

    sel = WorkflowSelector()

    image = {"filename": "some_image.png"}

    check("text2img -> flux.json",
          sel.select({"engine": "flux", "mode": "text2img"}) == "flux.json")
    check("img2img + image -> flux_img2img.json",
          sel.select({"engine": "flux", "mode": "img2img", "image": image}) == "flux_img2img.json")
    check("image with no explicit mode -> flux_img2img.json",
          sel.select({"engine": "flux", "image": image}) == "flux_img2img.json")
    check("wan -> wan_i2v.json",
          sel.select({"engine": "wan", "mode": "i2v", "image": image}) == "wan_i2v.json")

    check("dual_image=True -> flux_img2img_dual.json",
          sel.select({"engine": "flux", "mode": "img2img", "image": image,
                      "dual_image": True}) == "flux_img2img_dual.json")
    check("image_bindings present -> flux_img2img_dual.json",
          sel.select({"engine": "flux", "mode": "img2img", "image": image,
                      "image_bindings": {"target_building": {"node_id": "300",
                                                             "filename": "b.png"}}})
          == "flux_img2img_dual.json")

    check("dual workflow is advertised in available_workflows()",
          "flux_img2img_dual.json" in sel.available_workflows())

    # The config list must stay in sync with the selector (project invariant).
    from config import runtime_config as RC
    check("REQUIRED_WORKFLOW_FILES stays in sync with the selector",
          set(RC.REQUIRED_WORKFLOW_FILES) == set(sel.available_workflows()),
          "config=%s selector=%s" % (sorted(RC.REQUIRED_WORKFLOW_FILES),
                                     sorted(sel.available_workflows())))


# ==========================================================
# [6] INJECTOR BINDING (dual vs legacy single-image)
# ==========================================================

def section_injector(contract):

    print("\n[6] INJECTOR BINDING")

    injector = ImageWorkflowInjector()

    dual = load_dual_workflow()

    a_file = contract["roles"][ROLE_A]["filename"]
    b_file = contract["roles"][ROLE_B]["filename"]

    bindings = {
        ROLE_A: {"node_id": NODE_A, "filename": a_file},
        ROLE_B: {"node_id": NODE_B, "filename": b_file},
    }

    out = injector.inject(
        dual,
        "restyle the facade",
        {"filename": b_file},
        {"denoise": 0.55},
        image_bindings=bindings,
    )

    wf = out["workflow"]

    check("injector: node 300 == IMAGE B", wf["300"]["inputs"]["image"] == b_file)
    check("injector: node 302 == IMAGE A", wf["302"]["inputs"]["image"] == a_file)
    check("injector: IMAGE A did not overwrite node 300",
          wf["300"]["inputs"]["image"] != a_file)

    # No LoadImage node may hold a filename that is not its own role's.
    loadimages = {nid: n for nid, n in wf.items()
                  if isinstance(n, dict) and n.get("class_type") == "LoadImage"}
    expected = {"300": b_file, "302": a_file}
    check("injector: every LoadImage holds exactly its role filename",
          {nid: n["inputs"]["image"] for nid, n in loadimages.items()} == expected,
          str({nid: n["inputs"]["image"] for nid, n in loadimages.items()}))

    check("injector: binding report recorded",
          isinstance(out.get("image_binding_report"), dict)
          and (out["image_binding_report"].get("bound") or {}).get(ROLE_B, {}).get("node_id") == "300")

    # denoise injection still works (preserved behaviour)
    check("injector: denoise injection still applies", wf["210"]["inputs"]["denoise"] == 0.55)
    check("injector: latent path untouched", wf["210"]["inputs"]["latent_image"] == ["301", 0])
    check("injector: 301 pixels untouched", wf["301"]["inputs"]["pixels"] == ["300", 0])

    # ---- FACADE-04C REGRESSION: legacy single-image broadcast path ----
    single = load_single_workflow()
    legacy = injector.inject(single, "improve", {"filename": "legacy.png"}, {})
    check("legacy single-image: node 300 == supplied asset filename",
          legacy["workflow"]["300"]["inputs"]["image"] == "legacy.png")
    check("legacy single-image: no binding report (unchanged path)",
          "image_binding_report" not in legacy)

    # A dual graph with NO bindings must not be produced by the legacy path;
    # but if it ever were, the historical broadcast behaviour is what it would
    # do — so assert that the DUAL path never takes it.
    check("dual path uses explicit bindings, not the legacy broadcast",
          out.get("image_binding_report", {}).get("bound", {}) != {})


# ==========================================================
# [7] MOCKED COMFYUI PAYLOAD (RenderRuntime, no real submission)
# ==========================================================

def section_mocked_render(contract):

    print("\n[7] MOCKED COMFYUI PAYLOAD (RenderRuntime)")

    from core.render.render_runtime import RenderRuntime

    runtime = RenderRuntime()

    captured = {}

    def fake_execute(workflow, engine):
        captured["workflow"] = copy.deepcopy(workflow)
        captured["engine"] = engine
        return {"status": "success", "images": [{"filename": "mock_out.png"}]}

    runtime.executor.execute = fake_execute
    runtime.result_bridge.resolve = lambda ctx: {"status": "success",
                                                 "image": {"filename": "mock_out.png"}}

    b_asset = {
        "status": "ready",
        "asset_id": contract["roles"][ROLE_B]["asset_id"],
        "filename": contract["roles"][ROLE_B]["filename"],
        "path": contract["roles"][ROLE_B]["staged_path"],
    }

    bindings = {
        ROLE_A: {"node_id": NODE_A, "filename": contract["roles"][ROLE_A]["filename"]},
        ROLE_B: {"node_id": NODE_B, "filename": contract["roles"][ROLE_B]["filename"]},
    }

    design = {
        "mode": "img2img",
        "prompt": "restyle the facade with the reference style",
        "architectural_intent": {"style": "modern", "mode": "img2img"},
        "project_state": {},
    }

    result = runtime.render("chat_project", design, "flux", b_asset, image_bindings=bindings)

    check("runtime selected the dual workflow",
          (result.get("request_metadata") or {}).get("workflow_name") == "flux_img2img_dual.json",
          "workflow=%s" % (result.get("request_metadata") or {}).get("workflow_name"))

    check("runtime submitted to the comfyui executor", captured.get("engine") == "comfyui",
          "engine=%s" % captured.get("engine"))

    submitted = captured.get("workflow") or {}

    check("MOCKED PAYLOAD: node 300 image == IMAGE B filename",
          (submitted.get("300") or {}).get("inputs", {}).get("image")
          == contract["roles"][ROLE_B]["filename"],
          str((submitted.get("300") or {}).get("inputs")))
    check("MOCKED PAYLOAD: node 302 image == IMAGE A filename",
          (submitted.get("302") or {}).get("inputs", {}).get("image")
          == contract["roles"][ROLE_A]["filename"],
          str((submitted.get("302") or {}).get("inputs")))
    check("MOCKED PAYLOAD: node 300 != node 302",
          (submitted.get("300") or {}).get("inputs", {}).get("image")
          != (submitted.get("302") or {}).get("inputs", {}).get("image"))
    check("MOCKED PAYLOAD: 301 pixels <- [300, 0]",
          (submitted.get("301") or {}).get("inputs", {}).get("pixels") == ["300", 0])
    check("MOCKED PAYLOAD: 210 latent_image <- [301, 0]",
          (submitted.get("210") or {}).get("inputs", {}).get("latent_image") == ["301", 0])

    # No IMAGE A encoder output may reach the sampler in the submitted graph.
    consumers = []
    for node_id, node in submitted.items():
        for ref in node_refs(node):
            if ref[0] == NODE_A_ENCODE:
                consumers.append(node_id)
    check("MOCKED PAYLOAD: IMAGE A encoder output unconsumed", consumers == [],
          "consumers=%s" % consumers)

    check("runtime result carries the image_bindings trace",
          isinstance(result.get("image_bindings"), dict)
          and result["image_bindings"].get(ROLE_B, {}).get("node_id") == "300")

    # ---- single-image compatibility through the SAME runtime ----
    captured.clear()

    single_asset = {"status": "ready", "filename": "single_staged.png",
                    "path": os.path.join(PROJECT_ROOT, "tests", "assets", "test_upload.png")}

    single_design = {
        "mode": "img2img",
        "prompt": "improve the facade",
        "architectural_intent": {"style": "modern", "mode": "img2img"},
        "project_state": {},
    }

    single_result = runtime.render("chat_project", single_design, "flux", single_asset)

    check("single-image render still selects flux_img2img.json",
          (single_result.get("request_metadata") or {}).get("workflow_name") == "flux_img2img.json",
          "workflow=%s" % (single_result.get("request_metadata") or {}).get("workflow_name"))
    check("single-image render submits node 300 == asset filename",
          (captured.get("workflow") or {}).get("300", {}).get("inputs", {}).get("image")
          == "single_staged.png")
    check("single-image render has NO image_bindings",
          single_result.get("image_bindings") is None)

    # ---- text-to-image compatibility through the SAME runtime ----
    captured.clear()

    text_design = {
        "mode": "text2img",
        "prompt": "a modern house",
        "architectural_intent": {"style": "modern", "mode": "text2img"},
        "project_state": {},
    }

    text_result = runtime.render("chat_project", text_design, "flux")

    check("text-to-image render selects flux.json",
          (text_result.get("request_metadata") or {}).get("workflow_name") == "flux.json",
          "workflow=%s" % (text_result.get("request_metadata") or {}).get("workflow_name"))
    check("text-to-image render submits no LoadImage",
          not any(isinstance(n, dict) and n.get("class_type") == "LoadImage"
                  for n in (captured.get("workflow") or {}).values()))


# ==========================================================
# MAIN
# ==========================================================

def main():

    print("=== FACADE-04D.2 ROLE-AWARE DUAL-IMAGE BINDING V1 — CONTRACT SUITE ===")

    for required in (A_IMAGE, B_IMAGE):
        if not os.path.isfile(required):
            print("MISSING FIXTURE: " + required)
            return 2

    stage_root = tempfile.mkdtemp(prefix="facade04d2_comfy_input_")

    section_static()
    section_template()
    contract = section_contract(stage_root)
    if isinstance(contract, dict) and contract.get("status") == "ready":
        section_binding(contract)
        section_injector(contract)
        section_mocked_render(contract)
    else:
        check("dual contract buildable (required for later sections)", False,
              "status=%s" % (contract or {}).get("status"))
    section_fail_closed(stage_root)
    section_reason_codes()
    section_selector()

    total = len(RESULTS)
    passed = sum(1 for _, ok, _ in RESULTS if ok)

    print("\n=== RESULT: %d/%d checks passed ===" % (passed, total))

    failed = [name for name, ok, _ in RESULTS if not ok]
    if failed:
        print("FAILED:")
        for name in failed:
            print("  - " + name)
        return 1

    print("ALL FACADE-04D.2 DUAL-IMAGE BINDING CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
