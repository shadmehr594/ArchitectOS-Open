# ==========================================================
# ArchitectOS Image Asset Bridge v3.1
# Asset Registration Layer for ComfyUI
#
# IMAGE_TO_IMAGE_05 — TEST-RENDER PREVIEW SOURCE (CODE ENFORCED)
#
#   The ORIGINAL source stays the authoritative asset. When a
#   DRAFT/PREVIEW render profile is active, a TEMPORARY downscaled
#   working copy is created beside the ComfyUI input copy and that
#   copy is what LoadImage loads. The original is never modified.
#
#   With no profile active this class behaves exactly as v3 did.
# ==========================================================


import os
import shutil
import time
import uuid


from config import runtime_config as RC

from core.render.image_preview_v1 import (
    PREVIEW_NOT_REQUIRED,
    make_preview,
    is_preview_usable,
)

from core.render.render_draft_v1 import (
    resolve_profile as resolve_render_profile,
)


CONTRACT = "ImageAssetBridgeV3"
VERSION = "3.1"



class ImageAssetBridge:


    VERSION = "3.1"



    def __init__(
        self,
        comfy_input=None
    ):


        # TEXT_TO_IMAGE_COMFY_03 / IMAGE_TO_IMAGE_05
        # Single runtime config source: never hardcode the ComfyUI root.
        self.comfy_input = (
            comfy_input
            or RC.COMFYUI_INPUT_DIR
        )


        os.makedirs(
            self.comfy_input,
            exist_ok=True
        )


        print(
            "🖼️ IMAGE ASSET BRIDGE v3.1 ONLINE"
        )



    # ======================================================
    # IMAGE DIMENSIONS  (header read only, never decodes)
    # ======================================================

    @staticmethod
    def _png_dimensions(path):

        try:

            with open(path, "rb") as handle:

                head = handle.read(24)

            if head[:8] != b"\x89PNG\r\n\x1a\n":

                return None

            return [
                int.from_bytes(head[16:20], "big"),
                int.from_bytes(head[20:24], "big"),
            ]

        except Exception:

            return None



    # ======================================================
    # REGISTER IMAGE
    # ======================================================


    def register(
        self,
        project_id,
        image_path,
        preview=None
    ):


        if not image_path:

            return {

                "status":
                    "error",

                "message":
                    "empty_path"

            }



        if not os.path.exists(
            image_path
        ):

            return {

                "status":
                    "error",

                "message":
                    "image_not_found",

                "path":
                    image_path

            }



        ext = os.path.splitext(
            image_path
        )[1]


        filename = (
            "architectos_"
            + str(uuid.uuid4())[:8]
            + ext
        )



        target = os.path.join(
            self.comfy_input,
            filename
        )



        shutil.copy2(
            image_path,
            target
        )


        # --------------------------------------------------
        # IMAGE_TO_IMAGE_05 — TEST-RENDER PREVIEW SOURCE
        #
        # The original is copied above and stays authoritative in
        # `path`. When a test profile is active we additionally create
        # a temporary downscaled working copy and point `filename`
        # (what ComfyUI's LoadImage loads) at that copy instead.
        # --------------------------------------------------

        # I2I_JPEG_PREVIEW_SAFE_STAGING_V1 — the Chat route forwards the
        # resolved profile NAME ("PREVIEW"), not the contract dict. Treat a
        # name as an explicit request; otherwise the working-copy mechanism
        # never activates from the product UI.
        if isinstance(preview, dict):

            profile = preview

        elif isinstance(preview, str) and preview.strip():

            profile = resolve_render_profile(explicit=preview.strip())

        else:

            profile = resolve_render_profile()


        original_dimensions = self._png_dimensions(image_path)


        preview_record = {

            "contract": "ImagePreviewV1",
            "version": "1.0",

            "preview_available": False,
            "preview_reason": "profile_inactive",

            "original_source_path": image_path,
            "working_preview_path": None,

            "original_dimensions": original_dimensions,
            "working_dimensions": original_dimensions,

            "downscaled": False,
            "upscaled": False,

            "aspect_ratio_preserved": None,
            "original_preserved": True,
        }


        if (
            isinstance(profile, dict)
            and profile.get("active")
            and profile.get("preview_source")
        ):

            preview_record = make_preview(

                image_path,

                self.comfy_input,

                long_edge=profile.get("long_edge"),

                # I2I_JPEG_PREVIEW_SAFE_STAGING_V1 — make_preview always
                # writes PNG, so the working copy must carry a .png
                # extension even when the source is a .jpg.
                filename=(
                    "architectos_preview_"
                    + str(uuid.uuid4())[:8]
                    + ".png"
                ),
            )


            if is_preview_usable(preview_record):

                # LoadImage loads the downscaled working copy.
                filename = os.path.basename(
                    preview_record["working_preview_path"]
                )

                print(
                    "🪶 PREVIEW SOURCE ACTIVE:",
                    preview_record.get("original_dimensions"),
                    "->",
                    preview_record.get("working_dimensions"),
                    "| profile",
                    profile.get("name")
                )

            else:

                reason = preview_record.get("preview_reason")

                if reason not in PREVIEW_NOT_REQUIRED:

                    # I2I_JPEG_PREVIEW_SAFE_STAGING_V1 — a working copy was
                    # explicitly requested and failed. Never silently send
                    # the full-resolution original to ComfyUI.
                    print(
                        "⛔ PREVIEW SOURCE REQUIRED BUT UNAVAILABLE:",
                        reason
                    )

                    return {

                        "status": "error",

                        "message": "preview_source_unavailable",

                        "preview_reason": reason,

                        "project_id": project_id,

                        "original_source_path": image_path,

                        "preview": preview_record,

                        "filename": None,
                        "path": None,
                    }

                print(
                    "⚠️ PREVIEW NOT REQUIRED, USING ORIGINAL:",
                    reason
                )



        return {

            "status":
                "ready",

            "asset_id":
                "asset_" + str(uuid.uuid4())[:8],

            "project_id":
                project_id,

            # What ComfyUI's LoadImage loads.
            "filename":
                filename,

            # Authoritative asset (the original copy), never the preview.
            "path":
                target,

            "created_at":
                time.time(),

            # ----------------------------------------------
            # IMAGE_TO_IMAGE_05 — test-render provenance
            # ----------------------------------------------

            "original_source_path":
                preview_record.get("original_source_path"),

            "working_preview_path":
                preview_record.get("working_preview_path"),

            "original_dimensions":
                preview_record.get("original_dimensions"),

            "working_dimensions":
                preview_record.get("working_dimensions"),

            "test_profile": {

                "contract": profile.get("contract"),
                "name": profile.get("name"),
                "active": profile.get("active"),
                "steps": profile.get("steps"),
                "long_edge": profile.get("long_edge"),
                "preview_source": profile.get("preview_source"),
                "production_resolution": profile.get("production_resolution"),
                "test_profile": profile.get("test_profile"),
                "source": profile.get("source"),
            },

            "preview":
                preview_record,

        }



    # ======================================================
    # PREPARE ASSET
    # ======================================================


    def prepare_asset(
        self,
        asset
    ):


        if not asset:

            return None



        if isinstance(
            asset,
            str
        ):

            return {

                "filename":
                    asset,

                "status":
                    "ready"

            }



        filename = asset.get(
            "filename"
        )


        path = asset.get(
            "path"
        )



        return {


            "asset_id":

                asset.get(
                    "asset_id"
                ),



            "filename":

                filename,



            "path":

                path,



            "status":

                asset.get(
                    "status",
                    "ready"
                ),



            "type":

                "source_image"

        }