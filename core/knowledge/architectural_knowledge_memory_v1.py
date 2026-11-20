"""Architectural Knowledge Memory (V1).

The first PERMANENT architectural knowledge store. It accepts ONLY a
human-confirmed entry and keeps it as a reusable, revisioned memory item.

    ArchitecturalKnowledgeConfirmedEntryV1
              ↓
    Architectural Knowledge Memory            <- THIS LAYER
              ↓
    (read-only API for a FUTURE design consumer — NOT connected here)

Core principle
    ArchitectOS does not learn from raw conversation. It learns only from
    CONFIRMED HUMAN KNOWLEDGE. A human teaches, the system extracts, the
    human confirms, the memory stores.

It
    accepts only a confirmed entry (never a raw candidate)
    stores a contextual, non-absolute memory item
    routes an item to one or MORE taxonomy paths
    keeps every revision (correction = refinement, never deletion)
    offers a READ-ONLY query API

It MUST NOT
    carry confidence / truth / authority / AI approval
    store an absolute rule
    auto-learn / auto-promote
    emit geometry / coordinates / dimensions / placement / CAD / BIM
    connect to design generation

Dependency direction

    this module  ->  core.knowledge.human_knowledge_validation_loop_v1 (the confirmed entry contract)
    this module  ->  core.vision / core.render / core.bim / core.geometry / core.runtime  FORBIDDEN
"""

from __future__ import annotations


import json
import os
import time
import uuid

from copy import deepcopy

from typing import Any, Dict, List, Optional


from core.knowledge.human_knowledge_validation_loop_v1 import (
    ENTRY_CONTRACT,
)


CONTRACT = "ArchitecturalKnowledgeMemoryEntryV1"

STORE_CONTRACT = "ArchitecturalKnowledgeMemoryStoreV1"

VERSION = "1.0"


# ----------------------------------------------------------
# TASK 1 — the required memory-entry fields
# ----------------------------------------------------------

REQUIRED_FIELDS = (
    "knowledge_id",
    "content",
    "element",
    "function",
    "relationship",
    "fixed_properties",
    "variable_properties",
    "context",
    "exceptions",
    "human_explanation_basis",
    "source_space",
    "category_path",
    "revision_history",
)


# ----------------------------------------------------------
# TASK 2 — the expandable taxonomy
# ----------------------------------------------------------

TAXONOMY: Dict[str, List[str]] = {
    "Global": [
        "Spatial_Principles",
        "Circulation",
        "Privacy",
        "Lighting",
        "Structure",
        "General_Relationships",
    ],
    "Residential": [
        "Bedroom",
        "Master_Bedroom",
        "Living_Room",
        "Kitchen",
        "Bathroom",
        "Parking",
        "Entrance",
    ],
    "Commercial": [],
    "Mixed_Use": [],
    "Building_Types": [],
    "Cross_Space_Relationships": [],
}


def taxonomy_paths() -> List[str]:

    """Every valid path, e.g. `Global/Privacy`, `Residential/Bathroom`."""

    paths: List[str] = []

    for top, children in TAXONOMY.items():

        if children:

            paths.extend("%s/%s" % (top, child) for child in children)

        else:

            paths.append(top)

    return paths


# ----------------------------------------------------------
# TASK 3 — the routing tables (a CLOSED, documented vocabulary)
# ----------------------------------------------------------

# A space token -> its taxonomy path. Written lowercase; matching normalises.
SPACE_TO_CATEGORY: Dict[str, str] = {
    # building domains
    "residential": "Residential",
    "commercial": "Commercial",
    "mixed use": "Mixed_Use",
    # residential spaces
    "bedroom": "Residential/Bedroom",
    "master bedroom": "Residential/Master_Bedroom",
    "master_bedroom": "Residential/Master_Bedroom",
    "living": "Residential/Living_Room",
    "living room": "Residential/Living_Room",
    "dining": "Residential/Living_Room",
    "kitchen": "Residential/Kitchen",
    "bathroom": "Residential/Bathroom",
    "wc": "Residential/Bathroom",
    "parking": "Residential/Parking",
    "entrance": "Residential/Entrance",
    # a LIMITED-vocabulary association: a closet is treated as a
    # master-bedroom space (the checkpoint's own example routes it there).
    # The meaning lexicon normalises "closet" to `storage` / `wardrobe`.
    "closet": "Residential/Master_Bedroom",
    "wardrobe": "Residential/Master_Bedroom",
    "storage": "Residential/Master_Bedroom",
    # global elements
    "stair": "Global/Structure",
    "staircase": "Global/Structure",
    "window": "Global/Lighting",
    "facade": "Global/Structure",
}

