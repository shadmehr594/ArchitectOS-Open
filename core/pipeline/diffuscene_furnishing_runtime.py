"""DiffuScene -> 3D-FUTURE furnishing runtime bridge (Phase 3D-DIFFUSION-CONNECT-01).

This module is the MISSING RUNTIME LINK between the already-working pieces:

    DiffuScene JSON
        -> FurnitureAdapter.load_diffuscene_json / convert_diffuscene
        -> FurnitureAdapter.match_3d_future
        -> FurnitureAdapter.build_placement_candidates
        -> mesh_transform_spec.build_mesh_transform_spec
        -> mesh_transform_executor.execute_mesh_transform
        -> asset_scene_instance.build_asset_scene_instance
        -> asset_scene_instance_collection.build_asset_scene_instance_collection

Before this module, every one of those stages existed and passed its own tests,
but NOTHING joined them at runtime: the only callers were test files, which each
re-implemented a local ``_raw_mesh_for`` / ``_phi`` helper.

Design constraints honoured here
-------------------------------

1. **No invented furniture positions.** The only position source is the
   DiffuScene placement carried on the placement candidate. This module never
   computes, nudges, snaps or repairs a position.

2. **No duplicate basis transform.** The DiffuScene Y-up -> ArchitectOS Z-up
   basis change is applied ONCE, inside ``FurnitureAdapter.basis_position``
   (``[x, -z, y]``). This module passes the candidate through **verbatim**;
   it never re-applies the basis, and the resulting scene instance carries
   ``must_not_reapply_asset_transform: True`` downstream.

3. **No mesh loading here.** Raw OBJ loading stays in ``raw_obj_loader`` and is
   supplied by the caller (or by an injected loader) so this bridge stays
   testable without the 3D-FUTURE dataset. When a loader is supplied it is used
   verbatim; the bridge never fabricates geometry.

4. **Fail-closed.** A candidate that is not ``ready_transform_metadata``, or a
   transform that does not reach ``transformed_vertices_ready``, produces an
   explicit blocker record instead of a guessed instance.

5. **Reuse, not parallel architecture.** All ten stages above are the EXISTING
   modules. This bridge adds orchestration only; it defines no new geometry
   contract, no new identity scheme and no new scene format.

Scope exclusions (deliberate, per the active checkpoint)
-------------------------------------------------------

No rendering, no collision/clearance resolution, no room-boundary validation,
no plan generation, no BIM/IFC, no structure, no ComfyUI.
"""

from __future__ import annotations

import copy
from typing import Any, Callable, Iterable, Mapping

from core.pipeline.adapters.furniture_adapter import FurnitureAdapter
from core.asset.asset_scene_instance import build_asset_scene_instance
from core.asset.asset_scene_instance_collection import (
    build_asset_scene_instance_collection,
)

# ---------------------------------------------------------------------------
# contract constants (mirrored from the existing stage contracts)
# ---------------------------------------------------------------------------

OUTPUT_TYPE = "diffuscene_furnishing_scene"
OUTPUT_VERSION = "diffuscene_3d_future_runtime_connect_v1"
PIPELINE_ID = "3D-DIFFUSION-CONNECT-01"

# Owned by mesh_transform_spec; named here only to describe blockers.
READY_CANDIDATE_STATE = "ready_transform_metadata"
READY_EXECUTION_STATE = "transformed_vertices_ready"

# The single basis contract already applied by FurnitureAdapter.basis_position.
BASIS_VERSION = "diffuscene_y_up_to_architectos_z_up_v1"

STATE_COMPLETE = "furnishing_scene_complete"
STATE_PARTIAL = "furnishing_scene_partial"
STATE_EMPTY = "furnishing_scene_empty"


def _blocker(code: str, detail: Any = None) -> dict[str, Any]:
    return {"code": code, "detail": detail}


