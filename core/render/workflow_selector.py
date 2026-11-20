# ==========================================================
# ArchitectOS Workflow Selector v3
# Render Intent -> Workflow Routing
# ==========================================================


# ==========================================================
# V22_HIGHRISE_NIGHT_ROUTING_V1 — EXPLICIT MODE OPT-IN
#
# `core/render/experimental/architectos_v22_highrise_night_v1.py`
# owns two render modes. Neither mode is a workflow FILE: each one
# configures a BASE graph through
# `build_mode_specific_stage2_workflow()`, which is the single
# owner of the ControlNet branch, the denoise band and the
# strength/end_percent pair. The selector's whole job for a v22
# request is therefore to name that base graph — and to refuse a
# combination it cannot honour.
#
# Fail closed. An unknown mode, a non-flux engine, a competing
# opt-in, or a mode/source mismatch returns None. None is the
# existing "no workflow" contract and RenderRuntime already turns
# it into `status: unknown_workflow`. It is NEVER replaced by
# `flux.json`, because a mode that was asked for and not applied
# is a different render, not a weaker one.
#
# MODE_1 is text-to-image, so an image makes it an edit.
# MODE_3 is a source-latent relight, so NO image leaves it with
# nothing to relight and it must not degrade into a fresh
# generation.
# ==========================================================

V22_MODE_TXT2IMG_EXACT_FLOORS = "MODE_1_TXT2IMG_EXACT_FLOORS"

V22_MODE_DAY_TO_NIGHT_RELIGHT = "MODE_3_DAY_TO_NIGHT_RELIGHT"


#: mode -> the base graph `build_mode_specific_stage2_workflow()` expects.
V22_MODE_BASE_WORKFLOW = {

    V22_MODE_TXT2IMG_EXACT_FLOORS: "flux.json",

    V22_MODE_DAY_TO_NIGHT_RELIGHT: "flux_img2img.json",

}


