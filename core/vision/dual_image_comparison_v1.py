"""DUAL_IMAGE_COMPARISON_V1 — a grounded A/B comparison reply contract.

WHY THIS MODULE EXISTS
======================

A two-image comparison turn already runs the real vision provider on BOTH
role-bound assets and produces two complete
`ReferenceArchitecturalAnalysisV1` contracts (`analyze_ab_references`).  That
evidence was stored on the render trace and then had NO consumer: the turn
fell through to the generic text-chat path, whose prompt carries no image
and no evidence, so the model truthfully-from-its-own-view answered
"I don't see any building photographs attached".

The broken handoff was therefore not the vision stage and not the router: it
was the missing PROJECTION from the existing analysis contract to a reply
contract.  This module is that projection and nothing else.

DESIGN RULES
============

* It consumes the EXISTING `ReferenceArchitecturalAnalysisV1` pair.  It never
  calls a provider, never renders, never writes state.
* Every asserted difference names the contract fields it was derived from
  (`source_fields`), so a reader can trace the claim back to the analysis.
* A facet is asserted as a DIFFERENCE only when BOTH sides carry a value.
  A one-sided or empty facet is reported as NOT COMPARABLE — never guessed.
* Image A is the appearance reference and image B is the geometry authority.
  The comparison says so, because the roles are part of the evidence.
* No architectural claim is invented: values are passed through verbatim
  from the analysis contract.
"""

CONTRACT = "DualImageComparisonV1"
VERSION = "1.0"

#: Analysis statuses that mean "the provider produced nothing usable".
_UNUSABLE_STATUS = (None, "", "PROVIDER_UNAVAILABLE", "FAILED")

#: Facet order is the reading order of the reply: style first, then the
#: elements that carry it, then the compositional envelope.
_FACETS = (
    "style",
    "materials",
    "openings",
    "arches",
    "roof",
    "ornament",
    "composition",
    "colour",
    "entrance",
    "relief",
    "floors",
    "balconies",
)

_LABELS = {
    "style": ("Architectural style", "سبک معماری"),
    "materials": ("Primary materials", "مصالح اصلی"),
    "openings": ("Windows and openings", "پنجره‌ها و بازشوها"),
    "arches": ("Arches", "قوس‌ها"),
    "roof": ("Roof and upper termination", "بام و بخش بالایی"),
    "ornament": ("Ornament and relief", "تزئینات و نقش‌برجسته‌ها"),
    "composition": ("Composition and symmetry", "ترکیب‌بندی و تقارن"),
    "colour": ("Colour palette", "پالت رنگ"),
    "entrance": ("Entrance hierarchy", "سلسله‌مراتب ورودی"),
    "relief": ("Facade depth and relief", "عمق و برجستگی نما"),
    "floors": ("Visible floor count", "تعداد طبقات قابل مشاهده"),
    "balconies": ("Balconies", "بالکن‌ها"),
}


# ==========================================================
# NORMALISATION — contract values to comparable strings
# ==========================================================

def _text(value):
    """A short, human-readable rendering of a contract value."""

    if value is None:
        return ""

    if isinstance(value, bool):
        return "yes" if value else "no"

    if isinstance(value, (int, float)):
        return str(value)

    if isinstance(value, str):
        return value.strip()

    if isinstance(value, dict):

        # `{"present": false}` / `{"present": true, ...}` is the contract's
        # presence idiom for optional elements.
        if "present" in value and not value.get("present"):
            return "absent"

        parts = []

        for key in sorted(value.keys()):

            item = value.get(key)

            if item in (None, "", [], {}):
                continue

            if isinstance(item, bool):
                item = "yes" if item else "no"

            parts.append(str(key) + ": " + str(item))

        return ", ".join(parts)

    if isinstance(value, (list, tuple)):

        items = [str(item).strip() for item in value if str(item).strip()]

        return ", ".join(items)

    return str(value)


def _style_value(analysis):
    """Style with its confidence, from `facade_style` + `style_candidates`."""

    style = _text(analysis.get("facade_style"))

    confidence = analysis.get("style_confidence")

    candidates = analysis.get("style_candidates")

    if not style and isinstance(candidates, (list, tuple)) and candidates:

        first = candidates[0]

        if isinstance(first, dict):

            style = _text(first.get("style"))

            if confidence is None:

                confidence = first.get("confidence")

    if style and isinstance(confidence, (int, float)):

        return style + " (confidence " + ("%.2f" % float(confidence)) + ")"

    return style


def _material_types(analysis):
    """Material type names from the contract's `materials` list."""

    materials = analysis.get("materials")

    if not isinstance(materials, (list, tuple)):

        return []

    names = []

    for item in materials:

        if isinstance(item, dict):

            name = _text(item.get("type"))

        else:

            name = _text(item)

        if name and name not in names:

            names.append(name)

    return names


