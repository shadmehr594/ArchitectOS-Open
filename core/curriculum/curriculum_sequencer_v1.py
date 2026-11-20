# ==========================================================
# ArchitectOS Curriculum Sequencer v1
#
# CURRICULUM FOUNDATION FIX — PART 5
#
# The ORDER in which a human teacher walks the architectural
# curriculum:
#
#   Space Types -> Relationships -> Privacy -> Zoning -> Bubble Diagram
#              -> Patterns -> Design Reasoning
#
# SEVEN steps. Steps 1-5 were built by CURRICULUM_FOUNDATION_FIX;
# steps 6-7 were added by CURRICULUM_FOUNDATION_FIX_02 so the sequence
# matches the seven teaching parts the curriculum defines.
#
# THIS IS A FOUNDATION, NOT A LESSON PLAN.
#
#   * there is NO lesson content here — `LESSONS` is deliberately empty
#   * nothing is persisted; progress is a value the caller SUPPLIES
#   * nothing is learned; a step can only be not_started / in_progress /
#     completed, and "completed" means "the teacher covered it", never
#     "the system knows it"
#   * the corpus is READ ONLY
#
# Every step names the module that already backs it (built in Phases
# 10-12) and the read-only surface a teacher would use. The sequencer
# adds ORDER and GATING; it adds no architectural knowledge.
#
# Deliberately NOT here: persistence, a progress store, lesson text,
# exercises, assessment, and any notion of a "score". Curriculum
# Phase 01 owns those.
# ==========================================================


from __future__ import annotations


CONTRACT = "CurriculumSequencerV1"
VERSION = "1.0"


# ----------------------------------------------------------
# STEP STATUS (progress vocabulary — NOT a knowledge vocabulary)
#
# There is no "learned" and no "mastered" here on purpose. Progress is
# a record of what a TEACHER has covered.
# ----------------------------------------------------------

STEP_NOT_STARTED = "not_started"
STEP_IN_PROGRESS = "in_progress"
STEP_COMPLETED = "completed"


ALL_STEP_STATUSES = (
    STEP_NOT_STARTED,
    STEP_IN_PROGRESS,
    STEP_COMPLETED,
)


# ----------------------------------------------------------
# THE CURRICULUM SEQUENCE
#
# (key, label_fa, label_en, prerequisites, backing_module,
#  aspect_set, surface)
#
# `backing_module` is an EXISTING module — the sequencer consumes it,
# it does not restate its knowledge.
# ----------------------------------------------------------

