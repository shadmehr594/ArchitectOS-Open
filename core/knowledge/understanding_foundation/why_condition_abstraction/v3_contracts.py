"""Shared, immutable contract surface for the V3 experiment.

WHY / CONDITION ABSTRACTION EXPERIMENT V3.

This module is the ONE place where V3's shared vocabulary lives. It exists so
that the leak firewall between the two modes can be enforced in a single,
auditable location rather than being re-declared by each boundary.

Two modes, never blurred
------------------------

MODE P  representation-dependent generalization.
        Receives a PREDEFINED relational vocabulary. Its ceiling is
        STRUCTURED_GENERALIZATION and it may NEVER report emergent relational
        abstraction. Everything it produces is ENGINEERED or DERIVED.

MODE E  emergent relational structure.
        Receives NO architectural relation vocabulary - not one term. It gets
        only generic relational scaffolding (subject / object / slot / polarity
        / modality / provenance / WHY). Relation slots must be DERIVED from the
        corpus. If it cannot derive one, it must say so honestly, and the
        experiment is ALLOWED TO FAIL with PREDEFINED-REPRESENTATION-DEPENDENCE.

The distinction is the whole point of V3: V2 proved that a pipeline with
predefined formal vocabulary can generalize structurally, but never showed that
the RELATION was learned rather than engineered. V3 separates the two claims so
each can fail on its own.

Isolation
---------

This package is structurally isolated from the frozen V2 package. It does not
import, reuse, subclass or copy any V2 module, constant or algorithm. The
relation vocabulary that V2 legitimately uses (actor/action/object/boundary,
access/separation/control/exposure) is on V3's Mode-E forbidden list, because a
Mode-E learner that had those words would not be deriving anything.

Nothing here is a learned model, a design rule, a geometry intent, or a memory
record. All boundaries are transient, read-only and non-learning.
"""

# --------------------------------------------------------------------------- #
# Boundary contracts
# --------------------------------------------------------------------------- #

PACKAGE = "why_condition_abstraction"
PACKAGE_VERSION = "1.0"

CONDITION_CONTRACT = "V3ConditionV1"
CONDITION_VERSION = "1.0"

WHY_GROUNDING_CONTRACT = "V3WhyGroundingV1"
WHY_GROUNDING_VERSION = "1.0"

LEARNER_CONTRACT = "V3AbstractionLearnerV1"
LEARNER_VERSION = "1.0"
LEARNER_DIRECTIVE_CONTRACT = "V3AbstractionDirectiveV1"
LEARNER_DIRECTIVE_VERSION = "1.0"

PROBE_CONTRACT = "V3AbstractionProbeV1"
PROBE_VERSION = "1.0"
PROBE_DIRECTIVE_CONTRACT = "V3AbstractionProbeDirectiveV1"
PROBE_DIRECTIVE_VERSION = "1.0"

ABSTRACTION_CONTRACT = "V3WhyGroundedAbstractionV1"
ABSTRACTION_VERSION = "1.0"

NOVEL_PATTERN_CONTRACT = "V3NovelRelationalPatternV1"
NOVEL_PATTERN_VERSION = "1.0"

TEST_SUBJECT = "why-grounded abstraction over architectural conditions and human reasons"

DEMONSTRATION_LABEL = (
    "controlled why-grounded condition abstraction over human teaching examples"
)

# --------------------------------------------------------------------------- #
# Modes - the two claims, separated on purpose
# --------------------------------------------------------------------------- #

MODE_P = "P"
MODE_E = "E"
MODES = (MODE_P, MODE_E)

MODE_DESCRIPTIONS = {
    MODE_P:
        "representation-dependent generalization over a predefined relational "
        "vocabulary; ceiling STRUCTURED_GENERALIZATION; can never report a "
        "novel relational pattern",
    MODE_E:
        "emergent relational structure; receives NO architectural relation "
        "vocabulary and must DERIVE relation slots from the corpus, or honestly "
        "fail",
}

# --------------------------------------------------------------------------- #
# The evidence hierarchy. Level E is the only conceptual level, and it is
# reachable ONLY if predefined-vocabulary dependence has been measured and
# reported. MODE P can never exceed LEVEL B.
# --------------------------------------------------------------------------- #

