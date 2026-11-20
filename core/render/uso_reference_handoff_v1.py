# -*- coding: utf-8 -*-
"""EXISTING_VISUAL_KNOWLEDGE_USO_V1 — NARROW USO REFERENCE HANDOFF.

WHAT THIS IS
------------
The single missing seam between two things ArchitectOS already has:

* the **visual reference knowledge** it already owns (78 ``AR-###`` references
  plus the newer classical pack), and
* the **verified local USO reference-conditioned T2I graph**
  (``REFERENCE_GUIDED_DESIGN_PASS``).

It is a handoff, not a system. It does not classify images, does not parse
style, does not own a database and does not render. It:

1. resolves a reference **identity** (explicit id, or a candidate set derived
   from declared metadata only);
2. **fails closed** if the reference is missing, inaccessible or hash-damaged;
3. stages the exact file under a deterministic name so the renderer reads the
   bytes that the index certified;
4. binds that filename to the graph's single ``LoadImage``;
5. verifies the graph really is the USO reference-conditioned **text-to-image**
   graph (and not an img2img / edit graph wearing the same name);
6. emits lineage.

AUTHORITY
---------
``annotation_authority`` is inherited from the index and is ``none`` everywhere.
A declared observation may rank candidates; it may never certify a style. When
the declared evidence cannot separate candidates, this module returns them
instead of guessing.
"""

import hashlib
import os
import re
import shutil

CONTRACT = "UsoReferenceHandoffV1"
VERSION = "1.0"

#: The graph this handoff is allowed to drive.
USO_WORKFLOW = "flux_uso_reference.json"

#: Structural expectations of that graph. If any of these is untrue the handoff
#: refuses rather than rendering something that only looks conditioned.
REQUIRED_CLASSES = {
    "UNETLoader": 1,
    "DualCLIPLoader": 1,
    "VAELoader": 1,
    # one positive + one negative terminal, exactly like the production graph
    "CLIPTextEncode": 2,
    "LoadImage": 1,
    "CLIPVisionLoader": 1,
    "CLIPVisionEncode": 1,
    "LoraLoaderModelOnly": 1,
    "ModelPatchLoader": 1,
    "USOStyleReference": 1,
    "EmptySD3LatentImage": 1,
    "KSampler": 1,
    "VAEDecode": 1,
    "SaveImage": 1,
}

#: USO is trained against SigLIP. Feeding CLIP-ViT-H here degrades silently.
REQUIRED_ENCODER = "sigclip_vision_patch14_384.safetensors"
REQUIRED_LORA = "uso-flux1-dit-lora-v1.safetensors"
REQUIRED_PROJECTOR = "uso-flux1-projector-v1.safetensors"

REFERENCE_ID_RE = re.compile(r"\b(AR-\d{3}|CLASSICAL_REF_\d{2})\b", re.IGNORECASE)

#: Canonical element id -> tokens that may legitimately appear in a *declared*
#: observation. Keys are the EXACT ids produced by
#: ``persian_architectural_understanding`` (``_ELEMENT_TERMS``), not invented
#: names, plus the request channels that carry an element-like signal.
ELEMENT_TOKENS = {
    # --- _ELEMENT_TERMS ids -------------------------------------------------
    "columns": ("column", "colonnade", "pilaster"),
    "capitals": ("capital", "acanthus"),
    "cornices": ("cornice", "entablature", "modillion"),
    "arches": ("arch", "arched", "arcade"),
    "pediments": ("pediment",),
    "balustrades": ("balustrade", "baluster", "railing"),
    "sculptural relief": ("relief", "carving", "carved", "ornament", "moulding",
                          "molding", "filigree", "plaster"),
    "quoins": ("quoin",),
    # --- request channels that are not in _ELEMENT_TERMS --------------------
    "balconies": ("balcony", "balconies", "terrace"),
    "entrance": ("entrance", "portal", "portico", "stair", "steps"),
    "windows": ("window",),
    "dome": ("dome",),
    "courtyard": ("courtyard", "court"),
}

#: Canonical material id -> tokens. Keys are the exact ids from ``MATERIAL_TERMS``.
MATERIAL_TOKENS = {
    "travertine": ("travertine",),
    "marble": ("marble",),
    "natural_stone": ("stone", "limestone", "ashlar", "stone-like", "carved-stone"),
    "stone": ("stone", "limestone", "ashlar"),
    "light_color": ("light", "ivory", "cream", "beige", "white"),
    "dark_color": ("dark",),
    "traditional_brick": ("brick",),
    "red_brick": ("brick", "red"),
    "fire_brick": ("brick",),
    "brick": ("brick",),
    "glazed_tile": ("tile", "glazed"),
    "metal": ("metal", "iron", "ironwork", "steel"),
    "glass": ("glass", "glazing"),
    "wood": ("wood", "timber"),
    "concrete": ("concrete",),
    "white_cement": ("cement", "plaster"),
}