# A principle word -> its Global path. Found anywhere in the knowledge text.
PRINCIPLE_TO_CATEGORY: Dict[str, str] = {
    "privacy": "Global/Privacy",
    "private": "Global/Privacy",
    "circulation": "Global/Circulation",
    "movement": "Global/Circulation",
    "light": "Global/Lighting",
    "lighting": "Global/Lighting",
    "daylight": "Global/Lighting",
    "structure": "Global/Structure",
    "spatial": "Global/Spatial_Principles",
}


_NON_CLAIMS = {
    "not_confidence": True,
    "not_truth": True,
    "not_authority": True,
    "not_absolute_rule": True,
    "not_ai_approved": True,
    "not_automatic_learning": True,
    "not_design": True,
    "not_geometry": True,
    "not_cad_or_bim": True,
}


# The memory stores words about architecture — never geometry.
FORBIDDEN_TERMS = (
    "geometry", "polygon", "coordinate", "coordinates", "dimension",
    "dimensions", "placement", "cad", "dwg", "bim", "ifc", "revit",
)


ABSOLUTE_TERMS = (
    "must", "always", "required",
    "باید", "همیشه", "الزام", "لازم است",
)


class ArchitecturalKnowledgeMemoryError(ValueError):
    """Raised when something that is not confirmed knowledge enters memory."""


def _norm(value) -> str:

    text = str(value or "").lower()

    text = text.replace("\u200c", " ")

    text = text.replace("\u064a", "\u06cc").replace("\u0643", "\u06a9")

    return text


def _new_knowledge_id():

    return "akm_" + uuid.uuid4().hex[:12]


def _category_for_space(token) -> Optional[str]:

    key = _norm(token).strip().replace("_", " ")

    key = " ".join(key.split())

    return SPACE_TO_CATEGORY.get(key)


def _unique(values) -> List[Any]:

    result: List[Any] = []

    for value in values:

        if value and value not in result:

            result.append(value)

    return result


# ----------------------------------------------------------
# TASK 3 — routing
# ----------------------------------------------------------

def route_confirmed_entry(confirmed_entry) -> Dict[str, List[str]]:

    """Route a confirmed entry to one or MORE memory paths.

    A path we cannot place becomes a PENDING category proposal — it is NEVER
    silently added to the taxonomy.
    """

    facets = confirmed_entry.get("facets") or {}

    paths: List[str] = []

    pending: List[str] = []

    def add(path):

        if path and path not in paths:

            paths.append(path)

    elements = list(facets.get("element") or [])

    contexts = list(facets.get("context") or [])

    # space tokens -> their categories; an unmapped ELEMENT is a pending
    # category proposal (never a silent addition)
    for token in elements:

        category = _category_for_space(token)

        if category:

            add(category)

        elif str(token or "").strip():

            proposal = str(token).strip()

            if proposal not in pending:

                pending.append(proposal)

    for token in contexts:

        category = _category_for_space(token)

        if category:

            add(category)

    # a relationship -> cross-space knowledge
    relationship = list(facets.get("relationship") or [])

    if relationship:

        add("Cross_Space_Relationships")

    # a principle word -> its Global path
    haystack = " ".join(
        [
            str(confirmed_entry.get("human_basis") or ""),
            " ".join(str(v) for v in relationship),
            " ".join(str(v) for v in list(facets.get("reason") or [])),
            " ".join(str(v) for v in list(facets.get("effect") or [])),
        ]
    )

    form = _norm(haystack)

    for word, path in PRINCIPLE_TO_CATEGORY.items():

        if _norm(word) in form:

            add(path)

    return {"paths": paths, "pending_proposals": pending}


# ----------------------------------------------------------
# TASK 1 / 5 / 6 — the memory entry
# ----------------------------------------------------------

def _absolute_wording(entry) -> List[str]:

    found: List[str] = []

    values = list(entry.get("element") or []) + list(entry.get("relationship") or [])

    values.append(entry.get("content") or "")

    values.append(entry.get("human_explanation_basis") or "")

    for value in values:

        form = _norm(value)

        for term in ABSOLUTE_TERMS:

            if _norm(term) in form and term not in found:

                found.append(term)

    return found


