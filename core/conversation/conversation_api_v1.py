# ==========================================================
# ArchitectOS Conversation API v1
#
# PHASE 08 — read/observe surface for the teaching foundation.
#
# Additive only.  This blueprint does NOT create an assistant: it
# exposes the ONE teaching foundation that the canonical ChatArchitect
# already uses, so the acceptance runner can prove contracts against a
# real runtime path.
#
# No endpoint here renders, calls ComfyUI or generates images.
# ==========================================================


from __future__ import annotations


from flask import Blueprint, jsonify, request


from core.conversation.teaching_foundation_v1 import teaching_foundation

from core.conversation.teaching_candidate_v1 import (
    ALLOWED_STATUSES,
    PERMANENT_LEARNING_IMPLEMENTED,
)

from core.conversation.conversation_language_v1 import (
    project_language_record,
    resolve_conversation_language,
)

from core.conversation.execution_boundary_v1 import describe as boundary

from core.conversation.interruption_audit_v1 import audit as interruption

from core.conversation.turn_semantics_v1 import (
    classify_turn,
    ALL_TURN_KINDS,
    teaching_aspects,
    TEACHING_INTENT,
)

# PHASE 09 — architectural learning bridge (read + promotion preparation)
from core.conversation.knowledge_read_bridge_v1 import (
    knowledge_read_bridge,
)

from core.conversation.knowledge_promotion_bridge_v1 import (
    knowledge_promotion_bridge,
)

from core.conversation.teaching_storage_guard_v1 import (
    teaching_storage_guard,
)

from core.conversation.teaching_meaning_v1 import (
    ALL_KNOWLEDGE_CLASSES,
    ALL_SCOPES,
    ALL_PROVENANCES,
)


CONTRACT = "ConversationApiV1"
VERSION = "1.0"


