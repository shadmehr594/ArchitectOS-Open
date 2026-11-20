# ==========================================================
# ArchitectOS Image Workflow Injector v3.2
# Dynamic Image + Existing Prompt Injection
#
# FIX:
# - Preserve ImageEditPromptBuilder output
# - No prompt rewriting
# - Stable img2img workflow injection
# - Preserve geometry edit pipeline
# - Detect positive / negative CLIP routing
# - Inject negative prompt correctly
# - Stable Flux img2img support
# ==========================================================


import copy



# ==========================================================
# FACADE-04D.3C-3 — CONDITIONING ROUTE CONTRACT
#
# A KSampler's `positive` / `negative` input may point at a conditioning
# PASSTHROUGH node instead of directly at a CLIPTextEncode. Prompt injection
# must follow ONLY these links — always along the SAME polarity — until it
# reaches the real CLIPTextEncode terminal.
#
# Anything outside this set is NOT traversed: an unsupported graph is refused
# (fail closed) rather than silently keeping the workflow's template prompt.
# ==========================================================

#: Conditioning nodes that forward their own `positive` / `negative` input.
CONDITIONING_PASSTHROUGH = (

    "ControlNetApplyAdvanced",

    "ControlNetApply",

    "WanImageToVideo",

    "WanFirstLastFrameToVideo",

    # KNOWLEDGE_RECOVERY_01 — the GPU-verified FLUX.1 Kontext
    # instruction-edit graph routes its conditioning through these three
    # nodes, and each of them forwards `conditioning` -> `conditioning`
    # WITHOUT changing polarity:
    #
    #   KSampler.positive -> FluxGuidance -> ReferenceLatent -> CLIPTextEncode
    #   KSampler.negative -> ConditioningZeroOut -> CLIPTextEncode
    #
    # Without them the route could not resolve, the injector failed
    # closed, and the Kontext graph was unreachable from the product.
    # Adding them lets the existing resolver reach the real terminals;
    # no traversal rule is weakened.
    "FluxGuidance",

    "ReferenceLatent",

    "ConditioningZeroOut",

)

#: The only node class a conditioning link may terminate at.
PROMPT_TERMINAL = "CLIPTextEncode"


#: KNOWLEDGE_RECOVERY_01 — the input key each passthrough class uses to
#: forward its conditioning.
#:
#: The four pre-existing classes expose SEPARATE `positive` / `negative`
#: inputs, so the key equals the polarity. The FLUX.1 Kontext nodes expose a
#: single `conditioning` input: they do not know about polarity, so the
#: polarity is carried by the LINK (which KSampler slot the walk started
#: from), never by the input name. Following them can therefore still not
#: swap positive and negative.
CONDITIONING_INPUT_KEY = {

    "FluxGuidance": "conditioning",

    "ReferenceLatent": "conditioning",

    "ConditioningZeroOut": "conditioning",

}

#: Defensive bound; a longer chain is treated as cyclic.
MAX_CONDITIONING_DEPTH = 16



