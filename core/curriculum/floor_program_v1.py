# ==========================================================
# ArchitectOS Floor Program Reasoning v1
#
# PHASE 12 - PART 3 - PROGRAM REASONING
#
#   free-form requirement (fa | en)
#        -> building program understanding      (Part 1)
#        -> floor program model                 (Part 2)
#        -> REASONED FLOOR PROGRAM + trace      (Part 3, here)
#
# This is the layer between
#
#   SPACE + RELATIONSHIP + BUBBLE DIAGRAM   (Phases 10 + 11)
#                      and
#   future layout generation                (NOT this phase)
#
# SEMANTIC ONLY. No geometry, no coordinates, no walls, no doors, no
# CAD, no BIM, no IFC, no render.
#
# TWO PROGRAM SOURCES, deliberately:
#
#   residential / villa
#       Phase 11's `program_spaces()` is used, because it is the layer
#       that already knows how to EXPAND a bedroom count and apply the
#       curriculum completion. Re-deriving that here would create the
#       second implementation this phase is forbidden to create.
#
#   commercial / mixed use / other
#       the frozen `building_program_knowledge` payload is used
#       directly, because a bedroom count is not what drives those
#       programs.
#
# Which path ran is recorded on the result as `program_source`, and the
# mixed-use case states its residential component explicitly.
# ==========================================================


from __future__ import annotations


from core.conversation.turn_semantics_v1 import script_of

from core.curriculum.space_types_v1 import space_types

from core.curriculum.zone_model_v1 import zone_display, ALL_ZONES

from core.curriculum.program_model_v1 import (
    program_model,
    PRIORITY_P1,
    PRIORITY_P2,
    PRIORITY_P3,
    priority_display,
    building_type_display,
    BUILDING_TYPE_RESIDENTIAL,
    BUILDING_TYPE_VILLA,
    BUILDING_TYPE_MIXED_USE,
    BUILDING_TYPE_COMMERCIAL,
    CONSTRAINT_FORBIDDEN_OPENING,
    CONSTRAINT_BUFFERED_CONNECTION,
    CONSTRAINT_PRIVACY_SEPARATION,
    CONSTRAINT_CONTROLLED_ACCESS,
    CONSTRAINT_CAPACITY,
    CONSTRAINT_ACCESS_REQUIRED,
)

from core.curriculum.program_classifier_v1 import program_classifier

from core.curriculum.bubble_diagram_v1 import bubble_diagram_builder


CONTRACT = "FloorProgramReasoningV1"
VERSION = "1.0"


# Programs that Phase 11 expands (bedroom count + curriculum completion).
PHASE11_EXPANDED_TYPES = (
    BUILDING_TYPE_RESIDENTIAL,
    BUILDING_TYPE_VILLA,
)


CONSTRAINT_REASON_LABELS = {
    CONSTRAINT_FORBIDDEN_OPENING: {
        "fa": "\u0628\u0627\u0632\u0634\u0648\u06cc "
              "\u0645\u0633\u062a\u0642\u06cc\u0645 \u0645\u0645\u0646\u0648\u0639",
        "en": "direct opening forbidden",
    },
    CONSTRAINT_BUFFERED_CONNECTION: {
        "fa": "\u0641\u0642\u0637 \u0628\u0627 \u0648\u0627\u0633\u0637\u0647",
        "en": "buffered connection only",
    },
    CONSTRAINT_PRIVACY_SEPARATION: {
        "fa": "\u062c\u062f\u0627\u06cc\u06cc "
              "\u062d\u0631\u06cc\u0645 \u062e\u0635\u0648\u0635\u06cc",
        "en": "private separation",
    },
    CONSTRAINT_CONTROLLED_ACCESS: {
        "fa": "\u062f\u0633\u062a\u0631\u0633\u06cc "
              "\u06a9\u0646\u062a\u0631\u0644\u200c\u0634\u062f\u0647",
        "en": "controlled access",
    },
    CONSTRAINT_CAPACITY: {
        "fa": "\u0638\u0631\u0641\u06cc\u062a",
        "en": "capacity",
    },
    CONSTRAINT_ACCESS_REQUIRED: {
        "fa": "\u0646\u06cc\u0627\u0632 \u062f\u0633\u062a\u0631\u0633\u06cc",
        "en": "access required",
    },
}