def create_conversation_blueprint():

    api = Blueprint("architectos_conversation_api", __name__)

    # ======================================================
    # STATUS
    # ======================================================

    @api.route("/api/conversation/status", methods=["GET"])
    def conversation_status():

        project_id = request.args.get("project_id")

        return jsonify({

            "status": "success",

            "contract": CONTRACT,
            "version": VERSION,

            **teaching_foundation.status(project_id),

            "allowed_statuses": list(ALLOWED_STATUSES),

            "turn_kinds": list(ALL_TURN_KINDS),

            "language": project_language_record(project_id),

            "execution_boundary": boundary(),
        })

    # ======================================================
    # TURN SEMANTICS (pure classification, nothing persisted)
    # ======================================================

    @api.route(
        "/api/conversation/turn-semantics",
        methods=["POST"],
    )
    def conversation_turn_semantics():

        data = request.get_json(silent=True) or {}

        text = data.get("text") or data.get("message") or ""

        return jsonify({

            "status": "success",

            "contract": CONTRACT,

            "persisted": False,

            "result": classify_turn(
                text,
                language=data.get("language"),
            ),
        })

    # ======================================================
    # OBSERVE (classify + record candidate, no assistant call)
    # ======================================================

    @api.route(
        "/api/conversation/observe",
        methods=["POST"],
    )
    def conversation_observe():

        data = request.get_json(silent=True) or {}

        text = data.get("text") or data.get("message") or ""

        project_id = data.get("project_id") or data.get("session_id")

        observation = teaching_foundation.observe_turn(

            text,

            raw_text=text,

            session_id=project_id,

            context={
                "input_type": data.get("input_type") or "text",
                "stt_language": data.get("stt_language"),
                "reply_language": data.get("language"),
            },

            input_type=data.get("input_type") or "text",
        )

        return jsonify({

            "status": "success",

            "contract": CONTRACT,

            "render_requested": False,
            "comfy_invoked": False,
            "image_generation": False,

            "observation": observation,
        })

    # ======================================================
    # TEACH-BACK
    # ======================================================

    @api.route("/api/conversation/teach-back", methods=["GET", "POST"])
    def conversation_teach_back():

        if request.method == "POST":

            data = request.get_json(silent=True) or {}

        else:

            data = dict(request.args)

        project_id = data.get("project_id")

        language = data.get("language")

        if not language:

            language = resolve_conversation_language(
                project_id=project_id,
                persist=False,
            ).get("language")

        return jsonify({

            "status": "success",

            "contract": CONTRACT,

            "permanent_learning_implemented": (
                PERMANENT_LEARNING_IMPLEMENTED
            ),

            "result": teaching_foundation.teach_back(
                project_id=project_id,
                language=language,
            ),
        })

    # ======================================================
    # CANDIDATES
    # ======================================================

    @api.route("/api/conversation/candidates", methods=["GET"])
    def conversation_candidates():

        project_id = request.args.get("project_id")

        return jsonify({

            "status": "success",

            "contract": CONTRACT,

            "project_id": project_id,

            "allowed_statuses": list(ALLOWED_STATUSES),

            "permanent_learning_implemented": False,

            "learned_count": teaching_foundation.learned_count(
                project_id
            ),

            "count": len(teaching_foundation.candidates(project_id)),

            "candidates": teaching_foundation.candidates(
                project_id,
                status=request.args.get("status"),
                domain=request.args.get("domain"),
            ),
        })

    # ======================================================
    # EXECUTION BOUNDARY (08G)
    # ======================================================

    @api.route(
        "/api/conversation/execution-boundary",
        methods=["GET"],
    )
    def conversation_execution_boundary():

        return jsonify({

            "status": "success",

            "contract": CONTRACT,

            "result": boundary(),
        })

    # ======================================================
    # INTERRUPTION AUDIT (08F, read-only)
    # ======================================================

    @api.route(
        "/api/conversation/interruption-audit",
        methods=["GET"],
    )
    def conversation_interruption_audit():

        return jsonify({

            "status": "success",

            "contract": CONTRACT,

            "result": interruption(),
        })

    # ======================================================
    # LANGUAGE (08E)
    # ======================================================

    @api.route("/api/conversation/language", methods=["GET", "POST"])
    def conversation_language():

        if request.method == "POST":

            data = request.get_json(silent=True) or {}

            project_id = data.get("project_id")

            decision = resolve_conversation_language(

                project_id=project_id,

                explicit=data.get("language"),

                text=data.get("text"),

                stt_language=data.get("stt_language"),

                persist=True,
            )

        else:

            project_id = request.args.get("project_id")

            decision = resolve_conversation_language(

                project_id=project_id,

                text=request.args.get("text"),

                stt_language=request.args.get("stt_language"),

                persist=bool(request.args.get("text")),
            )

        return jsonify({

            "status": "success",

            "contract": CONTRACT,

            "project_id": project_id,

            "decision": decision,

            "stored": project_language_record(project_id),
        })

    # ======================================================
    # PHASE 09 — ARCHITECTURAL LEARNING BRIDGE
    # ======================================================

    @api.route("/api/conversation/knowledge/sources", methods=["GET"])
    def conversation_knowledge_sources():

        """READ-ONLY provenance of the existing architectural corpus."""

        return jsonify({

            "status": "success",

            "contract": CONTRACT,

            "read_only": True,

            "writes_performed": 0,

            "result": knowledge_read_bridge.read_report(),
        })

    @api.route("/api/conversation/knowledge/spaces", methods=["GET"])
    def conversation_knowledge_spaces():

        zone = request.args.get("zone")

        spaces = knowledge_read_bridge.spaces(zone)

        return jsonify({

            "status": "success",

            "contract": CONTRACT,

            "read_only": True,

            "zone": zone,

            "zones": knowledge_read_bridge.space_zones(),

            "count": len(spaces),

            "spaces": spaces,
        })

    @api.route("/api/conversation/knowledge/patterns", methods=["GET"])
    def conversation_knowledge_patterns():

        return jsonify({

            "status": "success",

            "contract": CONTRACT,

            "read_only": True,

            "positive_count": len(knowledge_read_bridge.patterns()),

            "negative_count": len(
                knowledge_read_bridge.negative_patterns()
            ),

            "patterns": knowledge_read_bridge.patterns(),

            "negative_patterns": (
                knowledge_read_bridge.negative_patterns()
            ),
        })

    @api.route("/api/conversation/knowledge/lookup", methods=["GET"])
    def conversation_knowledge_lookup():

        return jsonify({

            "status": "success",

            "contract": CONTRACT,

            "read_only": True,

            "term": request.args.get("term"),

            "result": knowledge_read_bridge.lookup_term(
                request.args.get("term"),
                language=request.args.get("language"),
            ),
        })

    @api.route(
        "/api/conversation/knowledge/promotion/status",
        methods=["GET"],
    )
    def conversation_promotion_status():

        return jsonify({

            "status": "success",

            "contract": CONTRACT,

            "result": knowledge_promotion_bridge.status(
                request.args.get("project_id")
            ),
        })

    @api.route(
        "/api/conversation/knowledge/promotion/validate",
        methods=["POST"],
    )
    def conversation_promotion_validate():

        data = request.get_json(silent=True) or {}

        project_id = data.get("project_id")

        candidate = None

        if data.get("candidate_id"):

            candidate = teaching_foundation.store.get(
                project_id, data.get("candidate_id")
            )

        elif isinstance(data.get("candidate"), dict):

            candidate = data.get("candidate")

        if candidate is None:

            return jsonify({
                "status": "error",
                "error": "candidate_not_found",
            }), 404

        return jsonify({

            "status": "success",

            "contract": CONTRACT,

            "promotion_implemented": False,

            "validation": knowledge_promotion_bridge.validate_candidate(
                candidate, project_id=project_id
            ),
        })

    @api.route(
        "/api/conversation/knowledge/promotion/request",
        methods=["POST"],
    )
    def conversation_promotion_request():

        data = request.get_json(silent=True) or {}

        result = knowledge_promotion_bridge.request_promotion(

            data.get("candidate_id"),

            data.get("project_id"),

            target_registry=data.get("target_registry"),

            requested_by=data.get("requested_by") or "human",

            note=data.get("note"),
        )

        return jsonify({

            "status": result.get("status"),

            "contract": CONTRACT,

            "promotion_implemented": False,

            "result": result,
        })

    @api.route(
        "/api/conversation/knowledge/storage-guard",
        methods=["GET"],
    )
    def conversation_storage_guard():

        project_id = request.args.get("project_id")

        return jsonify({

            "status": "success",

            "contract": CONTRACT,

            "result": teaching_storage_guard.audit(
                [project_id] if project_id else None
            ),
        })

    @api.route(
        "/api/conversation/knowledge/taxonomy",
        methods=["GET"],
    )
    def conversation_taxonomy():

        return jsonify({

            "status": "success",

            "contract": CONTRACT,

            "knowledge_classes": list(ALL_KNOWLEDGE_CLASSES),

            "scopes": list(ALL_SCOPES),

            "provenances": list(ALL_PROVENANCES),

            "teaching_intent_kind": TEACHING_INTENT,

            "teaching_aspects": teaching_aspects("fa"),

            "promotion_implemented": False,
        })

    # ======================================================
    # PHASE 10 — SPACE TYPES + ADJACENCY INTELLIGENCE
    #
    # Read-only curriculum surfaces. No endpoint renders.
    # ======================================================

    @api.route("/api/conversation/curriculum/status", methods=["GET"])
    def conversation_curriculum_status():

        from core.curriculum.space_types_v1 import space_types

        from core.curriculum.adjacency_model_v1 import adjacency_model

        from core.curriculum.privacy_logic_v1 import privacy_logic

        from core.curriculum.space_curriculum_v1 import space_curriculum

        return jsonify({

            "status": "success",
            "contract": CONTRACT,

            "space_types": space_types.report(),
            "adjacency": adjacency_model.report(),
            "privacy": privacy_logic.report(),
            "curriculum": space_curriculum.report(),

            "render_requested": False,
            "comfy_invoked": False,
        })

    @api.route("/api/conversation/curriculum/spaces", methods=["GET"])
    def conversation_curriculum_spaces():

        from core.curriculum.space_types_v1 import space_types

        category = request.args.get("category")

        spaces = (
            space_types.by_category(category) if category
            else space_types.spaces()
        )

        return jsonify({

            "status": "success",
            "contract": CONTRACT,

            "read_only": True,

            "count": len(spaces),

            "categories": space_types.categories(),

            "spaces": spaces,
        })

    @api.route("/api/conversation/curriculum/space", methods=["GET"])
    def conversation_curriculum_space():

        from core.curriculum.space_types_v1 import space_types

        term = request.args.get("term") or request.args.get("space_id")

        # Resolve through the SHARED alias table FIRST, so a bare term
        # ("bedroom", "اتاق خواب") reaches the richer curriculum record
        # even when the frozen ontology also carries a flatter record
        # under that literal id. An explicit id still resolves as a
        # fallback, so no existing caller loses its lookup.
        space_id = space_types.find(term) or (
            term if space_types.space(term) else None
        )

        return jsonify({

            "status": "success",
            "contract": CONTRACT,

            "term": term,
            "space_id": space_id,

            "space": space_types.space(space_id) if space_id else None,
        })

    @api.route("/api/conversation/curriculum/relations", methods=["GET"])
    def conversation_curriculum_relations():

        from core.curriculum.adjacency_model_v1 import adjacency_model

        from core.curriculum.space_types_v1 import space_types

        term = request.args.get("term")

        relation_type = request.args.get("relation_type")

        space_id = space_types.find(term) if term else None

        return jsonify({

            "status": "success",
            "contract": CONTRACT,

            "read_only": True,

            "space_id": space_id,

            "count": len(
                adjacency_model.relations(
                    space_id, relation_type=relation_type
                )
            ),

            "relations": adjacency_model.relations(
                space_id, relation_type=relation_type
            ),
        })

    @api.route("/api/conversation/curriculum/relation", methods=["GET"])
    def conversation_curriculum_relation():

        from core.curriculum.adjacency_model_v1 import adjacency_model

        source = request.args.get("source")
        target = request.args.get("target")

        return jsonify({

            "status": "success",
            "contract": CONTRACT,

            "relation": adjacency_model.relation_between(source, target),

            "explanation": adjacency_model.explain(
                request.args.get("source_id"),
                request.args.get("target_id"),
                language=request.args.get("language") or "en",
            ),
        })

    @api.route("/api/conversation/curriculum/query", methods=["POST"])
    def conversation_curriculum_query():

        """Space + relationship reasoning (curriculum Part 6 A/B/C)."""

        from core.curriculum.space_query_v1 import space_query

        data = request.get_json(silent=True) or {}

        text = data.get("text") or data.get("message") or ""

        return jsonify({

            "status": "success",
            "contract": CONTRACT,

            "render_requested": False,
            "comfy_invoked": False,

            "result": space_query.analyze(
                text, language=data.get("language")
            ),
        })

    @api.route("/api/conversation/curriculum/privacy", methods=["GET"])
    def conversation_curriculum_privacy():

        from core.curriculum.privacy_logic_v1 import privacy_logic

        from core.curriculum.space_types_v1 import space_types

        source = space_types.find(request.args.get("source"))
        target = space_types.find(request.args.get("target"))

        if not source or not target:

            return jsonify({
                "status": "error",
                "error": "space_not_resolved",
                "source": source,
                "target": target,
            }), 404

        return jsonify({

            "status": "success",
            "contract": CONTRACT,

            "evaluation": privacy_logic.evaluate(source, target),
        })

    # ======================================================
    # CURRICULUM FOUNDATION FIX — CURRICULUM SEQUENCER
    #
    # ORDER ONLY. There are no lessons, nothing is persisted and nothing
    # is learned. The caller may pass progress as query parameters
    # (step=status pairs) to see the plan from a given point; the
    # sequencer never stores it.
    # ======================================================

    @api.route("/api/conversation/curriculum/sequence", methods=["GET"])
    def conversation_curriculum_sequence():

        from core.curriculum.curriculum_sequencer_v1 import (
            curriculum_sequencer,
            STEP_KEYS,
        )

        # Only the known step keys (plus `language`) are accepted. An
        # unknown parameter is REFUSED rather than ignored: silently
        # dropping `?not_a_step=completed` would report a valid plan for
        # progress the caller never actually expressed.
        allowed = set(STEP_KEYS) | {"language"}

        unknown = sorted(
            arg for arg in request.args.keys() if arg not in allowed
        )

        progress = {}

        for key in STEP_KEYS:

            value = request.args.get(key)

            if value:

                progress[key] = value

        validation = curriculum_sequencer.validate_progress(progress)

        if unknown or not validation["valid"]:

            return jsonify({
                "status": "error",
                "error": "invalid_progress",
                "unknown_parameters": unknown,
                "validation": validation,
            }), 400

        language = request.args.get("language") or "en"

        return jsonify({

            "status": "success",
            "contract": CONTRACT,

            "render_requested": False,
            "comfy_invoked": False,

            "sequence": curriculum_sequencer.sequence(language),

            "plan": curriculum_sequencer.plan(progress, language),

            "validation": validation,

            "report": curriculum_sequencer.report(),
        })

    # ======================================================
    # PHASE 11 — BUBBLE DIAGRAM INTELLIGENCE
    #
    # Semantic spatial diagrams only. No geometry, no coordinates,
    # no rendering. Every endpoint is read-only with respect to the
    # corpus and never invokes ComfyUI.
    # ======================================================

    @api.route("/api/conversation/diagram/status", methods=["GET"])
    def conversation_diagram_status():

        from core.curriculum.bubble_diagram_v1 import (
            bubble_diagram_builder,
        )

        from core.curriculum.zone_model_v1 import zone_model

        from core.curriculum.site_intent_v1 import site_intent

        from core.curriculum.spatial_case_reasoning_v1 import (
            spatial_case_reasoning,
        )

        from core.curriculum.diagram_curriculum_v1 import (
            diagram_curriculum,
        )

        return jsonify({

            "status": "success",
            "contract": CONTRACT,

            "diagram": bubble_diagram_builder.report(),
            "zones": zone_model.report(),
            "site": site_intent.report(),
            "case_reasoning": spatial_case_reasoning.report(),
            "curriculum": diagram_curriculum.report(),

            "render_requested": False,
            "comfy_invoked": False,
            "geometry_generated": False,
        })

    @api.route("/api/conversation/diagram/generate", methods=["POST"])
    def conversation_diagram_generate():

        """SPACE + RELATIONSHIP -> semantic bubble diagram."""

        from core.curriculum.bubble_diagram_v1 import (
            bubble_diagram_builder,
        )

        data = request.get_json(silent=True) or {}

        requirement = (
            data.get("requirement")
            or data.get("text")
            or data.get("message")
            or ""
        )

        diagram = bubble_diagram_builder.build(

            requirement,

            site_text=data.get("site"),

            language=data.get("language"),

            project_id=data.get("project_id"),
        )

        return jsonify({

            "status": "success",
            "contract": CONTRACT,

            "render_requested": False,
            "comfy_invoked": False,

            "diagram": diagram,
        })

    @api.route("/api/conversation/diagram/site", methods=["POST"])
    def conversation_diagram_site():

        from core.curriculum.site_intent_v1 import site_intent

        data = request.get_json(silent=True) or {}

        return jsonify({

            "status": "success",
            "contract": CONTRACT,

            "render_requested": False,

            "result": site_intent.parse(
                data.get("text") or data.get("site") or "",
                language=data.get("language"),
            ),
        })

    @api.route("/api/conversation/diagram/why", methods=["POST"])
    def conversation_diagram_why():

        from core.curriculum.spatial_case_reasoning_v1 import (
            spatial_case_reasoning,
        )

        data = request.get_json(silent=True) or {}

        return jsonify({

            "status": "success",
            "contract": CONTRACT,

            "render_requested": False,

            "result": spatial_case_reasoning.analyze(
                data.get("text") or data.get("question") or "",
                language=data.get("language"),
            ),
        })

    # ======================================================
    # PHASE 12 — FLOOR PROGRAM REASONING
    #
    # Semantic program reasoning only. No floor plan, no coordinates,
    # no walls, no doors, no CAD, no BIM, no IFC, no render. Every
    # endpoint is read-only with respect to the corpus and never
    # invokes ComfyUI.
    # ======================================================

    @api.route("/api/conversation/program/status", methods=["GET"])
    def conversation_program_status():

        from core.curriculum.program_model_v1 import program_model

        from core.curriculum.program_classifier_v1 import (
            program_classifier,
        )

        from core.curriculum.floor_program_v1 import (
            floor_program_reasoning,
        )

        from core.curriculum.program_curriculum_v1 import (
            program_curriculum,
        )

        return jsonify({

            "status": "success",
            "contract": CONTRACT,

            "model": program_model.report(),
            "classifier": program_classifier.report(),
            "reasoning": floor_program_reasoning.report(),
            "curriculum": program_curriculum.report(),

            "render_requested": False,
            "comfy_invoked": False,
            "geometry_generated": False,
        })

    @api.route("/api/conversation/program/reason", methods=["POST"])
    def conversation_program_reason():

        """Free-form requirement -> reasoned semantic floor program."""

        from core.curriculum.floor_program_v1 import (
            floor_program_reasoning,
        )

        data = request.get_json(silent=True) or {}

        requirement = (
            data.get("requirement")
            or data.get("text")
            or data.get("message")
            or ""
        )

        result = floor_program_reasoning.reason(

            requirement,

            language=data.get("language"),

            project_id=data.get("project_id"),
        )

        return jsonify({

            "status": "success",
            "contract": CONTRACT,

            "render_requested": False,
            "comfy_invoked": False,

            "result": result,
        })

    @api.route("/api/conversation/program/classify", methods=["POST"])
    def conversation_program_classify():

        from core.curriculum.program_classifier_v1 import (
            program_classifier,
        )

        data = request.get_json(silent=True) or {}

        return jsonify({

            "status": "success",
            "contract": CONTRACT,

            "render_requested": False,

            "result": program_classifier.classify(
                data.get("text") or data.get("requirement") or "",
                language=data.get("language"),
            ),
        })

    return api
