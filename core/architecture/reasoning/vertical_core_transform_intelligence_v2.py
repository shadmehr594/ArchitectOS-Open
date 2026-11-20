"""General rigid-body vertical-core transform search for architecture-only studies."""
from copy import deepcopy

from shapely.affinity import rotate, translate
from shapely.geometry import Polygon
from shapely.ops import unary_union


class VerticalCoreTransformIntelligenceV2:
    """Rotate a composable core, then search translations toward parcel centre."""

    ROTATIONS = (0, 90, 180, 270)
    COMPONENT_KEYS = ("polygon", "stair", "elevator", "lobby")
    EPS = 1e-6

    def search(self, buildable_envelope, reference_core, vehicle_constraints=None,
               translation_step=.5, clearance=.15):
        envelope = Polygon(buildable_envelope)
        forbidden, layers = self._vehicle_envelope(vehicle_constraints or {}, clearance)
        unique_orientations = self._unique_orientations(reference_core)
        candidates = []
        for rotation_degrees, rotated in unique_orientations:
            shape = Polygon(rotated["polygon"])
            for dx, dy in self._translations_toward_centre(envelope, shape, translation_step):
                core = self._translate_core(rotated, dx, dy)
                core_shape = Polygon(core["polygon"])
                outside = not envelope.buffer(self.EPS).covers(core_shape)
                conflict_area = core_shape.intersection(forbidden).area if not forbidden.is_empty else 0.0
                reasons = []
                if outside:
                    reasons.append("core_outside_buildable_envelope")
                if conflict_area > self.EPS:
                    reasons.append("core_intersects_vehicle_forbidden_envelope")
                parcel_centre = envelope.centroid
                candidates.append({
                    "strategy": "ROTATE_TRANSLATE_COUPLED_SEARCH",
                    "rotation_degrees": rotation_degrees,
                    "translation_vector": [dx, dy],
                    "core": core,
                    "core_area": core_shape.area,
                    "centrality_distance": core_shape.centroid.distance(parcel_centre),
                    "edge_clearance": core_shape.boundary.distance(envelope.boundary),
                    "vehicle_conflict_area": conflict_area,
                    "vehicle_forbidden_envelope": self._polygons(forbidden),
                    "vehicle_forbidden_layers": layers,
                    "hard_rejection_reasons": reasons,
                    "hard_validation_status": "hard_valid" if not reasons else "not_feasible",
                    "vertical_alignment_status": "exact_xy_alignment",
                })
        return {
            "contract": "VerticalCoreTransformIntelligenceV2",
            "rotations_requested": list(self.ROTATIONS),
            "rotations_explored": [r for r, _ in unique_orientations],
            "equivalent_rotations_pruned": len(self.ROTATIONS) - len(unique_orientations),
            "composable_components": list(self.COMPONENT_KEYS[1:]),
            "vehicle_envelope_clearance": clearance,
            "candidate_count": len(candidates),
            "candidates": candidates,
        }

    def _unique_orientations(self, core):
        origin = Polygon(core["polygon"]).centroid
        seen, out = set(), []
        for angle in self.ROTATIONS:
            transformed = self._rotate_core(core, angle, origin)
            shape = Polygon(transformed["polygon"])
            signature = self._shape_signature(shape)
            if signature in seen:
                continue
            seen.add(signature)
            out.append((angle, transformed))
        return out

    def _rotate_core(self, core, angle, origin):
        result = deepcopy(core)
        for key in self.COMPONENT_KEYS:
            if isinstance(core.get(key), list) and len(core[key]) >= 3:
                result[key] = self._poly(rotate(Polygon(core[key]), angle, origin=origin))
        result["orientation_degrees"] = angle
        result["transform_topology"] = "composable_rigid_core"
        return result

    def _translate_core(self, core, dx, dy):
        result = deepcopy(core)
        for key in self.COMPONENT_KEYS:
            if isinstance(core.get(key), list) and len(core[key]) >= 3:
                result[key] = self._poly(translate(Polygon(core[key]), dx, dy))
        result["location"] = "coupled_transform_search"
        return result

    def _translations_toward_centre(self, envelope, shape, step):
        x0, y0, x1, y1 = envelope.bounds
        sx0, sy0, sx1, sy1 = shape.bounds
        target_x = (x0 + x1) / 2 - (sx1 - sx0) / 2
        target_y = (y0 + y1) / 2 - (sy1 - sy0) / 2
        min_x, max_x = x0 - sx0, x1 - sx1
        min_y, max_y = y0 - sy0, y1 - sy1
        xs = self._axis_values(min_x, max_x, target_x - sx0, step)
        ys = self._axis_values(min_y, max_y, target_y - sy0, step)
        return sorted(((dx, dy) for dx in xs for dy in ys),
                      key=lambda d: abs((shape.centroid.x+d[0])-envelope.centroid.x) +
                                    abs((shape.centroid.y+d[1])-envelope.centroid.y))

    @staticmethod
    def _axis_values(low, high, preferred, step):
        values = {round(low, 6), round(high, 6), round(max(low, min(high, preferred)), 6)}
        value = low
        while value <= high + 1e-9:
            values.add(round(value, 6)); value += step
        return sorted(values)

    def _vehicle_envelope(self, constraints, clearance):
        layers, shapes = {}, []
        aliases = (("stalls", "parking_stalls"), ("maneuvering", "maneuvering_field"),
                   ("access", "drive_lane"), ("swept", "swept_path"))
        for layer, key in aliases:
            value = constraints.get(key, [])
            raw = value if key == "parking_stalls" else ([value] if value else [])
            polygons = [Polygon(v.get("polygon", v) if isinstance(v, dict) else v) for v in raw]
            polygons = [p for p in polygons if p.is_valid and not p.is_empty]
            layer_shape = unary_union(polygons).buffer(clearance, join_style=2) if polygons else Polygon()
            layers[layer] = self._polygons(layer_shape)
            if not layer_shape.is_empty: shapes.append(layer_shape)
        return (unary_union(shapes) if shapes else Polygon()), layers

    @staticmethod
    def _shape_signature(shape):
        c = shape.centroid
        normalized = translate(shape, -c.x, -c.y)
        return normalized.normalize().wkb_hex

    @staticmethod
    def _poly(shape):
        return [[float(x), float(y)] for x, y in list(shape.exterior.coords)[:-1]]

    def _polygons(self, shape):
        return [self._poly(p) for p in getattr(shape, "geoms", [shape]) if p.geom_type == "Polygon" and not p.is_empty]