# ==========================================================
# 1. SELECTION
# ==========================================================

def find_explicit_id(text):
    """Return the reference id the user actually typed, or None."""
    if not text:
        return None
    match = REFERENCE_ID_RE.search(str(text))
    return match.group(1).upper() if match else None


REFERENCE_ID_PATTERN = re.compile(r"^(AR-\d{3}|CLASSICAL_REF_\d{2})$", re.IGNORECASE)


def normalise_reference_id(value):
    """Validate a UI-supplied reference id. Returns the canonical form or None.

    The UI sends an IDENTIFIER, never a path. Anything that is not exactly one
    of the two collection id shapes is rejected here, before it can reach the
    index or the filesystem.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text or len(text) > 32:
        return None
    if not REFERENCE_ID_PATTERN.match(text):
        return None
    return text.upper()


def select_explicit(index, reference_id):
    """Explicit selection. Deterministic, and it NEVER consults ranking.

    A user who picks AR-077 must get AR-077 — not whichever reference the
    declared metadata happens to score highest.
    """
    canonical = normalise_reference_id(reference_id)
    if canonical is None:
        return {
            "status": "invalid_reference_id",
            "requested_id": reference_id,
            "message": "reference id must look like AR-023 or CLASSICAL_REF_03",
            "candidates": [],
        }
    entry = index.resolve_canonical(canonical)
    if entry is None:
        return {
            "status": "reference_not_found",
            "requested_id": canonical,
            "message": "%s is not in the reference index" % canonical,
            "candidates": [],
        }
    if not entry.get("accessible") or not entry.get("absolute_path"):
        return {
            "status": "reference_unavailable",
            "requested_id": canonical,
            "reference": entry,
            "message": "%s is indexed but its file is not readable" % canonical,
            "candidates": [],
        }
    return {
        "status": "selected_explicit",
        "requested_id": canonical,
        "reference": entry,
        "evidence": ["explicit_user_selection"],
        "candidates": [],
    }


def _declared_text(entry):
    obs = entry.get("declared_observations") or {}
    parts = []
    for value in obs.values():
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, (list, tuple)):
            parts.extend(str(v) for v in value)
    return " ".join(parts).lower()


def _style_terms(style_id):
    """Render a canonical style id into the word forms a manifest may use."""
    if not style_id:
        return []
    sid = str(style_id).lower()
    return [sid.replace("_", " "), sid.replace("_", "-")]


def request_signals(understanding):
    """Read the EXISTING understanding contract. No second parser.

    Real shapes (verified against the live engine, not assumed):
      elements  -> list of canonical ids
      materials -> {"primary": id|None, "mentions": [ids], "tone": str|None}
      style     -> {"target": id|None, "mix": [ids], "mentions": [ids]}
      balconies -> {"complexity": ...}, entrance -> {"emphasis": ...}
    """
    understanding = understanding or {}

    elements = [str(e) for e in (understanding.get("elements") or [])]

    for channel in ("balconies", "entrance", "windows"):
        value = understanding.get(channel)
        if isinstance(value, dict) and any(v is not None for v in value.values()):
            elements.append(channel)

    materials = []
    mat = understanding.get("materials")
    if isinstance(mat, dict):
        if mat.get("primary"):
            materials.append(str(mat["primary"]))
        materials.extend(str(m) for m in (mat.get("mentions") or []))
    elif isinstance(mat, (list, tuple)):
        materials.extend(str(m) for m in mat)

    style_terms = []
    style = understanding.get("style")
    if isinstance(style, dict):
        style_terms.extend(_style_terms(style.get("target")))
        for sid in (style.get("mix") or []):
            style_terms.extend(_style_terms(sid))
    elif isinstance(style, str):
        style_terms.extend(_style_terms(style))

    # de-duplicate, keep order
    def _uniq(seq):
        seen, out = set(), []
        for item in seq:
            if item and item not in seen:
                seen.add(item)
                out.append(item)
        return out

    return _uniq(elements), _uniq(materials), _uniq([t for t in style_terms if t])



def _score(entry, elements, materials, style_terms):
    """Score an entry against the request using DECLARED metadata only."""
    text = _declared_text(entry)
    if not text.strip():
        return 0, []
    hits = []

    for element in elements or []:
        tokens = ELEMENT_TOKENS.get(element)
        if not tokens:
            continue
        if any(tok in text for tok in tokens):
            hits.append("element:%s" % element)

    for material in materials or []:
        tokens = MATERIAL_TOKENS.get(material)
        if not tokens:
            continue
        if any(tok in text for tok in tokens):
            hits.append("material:%s" % material)

    for term in style_terms or []:
        if term and term in text:
            hits.append("style:%s" % term)

    return len(hits), hits


def select_reference(index, request_text=None, understanding=None,
                     require_explicit_when_ambiguous=True):
    """Resolve the reference for this request.

    Returns a dict with ``status`` in:
      ``selected_explicit``   - the user named an id; deterministic
      ``selected_knowledge``  - one candidate uniquely supported by declared evidence
      ``ambiguous``           - several candidates tie; they are exposed, nothing chosen
      ``insufficient_evidence`` - nothing supports the request
      ``reference_not_found`` - the named id does not exist
      ``reference_unavailable`` - the named id exists but its file is unusable
      ``reference_already_accepted`` - the named id is a previous accepted binding
    """
    explicit = find_explicit_id(request_text)

    if explicit:
        entry = index.resolve_canonical(explicit)
        if entry is None:
            return {
                "status": "reference_not_found",
                "requested_id": explicit,
                "message": "%s is not in the reference index" % explicit,
                "candidates": [],
            }
        if not entry.get("accessible") or not entry.get("absolute_path"):
            return {
                "status": "reference_unavailable",
                "requested_id": explicit,
                "reference": entry,
                "message": "%s is indexed but its file is not readable" % explicit,
                "candidates": [],
            }
        return {
            "status": "selected_explicit",
            "requested_id": explicit,
            "reference": entry,
            "evidence": ["explicit_user_reference"],
            "candidates": [],
        }

    understanding = understanding or {}
    if not understanding and request_text:
        # Path B must be usable on its own. The request signals come from the
        # EXISTING understanding layer — this module never parses text itself.
        try:
            from core.prompt_intelligence.persian_architectural_understanding import (
                understand as _understand,
            )

            understanding = _understand(request_text) or {}
        except Exception as exc:  # noqa: BLE001
            understanding = {"__understanding_error__": repr(exc)}

    elements, materials, style_terms = request_signals(understanding)

    ranked = []
    for entry in index.usable():
        score, hits = _score(entry, elements, materials, style_terms)
        if score:
            ranked.append({"entry": entry, "score": score, "evidence": hits})
    ranked.sort(key=lambda r: (-r["score"], r["entry"]["reference_id"]))

    if not ranked:
        return {
            "status": "insufficient_evidence",
            "message": "no indexed reference declares anything matching this request",
            "requested_elements": list(elements),
            "requested_materials": list(materials),
            "candidates": [],
        }

    top = ranked[0]
    second = ranked[1] if len(ranked) > 1 else None
    margin = top["score"] - (second["score"] if second else 0)

    # Never auto-select on thin or tied evidence.
    if top["score"] < 2 or (second and margin < 1):
        return {
            "status": "ambiguous",
            "message": "declared evidence does not separate the candidates",
            "requested_elements": list(elements),
            "requested_materials": list(materials),
            "candidates": [
                {
                    "reference_id": r["entry"]["reference_id"],
                    "collection": r["entry"]["collection"],
                    "score": r["score"],
                    "evidence": r["evidence"],
                    "review_status": r["entry"].get("review_status"),
                }
                for r in ranked[:5]
            ],
        }

    return {
        "status": "selected_knowledge",
        "reference": top["entry"],
        "evidence": top["evidence"],
        "score": top["score"],
        "margin": margin,
        "authority": "declared_metadata_only",
        "candidates": [
            {
                "reference_id": r["entry"]["reference_id"],
                "score": r["score"],
                "evidence": r["evidence"],
            }
            for r in ranked[:5]
        ],
    }


# ==========================================================
# 2. GRAPH CONTRACT (FAIL CLOSED)
# ==========================================================

def verify_uso_graph(workflow):
    """Prove the graph is the USO reference-conditioned T2I graph. Never assume."""
    errors = []
    if not isinstance(workflow, dict) or not workflow:
        return {"ok": False, "errors": ["workflow is empty"]}

    nodes = {k: v for k, v in workflow.items() if isinstance(v, dict) and "class_type" in v}

    # ComfyUI's /prompt endpoint treats EVERY top-level key as a node id and
    # rejects anything else outright. A documentation key such as "_meta" makes
    # the whole submission fail with submit_error and no explanation in the
    # render result, so it is caught here instead.
    stray = [k for k in workflow.keys() if k not in nodes]
    if stray:
        return {
            "ok": False,
            "errors": [
                "non-node top-level key(s) %s — ComfyUI rejects these as invalid nodes"
                % (sorted(stray),)
            ],
        }

    counts = {}
    for node in nodes.values():
        counts[node["class_type"]] = counts.get(node["class_type"], 0) + 1

    for cls, expected in REQUIRED_CLASSES.items():
        if counts.get(cls, 0) != expected:
            errors.append(
                "expected exactly %d %s node(s), found %d" % (expected, cls, counts.get(cls, 0))
            )

    if "VAEEncode" in counts:
        errors.append("VAEEncode present: this is an img2img/edit graph, not reference-guided T2I")
    if "ReferenceLatent" in counts:
        errors.append("ReferenceLatent present: that is the Kontext edit path, not USO style conditioning")

    by_type = {}
    for nid, node in nodes.items():
        by_type.setdefault(node["class_type"], []).append(nid)

    sampler = (by_type.get("KSampler") or [None])[0]
    uso = (by_type.get("USOStyleReference") or [None])[0]
    cve = (by_type.get("CLIPVisionEncode") or [None])[0]
    load = (by_type.get("LoadImage") or [None])[0]
    lora = (by_type.get("LoraLoaderModelOnly") or [None])[0]
    patch = (by_type.get("ModelPatchLoader") or [None])[0]
    encoder = (by_type.get("CLIPVisionLoader") or [None])[0]
    latent = (by_type.get("EmptySD3LatentImage") or [None])[0]

    def link(node_id, field):
        if node_id is None:
            return None
        value = (nodes.get(node_id, {}).get("inputs") or {}).get(field)
        return value[0] if isinstance(value, list) and value else None

    if sampler and uso:
        if link(sampler, "model") != uso:
            errors.append("KSampler.model does not come from USOStyleReference")
        if (nodes[sampler]["inputs"] or {}).get("denoise") != 1.0:
            errors.append(
                "KSampler.denoise is %r, not 1.0 — a reference variation, not generation"
                % ((nodes[sampler]["inputs"] or {}).get("denoise"),)
            )
        if link(sampler, "latent_image") != latent:
            errors.append("KSampler.latent_image does not come from EmptySD3LatentImage")

        # The production prompt injector resolves KSampler.positive/negative to
        # their IMMEDIATE upstream node. If a conditioning pass-through node sits
        # in between, the compiled prompt is silently dropped and the graph's
        # template prompt renders instead. Fail closed on that shape.
        for field in ("positive", "negative"):
            target = link(sampler, field)
            target_type = (nodes.get(str(target), {}) or {}).get("class_type") if target else None
            if target_type != "CLIPTextEncode":
                errors.append(
                    "KSampler.%s must point directly at a CLIPTextEncode so the compiled "
                    "prompt can be injected (found %r)" % (field, target_type)
                )
    if uso:
        if link(uso, "model") != lora:
            errors.append("USOStyleReference.model does not come from the USO LoRA node")
        if link(uso, "model_patch") != patch:
            errors.append("USOStyleReference.model_patch does not come from ModelPatchLoader")
        if link(uso, "clip_vision_output") != cve:
            errors.append("USOStyleReference.clip_vision_output does not come from CLIPVisionEncode")
    if cve and load:
        if link(cve, "image") != load:
            errors.append("CLIPVisionEncode.image does not come from the reference LoadImage")
        if link(cve, "clip_vision") != encoder:
            errors.append("CLIPVisionEncode.clip_vision does not come from CLIPVisionLoader")

    if encoder:
        name = (nodes[encoder]["inputs"] or {}).get("clip_name")
        if name != REQUIRED_ENCODER:
            errors.append("CLIPVisionLoader uses %r, USO requires %r" % (name, REQUIRED_ENCODER))
    if lora:
        name = (nodes[lora]["inputs"] or {}).get("lora_name")
        if name != REQUIRED_LORA:
            errors.append("LoRA is %r, expected %r" % (name, REQUIRED_LORA))
    if patch:
        name = (nodes[patch]["inputs"] or {}).get("name")
        if name != REQUIRED_PROJECTOR:
            errors.append("ModelPatchLoader is %r, expected %r" % (name, REQUIRED_PROJECTOR))

    return {
        "ok": not errors,
        "errors": errors,
        "node_ids": {
            "load_image": load,
            "clip_vision_encode": cve,
            "uso_style_reference": uso,
            "ksampler": sampler,
            "latent": latent,
        },
    }


# ==========================================================
# 3. STAGING + BINDING
# ==========================================================

def _sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def stage_reference(entry, input_dir):
    """Copy the certified bytes into the renderer's input directory.

    The original file is read, never moved or renamed. The staged name is
    deterministic and derived from the reference id, so two renders of the same
    reference can never be confused and a re-render reuses the same bytes.
    """
    if not entry or not entry.get("absolute_path"):
        return {"ok": False, "error": "reference has no readable file"}
    src = entry["absolute_path"]
    if not os.path.exists(src):
        return {"ok": False, "error": "reference file missing on disk: %s" % src}

    declared = str(entry.get("sha256") or "").lower()
    actual = _sha256_file(src)
    if declared and actual != declared:
        return {
            "ok": False,
            "error": "reference digest mismatch: declared %s, actual %s" % (declared, actual),
        }

    safe_id = re.sub(r"[^A-Za-z0-9_-]", "_", str(entry["reference_id"]))
    ext = os.path.splitext(src)[1].lower() or ".jpg"
    filename = "architectos_ref_%s%s" % (safe_id, ext)

    os.makedirs(input_dir, exist_ok=True)
    dst = os.path.join(input_dir, filename)
    if not os.path.exists(dst) or _sha256_file(dst) != actual:
        shutil.copy2(src, dst)

    return {
        "ok": True,
        "filename": filename,
        "staged_path": dst,
        "sha256": actual,
        "source_path": src,
        "bytes": os.path.getsize(dst),
    }


def bind_reference(workflow, filename, node_id=None):
    """Write the reference filename to the graph's single LoadImage node."""
    nodes = {k: v for k, v in workflow.items() if isinstance(v, dict) and "class_type" in v}
    load_nodes = [nid for nid, n in nodes.items() if n.get("class_type") == "LoadImage"]

    if len(load_nodes) != 1:
        return {
            "ok": False,
            "error": "expected exactly one LoadImage, found %d" % len(load_nodes),
            "load_nodes": load_nodes,
        }

    target = node_id or load_nodes[0]
    if target not in load_nodes:
        return {"ok": False, "error": "node %s is not a LoadImage" % target}

    nodes[target].setdefault("inputs", {})["image"] = filename
    return {"ok": True, "node_id": target, "filename": filename}