def _material_evidence(analysis):
    """Per-material evidence statements, as supplied by the analysis."""

    materials = analysis.get("materials")

    if not isinstance(materials, (list, tuple)):

        return []

    evidence = []

    for item in materials:

        if not isinstance(item, dict):

            continue

        statement = _text(item.get("evidence"))

        if statement and statement not in evidence:

            evidence.append(statement)

    return evidence


def _floor_value(analysis):

    count = analysis.get("visible_floor_count")

    if isinstance(count, int) and count > 0:

        return str(count)

    return ""


# ==========================================================
# FACET EXTRACTION
# ==========================================================

def _facet_values(facet, analysis):
    """(comparable value, source contract fields) for one facet."""

    if facet == "style":

        return _style_value(analysis), ["facade_style", "style_candidates", "style_confidence"]

    if facet == "materials":

        names = _material_types(analysis)

        return ", ".join(names), ["materials"]

    if facet == "openings":

        value = _text(analysis.get("windows"))

        if not value:

            value = _text(analysis.get("opening_pattern"))

        return value, ["windows", "opening_pattern", "window_proportions"]

    if facet == "arches":

        return _text(analysis.get("arches")), ["arches"]

    if facet == "roof":

        return _text(analysis.get("roof_features")), ["roof_features"]

    if facet == "ornament":

        parts = []

        level = _text(analysis.get("ornament_level"))

        if level:

            parts.append("level: " + level)

        classical = _text(analysis.get("classical_features"))

        if classical:

            parts.append("classical: " + classical)

        modern = _text(analysis.get("modern_features"))

        if modern:

            parts.append("modern: " + modern)

        return "; ".join(parts), [
            "ornament_level",
            "classical_features",
            "modern_features",
        ]

    if facet == "composition":

        parts = []

        for key in ("symmetry", "facade_rhythm", "horizontality", "verticality"):

            value = _text(analysis.get(key))

            if value:

                parts.append(key + ": " + value)

        return "; ".join(parts), [
            "symmetry",
            "facade_rhythm",
            "horizontality",
            "verticality",
        ]

    if facet == "colour":

        palette = _text(analysis.get("color_palette"))

        tones = _text(analysis.get("dominant_tones"))

        parts = []

        if palette:

            parts.append("palette: " + palette)

        if tones:

            parts.append("tones: " + tones)

        return "; ".join(parts), ["color_palette", "dominant_tones"]

    if facet == "entrance":

        return _text(analysis.get("entrance_hierarchy")) or _text(
            analysis.get("entrance")
        ), ["entrance_hierarchy", "entrance"]

    if facet == "relief":

        depth = _text(analysis.get("facade_depth"))

        frame = _text(analysis.get("window_frame_language"))

        parts = []

        if depth:

            parts.append("depth: " + depth)

        if frame:

            parts.append("frame: " + frame)

        return "; ".join(parts), ["facade_depth", "window_frame_language"]

    if facet == "floors":

        return _floor_value(analysis), ["visible_floor_count"]

    if facet == "balconies":

        return _text(analysis.get("balconies")), ["balconies", "balcony_language"]

    return "", []


def _analysis_usable(analysis):

    if not isinstance(analysis, dict) or not analysis:

        return False

    return analysis.get("analysis_status") not in _UNUSABLE_STATUS


def _side_provenance(analysis):

    return {
        "provider": analysis.get("provider"),
        "model": analysis.get("model"),
        "analysis_status": analysis.get("analysis_status"),
        "reference_quality": analysis.get("reference_quality"),
        "image_id": analysis.get("image_id"),
        "source_hash": analysis.get("source_hash"),
        "analysis_hash": analysis.get("analysis_hash"),
        "style_confidence": analysis.get("style_confidence"),
        "visible_floor_count": analysis.get("visible_floor_count"),
        "uncertainties": list(analysis.get("uncertainties") or []),
        "unsupported_inferences": list(analysis.get("unsupported_inferences") or []),
        "perspective_limitations": list(analysis.get("perspective_limitations") or []),
        "occlusions": list(analysis.get("occlusions") or []),
    }


# ==========================================================
# BUILD
# ==========================================================

def _site_objects(analysis):
    """The permanent/worksite split for ONE side, from existing evidence."""

    if not isinstance(analysis, dict) or not analysis:
        return {}

    try:
        from core.vision.site_object_classification_v1 import (
            classify_site_objects,
        )
    except Exception:
        return {}

    return classify_site_objects(analysis)


