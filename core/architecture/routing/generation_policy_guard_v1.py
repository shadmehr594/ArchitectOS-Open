"""ARCHITECTOS INTERNAL GENERATOR GUARDRAIL — generation policy + bypass guard.

LOCKED PRODUCT DECISION
-----------------------
HouseDiffusion is the PRIMARY ArchitectOS plan generator under
``HOUSE_DIFFUSION_GENERATION_POLICY_V1``:

    User / ArchitectOS Program
      -> HouseDiffusion
      -> HouseDiffusionAcceptedBaselineAdapterV1
      -> AcceptedArchitecturalBaselineEnvelopeV1
      -> Design-02 -> Design-03 -> Design-04 -> Design-05

The internal rule-based synthesis branch (LayoutReasoner /
SpatialPlacementReasoner / PlanModelReasoner / KnowledgeSpaceGenerator /
CoherentFloorPlanResolverV1 / ArchitecturalLayoutIntelligenceV1 and the
deterministic treemap partition) is NOT a primary plan generator. It may run
ONLY as:

* ``DIAGNOSTIC``          - explicit, isolated inspection/testing
* ``EXPLICIT_FALLBACK``   - explicitly authorised by policy, visibly recorded

This module is the GUARD. It belongs at the generator-selection / routing
boundary, never inside a reusable downstream module.

Failure code: ``PRIMARY_GENERATOR_BYPASS_DETECTED``.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


CONTRACT = "ArchitectosGenerationPolicyGuardV1"
VERSION = "1.0"

#: The locked generation policy. Primary plan generation is HouseDiffusion.
HOUSE_DIFFUSION_GENERATION_POLICY_V1 = "HOUSE_DIFFUSION_GENERATION_POLICY_V1"

#: Generator identities.
PRIMARY_GENERATOR_HOUSE_DIFFUSION = "HOUSE_DIFFUSION"
INTERNAL_GENERATOR = "ARCHITECTOS_INTERNAL"

#: Failure code raised when the internal generator is used as the normal
#: primary plan source while the HouseDiffusion policy is in force.
PRIMARY_GENERATOR_BYPASS_DETECTED = "PRIMARY_GENERATOR_BYPASS_DETECTED"

#: Invocation roles for the internal synthesis branch.
ROLE_PRIMARY = "PRIMARY"
ROLE_EXPLICIT_FALLBACK = "EXPLICIT_FALLBACK"
ROLE_DIAGNOSTIC = "DIAGNOSTIC"

ROLES = (ROLE_PRIMARY, ROLE_EXPLICIT_FALLBACK, ROLE_DIAGNOSTIC)

#: Reason codes for a recorded fallback.
FALLBACK_REASON_ROUTE_NOT_WIRED = "HOUSE_DIFFUSION_ROUTE_NOT_WIRED"
FALLBACK_REASON_PRIMARY_UNAVAILABLE = "HOUSE_DIFFUSION_UNAVAILABLE"
FALLBACK_REASON_PRIMARY_FAILED = "HOUSE_DIFFUSION_GENERATION_FAILED"

#: Modules that make up the internal rule-based plan-synthesis branch.
INTERNAL_GENERATOR_MODULES = (
    "core.architecture.brain.architectural_brain",
    "core.architecture.reasoning.layout_reasoner",
    "core.architecture.reasoning.spatial_placement_reasoner",
    "core.architecture.reasoning.plan_model_reasoner",
    "core.architecture.reasoning.knowledge_space_generator",
    "core.architecture.reasoning.layout_regeneration_reasoner_v1",
    "core.architecture.reasoning.coherent_floor_plan_resolver_v1",
    "core.architecture.reasoning.architectural_layout_intelligence_v1",
)

#: Downstream ArchitectOS intelligence that stays ACTIVE. These are NOT part of
#: the internal synthesis branch and must never be marked legacy.
ACTIVE_DOWNSTREAM_INTELLIGENCE = (
    "AcceptedArchitecturalBaselineEnvelopeV1",
    "Design-02",
    "Design-03",
    "Design-04",
    "Design-05",
    "semantic_validation",
    "opening_privacy_site_intelligence",
    "floor_roof_interpretation",
    "structural_readiness",
)


class PrimaryGeneratorBypassError(RuntimeError):
    """Raised when the internal generator is selected as the normal primary source."""

    code = PRIMARY_GENERATOR_BYPASS_DETECTED


@dataclass(frozen=True)
class GenerationPolicy:
    """Explicit generation policy: who is primary, and whether fallback is allowed."""

    policy_id: str
    primary_generator: str
    fallback_authorized: bool
    fallback_reason: str | None = None
    notes: str = ""

    @property
    def is_house_diffusion(self) -> bool:
        return self.policy_id == HOUSE_DIFFUSION_GENERATION_POLICY_V1


#: The locked production policy.
#:
#: HouseDiffusion is primary. The internal generator is authorised ONLY as an
#: explicit, recorded fallback while the HouseDiffusion runtime route is not yet
#: wired (see HOUSE-DIFFUSION-PRODUCTION-PATH-02, blocked at the
#: generated-candidate -> accepted-baseline contract boundary).
HOUSE_DIFFUSION_POLICY = GenerationPolicy(
    policy_id=HOUSE_DIFFUSION_GENERATION_POLICY_V1,
    primary_generator=PRIMARY_GENERATOR_HOUSE_DIFFUSION,
    fallback_authorized=True,
    fallback_reason=FALLBACK_REASON_ROUTE_NOT_WIRED,
    notes=(
        "HouseDiffusion is the locked primary plan generator. Internal synthesis "
        "runs only as an explicit, recorded fallback until the HouseDiffusion "
        "runtime route is wired."
    ),
)

#: A legacy policy where the internal generator IS the primary source. Only
#: selectable explicitly; never the production default.
LEGACY_INTERNAL_POLICY = GenerationPolicy(
    policy_id="ARCHITECTOS_LEGACY_INTERNAL_GENERATION_POLICY",
    primary_generator=INTERNAL_GENERATOR,
    fallback_authorized=False,
    notes="Legacy compatibility only. Not the production policy.",
)

DEFAULT_POLICY = HOUSE_DIFFUSION_POLICY


def resolve_policy(policy: GenerationPolicy | str | None) -> GenerationPolicy:
    """Resolve a policy id/object to a GenerationPolicy. Defaults to locked policy."""
    if policy is None:
        return DEFAULT_POLICY
    if isinstance(policy, GenerationPolicy):
        return policy
    if isinstance(policy, str):
        if policy == HOUSE_DIFFUSION_GENERATION_POLICY_V1:
            return HOUSE_DIFFUSION_POLICY
        if policy == LEGACY_INTERNAL_POLICY.policy_id:
            return LEGACY_INTERNAL_POLICY
        return GenerationPolicy(policy_id=policy,
                                primary_generator=PRIMARY_GENERATOR_HOUSE_DIFFUSION,
                                fallback_authorized=False)
    raise TypeError(f"unsupported generation policy: {policy!r}")


def guard_internal_plan_generation(
    *,
    invocation_role: str = ROLE_PRIMARY,
    generation_policy: GenerationPolicy | str | None = None,
    fallback_authorized: bool | None = None,
    fallback_reason: str | None = None,
    primary_generator_attempted: bool = False,
    primary_generator_error: str | None = None,
    source: str = "",
) -> dict[str, Any]:
    """Enforce the generation policy for an internal-generator invocation.

    ``invocation_role`` defaults to ``PRIMARY`` on purpose: a call site that does
    not declare why it is running the internal generator is treated as claiming
    the primary production role and therefore FAILS.

    Returns the runtime metadata to attach to the result. Raises
    ``PrimaryGeneratorBypassError`` (code ``PRIMARY_GENERATOR_BYPASS_DETECTED``)
    when the internal generator would run as the normal primary source under the
    HouseDiffusion policy, or as an unauthorised fallback.
    """
    policy = resolve_policy(generation_policy)

    if invocation_role not in ROLES:
        raise ValueError(
            f"unknown invocation_role {invocation_role!r}; expected one of {ROLES}")

    base: dict[str, Any] = {
        "generation_policy": policy.policy_id,
        "primary_generator": policy.primary_generator,
        "internal_generator_role": invocation_role,
        "source": source,
    }

    # ---- DIAGNOSTIC: explicit, isolated use. Never claims production output.
    if invocation_role == ROLE_DIAGNOSTIC:
        return {
            **base,
            "fallback_used": False,
            "fallback_reason": None,
            "primary_generator_attempted": False,
            "primary_generator_error": None,
            "production_output": False,
        }

    # ---- PRIMARY: only legal when the policy's primary generator IS internal.
    if invocation_role == ROLE_PRIMARY:
        if policy.is_house_diffusion:
            raise PrimaryGeneratorBypassError(
                f"{PRIMARY_GENERATOR_BYPASS_DETECTED}: internal generator "
                f"({INTERNAL_GENERATOR}) selected as the normal primary plan source "
                f"while generation_policy={policy.policy_id} locks "
                f"{PRIMARY_GENERATOR_HOUSE_DIFFUSION} as primary. "
                f"source={source or 'unspecified'}")
        return {
            **base,
            "fallback_used": False,
            "fallback_reason": None,
            "primary_generator_attempted": False,
            "primary_generator_error": None,
            "production_output": True,
        }

    # ---- EXPLICIT_FALLBACK: requires authorisation, and is always recorded.
    authorized = policy.fallback_authorized if fallback_authorized is None else bool(
        fallback_authorized)
    if not authorized:
        raise PrimaryGeneratorBypassError(
            f"{PRIMARY_GENERATOR_BYPASS_DETECTED}: internal generator "
            f"({INTERNAL_GENERATOR}) invoked as an UNAUTHORISED fallback. "
            f"generation_policy={policy.policy_id} does not authorise fallback. "
            f"source={source or 'unspecified'}")

    return {
        **base,
        "fallback_used": True,
        "fallback_generator": INTERNAL_GENERATOR,
        "fallback_reason": fallback_reason or policy.fallback_reason
        or FALLBACK_REASON_PRIMARY_UNAVAILABLE,
        "fallback_authorized": True,
        "primary_generator_attempted": bool(primary_generator_attempted),
        "primary_generator_error": primary_generator_error,
        "production_output": True,
    }


def internal_generator_metadata(**kwargs: Any) -> dict[str, Any]:
    """Convenience wrapper. See ``guard_internal_plan_generation``."""
    return guard_internal_plan_generation(**kwargs)


def role_marker(entrypoint: str, *, module: str) -> dict[str, Any]:
    """The declared role of an internal-generator entrypoint (source marker)."""
    return {
        "module": module,
        "entrypoint": entrypoint,
        "ARCHITECTOS_GENERATION_ROLE": "DIAGNOSTIC_OR_EXPLICIT_FALLBACK",
        "PRODUCTION_PRIMARY": False,
        "primary_generator": PRIMARY_GENERATOR_HOUSE_DIFFUSION,
        "generation_policy": HOUSE_DIFFUSION_GENERATION_POLICY_V1,
    }


__all__ = [
    "CONTRACT", "VERSION",
    "HOUSE_DIFFUSION_GENERATION_POLICY_V1",
    "PRIMARY_GENERATOR_HOUSE_DIFFUSION", "INTERNAL_GENERATOR",
    "PRIMARY_GENERATOR_BYPASS_DETECTED",
    "ROLE_PRIMARY", "ROLE_EXPLICIT_FALLBACK", "ROLE_DIAGNOSTIC", "ROLES",
    "FALLBACK_REASON_ROUTE_NOT_WIRED", "FALLBACK_REASON_PRIMARY_UNAVAILABLE",
    "FALLBACK_REASON_PRIMARY_FAILED",
    "INTERNAL_GENERATOR_MODULES", "ACTIVE_DOWNSTREAM_INTELLIGENCE",
    "PrimaryGeneratorBypassError", "GenerationPolicy",
    "HOUSE_DIFFUSION_POLICY", "LEGACY_INTERNAL_POLICY", "DEFAULT_POLICY",
    "resolve_policy", "guard_internal_plan_generation", "internal_generator_metadata",
    "role_marker",
]