CURRICULUM_STEPS = (

    {
        "key": "space_types",
        "label_fa": "\u0627\u0646\u0648\u0627\u0639 \u0641\u0636\u0627",
        "label_en": "space types",
        "order": 1,
        "prerequisites": (),
        "backing_module": "core/curriculum/space_types_v1.py",
        "aspect_set": "space",
        "surface": "/api/conversation/curriculum/spaces",
        "goal_en": "name the spaces and say what each one IS",
        "goal_fa": "\u0646\u0627\u0645\u200c\u06af\u0630\u0627\u0631\u06cc \u0641\u0636\u0627\u0647\u0627 "
                   "\u0648 \u062a\u0639\u0631\u06cc\u0641 \u0647\u0631 \u06cc\u06a9",
    },

    {
        "key": "relationships",
        "label_fa": "\u0631\u0648\u0627\u0628\u0637 \u0641\u0636\u0627\u0647\u0627",
        "label_en": "relationships",
        "order": 2,
        "prerequisites": ("space_types",),
        "backing_module": "core/curriculum/adjacency_model_v1.py",
        "aspect_set": "space",
        "surface": "/api/conversation/curriculum/relations",
        "goal_en": "say which spaces connect, and how strongly",
        "goal_fa": "\u06a9\u062f\u0627\u0645 \u0641\u0636\u0627\u0647\u0627 \u0628\u0647 \u0647\u0645 "
                   "\u0645\u062a\u0635\u0644 \u0645\u06cc\u200c\u0634\u0648\u0646\u062f \u0648 \u0628\u0627 "
                   "\u0686\u0647 \u0642\u062f\u0631\u062a\u06cc",
    },

    {
        "key": "privacy",
        "label_fa": "\u062d\u0631\u06cc\u0645 \u062e\u0635\u0648\u0635\u06cc",
        "label_en": "privacy",
        "order": 3,
        "prerequisites": ("relationships",),
        "backing_module": "core/curriculum/privacy_logic_v1.py",
        "aspect_set": "space",
        "surface": "/api/conversation/curriculum/privacy",
        "goal_en": "say which spaces must be separated, and from what",
        "goal_fa": "\u06a9\u062f\u0627\u0645 \u0641\u0636\u0627\u0647\u0627 \u0628\u0627\u06cc\u062f "
                   "\u062c\u062f\u0627 \u0628\u0627\u0634\u0646\u062f \u0648 \u0627\u0632 \u0686\u0647",
    },

    {
        "key": "zoning",
        "label_fa": "\u0632\u0648\u0646\u200c\u0628\u0646\u062f\u06cc",
        "label_en": "zoning",
        "order": 4,
        "prerequisites": ("privacy",),
        "backing_module": "core/curriculum/zone_model_v1.py",
        "aspect_set": "diagram",
        "surface": "/api/conversation/curriculum/status",
        "goal_en": "group the spaces into the six semantic zones",
        "goal_fa": "\u06af\u0631\u0648\u0647\u200c\u0628\u0646\u062f\u06cc \u0641\u0636\u0627\u0647\u0627 "
                   "\u062f\u0631 \u0634\u0634 \u0645\u0646\u0637\u0642\u0647\u0654 \u0645\u0639\u0646\u0627\u06cc\u06cc",
    },

    {
        "key": "bubble_diagram",
        "label_fa": "\u062f\u06cc\u0627\u06af\u0631\u0627\u0645 \u062d\u0628\u0627\u0628\u06cc",
        "label_en": "bubble diagram",
        "order": 5,
        "prerequisites": ("zoning",),
        "backing_module": "core/curriculum/bubble_diagram_v1.py",
        "aspect_set": "diagram",
        "surface": "/api/conversation/diagram/generate",
        "goal_en": "express the spaces and their relations as one diagram",
        "goal_fa": "\u0628\u06cc\u0627\u0646 \u0641\u0636\u0627\u0647\u0627 \u0648 "
                   "\u0631\u0648\u0627\u0628\u0637\u200c\u0634\u0627\u0646 \u062f\u0631 \u06cc\u06a9 "
                   "\u062f\u06cc\u0627\u06af\u0631\u0627\u0645",
    },

    {
        "key": "patterns",
        "label_fa": "\u0627\u0644\u06af\u0648\u0647\u0627\u06cc \u0645\u0639\u0645\u0627\u0631\u06cc",
        "label_en": "architectural patterns",
        "order": 6,
        "prerequisites": ("bubble_diagram",),
        "backing_module": "core/curriculum/pattern_curriculum_v1.py",
        "aspect_set": "pattern",
        "surface": "/api/conversation/knowledge/patterns",
        "goal_en": "recognise recurring arrangements and say when they apply",
        "goal_fa": "\u0634\u0646\u0627\u062e\u062a \u0686\u06cc\u062f\u0645\u0627\u0646\u200c\u0647\u0627\u06cc "
                   "\u062a\u06a9\u0631\u0627\u0631\u0634\u0648\u0646\u062f\u0647 \u0648 "
                   "\u0632\u0645\u06cc\u0646\u0647\u0654 \u06a9\u0627\u0631\u0628\u0631\u062f\u0634\u0627\u0646",
        # Coverage is NOT uniform: residential has a corpus, commercial and
        # mixed-use do not and stay blocked. The sequencer exposes that
        # boundary per step (see `_coverage`).
        "has_coverage_boundary": True,
    },

    {
        "key": "design_reasoning",
        "label_fa": "\u0627\u0633\u062a\u062f\u0644\u0627\u0644 \u0637\u0631\u0627\u062d\u06cc",
        "label_en": "design reasoning",
        "order": 7,
        "prerequisites": ("patterns",),
        "backing_module": "core/curriculum/floor_program_v1.py",
        "aspect_set": "program",
        "surface": "/api/conversation/program/reason",
        "goal_en": "turn requirements and constraints into decisions",
        "goal_fa": "\u062a\u0628\u062f\u06cc\u0644 \u0646\u06cc\u0627\u0632\u0647\u0627 \u0648 "
                   "\u0645\u062d\u062f\u0648\u062f\u06cc\u062a\u200c\u0647\u0627 \u0628\u0647 "
                   "\u062a\u0635\u0645\u06cc\u0645\u200c\u0647\u0627\u06cc \u0637\u0631\u0627\u062d\u06cc",
    },
)