class ImageWorkflowInjector:


    VERSION = "3.2"



    def __init__(self):

        print(
            "🖼️ IMAGE WORKFLOW INJECTOR v3.2 ONLINE"
        )



    # ======================================================
    # NORMALIZE PROMPT
    # ======================================================


    def normalize_prompt(
        self,
        prompt
    ):


        if prompt is None:

            return ""


        if isinstance(
            prompt,
            dict
        ):


            return str(
                prompt.get(
                    "description",
                    ""
                )
            )


        return str(
            prompt
        )



    # ======================================================
    # DEFAULT NEGATIVE
    # ======================================================


    def normalize_negative(
        self
    ):


        return (

            "low quality, blurry, distorted, "
            "bad geometry, wrong perspective, "
            "deformed building, unrealistic architecture, "
            "bad materials, bad lighting, "
            "changed structure, extra floors, "
            "missing windows, broken facade"

        )



    # ======================================================
    # FOLLOW ONE CONDITIONING LINK
    #
    # FACADE-04D.3C-3 — resolve a single KSampler conditioning link to its
    # CLIPTextEncode terminal, following ONLY supported conditioning
    # passthrough nodes and ONLY along the SAME polarity
    # (`positive` -> `positive`, `negative` -> `negative`). The polarity can
    # therefore never be swapped.
    #
    # Returns `(terminal_node_id, None)` on success, or
    # `(None, error_code)` for an unsupported / ambiguous / cyclic graph.
    # ======================================================

    def _follow_conditioning_link(
        self,
        workflow,
        link,
        polarity
    ):

        if not (
            isinstance(
                link,
                list
            )
            and len(link) > 0
        ):

            return None, "ambiguous_conditioning_link"

        node_id = str(
            link[0]
        )

        visited = []

        while True:

            if node_id in visited:

                return None, "cyclic_conditioning_graph"

            visited.append(
                node_id
            )

            if len(visited) > MAX_CONDITIONING_DEPTH:

                return None, "cyclic_conditioning_graph"

            node = workflow.get(
                node_id
            )

            if not isinstance(
                node,
                dict
            ):

                return None, "unsupported_conditioning_graph"

            class_type = node.get(
                "class_type"
            )

            if class_type == PROMPT_TERMINAL:

                return node_id, None

            if class_type not in CONDITIONING_PASSTHROUGH:

                return None, "unsupported_conditioning_graph"

            nxt = (
                node.get(
                    "inputs",
                    {}
                )
                or {}
            ).get(
                CONDITIONING_INPUT_KEY.get(
                    class_type,
                    polarity
                )
            )

            if not (
                isinstance(
                    nxt,
                    list
                )
                and len(nxt) > 0
            ):

                return None, "ambiguous_conditioning_link"

            node_id = str(
                nxt[0]
            )



    # ======================================================
    # RESOLVE CLIP ROUTES  (FACADE-04D.3C-3)
    #
    # Structured resolution with an explicit status. `resolved` is returned
    # ONLY when every KSampler's positive and negative conditioning links
    # resolve to a DISTINCT CLIPTextEncode terminal. Any unsupported /
    # ambiguous / cyclic graph, a polarity collision, or a missing terminal
    # returns `blocked` with stable error codes.
    # ======================================================

    def resolve_clip_routes(
        self,
        workflow
    ):

        report = {

            "status": "resolved",

            "positive": set(),

            "negative": set(),

            "errors": [],

            "traversal": [],

        }

        if not isinstance(
            workflow,
            dict
        ) or not workflow:

            report["status"] = "blocked"

            report["errors"].append(
                "empty_workflow"
            )

            return report

        samplers = [

            str(node_id)

            for node_id, node in workflow.items()

            if isinstance(node, dict)

            and node.get("class_type") == "KSampler"

        ]

        if not samplers:

            report["status"] = "blocked"

            report["errors"].append(
                "no_sampler_conditioning"
            )

            return report

        for sampler_id in samplers:

            inputs = (
                workflow.get(
                    sampler_id,
                    {}
                ).get(
                    "inputs",
                    {}
                )
                or {}
            )

            for polarity, bucket in (

                ("positive", report["positive"]),

                ("negative", report["negative"]),

            ):

                terminal, error = self._follow_conditioning_link(
                    workflow,
                    inputs.get(polarity),
                    polarity
                )

                report["traversal"].append({

                    "sampler": sampler_id,

                    "polarity": polarity,

                    "terminal": terminal,

                    "error": error,

                })

                if error:

                    report["errors"].append(
                        error
                    )

                else:

                    bucket.add(
                        terminal
                    )

        if (
            not report["errors"]
            and (report["positive"] & report["negative"])
        ):

            report["errors"].append(
                "conditioning_polarity_conflict"
            )

        if (
            not report["errors"]
            and not report["positive"]
        ):

            report["errors"].append(
                "no_positive_conditioning_terminal"
            )

        if report["errors"]:

            report["status"] = "blocked"

        return report


    # ======================================================
    # DETECT CLIP ROUTES
    #
    # Backward-compatible 2-tuple view of `resolve_clip_routes()`. It now
    # returns the RESOLVED CLIPTextEncode terminals (not the raw immediate
    # link targets), so a conditioned graph yields 206 / 212 instead of the
    # ControlNetApplyAdvanced node 311.
    # ======================================================

    def detect_clip_routes(
        self,
        workflow
    ):

        report = self.resolve_clip_routes(
            workflow
        )

        return (

            report["positive"],

            report["negative"]

        )



    # ======================================================
    # INJECT CLIP PROMPTS
    # ======================================================


    def inject_prompt(
        self,
        workflow,
        prompt,
        negative_prompt=None
    ):


        positive_prompt = self.normalize_prompt(
            prompt
        )


        # KNOWLEDGE_RECOVERY_01 — an explicit negative may be supplied.
        # `None` (every existing caller) keeps the historical default
        # negative byte for byte. An empty string is honoured, which lets
        # a caller state truthfully that a graph consumes NO negative
        # conditioning instead of writing a negative it would discard.
        negative_prompt = (
            self.normalize_negative()
            if negative_prompt is None
            else str(negative_prompt)
        )



        # ==================================================
        # FACADE-04D.3C-3 — CONDITIONING-AWARE ROUTE RESOLUTION
        #
        # The KSampler may reach its CLIPTextEncode terminals through a
        # conditioning passthrough (ControlNetApplyAdvanced in the conditioned
        # dual-image graph). Resolve the real terminals first so the prompt is
        # written to 206 / 212 instead of being skipped and the workflow's
        # template prompt surviving.
        #
        # FAIL CLOSED: an unsupported, ambiguous or cyclic conditioning graph
        # injects NOTHING and reports `blocked`, so the caller can refuse the
        # render rather than submitting a template prompt.
        # ==================================================

        resolution = self.resolve_clip_routes(
            workflow
        )

        positive_nodes = resolution["positive"]

        negative_nodes = resolution["negative"]



        print(
            "✅ IMG2IMG POSITIVE NODES:",
            positive_nodes
        )


        print(
            "⛔ IMG2IMG NEGATIVE NODES:",
            negative_nodes
        )


        if resolution["status"] != "resolved":


            print(
                "⛔ PROMPT INJECTION BLOCKED:",
                resolution["errors"]
            )


            return workflow, resolution



        for node_id,node in workflow.items():


            if not isinstance(
                node,
                dict
            ):

                continue



            if node.get(
                "class_type"
            ) != "CLIPTextEncode":

                continue



            inputs = node.setdefault(
                "inputs",
                {}
            )



            if "text" not in inputs:

                continue



            # ==============================================
            # POSITIVE
            # ==============================================


            if str(
                node_id
            ) in positive_nodes:


                inputs["text"] = positive_prompt


                print(
                    "🔥 IMG2IMG POSITIVE PROMPT:",
                    node_id
                )


                continue



            # ==============================================
            # NEGATIVE
            # ==============================================


            if str(
                node_id
            ) in negative_nodes:


                inputs["text"] = negative_prompt


                print(
                    "⛔ IMG2IMG NEGATIVE PROMPT:",
                    node_id
                )


                continue



            print(
                "⚠️ UNKNOWN CLIP NODE SKIPPED:",
                node_id
            )



        return workflow, resolution



    # ======================================================
    # INJECT
    # ======================================================


    # ======================================================
    # DENOISE / STRENGTH  (IMAGE_TO_IMAGE_05)
    #
    # Single authoritative denoise injection for img2img.
    # The value comes from the deterministic preservation level
    # (high_preservation / balanced / creative) and is validated
    # before it is written. flux_img2img.json is never edited.
    # ======================================================

    def inject_denoise(
        self,
        workflow,
        context
    ):


        if not isinstance(
            context,
            dict
        ):

            return workflow


        denoise = context.get(
            "denoise"
        )


        try:

            denoise = float(
                denoise
            )

        except (TypeError, ValueError):

            return workflow


        if denoise <= 0 or denoise > 1:

            return workflow


        denoise = round(
            denoise,
            3
        )


        for node_id,node in workflow.items():


            if not isinstance(
                node,
                dict
            ):

                continue


            if node.get(
                "class_type"
            ) != "KSampler":

                continue


            inputs = node.setdefault(
                "inputs",
                {}
            )


            old_denoise = inputs.get(
                "denoise"
            )


            inputs["denoise"] = denoise


            print(
                "🎚️ IMG2IMG DENOISE:",
                node_id,
                old_denoise,
                "->",
                denoise
            )


        return workflow



    # ======================================================
    # SEED  (IMAGE_TO_IMAGE_05)
    #
    # Removes the frozen seed 0 baseline so consecutive edits can
    # vary deterministically.
    # ======================================================

    def inject_seed(
        self,
        workflow,
        context
    ):


        if not isinstance(
            context,
            dict
        ):

            return workflow


        seed = context.get(
            "seed"
        )


        try:

            seed = int(
                seed
            )

        except (TypeError, ValueError):

            return workflow


        for node_id,node in workflow.items():


            if not isinstance(
                node,
                dict
            ):

                continue


            if node.get(
                "class_type"
            ) != "KSampler":

                continue


            inputs = node.setdefault(
                "inputs",
                {}
            )


            old_seed = inputs.get(
                "seed"
            )


            inputs["seed"] = seed


            print(
                "🎲 IMG2IMG SEED:",
                node_id,
                old_seed,
                "->",
                seed
            )


        return workflow



    # ======================================================
    # STEPS  (draft / preview profile)
    #
    # Used by the draft profile so functional/acceptance renders can
    # validate the pipeline quickly. Production defaults are unchanged
    # because nothing injects steps unless a draft profile is active.
    # ======================================================

    def inject_steps(
        self,
        workflow,
        context
    ):


        if not isinstance(
            context,
            dict
        ):

            return workflow


        steps = context.get(
            "steps"
        )


        try:

            steps = int(
                steps
            )

        except (TypeError, ValueError):

            return workflow


        if steps <= 0 or steps > 150:

            return workflow


        for node_id,node in workflow.items():


            if not isinstance(
                node,
                dict
            ):

                continue


            if node.get(
                "class_type"
            ) != "KSampler":

                continue


            inputs = node.setdefault(
                "inputs",
                {}
            )


            old_steps = inputs.get(
                "steps"
            )


            inputs["steps"] = steps


            print(
                "🪜 IMG2IMG STEPS:",
                node_id,
                old_steps,
                "->",
                steps
            )


        return workflow



    # ======================================================
    # MAIN
    # ======================================================

    def inject(
        self,
        workflow,
        prompt,
        image_asset=None,
        context=None,
        image_bindings=None,
        mask_asset=None
    ):


        # ==================================================
        # ISOLATED WORKING COPY
        # ==================================================

        injected = copy.deepcopy(
            workflow
        )


        # ==================================================
        # DENOISE + SEED  (before prompt/image injection)
        #
        # NOTE: dimensions are deliberately NEVER injected for
        # img2img - the latent comes from the source image via
        # VAEEncode, so width/height are source-driven.
        # ==================================================

        injected = self.inject_denoise(
            injected,
            context
        )


        injected = self.inject_seed(
            injected,
            context
        )


        injected = self.inject_steps(
            injected,
            context
        )


        result = {


            "workflow":

                injected,


            "architectos_prompt":

                prompt,


            "status":

                "injected"

        }



        # ==================================================
        # IMAGE INJECTION
        # ==================================================


        # ==================================================
        # FACADE-04D.2 — EXPLICIT ROLE-AWARE IMAGE BINDING
        #
        # When `image_bindings` is supplied (dual-image facade render) each
        # role is written to its OWN node id. The old "assign the filename to
        # EVERY LoadImage node" behaviour is skipped entirely, so IMAGE A can
        # never overwrite the IMAGE B geometry node (300) and vice versa.
        # ==================================================

        if image_bindings:

            from core.render.dual_image_binding_v1 import (
                bind_role_bindings,
            )

            injected, binding_report = bind_role_bindings(
                injected,
                image_bindings,
            )

            result["image_binding_report"] = binding_report

            for role, info in (binding_report.get("bound") or {}).items():

                print(
                    "🖼️ IMAGE BOUND:",
                    role,
                    "-> node",
                    info.get("node_id"),
                    info.get("filename")
                )

            for error in (binding_report.get("errors") or []):

                print(
                    "🖼️ IMAGE BINDING ERROR:",
                    error
                )

        elif image_asset:


            result["image_asset"] = image_asset



            filename = (

                image_asset.get(
                    "filename"
                )

                or

                image_asset.get(
                    "path"
                )

            )



            for node_id,node in injected.items():


                if not isinstance(
                    node,
                    dict
                ):

                    continue



                if node.get(
                    "class_type"
                ) == "LoadImage":


                    inputs = node.setdefault(
                        "inputs",
                        {}
                    )


                    inputs["image"] = filename



                    print(
                        "🖼️ IMAGE INJECTED:",
                        node_id,
                        filename
                    )


        # ==================================================
        # KNOWLEDGE_RECOVERY_01 — CALLER-SUPPLIED MASK
        #
        # The Kontext instruction-edit graph confines its change with an
        # `ImageCompositeMasked` node fed by `LoadImageMask`. The mask is
        # ALWAYS supplied by the caller: ArchitectOS does not generate,
        # segment or derive a mask here, and a missing mask is reported
        # rather than substituted. When no mask is supplied the graph's
        # own placeholder stays untouched and the request must be refused
        # upstream (precision-critical edits are never silently widened
        # to whole-image editing).
        # ==================================================

        if mask_asset:

            mask_filename = (

                mask_asset.get(
                    "filename"
                )

                or

                mask_asset.get(
                    "path"
                )

                if isinstance(mask_asset, dict)

                else mask_asset

            )

            mask_nodes = 0

            for node_id, node in injected.items():

                if not isinstance(node, dict):

                    continue

                if node.get("class_type") != "LoadImageMask":

                    continue

                node.setdefault("inputs", {})["image"] = mask_filename

                mask_nodes += 1

                print(
                    "🎭 MASK INJECTED:",
                    node_id,
                    mask_filename
                )

            result["mask_asset"] = mask_asset

            result["mask_nodes_injected"] = mask_nodes


        # IMAGE_EDIT_ENGINE_INTEGRATION_V1 — bind the existing Kontext
        # graph's actual input contract only after source and optional mask
        # filenames have been independently assigned.  This mutates the
        # isolated working copy, never the canonical workflow JSON.
        reference_edit_contract = self._bind_reference_edit_contract(
            injected,
            image_asset,
            mask_asset,
        )

        result["reference_edit_contract"] = reference_edit_contract

        if reference_edit_contract.get("status") == "blocked":

            result["status"] = "blocked"



        # ==================================================
        # PROMPT INJECTION
        # ==================================================


        final_prompt = self.normalize_prompt(
            prompt
        )



        print(
            "🔥 IMG2IMG FINAL PROMPT:",
            final_prompt
        )



        injected, prompt_injection = self.inject_prompt(
            injected,
            final_prompt,
            # KNOWLEDGE_RECOVERY_01 — forwarded only when the caller stated
            # one. `None` keeps the historical default negative.
            negative_prompt=(
                (context or {}).get("negative_prompt")
                if isinstance(context, dict)
                else None
            )
        )



        result["workflow"] = injected

        # API_JSON_SERIALIZATION_FIX_V1 — route resolution deliberately uses
        # sets internally for uniqueness and polarity-intersection checks.
        # `result`, however, is public render metadata and is eventually
        # returned by the Chat HTTP API.  Keep the resolver contract intact,
        # but project its two node collections to deterministic JSON arrays at
        # this ownership boundary.  The remaining report fields are already
        # JSON-compatible and are preserved byte-for-byte.
        prompt_injection_metadata = dict(prompt_injection)

        for polarity in ("positive", "negative"):

            nodes = prompt_injection_metadata.get(polarity)

            if isinstance(nodes, set):

                prompt_injection_metadata[polarity] = sorted(
                    str(node_id) for node_id in nodes
                )

        result["prompt_injection"] = prompt_injection_metadata



        # FACADE-04D.3C-3 — fail closed. An unresolved conditioning graph must
        # never be submitted with the workflow's template prompt, so the
        # result is flagged `blocked` for the caller's gate.
        if prompt_injection.get("status") != "resolved":


            result["status"] = "blocked"


        return result
    # ======================================================
    # KONTEXT SOURCE-DIMENSION / OPTIONAL-MASK CONTRACT
    #
    # The production Kontext graph is the accepted ReferenceLatent
    # instruction-edit graph.  Unlike ordinary img2img it samples from an
    # EmptySD3LatentImage, so its dimensions must be bound explicitly to the
    # staged source.  Root B's accepted orchestrator also treats the
    # compositing mask as optional: maskless global edits save VAEDecode
    # directly; localized edits save ImageCompositeMasked.
    # ======================================================

    @staticmethod
    def _is_reference_latent_edit(workflow):

        class_types = {
            str((node or {}).get("class_type"))
            for node in (workflow or {}).values()
            if isinstance(node, dict)
        }

        return bool(
            "ReferenceLatent" in class_types
            and "EmptySD3LatentImage" in class_types
        )


    def _bind_reference_edit_contract(
        self,
        workflow,
        image_asset,
        mask_asset,
    ):

        report = {
            "contract": "ReferenceLatentEditInputV1",
            "status": "not_applicable",
            "scope": None,
            "width": None,
            "height": None,
            "save_source_node": None,
            "errors": [],
        }

        if not self._is_reference_latent_edit(workflow):

            return report

        report["status"] = "resolved"
        report["scope"] = "localized" if mask_asset else "global"

        dimensions = (
            image_asset.get("working_dimensions")
            if isinstance(image_asset, dict)
            else None
        )

        # Normal production assets carry `working_dimensions`.  Legacy
        # internal callers may provide only the staged file path; reuse the
        # existing ImageAssetBridge PNG reader rather than falling back to the
        # workflow's 384x512 placeholder or inventing resize behaviour.
        if (
            not dimensions
            and isinstance(image_asset, dict)
            and image_asset.get("path")
        ):

            try:

                from core.render.image_asset_bridge import ImageAssetBridge

                dimensions = ImageAssetBridge._png_dimensions(
                    image_asset.get("path")
                )

            except (OSError, TypeError, ValueError):

                dimensions = None

        if not (
            isinstance(dimensions, (list, tuple))
            and len(dimensions) == 2
        ):

            report["status"] = "blocked"
            report["errors"].append("source_dimensions_missing")
            return report

        try:

            width = int(dimensions[0])
            height = int(dimensions[1])

        except (TypeError, ValueError):

            width = 0
            height = 0

        # EmptySD3LatentImage exposes dimensions in 16-pixel increments.
        # Refuse rather than rounding or resizing: the staged source remains
        # the only resolution authority and localized compositing must stay
        # pixel-aligned with it.
        if (
            width <= 0
            or height <= 0
            or width % 16
            or height % 16
        ):

            report["status"] = "blocked"
            report["errors"].append("source_dimensions_not_model_compatible")
            return report

        empty_latents = [
            (str(node_id), node)
            for node_id, node in workflow.items()
            if isinstance(node, dict)
            and node.get("class_type") == "EmptySD3LatentImage"
        ]
        decoded = [
            str(node_id)
            for node_id, node in workflow.items()
            if isinstance(node, dict)
            and node.get("class_type") == "VAEDecode"
        ]
        composites = [
            str(node_id)
            for node_id, node in workflow.items()
            if isinstance(node, dict)
            and node.get("class_type") == "ImageCompositeMasked"
        ]
        saves = [
            node
            for node in workflow.values()
            if isinstance(node, dict)
            and node.get("class_type") == "SaveImage"
        ]

        if len(empty_latents) != 1 or len(decoded) != 1 or len(saves) != 1:

            report["status"] = "blocked"
            report["errors"].append("ambiguous_reference_edit_graph")
            return report

        if mask_asset and len(composites) != 1:

            report["status"] = "blocked"
            report["errors"].append("localized_composite_missing")
            return report

        # SOURCE / MASK IDENTITY SAFETY V1 — verify the ACTUAL graph, not the
        # request. Whatever the caller believed, the injected workflow must
        # never feed one asset to both LoadImage and LoadImageMask: that is
        # SOURCE_MASK_MISROUTING, and it is invisible to every other check
        # here. The boundary in app.py also compares digests; this is the
        # structural backstop on the final graph.
        if mask_asset:

            source_names = {
                str((node.get("inputs") or {}).get("image") or "")
                for node in workflow.values()
                if isinstance(node, dict)
                and node.get("class_type") == "LoadImage"
            }

            mask_names = {
                str((node.get("inputs") or {}).get("image") or "")
                for node in workflow.values()
                if isinstance(node, dict)
                and node.get("class_type") == "LoadImageMask"
            }

            shared = (source_names & mask_names) - {""}

            if shared:

                report["status"] = "blocked"
                report["errors"].append("source_mask_identity_collision")
                report["colliding_filenames"] = sorted(shared)
                return report

        latent_id, latent_node = empty_latents[0]
        latent_node.setdefault("inputs", {})["width"] = width
        latent_node.setdefault("inputs", {})["height"] = height

        save_source = composites[0] if mask_asset else decoded[0]
        saves[0].setdefault("inputs", {})["images"] = [save_source, 0]

        report.update({
            "latent_node": latent_id,
            "width": width,
            "height": height,
            "save_source_node": save_source,
        })

        # ==================================================
        # FACADE_I2I_SUBMISSION_SAFETY_V1 — DEAD MASK BRANCH
        #
        # A maskless edit rebinds SaveImage to VAEDecode, which leaves the
        # graph's own `LoadImageMask` -> `ImageCompositeMasked` pair with no
        # path to any output. The sampler never sees them, but they are still
        # part of the submitted prompt, and they still name an input file
        # (`mask.png`) that need not exist. ComfyUI validates every node in a
        # submitted prompt, so an unreachable node with an invalid image input
        # is a real submission hazard even though it cannot affect the render.
        #
        # The dead branch is removed from the ISOLATED working copy only. A
        # caller-supplied mask is untouched: with a mask the composite IS the
        # save source and nothing here runs.
        # ==================================================

        report["mask_branch_pruning"] = (
            {"status": "retained_masked_edit", "pruned_nodes": []}
            if mask_asset
            else self._prune_dead_mask_branch(workflow)
        )

        return report

    # ======================================================
    # FACADE_I2I_SUBMISSION_SAFETY_V1 — DEAD MASK BRANCH PRUNING
    #
    # Only nodes reachable FROM a `LoadImageMask` are candidates, and only
    # those that no output can reach are removed. A node the output depends on
    # is never a candidate, and an unrelated unreachable node (a pre-existing
    # graph quirk elsewhere) is never touched.
    # ======================================================

    @staticmethod
    def _prune_dead_mask_branch(workflow):

        mask_ids = [
            str(node_id)
            for node_id, node in workflow.items()
            if isinstance(node, dict)
            and node.get("class_type") == "LoadImageMask"
        ]

        if not mask_ids:

            return {"status": "not_applicable", "pruned_nodes": []}

        consumers = {}

        for node_id, node in workflow.items():

            if not isinstance(node, dict):
                continue

            for value in ((node.get("inputs") or {}).values()):

                if (
                    isinstance(value, list)
                    and len(value) == 2
                    and isinstance(value[0], (str, int))
                ):
                    consumers.setdefault(str(value[0]), []).append(str(node_id))

        # Forward closure from every mask loader: the mask branch itself.
        branch = set()
        stack = list(mask_ids)

        while stack:

            node_id = stack.pop()

            if node_id in branch:
                continue

            branch.add(node_id)
            stack.extend(consumers.get(node_id, ()))

        # Backward closure from every output: what the render needs.
        live = set()
        stack = [
            str(node_id)
            for node_id, node in workflow.items()
            if isinstance(node, dict) and node.get("class_type") == "SaveImage"
        ]

        while stack:

            node_id = stack.pop()

            if node_id in live or node_id not in workflow:
                continue

            live.add(node_id)

            for value in ((workflow.get(node_id) or {}).get("inputs") or {}).values():

                if (
                    isinstance(value, list)
                    and len(value) == 2
                    and isinstance(value[0], (str, int))
                ):
                    stack.append(str(value[0]))

        pruned = []

        for node_id in sorted(branch - live):

            node = workflow.pop(node_id, None)

            if isinstance(node, dict):
                pruned.append({
                    "node_id": node_id,
                    "class_type": node.get("class_type"),
                })

        if pruned:
            print(
                "🧹 DEAD MASK BRANCH PRUNED:",
                [item["node_id"] for item in pruned]
            )

        return {
            "status": "pruned" if pruned else "no_dead_nodes",
            "pruned_nodes": pruned,
            "remaining_mask_nodes": [
                str(node_id)
                for node_id, node in workflow.items()
                if isinstance(node, dict)
                and node.get("class_type") == "LoadImageMask"
            ],
        }
