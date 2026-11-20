# ==========================================================
# ArchitectOS Knowledge Read Bridge v1
#
# PHASE 09 — READ BRIDGE PREPARATION
#
# A CONTROLLED READ-ONLY interface over the architectural knowledge
# that ArchitectOS already owns.  This module:
#
#   - does NOT redesign, rewrite or re-derive any existing knowledge
#   - does NOT write anything, ever
#   - returns DEEP COPIES so a caller can never mutate the corpus
#   - exposes provenance (path + sha256 + counts) for every source
#
# It exists so that a future teaching phase can READ:
#   core/knowledge/architectural_ontology.json
#   core/knowledge/site_ontology.json
#   core/architecture/knowledge/architectural_space_knowledge_v1.py
#   the residential pattern libraries
#   the human architectural learning registry
#
# There is no write path in this file.  `assert_read_only()` proves it.
# ==========================================================


from __future__ import annotations


import copy
import hashlib
import json
import os


CONTRACT = "KnowledgeReadBridgeV1"
VERSION = "1.0"


REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)


# ----------------------------------------------------------
# SOURCE REGISTRY  (declarative, read-only)
# ----------------------------------------------------------

JSON_SOURCES = (
    {
        "id": "architectural_ontology",
        "path": "core/knowledge/architectural_ontology.json",
        "description": "spaces / building types / materials ontology",
        "count_keys": ("spaces", "building_types", "materials"),
    },
    {
        "id": "site_ontology",
        "path": "core/knowledge/site_ontology.json",
        "description": "site directions / setbacks / open spaces",
        "count_keys": ("directions", "building_position", "setbacks",
                       "open_spaces"),
    },
    {
        "id": "residential_pattern_library",
        "path": (
            "core/architecture/knowledge/RESIDENTIAL_PATTERN_LIBRARY.json"
        ),
        "description": "positive residential design patterns",
        "count_keys": ("patterns",),
    },
    {
        "id": "residential_negative_pattern_library",
        "path": (
            "core/architecture/knowledge/"
            "RESIDENTIAL_NEGATIVE_PATTERN_LIBRARY.json"
        ),
        "description": "negative / failure patterns",
        "count_keys": ("patterns",),
    },
    {
        "id": "pattern_selection_model",
        "path": (
            "core/architecture/knowledge/PATTERN_SELECTION_MODEL.json"
        ),
        "description": "pattern selection pipeline + factors",
        "count_keys": (),
    },
    {
        "id": "reference_pattern_evidence",
        "path": (
            "core/architecture/knowledge/REFERENCE_PATTERN_EVIDENCE.json"
        ),
        "description": "relations-only reference evidence",
        "count_keys": ("samples",),
    },
    {
        "id": "human_learning_registry",
        "path": (
            "core/architecture/knowledge/"
            "human_architectural_learning_registry_v1.json"
        ),
        "description": "append-only accepted human learning ledger",
        "count_keys": ("items",),
    },
    {
        "id": "residential_floor_precedent",
        "path": (
            "core/architecture/knowledge/"
            "residential_floor_precedent_patterns_v2.json"
        ),
        "description": "residential floor precedent patterns",
        "count_keys": (),
    },
)


MODULE_SOURCES = (
    {
        "id": "space_knowledge",
        "path": (
            "core/architecture/knowledge/architectural_space_knowledge_v1.py"
        ),
        "module": "core.architecture.knowledge."
                  "architectural_space_knowledge_v1",
        "description": "space specs / privacy / circulation / daylight rules",
    },
)


# ----------------------------------------------------------
# READ-ONLY GUARD
# ----------------------------------------------------------

# Incremented ONLY by _refuse_write(), which always raises. It must stay
# at 0 for the lifetime of the process.
_WRITE_ATTEMPTS = 0


def _refuse_write(*_args, **_kwargs):

    global _WRITE_ATTEMPTS

    _WRITE_ATTEMPTS += 1

    raise PermissionError(
        "KnowledgeReadBridgeV1 is READ-ONLY. Writing architectural "
        "knowledge is owned by the (future) explicit promotion bridge."
    )


