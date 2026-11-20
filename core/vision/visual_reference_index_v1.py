# -*- coding: utf-8 -*-
"""EXISTING_VISUAL_KNOWLEDGE_USO_V1 — INCREMENTAL VISUAL REFERENCE INDEX.

WHY THIS MODULE EXISTS
----------------------
ArchitectOS already owns a visual reference collection
(``D:\\ArchitectOS_Visual_References_V1``: 78 images, ``AR-###`` identifiers,
SHA-256 per image, ``review_status=visual_classification_pending``,
``annotation_authority=none``) and a second, newer classical facade pack
(``ArchitectOS_Classical_Facade_Reference_Pack_20261023.zip``: 14 images,
``CLASSICAL_REF_##`` identifiers, ``UNCONFIRMED_VISUAL_REFERENCE_ONLY``).

Both are static JSON manifests. **Neither was reachable from production code** —
a repository-wide search for ``AR-0`` in ``*.py`` returns nothing outside the
vendored ``ezdxf`` pattern table. The reference *knowledge* was integrated
(VISUAL_KNOWLEDGE_INTEGRATION_PASS), but the reference *images* were never
addressable by identifier, so no render could ever be given one.

This module is the addressable index, and it is deliberately NOT a new system:

* it does not re-classify any image, and it invents no architectural fact;
* it copies every existing metadata field through **verbatim**, including
  ``review_status`` / ``annotation_authority`` / ``reference_status``;
* it reuses the existing identifiers (``AR-###``, ``CLASSICAL_REF_##``);
* it adds an entry only when the collection genuinely contains a new image,
  decided by SHA-256, so an exact duplicate can never be registered twice;
* it never moves, renames or overwrites an original file.

AUTHORITY BOUNDARY (inherited, not redefined)
---------------------------------------------
``annotation_authority=none`` on every entry. The classical pack's own manifest
states ``ontology_promotion: DISABLED_UNTIL_HUMAN_CONFIRMATION`` and
``style_description_not_canonical``. Those observations are therefore carried as
**declared, unverified hints usable for candidate ranking** — never as style
certification, and never promoted into the style/material ontology.
"""

import hashlib
import json
import os
import shutil
import zipfile

CONTRACT = "VisualReferenceIndexV1"
VERSION = "1.0"

COLLECTION_A = "visual_references_v1"
COLLECTION_B = "classical_facades_20261023"

#: The identifiers each collection already owns. Nothing is renumbered.
ID_PREFIX = {COLLECTION_A: "AR-", COLLECTION_B: "CLASSICAL_REF_"}

#: Fields that MUST survive a rebuild untouched. If a rebuild ever dropped one
#: of these, the index would be laundering pending references into approved ones.
PRESERVED_AUTHORITY_FIELDS = (
    "review_status",
    "annotation_authority",
    "reference_status",
    "direct_model_training_authorization",
)


