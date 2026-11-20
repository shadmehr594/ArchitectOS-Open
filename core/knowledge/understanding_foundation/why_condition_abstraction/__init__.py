"""V3 - WHY / CONDITION ABSTRACTION EXPERIMENT.

A separate, isolated experiment. It exists because V2 did not demonstrate
conceptual abstraction: V2's invariants turned out to be literal stem tokens,
its invariance criterion was lexical at its core, zero-word transfer was never
shown, and same-structure/different-meaning cases were not separated. Its own
report is honest about this and its own probe said
``ABSTRACTION_STABILITY_NOT_DEMONSTRATED``.

V2 IS FROZEN. This package does not import, reuse, subclass, copy or depend on
any V2 module, constant or algorithm. The V2 vocabulary is on V3's Mode-E
forbidden list precisely so that V2's engineering cannot be inherited under a
new name.

What V3 asks
------------

    Can an abstraction be built from ARCHITECTURAL CONDITIONS plus the human's
    own WHY, in a way that does not depend on the vocabulary or the surface
    structure of the examples?

And, more sharply:

    If it can only be built by supplying a predefined architectural relation
    vocabulary, then what has been demonstrated is REPRESENTATION DEPENDENCE,
    not emergence - and that is a valid, reportable result.

Two modes, separated so each claim can fail on its own
------------------------------------------------------

MODE P
    Representation-dependent generalization. Receives a predefined relational
    vocabulary (declared in ``v3_contracts``). Ceiling: LEVEL_B
    STRUCTURED_GENERALIZATION. It may NEVER report a novel relational pattern or
    conceptual abstraction evidence.

MODE E
    Emergent relational structure. Receives NO architectural relation
    vocabulary - not one term - only generic relational scaffolding. It must
    DERIVE relation slots from the corpus, or honestly report that it could not.
    When it cannot, the emitted failure is
    ``PREDEFINED-REPRESENTATION-DEPENDENCE``.

Modules
-------

``v3_contracts``
    The single source of shared vocabulary, the Mode-E firewall, the evidence
    hierarchy, the eleven failure modes, and the representation provenance
    ledger.

``v3_condition_model_v1``
    ``V3ConditionV1``: one architectural condition, with a generic relation
    scaffold, a verbatim WHY, and provenance on every element.

``v3_why_grounding_v1``
    ``V3WhyGroundingV1``: how a condition is bound to a human's reason, and how
    that binding is judged. The WHY is first-class, never an afterthought.

``v3_abstraction_learner_v1``
    Phases 1-4. Produces ``V3WhyGroundedAbstractionV1`` in Mode P and/or Mode E.

``v3_abstraction_probe_v1``
    Phases 5-6. Unseen reasoning, the eleven mandatory failure modes, leakage
    audit, and the evidence-level verdict.

``v3_harness_v1``
    A thin, deterministic runner for one full P/E comparison.

Nothing produced here is a learned model, a design solution, a rule, a geometry
intent, a BIM entity, a render, or a memory. Every boundary is transient,
read-only, non-persistent and non-learning.
"""

from . import v3_contracts  # noqa: F401

__all__ = ["v3_contracts"]

__package_kind__ = "experiment"
__frozen_dependency__ = None
__isolated_from_v2__ = True
__produces__ = "semantic_representation_only"