LEVEL_A = "LEVEL_A_ENGINEERED_REPRESENTATION"
LEVEL_B = "LEVEL_B_STRUCTURED_GENERALIZATION"
LEVEL_C = "LEVEL_C_WHY_GROUNDED_GENERALIZATION"
LEVEL_D = "LEVEL_D_EMERGENT_RELATIONAL_ABSTRACTION"
LEVEL_E = "LEVEL_E_CONCEPTUAL_ABSTRACTION_EVIDENCE"

EVIDENCE_LEVELS = (LEVEL_A, LEVEL_B, LEVEL_C, LEVEL_D, LEVEL_E)

EVIDENCE_LEVEL_RANK = {
    LEVEL_A: 0,
    LEVEL_B: 1,
    LEVEL_C: 2,
    LEVEL_D: 3,
    LEVEL_E: 4,
}

# The level each mode is ALLOWED to reach. This is a hard ceiling, enforced by
# the learner and re-checked by the probe.
MODE_CEILING = {
    MODE_P: LEVEL_B,
    MODE_E: LEVEL_E,
}

# The level MODE P must never exceed, stated as its own constant so a test can
# assert it without reading the ceiling table.
MODE_P_CEILING = LEVEL_B

# --------------------------------------------------------------------------- #
# Epistemic statuses - the closed scale
# --------------------------------------------------------------------------- #

STATUS_ENGINEERED = "ENGINEERED"
STATUS_DERIVED = "DERIVED"
STATUS_GENERALIZED = "GENERALIZED"
STATUS_CONCEPTUAL_ABSTRACTION_EVIDENCE = "CONCEPTUAL_ABSTRACTION_EVIDENCE"
STATUS_NOT_DEMONSTRATED = "NOT_DEMONSTRATED"
STATUS_NOVEL_RELATIONAL_PATTERN = "NOVEL_RELATIONAL_PATTERN"

EPISTEMIC_STATUSES = (
    STATUS_ENGINEERED,
    STATUS_DERIVED,
    STATUS_GENERALIZED,
    STATUS_CONCEPTUAL_ABSTRACTION_EVIDENCE,
    STATUS_NOT_DEMONSTRATED,
    STATUS_NOVEL_RELATIONAL_PATTERN,
)

# The statuses a LEARNER boundary may assign. The reserved evidence status is
# deliberately absent: only the probe boundary may grant it.
LEARNER_ASSIGNABLE_STATUSES = (
    STATUS_ENGINEERED,
    STATUS_DERIVED,
    STATUS_GENERALIZED,
    STATUS_NOT_DEMONSTRATED,
)

RESERVED_EVIDENCE_STATUS = STATUS_CONCEPTUAL_ABSTRACTION_EVIDENCE

# --------------------------------------------------------------------------- #
# Provenance of every representation element. This is the audit's central
# requirement: nothing may enter a representation without its origin declared.
# --------------------------------------------------------------------------- #

ORIGIN_ENGINEERED = "ENGINEERED"          # supplied by this code, before data
ORIGIN_DERIVED = "DERIVED"                # computed from the corpus by a rule
ORIGIN_EMERGENT = "EMERGENT"              # contingent on corpus content alone

REPRESENTATION_ORIGINS = (
    ORIGIN_ENGINEERED,
    ORIGIN_DERIVED,
    ORIGIN_EMERGENT,
)

# --------------------------------------------------------------------------- #
# Generic relational scaffolding. This is the ONLY vocabulary MODE E receives.
# None of these terms names an architectural relation: they are placeholders a
# relation can be built INTO, not relations themselves.
# --------------------------------------------------------------------------- #

GENERIC_SCAFFOLD_FIELDS = (
    "subject",
    "object",
    "relation_slot",
    "scope_slot",
    "polarity",
    "modality",
    "provenance",
    "WHY",
)

# The scaffolding must never be mistaken for a derived relation.
SCAFFOLD_IS_NOT_A_RELATION = True

# --------------------------------------------------------------------------- #
# THE MODE-E FIREWALL.
#
# MODE E must not receive a single architectural relation word. These are the
# terms that carry an architectural relation judgement. They are permitted in
# MODE P (which is explicitly representation-dependent and says so), and are
# forbidden inside any Mode-E-produced representation.
#
# The list includes V2's formal + interpretive vocabulary, so that V3 cannot
# smuggle V2's engineering back in under a new name.
# --------------------------------------------------------------------------- #