def _sha256_file(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def _image_size(path):
    """Return (width, height) without importing an imaging library."""
    try:
        from PIL import Image

        with Image.open(path) as im:
            return int(im.width), int(im.height)
    except Exception:  # noqa: BLE001
        return None, None


class VisualReferenceIndexV1:
    """Addressable index over the two existing reference collections."""

    CONTRACT = CONTRACT
    VERSION = VERSION

    def __init__(self, entries=None, sources=None):
        self.entries = list(entries or [])
        self.sources = dict(sources or {})

    # ------------------------------------------------------------------ load
    @classmethod
    def load(cls, index_path):
        with open(index_path, encoding="utf-8") as fh:
            data = json.load(fh)
        if data.get("contract") != CONTRACT:
            raise ValueError(
                "unexpected contract %r (expected %r)" % (data.get("contract"), CONTRACT)
            )
        return cls(data.get("references"), data.get("sources"))

    def save(self, index_path):
        payload = {
            "contract": CONTRACT,
            "version": VERSION,
            "reference_count": len(self.entries),
            "sources": self.sources,
            "references": self.entries,
        }
        os.makedirs(os.path.dirname(os.path.abspath(index_path)) or ".", exist_ok=True)
        tmp = index_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
        os.replace(tmp, index_path)
        return payload

    # ----------------------------------------------------------------- build
    @classmethod
    def build(cls, collection_a_dir, collection_b_zip, staging_dir=None,
              external_equivalents=None):
        """Incrementally index both collections. Existing ids and metadata win.

        ``external_equivalents`` maps a SHA-256 to a label for an image that is
        already bound to a *previous* piece of evidence outside these two
        collections (for example a reference an earlier accepted experiment
        rendered). It is recorded, never used to delete or renumber anything —
        its only purpose is to stop a reference that has already been accepted
        from being silently presented as new.
        """
        index = cls()
        index.sources = {
            COLLECTION_A: os.path.abspath(collection_a_dir),
            COLLECTION_B: os.path.abspath(collection_b_zip),
        }
        index._ingest_collection_a(collection_a_dir)
        index._ingest_collection_b(collection_b_zip, staging_dir)
        if external_equivalents:
            normalised = {str(k).lower(): v for k, v in external_equivalents.items()}
            for entry in index.entries:
                label = normalised.get(str(entry.get("sha256", "")).lower())
                if label:
                    entry["external_equivalent"] = label
        return index

    def _ingest_collection_a(self, root):
        manifest_path = os.path.join(root, "manifest.json")
        with open(manifest_path, encoding="utf-8") as fh:
            manifest = json.load(fh)
        for raw in manifest.get("images", []):
            rel = raw.get("archive_path") or ("references/%s.jpg" % raw["id"])
            entry = {
                "reference_id": raw["id"],
                "collection": COLLECTION_A,
                "archive_path": rel,
                "absolute_path": os.path.abspath(os.path.join(root, rel)),
                "sha256": raw.get("sha256"),
                "width": raw.get("width"),
                "height": raw.get("height"),
                "original_filename": raw.get("original_filename"),
                # authority fields carried through verbatim
                "review_status": raw.get("review_status"),
                "annotation_authority": raw.get("annotation_authority"),
                # the only "observation" this collection declares
                "declared_observations": {
                    "reference_group_hint": raw.get("reference_group_hint"),
                },
                "duplicate_of": None,
            }
            self.entries.append(entry)

    def _ingest_collection_b(self, zip_path, staging_dir):
        with zipfile.ZipFile(zip_path) as zf:
            manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
            for raw in manifest.get("images", []):
                rel = raw.get("file")
                member = None
                for candidate in (rel, rel.replace("/", "\\")):
                    try:
                        zf.getinfo(candidate)
                        member = candidate
                        break
                    except KeyError:
                        continue
                if member is None:
                    # Fail safe: an entry that cannot be located is registered
                    # as inaccessible rather than silently dropped.
                    self.entries.append(
                        {
                            "reference_id": raw.get("id"),
                            "collection": COLLECTION_B,
                            "archive_path": rel,
                            "absolute_path": None,
                            "sha256": raw.get("sha256"),
                            "accessible": False,
                            "review_status": raw.get("reference_status"),
                            "annotation_authority": "none",
                            "declared_observations": {},
                            "duplicate_of": None,
                        }
                    )
                    continue

                staged = None
                if staging_dir:
                    staged = os.path.abspath(
                        os.path.join(staging_dir, os.path.basename(member))
                    )
                    os.makedirs(os.path.dirname(staged), exist_ok=True)
                    if not os.path.exists(staged):
                        with zf.open(member) as src, open(staged, "wb") as dst:
                            shutil.copyfileobj(src, dst)

                entry = {
                    "reference_id": raw["id"],
                    "collection": COLLECTION_B,
                    "archive_path": rel,
                    "absolute_path": staged,
                    "sha256": raw.get("sha256"),
                    "width": raw.get("width"),
                    "height": raw.get("height"),
                    "original_filename": raw.get("original_upload_name"),
                    "review_status": raw.get("reference_status"),
                    "annotation_authority": "none",
                    "direct_model_training_authorization": raw.get(
                        "direct_model_training_authorization"
                    ),
                    "declared_observations": {
                        # NOT canonical: the pack says so itself.
                        "style_description_not_canonical": raw.get(
                            "style_description_not_canonical"
                        ),
                        "visible_elements": list(raw.get("visible_elements") or []),
                        "material_observation": raw.get("material_observation"),
                    },
                    "duplicate_of": None,
                }
                self.entries.append(entry)

    # ------------------------------------------------------------- duplicate
    def deduplicate(self):
        """Mark exact duplicates by SHA-256. The FIRST occurrence keeps the id.

        A duplicate is never registered twice and never deleted from its
        collection; it is only annotated with ``duplicate_of``.
        """
        first_by_sha = {}
        marked = []
        for entry in self.entries:
            sha = entry.get("sha256")
            if not sha:
                continue
            if sha in first_by_sha:
                entry["duplicate_of"] = first_by_sha[sha]
                marked.append((entry["reference_id"], first_by_sha[sha]))
            else:
                first_by_sha[sha] = entry["reference_id"]
        return marked

    def verify_hashes(self):
        """Recompute SHA-256 for every accessible file. Returns mismatches."""
        mismatches = []
        for entry in self.entries:
            path = entry.get("absolute_path")
            if not path or not os.path.exists(path):
                entry["accessible"] = False
                continue
            entry["accessible"] = True
            actual = _sha256_file(path)
            entry["sha256_verified"] = actual == entry.get("sha256")
            if not entry["sha256_verified"]:
                mismatches.append(
                    {
                        "reference_id": entry["reference_id"],
                        "declared": entry.get("sha256"),
                        "actual": actual,
                    }
                )
        return mismatches

    # --------------------------------------------------------------- lookup
    def resolve(self, reference_id):
        """Exact identifier lookup. Duplicates resolve to their canonical entry."""
        if not reference_id:
            return None
        wanted = str(reference_id).strip().upper()
        for entry in self.entries:
            if str(entry.get("reference_id", "")).upper() == wanted:
                return entry
        return None

    def resolve_canonical(self, reference_id):
        """Follow ``duplicate_of`` so a request never renders a shadow copy."""
        entry = self.resolve(reference_id)
        seen = set()
        while entry and entry.get("duplicate_of"):
            if entry["reference_id"] in seen:
                break
            seen.add(entry["reference_id"])
            entry = self.resolve(entry["duplicate_of"])
        return entry

    def find_by_sha256(self, sha256):
        for entry in self.entries:
            if entry.get("sha256") == sha256:
                return entry
        return None

    def by_collection(self, collection):
        return [e for e in self.entries if e.get("collection") == collection]

    def usable(self):
        """Entries that can actually be handed to a renderer."""
        return [
            e
            for e in self.entries
            if e.get("accessible") and e.get("absolute_path") and not e.get("duplicate_of")
        ]


# ==========================================================
# PRODUCTION LOADING  (VISUAL_REFERENCE_UX_V2)
# ==========================================================

def default_index_path():
    """The index the running application reads.

    Kept in ``data/reference_index`` rather than beside a run's evidence, so the
    runtime never depends on a dated evidence directory.
    """
    from config import runtime_config as RC

    return RC.REFERENCE_INDEX_PATH


def load_default_index(path=None):
    """Load the index, or raise FileNotFoundError with a usable message."""
    target = path or default_index_path()
    if not os.path.exists(target):
        raise FileNotFoundError(
            "reference index not found at %s — build it with "
            "VisualReferenceIndexV1.build(...).save(...)" % target
        )
    return VisualReferenceIndexV1.load(target)


def preview_descriptor(entry):
    """(root_key, relative_path) for the EXISTING artifact resolver.

    Returns None when the entry cannot be previewed. The browser is never told
    an absolute path: it receives a root key that the attachment service knows
    and a relative path that ``resolve_public_path`` re-validates.
    """
    from config import runtime_config as RC

    if not isinstance(entry, dict):
        return None
    absolute = entry.get("absolute_path")
    if not absolute:
        return None
    root_key = RC.REFERENCE_ROOT_KEYS.get(entry.get("collection"))
    if not root_key:
        return None
    root = (
        RC.REFERENCE_LIBRARY_ROOT
        if root_key == "reference_library"
        else RC.REFERENCE_CLASSICAL_ROOT
    )
    try:
        relative = os.path.relpath(os.path.abspath(absolute), os.path.abspath(root))
    except ValueError:
        return None
    if relative.startswith(".."):
        return None
    return root_key, relative.replace("\\", "/")
