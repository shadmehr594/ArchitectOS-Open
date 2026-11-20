"""Shared, route-neutral facade knowledge resolution.

This module adapts the existing ArchitectOS facade/style/material knowledge for
rendering routes.  It is deliberately not a new facade design engine: it only
canonicalizes identifiers, calls the existing resolvers/reasoners, and exposes
their evidence through one stable contract.
"""

from __future__ import annotations

from copy import deepcopy
import json
import os
import re
from typing import Any, Dict, Iterable, List

from core.architecture.knowledge.facade_resolver import ArchitecturalFacadeResolverV1
from core.architecture.knowledge.material_resolver import ArchitecturalMaterialResolverV1
from core.architecture.reasoning.facade_assembly_reasoner import FacadeAssemblyReasoner
from core.architecture.reasoning.facade_composition_reasoner import FacadeCompositionReasoner


UNKNOWN = "UNKNOWN"


# ==========================================================
# STYLE_SYNONYM_INDEX_V1
#
# `architectural_style_ontology.json` has always declared `synonyms`
# for every style — including the Persian names — but NOTHING read
# them: `canonicalize_style` only knew the hardcoded `_ALIASES` map,
# so a request written in Persian reached the resolvers as an
# unknown style id. The index below is built ONCE from the existing
# ontology, so a declared synonym is a real alias instead of dead
# data. Explicit `_ALIASES` entries still win, so no behaviour that
# was already decided changes.
# ==========================================================

_SYNONYM_INDEX = None


def _style_synonym_index():
    global _SYNONYM_INDEX

    if _SYNONYM_INDEX is not None:
        return _SYNONYM_INDEX

    index = {}

    try:
        path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "architectural_style_ontology.json",
        )

        with open(path, "r", encoding="utf-8") as handle:
            styles = json.load(handle).get("styles", {})

        for style_id, record in styles.items():

            if not isinstance(record, dict):
                continue

            for synonym in record.get("synonyms") or []:

                key = str(synonym).strip().lower().replace(" ", "_")

                if key:
                    index.setdefault(key, style_id)

    except Exception:
        index = {}

    _SYNONYM_INDEX = index

    return index


class ResolvedFacadeKnowledgeV1(dict):
    """Dictionary-compatible DTO for shared facade rendering knowledge."""

    CONTRACT = "ResolvedFacadeKnowledgeV1"