MODE_E_FORBIDDEN_RELATION_TERMS = (
    # V3-proposed Mode P relation vocabulary
    "encounter",
    "access",
    "containment",
    "adjacency",
    "sequence",
    "separation",
    "modality_of_action",
    "persistence",
    # V3-proposed Mode P scope vocabulary
    "domain_containment",
    "temporal_sequence",
    "boundary_crossing",
    "observational_line",
    "acoustic_path",
    # V2 interpretive axes - forbidden here so V3 cannot inherit V2
    "control",
    "exposure",
    # architectural role / semantic labels
    "privacy",
    "territory",
    "threshold",
    "prospect",
    "refuge",
    "orientation",
    "hierarchy",
    "circulation",
    "enclosure",
    "permeability",
)

# MODE P's declared, predefined relation vocabulary. Declared here ONLY so the
# audit can prove Mode E never receives it. Loading this in Mode E is a hard
# error (see `assert_mode_e_receives_no_relation_vocabulary`).
MODE_P_RELATION_VOCABULARY = (
    "encounter",
    "access",
    "containment",
    "adjacency",
    "sequence",
    "separation",
    "modality_of_action",
    "persistence",
)

MODE_P_SCOPE_VOCABULARY = (
    "domain_containment",
    "temporal_sequence",
    "boundary_crossing",
    "observational_line",
    "acoustic_path",
)

# --------------------------------------------------------------------------- #
# The eleven mandatory failure modes. EVERY run emits ALL ELEVEN, each with an
# explicit measured / not-measured state. A failure mode may not be omitted, and
# may not be reported as passed when it was never actually exercised.
# --------------------------------------------------------------------------- #

FAILURE_LEXICAL_DEPENDENCE = "LEXICAL_DEPENDENCE"
FAILURE_STRUCTURAL_DEPENDENCE = "STRUCTURAL_DEPENDENCE"
FAILURE_WHY_IGNORED = "WHY_IGNORED"
FAILURE_SAME_STRUCTURE_CONFLATION = "SAME_STRUCTURE_CONFLATION"
FAILURE_DIFFERENT_FORM = "DIFFERENT_FORM_FAILURE"
FAILURE_COUNTERFACTUAL = "COUNTERFACTUAL_FAILURE"
FAILURE_NOVEL_COMBINATION = "NOVEL_COMBINATION_FAILURE"
FAILURE_UNCERTAINTY_COLLAPSE = "UNCERTAINTY_COLLAPSE"
FAILURE_EVALUATION_LEAKAGE = "EVALUATION_LEAKAGE"
FAILURE_HIDDEN_SEMANTIC_MATCHER = "HIDDEN_SEMANTIC_MATCHER"
FAILURE_PREDEFINED_REPRESENTATION_DEPENDENCE = "PREDEFINED-REPRESENTATION-DEPENDENCE"

FAILURE_MODES = (
    FAILURE_LEXICAL_DEPENDENCE,
    FAILURE_STRUCTURAL_DEPENDENCE,
    FAILURE_WHY_IGNORED,
    FAILURE_SAME_STRUCTURE_CONFLATION,
    FAILURE_DIFFERENT_FORM,
    FAILURE_COUNTERFACTUAL,
    FAILURE_NOVEL_COMBINATION,
    FAILURE_UNCERTAINTY_COLLAPSE,
    FAILURE_EVALUATION_LEAKAGE,
    FAILURE_HIDDEN_SEMANTIC_MATCHER,
    FAILURE_PREDEFINED_REPRESENTATION_DEPENDENCE,
)