def build_memory_entry(
    confirmed_entry,
    *,
    previous_entry=None,
) -> Dict[str, Any]:

    """Build a memory entry from a CONFIRMED entry only."""

    if not isinstance(confirmed_entry, dict):

        raise ArchitecturalKnowledgeMemoryError(
            "memory accepts a confirmed entry dict only"
        )

    if confirmed_entry.get("contract") != ENTRY_CONTRACT:

        raise ArchitecturalKnowledgeMemoryError(
            "memory accepts only %s (got %r)"
            % (ENTRY_CONTRACT, confirmed_entry.get("contract"))
        )

    if confirmed_entry.get("status") != "confirmed":

        raise ArchitecturalKnowledgeMemoryError(
            "memory accepts only a CONFIRMED entry; got status %r"
            % (confirmed_entry.get("status"),)
        )

    facets = confirmed_entry.get("facets") or {}

    routing = route_confirmed_entry(confirmed_entry)

    elements = list(facets.get("element") or [])

    contexts = list(facets.get("context") or [])

    source_space = None

    for token in elements + contexts:

        if _category_for_space(token):

            source_space = str(token)

            break

    if source_space is None and elements:

        source_space = str(elements[0])

    knowledge_id = _new_knowledge_id()

    revision = 1

    previous_revision = None

    revision_history: List[Dict[str, Any]] = []

    if previous_entry is not None:

        revision = int(previous_entry.get("revision") or 1) + 1

        previous_revision = previous_entry.get("knowledge_id")

        revision_history = deepcopy(previous_entry.get("revision_history") or [])

    human_basis = confirmed_entry.get("human_basis")

    entry: Dict[str, Any] = {
        "contract": CONTRACT,
        "version": VERSION,
        "knowledge_id": knowledge_id,
        # the knowledge text — the human's own words
        "content": human_basis,
        "element": elements,
        "function": list(facets.get("function") or []),
        "relationship": list(facets.get("relationship") or []),
        "fixed_properties": list(facets.get("fixed_properties") or []),
        "variable_properties": list(facets.get("variable_properties") or []),
        "context": contexts,
        "exceptions": list(facets.get("exceptions") or []),
        "human_explanation_basis": human_basis,
        "source_space": source_space,
        "category_path": routing["paths"],
        "pending_category_proposals": routing["pending_proposals"],
        # revision system
        "revision": revision,
        "previous_revision": previous_revision,
        "superseded_by": None,
        "status": "active",
        "revision_history": revision_history,
        # safety — a memory item is never an absolute rule
        "is_absolute": False,
        "absolute_wording": _absolute_wording(
            {
                "element": elements,
                "relationship": facets.get("relationship"),
                "content": human_basis,
                "human_explanation_basis": human_basis,
            }
        ),
        "non_claims": dict(_NON_CLAIMS),
        "persistent": True,
        "read_only": True,
    }

    revision_history = revision_history + [
        {
            "revision": revision,
            "knowledge_id": knowledge_id,
            "at": time.time(),
            "human_explanation_basis": human_basis,
        }
    ]

    entry["revision_history"] = revision_history

    # ---- the memory never stores geometry ----
    payload = _norm(
        {
            key: entry[key]
            for key in (
                "content", "element", "function", "relationship",
                "fixed_properties", "variable_properties", "context",
                "exceptions", "human_explanation_basis",
            )
        }
    )

    for term in FORBIDDEN_TERMS:

        if term in payload:

            raise ArchitecturalKnowledgeMemoryError(
                "memory refused a geometry term: " + term
            )

    return entry


# ==========================================================
# THE MEMORY (TASK 1 / 4 / 7)
# ==========================================================