STEP_KEYS = tuple(step["key"] for step in CURRICULUM_STEPS)


# Deliberately empty. The sequencer orders a curriculum; it does not
# contain one. Curriculum Phase 01 supplies the lessons.
LESSONS = ()


FORBIDDEN_STEP_STATUSES = (
    "learned",
    "mastered",
    "known",
    "permanent",
    "truth",
)


class CurriculumSequencerV1:

    CONTRACT = CONTRACT
    VERSION = VERSION

    def __init__(self, steps=None):

        self.steps = tuple(steps or CURRICULUM_STEPS)

        print(
            "\U0001f9ed CURRICULUM SEQUENCER v1.0 ONLINE "
            "(%d steps, order only - no lessons)" % len(self.steps)
        )

    # ======================================================
    # COVERAGE BOUNDARY (optional, per step)
    # ======================================================

    def _coverage(self, key):

        """A step's corpus coverage, when it has one.

        Only PATTERNS does: residential patterns have a corpus, while
        commercial and mixed-use have none and must stay blocked. The
        boundary is READ from the pattern curriculum, which derives it
        from evidence in the read bridge — so this never hardcodes
        availability, and registering a commercial pattern library would
        open the family with no change here.
        """

        if key != "patterns":

            return None

        try:

            from core.curriculum.pattern_curriculum_v1 import (
                pattern_curriculum,
            )

            return pattern_curriculum.coverage()

        except Exception as error:

            print(
                "CURRICULUM COVERAGE ERROR:",
                type(error).__name__,
                error,
            )

            return None

    # ======================================================
    # SEQUENCE
    # ======================================================

    def sequence(self, language="en"):

        """The ordered curriculum, without any progress state."""

        fa = str(language or "").startswith("fa")

        return [
            {
                "key": step["key"],
                "order": step["order"],
                "label": step["label_fa"] if fa else step["label_en"],
                "goal": step["goal_fa"] if fa else step["goal_en"],
                "prerequisites": list(step["prerequisites"]),
                "backing_module": step["backing_module"],
                "aspect_set": step["aspect_set"],
                "surface": step["surface"],
                "has_lesson": step["key"] in self.lesson_keys(),
                "coverage": self._coverage(step["key"]),
            }
            for step in sorted(self.steps, key=lambda s: s["order"])
        ]

    # ------------------------------------------------------

    def lesson_keys(self):

        """Keys that currently have lesson content.

        Always empty in this phase — the field exists so a later phase
        can fill it without changing the contract.
        """

        return tuple(
            lesson.get("step")
            for lesson in LESSONS
            if lesson.get("step")
        )

    # ------------------------------------------------------

    def step(self, key):

        for step in self.steps:

            if step["key"] == key:

                return dict(step)

        return None

    # ------------------------------------------------------

    def prerequisites(self, key):

        step = self.step(key)

        return tuple(step["prerequisites"]) if step else ()

    # ======================================================
    # PROGRESS (supplied by the caller — never persisted here)
    # ======================================================

    def progress_template(self):

        return {key: STEP_NOT_STARTED for key in STEP_KEYS}

    # ------------------------------------------------------

    def validate_progress(self, progress):

        """Reject unknown steps and any knowledge-like status."""

        progress = progress or {}

        problems = []

        for key, value in progress.items():

            if key not in STEP_KEYS:

                problems.append({"step": key, "problem": "unknown_step"})

                continue

            if value in FORBIDDEN_STEP_STATUSES:

                problems.append(
                    {"step": key, "problem": "forbidden_status",
                     "status": value}
                )

                continue

            if value not in ALL_STEP_STATUSES:

                problems.append(
                    {"step": key, "problem": "unknown_status",
                     "status": value}
                )

        return {
            "valid": not problems,
            "problems": problems,
            "allowed_statuses": list(ALL_STEP_STATUSES),
            "forbidden_statuses": list(FORBIDDEN_STEP_STATUSES),
        }

    # ------------------------------------------------------

    def _status(self, progress, key):

        value = (progress or {}).get(key)

        return value if value in ALL_STEP_STATUSES else STEP_NOT_STARTED

    # ------------------------------------------------------

    def is_completed(self, progress, key):

        return self._status(progress, key) == STEP_COMPLETED

    # ------------------------------------------------------

    def is_available(self, progress, key):

        """A step is available when every prerequisite is COMPLETED **and
        every earlier step in the sequence is completed too**.

        Enforcing the full order — not merely the immediate prerequisite —
        is what makes this a SEQUENCER. Without it, marking `zoning`
        complete on its own would unlock `bubble_diagram`, so a teacher
        could reach the diagram having covered none of the basics.
        """

        step = self.step(key)

        if not step:

            return False

        if self._status(progress, key) == STEP_COMPLETED:

            return False

        earlier = [
            other["key"] for other in self.steps
            if other["order"] < step["order"]
        ]

        required = set(step["prerequisites"]) | set(earlier)

        return all(
            self.is_completed(progress, prerequisite)
            for prerequisite in required
        )

    # ------------------------------------------------------

    def available_steps(self, progress=None):

        return [
            step["key"]
            for step in sorted(self.steps, key=lambda s: s["order"])
            if self.is_available(progress, step["key"])
        ]

    # ------------------------------------------------------

    def next_step(self, progress=None):

        """The next step the teacher may start, or None if finished."""

        available = self.available_steps(progress)

        return available[0] if available else None

    # ------------------------------------------------------

    def is_complete(self, progress=None):

        return all(
            self.is_completed(progress, key) for key in STEP_KEYS
        )

    # ------------------------------------------------------

    def progress_ratio(self, progress=None):

        done = len(
            [key for key in STEP_KEYS if self.is_completed(progress, key)]
        )

        return round(done / float(len(STEP_KEYS)), 3)

    # ======================================================
    # PLAN
    # ======================================================

    def plan(self, progress=None, language="en"):

        """The ordered plan, annotated with the caller's progress."""

        fa = str(language or "").startswith("fa")

        planned = []

        for step in sorted(self.steps, key=lambda s: s["order"]):

            key = step["key"]

            status = self._status(progress, key)

            planned.append(
                {
                    "key": key,
                    "order": step["order"],
                    "label": step["label_fa"] if fa else step["label_en"],
                    "goal": step["goal_fa"] if fa else step["goal_en"],
                    "prerequisites": list(step["prerequisites"]),
                    "backing_module": step["backing_module"],
                    "aspect_set": step["aspect_set"],
                    "surface": step["surface"],
                    "status": status,
                    "available": self.is_available(progress, key),
                    "has_lesson": key in self.lesson_keys(),
                    "coverage": self._coverage(key),
                }
            )

        return {

            "contract": CONTRACT,
            "version": VERSION,

            "language": "fa" if fa else "en",

            "steps": planned,

            "step_count": len(planned),

            "next_step": self.next_step(progress),

            "available_steps": self.available_steps(progress),

            "completed_steps": [
                key for key in STEP_KEYS
                if self.is_completed(progress, key)
            ],

            "progress_ratio": self.progress_ratio(progress),

            "is_complete": self.is_complete(progress),

            # ---- hard scope guarantees ----
            "has_lessons": bool(self.lesson_keys()),
            "lesson_count": len(self.lesson_keys()),

            "persists_progress": False,
            "permanent_learning": False,

            "contains_geometry": False,
            "contains_coordinates": False,
            "render_requested": False,
            "comfy_invoked": False,

            "deterministic": True,
            "llm_used": False,
            "network_used": False,
        }

    # ======================================================

    def report(self):

        return {

            "contract": CONTRACT,
            "version": VERSION,

            "read_only": True,
            "writes_performed": 0,

            "step_count": len(self.steps),
            "step_keys": list(STEP_KEYS),

            "coverage_boundary_steps": [
                step["key"] for step in self.steps
                if step.get("has_coverage_boundary")
            ],

            "step_statuses": list(ALL_STEP_STATUSES),
            "forbidden_step_statuses": list(FORBIDDEN_STEP_STATUSES),

            "lesson_count": len(LESSONS),
            "has_lessons": bool(LESSONS),

            "persists_progress": False,
            "permanent_learning": False,

            "consumes": [
                step["backing_module"] for step in self.steps
            ],

            "contains_geometry": False,
            "contains_coordinates": False,

            "next_stage_not_started": (
                "lesson content / exercises / assessment (Curriculum Phase 01)"
            ),
        }


curriculum_sequencer = CurriculumSequencerV1()