def constraint_label(kind, language="en"):

    entry = CONSTRAINT_REASON_LABELS.get(kind) or {}

    return entry.get(
        "fa" if str(language or "").startswith("fa") else "en"
    ) or str(kind)


class FloorProgramReasoningV1:

    CONTRACT = CONTRACT
    VERSION = VERSION

    def __init__(self, classifier=None, model=None, builder=None,
                 registry=None):

        self.classifier = classifier or program_classifier

        self.model = model or program_model

        self.builder = builder or bubble_diagram_builder

        self.registry = registry or space_types

        print(
            "\U0001f3d7\ufe0f FLOOR PROGRAM REASONING v1.0 ONLINE "
            "(program -> zones -> spaces -> priorities -> constraints)"
        )

    # ======================================================
    # PROGRAM KNOWLEDGE (frozen corpus)
    # ======================================================

    def _program_payload(self, building_type):

        try:

            from core.architecture.knowledge.building_program_knowledge import (  # noqa: E501
                BuildingProgramKnowledge,
            )

            knowledge = BuildingProgramKnowledge()

            return knowledge.get_program(building_type)

        except Exception as error:

            print("PHASE 12 PROGRAM KNOWLEDGE ERROR:", error)

            return None

    # ======================================================
    # REASON
    # ======================================================

    def reason(self, requirement, language=None, project_id=None):

        raw = str(requirement or "")

        lang = (
            "fa" if str(language or "").startswith("fa")
            else "en" if str(language or "").startswith("en")
            else ("fa" if script_of(raw) == "persian" else "en")
        )

        # ---- Part 1: understanding ----
        classification = self.classifier.classify(raw, lang)

        building_type = classification["building_type"]

        occupancy = {
            "household_size": classification["occupancy"].get(
                "household_size"
            ),
            "bedrooms": classification["occupancy"].get("bedrooms"),
        }

        # ---- Part 2: the floor program ----
        program_source = None

        curriculum_completion = []

        if building_type in PHASE11_EXPANDED_TYPES:

            expanded = self.builder.program_spaces(raw, lang)

            program_source = "PHASE_11_PROGRAM_SPACES"

            curriculum_completion = (
                expanded.get("curriculum_completion_added") or []
            )

            floor_program = self.model.build_from_instances(
                expanded["instances"],
                building_type,
                occupancy=occupancy,
                language=lang,
            )

        else:

            payload = self._program_payload(building_type)

            program_source = "BUILDING_PROGRAM_KNOWLEDGE"

            if payload:

                floor_program = self.model.build(
                    payload,
                    building_type,
                    occupancy=occupancy,
                    language=lang,
                )

            else:

                # Unknown type with no frozen payload: fall back to the
                # residential instance path rather than returning
                # nothing, and say that is what happened.
                expanded = self.builder.program_spaces(raw, lang)

                program_source = "PHASE_11_PROGRAM_SPACES_FALLBACK"

                floor_program = self.model.build_from_instances(
                    expanded["instances"],
                    building_type,
                    occupancy=occupancy,
                    language=lang,
                )

        # ---- Part 3: the reasoning trace ----
        summary = self.space_summary(floor_program, lang)

        reasoning = self._trace(
            classification,
            floor_program,
            summary,
            program_source,
            curriculum_completion,
            lang,
        )

        return {

            "contract": CONTRACT,
            "version": VERSION,

            "project_id": project_id,

            "input": {"requirement": raw, "site": None},

            "language": lang,

            "building_type": building_type,

            "building_type_label": building_type_display(
                building_type, lang
            ),

            "classification": classification,

            "occupancy": occupancy,

            "program_source": program_source,

            "curriculum_completion_added": curriculum_completion,

            "floor_program": floor_program,

            "space_summary": summary,

            "zones": floor_program["zones"],

            "priorities": floor_program["priorities"],

            "constraints": floor_program["constraints"],

            "relationships": floor_program["relationships"],

            "reasoning": reasoning,

            "narrative": self.narrative(reasoning, lang),

            # ---- hard scope guarantees ----
            "semantic_only": True,
            "contains_geometry": False,
            "contains_coordinates": False,
            "contains_walls": False,
            "contains_openings": False,
            "render_requested": False,
            "comfy_invoked": False,

            "deterministic": True,
            "llm_used": False,
            "network_used": False,

            "next_stage_not_started": (
                "layout generation / floor plan / walls / openings"
            ),
        }

    # ======================================================
    # SPACE SUMMARY (collapses repeated instances)
    # ======================================================

    def space_summary(self, floor_program, language="en"):

        """Group the program's spaces, collapsing repeats.

        "BEDROOM_DOUBLE x2" becomes one row with count 2, so the summary
        can say "3 bedrooms" the way a person would.
        """

        buckets = {}

        for entry in floor_program["spaces"]:

            key = entry["space_id"] or entry["program_name"]

            bucket = buckets.setdefault(
                key,
                {
                    "space_id": entry["space_id"],
                    "program_name": entry["program_name"],
                    "count": 0,
                    "required": entry["required"],
                    "zone": entry["zone"],
                    "priority": entry["priority"],
                    "category": entry["category"],
                    "privacy_level": entry["privacy_level"],
                },
            )

            bucket["count"] += 1

        summary = []

        for key, bucket in buckets.items():

            record = self.registry.space(bucket["space_id"]) if (
                bucket["space_id"]
            ) else None

            name = (record or {}).get("name") or {}

            summary.append(
                {
                    **bucket,
                    "key": key,
                    "name": name.get(
                        "fa" if str(language or "").startswith("fa")
                        else "en"
                    ) or bucket["program_name"],
                    "zone_label": zone_display(bucket["zone"], language)
                    if bucket["zone"] else None,
                    "priority_label": priority_display(
                        bucket["priority"], language
                    ),
                }
            )

        # deterministic order: by zone, then by priority, then by key
        zone_order = {zone: index for index, zone in enumerate(ALL_ZONES)}

        summary.sort(
            key=lambda item: (
                zone_order.get(item["zone"], len(ALL_ZONES)),
                item["priority"] or "P9",
                item["key"],
            )
        )

        return summary

    # ======================================================
    # REASONING TRACE
    # ======================================================

    def _trace(self, classification, floor_program, summary,
               program_source, curriculum_completion, language):

        fa = str(language or "").startswith("fa")

        lines = []

        counts = floor_program["counts"]

        # ---- 1. what was understood ----
        lines.append(
            {
                "step": "building_type",
                "en": "Building type: %s (evidence: %s)."
                      % (
                          floor_program["building_type"],
                          classification["building_type_source"],
                      ),
                "fa": "\u0646\u0648\u0639 \u0633\u0627\u062e\u062a\u0645\u0627\u0646: %s."
                      % building_type_display(
                          floor_program["building_type"], "fa"
                      ),
                "evidence": classification["building_type_evidence"],
            }
        )

        occupancy = floor_program.get("occupancy") or {}

        people = occupancy.get("household_size")

        bedrooms = occupancy.get("bedrooms")

        if people or bedrooms:

            lines.append(
                {
                    "step": "occupancy",
                    "en": "Occupancy: %s%s."
                          % (
                              ("%d people" % people) if people else "n/a",
                              (", %d bedrooms" % bedrooms)
                              if bedrooms else "",
                          ),
                    "fa": "\u0633\u0631\u0627\u0646\u0647: %s%s."
                          % (
                              ("%d \u0646\u0641\u0631" % people)
                              if people else "\u0646\u0627\u0645\u0634\u062e\u0635",
                              ("\u060c %d \u062e\u0648\u0627\u0628" % bedrooms)
                              if bedrooms else "",
                          ),
                    "evidence": {
                        "household_size": people,
                        "bedrooms": bedrooms,
                        "bedrooms_source": occupancy.get(
                            "bedrooms_source"
                        ),
                    },
                }
            )

        # ---- 2. required spaces (the brief's list) ----
        lines.append(
            {
                "step": "required_spaces",
                "en": "Required spaces (%d): %s."
                      % (counts["required"], self.required_names(summary, "en")),
                "fa": "\u0641\u0636\u0627\u0647\u0627\u06cc \u0636\u0631\u0648\u0631\u06cc "
                      "(%d): %s." % (counts["required"],
                                     self.required_names(summary, "fa")),
                "evidence": {
                    "required": counts["required"],
                    "optional": counts["optional"],
                },
            }
        )

        if curriculum_completion:

            lines.append(
                {
                    "step": "curriculum_completion",
                    "en": "Added by the curriculum (absent from the frozen "
                          "program): %s." % ", ".join(curriculum_completion),
                    "fa": "\u0627\u0641\u0632\u0648\u062f\u0647 \u0634\u062f\u0647 "
                          "\u062a\u0648\u0633\u0637 \u06a9\u0648\u0631\u06cc\u06a9\u0648\u0644\u0648\u0645: %s."
                          % ", ".join(curriculum_completion),
                    "evidence": curriculum_completion,
                }
            )

        # ---- 3. zones ----
        zone_lines = []

        for zone in floor_program["zones"]:

            zone_lines.append("%s (%d)" % (zone["label"], zone["count"]))

        lines.append(
            {
                "step": "zones",
                "en": "Functional zones: %s." % "; ".join(zone_lines),
                "fa": "\u0645\u0646\u0637\u0642\u0647\u200c\u0647\u0627\u06cc "
                      "\u0639\u0645\u0644\u06a9\u0631\u062f\u06cc: %s."
                      % "; ".join(zone_lines),
                "evidence": {
                    z["name"]: z["count"] for z in floor_program["zones"]
                },
            }
        )

        # ---- 4. privacy hierarchy ----
        bands = {}

        for entry in floor_program["spaces"]:

            zone = entry.get("zone")

            if zone:

                bands.setdefault(zone, set()).add(entry.get("privacy_level"))

        hierarchy = [
            {
                "zone": zone,
                "privacy_levels": sorted(
                    level for level in bands[zone] if level
                ),
            }
            for zone in [z["name"] for z in floor_program["zones"]]
        ]

        lines.append(
            {
                "step": "privacy_hierarchy",
                "en": "Privacy hierarchy: %s."
                      % ", ".join(
                          "%s -> %s"
                          % (
                              zone_display(item["zone"], "en"),
                              "/".join(item["privacy_levels"]) or "n/a",
                          )
                          for item in hierarchy
                      ),
                "fa": "\u0633\u0644\u0633\u0644\u0647\u200c\u0645\u0631\u0627\u062a\u0628 "
                      "\u062d\u0631\u06cc\u0645 \u062e\u0635\u0648\u0635\u06cc "
                      "\u062a\u0634\u062e\u06cc\u0635 \u062f\u0627\u062f\u0647 \u0634\u062f.",
                "evidence": hierarchy,
            }
        )

        # ---- 5. priorities ----
        priority_lines = [
            "%s: %d"
            % (priority_display(item["priority"], "en"), item["count"])
            for item in floor_program["priorities"]
            if item["count"]
        ]

        lines.append(
            {
                "step": "priorities",
                "en": "Priorities: %s." % ", ".join(priority_lines),
                "fa": "\u0627\u0648\u0644\u0648\u06cc\u062a\u200c\u0647\u0627: %s."
                      % ", ".join(
                          "%s: %d"
                          % (priority_display(item["priority"], "fa"),
                             item["count"])
                          for item in floor_program["priorities"]
                          if item["count"]
                      ),
                "evidence": {
                    item["priority"]: item["count"]
                    for item in floor_program["priorities"]
                },
            }
        )

        # ---- 6. constraints ----
        by_kind = {}

        for constraint in floor_program["constraints"]:

            by_kind.setdefault(constraint["kind"], []).append(constraint)

        if by_kind:

            lines.append(
                {
                    "step": "constraints",
                    "en": "Constraints: %s."
                          % ", ".join(
                              "%s x%d" % (constraint_label(kind, "en"), len(v))
                              for kind, v in sorted(by_kind.items())
                          ),
                    "fa": "\u0645\u062d\u062f\u0648\u062f\u06cc\u062a\u200c\u0647\u0627: %s."
                          % ", ".join(
                              "%s x%d" % (constraint_label(kind, "fa"), len(v))
                              for kind, v in sorted(by_kind.items())
                          ),
                    "evidence": {
                        kind: len(v) for kind, v in sorted(by_kind.items())
                    },
                }
            )

        # ---- 7. the hard scope statement ----
        lines.append(
            {
                "step": "scope",
                "en": "This is a SEMANTIC program: no geometry, no "
                      "coordinates, no walls, no doors were produced.",
                "fa": "\u0627\u06cc\u0646 \u0628\u0631\u0646\u0627\u0645\u0647 "
                      "\u0641\u0642\u0637 \u0645\u0639\u0646\u0627\u06cc\u06cc "
                      "\u0627\u0633\u062a: \u0647\u06cc\u0686 \u0647\u0646\u062f\u0633\u0647\u060c "
                      "\u0645\u062e\u062a\u0635\u0627\u062a\u060c \u062f\u06cc\u0648\u0627\u0631 "
                      "\u06cc\u0627 \u062f\u0631\u06cc \u062a\u0648\u0644\u06cc\u062f \u0646\u0634\u062f.",
                "evidence": {
                    "contains_geometry": False,
                    "contains_coordinates": False,
                },
            }
        )

        return lines

    # ------------------------------------------------------

    def required_names(self, summary, language="en"):

        """Brief-style list: "living, kitchen, dining, 3 bedrooms"."""

        fa = str(language or "").startswith("fa")

        parts = []

        for item in summary:

            if not item["required"]:

                continue

            name = item["name"]

            if item["count"] > 1:

                parts.append("%d x %s" % (item["count"], name))

            else:

                parts.append(name)

        return ", ".join(parts) if parts else (
            "\u0647\u06cc\u0686" if fa else "none"
        )

    # ------------------------------------------------------

    def narrative(self, reasoning, language="en"):

        key = "fa" if str(language or "").startswith("fa") else "en"

        return "\n".join(
            line.get(key) or line.get("en") or ""
            for line in reasoning
        )

    # ======================================================

    def report(self):

        return {

            "contract": CONTRACT,
            "version": VERSION,

            "read_only": True,
            "writes_performed": 0,

            "reasoning_steps": [
                "building_type",
                "occupancy",
                "required_spaces",
                "curriculum_completion",
                "zones",
                "privacy_hierarchy",
                "priorities",
                "constraints",
                "scope",
            ],

            "program_sources": [
                "PHASE_11_PROGRAM_SPACES",
                "BUILDING_PROGRAM_KNOWLEDGE",
                "PHASE_11_PROGRAM_SPACES_FALLBACK",
            ],

            "consumes": [
                "core/curriculum/program_model_v1.py",
                "core/curriculum/program_classifier_v1.py",
                "core/curriculum/space_types_v1.py",
                "core/curriculum/adjacency_model_v1.py",
                "core/curriculum/privacy_logic_v1.py",
                "core/curriculum/zone_model_v1.py",
                "core/curriculum/bubble_diagram_v1.py",
                "core/architecture/knowledge/building_program_knowledge.py",
            ],

            "contains_geometry": False,
            "contains_coordinates": False,

            "deterministic": True,
            "llm_used": False,
            "network_used": False,

            "next_stage_not_started": (
                "layout generation / floor plan / walls / openings"
            ),
        }


floor_program_reasoning = FloorProgramReasoningV1()
