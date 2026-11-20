# ==========================================================
# ArchitectOS Render Runtime v7.4
# Unified Image / Video Aware Render Pipeline
#
# FIX:
# - Stable img2img routing
# - Preserve architectural intent
# - Preserve render mode
# - Context injection upgrade
# - Prompt pipeline stabilization
# - Fix undefined payload debug
# - Protect incoming architectural intent
# ==========================================================


import os
import time


from core.prompt_intelligence.prompt_router import PromptRouter
from core.prompt_intelligence.render_prompt_resolver_v1 import (
    resolve_render_prompt,
)

# TEXT_TO_IMAGE_COMFY_03 — explicit preset layer
from core.render.render_preset_v1 import (
    resolve_preset as resolve_render_preset,
    build_quality_tail as build_preset_quality_tail,
    tail_conflicts as preset_tail_conflicts,
    tail_reinforcement as preset_tail_reinforcement,
    CONTRACT as RENDER_PRESET_CONTRACT,
    VERSION as RENDER_PRESET_VERSION,
)

from core.cognition.architectural_terminology_v1 import (
    normalize_architectural_terms,
)

# IMAGE_TO_IMAGE_05 — draft/preview profile for functional renders
from core.render.render_draft_v1 import (
    profile as render_draft_profile,
    resolve_profile as resolve_render_profile,
)

# IMAGE_TO_IMAGE_05 — truthful img2img capability contract
from core.render.image_edit_capability_v1 import (
    capability_flags as image_edit_capability_flags,
)
from core.render.workflow_loader import WorkflowLoader
from core.render.workflow_selector import WorkflowSelector
from core.render.workflow_injector import WorkflowInjector
from core.render.image_workflow_injector import ImageWorkflowInjector
from core.render.workflow_executor import WorkflowExecutor
from core.prompt_intelligence.architectural_intent import ArchitecturalIntent
from core.prompt_intelligence.image_edit_intent import ImageEditIntent
from core.render.render_result_bridge import RenderResultBridge
from core.render.comfy_ws_listener import (
    ComfyProgressListener,
    sampler_node_ids,
    make_client_id,
    build_ws_url,
)
from core.architecture.knowledge.resolved_facade_knowledge import (
    SharedFacadeKnowledgeResolverV1,
)


# ==========================================================
# V22_HIGHRISE_NIGHT_ROUTING_V1 — SUBMISSION GRAPH
#
# `build_mode_specific_stage2_workflow()` stamps the active mode onto
# the graph as `_architectos_mode` so a caller can tell which mode
# produced it. ComfyUI's POST /prompt accepts NODE objects only, and
# `comfy_http_runtime` strips exactly one internal key
# (`_architectos_runtime`), so an unstripped stamp would be submitted
# as a phantom node and the whole graph would be rejected.
#
# The stamp is therefore removed from the graph that is submitted and
# kept in the render trace instead. This is a pure function so the
# removal is testable without a GPU.
# ==========================================================

def strip_v22_graph_metadata(workflow):
    """Remove v22 bookkeeping keys from a graph about to be submitted."""

    if isinstance(workflow, dict):

        workflow.pop("_architectos_mode", None)

    return workflow