# ==========================================================
# 4. LINEAGE
# ==========================================================

def extract_sampler_prompt(workflow):
    """Return the exact text the sampler consumed.

    The compiled prompt is only the INPUT to the render layer; the layer appends
    its own prompt (storey count, building type, lighting). Recording the
    compiled text as "the prompt" would misreport what the model was told.
    """
    if not isinstance(workflow, dict):
        return None
    nodes = {k: v for k, v in workflow.items() if isinstance(v, dict) and "class_type" in v}
    sampler = next((v for v in nodes.values() if v.get("class_type") == "KSampler"), None)
    if not sampler:
        return None
    link = (sampler.get("inputs") or {}).get("positive")
    if not (isinstance(link, list) and link):
        return None
    node = nodes.get(str(link[0]))
    if not node or node.get("class_type") != "CLIPTextEncode":
        return None
    return (node.get("inputs") or {}).get("text")


def build_lineage(reference, selection, staged, workflow_name, prompt,
                  understanding=None, workflow=None):
    """Everything needed to reproduce and to audit this render."""
    ref = reference or {}
    return {
        "contract": CONTRACT,
        "version": VERSION,
        "reference_id": ref.get("reference_id"),
        "reference_collection": ref.get("collection"),
        "reference_archive_path": ref.get("archive_path"),
        "reference_source_path": ref.get("absolute_path"),
        "reference_sha256": (staged or {}).get("sha256") or ref.get("sha256"),
        "reference_declared_sha256": ref.get("sha256"),
        "reference_staged_filename": (staged or {}).get("filename"),
        "reference_review_status": ref.get("review_status"),
        "reference_annotation_authority": ref.get("annotation_authority"),
        "reference_declared_observations": ref.get("declared_observations"),
        "reference_external_equivalent": ref.get("external_equivalent"),
        "selection_status": (selection or {}).get("status"),
        "selection_evidence": (selection or {}).get("evidence"),
        "selection_authority": (selection or {}).get("authority"),
        "workflow": workflow_name,
        "base_model": "flux1-dev-fp8.safetensors",
        "conditioning": "uso_style_reference",
        "render_kind": "reference_conditioned_text_to_image",
        "prompt_chars": len(prompt or ""),
        "prompt": prompt,
        "understanding": understanding or {},
        "graph_node_count": len(workflow or {}),
        "ontology_promotion": "none",
    }