FAILURE_MODE_DESCRIPTIONS = {
    FAILURE_LEXICAL_DEPENDENCE:
        "the derived relation survives only because the same surface words "
        "recur; renaming every filler must not change it",
    FAILURE_STRUCTURAL_DEPENDENCE:
        "the derived relation survives only because the same clause shape "
        "recurs; the same idea in a different form must still be reachable",
    FAILURE_WHY_IGNORED:
        "swapping only the WHY, leaving conditions intact, must change the "
        "derivation; if it does not, the WHY was never used",
    FAILURE_SAME_STRUCTURE_CONFLATION:
        "two conditions with the same scaffolding but different WHYs must not "
        "collapse to the same relation",
    FAILURE_DIFFERENT_FORM:
        "the same idea expressed in a different form must not be lost",
    FAILURE_COUNTERFACTUAL:
        "changing one condition and holding the WHY fixed must be traceable in "
        "the derivation",
    FAILURE_NOVEL_COMBINATION:
        "a combination of conditions never seen together must be handled "
        "explicitly, not silently dropped",
    FAILURE_UNCERTAINTY_COLLAPSE:
        "the abstraction must retain alternatives and uncertainty rather than "
        "reporting one certain reading",
    FAILURE_EVALUATION_LEAKAGE:
        "no expected answer, concept name or evaluation key may reach the "
        "learner, and none may be read before the verdict",
    FAILURE_HIDDEN_SEMANTIC_MATCHER:
        "no stem, synonym table, role map, threshold, keyword list, embedding "
        "or similarity library may silently carry the derivation",
    FAILURE_PREDEFINED_REPRESENTATION_DEPENDENCE:
        "if a Mode-E result is reproducible only by reintroducing a predefined "
        "architectural relation word, the experiment has demonstrated "
        "representation dependence, not emergence",
}

FAILURE_MODE_STATES = (
    "NOT_EXERCISED",
    "MEASURED_PASS",
    "MEASURED_FAIL",
    "INCONCLUSIVE",
)

# --------------------------------------------------------------------------- #
# Fingerprint semantics. A fingerprint measures STABILITY of a representation.
# It is NEVER evidence of learning. V2 used fingerprint equality as if it were
# such evidence; V3 does not.
# --------------------------------------------------------------------------- #

FINGERPRINT_SEMANTICS = "representation_stability"

FINGERPRINT_IS_NOT_LEARNING_EVIDENCE = True

# --------------------------------------------------------------------------- #
# Contracts that must never reach this boundary. Identical in spirit to V2's
# list: V3 is a semantic boundary, not a geometry, CAD, BIM or render boundary.
# --------------------------------------------------------------------------- #

FORBIDDEN_CONTRACTS = (
    "ArchitecturalCADDrawingV1",
    "ArchitecturalDXFDrawingV1",
    "ArchitecturalDWGDrawingV1",
    "ArchitecturalBIMEntityV1",
    "ArchitecturalIFCEntityV1",
    "ArchitecturalRenderingOutputV1",
    "ArchitecturalGeometryIntentV1",
    "ArchitecturalMemoryRecordV1",
    "ArchitecturalVisionReportV1",
    "ArchitecturalDesignReasoningResultV1",
    "ArchitecturalDesignReasoningInputV1",
    "ArchitecturalSpatialReasoningCandidateV1",
    "ArchitecturalSemanticGraphV1",
    "ArchitecturalLayoutIntentResolverV1",
    "ProgramIntentResolutionV1",
    "ImageIntentV1",
    "SiteIntentV1",
    "ArchitecturalUnderstandingV1",
    "ArchitecturalUnderstandingV2",
    "ArchitecturalObservationV1",
    "ArchitecturalConceptOntologyV1",
    "ArchitecturalConceptRelationshipV1",
)

# Keys that carry an expected answer. They may never appear in learner-visible
# input, and may never be READ before the verdict is reached.
EVALUATION_KEYS = (
    "expected",
    "expected_outcome",
    "expected_concept",
    "expected_label",
    "expected_relation",
    "answer",
    "ground_truth",
    "target",
    "target_relation",
    "target_skeleton",
    "intended_concept",
    "intended_relation",
    "intended_invariant",
    "evaluation",
    "evaluation_expectations",
    "author_reference",
)

# Terms this package must never emit as its own authored language. These are
# production-domain terms, not research terms: V3 produces a semantic
# representation and nothing else.
FORBIDDEN_EMITTED_TERMS = (
    "design_solution",
    "design_rule",
    "layout",
    "placement",
    "geometry",
    "dimension",
    "cad",
    "dwg",
    "dxf",
    "bim",
    "ifc",
    "render",
    "optimal",
    "recommended",
    "synonym",
    "embedding",
)

# --------------------------------------------------------------------------- #
# Non-claims. Emitted by every boundary, on every run.
# --------------------------------------------------------------------------- #