class RenderRuntime:

    VERSION = "7.4"




    def __init__(
        self,
        semantic_intent=None
    ):


        self.semantic_intent = semantic_intent


        self.intent = ArchitecturalIntent()


        self.loader = WorkflowLoader()


        self.selector = WorkflowSelector()


        self.workflow_injector = WorkflowInjector()


        self.image_injector = ImageWorkflowInjector()


        # EXISTING_VISUAL_KNOWLEDGE_USO_V1 — the reference payload bound by the
        # most recent USO render, for lineage. None for every other route.
        self.last_uso_reference = None


        self.executor = WorkflowExecutor()

        # REAL_RENDER_LIFECYCLE_V1 — the ONE ComfyUI job this runtime
        # currently owns, published at submission time (before the blocking
        # wait) so a read-only status endpoint can report real lifecycle
        # state. Cleared in the same `finally` that releases the render
        # guard. `_render_generation` makes every record attributable to a
        # single invocation, so an older render can never clear or
        # overwrite a newer one.
        self.active_render = None
        self._render_generation = 0

        # REAL_SAMPLING_PROGRESS_B_PLUS — the WebSocket listener for
        # the current render. Read by the status endpoint to report
        # verified sampler step progress. Cleared with active_render.
        self._progress_listener = None



        self.result_bridge = RenderResultBridge()


        self.prompt_builder = PromptRouter()


        self.image_edit_intent = ImageEditIntent()


        self.facade_knowledge_resolver = SharedFacadeKnowledgeResolverV1()


        # ==================================================
        # RENDER HANDOFF TRACE (CHAT_LANGUAGE_02)
        # Last request actually received by this runtime.
        # Diagnostic only - no behaviour depends on it.
        # ==================================================

        self.last_render_request = {}


        # TEXT_TO_IMAGE_COMFY_03 — last resolved request metadata
        # (preset / final prompt / seed / size / status). Diagnostic.
        self.last_render_metadata = {}

        # FACADE-04D.3C-5B.1 — H2 (safe Ollama release) trace of the last
        # render. H2 runs HERE, immediately before the ComfyUI submit, so that
        # it is the request's LAST model operation and the GPU handoff covers
        # the whole protected rendering period. Diagnostic + fail-closed.
        self.last_gpu_handoff_h2 = None

        # FACADE-04D.3C-5B.1 — outcome of the protected rendering period
        # (the exclusive `gpu_render` lease). Machine-readable so a refused
        # render is diagnosable even though the response adapter rebuilds the
        # envelope and drops a top-level `reason`.
        self.last_gpu_handoff_render = None

        # V4.3F — ORPHANED RENDER. When a ComfyUI job's termination cannot be
        # confirmed, the `gpu_render` lease is deliberately NOT released: the
        # guard object is parked here so ownership survives the request. This
        # blocks every later ArchitectOS GPU operation (including Ollama, which
        # cannot take the lease) until positive evidence shows the job stopped.
        #
        # LIMIT: these are OS advisory locks. They are released by the OS when
        # the process dies, so this protects against a leaked job inside a live
        # process — it does NOT protect across a crash or restart, and it is not
        # claimed to.
        self._orphaned_render_guard = None
        self._orphaned_prompt_id = None
        self._orphaned_reason = None
        self._orphaned_since = None



        # ==================================================
        # PRESERVE INJECTED SEMANTIC INTENT ENGINE
        # ==================================================

        if self.semantic_intent is None:

            from core.intelligence.semantic_intent import SemanticIntentEngine


            self.semantic_intent = SemanticIntentEngine(
                fallback=self.intent
            )



        print(
            "🚀 RENDER RUNTIME v7.4 ONLINE"
        )

    # ======================================================
    # REAL_RENDER_LIFECYCLE_V1 — ACTIVE RENDER RECORD
    #
    # Two tiny accessors, so the publish/clear contract is explicit and
    # directly testable without running a render. They touch nothing else.
    # ======================================================

    def _resolve_owner_project_id(self):
        """The project that owns the render happening in THIS request.

        CORRECTED (B+ independent review): the ONLY accepted source is
        Flask's request-scoped `g.project_id`, which app.py binds from
        the request body/form before any handler runs.

        The process-wide project-session singleton is deliberately NOT
        consulted. Reading it would reintroduce the cross-request race
        this phase removes: a concurrent request for a different project
        could move the singleton between app.py's check and this read.

        Returns None when no request-scoped owner exists. Callers treat
        None as "unowned": no progress record is published, and the
        render itself is unaffected.
        """
        try:
            from flask import g as _flask_g
        except Exception:
            return None

        try:
            owner = getattr(_flask_g, "project_id", None)
        except Exception:
            # Outside a Flask request context `g` raises on attribute
            # access, which is exactly the "no owner" case.
            return None

        if not owner:
            return None

        return str(owner)

    def _publish_active_render(self, record):
        self.active_render = record
        return record

    def _clear_active_render(self, generation):
        """Clear ONLY the record owned by `generation`.

        Returns True when it cleared something. A late finish from an
        older render therefore cannot wipe a newer render's record.
        """

        if (
            self.active_render is not None
            and self.active_render.get("generation") == generation
        ):

            self.active_render = None
            self._progress_listener = None
            return True

        return False



    # ======================================================
    # RENDER
    # ======================================================

    def resolve_shared_facade_knowledge(self, intent_data):

        resolved = self.facade_knowledge_resolver.resolve(
            intent_data
        )

        intent_data["resolved_facade_knowledge"] = resolved
        intent_data["facade_knowledge_consumed"] = True

        canonical_style = resolved.get("canonical_style")
        if canonical_style and canonical_style != "UNKNOWN":
            intent_data.setdefault(
                "requested_style",
                resolved.get("requested_style")
            )
            intent_data["style"] = canonical_style

        return resolved


    # ======================================================
    # EFFECTIVE RENDER PARAMS  (TEXT_TO_IMAGE_COMFY_03)
    #
    # Reads the values that were ACTUALLY sent to ComfyUI from the
    # injected workflow, rather than trusting the requested values.
    # ======================================================

    @staticmethod
    def _workflow_render_params(workflow):

        params = {

            "width": None,
            "height": None,
            "steps": None,
            "denoise": None,

        }

        if not isinstance(workflow, dict):

            return params

        for node in workflow.values():

            if not isinstance(node, dict):

                continue

            inputs = node.get("inputs")

            if not isinstance(inputs, dict):

                continue

            class_type = node.get("class_type")

            if class_type in ("EmptyLatentImage", "EmptySD3LatentImage"):

                params["width"] = inputs.get("width")
                params["height"] = inputs.get("height")

            elif class_type == "KSampler":

                params["steps"] = inputs.get("steps")

                params["denoise"] = inputs.get("denoise")

        return params


    # ======================================================
    # PRESET RESOLUTION  (TEXT_TO_IMAGE_COMFY_03)
    # ======================================================

    def _resolve_request_preset(self, design):
        """Resolve the render preset for this request.

        Precedence:
          0. img2img suppresses an AUTOMATICALLY supplied preset (authoritative);
             an EXPLICIT user-selected preset is preserved
          1. an already-resolved preset contract supplied by the caller
             (avoids recomputing terminology in the chat path)
          2. explicit preset name on the request
          3. deterministic inference from the user's own wording
          4. safe default / none
        """

        # --------------------------------------------------
        # IMAGE_TO_IMAGE_05 — PRESETS ARE SUPPRESSED FOR IMG2IMG
        #
        # Text-to-image presets control lighting tails, dimensions and
        # steps. For img2img the latent comes from the source image and
        # the appearance is controlled by the preservation level, so
        # applying a preset would contaminate the edit.
        #
        # FACADE-04D.3C-4 — this rule must be evaluated BEFORE the
        # caller-supplied preset. The chat layer always supplies a resolved
        # preset; when this check came second, an AUTOMATICALLY inferred
        # text-to-image preset (exterior_day: steps 20 + a "bright natural
        # daylight" tail) was applied to img2img renders, overriding the
        # workflow's authored steps and contaminating the edit prompt.
        #
        # An EXPLICIT user-selected preset (source == "explicit") is a
        # deliberate user setting and is preserved unchanged.
        # --------------------------------------------------

        if str(design.get("mode")) == "img2img":

            given = design.get("preset_resolution")

            if (
                isinstance(given, dict)
                and given.get("contract") == RENDER_PRESET_CONTRACT
                and given.get("source") == "explicit"
            ):

                return given


            return {

                "contract": RENDER_PRESET_CONTRACT,
                "version": RENDER_PRESET_VERSION,

                "name": None,
                "preset": None,

                "source": "suppressed_for_img2img",
                "reason": "img2img_is_source_driven",

                "width": None,
                "height": None,
                "steps": None,
                "seed_mode": None,
                "seed": None,

                "quality_tail": "",
                "tags": {},

            }


        given = design.get("preset_resolution")

        if (
            isinstance(given, dict)
            and given.get("contract") == RENDER_PRESET_CONTRACT
        ):

            return given


        terminology = design.get("terminology")

        if not isinstance(terminology, dict):

            terminology = normalize_architectural_terms(
                design.get("original_prompt")
                or design.get("prompt")
                or ""
            )


        return resolve_render_preset(
            terminology=terminology,
            explicit=design.get("preset"),
        )


    # ======================================================
    # TRUTHFUL RENDER STATUS
    # ======================================================

    # Execution statuses that mean "ComfyUI finished the workflow".
    EXECUTION_COMPLETED_STATUSES = (
        "completed",
    )


    def _resolve_render_status(
        self,
        execution,
        resolved_result
    ):
        """Derive the render status from the REAL execution outcome.

        RUNTIME_FOUNDATION_01:
        render() used to hardcode status="success", so a failed ComfyUI
        run, a rejected workflow or a missing output file was still
        reported as success. Success is now returned ONLY when the
        executor reported a completed execution AND a real output asset
        (image or video) was actually produced.
        """

        if not isinstance(
            execution,
            dict
        ):

            return "execution_unknown"


        execution_status = execution.get(
            "status"
        )


        if execution_status is None:

            return "execution_unknown"


        execution_status = str(
            execution_status
        )


        # --------------------------------------------------
        # NOT COMPLETED -> PRESERVE THE REAL FAILURE REASON
        # --------------------------------------------------

        if execution_status not in self.EXECUTION_COMPLETED_STATUSES:

            return execution_status


        # --------------------------------------------------
        # COMPLETED -> AN OUTPUT MUST REALLY EXIST
        # --------------------------------------------------

        videos = execution.get(
            "videos"
        )

        if isinstance(
            videos,
            list
        ) and videos:

            return "success"


        if isinstance(
            resolved_result,
            dict
        ):

            asset = (

                resolved_result.get(
                    "image_asset"
                )

                or

                resolved_result.get(
                    "image"
                )

            )

            if asset:

                # TEXT_TO_IMAGE_COMFY_03 — truthful output contract.
                # An asset whose file is known to be missing must never
                # be reported as success. When the flag is absent the
                # previous behaviour is preserved unchanged.
                if (
                    isinstance(asset, dict)
                    and asset.get("exists") is False
                ):

                    return "output_missing"

                return "success"


            resolved_status = resolved_result.get(
                "status"
            )


            if resolved_status in (
                "success",
                None
            ):

                return "completed_no_output"


            return str(
                resolved_status
            )


        return "completed_no_output"


    # ==================================================
    # V4.3F — ORPHANED-JOB OWNERSHIP
    #
    # A render whose ComfyUI job could not be proven stopped keeps the
    # `gpu_render` lease. These helpers decide, from positive evidence only,
    # whether that lease may be given up.
    #
    # "Cannot observe" is never treated as "idle": if there is no lifecycle
    # channel (no queue reader on the executor) the answer is False.
    # ==================================================

    def _comfy_lifecycle(self):
        """The object able to read the ComfyUI queue, or None."""

        comfy = getattr(
            getattr(self, "executor", None),
            "comfy",
            None
        )

        if comfy is None or not hasattr(comfy, "queue_state"):

            return None

        return comfy


    def _prove_no_active_job(self, prompt_id):
        """Return (proved, detail). ``proved=False`` means UNKNOWN, not busy."""

        comfy = self._comfy_lifecycle()

        if comfy is None:

            return False, "no_lifecycle_channel"

        try:

            state = comfy.queue_state()

        except BaseException as exc:

            return False, "queue_exception:%s" % exc

        if not isinstance(state, dict) or not state.get("ok"):

            return False, "queue_unreadable"

        running = state.get("running") or []
        pending = state.get("pending") or []

        if prompt_id is None:

            # No id to look for: only a completely empty queue is proof.
            if running or pending:

                return False, "queue_not_empty"

            return True, "queue_empty"

        if str(prompt_id) in running or str(prompt_id) in pending:

            return False, "job_still_active"

        return True, "job_not_in_queue"


    def _retain_orphaned_render(self, guard, prompt_id, reason):
        """Park the guard so ownership survives this request."""

        self._orphaned_render_guard = guard
        self._orphaned_prompt_id = prompt_id
        self._orphaned_reason = reason
        self._orphaned_since = time.time()

        print(
            "🪢 GPU LEASE RETAINED: ComfyUI job state unconfirmed",
            "| prompt:",
            prompt_id,
            "| reason:",
            reason
        )


    def _recover_orphaned_render(self):
        """Release a parked guard ONLY on positive evidence. Returns bool."""

        guard = self._orphaned_render_guard

        if guard is None:

            return True

        proved, detail = self._prove_no_active_job(
            self._orphaned_prompt_id
        )

        if not proved:

            self.last_gpu_handoff_render = {
                "contract": "GpuHandoffV1",
                "version": "1.0",
                "stage": "protected_render_period",
                "status": "orphaned",
                "reason": self._orphaned_reason or "job_state_unconfirmed",
                "prompt_id": self._orphaned_prompt_id,
                "recovery_detail": detail,
                "orphaned_since": self._orphaned_since,
            }

            return False

        try:

            guard.release()

        finally:

            self._orphaned_render_guard = None
            self._orphaned_prompt_id = None
            self._orphaned_reason = None
            self._orphaned_since = None

        print(
            "♻️ GPU LEASE RECOVERED: previous job confirmed stopped",
            "|",
            detail
        )

        return True


    # ==================================================
    # V4.3G — RECLAIM IDLE COMFYUI CACHE BEFORE BLOCKING
    #
    # The VRAM preflight measures FREE memory only. A completed render can
    # leave a large *reclaimable* model cache resident; the next render is
    # then refused even though nothing is executing. That is a resource
    # lifecycle gap, not a safety defect — and the fix must not weaken the
    # gate.
    #
    # This reuses the EXISTING H1 release verbatim. It does not introduce a
    # second lock, a manager, or a threshold change, and it cannot interrupt
    # or cancel anything: H1 refuses unless the ComfyUI queue is provably
    # empty, and it never signals the server. Because the caller already
    # holds the `gpu_render` lease, no other ArchitectOS render can submit
    # during the window; H1's own `comfyui` lease keeps the
    # [queue-read -> /free] pair atomic. Lock order stays
    # `gpu_render -> comfyui`, matching LOCK_ORDER.
    #
    # Returns H1's verdict. A `released` status is NOT proof that the floor
    # was reached — the caller must re-measure with the original gate.
    # ==================================================

    def _reclaim_idle_comfyui_cache(self, vram):
        """Attempt the existing H1 release. Never raises, never guesses."""

        if self._orphaned_render_guard is not None:

            return {
                "status": "skipped",
                "reason": "orphaned_job_unconfirmed",
            }

        if not isinstance(vram, dict) or vram.get("reason") != "insufficient_vram":

            # `vram_unmeasured` in particular must never be "fixed" by
            # releasing models: an unreadable GPU is unknown, not full.
            return {
                "status": "skipped",
                "reason": "not_insufficient_vram",
            }

        if vram.get("free_mib") is None or vram.get("raw_bytes") is None:

            return {
                "status": "skipped",
                "reason": "measurement_unreadable",
            }

        try:

            from core.runtime.gpu_handoff_v1 import release_comfyui_for_vision

            return release_comfyui_for_vision()

        except BaseException as exc:

            return {
                "status": "blocked",
                "reason": "release_exception:%s" % exc,
            }


    def render(
        self,
        project_id,
        design,
        engine="flux",
        image_asset=None,
        image_bindings=None,
        conditioned=False,
        mask_asset=None,
        kontext_edit=False,
        uso_reference=None,
        v22_mode=None,
        v22_control_image=None,
        v22_source_image=None
    ):


        design = design or {}


        # ==================================================
        # REAL_RENDER_LIFECYCLE_V1 — OWNERSHIP OF THIS RENDER
        #
        # CORRECTED (B+ independent review): the owner is taken ONLY from
        # Flask's request-scoped `g.project_id`, which app.py binds from
        # the request body/form before any handler runs.
        #
        # The previous version fell back to the process-wide
        # project-session singleton. That fallback is exactly the
        # cross-request race this phase exists to remove: a second
        # request for another project could move the singleton between
        # app.py's check and this capture, and the render would then be
        # attributed to the wrong project. There is NO fallback now.
        #
        # When no request-scoped owner exists, `_owner_project_id` stays
        # None: no progress record is published (an unowned prompt id is
        # never exposed), while the render itself runs unchanged.
        #
        # LIMITATION: this identifies the PROJECT of a request. It is not
        # a per-turn identity; two turns of the SAME project are
        # separated by `_generation`, not by the owner id. See the
        # correction report.
        # ==================================================

        _owner_project_id = self._resolve_owner_project_id()

        self._render_generation = int(self._render_generation or 0) + 1

        _generation = self._render_generation


        # FACADE-04D.3B-2 — conditioning trace, filled in by the gates below.
        # None for every unconditioned render (the historical behaviour).
        _conditioning = None


        # ==================================================
        # RENDER HANDOFF TRACE (CHAT_LANGUAGE_02)
        # Records the EXACT request this runtime received, before any
        # internal rebuilding, so the chat -> render handoff is provable.
        # ==================================================

        self.last_render_request = {

            "project_id":
                project_id,

            "engine":
                engine,

            "mode":
                design.get("mode"),

            "received_prompt":
                design.get("prompt"),

            "received_original_prompt":
                design.get("original_prompt"),

            "compiled_render_prompt":
                design.get("compiled_render_prompt"),

            "has_image_asset":
                bool(image_asset),

            # FACADE-04D.2 — role-aware dual-image binding was supplied
            # (IMAGE A -> its own node, IMAGE B -> node 300). Diagnostic.
            "has_image_bindings":
                bool(image_bindings),

            # FACADE-04D.3B-2 — explicit opt-in to the conditioned graph.
            "conditioned":
                bool(conditioned),

            # V22_HIGHRISE_NIGHT_ROUTING_V1 — explicit mode opt-in. None
            # for every existing caller, which keeps every route byte for
            # byte.
            "v22_mode":
                v22_mode,

            "received_at":
                time.time(),

        }

        # FACADE-04D.3C-5B.1 — the H2 trace of THIS render. Reset first so a
        # previous request's trace can never leak into this one.
        self.last_gpu_handoff_h2 = None
        self.last_gpu_handoff_render = None


        print(
            "========== DEBUG CONTRACT =========="
        )

        print(
            "DESIGN TYPE:",
            type(design)
        )

        print(
            "DESIGN KEYS:",
            design.keys()
        )

        print(
            "ARCH INTENT RAW:",
            design.get("architectural_intent")
        )

        print(
            "PROMPT RAW:",
            design.get("prompt")
        )

        print(
            "===================================="
        )


        print(
            "🚨 RUNTIME ENTRY ARCH INTENT:",
            design.get(
                "architectural_intent",
                {}
            )
        )


        print(
            "🚨 RUNTIME ENTRY PROMPT:",
            design.get(
                "prompt",
                ""
            )
        )


        print(
            "🚨 OBJECT ID DESIGN:",
            id(design)
        )


        print(
            "🚨 DESIGN ARCH BEFORE ANY CHANGE:",
            design.get("architectural_intent")
        )



        print(
            "🔥 RUNTIME RECEIVED DESIGN:",
            design
        )



        print(
            "🔥 RUNTIME RECEIVED ARCH INTENT:",
            design.get(
                "architectural_intent",
                {}
            )
        )



        render_id = int(
            time.time()
        )


        # ==================================================
        # TEXT_TO_IMAGE_COMFY_03 — PRESET RESOLUTION
        #
        # Explicit request parameter > deterministic inference from
        # the user's own wording > safe default. Never an LLM call.
        # ==================================================

        preset = self._resolve_request_preset(
            design
        )

        print(
            "🎛️ RENDER PRESET:",
            preset.get("name"),
            "| source:",
            preset.get("source"),
            "| reason:",
            preset.get("reason")
        )


        # ==================================================
        # IMAGE_TO_IMAGE_05 — DRAFT / PREVIEW PROFILE
        #
        # Off by default. Acceptance scripts opt in so functional
        # validation does not spend final-quality render time.
        # ==================================================

        # PROJECT_WORKSPACE_UI_06 — an explicit per-request render
        # profile (from the workspace quality selector or chat intent)
        # takes precedence over the environment switch.
        profile_resolution = resolve_render_profile(
            explicit=design.get("render_profile")
        )

        if profile_resolution.get("active"):

            draft = {

                "contract": profile_resolution.get("contract"),
                "version": profile_resolution.get("version"),

                # Only DRAFT/PREVIEW are functional test profiles.
                "draft": bool(profile_resolution.get("test_profile")),

                "steps": profile_resolution.get("steps"),

                "profile": profile_resolution.get("name"),
                "preview_long_edge": profile_resolution.get("long_edge"),
                "production_resolution": profile_resolution.get(
                    "production_resolution"
                ),
            }

        else:

            draft = render_draft_profile(
                explicit=design.get("draft")
            )

        print(
            "🧪 RENDER DRAFT MODE:",
            draft.get("draft"),
            "| steps:",
            draft.get("steps"),
            "| profile:",
            draft.get("profile")
        )


        seed = render_id


        # --------------------------------------------------
        # SEED PRECEDENCE  (TEXT_TO_IMAGE_COMFY_03B)
        #   1. explicit request seed
        #   2. preset fixed seed
        #   3. time-derived (existing behaviour, unchanged)
        #
        # An explicit request seed lets two renders differ ONLY by
        # preset, which is how preset lighting semantics are isolated.
        # --------------------------------------------------

        requested_seed = design.get("seed")

        if requested_seed is not None:

            try:

                seed = int(requested_seed)

                print(
                    "🎲 REQUEST SEED:",
                    seed
                )

            except (TypeError, ValueError):

                print(
                    "⚠️ INVALID REQUEST SEED IGNORED:",
                    requested_seed
                )

        elif (
            preset.get("seed_mode") == "fixed"
            and preset.get("seed") is not None
        ):

            seed = int(
                preset.get("seed")
            )

            print(
                "🎲 PRESET FIXED SEED:",
                seed
            )



        design[

            "render_id"

        ] = render_id



        design[

            "seed"

        ] = seed



        # --------------------------------------------------
        # NORMALIZE MODE
        # --------------------------------------------------


        mode = design.get(
            "mode"
        )



        if (
            image_bindings
            or (
                image_asset
                and image_asset.get("filename")
            )
        ):


            mode = "img2img"



        elif mode not in [

            "img2img",

            "text2img"

        ]:


            mode = "text2img"



        design[

            "mode"

        ] = mode



        print(
            "🖼️ IMAGE ASSET RECEIVED:",
            image_asset
        )


        print(
            "🔥 RENDER MODE:",
            mode
        )
        # --------------------------------------------------
        # ARCHITECTURAL INTENT PRESERVATION
        # --------------------------------------------------


        existing_intent = design.get(
            "architectural_intent",
            {}
        )


        print(
            "🚨 DEBUG EXISTING ARCH INTENT:",
            existing_intent
        )



        if isinstance(
            existing_intent,
            dict
        ) and existing_intent:


            print(
                "🧠 EXISTING ARCHITECTURAL INTENT PRESERVED"
            )


            # IMPORTANT:
            # never mutate original handler payload

            intent_data = existing_intent.copy()



        elif mode == "img2img":


            print(
                "🖼️ IMAGE EDIT SEMANTIC INTENT EXTRACTION"
            )



            user_text = (

                design.get(
                    "prompt",
                    ""
                )

                or

                design.get(
                    "text",
                    ""
                )

            )



            intent_data = self.semantic_intent.extract(
                user_text
            )



            print(
                "SEMANTIC IMAGE INTENT:",
                intent_data
            )



            if not intent_data:


                intent_data = self.image_edit_intent.extract(
                    design
                )


                print(
                    "🔥 RENDER IMAGE EDIT INTENT:",
                    intent_data
                )



        else:


            if existing_intent:


                print(
                    "🧠 USING IMAGE TOOL INTENT"
                )


                intent_data = existing_intent


            else:


                print(
                    "🔥 RENDER INTENT EXTRACTION:",
                    design
                )


                intent_data = self.intent.extract(
                    design
                )


        # --------------------------------------------------
        # NORMALIZE INTENT
        # --------------------------------------------------

        if not isinstance(
            intent_data,
            dict
        ):


            intent_data = {}



        # --------------------------------------------------
        # FORCE MODE PRESERVATION
        # --------------------------------------------------


        intent_data["mode"] = mode



        if mode == "img2img":


            intent_data[

                "preserve_geometry"

            ] = True



            intent_data[

                "request_type"

            ] = "facade_material_edit"



            intent_data[

                "camera"

            ] = "same as original image"




        # --------------------------------------------------
        # MERGE ARCHITECTURAL INTENT
        # --------------------------------------------------


        previous_intent = design.get(
            "architectural_intent",
            {}
        )



        if isinstance(
            previous_intent,
            dict
        ) and previous_intent:


            print(
                "🧠 MERGING EXISTING ARCHITECTURAL INTENT"
            )



            merged_intent = previous_intent.copy()



            for key, value in intent_data.items():


                if key in [

                    "building_type",

                    "style",

                    "materials",

                    "objects",

                    "environment",

                    "camera",

                    "mood"

                ]:


                    if key in previous_intent:


                        old = previous_intent[key]


                        if (

                            old

                            and old != []

                            and old != ""

                        ):


                            continue



                if (

                    value is not None

                    and value != ""

                    and value != []

                    and value != {}

                    and str(value).lower()
                        not in [

                            "unknown",

                            "none",

                            "building"

                        ]

                ):

                    merged_intent[key] = value


            intent_data = merged_intent




        design[

            "architectural_intent"

        ] = intent_data


        # --------------------------------------------------
        # SHARED FACADE KNOWLEDGE
        # --------------------------------------------------
        # Resolve once, after route-specific intent normalization and before
        # either prompt builder runs.  Mode/workflow selection remains fully
        # route-specific.

        resolved_facade = self.resolve_shared_facade_knowledge(
            intent_data
        )




        print(
            "🔥 PRESERVED FINAL INTENT:",
            intent_data
        )



        # --------------------------------------------------
        # PROMPT BUILDER CONTEXT
        # --------------------------------------------------


        prompt_input = {


            "prompt":

                design.get(
                    "prompt",
                    ""
                ),



            "architectural_intent":

                intent_data,



            "design_context":

                {


                    "project_id":

                        project_id,



                    "mode":

                        mode,



                    "image_asset":

                        image_asset,



                    "design":

                        design

                }


        }




        print(
            "RENDER INPUT PROMPT TYPE:",
            type(
                prompt_input.get(
                    "prompt"
                )
            )
        )



        print(
            "RENDER INPUT PROMPT:",
            prompt_input.get(
                "prompt"
            )
        )



        print(
            "🧠 FINAL INTENT TO PROMPT:",
            intent_data
        )


        print(
            "🔥 DESIGN PROMPT BEFORE RUNTIME BUILDER:",
            design.get("prompt")
        )

        print(
            "🔥 EXISTING BUILT PROMPT:",
            design.get("architectural_intent", {}).get("built_prompt")
        )



        # FINAL_SAMPLER_AUTHORITY_FIX_V1 — the chat/render handoff already
        # carries two existing authority contracts for a resolved T2I turn:
        # the compiled architectural prompt consumed by
        # ``resolve_render_prompt`` and the bounded RenderConstraintBlockV1.
        # Re-running PromptBuilder in that state reconstructed hard properties
        # from an incomplete projection of intent (missing floors became one)
        # and flattened ontology metadata into competing style requirements.
        #
        # Skip that reconstruction only when BOTH existing carriers are valid
        # and non-empty.  This avoids trusting ``design['prompt']`` and avoids
        # manually joining strings: the existing resolver below remains the
        # sole composer.  Legacy/direct requests without the full handoff and
        # every image-edit mode retain the historical builder path.
        _compiled_handoff = design.get("compiled_render_prompt")
        _instruction_handoff = design.get("architectural_instruction")

        _authoritative_t2i_handoff = (
            mode == "text2img"
            and (
                isinstance(_compiled_handoff, str)
                and bool(_compiled_handoff.strip())
                or isinstance(_compiled_handoff, dict)
                and any(
                    bool(str(_compiled_handoff.get(key) or "").strip())
                    for key in ("positive_prompt", "description", "prompt")
                )
            )
            and isinstance(_instruction_handoff, dict)
            and _instruction_handoff.get("contract") == "RenderConstraintBlockV1"
            and bool(
                str(
                    _instruction_handoff.get("constraint_block")
                    or _instruction_handoff.get("english_instruction")
                    or ""
                ).strip()
            )
        )

        if _authoritative_t2i_handoff:

            prompt = ""

            print(
                "🧭 AUTHORITATIVE T2I HANDOFF: second builder pass skipped"
            )

        else:

            prompt = self.prompt_builder.build(
                prompt_input,
                mode=mode
            )

        self.last_render_request["authoritative_t2i_handoff"] = (
            _authoritative_t2i_handoff
        )

        self.last_render_request["builder_reconstruction_skipped"] = (
            _authoritative_t2i_handoff
        )



        print(
            "📝 BUILT IMAGE PROMPT:",
            prompt
        )
        print(
            "🚨 FINAL PROMPT TYPE:",
            type(prompt)
        )


        print(
            "🚨 FINAL PROMPT CONTENT:",
            prompt
        )



        if isinstance(
            prompt,
            dict
        ):


            prompt = prompt.get(
                "description",
                ""
            )



        elif not isinstance(
            prompt,
            str
        ):


            prompt = str(
                prompt
            )



        print(
            "FINAL NORMALIZED PROMPT:",
            prompt
        )



        # --------------------------------------------------
        # COMPILED ARCHITECTURAL PROMPT CONSUMPTION
        #
        # CHAT_LANGUAGE_02
        #
        # The compiled English architectural prompt must actually be
        # CONSUMED here.  Previously it only existed in session context,
        # because PromptBuilder rebuilds the prompt from
        # architectural_intent and discards any incoming prompt string.
        #
        # When no compiled prompt is supplied this is a no-op and the
        # previous behaviour is preserved byte for byte.
        # --------------------------------------------------

        prompt_resolution = resolve_render_prompt(

            compiled_prompt=design.get(
                "compiled_render_prompt"
            ),

            builder_prompt=prompt,

            user_text=(
                design.get("original_prompt")
                or design.get("prompt")
                or ""
            ),

            # TEXT_TO_IMAGE_COMFY_03 — selected preset quality tail.
            # Purely lighting / quality language: it never restates
            # building type, style, material, camera or day/night.
            preset_tail=build_preset_quality_tail(
                preset.get("name")
            ),

            # TEXT_TO_IMAGE_COMFY_03B — preset intent is authoritative.
            # Only CONFLICTING generic builder filler is removed; the
            # compiled architectural prompt is never filtered.
            preset_name=preset.get("name"),

            # IMAGE_TO_IMAGE_05 — the edit delta is authoritative for
            # img2img, so its conflict terms are merged with the preset
            # ones. The generic img2img builder tail is a
            # text-to-image facade/daylight template and would otherwise
            # contradict the requested delta ("Natural lighting" on a
            # night edit).
            conflict_terms=(
                tuple(preset_tail_conflicts(preset.get("name")))
                + tuple(design.get("edit_conflict_terms") or ())
            ),

            reinforcement=preset_tail_reinforcement(
                preset.get("name")
            ),

            # RENDER_INSTRUCTION_HANDOFF_V1 — the bounded A/B constraint block
            # (geometry shape, target preservation, temporary-object rules).
            # Absent for every turn without an A/B instruction, in which case
            # the resolved prompt is byte-identical to the previous behaviour.
            architectural_instruction=design.get(
                "architectural_instruction"
            ),

        )


        prompt = prompt_resolution.get(
            "prompt"
        ) or prompt


        print(
            "🔥 RENDER PROMPT SOURCE:",
            prompt_resolution.get("source")
        )

        print(
            "🔥 RENDER PROMPT CONSUMED BY RUNTIME:",
            prompt
        )


        self.last_render_request["resolved_prompt"] = prompt

        self.last_render_request["prompt_source"] = (
            prompt_resolution.get("source")
        )

        self.last_render_request["compiled_consumed"] = (
            prompt_resolution.get("compiled_consumed")
        )

        # RENDER_INSTRUCTION_HANDOFF_V1 — log what actually reached the
        # sampler: the block, its size and whether the budget cut it.
        self.last_render_request["architectural_instruction"] = (
            prompt_resolution.get("instruction_block")
        )

        self.last_render_request["architectural_instruction_chars"] = (
            prompt_resolution.get("instruction_chars")
        )

        self.last_render_request["architectural_instruction_truncated"] = (
            prompt_resolution.get("instruction_truncated")
        )

        if prompt_resolution.get("instruction_applied"):

            print(
                "🧭 RENDER CONSTRAINTS APPLIED:",
                prompt_resolution.get("instruction_chars"),
                "chars | truncated:",
                prompt_resolution.get("instruction_truncated"),
            )

        self.last_render_request["preset"] = preset.get("name")

        self.last_render_request["preset_source"] = preset.get("source")



        # --------------------------------------------------
        # WORKFLOW SELECTION
        # --------------------------------------------------


        workflow_context = {


            "engine":

                engine,



            "mode":

                mode,



            "image":

                image_asset,



            # FACADE-04D.2 — explicit dual-image signal for the selector.
            # `image` (IMAGE B) is still supplied, so single-image behaviour
            # is unchanged when no bindings are present.
            "dual_image":

                bool(image_bindings),

            "image_bindings":

                image_bindings,

            # FACADE-04D.3B-2 — explicit opt-in. Absent/False keeps the
            # accepted FACADE-04D.2 workflow.
            "conditioned":

                bool(conditioned),

            # KNOWLEDGE_RECOVERY_01 — explicit opt-in for the GPU-verified
            # FLUX.1 Kontext instruction-edit graph. Absent/False keeps
            # every existing route byte for byte.
            "kontext_edit":

                bool(kontext_edit),

            # EXISTING_VISUAL_KNOWLEDGE_USO_V1 — explicit opt-in for the USO
            # reference-conditioned text-to-image graph. Absent/None keeps
            # every existing route byte for byte.
            "uso_reference":

                bool(uso_reference),

            # V22_HIGHRISE_NIGHT_ROUTING_V1 — explicit mode opt-in. The
            # selector resolves it to the BASE graph; the mode builder
            # below configures that graph.
            "v22_mode":

                v22_mode or None

        }



        workflow_name = self.selector.select(
            workflow_context
        )



        if not workflow_name:


            return {


                "status":

                    "unknown_workflow",


                "engine":

                    engine,


                "mode":

                    mode

            }




        # ==================================================
        # EXISTING_VISUAL_KNOWLEDGE_USO_V1 — REFERENCE BINDING GATE (FAIL CLOSED)
        #
        # A reference-guided render without a bound reference is not a weaker
        # render, it is a different render. It is refused here so it can never
        # degrade into a plain text-to-image prompt that silently ignores the
        # user's reference. Contradictory opt-ins are refused too rather than
        # resolved by precedence.
        # ==================================================

        if uso_reference:

            if kontext_edit or image_bindings or conditioned or image_asset:

                print("⛔ USO RENDER BLOCKED: conflicting render opt-ins")

                return {

                    "status": "uso_reference_conflicts_with_edit",

                    "engine": engine,

                    "mode": mode,

                    "workflow": workflow_name,

                    "conflicts": {
                        "kontext_edit": bool(kontext_edit),
                        "image_bindings": bool(image_bindings),
                        "conditioned": bool(conditioned),
                        "image_asset": bool(image_asset),
                    }

                }

            if not isinstance(uso_reference, dict) or not uso_reference.get("filename"):

                print("⛔ USO RENDER BLOCKED: no reference asset bound")

                return {

                    "status": "uso_reference_requires_binding",

                    "engine": engine,

                    "mode": mode,

                    "workflow": workflow_name

                }


        # ==================================================
        # FACADE-04D.3B-2 — CONDITIONED RENDER GATE (FAIL CLOSED)
        #
        # Real USO style + ControlNet geometry conditioning is OPT-IN. When it
        # is requested it must NEVER degrade into an unconditioned or a
        # text-to-image render: a missing dual-image binding or a missing
        # conditioning model aborts the request.
        # ==================================================

        if conditioned:

            from core.render import dual_image_conditioning_v1 as _cond

            if not image_bindings:

                print("⛔ CONDITIONED RENDER BLOCKED: dual-image binding required")

                return {

                    "status": "conditioning_requires_dual_binding",

                    "engine": engine,

                    "mode": mode,

                    "conditioning": {
                        "contract": _cond.CONTRACT,
                        "conditioning_wired": False,
                        "conditioning_runtime_verified": False,
                        "conditioning_effect_verified": False,
                        "reason": "conditioning_requires_dual_binding",
                    }

                }

            _model_report = _cond.verify_conditioning_models()

            _conditioning = _cond.conditioning_trace(None, _model_report)

            if _model_report.get("status") != "ready":

                print(
                    "⛔ CONDITIONED RENDER BLOCKED: conditioning models unavailable",
                    _conditioning.get("models_missing"),
                    _conditioning.get("models_invalid")
                )

                return {

                    "status": "conditioning_models_missing",

                    "engine": engine,

                    "mode": mode,

                    "conditioning": _conditioning

                }




        print(
            "🔎 LOAD WORKFLOW:",
            workflow_name
        )




        loaded = self.loader.load(
            workflow_name
        )



        if loaded.get(
            "status"
        ) != "loaded":


            return loaded



        workflow = loaded.get(
            "workflow"
        )




        # ==================================================
        # V22_HIGHRISE_NIGHT_ROUTING_V1 — MODE CONFIGURATION
        #
        # `build_mode_specific_stage2_workflow()` is the ONE owner of
        # the v22 mode contract: it attaches the ControlNet branch when
        # the base graph has none, and it writes the mode's denoise,
        # strength and start/end percent onto the graph. It is applied
        # HERE — after load, before any verification and before the
        # injectors — so the graph that is verified and submitted is
        # the graph the mode configured.
        #
        # Fail closed, three ways:
        #   * the ControlNet asset is checked with the SAME verified
        #     spec the conditioned route uses (`verify_conditioning_models`);
        #     a missing asset aborts instead of submitting a graph whose
        #     ControlNetLoader would fail on the server;
        #   * a graph that cannot carry the branch raises
        #     MissingControlNetNodeError, which aborts;
        #   * an unknown mode raises ValueError, which aborts.
        # None of these degrade into an unconditioned render.
        # ==================================================

        _v22_trace = None

        if v22_mode:

            from core.render.experimental.architectos_v22_highrise_night_v1 import (
                build_mode_specific_stage2_workflow,
                MissingControlNetNodeError,
            )

            from core.render import dual_image_conditioning_v1 as _v22_cond

            _v22_models = _v22_cond.verify_conditioning_models()

            _v22_controlnet_ready = bool(
                (_v22_models.get("present") or {}).get("geometry_controlnet")
            )

            if not _v22_controlnet_ready:

                print(
                    "⛔ V22 RENDER BLOCKED: ControlNet asset unavailable"
                )

                return {

                    "status": "v22_controlnet_unavailable",

                    "engine": engine,

                    "mode": mode,

                    "workflow": workflow_name,

                    "v22_mode": v22_mode

                }

            try:

                _v22_seed = int(design.get("seed") or 123456789)

            except (TypeError, ValueError):

                _v22_seed = 123456789

            try:

                workflow = build_mode_specific_stage2_workflow(

                    workflow,

                    v22_mode,

                    str(
                        design.get("compiled_render_prompt")
                        or design.get("prompt")
                        or ""
                    ),

                    str(design.get("negative_prompt") or ""),

                    _v22_seed,

                    control_image_name=v22_control_image,

                    source_image_name=v22_source_image

                )

            except MissingControlNetNodeError as _v22_error:

                print(
                    "⛔ V22 RENDER BLOCKED: graph cannot carry ControlNet",
                    _v22_error
                )

                return {

                    "status": "v22_graph_invalid",

                    "engine": engine,

                    "mode": mode,

                    "workflow": workflow_name,

                    "v22_mode": v22_mode,

                    "reason": str(_v22_error)

                }

            except ValueError as _v22_error:

                print(
                    "⛔ V22 RENDER BLOCKED: unsupported mode",
                    _v22_error
                )

                return {

                    "status": "v22_mode_invalid",

                    "engine": engine,

                    "mode": mode,

                    "workflow": workflow_name,

                    "v22_mode": v22_mode,

                    "reason": str(_v22_error)

                }

            # The builder stamps the mode onto the graph for traceability.
            # ComfyUI's POST /prompt accepts node objects only, and
            # `_architectos_runtime` is the only key the HTTP layer strips,
            # so this stamp must not travel with the graph. The mode is
            # recorded in `_v22_trace` instead.
            workflow = strip_v22_graph_metadata(workflow)

            _v22_trace = {

                "mode": v22_mode,

                "control_image": v22_control_image,

                "source_image": v22_source_image,

                "controlnet_asset": _v22_models.get("present", {}).get(
                    "geometry_controlnet"
                )

            }

            print(
                "🏙️ V22 MODE APPLIED:",
                v22_mode
            )




        # ==================================================
        # FACADE-04D.3B-2 — STATIC CONDITIONED-GRAPH VERIFICATION
        #
        # The wiring is verified BEFORE anything can be submitted. A graph that
        # is not wired correctly aborts the request; it is never silently
        # downgraded to the unconditioned or text-to-image path.
        #
        # This proves WIRING ONLY. `conditioning_runtime_verified` and
        # `conditioning_effect_verified` stay False.
        # ==================================================

        if conditioned:

            from core.render import dual_image_conditioning_v1 as _cond

            _graph_report = _cond.verify_conditioning_graph(workflow)

            _conditioning = _cond.conditioning_trace(_graph_report, _model_report)

            if _graph_report.get("status") != "wired":

                print(
                    "⛔ CONDITIONED RENDER BLOCKED: graph not wired",
                    _graph_report.get("errors")
                )

                return {

                    "status": "conditioning_graph_invalid",

                    "engine": engine,

                    "mode": mode,

                    "workflow": workflow_name,

                    "conditioning": _conditioning

                }




        # --------------------------------------------------
        # EXISTING_VISUAL_KNOWLEDGE_USO_V1 — STATIC USO GRAPH VERIFICATION
        #
        # Verified BEFORE anything can be submitted. A graph that is not the
        # reference-conditioned text-to-image graph aborts the request; it is
        # never silently downgraded to a plain text-to-image render or to an
        # img2img variation of the reference.
        #
        # This proves WIRING ONLY — never that the reference influenced the
        # pixels.
        # --------------------------------------------------

        if uso_reference:

            from core.render import uso_reference_handoff_v1 as _uso

            _uso_graph_report = _uso.verify_uso_graph(workflow)

            if not _uso_graph_report.get("ok"):

                print(
                    "⛔ USO RENDER BLOCKED: graph contract not satisfied",
                    _uso_graph_report.get("errors")
                )

                return {

                    "status": "uso_graph_invalid",

                    "engine": engine,

                    "mode": mode,

                    "workflow": workflow_name,

                    "uso_graph": _uso_graph_report

                }


        # --------------------------------------------------
        # FULL RENDER CONTEXT
        # --------------------------------------------------


        render_context = {


            "render_id":

                render_id,



            "seed":

                seed,



            # TEXT_TO_IMAGE_COMFY_03 — preset-controlled render params.
            # None values are ignored by the injector, so a request with
            # no preset keeps the workflow's own values.
            "width":

                preset.get("width"),

            "height":

                preset.get("height"),

            "steps":

                (
                    draft.get("steps")
                    if draft.get("draft")
                    else preset.get("steps")
                ),



            # IMAGE_TO_IMAGE_05 — draft/preview flag (metadata only)
            "draft_mode":

                bool(draft.get("draft")),



            # IMAGE_TO_IMAGE_05 — deterministic edit strength.
            # Only meaningful for img2img; ignored otherwise.
            #
            # KNOWLEDGE_RECOVERY_01 — the Kontext instruction-edit graph is
            # NOT strength-driven: it starts from EmptySD3LatentImage and
            # carries the source ONLY through ReferenceLatent, so its
            # denoise is fixed at 1.0 by the graph. Injecting a preservation
            # denoise here would partially denoise a zero latent and degrade
            # the verified configuration, so it is deliberately withheld for
            # this route (the injector already ignores a None value).
            # V22_HIGHRISE_NIGHT_ROUTING_V1 — the mode owns denoise. The
            # builder above wrote the mode's value onto the sampler, so the
            # injector must not overwrite it with the caller's preservation
            # level (the same reason Kontext and USO withhold it).
            "denoise":

                (
                    None
                    if (kontext_edit or uso_reference or v22_mode)
                    else design.get("denoise")
                ),

            # KNOWLEDGE_RECOVERY_01 — the Kontext instruction-edit graph
            # wires ConditioningZeroOut(CLIPTextEncode) as its negative and
            # runs at cfg=1, so it consumes NO negative conditioning. An
            # explicit empty string is passed so the injector does not write
            # a negative the graph would silently discard. The request's
            # negative constraints are preserved in the architectural
            # planning/validation layer and the unsupported conditioning is
            # reported rather than implied.
            "negative_prompt":

                (
                    ""
                    if kontext_edit
                    else None
                ),



            "mode":

                mode,



            "engine":

                engine,



            "architectural_intent":

                intent_data,



            "project_id":

                project_id



        }




        print(
            "🔥 FULL RENDER CONTEXT:",
            render_context
        )




        # --------------------------------------------------
        # WORKFLOW INJECTION
        # --------------------------------------------------



        if (
            (image_asset or image_bindings)
            and (mode == "img2img" or engine == "wan" or kontext_edit)
        ):


            print(
                "🖼️ IMG2IMG WORKFLOW ACTIVE"
            )



            print(
                "🖼️ IMG2IMG SOURCE ASSET:",
                image_asset
            )



            injected = self.image_injector.inject(

                workflow,

                prompt,

                image_asset,

                render_context,

                # FACADE-04D.2 — explicit role/node-id binding. When absent
                # (every legacy caller) the injector keeps its historical
                # single-asset behaviour byte for byte.
                image_bindings=image_bindings,

                # KNOWLEDGE_RECOVERY_01 — caller-supplied mask for the
                # Kontext instruction-edit graph. None for every existing
                # caller, which leaves the workflow untouched.
                mask_asset=mask_asset

            )



        else:


            print(
                "🎨 TEXT2IMG WORKFLOW ACTIVE"
            )



            injected = self.workflow_injector.inject(

                workflow,

                prompt,

                render_context

            )



        # ==================================================
        # FACADE-04D.3C-3 — PROMPT INJECTION FAIL-CLOSED GATE
        #
        # If the conditioning graph could not be resolved to its CLIPTextEncode
        # terminals, the injected graph still carries the workflow's template
        # prompt. Submitting it would render the wrong instruction, so the
        # request is refused here and never silently degraded.
        # ==================================================

        if (
            isinstance(injected, dict)
            and injected.get("status") == "blocked"
        ):

            print(
                "⛔ RENDER BLOCKED: prompt injection could not resolve conditioning"
            )

            return {

                "status": "prompt_injection_blocked",

                "engine": engine,

                "mode": mode,

                "workflow": workflow_name,

                "prompt_injection": injected.get("prompt_injection")

            }



        # --------------------------------------------------
        # EXISTING_VISUAL_KNOWLEDGE_USO_V1 — BIND THE REFERENCE
        #
        # The reference is written to the graph's single LoadImage node AFTER
        # prompt injection, so the compiled text constraints and the visual
        # reference are bound in the same submission. A bind failure aborts the
        # render: the graph's placeholder filename is never submitted.
        # --------------------------------------------------

        if uso_reference:

            from core.render import uso_reference_handoff_v1 as _uso

            _uso_bind = _uso.bind_reference(

                injected.get("workflow"),

                uso_reference.get("filename")

            )

            if not _uso_bind.get("ok"):

                print(
                    "⛔ USO RENDER BLOCKED: reference bind failed",
                    _uso_bind.get("error")
                )

                return {

                    "status": "uso_reference_bind_failed",

                    "engine": engine,

                    "mode": mode,

                    "workflow": workflow_name,

                    "uso_binding": _uso_bind

                }

            injected["uso_reference_binding"] = _uso_bind

            self.last_uso_reference = uso_reference

            print(
                "🖼️ USO REFERENCE BOUND:",
                _uso_bind.get("node_id"),
                _uso_bind.get("filename")
            )


        print(
            "🔥 WORKFLOW AFTER INJECTION:",
            injected
        )
        # --------------------------------------------------
        # EXECUTION ENGINE
        # --------------------------------------------------


        # WAN is installed as a ComfyUI workflow, so it must use the real
        # Comfy HTTP executor instead of the legacy placeholder connector.
        runtime_engine = "comfyui" if engine in ("flux", "wan") else engine



        print(
            "🚨 BEFORE EXECUTOR:",
            injected
        )


        print(
            "🚨 EXECUTOR TYPE:",
            runtime_engine
        )



        # FIX:
        # payload was undefined in v7.3
        # use design instead


        print(
            "🔥 FINAL DESIGN PAYLOAD:",
            design
        )


        print(
            "🔥 FINAL ARCH INTENT:",
            design.get(
                "architectural_intent",
                {}
            )
        )


        print(
            "🚀 EXECUTOR WILL START"
        )


        print(
            "🚀 EXECUTOR WORKFLOW TYPE:",
            type(
                injected.get("workflow")
            )
            if isinstance(injected, dict)
            else type(injected)
        )


        print(
            "========== WORKFLOW CONTRACT DEBUG =========="
            )

        print(
            "INJECTED TYPE:",
            type(injected)
        )

        print(
            "INJECTED KEYS:",
            injected.keys()
            if isinstance(injected, dict)
            else None
        )

        if isinstance(injected, dict):

            workflow_debug = injected.get(
                "workflow",
                {}
            )

            print(
                "WORKFLOW TYPE:",
                type(workflow_debug)
            )

            if isinstance(workflow_debug, dict):

                print(
                    "WORKFLOW NODE COUNT:",
                    len(workflow_debug)
                )

                print(
                    "WORKFLOW NODE IDS:",
                    list(workflow_debug.keys())
                )

        print(
            "PROMPT SENT TO WORKFLOW:",
            prompt
        )

        print(
            "MODE:",
            mode
        )

        print(
            "ENGINE:",
            engine
        )

        print(
            "============================================="
        )



        # ==================================================
        # FACADE-04D.3C-5B.1 — PROTECTED RENDERING PERIOD (RACE A)
        #
        # Everything above that calls a model has already run: the image
        # handler's semantic-intent extraction AND this runtime's own
        # `semantic_intent.extract()` (the mode == "img2img" branch). That is
        # exactly why H2 does NOT live in the image handler: placing it there
        # let this runtime reload qwen3.8:27b immediately after H2 had unloaded
        # it. The GPU is handed over to the FLUX/ComfyUI stack HERE.
        #
        # 1. The cross-process `gpu_render` lease is taken EXCLUSIVELY. Every
        #    ArchitectOS Ollama inference needs it, so no chat, vision,
        #    teaching or coder request can reload a model into the same
        #    ~16 GiB while the render owns the GPU. H2 releasing its own model
        #    lease did NOT provide this.
        # 2. H2 then unloads the vision model UNDER that lease, so the unload
        #    cannot be undone by a later inference.
        # 3. The lease is held across the executor and released in `finally`,
        #    so it is released on success, failure, timeout and exception.
        #
        # Scoped to every render that loads the FLUX/ComfyUI stack and can
        # therefore collide with a resident Ollama model.
        #
        # V4.3D — the previous predicate was `image_bindings or conditioned`,
        # which only the dual-image and conditioned callers set. Single-image
        # I2I and Kontext supply `image_asset` instead, so they ran with no
        # lease and no H2: a concurrent chat/vision request could reload
        # qwen3.8:27b (12.44 GiB) while FLUX was sampling. `image_asset` is the
        # signal those paths DO set and is None for pure text-to-image, so T2I
        # behaviour is unchanged by this extension.
        # ==================================================

        # ==================================================
        # V4.3F — ORPHAN GATE
        #
        # If a previous request could not prove its ComfyUI job stopped, the
        # lease is still owned by this runtime. No new GPU work may start —
        # not a render, and (through the lease) not an Ollama load — until the
        # queue stops listing that job. Recovery happens here, before any new
        # acquisition, so the check cannot be skipped by a caller.
        # ==================================================

        if not self._recover_orphaned_render():

            print(
                "⛔ RENDER BLOCKED: previous ComfyUI job state unconfirmed"
            )

            return {

                "status": "gpu_handoff_orphaned",

                "reason": "previous_job_state_unconfirmed",

                "engine": engine,

                "mode": mode,

                "workflow": workflow_name,

                "prompt_id": self._orphaned_prompt_id,

                "gpu_handoff_render": self.last_gpu_handoff_render,

            }


        _render_guard = None

        # V4.3F — `engine == "flux"` closes the last unprotected path.
        #
        # V4.3D extended this predicate with `image_asset` so single-image I2I
        # and Kontext were covered, but text-to-image supplies none of the
        # three signals and still ran with no lease, no H2 and no VRAM gate
        # while loading the same FLUX graph.
        #
        # `engine` is the right discriminator: `runtime_engine` above maps
        # ("flux", "wan") -> "comfyui", every FLUX call site passes "flux", and
        # the WAN i2v call site passes "wan". So this selects exactly the paths
        # that load the FLUX stack and leaves WAN on its previous behaviour —
        # WAN must not inherit the FLUX-specific 11 GiB floor.
        if image_bindings or conditioned or image_asset or engine == "flux":

            # ==================================================
            # AUTHORITY_HANDOFF_V1 — PRE-DISPATCH GEOMETRY GATE
            #
            # A geometric operation that the same request explicitly forbids,
            # or a geometric request whose authorisation could not be
            # established, must not reach the GPU. This runs BEFORE the lease,
            # before H2 and before the VRAM gate, so a blocked request performs
            # no GPU action at all.
            #
            # This is a policy gate on the INSTRUCTION. It makes no claim that
            # a permitted instruction preserves geometry.
            # ==================================================

            _authority_gate = None
            _authority_blocking = ()
            _authority_failed = None

            try:

                from core.prompt_intelligence.geometry_authority_handoff_v1 import (
                    resolve_geometry_authority as _resolve_authority,
                    STATUS_CONFLICT as _AUTH_CONFLICT,
                    STATUS_UNRESOLVED as _AUTH_UNRESOLVED,
                )

                _authority_blocking = (_AUTH_CONFLICT, _AUTH_UNRESOLVED)

                _intent_for_authority = design.get("architectural_intent") or {}

                _authority_gate = _resolve_authority(
                    (),
                    preserve_geometry=bool(
                        _intent_for_authority.get("preserve_geometry", True)
                    ),
                    preserve_constraints=(
                        _intent_for_authority.get("preserve_constraints") or ()
                    ),
                    user_text=(
                        _intent_for_authority.get("normalized_prompt")
                        or design.get("prompt")
                        or ""
                    ),
                    edit_class=(design.get("edit_delta") or {}).get("edit_class"),
                )

            except BaseException as _authority_exc:

                # FAIL-CLOSED. The resolver is pure CPU — no I/O, no GPU, no
                # model (geometry_authority_handoff_v1.py:29) — so a raise here
                # means import, signature or logic is broken. Treating that as
                # "no verdict" used to fall through to dispatch and send an
                # unchecked geometric instruction to the GPU, because the block
                # test below only fires on a dict carrying a blocking status.
                # A failed resolver is an UNRESOLVED authorisation, not an
                # admissible request. The request is refused before the lease.
                _authority_failed = _authority_exc
                _authority_gate = None

            if _authority_failed is not None:

                _authority_failure = {
                    "contract": "GeometryAuthorityHandoffV1",
                    "status": "geometric_authorization_unresolved",
                    "resolver_error": "%s: %s" % (
                        type(_authority_failed).__name__,
                        _authority_failed,
                    ),
                }

                self.last_gpu_handoff_render = {
                    "status": "geometry_authority_blocked",
                    "reason": "authority_resolver_failed",
                    "geometry_authority": _authority_failure,
                }

                print(
                    "⛔ RENDER BLOCKED: geometry authority resolver failed",
                    type(_authority_failed).__name__,
                )

                return {
                    "status": "geometry_authority_blocked",
                    "reason": "authority_resolver_failed",
                    "engine": engine,
                    "mode": mode,
                    "workflow": workflow_name,
                    "geometry_authority": _authority_failure,
                }

            if (
                isinstance(_authority_gate, dict)
                and _authority_gate.get("status") in _authority_blocking
            ):

                self.last_gpu_handoff_render = {
                    "status": "geometry_authority_blocked",
                    "reason": _authority_gate.get("status"),
                    "geometry_authority": _authority_gate,
                }

                print(
                    "⛔ RENDER BLOCKED: geometry authority",
                    _authority_gate.get("status"),
                )

                return {
                    "status": "geometry_authority_blocked",
                    "reason": _authority_gate.get("status"),
                    "engine": engine,
                    "mode": mode,
                    "workflow": workflow_name,
                    "geometry_authority": _authority_gate,
                }

            from core.runtime.gpu_handoff_v1 import (
                gpu_render_lease,
                unload_ollama_models_for_render,
                require_render_vram,
                CONTRACT as _GPU_CONTRACT,
                VERSION as _GPU_VERSION,
            )

            self.last_gpu_handoff_render = {
                "contract": _GPU_CONTRACT,
                "version": _GPU_VERSION,
                "stage": "protected_render_period",
                "status": None,
                "reason": None,
            }

            _render_guard = gpu_render_lease()

            if not _render_guard.acquire():

                print(
                    "⛔ RENDER BLOCKED: protected GPU render lease unavailable"
                )

                self.last_gpu_handoff_render["status"] = "blocked"
                self.last_gpu_handoff_render["reason"] = "render_lease_unavailable"

                return {

                    "status": "gpu_handoff_blocked",

                    "reason": "render_lease_unavailable",

                    "engine": engine,

                    "mode": mode,

                    "workflow": workflow_name,

                    "gpu_handoff_h2": None,

                }

            self.last_gpu_handoff_render["status"] = "acquired"

            try:

                _h2 = unload_ollama_models_for_render()

            except BaseException:

                _render_guard.release()

                raise

            self.last_gpu_handoff_h2 = _h2

            print(
                "🧮 GPU HANDOFF H2:",
                _h2.get("status"),
                "|",
                _h2.get("reason"),
                "| ownership:",
                _h2.get("ownership"),
                "| unloaded:",
                _h2.get("unloaded"),
                "| skipped_in_use:",
                _h2.get("skipped_in_use"),
            )

            if _h2.get("status") not in ("unloaded", "not_loaded", "not_running"):

                print(
                    "⛔ RENDER BLOCKED: GPU handoff H2",
                    _h2.get("reason"),
                )

                self.last_gpu_handoff_render["status"] = "blocked"
                self.last_gpu_handoff_render["reason"] = (
                    "gpu_handoff_h2_" + str(_h2.get("reason"))
                )

                _render_guard.release()

                return {

                    "status": "gpu_handoff_blocked",

                    "reason": "gpu_handoff_h2_" + str(_h2.get("reason")),

                    "engine": engine,

                    "mode": mode,

                    "workflow": workflow_name,

                    "gpu_handoff_h2": _h2,

                }

            # ==================================================
            # V4.3D — VRAM PREFLIGHT (fail closed)
            #
            # The lease proves exclusive ownership; it does NOT prove the
            # card can hold the graph. Measured on this machine: a resident
            # qwen3.8:27b leaves 2.23 GiB of 15.98 GiB, while the FLUX fp8
            # workflow needs ~11 GB. Submitting in that state is the exact
            # condition the driver bugcheck may have come from.
            #
            # The value comes from H2's own measurement (bytes) when
            # available; otherwise one /system_stats read. Unmeasurable
            # BLOCKS — never "assume it is fine".
            # ==================================================

            _vram = require_render_vram(_h2)

            self.last_gpu_handoff_render["vram"] = _vram

            print(
                "🧮 RENDER VRAM PREFLIGHT:",
                _vram.get("reason"),
                "| free_mib:",
                _vram.get("free_mib"),
                "| min_mib:",
                _vram.get("min_free_mib"),
                "| source:",
                _vram.get("measurement_source"),
            )

            if not _vram.get("ok"):

                # V4.3G — one controlled recovery attempt, then the SAME gate.
                # The threshold is untouched: recovery may only make the
                # measurement pass, never lower the bar it must pass.
                _reclaim = self._reclaim_idle_comfyui_cache(_vram)

                self.last_gpu_handoff_render["vram_release"] = _reclaim

                print(
                    "🧯 COMFY CACHE RECLAIM:",
                    _reclaim.get("status"),
                    "|",
                    _reclaim.get("reason"),
                )

                if _reclaim.get("status") == "released":

                    # Re-measure real free VRAM. H1's `released` verdict alone
                    # is never treated as proof of sufficiency.
                    #
                    # V4.3G.1 — pass None, not `_h2`. `require_render_vram()`
                    # prefers a numeric `h2_trace["vram_free_after"]` over any
                    # live read, and H2's snapshot was taken BEFORE the release.
                    # Re-passing `_h2` therefore re-applied the stale pre-release
                    # measurement, so recovery could never admit a render no
                    # matter how much H1 freed. `None` is not a dict: it skips
                    # the H2 branch, forces a fresh `/system_stats` read, labels
                    # the source `comfyui_system_stats`, and still fails closed
                    # (`vram_unmeasured`) when the card cannot be read. The
                    # threshold and the gate itself are unchanged.
                    _vram = require_render_vram(None)

                    self.last_gpu_handoff_render["vram"] = _vram

                    print(
                        "🧮 RENDER VRAM PREFLIGHT (post-release):",
                        _vram.get("reason"),
                        "| free_mib:",
                        _vram.get("free_mib"),
                    )

            if not _vram.get("ok"):

                print(
                    "⛔ RENDER BLOCKED: VRAM preflight",
                    _vram.get("reason"),
                )

                self.last_gpu_handoff_render["status"] = "blocked"
                self.last_gpu_handoff_render["reason"] = _vram.get("reason")

                _render_guard.release()

                return {

                    "status": "gpu_handoff_blocked",

                    "reason": _vram.get("reason"),

                    "engine": engine,

                    "mode": mode,

                    "workflow": workflow_name,

                    "gpu_handoff_h2": _h2,

                    "vram": _vram,

                }

        # ==================================================
        # V4.3F — RELEASE ONLY ON A CONFIRMED TERMINAL STATE
        #
        # `completed`, `execution_error`, `submit_error` and a confirmed
        # `timeout` / `timeout_cancelled` all mean ComfyUI is not executing
        # this prompt, so releasing is safe. `timeout_unconfirmed` means the
        # opposite: the job may still be sampling. Releasing there is the
        # defect this phase exists to remove, so the guard is parked instead.
        #
        # An exception or a missing prompt id is ambiguous: if a lifecycle
        # channel exists, the queue is consulted before giving up the lease.
        # If no channel exists at all (a stub executor), there is nothing to
        # consult and the previous behaviour is kept.
        # ==================================================

        _execution_status = None
        _execution_prompt_id = None
        _raised = False

        # ==================================================
        # REAL_SAMPLING_PROGRESS_B_PLUS — WEBSOCKET LISTENER
        #
        # A per-render WebSocket listener is opened BEFORE submission
        # so it is ready to receive the first progress event the
        # moment ComfyUI starts sampling. The listener is scoped to
        # this render's prompt_id (captured in the _publish_submitted
        # callback) and identifies sampler nodes from the ACTUAL
        # submitted workflow — never guessed.
        #
        # If the WebSocket fails to connect, the existing poll-based
        # lifecycle continues unchanged. The listener is a daemon
        # thread, so it never blocks the render or its cleanup.
        # ==================================================

        _ws_client_id = make_client_id()
        _ws_listener = None
        _sampler_node_ids = frozenset()

        try:

            _submitted_workflow = injected.get("workflow")

            if isinstance(_submitted_workflow, dict):
                _sampler_node_ids = sampler_node_ids(_submitted_workflow)

        except Exception:
            _sampler_node_ids = frozenset()

        # ==================================================
        # CORRECTION — THE LISTENER MUST BE READY BEFORE SUBMIT
        #
        # ComfyUI routes progress to the client_id that is CONNECTED at
        # the time the event fires. Opening the socket lazily inside the
        # worker thread meant the first steps could be emitted before the
        # handshake finished. `start()` now blocks until the handshake
        # resolves and returns True only on a real connection; the
        # submission happens after this point.
        #
        # Nothing is opened when the render has no verified owner: an
        # unowned record is never published, so a socket would be waste.
        # A failed handshake is reported honestly (ready=False) and the
        # render continues on the existing poll-based lifecycle.
        # ==================================================

        # ==================================================
        # EXECUTOR_CONTROL_FLOW_RECOVERY_V3 — TWO SEPARATE TRY BLOCKS
        #
        # The listener setup is optional telemetry and must never abort
        # the render, so it gets its own narrow handler. The submission
        # below must run on the NORMAL path: it previously sat inside the
        # listener's `except` handler, so `execution` was only assigned
        # when the listener setup FAILED — the happy path raised
        # UnboundLocalError at the first read of `execution`.
        #
        # Nesting the telemetry handler inside the submission try keeps
        # the existing `except BaseException` / `finally` (lease release,
        # listener stop, active-render clear) covering BOTH, exactly as
        # before, while guaranteeing submission is unreachable only by
        # exception.
        # ==================================================

        try:

            try:

                _comfy_endpoint = getattr(
                    getattr(self.executor, "comfy", None),
                    "endpoint",
                    None,
                )

                if _comfy_endpoint and _owner_project_id:

                    _ws_url = build_ws_url(
                        _comfy_endpoint, _ws_client_id
                    )

                    _ws_listener = ComfyProgressListener(
                        _ws_url,
                        prompt_id="",  # bound in _publish_submitted
                        client_id=_ws_client_id,
                        sampler_node_ids=_sampler_node_ids,
                    )

                    if not _ws_listener.start():
                        # Honest fallback: no sampling progress this render.
                        print(
                            "⚠️ SAMPLING PROGRESS UNAVAILABLE:",
                            (_ws_listener.stats() or {}).get("last_error")
                        )
                        _ws_listener.stop()
                        _ws_listener = None

            except Exception as _ws_error:

                print(
                    "⚠️ SAMPLING PROGRESS SETUP FAILED:",
                    type(_ws_error).__name__,
                    _ws_error
                )

                _ws_listener = None

            # ==================================================
            # REAL_RENDER_LIFECYCLE_V1 — PUBLISH THE REAL JOB ID
            #
            # Called by the executor the moment ComfyUI returns a valid
            # prompt id, i.e. BEFORE `wait_for_result()` blocks. The record
            # is scoped to THIS invocation by `_generation` and to the
            # requesting project by `_owner_project_id`.
            #
            # REAL_SAMPLING_PROGRESS_B_PLUS — the WebSocket listener's
            # prompt_id filter is set here, and sampler_node_ids are
            # published so the status endpoint can report verified
            # sampling steps.
            # ==================================================

            def _publish_submitted(_prompt_id):

                if not _owner_project_id:

                    return

                # Bind the listener to this prompt_id so it only
                # processes events for THIS render. bind_prompt_id
                # refuses an empty id, so binding can never widen the
                # filter to "accept anything".
                if _ws_listener is not None:
                    _ws_listener.bind_prompt_id(_prompt_id)

                self._progress_listener = _ws_listener

                self._publish_active_render({

                    "prompt_id":
                        str(_prompt_id),

                    "project_id":
                        str(_owner_project_id),

                    "generation":
                        _generation,

                    "engine":
                        engine,

                    "workflow":
                        workflow_name,

                    "submitted_at":
                        time.time(),

                    "client_id":
                        _ws_client_id,

                    "sampler_node_ids":
                        sorted(_sampler_node_ids),

                })

            execution = self.executor.execute(

                injected[

                    "workflow"

                ],

                runtime_engine,

                on_submitted=_publish_submitted,

                client_id=_ws_client_id

            )

            if isinstance(execution, dict):

                _execution_status = execution.get("status")
                _execution_prompt_id = execution.get("prompt_id")

        except BaseException:

            _raised = True

            raise

        finally:

            if _render_guard is not None:

                _retain = False

                # Statuses that say "a submission happened, but its outcome is
                # not established". These are the only ones where a job may
                # exist without us knowing.
                _may_be_executing = _execution_status in (
                    "timeout_unconfirmed",
                    "missing_prompt_id",
                )

                if _may_be_executing or _raised:

                    _proved, _detail = self._prove_no_active_job(
                        _execution_prompt_id
                    )

                    if not _proved:

                        # V4.3F closeout — a missing queue reader must not be
                        # read as "idle".
                        #
                        # Previously this also required a reader to exist, so a
                        # submitted job whose timeout could not be confirmed was
                        # RELEASED whenever the executor had no queue channel —
                        # i.e. the one case where the state is least known
                        # released the lock. If the status itself says a
                        # submission happened, retention no longer depends on
                        # being able to observe it.
                        #
                        # An executor EXCEPTION is different: it is not evidence
                        # that anything was submitted, and with no channel at
                        # all there would be nothing to observe and no way to
                        # ever recover, so the previous reader-gated behaviour
                        # is kept for that case only.
                        if _may_be_executing or self._comfy_lifecycle() is not None:

                            _retain = True

                if _retain:

                    self._retain_orphaned_render(
                        _render_guard,
                        _execution_prompt_id,
                        _execution_status or "executor_exception"
                    )

                else:

                    _render_guard.release()



            # ==================================================
            # REAL_RENDER_LIFECYCLE_V1 — THIS INVOCATION IS OVER
            #
            # Whatever the outcome, this invocation no longer owns a job.
            # Guarded by generation so a newer render's record is never
            # cleared by an older one finishing late.
            # ==================================================

            # REAL_SAMPLING_PROGRESS_B_PLUS — stop the WebSocket
            # listener on ALL terminal paths. This is the single
            # cleanup point: success, failure, cancellation, and
            # exception all reach this finally.
            #
            # stop() performs a real close handshake and returns False
            # if the worker did not exit within the join budget. That
            # is reported rather than hidden: a listener that cannot be
            # stopped must not be described as cleaned up.

            if _ws_listener is not None:
                try:
                    if not _ws_listener.stop():
                        print(
                            "⚠️ SAMPLING LISTENER STOP INCOMPLETE:",
                            (_ws_listener.stats() or {})
                        )
                except Exception as _stop_error:
                    print(
                        "⚠️ SAMPLING LISTENER STOP FAILED:",
                        type(_stop_error).__name__,
                        _stop_error
                    )

            if (
                self.active_render is not None
                and self.active_render.get("generation") == _generation
            ):

                self._clear_active_render(_generation)

            # `_clear_active_render` re-checks the generation, so a late
            # finish from an older render is a no-op there as well.



        # Any retained guard means this request gave up ownership without proof
        # that the job stopped — not just `timeout_unconfirmed`. A lost prompt
        # id is equally unconfirmed, and reporting it as a normal envelope
        # would hide that the next render is already blocked.
        if self._orphaned_render_guard is not None:

            _orphan_reason = (
                "prompt_id_lost"
                if _execution_status == "missing_prompt_id"
                else "job_state_unconfirmed"
            )

            self.last_gpu_handoff_render["status"] = "orphaned"
            self.last_gpu_handoff_render["reason"] = _orphan_reason
            self.last_gpu_handoff_render["prompt_id"] = _execution_prompt_id

            print(
                "⛔ RENDER ORPHANED: ComfyUI job not confirmed stopped"
            )

            return {

                "status": "gpu_handoff_orphaned",

                "reason": _orphan_reason,

                "engine": engine,

                "mode": mode,

                "workflow": workflow_name,

                "prompt_id": _execution_prompt_id,

                "gpu_handoff_render": self.last_gpu_handoff_render,

            }



        print(
            "🔥 WORKFLOW EXECUTION RESULT:",
            execution
        )




        # --------------------------------------------------
        # RESULT CONTEXT
        # --------------------------------------------------


        result_context = {


            "project_id":

                project_id,



            "render_id":

                render_id,



            "engine":

                engine,



            "workflow":

                workflow_name,



            "prompt":

                prompt,



            "architectural_intent":

                intent_data,



            "design":

                design,



            "execution":

                execution

        }




        resolved_result = self.result_bridge.resolve(
            result_context
        )



        print(
            "🚨 RESULT BRIDGE OUTPUT:",
            resolved_result
        )



        print(
            "🖼️ RESOLVED IMAGE RESULT:",
            resolved_result
        )


        # --------------------------------------------------
        # FINAL IMAGE ASSET RESOLUTION
        # --------------------------------------------------

        final_image_asset = image_asset


        if not final_image_asset:

            if isinstance(
                resolved_result,
                dict
            ):

                final_image_asset = (
                    resolved_result.get(
                        "image_asset"
                    )
                    or
                    resolved_result.get(
                        "image"
                    )
                )


        print(
            "🖼️ FINAL IMAGE ASSET:",
            final_image_asset
        )




        # --------------------------------------------------
        # FINAL RESPONSE
        # --------------------------------------------------


        # RUNTIME_FOUNDATION_01:
        # status must reflect the real execution outcome.
        render_status = self._resolve_render_status(
            execution,
            resolved_result
        )


        print(
            "📌 RENDER RUNTIME FINAL STATUS:",
            render_status
        )


        # --------------------------------------------------
        # TEXT_TO_IMAGE_COMFY_03 — REQUEST METADATA
        # --------------------------------------------------

        effective_params = self._workflow_render_params(
            injected.get("workflow")
            if isinstance(injected, dict)
            else None
        )


        output_asset = None

        if isinstance(resolved_result, dict):

            output_asset = (
                resolved_result.get("image_asset")
                or resolved_result.get("image")
            )


        request_metadata = {

            "contract": "RenderRequestMetadataV1",

            "preset": preset.get("name"),
            "preset_source": preset.get("source"),
            "preset_reason": preset.get("reason"),
            "preset_tags": preset.get("tags"),

            "final_prompt": prompt,

            "workflow_name": workflow_name,

            "seed": seed,

            "width": effective_params.get("width"),
            "height": effective_params.get("height"),
            "steps": effective_params.get("steps"),

            "prompt_source": prompt_resolution.get("source"),

            # TEXT_TO_IMAGE_COMFY_03B — preset-aware tail filtering trace
            "removed_conflicting_tail_terms": prompt_resolution.get(
                "removed_conflicting_tail_terms"
            ),

            "removed_conflicting_tail_segments": prompt_resolution.get(
                "removed_conflicting_tail_segments"
            ),

            "retained_builder_tail": prompt_resolution.get(
                "retained_builder_tail"
            ),

            "preset_reinforcement": prompt_resolution.get(
                "preset_reinforcement"
            ),

            # IMAGE_TO_IMAGE_05 — preservation contract + injected strength
            "edit_preservation": design.get("preservation"),

            # IMAGE_TO_IMAGE_05 — edit-delta conflict terms requested by
            # the chat route (before segment filtering).
            "edit_conflict_terms": list(
                design.get("edit_conflict_terms") or ()
            ),

            "denoise": effective_params.get("denoise"),

            # V22_HIGHRISE_NIGHT_ROUTING_V1 — which mode configured the
            # submitted graph, and from which control/source assets. None
            # for every render that did not opt in.
            "v22": _v22_trace,

            # IMAGE_TO_IMAGE_05 — draft/preview indicator
            "draft_mode": bool(draft.get("draft")),

            "draft_steps": draft.get("steps") if draft.get("draft") else None,

            # IMAGE_TO_IMAGE_05 — render profile (DRAFT/PREVIEW/QUALITY/FINAL)
            "render_profile": (
                profile_resolution.get("name") or draft.get("profile")
            ),

            "render_profile_active": bool(
                profile_resolution.get("active") or draft.get("draft")
            ),

            "render_profile_production_resolution": (
                profile_resolution.get("production_resolution")
            ),

            # IMAGE_TO_IMAGE_05 — truthful img2img capability contract.
            # Derived from the actual workflow graph + model files.
            "edit_capability": (
                image_edit_capability_flags(
                    os.path.join(
                        self.loader.base_path,
                        workflow_name,
                    )
                )
                if str(design.get("mode")) == "img2img"
                else None
            ),

            # IMAGE_TO_IMAGE_05 — test-render preview provenance.
            # The original source remains the authoritative asset.
            "source_preview": (
                {
                    "original_source_path": image_asset.get(
                        "original_source_path"
                    ),
                    "working_preview_path": image_asset.get(
                        "working_preview_path"
                    ),
                    "original_dimensions": image_asset.get(
                        "original_dimensions"
                    ),
                    "working_dimensions": image_asset.get(
                        "working_dimensions"
                    ),
                    "test_profile": image_asset.get("test_profile"),
                }
                if isinstance(image_asset, dict)
                else None
            ),

            "output_asset": output_asset,

            "output_asset_exists": (
                output_asset.get("exists")
                if isinstance(output_asset, dict)
                else None
            ),

            "execution_status": (
                execution.get("status")
                if isinstance(execution, dict)
                else None
            ),

            # EXISTING_VISUAL_KNOWLEDGE_USO_V1 — reference lineage. Present
            # only for the USO reference-guided route; None everywhere else.
            "uso_reference": uso_reference if uso_reference else None,
            "uso_reference_binding": (
                injected.get("uso_reference_binding")
                if isinstance(injected, dict)
                else None
            ),

            "status": render_status,

            # RENDER_INSTRUCTION_HANDOFF_V1 — trace the bounded constraint
            # block that reached the sampler, its size and truncation state.
            "architectural_instruction": prompt_resolution.get(
                "instruction_block"
            ),
            "architectural_instruction_chars": prompt_resolution.get(
                "instruction_chars"
            ),
            "architectural_instruction_truncated": prompt_resolution.get(
                "instruction_truncated"
            ),

        }


        print(
            "🧾 RENDER REQUEST METADATA:",
            request_metadata
        )


        self.last_render_metadata = request_metadata


        return {


            "project_id":

                project_id,



            "render_id":

                render_id,



            "seed":

                seed,



            "workflow":

                workflow_name,



            "mode":

                mode,



            "engine":

                engine,



            "prompt":

                prompt,



            "architectural_intent":

                intent_data,



            "design":

                design,



            "image_asset":

                final_image_asset,


            # FACADE-04D.2 — role-aware dual-image binding trace
            # (IMAGE A -> its own node, IMAGE B -> node 300). None for
            # every single-image / text-to-image render.
            "image_bindings":

                image_bindings,


            # FACADE-04D.3B-2 — conditioning trace. None unless the
            # conditioned graph was explicitly requested. `conditioning_wired`
            # proves graph wiring only; runtime and effect verification stay
            # False until a supervised live render.
            "conditioning":

                _conditioning,


            # EXISTING_VISUAL_KNOWLEDGE_USO_V1 — reference lineage. Present
            # only for the USO reference-guided route; None everywhere else.
            # Records reference id, source digest, model, workflow and prompt.
            "uso_reference":

                uso_reference if uso_reference else None,

            "uso_reference_binding":

                (
                    injected.get("uso_reference_binding")
                    if isinstance(injected, dict)
                    else None
                ),


            "injected":

                injected,



            "execution":

                execution,



            "resolved":

                resolved_result,



            # CHAT_LANGUAGE_02 - provenance of the prompt actually used
            "prompt_resolution":

                prompt_resolution,



            # TEXT_TO_IMAGE_COMFY_03 - preset + render request metadata
            "preset":

                preset.get("name"),


            "request_metadata":

                request_metadata,



            "status":

                render_status

        }