class KnowledgeReadBridgeV1:

    CONTRACT = CONTRACT
    VERSION = VERSION

    def __init__(self):

        self._cache = {}

        print(
            "\U0001f4d6 KNOWLEDGE READ BRIDGE v1.0 ONLINE "
            "(read-only, no writes)"
        )

    # ======================================================
    # PATHS / INTEGRITY
    # ======================================================

    def _absolute(self, relative_path):

        return os.path.join(REPO_ROOT, relative_path)

    def _sha256(self, path):

        try:

            with open(path, "rb") as handle:

                return hashlib.sha256(handle.read()).hexdigest()

        except Exception:

            return None

    # ======================================================
    # JSON SOURCES
    # ======================================================

    def _load_json(self, source_id):

        if source_id in self._cache:

            return self._cache[source_id]

        source = next(
            (s for s in JSON_SOURCES if s["id"] == source_id), None
        )

        if source is None:

            return None

        path = self._absolute(source["path"])

        try:

            with open(path, "r", encoding="utf-8") as handle:

                payload = json.load(handle)

        except Exception:

            payload = None

        self._cache[source_id] = payload

        return payload

    def raw(self, source_id):

        """Deep copy of a whole source document (never the cache itself)."""

        return copy.deepcopy(self._load_json(source_id))

    # ======================================================
    # ARCHITECTURAL ONTOLOGY
    # ======================================================

    def architectural_ontology(self):

        return self.raw("architectural_ontology") or {}

    def spaces(self, zone=None):

        spaces = self.architectural_ontology().get("spaces") or {}

        if not zone:

            return copy.deepcopy(spaces)

        return copy.deepcopy(
            {
                key: value for key, value in spaces.items()
                if (value or {}).get("zone") == zone
            }
        )

    def space(self, space_id):

        return copy.deepcopy(
            (self.architectural_ontology().get("spaces") or {}).get(space_id)
        )

    def space_zones(self):

        spaces = self.architectural_ontology().get("spaces") or {}

        return sorted(
            {
                (value or {}).get("zone")
                for value in spaces.values()
                if (value or {}).get("zone")
            }
        )

    def building_types(self):

        return copy.deepcopy(
            self.architectural_ontology().get("building_types") or {}
        )

    def materials(self):

        return copy.deepcopy(
            self.architectural_ontology().get("materials") or {}
        )

    # ======================================================
    # SITE ONTOLOGY
    # ======================================================

    def site_ontology(self):

        return self.raw("site_ontology") or {}

    # ======================================================
    # SPACE KNOWLEDGE (module source)
    # ======================================================

    def space_knowledge(self):

        """Read the existing space-knowledge module WITHOUT modifying it."""

        try:

            from core.architecture.knowledge import (
                architectural_space_knowledge_v1 as sk,
            )

        except Exception as error:

            return {
                "available": False,
                "error": type(error).__name__ + ": " + str(error),
            }

        return {
            "available": True,
            "space_specs": copy.deepcopy(getattr(sk, "SPACE_SPECS", {})),
            "edge_types": list(getattr(sk, "EDGE_TYPES", ())),
            "non_transit": sorted(getattr(sk, "NON_TRANSIT", set())),
            "national_daylight_rules": copy.deepcopy(
                getattr(sk, "NATIONAL_DAYLIGHT_RULES", ())
            ),
            "daylight_source_quality": copy.deepcopy(
                getattr(sk, "DAYLIGHT_SOURCE_QUALITY", {})
            ),
            "provenance_levels": [
                member.name
                for member in getattr(sk, "Provenance", ())
            ],
        }

    # ======================================================
    # PATTERN LIBRARIES
    # ======================================================

    def patterns(self):

        payload = self.raw("residential_pattern_library") or {}

        return copy.deepcopy(payload.get("patterns") or [])

    def negative_patterns(self):

        payload = self.raw("residential_negative_pattern_library") or {}

        return copy.deepcopy(payload.get("patterns") or [])

    def pattern_selection_model(self):

        return self.raw("pattern_selection_model") or {}

    def reference_evidence(self):

        return self.raw("reference_pattern_evidence") or {}

    # ======================================================
    # HUMAN LEARNING REGISTRY  (read-only)
    # ======================================================

    def learning_registry(self, scope=None):

        payload = self.raw("human_learning_registry") or {}

        items = payload.get("items") or []

        if scope:

            items = [i for i in items if i.get("scope") == scope]

        return copy.deepcopy(items)

    def learning_item(self, item_id):

        for item in self.learning_registry():

            if item.get("id") == item_id:

                return item

        return None

    # ======================================================
    # TERM LOOKUP  (fa / en -> ontology space)
    # ======================================================

    def lookup_term(self, term, language=None):

        """Resolve a term to an ontology space via its synonyms."""

        needle = str(term or "").strip().lower()

        if not needle:

            return None

        for space_id, value in (self.spaces() or {}).items():

            synonyms = (value or {}).get("synonyms") or []

            for synonym in synonyms:

                if str(synonym).strip().lower() == needle:

                    return {
                        "space_id": space_id,
                        "zone": (value or {}).get("zone"),
                        "space_type": (value or {}).get("space_type"),
                        "matched_synonym": synonym,
                        "language": language,
                    }

        return None

    # ======================================================
    # PROVENANCE / INTEGRITY REPORT
    # ======================================================

    def read_report(self):

        sources = []

        for source in JSON_SOURCES + MODULE_SOURCES:

            path = self._absolute(source["path"])

            exists = os.path.isfile(path)

            entry = {
                "id": source["id"],
                "path": source["path"],
                "kind": "module" if "module" in source else "json",
                "description": source["description"],
                "exists": exists,
                "bytes": os.path.getsize(path) if exists else 0,
                "sha256": self._sha256(path) if exists else None,
                "access": "read_only",
            }

            if "count_keys" in source and source["count_keys"]:

                payload = self._load_json(source["id"]) or {}

                entry["counts"] = {
                    key: len(payload.get(key) or [])
                    for key in source["count_keys"]
                }

            sources.append(entry)

        return {
            "contract": CONTRACT,
            "version": VERSION,
            "read_only": True,
            "writes_performed": 0,
            "write_attempts_refused": _WRITE_ATTEMPTS,
            "source_count": len(sources),
            "sources": sources,
        }

    # ======================================================
    # SAFETY
    # ======================================================

    def assert_read_only(self):

        if _WRITE_ATTEMPTS != 0:

            raise AssertionError(
                "KnowledgeReadBridgeV1 performed a write attempt"
            )

        return True

    # Any accidental write call is refused loudly.
    def write(self, *args, **kwargs):

        return _refuse_write(*args, **kwargs)

    def save(self, *args, **kwargs):

        return _refuse_write(*args, **kwargs)

    def update(self, *args, **kwargs):

        return _refuse_write(*args, **kwargs)


knowledge_read_bridge = KnowledgeReadBridgeV1()