def build_comparison(analysis_ab, user_text=None):
    """Project an A/B analysis pair into `DualImageComparisonV1`.

    Read-only: no provider call, no render, no state write.
    """

    analysis_ab = analysis_ab if isinstance(analysis_ab, dict) else {}

    analysis_a = analysis_ab.get("A") if isinstance(analysis_ab.get("A"), dict) else {}

    analysis_b = analysis_ab.get("B") if isinstance(analysis_ab.get("B"), dict) else {}

    usable_a = _analysis_usable(analysis_a)

    usable_b = _analysis_usable(analysis_b)

    differences = []

    shared = []

    not_comparable = []

    for facet in _FACETS:

        value_a, fields_a = _facet_values(facet, analysis_a)

        value_b, fields_b = _facet_values(facet, analysis_b)

        label_en, label_fa = _LABELS[facet]

        entry = {
            "facet": facet,
            "label": {"en": label_en, "fa": label_fa},
            "A": value_a or None,
            "B": value_b or None,
            "source_fields": sorted(set(fields_a) | set(fields_b)),
        }

        if not usable_a or not usable_b or not value_a or not value_b:

            entry["status"] = "not_comparable"

            not_comparable.append(entry)

            continue

        same = value_a.strip().lower() == value_b.strip().lower()

        entry["status"] = "shared" if same else "differs"

        if same:

            shared.append(entry)

        else:

            differences.append(entry)

    if usable_a and usable_b:

        status = "compared"

    elif usable_a or usable_b:

        status = "partial"

    else:

        status = "analysis_unavailable"

    return {
        "contract": CONTRACT,
        "version": VERSION,
        "status": status,
        "roles": {
            "A": (analysis_ab.get("roles") or {}).get("A", "facade_reference"),
            "B": (analysis_ab.get("roles") or {}).get("B", "target_building"),
            "geometry_authority": (analysis_ab.get("roles") or {}).get(
                "geometry_authority", "target_building"
            ),
        },
        "a_analyzed": usable_a,
        "b_analyzed": usable_b,
        "differences": differences,
        "shared": shared,
        "not_comparable": not_comparable,
        "evidence": {
            "A": {
                "statements": list(analysis_a.get("evidence") or []),
                "materials": _material_evidence(analysis_a),
            },
            "B": {
                "statements": list(analysis_b.get("evidence") or []),
                "materials": _material_evidence(analysis_b),
            },
        },
        "provenance": {
            "A": _side_provenance(analysis_a),
            "B": _side_provenance(analysis_b),
            "analysis_only": True,
            "render_executed": False,
        },
        # SITE_OBJECT_CLASSIFICATION_V1 — an as-built comparison must report
        # temporary construction objects faithfully, and must never present
        # them as architecture.
        "site_objects": {
            "A": _site_objects(analysis_a),
            "B": _site_objects(analysis_b),
        },
        "user_text": (str(user_text).strip() if user_text else None),
    }


# ==========================================================
# RENDER
# ==========================================================

_HEADINGS = {
    "en": {
        "title": "Comparison of the two attached images",
        "roles": (
            "Image A is the appearance reference; image B is the target "
            "building and stays the geometry authority. No render was executed."
        ),
        "differs": "WHAT DIFFERS",
        "shared": "WHAT THEY SHARE",
        "not_comparable": "NOT COMPARABLE FROM THIS EVIDENCE",
        "evidence": "OBSERVED EVIDENCE",
        "site": "TEMPORARY OBJECTS AND SITE CONTEXT (not architecture)",
        "limits": "LIMITS OF THIS COMPARISON",
        "none": "(none)",
        "unavailable": (
            "The vision analysis did not return a usable result for {sides}, so "
            "no comparison is asserted. The images were received; the failure is "
            "in the analysis stage, not in the attachment."
        ),
        "partial": (
            "Only one side produced a usable analysis, so no difference is "
            "asserted."
        ),
        "not_comparable_line": "{label}: A = {a}; B = {b}",
        "not_comparable_missing": "no value reported",
    },
    "fa": {
        "title": "مقایسه دو تصویر پیوست",
        "roles": (
            "تصویر A مرجع ظاهر است؛ تصویر B ساختمان هدف و مرجع هندسه می‌ماند. "
            "هیچ رندری اجرا نشد."
        ),
        "differs": "تفاوت‌ها",
        "shared": "وجوه مشترک",
        "not_comparable": "قابل مقایسه نیست (بر پایه این شواهد)",
        "evidence": "شواهد مشاهده‌شده",
        "site": "اشیای موقت و زمینه سایت (معماری نیست)",
        "limits": "محدودیت‌های این مقایسه",
        "none": "(هیچ)",
        "unavailable": (
            "تحلیل بینایی برای {sides} نتیجه قابل استفاده‌ای برنگرداند، بنابراین "
            "هیچ مقایسه‌ای ادعا نمی‌شود. تصاویر دریافت شده‌اند؛ اشکال در مرحله "
            "تحلیل است، نه در پیوست تصویر."
        ),
        "partial": (
            "فقط یک طرف تحلیل قابل استفاده داشت، بنابراین هیچ تفاوتی ادعا نمی‌شود."
        ),
        "not_comparable_line": "{label}: A = {a}؛ B = {b}",
        "not_comparable_missing": "مقداری گزارش نشده",
    },
}