REQUIRED_NON_CLAIMS = {
    "not_a_learned_model": True,
    "not_proof_of_human_understanding": True,
    "not_a_design_solution": True,
    "not_a_rule": True,
    "not_geometry": True,
    "not_bim": True,
    "not_render": True,
    "not_memory": True,
    "not_persistent": True,
    "engineered_algorithm_is_not_learning": True,
    "class_name_does_not_imply_learning": True,
    "learned_flag_alone_does_not_prove_learning": True,
    "reserved_status_requires_full_gate_pass": True,
    "fingerprint_equality_is_not_learning_evidence": True,
    "mode_p_cannot_report_novel_relational_pattern": True,
    "mode_e_receives_no_architectural_relation_vocabulary": True,
    "predefined_representation_dependence_is_a_valid_result": True,
}

# --------------------------------------------------------------------------- #
# The ENGINEERED / DERIVED / EMERGENT ledger, declared once for the package.
#
# ENGINEERED  - machinery this code supplies before seeing any data.
# DERIVED     - computed from the corpus by an engineered rule.
# EMERGENT    - contingent on corpus content; nothing guarantees it appears.
# --------------------------------------------------------------------------- #

ENGINEERING_LEDGER = {
    "tokenizer": ORIGIN_ENGINEERED,
    "clause_splitter": ORIGIN_ENGINEERED,
    "condition_extractor": ORIGIN_ENGINEERED,
    "generic_scaffold": ORIGIN_ENGINEERED,
    "slot_scaffold_shape": ORIGIN_ENGINEERED,
    "polarity_marker_table": ORIGIN_ENGINEERED,
    "modality_marker_table": ORIGIN_ENGINEERED,
    "why_connector_table": ORIGIN_ENGINEERED,
    "relation_slot_coherence_test": ORIGIN_ENGINEERED,
    "recurrence_algorithm": ORIGIN_ENGINEERED,
    "necessity_test": ORIGIN_ENGINEERED,
    "why_binding_algorithm": ORIGIN_ENGINEERED,
    "fingerprint_function": ORIGIN_ENGINEERED,
    # MODE P ONLY. These are engineered by definition, and are exactly what
    # MODE E is denied.
    "mode_p_predefined_relation_vocabulary": ORIGIN_ENGINEERED,
    "mode_p_predefined_scope_vocabulary": ORIGIN_ENGINEERED,
}

EMERGENT_LEDGER = {
    "derived_relation_slots": "contingent on corpus",
    "derived_scope_slots": "contingent on corpus",
    "surviving_why_grounded_invariants": "contingent on corpus",
    "necessity_determinations": "contingent on corpus",
    "why_bindings": "contingent on corpus",
    "plausible_alternatives": "contingent on corpus",
    "novel_relational_pattern": "contingent on corpus; may never appear",
    "abstraction_fingerprint": "contingent on corpus",
}

# --------------------------------------------------------------------------- #
# Representation provenance ledger.
#
# Every representation ELEMENT V3 can put into a value is listed with the
# origin of its introduction. This is what the audit demanded: no element may
# enter a representation without its provenance being declared up front.
#
# `introduced_by` names the module responsible. `may_be_mode_e` states whether
# the element is allowed to appear in a Mode-E representation at all.
# --------------------------------------------------------------------------- #

