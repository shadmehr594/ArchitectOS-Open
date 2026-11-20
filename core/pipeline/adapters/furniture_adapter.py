import json
import math
import os
from pathlib import Path

from core.asset.placement_identity import (
    build_placement_identity,
    validate_placement_scope,
)
from core.interior.furniture_layout_engine import FurnitureLayoutEngine



class FurnitureAdapter:

    _CATEGORY_ALIASES = {
        "single_bed": "bed",
        "double_bed": "bed",
        "master_bed": "bed",
        "armchair": "chair",
        "dining_chair": "chair",
        "lounge_chair": "chair",
        "coffee_table": "table",
        "dining_table": "table",
        "side_table": "table",
        "nightstand": "cabinet",
        "bedside_table": "cabinet",
        "wardrobe": "cabinet",
        "bookshelf": "shelf",
    }

    # Basis defined by Phase 3D-G: DiffuScene is Y-up, ArchitectOS is Z-up.
    # B = [[1, 0, 0], [0, 0, -1], [0, 1, 0]]; p_architectos = B * p_diffuscene.
    _BASIS_VERSION = "diffuscene_y_up_to_architectos_z_up_v1"


    def __init__(self):

        self.engine = FurnitureLayoutEngine()



    def generate(self, state):


        furniture_config = state.get(

            "furniture",

            {}

        )


        spaces = furniture_config.get(

            "spaces",

            []

        )


        style = furniture_config.get(

            "style",

            "modern"

        )


        result = self.engine.generate(

            spaces,

            style

        )


        state["furniture_result"] = result


        return state


    def convert_diffuscene(self, scene):

        """Convert a DiffuScene scene to the ArchitectOS furniture contract."""

        if not isinstance(scene, list):
            raise ValueError("DiffuScene scene must be a list of objects")

        furniture = []

        for index, item in enumerate(scene):
            if not isinstance(item, dict):
                raise ValueError(
                    f"DiffuScene object at index {index} must be a mapping"
                )

            required = (
                "slot",
                "class_name",
                "center_xyz",
                "full_dims_xyz",
                "angle_rad",
                "objfeat",
            )
            missing = [key for key in required if key not in item]
            if missing:
                raise ValueError(
                    f"DiffuScene object at index {index} is missing: "
                    + ", ".join(missing)
                )

            if len(item["center_xyz"]) != 3:
                raise ValueError(
                    f"DiffuScene object at index {index} has invalid center_xyz"
                )
            if len(item["full_dims_xyz"]) != 3:
                raise ValueError(
                    f"DiffuScene object at index {index} has invalid full_dims_xyz"
                )

            furniture.append(
                {
                    "source_engine": "DiffuScene",
                    "slot": item["slot"],
                    "category": item["class_name"],
                    "center_xyz": list(item["center_xyz"]),
                    "full_dims_xyz": list(item["full_dims_xyz"]),
                    "rotation_y_rad": item["angle_rad"],
                    "objfeat": list(item["objfeat"]),
                }
            )

        return {"furniture": furniture}


    def load_diffuscene_json(self, path):

        """Load a DiffuScene JSON file and convert it to furniture contract data."""

        scene_path = Path(path)
        with scene_path.open("r", encoding="utf-8") as scene_file:
            scene = json.load(scene_file)

        return self.convert_diffuscene(scene)

    def match_3d_future(self, furniture_contract, asset_registry):

        """Attach the best compatible 3D-FUTURE asset to each furniture item.

        Registry records use the existing furniture naming where possible and
        require ``model_id``, ``category`` and ``full_dims_xyz``. ``objfeat``
        and ``model_path`` are optional. Category is a hard filter; dimensions
        rank compatible assets; cosine feature similarity is the final
        tie-breaker when both sides provide features.
        """

        if not isinstance(furniture_contract, dict) or not isinstance(
            furniture_contract.get("furniture"), list
        ):
            raise ValueError("Furniture contract must contain a furniture list")
        if isinstance(asset_registry, dict):
            assets = asset_registry.get("assets")
        else:
            assets = asset_registry
        if not isinstance(assets, list):
            raise ValueError("3D-FUTURE registry must be a list or contain assets")

        matched = []
        for item in furniture_contract["furniture"]:
            candidates = [
                asset for asset in assets
                if self._categories_compatible(
                    item.get("category"), asset.get("category")
                )
            ]
            if not candidates:
                enriched = dict(item)
                enriched["asset_match"] = None
                matched.append(enriched)
                continue

            ranked = []
            for asset in candidates:
                self._validate_asset(asset)
                dimension_score = self._dimension_similarity(
                    item["full_dims_xyz"], asset["full_dims_xyz"]
                )
                feature_score = self._feature_similarity(
                    item.get("objfeat"), asset.get("objfeat")
                )
                ranked.append((dimension_score, feature_score, asset))
            dimension_score, feature_score, asset = max(
                ranked,
                key=lambda row: (row[0], row[1], str(row[2]["model_id"])),
            )
            enriched = dict(item)
            enriched["asset_match"] = {
                "source": "3D-FUTURE",
                "model_id": asset["model_id"],
                "category": asset["category"],
                "full_dims_xyz": list(asset["full_dims_xyz"]),
                "model_path": asset.get("model_path"),
                "dimension_similarity": dimension_score,
                "objfeat_similarity": (
                    feature_score if feature_score != -1.0 else None
                ),
            }
            matched.append(enriched)

        return {"furniture": matched}

    def load_3d_future_registry(self, path):

        """Load 3D-FUTURE asset metadata for ``match_3d_future``."""

        registry_path = Path(path)
        with registry_path.open("r", encoding="utf-8") as registry_file:
            return json.load(registry_file)

    @classmethod
    def basis_position(cls, center_xyz):

        """Map a DiffuScene center to ArchitectOS room-local coordinates.

        Returns ``[ds_x, -ds_z, ds_y]``. No origin translation and no unit
        conversion are applied here; this is the basis change only.
        """

        x, y, z = cls._finite_triple(center_xyz, "center_xyz")

        return [x, -z, y]

    @classmethod
    def map_yaw(cls, rotation_y_rad):

        """Preserve the DiffuScene yaw as an ArchitectOS +Z yaw in radians."""

        return cls._finite_scalar(rotation_y_rad, "rotation_y_rad")

    def build_placement_candidates(
        self,
        furniture_contract,
        asset_registry,
        room_origin_xyz=None,
        *,
        placement_scope=None
    ):

        """Build transform-only placement candidates for matched furniture.

        This performs no mesh loading, no deformation, no floor snapping and no
        support inference. Dimension component correspondence stays unresolved,
        so source and target dimension vectors are preserved verbatim.

        ``placement_scope`` is an OPTIONAL keyword-only, caller-supplied
        machine-safe scope token. Together with the source item ordinal it forms
        a deterministic PLACEMENT identity that is independent of ``model_id``.
        When omitted, the placement identity stays explicitly ``unresolved``.
        """

        if not isinstance(furniture_contract, dict) or not isinstance(
            furniture_contract.get("furniture"), list
        ):
            raise ValueError("Furniture contract must contain a furniture list")
        if isinstance(asset_registry, dict):
            assets = asset_registry.get("assets")
        else:
            assets = asset_registry
        if not isinstance(assets, list):
            raise ValueError("3D-FUTURE registry must be a list or contain assets")

        origin = None
        if room_origin_xyz is not None:
            origin = self._finite_triple(room_origin_xyz, "room_origin_xyz")

        scope = validate_placement_scope(placement_scope)

        by_model_id = {}
        for asset in assets:
            if isinstance(asset, dict) and asset.get("model_id") is not None:
                by_model_id.setdefault(asset["model_id"], asset)

        # One candidate per source item, in stable input order. The source list
        # ordinal is the placement ordinal; no sorting and no deduplication.
        placements = [
            self._placement_candidate(item, by_model_id, origin, scope, ordinal)
            for ordinal, item in enumerate(furniture_contract["furniture"])
        ]

        return {"placements": placements}

    def _placement_candidate(self, item, by_model_id, origin, scope, ordinal):

        reasons = []

        source_engine = item.get("source_engine", "DiffuScene")

        # The FurnitureAdapter OWNS placement identity creation. It is
        # deterministic in (scope, ordinal) only, so it is never derived from
        # ``model_id`` (asset MODEL identity) and never from the DiffuScene
        # ``slot`` (source provenance). Downstream stages only COPY / PROPAGATE
        # this block.
        placement_identity = build_placement_identity(
            placement_scope=scope,
            ordinal=ordinal,
            source_engine=source_engine,
            source_slot=item.get("slot"),
        )

        match = item.get("asset_match")
        has_match = isinstance(match, dict) and match.get("model_id") is not None

        record = None
        raw_model_path = None
        if not has_match:
            state = "pending_asset_match"
            reasons.append("no_compatible_asset")
        else:
            record = by_model_id.get(match["model_id"])
            if record is None:
                state = "pending_raw_model_path"
                reasons.append("asset_record_not_found")
            elif not isinstance(record.get("raw_model_path"), str) or not (
                record["raw_model_path"].strip()
            ):
                state = "pending_raw_model_path"
                reasons.append("raw_model_path_unavailable")
            else:
                state = "ready_transform_metadata"
                raw_model_path = record["raw_model_path"]

        room_local_xyz = None
        try:
            room_local_xyz = self.basis_position(item.get("center_xyz"))
        except ValueError as error:
            reasons.append(f"invalid_source_position: {error}")
            if state == "ready_transform_metadata":
                state = "invalid_source_position"

        yaw_rad = None
        try:
            yaw_rad = self.map_yaw(item.get("rotation_y_rad"))
        except ValueError as error:
            reasons.append(f"invalid_source_rotation: {error}")
            if state == "ready_transform_metadata":
                state = "invalid_source_rotation"

        target_dims_xyz = None
        source_dims_xyz = None
        dimension_error = None
        try:
            target_dims_xyz = self._finite_triple(
                item.get("full_dims_xyz"), "full_dims_xyz"
            )
        except ValueError as error:
            dimension_error = error
        if dimension_error is None and has_match:
            try:
                source_dims_xyz = self._finite_triple(
                    match.get("full_dims_xyz"), "asset_full_dims_xyz"
                )
            except ValueError as error:
                dimension_error = error
        if dimension_error is not None:
            target_dims_xyz = None
            source_dims_xyz = None
            reasons.append(f"invalid_source_dimensions: {dimension_error}")
            if state == "ready_transform_metadata":
                state = "invalid_source_dimensions"

        world_xyz = None
        if room_local_xyz is not None and origin is not None:
            world_xyz = [
                room_local_xyz[index] + origin[index] for index in range(3)
            ]

        if state == "ready_transform_metadata":
            reasons.extend(
                [
                    "mesh_forward_unresolved",
                    "support_unresolved",
                    "fit_pending_axis_mapping",
                ]
            )

        return {
            "type": "furniture_asset_placement",
            "source_engine": source_engine,
            "slot": item.get("slot"),
            "category": item.get("category"),
            # Deterministic PLACEMENT identity (resolved or explicitly
            # unresolved). ``slot`` above stays raw provenance; this block is
            # the only scene-instance identity carrier.
            "placement_identity": placement_identity,
            "mesh_source": {
                "source": "3D-FUTURE",
                "model_id": match["model_id"] if has_match else None,
                "raw_model_path": raw_model_path,
            },
            "position": {
                "source_center_xyz": (
                    list(item["center_xyz"])
                    if isinstance(item.get("center_xyz"), (list, tuple))
                    else None
                ),
                "room_local_xyz": room_local_xyz,
                "world_xyz": world_xyz,
                "basis": self._BASIS_VERSION,
            },
            "rotation": {
                "source_y_rad": item.get("rotation_y_rad"),
                "yaw_rad": yaw_rad,
                "axis": "+Z",
                "mapping_status": "resolved",
                "mesh_forward_status": "unresolved",
            },
            "dimensions": {
                "source_asset_xyz": source_dims_xyz,
                "target_diffuscene_xyz": target_dims_xyz,
                "axis_mapping_status": "unresolved",
                "fit_status": "fit_pending_axis_mapping",
            },
            "units": {"status": "assumed_meters"},
            "scale": {
                "policy": "no_deformation",
                "scale_xyz": [1.0, 1.0, 1.0],
                "instance_scale_status": "unresolved_training_data_convention",
            },
            "anchor": {"support_status": "unresolved", "contact_z": None},
            "status": {"state": state, "reasons": reasons},
        }

    @staticmethod
    def _finite_scalar(value, label):

        if isinstance(value, bool):
            raise ValueError(f"{label} must be a real number")
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{label} must be a real number")
        if not math.isfinite(number):
            raise ValueError(f"{label} must be finite")

        return number

    @classmethod
    def _finite_triple(cls, values, label):

        if isinstance(values, (str, bytes)) or not isinstance(
            values, (list, tuple)
        ):
            raise ValueError(f"{label} must contain three values")
        if len(values) != 3:
            raise ValueError(f"{label} must contain three values")

        return [cls._finite_scalar(value, label) for value in values]

    @classmethod
    def _canonical_category(cls, category):
        value = str(category or "").strip().lower().replace("-", " ")
        value = "_".join(value.split())
        return cls._CATEGORY_ALIASES.get(value, value)

    @classmethod
    def _categories_compatible(cls, left, right):
        return cls._canonical_category(left) == cls._canonical_category(right)

    @staticmethod
    def _validate_asset(asset):
        required = ("model_id", "category", "full_dims_xyz")
        missing = [key for key in required if key not in asset]
        if missing:
            raise ValueError("3D-FUTURE asset is missing: " + ", ".join(missing))
        if len(asset["full_dims_xyz"]) != 3:
            raise ValueError("3D-FUTURE asset has invalid full_dims_xyz")

    @staticmethod
    def _dimension_similarity(target, candidate):
        if len(target) != 3 or len(candidate) != 3:
            raise ValueError("Furniture dimensions must contain three values")
        relative_error = sum(
            abs(float(actual) - float(expected)) / max(abs(float(expected)), 1e-9)
            for expected, actual in zip(target, candidate)
        ) / 3.0
        return 1.0 / (1.0 + relative_error)

    @staticmethod
    def _feature_similarity(target, candidate):
        if not target or not candidate or len(target) != len(candidate):
            return -1.0
        target_norm = math.sqrt(sum(float(value) ** 2 for value in target))
        candidate_norm = math.sqrt(sum(float(value) ** 2 for value in candidate))
        if not target_norm or not candidate_norm:
            return -1.0
        return sum(
            float(left) * float(right) for left, right in zip(target, candidate)
        ) / (target_norm * candidate_norm)


