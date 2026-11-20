"""
ArchitectOS Ramp 3D Geometry Engine v1.0

Creates 3D ramp geometry from ramp decisions.
"""
from math import hypot


class Ramp3DGeometryEngine:


    VERSION = "1.0"



    def __init__(self):

        print(
            f"🏗️ Ramp 3D Geometry Engine v{self.VERSION} ACTIVE"
        )



    # ==================================================
    # CREATE 3D POINTS
    # ==================================================

    def elevate_polygon(
        self,
        polygon,
        start_z,
        end_z
    ):


        points = []

        count = len(
            polygon
        )


        for index, point in enumerate(polygon):


            ratio = index / max(
                count - 1,
                1
            )


            z = (

                start_z

                +

                (
                    (end_z - start_z)
                    *
                    ratio
                )

            )


            points.append(

                [
                    point[0],
                    point[1],
                    round(
                        z,
                        3
                    )
                ]

            )


        return points


    def elevate_path(self, path, start_z, end_z):
        if not isinstance(path, list) or not path:
            return []
        distances = [0.0]
        for previous, current in zip(path, path[1:]):
            distances.append(
                distances[-1] + hypot(
                    float(current[0]) - float(previous[0]),
                    float(current[1]) - float(previous[1]),
                )
            )
        total = distances[-1]
        if total <= 0:
            return [[point[0], point[1], round(float(start_z), 3)] for point in path]
        return [
            [point[0], point[1], round(start_z + (end_z - start_z) * distance / total, 3)]
            for point, distance in zip(path, distances)
        ]


    def elevate_polygon_along_path(self, polygon, path, start_z, end_z):
        if not isinstance(path, list) or len(path) < 2:
            return self.elevate_polygon(polygon, start_z, end_z)
        segment_starts = []
        running = 0.0
        for first, second in zip(path, path[1:]):
            length = hypot(second[0] - first[0], second[1] - first[1])
            segment_starts.append((running, first, second, length))
            running += length
        if running <= 0:
            return self.elevate_polygon(polygon, start_z, end_z)
        elevated = []
        for point in polygon:
            best_distance_squared = None
            best_path_distance = 0.0
            for offset, first, second, length in segment_starts:
                if length <= 0:
                    continue
                dx, dy = second[0] - first[0], second[1] - first[1]
                ratio = ((point[0] - first[0]) * dx + (point[1] - first[1]) * dy) / (length * length)
                ratio = max(0.0, min(1.0, ratio))
                projected = [first[0] + dx * ratio, first[1] + dy * ratio]
                distance_squared = (point[0] - projected[0]) ** 2 + (point[1] - projected[1]) ** 2
                if best_distance_squared is None or distance_squared < best_distance_squared:
                    best_distance_squared = distance_squared
                    best_path_distance = offset + length * ratio
            z = start_z + (end_z - start_z) * best_path_distance / running
            elevated.append([point[0], point[1], round(z, 3)])
        return elevated



    # ==================================================
    # MAIN GENERATE
    # ==================================================

    def generate(
        self,
        ramp_geometry,
        ramp_decision
    ):


        polygon = ramp_geometry.get(
            "polygon",
            []
        )


        height = ramp_decision.get(
            "height",
            0
        )


        start_z = ramp_decision.get(
            "start_z",
            0
        )


        explicit_end_z = ramp_decision.get("end_z")
        end_z = explicit_end_z if isinstance(explicit_end_z, (int, float)) else start_z - height

        centerline = ramp_geometry.get("centerline", [])
        centerline_3d = self.elevate_path(centerline, start_z, end_z)

        surface_vertices = self.elevate_polygon_along_path(
            polygon, centerline, start_z, end_z
        ) if centerline else []
        surface_faces = []
        if len(surface_vertices) == 4:
            # The authoritative straight-ramp footprint is ordered as the two
            # longitudinal edges.  Two triangles preserve the actual inclined
            # architectural surface for model/CAD preview consumers.
            surface_faces = [[0, 1, 2], [0, 2, 3]]



        return {


            "type":
                "IfcRamp",


            "shape":
                ramp_geometry.get(
                    "shape"
                ),


            "slope":
                ramp_decision.get(
                    "slope"
                ),


            "width":
                ramp_decision.get(
                    "width",
                    6
                ),


            "start_z":
                start_z,


            "end_z":
                end_z,


            "geometry": surface_vertices or self.elevate_polygon(
                    polygon, start_z, end_z
                )

            ,"surface": {
                "vertices": surface_vertices,
                "faces": surface_faces,
                "geometry_status": "resolved" if surface_faces else "pending",
                "source": "ramp_footprint_and_centerline_3d",
            }

            ,"centerline_3d":
                centerline_3d

        }