# ==========================================================
# 5. THE CONNECTION (understanding -> knowledge -> reference -> render)
# ==========================================================

def _finalise_selection(selection, input_dir, understanding=None):
    """Stage and certify an already-made selection. Shared by both paths."""
    if selection.get("status") not in ("selected_explicit", "selected_knowledge"):
        return {
            "status": "reference_not_selected",
            "selection": selection,
            "understanding": understanding,
        }

    entry = selection["reference"]

    if entry.get("external_equivalent"):
        # Already bound to an accepted experiment. Not an error — but it must be
        # visible, so the same reference cannot be presented as a new one.
        selection = dict(selection)
        selection["already_accepted_binding"] = entry["external_equivalent"]

    staged = stage_reference(entry, input_dir)

    if not staged.get("ok"):
        return {
            "status": "reference_staging_failed",
            "selection": selection,
            "reference": entry,
            "error": staged.get("error"),
            "understanding": understanding,
        }

    return {
        "status": "ready",
        "selection": selection,
        "reference": entry,
        "staged": staged,
        "understanding": understanding,
    }


def prepare(request_text, index, input_dir, understanding=None):
    """Resolve, stage and certify a reference for this request.

    The understanding is taken from the EXISTING architectural understanding
    layer when the caller does not supply one; no second parser is introduced.
    """
    if understanding is None:
        try:
            from core.prompt_intelligence.persian_architectural_understanding import (
                understand as _understand,
            )

            understanding = _understand(request_text)
        except Exception as exc:  # noqa: BLE001
            understanding = {"__understanding_error__": repr(exc)}

    selection = select_reference(index, request_text, understanding)
    return _finalise_selection(selection, input_dir, understanding)