class ArchitecturalKnowledgeMemoryV1:

    """The permanent architectural knowledge memory.

    `path=None` -> an isolated in-memory instance (used by tests). With a path,
    the memory persists to a JSON file (append-only; revisions are kept).
    """

    CONTRACT = STORE_CONTRACT

    VERSION = VERSION

    # Memory learns ONLY from confirmed human knowledge.
    LEARNS_FROM_CONVERSATION = False

    AUTO_LEARNING = False

    def __init__(self, path: Optional[str] = None):

        self.path = path

        self._entries: List[Dict[str, Any]] = []

        if path and os.path.exists(path):

            self._load()

    # --------------------------------------------------

    def _load(self):

        try:

            with open(self.path, "r", encoding="utf-8") as handle:

                payload = json.load(handle)

            self._entries = list(payload.get("entries") or [])

        except Exception:

            self._entries = []

    def _save(self):

        if not self.path:

            return

        folder = os.path.dirname(self.path)

        if folder:

            os.makedirs(folder, exist_ok=True)

        payload = {
            "contract": STORE_CONTRACT,
            "version": VERSION,
            "updated_at": time.time(),
            "entries": self._entries,
        }

        with open(self.path, "w", encoding="utf-8") as handle:

            json.dump(payload, handle, ensure_ascii=False, indent=2)

    # --------------------------------------------------
    # TASK 7 — the write entry point (confirmed knowledge ONLY)
    # --------------------------------------------------

    def add_confirmed_entry(
        self,
        confirmed_entry,
        *,
        previous_revision: Optional[str] = None,
    ) -> Dict[str, Any]:

        """Store a human-confirmed entry. Anything else is REJECTED."""

        previous_entry = None

        if previous_revision:

            previous_entry = self._by_id(previous_revision)

            if previous_entry is None:

                raise ArchitecturalKnowledgeMemoryError(
                    "unknown previous_revision: %r" % (previous_revision,)
                )

        entry = build_memory_entry(
            confirmed_entry, previous_entry=previous_entry
        )

        if previous_entry is not None:

            previous_entry["superseded_by"] = entry["knowledge_id"]

            previous_entry["status"] = "superseded"

        self._entries.append(entry)

        self._save()

        return entry

    # --------------------------------------------------
    # TASK 7 — the READ-ONLY API
    # --------------------------------------------------

    def entries(self) -> List[Dict[str, Any]]:

        return deepcopy(self._entries)

    def active_entries(self) -> List[Dict[str, Any]]:

        return deepcopy(
            [e for e in self._entries if e.get("status") == "active"]
        )

    def _by_id(self, knowledge_id) -> Optional[Dict[str, Any]]:

        for entry in self._entries:

            if entry.get("knowledge_id") == knowledge_id:

                return entry

        return None

    def find_by_space(self, space) -> List[Dict[str, Any]]:

        category = _category_for_space(space)

        key = _norm(space)

        found = []

        for entry in self._entries:

            tokens = [_norm(t) for t in (entry.get("element") or [])]

            tokens += [_norm(t) for t in (entry.get("context") or [])]

            paths = [_norm(p) for p in (entry.get("category_path") or [])]

            if key in tokens or key in paths:

                found.append(entry)

            elif category and category in (entry.get("category_path") or []):

                found.append(entry)

        return deepcopy(found)

    def find_by_relationship(self, relationship) -> List[Dict[str, Any]]:

        key = _norm(relationship)

        found = []

        for entry in self._entries:

            for value in entry.get("relationship") or []:

                if key in _norm(value):

                    found.append(entry)

                    break

        return deepcopy(found)

    def find_by_category(self, path) -> List[Dict[str, Any]]:

        return deepcopy(
            [
                e for e in self._entries
                if path in (e.get("category_path") or [])
            ]
        )

    def get_revision_history(self, knowledge_id) -> List[Dict[str, Any]]:

        entry = self._by_id(knowledge_id)

        if entry is None:

            return []

        # walk back to the root revision
        root = entry

        seen = set()

        while root.get("previous_revision") and root.get("knowledge_id") not in seen:

            seen.add(root.get("knowledge_id"))

            parent = self._by_id(root.get("previous_revision"))

            if parent is None:

                break

            root = parent

        # walk forward through the whole chain
        chain: List[Dict[str, Any]] = []

        current = root

        guard = 0

        while current is not None and guard < 1000:

            chain.append(current)

            nxt = current.get("superseded_by")

            current = self._by_id(nxt) if nxt else None

            guard += 1

        return deepcopy(chain)

    def pending_category_proposals(self) -> List[str]:

        proposals: List[str] = []

        for entry in self._entries:

            for proposal in entry.get("pending_category_proposals") or []:

                if proposal not in proposals:

                    proposals.append(proposal)

        return proposals

    def count(self) -> int:

        return len(self._entries)

    def to_dict(self) -> Dict[str, Any]:

        return {
            "contract": STORE_CONTRACT,
            "version": VERSION,
            "persistent": bool(self.path),
            "entry_count": len(self._entries),
            "entries": deepcopy(self._entries),
            "non_claims": dict(_NON_CLAIMS),
        }

    def __repr__(self):

        return "ArchitecturalKnowledgeMemoryV1(entries=%d, persistent=%s)" % (
            len(self._entries),
            bool(self.path),
        )


architectural_knowledge_memory = ArchitecturalKnowledgeMemoryV1()