REPRESENTATION_PROVENANCE_LEDGER = {
    # --- generic scaffolding: engineered shape, Mode-E permitted -------------
    "subject": {
        "origin": ORIGIN_ENGINEERED,
        "introduced_by": "v3_condition_model_v1 (generic scaffold)",
        "may_be_mode_e": True,
        "note": "a placeholder for whoever/whatever the condition is about; "
                "not an architectural role",
    },
    "object": {
        "origin": ORIGIN_ENGINEERED,
        "introduced_by": "v3_condition_model_v1 (generic scaffold)",
        "may_be_mode_e": True,
        "note": "a placeholder for the second participant; not a target-space",
    },
    "relation_slot": {
        "origin": ORIGIN_EMERGENT,
        "introduced_by": "v3_abstraction_learner_v1 (Mode E derivation)",
        "may_be_mode_e": True,
        "note": "the slot the relation is placed INTO. The SHAPE is engineered "
                "(it is a slot); the CONTENT is emergent. In Mode E it starts "
                "as null and may never be filled with a predefined "
                "architectural relation word.",
    },
    "scope_slot": {
        "origin": ORIGIN_EMERGENT,
        "introduced_by": "v3_abstraction_learner_v1 (Mode E derivation)",
        "may_be_mode_e": True,
        "note": "same as relation_slot: engineered slot, emergent content",
    },
    "polarity": {
        "origin": ORIGIN_DERIVED,
        "introduced_by": "v3_condition_model_v1 (marker table + text evidence)",
        "may_be_mode_e": True,
        "note": "derived from explicit negation markers present in the text; "
                "the marker table is engineered",
    },
    "modality": {
        "origin": ORIGIN_DERIVED,
        "introduced_by": "v3_condition_model_v1 (marker table + text evidence)",
        "may_be_mode_e": True,
        "note": "derived from explicit modality markers; the marker table is "
                "engineered",
    },
    "provenance": {
        "origin": ORIGIN_ENGINEERED,
        "introduced_by": "v3_condition_model_v1",
        "may_be_mode_e": True,
        "note": "every element records where it came from; the requirement to "
                "record it is engineered",
    },
    "WHY": {
        "origin": ORIGIN_DERIVED,
        "introduced_by": "v3_why_grounding_v1",
        "may_be_mode_e": True,
        "note": "the human's own reason, taken verbatim; the CONNECTOR table "
                "that finds it is engineered, the reason is not",
    },
    # --- MODE P only: engineered architectural relation vocabulary ----------
    "predefined_relation_kind": {
        "origin": ORIGIN_ENGINEERED,
        "introduced_by": "v3_contracts.MODE_P_RELATION_VOCABULARY",
        "may_be_mode_e": False,
        "note": "one of encounter/access/containment/adjacency/sequence/"
                "separation/modality_of_action/persistence. ENGINEERED. "
                "Forbidden in Mode E.",
    },
    "predefined_scope_kind": {
        "origin": ORIGIN_ENGINEERED,
        "introduced_by": "v3_contracts.MODE_P_SCOPE_VOCABULARY",
        "may_be_mode_e": False,
        "note": "one of domain_containment/temporal_sequence/boundary_crossing/"
                "observational_line/acoustic_path. ENGINEERED. Forbidden in "
                "Mode E.",
    },
    # --- emergent content ---------------------------------------------------
    "derived_relation_slot": {
        "origin": ORIGIN_EMERGENT,
        "introduced_by": "v3_abstraction_learner_v1 (Mode E only)",
        "may_be_mode_e": True,
        "note": "a relation slot the corpus itself produced. Its appearance is "
                "contingent; it may never appear, and that is a legitimate "
                "experimental result.",
    },
    "why_grounded_invariant": {
        "origin": ORIGIN_EMERGENT,
        "introduced_by": "v3_abstraction_learner_v1",
        "may_be_mode_e": True,
        "note": "an invariant that survives across independent examples AND is "
                "bound to the humans' WHY",
    },
    "novel_relational_pattern": {
        "origin": ORIGIN_EMERGENT,
        "introduced_by": "v3_abstraction_learner_v1 (Mode E only)",
        "may_be_mode_e": True,
        "note": "a relational pattern not present in any initial vocabulary. "
                "MODE P may NEVER emit this.",
    },
    # --- engineered inference ----------------------------------------------
    "intended_effect": {
        "origin": ORIGIN_DERIVED,
        "introduced_by": "v3_condition_model_v1 (optional, is_inference=true)",
        "may_be_mode_e": True,
        "note": "an INFERRED effect, explicitly flagged as an inference; never "
                "presented as the human's own words",
    },
}


# --------------------------------------------------------------------------- #
# Module-level helpers
# --------------------------------------------------------------------------- #


def mode_e_forbidden_terms() -> tuple:
    """The complete set of terms Mode E must never receive or emit."""
    return tuple(MODE_E_FORBIDDEN_RELATION_TERMS)


def assert_mode_e_receives_no_relation_vocabulary(value) -> None:
    """Hard firewall: no architectural relation word may reach Mode E.

    Raises ValueError on the first forbidden term found. Called by the learner
    before Mode E touches any input, so a Mode-E run can never be silently
    assisted by a predefined relation word.
    """
    import json as _json

    blob = _json.dumps(value, sort_keys=True, default=str).lower()
    import re as _re

    for term in MODE_E_FORBIDDEN_RELATION_TERMS:
        if _re.search(r"(?<![a-z0-9_])" + _re.escape(term) + r"(?![a-z0-9_])",
                      blob):
            raise ValueError(
                "V3 Mode-E firewall: a predefined architectural relation "
                "vocabulary term reached Mode E: " + repr(term)
            )


