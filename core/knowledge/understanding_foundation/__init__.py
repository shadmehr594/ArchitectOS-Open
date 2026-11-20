"""Architectural understanding foundation.

This package holds the transient, read-only boundaries that let ArchitectOS
extract ARCHITECTURAL MEANING from human-taught examples, check whether a NEW
space was genuinely understood, TEST whether the meaning TRANSFERS to a new,
unseen situation rather than being matched by vocabulary, and DERIVE an
ABSTRACT concept from teaching examples whose wording and surface conditions
differ.

    architectural_understanding_foundation_v1.py
        Human example  ->  architectural concept, rationale, uncertainty.

    architectural_understanding_validation_v1.py
        Known concepts + a NEW space  ->  analysis of whether the concept was
        understood, or whether only the words were matched.

    architectural_concept_transfer_test_v1.py
        Human teaching examples + UNSEEN cases  ->  a controlled test of
        whether the concept TRANSFERS from architectural conditions alone.
        Reports LEARNED/TRANSFERRED vs RECOGNIZED FROM WORDS vs NOT ENOUGH
        INFORMATION, and enforces leakage guards L1-L4.

    architectural_abstraction_learner_v1.py  (ABSTRACTION TEST V2, Phases 1-4)
        Differently-worded teaching examples  ->  a DERIVED candidate
        abstraction. Keeps Level 1 RAW, Level 2A FormalStructure and Level 2B
        InterpretiveHypothesis strictly separate; runs Modes F/H/R; never
        assigns the reserved evidence status; records a GIVEN/ENGINEERED/
        EMERGENT ledger so no engineered algorithm is reported as learning.

    architectural_abstraction_probe_v1.py  (ABSTRACTION TEST V2, Phases 5-6)
        A derived abstraction + UNSEEN cases  ->  the seven-state evidence
        verdict. Runs nine adversarial probes, audits leakage, compares modes,
        runs Blind Relearning WITHOUT a semantic comparator, and grants the
        reserved CONCEPTUAL_ABSTRACTION_EVIDENCE status ONLY on a full pass.

    why_condition_abstraction/  (WHY / CONDITION ABSTRACTION EXPERIMENT V3)
        A SEPARATE, ISOLATED experiment. V2 proved that its invariants were
        literal stems and that cross-vocabulary stability was not demonstrated,
        so V3 rebuilds the question around architectural CONDITIONS plus the
        human's own WHY, and separates two claims that V2 had merged:

          MODE P  representation-dependent generalization over a PREDEFINED
                  relational vocabulary. Ceiling LEVEL_B. Can never report an
                  emergent pattern.
          MODE E  emergent relational structure. Receives NO architectural
                  relation vocabulary, derives relation slots from the corpus,
                  and reports PREDEFINED-REPRESENTATION-DEPENDENCE honestly
                  when it cannot.

        It emits all eleven failure modes and a representation provenance
        ledger on every run, and treats fingerprint equality as a STABILITY
        measurement rather than as learning evidence.

        V2 IS FROZEN. The V3 package imports nothing from the V2 modules above;
        the V2 vocabulary is on V3's Mode-E forbidden list so that V2's
        engineering cannot be inherited under a new name.

None of these boundaries draws, models, renders, or produces a design. There
is no CAD, BIM, IFC, geometry, layout-generation or rendering surface in this
package. None of them imports production ArchitectOS.
"""
