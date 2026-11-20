# ==========================================================
# PROJECT_WORKSPACE_UI_06 — OFFLINE PERSISTENCE PROBE
#
# Verifies, WITHOUT any render and WITHOUT starting a server:
#   create project -> add chat + upload + render + derived lineage
#   -> "restart" (drop in-memory state) -> reopen -> verify restore
#
# Usage:
#   python tools/probe_project_persistence_06.py
# ==========================================================


import os
import shutil
import sys


ROOT = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

if ROOT not in sys.path:

    sys.path.insert(0, ROOT)


from config import runtime_config as RC


def main():

    # Isolate the probe from real project data.
    probe_root = os.path.join(ROOT, ".pytest_tmp", "probe06_projects")

    if os.path.isdir(probe_root):

        shutil.rmtree(probe_root, ignore_errors=True)

    RC.PROJECTS_ROOT = probe_root
    RC.PROJECT_TRASH_ROOT = os.path.join(
        ROOT, ".pytest_tmp", "probe06_trash"
    )

    from core.project.project_workspace_v1 import ProjectWorkspace

    workspace = ProjectWorkspace(
        projects_root=RC.PROJECTS_ROOT,
        trash_root=RC.PROJECT_TRASH_ROOT,
    )

    # re-point the singletons at the probe root
    import core.project.project_workspace_v1 as PW
    PW.project_workspace = workspace

    import core.project.project_registry_bridge_v1 as PRB
    PRB.project_workspace = workspace

    import core.project.conversation_store_v1 as CS
    CS.project_workspace = workspace

    import core.project.project_session_v1 as PS
    PS.project_workspace = workspace

    from core.vision.image_registry_v1 import image_registry
    from core.chat.session_registry_v1 import session_registry
    from core.project.project_registry_bridge_v1 import (
        project_registry_bridge,
    )
    from core.project.project_session_v1 import project_session

    SOURCE = "C:/ComfyUI-Zluda/output/architectos_v11_00235_.png"
    RENDER = "C:/ComfyUI-Zluda/output/architectos_img2img_edit_00083_.png"
    DERIVED = "C:/ComfyUI-Zluda/output/architectos_img2img_edit_00084_.png"

    print("=" * 70)
    print("  STEP 1 — CREATE PROJECT")
    print("=" * 70)

    project = workspace.create("Persistence Test")

    project_id = project["project_id"]

    print("  project_id:", project_id)
    print("  name      :", project["project_name"])

    project_session.open(project_id)

    session_id = project_id

    print("=" * 70)
    print("  STEP 2 — ADD CHAT + UPLOAD + RENDER + DERIVED LINEAGE")
    print("=" * 70)

    conversation_store_state = session_registry.resolve(
        session_id
    )["conversation_state"]

    conversation_store_state.add_message("user", "یه ویلای مدرن میخوام")
    conversation_store_state.add_message("assistant", "حتماً، شروع میکنم.")

    uploaded = image_registry.register(
        session_id, path=SOURCE, source_type="uploaded", label="source.png"
    )

    render = image_registry.register(
        session_id, path=RENDER, source_type="text_to_image",
        label="night render",
    )

    derived = image_registry.register(
        session_id, path=DERIVED, source_type="image_to_image",
        parent_image_id=render["image_id"], label="stone edit",
    )

    print("  upload  ordinal:", uploaded["ordinal"])
    print("  render  ordinal:", render["ordinal"])
    print("  derived ordinal:", derived["ordinal"],
          "| parent", derived["parent_image_id"])

    save = project_session.autosave(project_id, reason="render_complete")

    print("  save state:", save["state"], "| count", save["save_count"])

    gallery = project_registry_bridge.gallery(project_id)

    print("  assets managed:", gallery["asset_count"])

    for asset in gallery["assets"]:

        print(
            "   ",
            asset["ordinal"],
            asset["source_type"],
            "|",
            asset["generated_filename"],
            "| active",
            asset["is_active"],
        )

    print("=" * 70)
    print("  STEP 3 — SIMULATED RESTART (drop ALL in-memory state)")
    print("=" * 70)

    project_session.close()

    image_registry._sessions.clear()

    session_registry._sessions.clear()

    print("  in-memory registry sessions:", image_registry.session_count())
    print("  in-memory session sessions :", session_registry.session_count())

    print("=" * 70)
    print("  STEP 4 — REOPEN PROJECT")
    print("=" * 70)

    reopened = project_session.open(project_id)

    print("  reopened:", reopened["project_name"])

    summary = project_session.recovery_summary(project_id)

    print("  messages restored :", summary["message_count"])
    print("  assets restored   :", summary["asset_count"])
    print("  ordinals restored :", summary["ordinals"])
    print("  active asset      :", summary["active_asset_id"])
    print("  last render       :", summary["last_render_asset_id"])
    print("  last derived      :", summary["last_derived_asset_id"])
    print("  lineage           :", summary["lineage"])

    active = image_registry.active(session_id)

    print("  registry.active() :", active["ordinal"] if active else None)

    by_ordinal = image_registry.by_ordinal(session_id, 2)

    print("  by_ordinal(2)     :", by_ordinal["label"] if by_ordinal else None)

    last_render = image_registry.last_render(session_id)

    print("  last_render()     :",
          last_render["label"] if last_render else None)

    print()
    print("=" * 70)
    print("  RESULT")
    print("=" * 70)

    ok = (
        summary["message_count"] == 2
        and summary["asset_count"] == 3
        and summary["ordinals"] == [1, 2, 3]
        and summary["last_render_asset_id"] == derived["image_id"]
        and by_ordinal is not None
    )

    print("  PERSISTENCE:", "PASS" if ok else "FAIL")

    return 0 if ok else 2


if __name__ == "__main__":

    sys.exit(main())