def evidence_level_at_most(level: str, ceiling: str) -> bool:
    """Is `level` within `ceiling` on the evidence hierarchy?"""
    return EVIDENCE_LEVEL_RANK.get(level, -1) <= EVIDENCE_LEVEL_RANK.get(
        ceiling, -1
    )


def clamp_evidence_level(level: str, ceiling: str) -> str:
    """Never allow a reported level to exceed the mode's ceiling."""
    if evidence_level_at_most(level, ceiling):
        return level
    return ceiling


__all__ = [
    "PACKAGE", "PACKAGE_VERSION",
    "CONDITION_CONTRACT", "CONDITION_VERSION",
    "WHY_GROUNDING_CONTRACT", "WHY_GROUNDING_VERSION",
    "LEARNER_CONTRACT", "LEARNER_VERSION",
    "LEARNER_DIRECTIVE_CONTRACT", "LEARNER_DIRECTIVE_VERSION",
    "PROBE_CONTRACT", "PROBE_VERSION",
    "PROBE_DIRECTIVE_CONTRACT", "PROBE_DIRECTIVE_VERSION",
    "ABSTRACTION_CONTRACT", "ABSTRACTION_VERSION",
    "NOVEL_PATTERN_CONTRACT", "NOVEL_PATTERN_VERSION",
    "TEST_SUBJECT", "DEMONSTRATION_LABEL",
    "MODE_P", "MODE_E", "MODES", "MODE_DESCRIPTIONS",
    "LEVEL_A", "LEVEL_B", "LEVEL_C", "LEVEL_D", "LEVEL_E",
    "EVIDENCE_LEVELS", "EVIDENCE_LEVEL_RANK", "MODE_CEILING", "MODE_P_CEILING",
    "STATUS_ENGINEERED", "STATUS_DERIVED", "STATUS_GENERALIZED",
    "STATUS_CONCEPTUAL_ABSTRACTION_EVIDENCE", "STATUS_NOT_DEMONSTRATED",
    "STATUS_NOVEL_RELATIONAL_PATTERN",
    "EPISTEMIC_STATUSES", "LEARNER_ASSIGNABLE_STATUSES",
    "RESERVED_EVIDENCE_STATUS",
    "ORIGIN_ENGINEERED", "ORIGIN_DERIVED", "ORIGIN_EMERGENT",
    "REPRESENTATION_ORIGINS",
    "GENERIC_SCAFFOLD_FIELDS", "SCAFFOLD_IS_NOT_A_RELATION",
    "MODE_E_FORBIDDEN_RELATION_TERMS",
    "MODE_P_RELATION_VOCABULARY", "MODE_P_SCOPE_VOCABULARY",
    "FAILURE_MODES", "FAILURE_MODE_DESCRIPTIONS", "FAILURE_MODE_STATES",
    "FAILURE_LEXICAL_DEPENDENCE", "FAILURE_STRUCTURAL_DEPENDENCE",
    "FAILURE_WHY_IGNORED", "FAILURE_SAME_STRUCTURE_CONFLATION",
    "FAILURE_DIFFERENT_FORM", "FAILURE_COUNTERFACTUAL",
    "FAILURE_NOVEL_COMBINATION", "FAILURE_UNCERTAINTY_COLLAPSE",
    "FAILURE_EVALUATION_LEAKAGE", "FAILURE_HIDDEN_SEMANTIC_MATCHER",
    "FAILURE_PREDEFINED_REPRESENTATION_DEPENDENCE",
    "FINGERPRINT_SEMANTICS", "FINGERPRINT_IS_NOT_LEARNING_EVIDENCE",
    "FORBIDDEN_CONTRACTS", "EVALUATION_KEYS", "FORBIDDEN_EMITTED_TERMS",
    "REQUIRED_NON_CLAIMS", "ENGINEERING_LEDGER", "EMERGENT_LEDGER",
    "REPRESENTATION_PROVENANCE_LEDGER",
    "mode_e_forbidden_terms", "assert_mode_e_receives_no_relation_vocabulary",
    "evidence_level_at_most", "clamp_evidence_level",
]
