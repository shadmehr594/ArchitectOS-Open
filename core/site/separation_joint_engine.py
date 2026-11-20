"""
ArchitectOS Separation Joint Engine v1.0

Calculates building separation based on:
- building height
- neighbor condition
- user requirement
"""


class SeparationJointEngine:


    VERSION = "1.0"



    def __init__(self):

        print(
            f"📐 Separation Joint Engine v{self.VERSION} ACTIVE"
        )



    # ==========================================
    # CALCULATE JOINT
    # ==========================================

    def calculate_joint(
        self,
        height,
        neighbor=False,
        enabled=True
    ):


        if not enabled:

            return 0



        if not neighbor:

            return 0



        # قابل تنظیم براساس ضابطه

        if height <= 10:

            return 0.10


        if height <= 20:

            return 0.20


        return 0.30




    # ==========================================
    # ANALYZE SITE EDGES
    # ==========================================

    def analyze(
        self,
        building,
        neighbors,
        requirement=None
    ):


        requirement = requirement or {}



        enabled = requirement.get(

            "enabled",

            True

        )



        height = building.get(

            "height",

            0

        )



        result = {}



        for side in [

            "north",

            "south",

            "east",

            "west"

        ]:


            neighbor_exists = neighbors.get(

                side,

                False

            )


            result[side] = {


                "neighbor":

                    neighbor_exists,


                "joint":

                    self.calculate_joint(

                        height,

                        neighbor_exists,

                        enabled

                    )

            }



        return {


            "separation_joints":

                result,


            "height":

                height

        }


    def apply_to_spatial_contract(
        self,
        contract,
        parcel_boundary,
        analysis
    ):
        """Apply rectangular parcel-edge joints before architectural layout.

        This is deliberately an architecture-side operation: room footprints
        that actually touch a parcel edge are inset, so all downstream floor,
        slab, boundary, wall and opening geometry inherits the same envelope.
        Rooms that do not touch an affected edge are preserved unchanged.
        """
        from copy import deepcopy

        resolved = deepcopy(contract or {})
        points = parcel_boundary if isinstance(parcel_boundary, list) else []
        if len(points) < 3:
            resolved["separation_joint_application"] = {
                "status": "pending",
                "reason": "rectangular_parcel_boundary_missing"
            }
            return resolved

        try:
            min_x = min(float(point[0]) for point in points)
            max_x = max(float(point[0]) for point in points)
            min_y = min(float(point[1]) for point in points)
            max_y = max(float(point[1]) for point in points)
        except (TypeError, ValueError, IndexError):
            resolved["separation_joint_application"] = {
                "status": "pending",
                "reason": "parcel_boundary_coordinates_invalid"
            }
            return resolved

        joints = (analysis or {}).get("separation_joints", {})
        offsets = {}
        for side in ("north", "south", "east", "west"):
            value = joints.get(side, {})
            value = value.get("joint", 0) if isinstance(value, dict) else value
            try:
                offsets[side] = max(0.0, float(value or 0))
            except (TypeError, ValueError):
                offsets[side] = 0.0

        tolerance = 1e-7
        applied_spaces = []
        for space in resolved.get("spaces", []):
            if not isinstance(space, dict):
                continue
            x, y = space.get("x"), space.get("y")
            dimensions = space.get("resolved_dimensions", {})
            width = space.get("width", dimensions.get("width"))
            depth = space.get("depth", dimensions.get("depth"))
            if not all(isinstance(value, (int, float)) for value in (x, y, width, depth)):
                continue

            original = [float(x), float(y), float(width), float(depth)]
            new_x, new_y, new_width, new_depth = original
            touched = []
            if abs(new_x - min_x) <= tolerance and offsets["west"]:
                new_x += offsets["west"]
                new_width -= offsets["west"]
                touched.append("west")
            if abs(original[0] + original[2] - max_x) <= tolerance and offsets["east"]:
                new_width -= offsets["east"]
                touched.append("east")
            if abs(new_y - min_y) <= tolerance and offsets["south"]:
                new_y += offsets["south"]
                new_depth -= offsets["south"]
                touched.append("south")
            if abs(original[1] + original[3] - max_y) <= tolerance and offsets["north"]:
                new_depth -= offsets["north"]
                touched.append("north")
            if new_width <= 0 or new_depth <= 0:
                raise ValueError("separation_joint_exceeds_space_footprint")
            if not touched:
                continue

            space["x"], space["y"] = new_x, new_y
            space["width"], space["depth"] = new_width, new_depth
            updated_dimensions = dict(dimensions)
            updated_dimensions.update({
                "width": new_width,
                "depth": new_depth,
                "area": new_width * new_depth,
            })
            space["resolved_dimensions"] = updated_dimensions
            space["separation_joint_edges"] = touched
            applied_spaces.append(space.get("name"))

        resolved["separation_joint_application"] = {
            "status": "applied",
            "offsets": offsets,
            "applied_spaces": applied_spaces,
            "source": "separation_joint_engine"
        }
        return resolved

    def resolve_buildable_envelope(self, parcel_boundary, analysis):
        """Create the pre-layout buildable envelope from resolved joints.

        Explicit per-edge offsets support convex non-axis-aligned parcels.
        The legacy north/south/east/west contract remains available for an
        axis-aligned rectangle.  No side name is inferred for an arbitrary
        polygon.
        """
        points = parcel_boundary if isinstance(parcel_boundary, list) else []
        if len(points) < 3:
            return {
                "status": "pending",
                "buildable_boundary": None,
                "reason": "parcel_boundary_required",
                "source": "separation_joint_engine",
            }
        try:
            normalized = [[float(point[0]), float(point[1])] for point in points]
        except (TypeError, ValueError, IndexError):
            return {
                "status": "pending", "buildable_boundary": None,
                "reason": "parcel_boundary_coordinates_invalid",
                "source": "separation_joint_engine",
            }
        edge_offsets = (analysis or {}).get("edge_offsets")
        if edge_offsets is not None:
            return self._resolve_polygon_edge_offsets(normalized, edge_offsets)
        if len(points) != 4:
            return {
                "status": "pending", "buildable_boundary": None,
                "reason": "explicit_edge_offsets_required_for_non_rectangular_parcel",
                "source": "separation_joint_engine",
            }
        xs = sorted(set(point[0] for point in normalized))
        ys = sorted(set(point[1] for point in normalized))
        if len(xs) != 2 or len(ys) != 2 or any(
            point not in ([xs[0], ys[0]], [xs[1], ys[0]], [xs[1], ys[1]], [xs[0], ys[1]])
            for point in normalized
        ):
            return {
                "status": "pending", "buildable_boundary": None,
                "reason": "axis_aligned_rectangular_parcel_required",
                "source": "separation_joint_engine",
            }
        joints = (analysis or {}).get("separation_joints", {})
        offsets = {}
        for side in ("north", "south", "east", "west"):
            item = joints.get(side, {})
            value = item.get("joint") if isinstance(item, dict) else item
            try:
                offsets[side] = float(value or 0.0)
            except (TypeError, ValueError):
                return {
                    "status": "pending", "buildable_boundary": None,
                    "reason": "separation_joint_value_invalid",
                    "source": "separation_joint_engine",
                }
            if offsets[side] < 0:
                return {
                    "status": "pending", "buildable_boundary": None,
                    "reason": "negative_separation_joint_invalid",
                    "source": "separation_joint_engine",
                }
        min_x = xs[0] + offsets["west"]
        max_x = xs[1] - offsets["east"]
        min_y = ys[0] + offsets["south"]
        max_y = ys[1] - offsets["north"]
        if min_x >= max_x or min_y >= max_y:
            return {
                "status": "pending", "buildable_boundary": None,
                "reason": "separation_joint_exhausts_parcel",
                "source": "separation_joint_engine",
            }
        return {
            "status": "resolved",
            "parcel_boundary": normalized,
            "buildable_boundary": [
                [min_x, min_y], [max_x, min_y],
                [max_x, max_y], [min_x, max_y],
            ],
            "offsets": offsets,
            "source": "separation_joint_engine",
            "geometry_authority": "pre_layout_architectural_site_contract",
        }

    def _resolve_polygon_edge_offsets(self, polygon, edge_offsets):
        """Intersect a convex parcel with explicit inward edge half-planes."""
        count = len(polygon)
        values = []
        for index in range(count):
            raw = edge_offsets.get(index, edge_offsets.get(str(index))) \
                if isinstance(edge_offsets, dict) else (
                    edge_offsets[index] if isinstance(edge_offsets, list) and index < len(edge_offsets) else None
                )
            try:
                value = float(raw)
            except (TypeError, ValueError):
                return {
                    "status": "pending", "buildable_boundary": None,
                    "reason": "explicit_offset_required_for_every_parcel_edge",
                    "source": "separation_joint_engine",
                }
            if value < 0:
                return {
                    "status": "pending", "buildable_boundary": None,
                    "reason": "negative_separation_joint_invalid",
                    "source": "separation_joint_engine",
                }
            values.append(value)

        signed_area = sum(
            a[0] * b[1] - b[0] * a[1]
            for a, b in zip(polygon, polygon[1:] + polygon[:1])
        ) / 2.0
        if abs(signed_area) <= 1e-10:
            return {
                "status": "pending", "buildable_boundary": None,
                "reason": "parcel_polygon_area_invalid",
                "source": "separation_joint_engine",
            }
        orientation = 1.0 if signed_area > 0 else -1.0
        result = [list(point) for point in polygon]
        tolerance = 1e-9

        for index, (a, b) in enumerate(zip(polygon, polygon[1:] + polygon[:1])):
            dx, dy = b[0] - a[0], b[1] - a[1]
            length = (dx * dx + dy * dy) ** 0.5
            if length <= tolerance:
                return {
                    "status": "pending", "buildable_boundary": None,
                    "reason": "parcel_edge_length_invalid",
                    "source": "separation_joint_engine",
                }
            threshold = values[index] * length

            def signed(point):
                return orientation * (dx * (point[1] - a[1]) - dy * (point[0] - a[0]))

            clipped = []
            for start, end in zip(result, result[1:] + result[:1]):
                start_value, end_value = signed(start), signed(end)
                start_inside = start_value + tolerance >= threshold
                end_inside = end_value + tolerance >= threshold
                if start_inside:
                    clipped.append(start)
                if start_inside != end_inside:
                    denominator = end_value - start_value
                    if abs(denominator) <= tolerance:
                        continue
                    parameter = (threshold - start_value) / denominator
                    clipped.append([
                        start[0] + parameter * (end[0] - start[0]),
                        start[1] + parameter * (end[1] - start[1]),
                    ])
            result = clipped
            if len(result) < 3:
                return {
                    "status": "pending", "buildable_boundary": None,
                    "reason": "separation_joint_exhausts_parcel",
                    "source": "separation_joint_engine",
                }

        area = abs(sum(
            a[0] * b[1] - b[0] * a[1]
            for a, b in zip(result, result[1:] + result[:1])
        ) / 2.0)
        return {
            "status": "resolved",
            "parcel_boundary": polygon,
            "buildable_boundary": result,
            "buildable_area": area,
            "edge_offsets": values,
            "source": "separation_joint_engine",
            "source_evidence": "explicit_project_edge_offsets",
            "geometry_authority": "pre_layout_architectural_site_contract",
        }