class WorkflowSelector:


    VERSION = "3.0"



    def __init__(self):

        print(
            "🔀 WORKFLOW SELECTOR v3 ONLINE"
        )



    # ======================================================
    # SELECT WORKFLOW
    # ======================================================


    def select(
        self,
        request
    ):


        if not request:

            return None



        # --------------------------------------
        # Normalize input
        # --------------------------------------

        engine = request.get(
            "engine",
            "flux"
        )


        mode = request.get(
            "mode"
        )


        image = request.get(
            "image"
        )



        # --------------------------------------
        # FACADE-04D.2 — DUAL-IMAGE (ROLE-AWARE)
        #
        # An EXPLICIT dual-image request (IMAGE A style reference +
        # IMAGE B geometry authority) routes to its own dedicated graph.
        # The single-valued `image` key must NEVER select it on its own,
        # so every existing caller keeps `flux_img2img.json` unchanged.
        # --------------------------------------

        dual_image = bool(
            request.get("dual_image")
        ) or bool(
            request.get("image_bindings")
        )


        # --------------------------------------
        # FACADE-04D.3B-2 — CONDITIONED DUAL-IMAGE (EXPLICIT OPT-IN)
        #
        # Real USO style + ControlNet geometry conditioning is NEVER chosen
        # implicitly. A dual-image request keeps using the accepted
        # FACADE-04D.2 graph unless `conditioned` is explicitly set.
        # --------------------------------------

        conditioned = bool(
            request.get("conditioned")
        )



        # --------------------------------------
        # KNOWLEDGE_RECOVERY_01 — KONTEXT INSTRUCTION EDIT
        #
        # FLUX.1 Kontext dev is the only installed instruction-edit
        # engine, and its graph is GPU-verified. It is NEVER chosen
        # implicitly: the caller must opt in with `kontext_edit`, so
        # every existing caller keeps its current workflow unchanged.
        # --------------------------------------

        kontext_edit = bool(
            request.get("kontext_edit")
        )

        # PRECISE_EDIT_UI_V1 — a supplied selection mask is NEVER silently
        # ignored. It used to be dropped here unless the caller also set
        # `kontext_edit`, so a request that carried a mask still ran the
        # whole-image graph and the localisation was lost without a word.
        # A mask only ever means "edit inside this region", and the Kontext
        # graph is the route that honours it.
        if request.get("mask"):

            kontext_edit = True

        # --------------------------------------
        # EXISTING_VISUAL_KNOWLEDGE_USO_V1 — USO REFERENCE-GUIDED T2I
        #
        # A reference image that guides a NEW design is neither an edit nor an
        # init image. It is NEVER chosen implicitly: the caller must opt in with
        # `uso_reference`, so every existing caller keeps its current workflow
        # unchanged (including the `image` -> img2img fallback below, which
        # would otherwise capture a reference asset and treat it as a source).
        # --------------------------------------

        uso_reference = bool(
            request.get("uso_reference")
        )


        # --------------------------------------
        # V22_HIGHRISE_NIGHT_ROUTING_V1
        #
        # Checked AFTER every other opt-in is resolved, so a competing
        # opt-in is visible here and can be refused rather than
        # silently resolved by precedence. Checked BEFORE the `image`
        # fallback below, so a MODE_1 request can never be captured by
        # the img2img fallback just because the session has an image.
        # --------------------------------------

        v22_mode = request.get(
            "v22_mode"
        )

        if v22_mode:

            if v22_mode not in V22_MODE_BASE_WORKFLOW:

                return None

            if engine != "flux":

                return None

            if uso_reference or kontext_edit or dual_image or conditioned:

                return None

            if (
                v22_mode == V22_MODE_TXT2IMG_EXACT_FLOORS
                and image
            ):

                return None

            if (
                v22_mode == V22_MODE_DAY_TO_NIGHT_RELIGHT
                and not image
            ):

                return None

            return V22_MODE_BASE_WORKFLOW[v22_mode]


        # --------------------------------------
        # FLUX
        # --------------------------------------

        if engine == "flux":


            # EXISTING_VISUAL_KNOWLEDGE_USO_V1 — explicit reference-guided
            # generation. Checked first so a reference asset can never be
            # mistaken for an img2img source by the `image` fallback below.
            # Contradictory opt-ins are refused by the runtime gate, not
            # silently resolved here.
            if uso_reference:

                return "flux_uso_reference.json"


            if kontext_edit:

                return "flux_kontext_edit.json"


            if dual_image and conditioned:

                return "flux_img2img_dual_conditioned.json"


            if dual_image:

                return "flux_img2img_dual.json"


            # explicit edit mode

            if mode in [
                "edit",
                "img2img",
                "image_edit"
            ]:

                return "flux_img2img.json"



            # image exists => edit

            if image:

                return "flux_img2img.json"



            # default generation

            return "flux.json"



        # --------------------------------------
        # WAN VIDEO
        # --------------------------------------

        if engine == "wan":


            return "wan_i2v.json"



        return None



    # ======================================================
    # HELPERS
    # ======================================================


    def available_workflows(
        self
    ):

        return [

            "flux.json",

            "flux_img2img.json",

            # KNOWLEDGE_RECOVERY_01 — GPU-verified Kontext instruction
            # edit graph (explicit opt-in via request["kontext_edit"]).
            "flux_kontext_edit.json",

            # FACADE-04D.2 — role-aware dual-image img2img graph.
            "flux_img2img_dual.json",

            # FACADE-04D.3B-2 — conditioned dual-image graph (explicit opt-in).
            "flux_img2img_dual_conditioned.json",

            # EXISTING_VISUAL_KNOWLEDGE_USO_V1 — USO reference-conditioned
            # text-to-image graph (explicit opt-in via request["uso_reference"]).
            "flux_uso_reference.json",

            "wan_i2v.json"

        ]