def prepare_explicit(reference_id, index, input_dir):
    """Stage and certify a reference the user selected in the interface.

    Explicit selection outranks any automatic ranking, so this path never calls
    ``select_reference`` at all.
    """
    selection = select_explicit(index, reference_id)
    return _finalise_selection(selection, input_dir, understanding=None)


def render_reference_guided(runtime, project_id, design, request_text, index,
                            input_dir, understanding=None):
    """The whole chain, through the real runtime.

    ``runtime`` is the existing ``RenderRuntime``; nothing here renders on its
    own. If the reference cannot be resolved the request is refused with the
    candidates exposed — it is never downgraded to a text-only render.
    """
    prepared = prepare(request_text, index, input_dir, understanding)

    if prepared.get("status") != "ready":
        return {
            "status": "reference_selection_blocked",
            "detail": prepared.get("status"),
            "selection": prepared.get("selection"),
            "error": prepared.get("error"),
            "understanding": prepared.get("understanding"),
        }

    entry = prepared["reference"]
    staged = prepared["staged"]
    selection = prepared["selection"]

    prompt = (
        (design or {}).get("compiled_render_prompt")
        or (design or {}).get("prompt")
        or ""
    )

    payload = {
        "filename": staged["filename"],
        "reference_id": entry["reference_id"],
        "sha256": staged["sha256"],
        "selection_status": selection.get("status"),
        "lineage": build_lineage(
            entry,
            selection,
            staged,
            USO_WORKFLOW,
            prompt,
            understanding=prepared.get("understanding"),
        ),
    }

    result = runtime.render(
        project_id=project_id,
        design=design,
        uso_reference=payload,
    )

    if isinstance(result, dict):
        injected = result.get("injected") or {}
        submitted = injected.get("workflow") if isinstance(injected, dict) else None
        sampler_text = extract_sampler_prompt(submitted)
        result["uso_lineage"] = payload["lineage"]
        result["uso_lineage"]["prompt_sent_to_sampler"] = sampler_text
        result["uso_lineage"]["prompt_sent_to_sampler_chars"] = len(sampler_text or "")
        result["uso_reference_payload"] = {
            k: v for k, v in payload.items() if k != "lineage"
        }

    return result

