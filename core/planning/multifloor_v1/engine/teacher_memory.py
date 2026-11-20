"""
ArchitectOS v11.0 — Intelligent Teacher Filter & Architectural Rule Memory (`engine/teacher_memory.py`)
Implements the user's exact architectural distinction:
  1. `HARD_ARCHITECTURAL_INVARIANTS` (`قوانین ثابت مهندسی و مقررات ملی ساختمان`):
     Universal laws that NEVER change from plan to plan (e.g., stair/elevator box fixed across all floors,
     zero column/beam intrusion in stair/elevator, zero door-column collision, unified corridor,
     bed headboard on solid wall, study desk by daylight window, door+window coordination on shared wall).
     Teacher Mode records and permanently locks ONLY universal architectural invariants.
  2. `CONTEXTUAL_DESIGN_STRATEGIES` (`فهم معماری و تصمیم‌های متناسب با هندسه هر طرح — نه قانون ثابت`):
     Plan-dependent choices (e.g., whether a duplex staircase is L-shaped `L_SHAPED` vs Semi-Circular `SEMI_CIRCULAR`,
     or whether a bed is oriented N-S or E-W depending on where the door and window sit on that specific room's walls).
     Teacher Mode NEVER hardcodes contextual choices as universal laws; instead, `SmartArchitecturalFurnitureSolver`
     and the synthesizer evaluate room geometry, wall openings, and proportions dynamically for each plan!
"""
from __future__ import annotations
import json
import os
from typing import Any, Dict, List

HARD_ARCHITECTURAL_INVARIANTS: Dict[str, Any] = {
    "stair_core_fixed_across_all_floors": True,
    "zero_column_beam_intrusion_in_stair_and_elevator": True,
    "zero_door_window_column_collision": True,
    "corridor_unified_single_color_no_extra_walls": True,
    "solid_partition_wall_between_bedrooms": True,
    "bed_headboard_on_solid_wall_clear_of_windows_and_doors": True,
    "study_desk_under_daylight_window": True,
    "vanity_desk_on_solid_wall_clear_of_door_swing": True,
    "shared_wall_door_and_window_separated": True,
    "pilotis_parking_zero_blocked_cars": True,
}

DEFAULT_TEACHER_RULES: Dict[str, Any] = {
    "version": "11.0",
    "hard_invariants": dict(HARD_ARCHITECTURAL_INVARIANTS),
    "contextual_design_policies": {
        "duplex_stair_selection_mode": "AUTO_BY_GALLERY_GEOMETRY",  # Chooses L_SHAPED or SEMI_CIRCULAR based on gallery width/prompt
        "furniture_placement_mode": "SMART_ARCHITECTURAL_SOLVER",   # Uses SmartArchitecturalFurnitureSolver per room topology
    },
    "learned_invariants_log": [],
    "skipped_contextual_notes": [],
}


class SafeTeacherMemory:
    """
    Filters Teacher feedback into Universal Architectural Invariants vs. Contextual Design Choices,
    persisting only true invariants to `teacher_rules_memory.json` without ever modifying Python source code.
    """

    def __init__(self, memory_path: str | None = None) -> None:
        if memory_path is None:
            here = os.path.dirname(os.path.abspath(__file__))
            memory_path = os.path.join(here, "teacher_rules_memory.json")
        self.memory_path = memory_path
        self.rules: Dict[str, Any] = json.loads(json.dumps(DEFAULT_TEACHER_RULES))
        self._load()

    def _load(self) -> None:
        if os.path.isfile(self.memory_path):
            try:
                with open(self.memory_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self.rules.update(data)
                    self.rules["hard_invariants"] = {
                        **HARD_ARCHITECTURAL_INVARIANTS,
                        **data.get("hard_invariants", {}),
                    }
            except Exception:
                pass

    def save(self) -> None:
        try:
            with open(self.memory_path, "w", encoding="utf-8") as f:
                json.dump(self.rules, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def learn_from_teacher_feedback(self, feedback_text: str) -> Dict[str, Any]:
        """
        Classifies user/teacher feedback into:
          - `HARD_INVARIANT` (saved permanently as a universal architectural law), or
          - `CONTEXTUAL_CHOICE` (handled dynamically per-plan by architectural geometry solver, NOT locked globally).
        """
        s = (feedback_text or "").strip()
        inv = self.rules.setdefault("hard_invariants", dict(HARD_ARCHITECTURAL_INVARIANTS))
        updates: Dict[str, Any] = {"classification": "HARD_INVARIANT", "applied_invariants": {}, "contextual_policies": {}}

        # Check if feedback describes contextual stair/form variations ("پله ال شکل", "نیم دایره", "بستگی به طراحی داره")
        if any(k in s for k in ("نیم دایره", "بستگی به طراحی", "قانون نیست")):
            updates["classification"] = "CONTEXTUAL_DESIGN_POLICY"
            self.rules["contextual_design_policies"]["duplex_stair_selection_mode"] = "AUTO_BY_GALLERY_GEOMETRY"
            updates["contextual_policies"]["duplex_stair_selection_mode"] = "AUTO_BY_GALLERY_GEOMETRY"
            sk: List[str] = list(self.rules.get("skipped_contextual_notes", []))
            if s and s not in sk:
                sk.append(s[:300])
                self.rules["skipped_contextual_notes"] = sk[-20:]

        # Universal Architectural Invariants
        if any(k in s for k in ("باکس راه پله", "تمام طبقات ثابت")):
            inv["stair_core_fixed_across_all_floors"] = True
            updates["applied_invariants"]["stair_core_fixed_across_all_floors"] = True
        if any(k in s for k in ("تخت خواب", "شمال غربی", "تخت")):
            inv["bed_headboard_on_solid_wall_clear_of_windows_and_doors"] = True
            updates["applied_invariants"]["west_bedroom_bed_in_nw_alcove"] = True
        if any(k in s for k in ("میز مطالعه", "نور روز", "زیر پنجره")):
            inv["study_desk_under_daylight_window"] = True
            updates["applied_invariants"]["study_desk_under_daylight_window"] = True
        if any(k in s for k in ("میز آرایش", "پنجره رو هم باید بکشی سمت شرق", "در میاد سمت غرب")):
            inv["vanity_desk_on_solid_wall_clear_of_door_swing"] = True
            inv["shared_wall_door_and_window_separated"] = True
            updates["applied_invariants"]["shared_wall_door_and_window_separated"] = True
        if any(k in s for k in ("دیوار بین دوتا اتاق", "دیوار بین دو اتاق", "طوسی")):
            inv["solid_partition_wall_between_bedrooms"] = True
            updates["applied_invariants"]["solid_partition_wall_between_bedrooms"] = True
        if any(k in s for k in ("رنگ راهرو یک تکه", "همون رنگ راهرو")):
            inv["corridor_unified_single_color_no_extra_walls"] = True
            updates["applied_invariants"]["corridor_unified_single_color_no_extra_walls"] = True

        if s and updates["applied_invariants"]:
            log: List[str] = list(self.rules.get("learned_invariants_log", []))
            if s not in log:
                log.append(s[:300])
                self.rules["learned_invariants_log"] = log[-25:]
        self.save()
        return updates