class SharedFacadeKnowledgeResolverV1:
    """Resolve existing facade ontologies without inventing missing semantics."""

    VERSION = "1.0"

    _ALIASES = {
        "classic": "classic",
        "classical": "classic",
        "roman": "roman_classic",
        "roman_classic": "roman_classic",
        "roman_classical": "roman_classic",
        "neoclassical": "neoclassical",
        "neo_classical": "neoclassical",
        "neo-classical": "neoclassical",
        "modern": "modern",
        "minimal": "modern_minimal",
        "modern_minimal": "modern_minimal",
        "contemporary": "modern",
        "contemporary_warm": "contemporary_warm",
        "contemporary_stone": "contemporary_stone",
        "iranian_brick": "iranian_brick",
        # FRENCH_FAMILY_ONTOLOGY_V1 — the four French-inspired families stay
        # DISTINCT; only explicit synonyms are folded onto them. A bare
        # "french"/"نمای فرانسوی" maps to French Classical, which is the root
        # of the family, and is recorded here rather than guessed per turn.
        "french": "french_classical",
        "french_classical": "french_classical",
        "french_classic": "french_classical",
        "french_classicism": "french_classical",
        "french_facade": "french_classical",
        "beaux_arts": "beaux_arts",
        "beaux-arts": "beaux_arts",
        "second_empire": "second_empire",
        "haussmann": "second_empire",
        "napoleon_iii": "second_empire",
        "mansard_style": "second_empire",
        "french_provincial": "french_provincial",
        "provence": "french_provincial",
        "provencal": "french_provincial",
        "rustic_french": "french_provincial",
    }

    _STYLE_FAMILIES = {
        "classic": "classical",
        "roman_classic": "classical",
        "neoclassical": "classical",
        "modern": "modern",
        "modern_minimal": "modern",
        "contemporary_warm": "contemporary",
        "contemporary_stone": "contemporary",
        "iranian_brick": "iranian",
        "french_classical": "french",
        "beaux_arts": "french",
        "second_empire": "french",
        "french_provincial": "french",
    }

    _ELEMENT_TERMS = {
        "arches": ("arch",),
        "columns": ("column",),
        "pilasters": ("pilaster",),
        "cornices": ("cornice",),
        "moldings": ("molding", "moulding", "trim"),
        "frames": ("frame", "surround"),
        "balustrades": ("balustrade", "stone railing"),
        "louvers": ("louver", "fin"),
        "brick_screens": ("brick screen", "perforated brick"),
        "recessed_frames": ("recessed frame", "deep frame", "recessed opening"),
        "projecting_frames": ("projecting frame",),
    }

    def __init__(self) -> None:
        self.facade_resolver = ArchitecturalFacadeResolverV1()
        self.material_resolver = ArchitecturalMaterialResolverV1()
        self.assembly_reasoner = FacadeAssemblyReasoner()
        self.composition_reasoner = FacadeCompositionReasoner()

    @classmethod
    def canonicalize_style(cls, style: Any) -> Dict[str, str]:
        requested = str(style or "").strip().lower().replace(" ", "_")
        canonical = cls._ALIASES.get(requested)

        if canonical is None:
            # STYLE_SYNONYM_INDEX_V1 — a synonym declared by the ontology is
            # an alias, including the Persian names.
            canonical = _style_synonym_index().get(requested, requested or UNKNOWN)

        family = cls._STYLE_FAMILIES.get(canonical, canonical if canonical != UNKNOWN else UNKNOWN)
        return {
            "requested_style": requested or UNKNOWN,
            "canonical_style": canonical,
            "style_family": family,
        }

    @classmethod
    def _optional_elements_for_request(cls, optional, request_text):
        """Optional style elements, kept ONLY when the request asked for them.

        STYLE_SPECIFIC_EXPRESSION_V1 — an optional element (a cupola, a
        mansard roof, figural sculpture, a dormer) must never be injected
        automatically: it is emitted only when the user's own words or
        structured details name it. Characteristic elements are unaffected,
        so a rich classical or Beaux-Arts request keeps its ornament.
        """

        text = str(request_text or "").lower().replace("_", " ")

        if not text:
            return []

        selected = []

        for element in cls._as_list(optional):

            words = str(element).lower().replace("_", " ").split()

            for word in words:

                # Prefix match, so "sculptural relief" answers "sculpture"
                # and "cupola" answers "cupola"/"cupolas".
                if len(word) >= 4 and word[:6] in text:

                    selected.append(element)

                    break

        return cls._unique(selected)

    @staticmethod
    def _as_list(value: Any) -> List[Any]:
        if value in (None, "", UNKNOWN):
            return []
        if isinstance(value, list):
            return list(value)
        if isinstance(value, (tuple, set)):
            return list(value)
        return [value]

    @staticmethod
    def _unique(values: Iterable[Any]) -> List[Any]:
        result: List[Any] = []
        seen = set()
        for value in values:
            if value in (None, "", [], {}):
                continue
            marker = repr(value)
            if marker not in seen:
                seen.add(marker)
                result.append(value)
        return result

    @classmethod
    def _semantic_strings(cls, value: Any) -> List[str]:
        result: List[str] = []
        if isinstance(value, str):
            cleaned = value.replace("_", " ").strip()
            if cleaned:
                result.append(cleaned)
        elif isinstance(value, dict):
            for item in value.values():
                result.extend(cls._semantic_strings(item))
        elif isinstance(value, (list, tuple, set)):
            for item in value:
                result.extend(cls._semantic_strings(item))
        return cls._unique(result)

    @classmethod
    def _classify_elements(cls, values: Iterable[str]) -> Dict[str, List[str]]:
        result = {key: [] for key in cls._ELEMENT_TERMS}
        for value in values:
            lowered = value.lower().replace("_", " ")
            for key, terms in cls._ELEMENT_TERMS.items():
                matched = False
                for term in terms:
                    if term == "arch":
                        matched = bool(re.search(r"\barch(?:es|ed)?\b", lowered))
                    elif term == "fin":
                        matched = bool(re.search(r"\bfins?\b", lowered))
                    else:
                        matched = term in lowered
                    if matched:
                        break
                if matched:
                    result[key].append(value)
        return {key: cls._unique(items) for key, items in result.items()}

    @staticmethod
    def _terms_containing(values: Iterable[str], *needles: str) -> List[str]:
        return [value for value in values if any(needle in value.lower() for needle in needles)]

    def _style_record(self, canonical_style: str) -> Dict[str, Any]:
        styles = self.material_resolver.styles.get("styles", {})
        if canonical_style in styles:
            return deepcopy(styles[canonical_style])
        # modern_minimal and contemporary variants are facade-language records,
        # while their family semantics are grounded in the existing modern style.
        if canonical_style in ("modern_minimal", "contemporary_warm", "contemporary_stone"):
            return deepcopy(styles.get("modern", {}))
        return {}

    def _facade_record(self, canonical_style: str) -> Dict[str, Any]:
        records = self.material_resolver.facade_language.get("facade_languages", {})
        return deepcopy(records.get(canonical_style, {}))

    def _resolve_materials(
        self,
        requested_materials: List[Any],
        canonical_style: str,
        style_record: Dict[str, Any],
        facade_record: Dict[str, Any],
        approved_materials: Any,
    ) -> Dict[str, Any]:
        material_db = self.material_resolver.materials.get("materials", {})
        explicit = self._unique(
            [str(item).strip().lower().replace(" ", "_") for item in requested_materials if str(item).strip()]
        )
        if not explicit:
            explicit = self._unique(
                self._as_list(style_record.get("materials"))
                + self._as_list(facade_record.get("materials"))
            )

        resolved = []
        compatible_options = []
        for name in explicit:
            if name in material_db:
                resolved.append({"name": name, **deepcopy(material_db[name])})
                continue
            family = "brick" if "brick" in name else "stone" if "stone" in name else name
            family_matches = []
            for material_name, data in material_db.items():
                searchable = " ".join(
                    [material_name]
                    + [str(item) for item in data.get("styles", [])]
                    + [str(item) for item in data.get("uses", [])]
                ).lower()
                if family in searchable:
                    family_matches.append(material_name)
            if family_matches:
                compatible_options.append({"requested": name, "options": self._unique(family_matches)})

        approved = self._semantic_strings(approved_materials)
        primary = self._unique(explicit + approved)
        cladding = []
        texture = []
        finish = []
        for item in resolved:
            uses = self._as_list(item.get("uses"))
            properties = self._as_list(item.get("properties"))
            if any("facade" in str(use) or "cladding" in str(use) for use in uses):
                cladding.append(item["name"])
            texture.extend([str(prop) for prop in properties if "texture" in str(prop)])
            finish.extend(self._as_list(item.get("finish")))

        return {
            "primary": primary or [UNKNOWN],
            "secondary": [UNKNOWN],
            "accent": [UNKNOWN],
            "cladding": self._unique(cladding) or [UNKNOWN],
            "texture": self._unique(texture) or [UNKNOWN],
            "finish": self._unique(finish) or [UNKNOWN],
            "resolved": resolved,
            "compatible_options": compatible_options,
            "selection_specificity": "EXPLICIT" if resolved else "FAMILY_OR_UNKNOWN",
        }

    def resolve(self, intent: Dict[str, Any]) -> ResolvedFacadeKnowledgeV1:
        intent = intent if isinstance(intent, dict) else {}
        building = intent.get("building") if isinstance(intent.get("building"), dict) else {}
        facade = intent.get("facade") if isinstance(intent.get("facade"), dict) else {}
        requested_style = intent.get("style") or building.get("style") or facade.get("style")
        style_ids = self.canonicalize_style(requested_style)
        canonical = style_ids["canonical_style"]

        style_record = self._style_record(canonical)
        facade_record = self._facade_record(canonical)
        facade_resolution = self.facade_resolver.resolve(
            {"style": canonical, "climate": intent.get("climate"), "orientation": intent.get("orientation")}
        )
        material_resolution = self.material_resolver.resolve(
            {"style": canonical, "climate": intent.get("climate", "default")}
        )
        assembly = self.assembly_reasoner.generate(
            canonical,
            facade_resolution,
            [item.get("name") for item in material_resolution.get("materials", [])],
        )
        composition_reasoning = self.composition_reasoner.analyze(canonical, assembly)

        approved_facade_language = intent.get("facade_language")
        approved_assembly = intent.get("facade_assembly")
        approved_composition = intent.get("facade_composition")
        user_details = self._unique(
            self._as_list(intent.get("facade_details"))
            + self._as_list(facade.get("details"))
        )

        # STYLE_SPECIFIC_EXPRESSION_V1 — optional elements are request-scoped.
        # `requested_style` is included because a user who types "mansard
        # roof" is asking for that element in the style string itself.
        _optional_pool = self._unique(
            self._as_list(style_record.get("optional_elements"))
            + self._as_list(facade_record.get("optional_elements"))
        )

        requested_optional_elements = self._optional_elements_for_request(
            _optional_pool,
            " ".join(
                [str(item) for item in user_details]
                + [str(requested_style or "")]
            ),
        )

        composition = self._unique(
            self._as_list(facade_record.get("composition"))
            + self._as_list(facade_resolution.get("composition"))
            + self._as_list(style_record.get("character"))
            + self._as_list(style_record.get("form_language"))
            + self._semantic_strings(approved_composition)
        )
        semantic_pool = self._unique(
            composition
            + self._as_list(style_record.get("character"))
            + self._as_list(style_record.get("form_language"))
            + self._as_list(style_record.get("facade_languages"))
            + self._as_list(facade_record.get("elements"))
            + self._semantic_strings(assembly)
            + self._semantic_strings(approved_facade_language)
            + self._semantic_strings(approved_assembly)
            + user_details
        )

        preserve = self._unique(self._as_list(intent.get("preserve_constraints")))
        if intent.get("preserve_geometry"):
            preserve.extend(
                [
                    "number_of_floors",
                    "overall_massing",
                    "building_silhouette",
                    "major_proportions",
                    "roofline",
                    "main_balconies",
                    "main_window_positions",
                    "main_door_positions",
                    "camera",
                    "perspective",
                    "major_recess_projection_geometry",
                ]
            )
        preserve = self._unique(preserve)

        materials = self._resolve_materials(
            self._as_list(intent.get("materials")),
            canonical,
            style_record,
            facade_record,
            approved_assembly,
        )

        source_names = []
        if style_record:
            source_names.append("architectural_style_ontology.json")
        if facade_record or facade_resolution.get("facade_language"):
            source_names.append("facade_language_ontology.json")
        if materials.get("resolved") or materials.get("compatible_options"):
            source_names.append("material_ontology.json")
        if user_details or requested_style or intent.get("materials"):
            source_names.append("user_request")
        if intent.get("render_source", {}).get("approval_status") is True:
            source_names.append("approved_design_intent")

        unresolved = []
        if canonical == UNKNOWN or not style_record and not facade_record:
            unresolved.append("style_semantics")
        if materials["primary"] == [UNKNOWN]:
            unresolved.append("material_selection")

        return ResolvedFacadeKnowledgeV1(
            {
                "contract": ResolvedFacadeKnowledgeV1.CONTRACT,
                "version": self.VERSION,
                **style_ids,
                "facade_language": {
                    "name": (
                        facade_resolution.get("facade_language")
                        or canonical
                        if style_record or facade_record
                        else UNKNOWN
                    ),
                    "composition": composition or [UNKNOWN],
                    "elements": self._unique(
                        self._as_list(facade_record.get("elements"))
                        + self._as_list(facade_resolution.get("elements"))
                        # STYLE_FACADE_ELEMENTS_V1 — a style whose facade
                        # vocabulary exists ONLY in the style ontology (e.g.
                        # neoclassical) used to resolve `elements: [UNKNOWN]`,
                        # so its own declared element list never reached the
                        # render prompt. The style record's list is used when
                        # no facade-language record supplies one; an existing
                        # facade record is never widened by this fallback.
                        + (
                            []
                            if self._as_list(facade_record.get("elements"))
                            else self._as_list(style_record.get("facade_languages"))
                        )
                        + self._semantic_strings(approved_facade_language)
                        + requested_optional_elements
                    ) or [UNKNOWN],
                },
                "composition": composition or [UNKNOWN],
                "symmetry": self._terms_containing(semantic_pool, "symmetr", "asymmetr") or [UNKNOWN],
                "vertical_horizontal_emphasis": self._terms_containing(
                    semantic_pool, "vertical", "horizontal"
                ) or [UNKNOWN],
                "solid_void_strategy": self._terms_containing(semantic_pool, "solid", "void") or [UNKNOWN],
                "entrance_hierarchy": self._terms_containing(semantic_pool, "entrance", "entry", "portal") or [UNKNOWN],
                "opening_treatment": self._terms_containing(semantic_pool, "opening", "window", "glazing") or [UNKNOWN],
                "balcony_treatment": self._terms_containing(semantic_pool, "balcony", "balustrade") or [UNKNOWN],
                "parapet_treatment": self._terms_containing(semantic_pool, "parapet", "cornice") or [UNKNOWN],
                "architectural_elements": self._classify_elements(semantic_pool),
                "materials": materials,
                "surface_strategy": {
                    "facade_assembly": approved_assembly or assembly or UNKNOWN,
                    "cladding": materials["cladding"],
                    "texture": materials["texture"],
                    "finish": materials["finish"],
                },
                "user_facade_details": user_details,
                "preserve_constraints": preserve,
                "geometry_authority": (
                    "SOURCE_IMAGE"
                    if intent.get("mode") == "img2img"
                    else "APPROVED_ARCHITECTOS_DESIGN"
                    if intent.get("render_source", {}).get("approval_status") is True
                    else "GENERATIVE_TEXT_INTENT"
                ),
                "geometry_preservation_method": (
                    "LOW_DENOISE_IMG2IMG_PLUS_PROMPT_CONSTRAINED"
                    if intent.get("mode") == "img2img"
                    else "APPROVED_DESIGN_PROMPT_CONSTRAINED"
                    if intent.get("render_source", {}).get("approval_status") is True
                    else "NOT_APPLICABLE"
                ),
                "provenance": self._unique(source_names),
                "unresolved": unresolved,
            }
        )