def _language(value):

    if not value:

        return "en"

    return "fa" if str(value).lower().startswith("fa") else "en"


def render_comparison(comparison, language=None):
    """Render the comparison as text in the requested language."""

    comparison = comparison if isinstance(comparison, dict) else {}

    language = _language(
        language or comparison.get("language") or _detect_language(comparison.get("user_text"))
    )

    words = _HEADINGS[language]

    status = comparison.get("status")

    lines = [words["title"], ""]

    lines.append(words["roles"])

    if status == "analysis_unavailable":

        missing = []

        if not comparison.get("a_analyzed"):

            missing.append("A")

        if not comparison.get("b_analyzed"):

            missing.append("B")

        lines.append("")

        lines.append(
            words["unavailable"].format(sides=" and ".join(missing) if missing else "both images")
        )

        return "\n".join(lines)

    if status == "partial":

        lines.append("")

        lines.append(words["partial"])

    def _facet_line(entry):

        label = (entry.get("label") or {}).get(language) or (entry.get("label") or {}).get("en")

        return "- " + str(label) + ": A = " + str(entry.get("A")) + "; B = " + str(
            entry.get("B")
        )

    for section_key, section_name in (
        ("differences", "differs"),
        ("shared", "shared"),
    ):

        entries = comparison.get(section_key) or []

        lines.append("")

        lines.append(words[section_name])

        if not entries:

            lines.append("- " + words["none"])

            continue

        for entry in entries:

            lines.append(_facet_line(entry))

    entries = comparison.get("not_comparable") or []

    if entries:

        lines.append("")

        lines.append(words["not_comparable"])

        for entry in entries:

            label = (entry.get("label") or {}).get(language) or (
                entry.get("label") or {}
            ).get("en")

            value_a = entry.get("A") or words["not_comparable_missing"]

            value_b = entry.get("B") or words["not_comparable_missing"]

            lines.append(
                words["not_comparable_line"].format(
                    label=label,
                    a=value_a,
                    b=value_b,
                )
            )

    # SITE_OBJECT_CLASSIFICATION_V1 — reported faithfully, never as
    # architecture. Only emitted when the analysis actually reported
    # something in these bands.
    site_objects = comparison.get("site_objects") or {}

    site_lines = []

    for side in ("A", "B"):

        classification = site_objects.get(side) or {}

        temporary = [
            entry.get("phrase")
            for entry in classification.get("temporary_objects") or []
        ]

        context = [
            entry.get("phrase")
            for entry in classification.get("site_context") or []
        ]

        if temporary:

            site_lines.append(
                side + " — " + (
                    "اشیای موقت ساخت: " if language == "fa"
                    else "temporary construction objects: "
                ) + "; ".join(str(item) for item in temporary[:6])
            )

        if context:

            site_lines.append(
                side + " — " + (
                    "زمینه سایت: " if language == "fa"
                    else "site context: "
                ) + "; ".join(str(item) for item in context[:6])
            )

    if site_lines:

        lines.append("")
        lines.append(words["site"])

        for entry in site_lines:
            lines.append("- " + entry)

    evidence = comparison.get("evidence") or {}
    lines.append("")

    lines.append(words["evidence"])

    for side in ("A", "B"):

        statements = list((evidence.get(side) or {}).get("statements") or [])

        if not statements:

            continue

        lines.append("")

        lines.append(side + ":")

        for statement in statements:

            lines.append("- " + str(statement))

    limits = []

    provenance = comparison.get("provenance") or {}

    for side in ("A", "B"):

        side_provenance = provenance.get(side) or {}

        for key in ("uncertainties", "perspective_limitations", "occlusions"):

            for item in side_provenance.get(key) or []:

                statement = side + ": " + str(item)

                if statement not in limits:

                    limits.append(statement)

    if limits:

        lines.append("")

        lines.append(words["limits"])

        for statement in limits:

            lines.append("- " + statement)

    return "\n".join(lines)


def _detect_language(text):

    if not text:

        return "en"

    persian = sum(1 for char in str(text) if "\u0600" <= char <= "\u06FF")

    return "fa" if persian > 0 else "en"