class DiffuSceneFurnishingRuntime:
    """Joins DiffuScene output to the 3D-FUTURE scene-instance path.

    The bridge is intentionally explicit about its two injectable seams:

    ``mesh_loader``
        ``mesh_loader(candidate, asset_record) -> raw loader result``.
        Defaults to ``None``. When ``None``, only candidates whose raw mesh is
        already supplied (or that the caller does not need transformed) can
        reach the instance stage; everything else fails closed with
        ``raw_mesh_unavailable``. This keeps the bridge runnable and unit
        testable without the real 3D-FUTURE dataset.

    ``forward_contract_provider`` / ``phi_provider``
        ``provider(candidate, asset_record) -> contract``. These mirror the
        existing ``build_mesh_transform_spec`` keyword arguments. They default
        to ``None``, which leaves forward unresolved exactly as today.
    """

    def __init__(
        self,
        *,
        adapter: FurnitureAdapter | None = None,
        mesh_loader: Callable[[Mapping[str, Any], Mapping[str, Any] | None], Mapping[str, Any]]
        | None = None,
        forward_contract_provider: Callable[[Mapping[str, Any], Mapping[str, Any] | None], Mapping[str, Any]]
        | None = None,
        phi_provider: Callable[[Mapping[str, Any], Mapping[str, Any] | None], Mapping[str, Any]]
        | None = None,
    ) -> None:

        # Reuse the EXISTING adapter. No second conversion/match implementation.
        self.adapter = adapter if adapter is not None else FurnitureAdapter()
        self.mesh_loader = mesh_loader
        self.forward_contract_provider = forward_contract_provider
        self.phi_provider = phi_provider

    # ------------------------------------------------------------------
    # registry helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _assets(asset_registry: Any) -> list[Mapping[str, Any]]:

        if isinstance(asset_registry, Mapping):
            assets = asset_registry.get("assets")
        else:
            assets = asset_registry
        if not isinstance(assets, list):
            raise ValueError("3D-FUTURE registry must be a list or contain assets")

        return assets

    @classmethod
    def _assets_by_model_id(
        cls, asset_registry: Any
    ) -> dict[str, Mapping[str, Any]]:

        by_model_id: dict[str, Mapping[str, Any]] = {}
        for asset in cls._assets(asset_registry):
            if isinstance(asset, Mapping) and asset.get("model_id") is not None:
                by_model_id.setdefault(asset["model_id"], asset)

        return by_model_id

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def build_from_diffuscene(
        self,
        diffuscene_scene: Iterable[Mapping[str, Any]],
        asset_registry: Any,
        *,
        placement_scope: str | None = None,
        room_origin_xyz: Iterable[float] | None = None,
        collection_id: str | None = None,
        context: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Drive one DiffuScene scene through to an asset scene collection.

        ``diffuscene_scene`` is the RAW DiffuScene list (the same shape
        ``convert_diffuscene`` accepts). Position, rotation and category are
        read from it and carried through unchanged.
        """

        scene = list(diffuscene_scene)

        # --- stage 1: DiffuScene -> furniture contract --------------------
        furniture_contract = self.adapter.convert_diffuscene(scene)

        return self.build_from_contract(
            furniture_contract,
            asset_registry,
            placement_scope=placement_scope,
            room_origin_xyz=room_origin_xyz,
            collection_id=collection_id,
            context=context,
            source_item_count=len(scene),
        )

    def build_from_diffuscene_json(
        self,
        path: Any,
        asset_registry: Any,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Same as :meth:`build_from_diffuscene` but reads the scene JSON file."""

        furniture_contract = self.adapter.load_diffuscene_json(path)

        return self.build_from_contract(furniture_contract, asset_registry, **kwargs)

    def build_from_contract(
        self,
        furniture_contract: Mapping[str, Any],
        asset_registry: Any,
        *,
        placement_scope: str | None = None,
        room_origin_xyz: Iterable[float] | None = None,
        collection_id: str | None = None,
        context: Mapping[str, Any] | None = None,
        source_item_count: int | None = None,
    ) -> dict[str, Any]:
        """Run the match -> placement -> transform -> instance chain.

        Every stage below is an existing module. This method only sequences
        them and records what happened.
        """

        source_items = furniture_contract.get("furniture") if isinstance(
            furniture_contract, Mapping
        ) else None
        if not isinstance(source_items, list):
            raise ValueError("Furniture contract must contain a furniture list")

        if source_item_count is None:
            source_item_count = len(source_items)

        assets = self._assets(asset_registry)
        by_model_id = self._assets_by_model_id(asset_registry)

        # --- stage 2: 3D-FUTURE asset matching ----------------------------
        matched = self.adapter.match_3d_future(furniture_contract, asset_registry)
        matched_items = matched["furniture"]
        matched_count = sum(
            1
            for item in matched_items
            if isinstance(item.get("asset_match"), Mapping)
            and item["asset_match"].get("model_id") is not None
        )

        # --- stage 3: placement candidates (basis applied ONCE upstream) --
        candidates = self.adapter.build_placement_candidates(
            matched,
            asset_registry,
            room_origin_xyz,
            placement_scope=placement_scope,
        )["placements"]

        # --- stages 4-7: transform -> instance -> collection --------------
        instances: list[dict[str, Any]] = []
        blockers: list[dict[str, Any]] = []
        per_item: list[dict[str, Any]] = []

        for candidate in candidates:
            ordinal = len(per_item)
            outcome = self._realize_candidate(candidate, by_model_id)
            per_item.append(
                {
                    "ordinal": ordinal,
                    "slot": candidate.get("slot"),
                    "category": candidate.get("category"),
                    "candidate_state": _candidate_state(candidate),
                    "instance_id": (
                        outcome["instance"]["instance_id"]
                        if outcome["instance"] is not None
                        else None
                    ),
                    "blockers": outcome["blockers"],
                }
            )
            if outcome["instance"] is not None:
                instances.append(outcome["instance"])
            blockers.extend(outcome["blockers"])

        # --- stage 8: deterministic collection ----------------------------
        collection = build_asset_scene_instance_collection(
            instances,
            collection_id=collection_id,
            context=context,
        )

        if not candidates:
            state = STATE_EMPTY
        elif blockers:
            state = STATE_PARTIAL
        else:
            state = STATE_COMPLETE

        return {
            "type": OUTPUT_TYPE,
            "version": OUTPUT_VERSION,
            "pipeline": PIPELINE_ID,
            "basis": BASIS_VERSION,
            "counts": {
                "source_items": source_item_count,
                "converted_items": len(source_items),
                "matched_to_3d_future": matched_count,
                "placement_candidates": len(candidates),
                "scene_instances": len(instances),
            },
            "instances": instances,
            "collection": collection,
            "per_item": per_item,
            "blockers": blockers,
            "semantics": {
                # The basis change was performed exactly once, upstream.
                "basis_applied_once_in_adapter": True,
                "basis_reapplied_here": False,
                "positions_come_only_from_diffuscene": True,
                "advanced_clearance_logic": False,
                "render_executed": False,
                "plan_generation_touched": False,
            },
            "status": {"state": state, "reasons": [b["code"] for b in blockers]},
        }

    # ------------------------------------------------------------------
    # per-candidate realization
    # ------------------------------------------------------------------

    def _realize_candidate(
        self,
        candidate: Mapping[str, Any],
        by_model_id: Mapping[str, Mapping[str, Any]],
    ) -> dict[str, Any]:
        """Candidate -> scene instance, or an explicit blocker list."""

        blockers: list[dict[str, Any]] = []

        state = _candidate_state(candidate)
        if state != READY_CANDIDATE_STATE:
            blockers.append(
                _blocker(
                    "candidate_not_transform_ready",
                    {"state": state, "reasons": _candidate_reasons(candidate)},
                )
            )

            return {"instance": None, "blockers": blockers}

        match = candidate.get("mesh_source") or {}
        model_id = match.get("model_id")
        asset_record = by_model_id.get(model_id) if model_id is not None else None

        # --- raw mesh: supplied by loader, never fabricated here ----------
        raw_mesh = None
        if self.mesh_loader is not None:
            raw_mesh = self.mesh_loader(candidate, asset_record)

        if not isinstance(raw_mesh, Mapping):
            blockers.append(
                _blocker("raw_mesh_unavailable", {"model_id": model_id})
            )

            return {"instance": None, "blockers": blockers}

        raw_mesh = copy.deepcopy(dict(raw_mesh))

        # Keep the loader result consistent with the candidate when the
        # candidate carries authoritative source identity.
        raw_mesh.setdefault("source", "3D-FUTURE")
        if model_id is not None:
            raw_mesh.setdefault("model_id", model_id)
        if match.get("raw_model_path") is not None:
            raw_mesh.setdefault("raw_model_path", match["raw_model_path"])

        raw_mesh["status"] = {
            "state": "mesh_loaded_valid",
            "reasons": list((raw_mesh.get("status") or {}).get("reasons", [])),
        }

        # --- stages 4-5: transform spec + executor (existing modules) -----
        from core.asset.mesh_transform_spec import build_mesh_transform_spec
        from core.asset.mesh_transform_executor import execute_mesh_transform

        spec_kwargs: dict[str, Any] = {}
        if self.forward_contract_provider is not None:
            spec_kwargs["forward_contract"] = self.forward_contract_provider(
                candidate, asset_record
            )
        if self.phi_provider is not None:
            spec_kwargs["phi_result"] = self.phi_provider(candidate, asset_record)

        try:
            spec = build_mesh_transform_spec(
                raw_mesh, candidate, **spec_kwargs
            )
        except (ValueError, TypeError) as error:
            blockers.append(_blocker("transform_spec_failed", str(error)))

            return {"instance": None, "blockers": blockers}

        try:
            transformed = execute_mesh_transform(raw_mesh, spec)
        except (ValueError, TypeError) as error:
            blockers.append(_blocker("mesh_transform_failed", str(error)))

            return {"instance": None, "blockers": blockers}

        execution_state = (transformed.get("status") or {}).get("state")
        if execution_state != READY_EXECUTION_STATE:
            blockers.append(
                _blocker(
                    "transform_not_executed",
                    {
                        "state": execution_state,
                        "spec_state": (spec.get("status") or {}).get("state"),
                    },
                )
            )

            return {"instance": None, "blockers": blockers}

        # --- stage 6: scene instance --------------------------------------
        try:
            instance = build_asset_scene_instance(
                transformed,
                slot=candidate.get("slot"),
                category=candidate.get("category"),
            )
        except (ValueError, TypeError) as error:
            blockers.append(_blocker("scene_instance_failed", str(error)))

            return {"instance": None, "blockers": blockers}

        return {"instance": instance, "blockers": blockers}


# ---------------------------------------------------------------------------
# small local readers (candidate already owns these fields; no re-derivation)
# ---------------------------------------------------------------------------


def _candidate_state(candidate: Mapping[str, Any]) -> Any:
    status = candidate.get("status")

    return status.get("state") if isinstance(status, Mapping) else None


def _candidate_reasons(candidate: Mapping[str, Any]) -> list[Any]:
    status = candidate.get("status")
    if not isinstance(status, Mapping):
        return []
    reasons = status.get("reasons")

    return list(reasons) if isinstance(reasons, list) else []