# ==========================================================
# PIPELINE STAGE ADAPTER (Phase 3D-DIFFUSION-CONNECT-02)
# ==========================================================


class FurnitureStageAdapter:
    """Expose the EXISTING DiffuScene furnishing runtime as the
    ``"furniture"`` engine of ``MasterArchitectPipeline``.

    This is the smallest possible connectivity change. It adds NO new
    geometry contract, NO second furnishing runtime and NO new scene format.

    Dispatch compatibility
    ----------------------
    ``MasterArchitectPipeline._execute_engine`` dispatches by probing, in
    order, ``execute`` / ``generate`` / ``apply`` / ``build`` / ``process`` /
    ``analyze``. This adapter exposes ``execute`` (highest priority) so the
    existing pipeline dispatches into it without any change to the pipeline.

    ``execute(state)`` returns a dict, so the pipeline stores it at
    ``state["furniture"]`` — a new key, so the pre-existing
    ``state["furniture_result"]`` (written by ``FurnitureAdapter.generate``)
    is left untouched.

    Fail-closed behaviour
    ---------------------
    Invoking the real runtime requires a **DiffuScene scene** and a
    **3D-FUTURE asset registry**. If either is absent, this adapter does NOT
    invent one and does NOT substitute an empty scene. It returns a
    fail-closed payload with ``status.state == "blocked"`` and an explicit
    blocker code. ``MasterArchitectPipeline`` still records the stage as
    ``success`` (the engine ran without raising), but the payload itself
    states that no furnishing scene was produced.

    Deliberately unresolved (unchanged by this phase)
    ------------------------------------------------
    mesh forward axis, support/anchor, instance scale convention and the
    dimension axis mapping stay exactly as ``build_placement_candidates``
    already reports them (``mesh_forward_status: "unresolved"``,
    ``support_status: "unresolved"``, ``instance_scale_status:
    "unresolved_training_data_convention"``, ``axis_mapping_status:
    "unresolved"``). This adapter never resolves, guesses or overrides them.

    Note that while those blockers persist, ``build_mesh_transform_spec``
    will refuse a candidate, so ``DiffuSceneFurnishingRuntime`` may return
    ``furnishing_scene_partial`` with zero instances. That is the CORRECT
    fail-closed outcome and is reported verbatim — it is not a connectivity
    failure.
    """

    #: key the pipeline stores this stage payload under
    STATE_KEY = "furniture"

    #: default registry path (existing repository asset)
    DEFAULT_REGISTRY_PATH = (
        "models/3d_future/asset_registry.json"
    )

    #: environment variable that overrides the registry path
    REGISTRY_ENV_VAR = "ARCHITECTOS_3D_FUTURE_REGISTRY"

    # own status vocabulary (distinct from the runtime's scene states)
    STAGE_BLOCKED = "blocked"
    STAGE_SKIPPED = "skipped"
    STAGE_COMPLETE = "stage_complete"

    def __init__(
        self,
        *,
        runtime=None,
        asset_registry=None,
        registry_path=None,
        scene_key="diffuscene_scene",
    ):

        # Reuse the EXISTING runtime class. No second runtime is created.
        if runtime is None:
            from core.pipeline.diffuscene_furnishing_runtime import (
                DiffuSceneFurnishingRuntime,
            )

            runtime = DiffuSceneFurnishingRuntime()

        self.runtime = runtime

        self._asset_registry = asset_registry
        self._registry_path = registry_path
        self.scene_key = scene_key

    # ==================================================
    # REGISTRY RESOLUTION
    # ==================================================

    def _resolve_registry(self, state):

        """Resolve the 3D-FUTURE registry, or ``None`` when unavailable.

        Resolution order: injected registry, state-provided registry, explicit
        path, environment override, repository default. No registry is ever
        fabricated.
        """

        if self._asset_registry is not None:
            return self._asset_registry

        for key in ("asset_registry", "3d_future_registry"):
            if isinstance(state, dict) and state.get(key) is not None:
                return state[key]

        candidates = []
        if self._registry_path:
            candidates.append(self._registry_path)

        environment = os.environ.get(self.REGISTRY_ENV_VAR)
        if environment:
            candidates.append(environment)

        candidates.append(self.DEFAULT_REGISTRY_PATH)

        for candidate in candidates:
            path = Path(candidate)
            if not path.is_absolute():
                path = Path(__file__).resolve().parents[3] / path
            if path.is_file():
                return self.runtime.adapter.load_3d_future_registry(path)

        return None

    # ==================================================
    # SCENE RESOLUTION
    # ==================================================

    def _resolve_scene(self, state):

        """Locate a DiffuScene scene in the pipeline state, or ``None``.

        Only an explicit scene (inline list or a path) is accepted. Missing
        scenes are NEVER replaced by an empty list, because an empty scene is
        indistinguishable from "DiffuScene produced nothing" downstream.
        """

        if not isinstance(state, dict):
            return None, None

        scene = state.get(self.scene_key)
        if scene is not None:
            return scene, self.scene_key

        path = state.get("diffuscene_scene_path")
        if path is not None:
            return Path(path), "diffuscene_scene_path"

        return None, None

    # ==================================================
    # PIPELINE ENTRY POINT (dispatched as the "furniture" engine)
    # ==================================================

    def execute(self, state):

        if not isinstance(state, dict):
            raise ValueError("Furniture stage expects a pipeline state mapping")

        scene, scene_source = self._resolve_scene(state)

        if scene is None:
            return self._blocked(
                state,
                scene_source=None,
                blocker_code="diffuscene_scene_missing",
                blocker_detail=(
                    f"no scene found under '{self.scene_key}' or "
                    "'diffuscene_scene_path'"
                ),
            )

        registry = self._resolve_registry(state)

        if registry is None:
            return self._blocked(
                state,
                scene_source=scene_source,
                blocker_code="asset_registry_unavailable",
                blocker_detail=(
                    "no 3D-FUTURE registry supplied and no readable registry "
                    f"at '{self.DEFAULT_REGISTRY_PATH}'"
                ),
            )

        kwargs = {
            "placement_scope": state.get("placement_scope"),
            "room_origin_xyz": state.get("room_origin_xyz"),
            "collection_id": state.get("collection_id"),
        }

        if isinstance(scene, (str, Path)):
            furnishing = self.runtime.build_from_diffuscene_json(
                scene, registry, **kwargs
            )
        else:
            furnishing = self.runtime.build_from_diffuscene(
                scene, registry, **kwargs
            )

        return self._stage_payload(
            furnishing,
            scene_source=scene_source,
            room_origin_applied=kwargs["room_origin_xyz"] is not None,
        )

    # ==================================================
    # PAYLOAD BUILDERS
    # ==================================================

    def _blocked(
        self,
        state,
        *,
        scene_source,
        blocker_code,
        blocker_detail,
    ):

        room_origin = state.get("room_origin_xyz")

        return {
            "type": "furniture_stage",
            "stage": self.STATE_KEY,
            "runtime": "DiffuSceneFurnishingRuntime",
            "basis": self.runtime.adapter._BASIS_VERSION,
            "scene_source": scene_source,
            "furnishing": None,
            "counts": {
                "source_items": None,
                "matched_to_3d_future": None,
                "placement_candidates": None,
                "scene_instances": None,
            },
            "semantics": {
                "invoked": False,
                "fail_closed": True,
                "runtime_reused": True,
                "second_runtime_created": False,
                "basis_applied_once_in_adapter": True,
                "basis_reapplied_here": False,
                "positions_come_only_from_diffuscene": True,
                "room_origin_applied": room_origin is not None,
                "mesh_forward_axis_resolved": False,
                "instance_scale_convention_resolved": False,
                "advanced_clearance_logic": False,
                "render_executed": False,
                "plan_generation_touched": False,
            },
            "blockers": [
                {"code": blocker_code, "detail": blocker_detail}
            ],
            "status": {
                "state": self.STAGE_BLOCKED,
                "reasons": [blocker_code],
            },
        }

    def _stage_payload(self, furnishing, *, scene_source, room_origin_applied=False):

        runtime_state = (furnishing.get("status") or {}).get("state")

        if runtime_state == "furnishing_scene_empty":
            stage_state = self.STAGE_SKIPPED
        else:
            stage_state = self.STAGE_COMPLETE

        return {
            "type": "furniture_stage",
            "stage": self.STATE_KEY,
            "runtime": "DiffuSceneFurnishingRuntime",
            "basis": furnishing.get("basis"),
            "scene_source": scene_source,
            "furnishing": furnishing,
            "counts": dict(furnishing.get("counts") or {}),
            "semantics": {
                "invoked": True,
                "fail_closed": False,
                "runtime_reused": True,
                "second_runtime_created": False,
                # copied verbatim from the runtime; never re-derived here
                "basis_applied_once_in_adapter": (
                    furnishing.get("semantics", {})
                    .get("basis_applied_once_in_adapter")
                ),
                "basis_reapplied_here": (
                    furnishing.get("semantics", {}).get("basis_reapplied_here")
                ),
                "positions_come_only_from_diffuscene": (
                    furnishing.get("semantics", {})
                    .get("positions_come_only_from_diffuscene")
                ),
                "room_origin_applied": bool(room_origin_applied),
                "mesh_forward_axis_resolved": False,
                "instance_scale_convention_resolved": False,
                "advanced_clearance_logic": False,
                "render_executed": False,
                "plan_generation_touched": False,
            },
            "blockers": list(furnishing.get("blockers") or []),
            "status": {
                "state": stage_state,
                "unresolved": [
                    "mesh_forward_axis",
                    "furniture_support_anchor",
                    "instance_scale_convention",
                    "dimension_axis_mapping",
                ],
                "runtime_state": runtime_state,
                "reasons": list(
                    (furnishing.get("status") or {}).get("reasons") or []
                ),
            },
        }
