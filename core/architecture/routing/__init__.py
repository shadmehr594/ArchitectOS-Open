"""ArchitectOS plan-generation routing and guardrails.

Locked direction: HouseDiffusion is the PRIMARY plan generator. The internal
rule-based synthesis branch is diagnostic / explicit-fallback only.
"""
from core.architecture.routing.generation_policy_guard_v1 import (  # noqa: F401
    HOUSE_DIFFUSION_GENERATION_POLICY_V1,
    PRIMARY_GENERATOR_BYPASS_DETECTED,
    PrimaryGeneratorBypassError,
    guard_internal_plan_generation,
)

__all__ = [
    "HOUSE_DIFFUSION_GENERATION_POLICY_V1",
    "PRIMARY_GENERATOR_BYPASS_DETECTED",
    "PrimaryGeneratorBypassError",
    "guard_internal_plan_generation",
]
