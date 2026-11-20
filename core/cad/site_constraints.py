import math


class SiteConstraintExtractor:


    VERSION = "SITE_CONSTRAINTS_v1"



    def extract(
        self,
        site_intelligence,
        geometry
    ):


        if not site_intelligence or site_intelligence.get("status") != "ready":

            return {
                "status":"failed",
                "reason":"invalid site"
            }



        boundary = site_intelligence["boundary"]


        access = self._detect_access(
            geometry,
            boundary,
            site_intelligence
        )

        north = self._detect_north(
            geometry
        )



        return {

            "status":
                "ready",


            "site_id":
                site_intelligence["site_id"],


            "constraints":
                {

                    "boundary":
                        boundary,


                    "area":
                        site_intelligence["area"],


                    "access":
                        access,

                    "north":
                        north,

                    "adjacency":
                        self._detect_adjacency(
                            site_intelligence,
                            geometry,
                            access
                        )

                }

        }



    # ---------------------------------

    def _detect_access(
        self,
        geometry,
        boundary,
        site_intelligence
    ):

        if len(boundary) < 2:

            return {

                "detected":
                    False,

                "confirmed":
                    False,

                "edge_index":
                    None,

                "road_width":
                    None,

                "confidence":
                    0.0

            }


        origin = site_intelligence.get(
            "origin",
            {}
        )


        ox = float(
            origin.get(
                "x",
                0.0
            )
        )

        oy = float(
            origin.get(
                "y",
                0.0
            )
        )


        source_boundary = [

            [
                float(p["x"]) + ox,
                float(p["y"]) + oy
            ]

            for p in boundary

        ]


        # ==========================================
        # ROAD GEOMETRY CANDIDATES
        # ==========================================

        road_layers = [

            "shabake_jadid",
            "---Rah_1"

        ]


        road_segments = []


        layers = geometry.get(
            "layers",
            {}
        )


        for layer_name in road_layers:

            for item in layers.get(
                layer_name,
                []
            ):

                item_type = item.get(
                    "type"
                )


                if item_type == "LINE":

                    start = item.get(
                        "start"
                    )

                    end = item.get(
                        "end"
                    )


                    if start and end:

                        road_segments.append(
                            {

                                "layer":
                                    layer_name,

                                "start":
                                    start,

                                "end":
                                    end

                            }
                        )


                elif item_type == "LWPOLYLINE":

                    points = item.get(
                        "points",
                        []
                    )


                    for index in range(
                        len(points) - 1
                    ):

                        road_segments.append(
                            {

                                "layer":
                                    layer_name,

                                "start":
                                    points[index],

                                "end":
                                    points[index + 1]

                            }
                        )


        # ==========================================
        # MATCH PARCEL EDGE TO ROAD GEOMETRY
        # ==========================================

        best_geometry_match = None


        for edge_index in range(
            len(source_boundary)
        ):

            a = source_boundary[
                edge_index
            ]

            b = source_boundary[
                (
                    edge_index + 1
                )
                %
                len(source_boundary)
            ]


            edge_angle = self._segment_angle(
                a,
                b
            )


            for road in road_segments:

                road_angle = self._segment_angle(
                    road["start"],
                    road["end"]
                )


                angle_difference = self._parallel_angle_difference(
                    edge_angle,
                    road_angle
                )


                if angle_difference > 5.0:

                    continue


                distance_a = self._point_segment_distance(
                    a,
                    road["start"],
                    road["end"]
                )


                distance_b = self._point_segment_distance(
                    b,
                    road["start"],
                    road["end"]
                )


                average_distance = (
                    distance_a
                    +
                    distance_b
                ) / 2.0


                distance_difference = abs(
                    distance_a
                    -
                    distance_b
                )


                if distance_difference > 1.0:

                    continue


                score = (
                    average_distance
                    +
                    angle_difference
                )


                if (
                    best_geometry_match is None
                    or
                    score
                    <
                    best_geometry_match["score"]
                ):

                    best_geometry_match = {

                        "edge_index":
                            edge_index,

                        "road_layer":
                            road["layer"],

                        "road_start":
                            road["start"],

                        "road_end":
                            road["end"],

                        "edge_angle":
                            edge_angle,

                        "road_angle":
                            road_angle,

                        "angle_difference":
                            angle_difference,

                        "distance":
                            average_distance,

                        "distance_a":
                            distance_a,

                        "distance_b":
                            distance_b,

                        "score":
                            score

                    }


        # ==========================================
        # ROAD WIDTH ANNOTATIONS
        # ==========================================

        road_labels = []


        for item in geometry.get(
            "text",
            []
        ):

            if (
                item.get("layer")
                !=
                "arze_maber"
            ):
                continue


            value = str(
                item.get(
                    "value",
                    ""
                )
            ).strip()


            position = item.get(
                "position"
            )


            if not position:
                continue


            road_width = self._parse_road_width(
                value
            )


            if road_width is None:
                continue


            road_labels.append(
                {

                    "value":
                        value,

                    "width":
                        road_width,

                    "position":
                        position

                }
            )


        # ==========================================
        # MATCH WIDTH LABEL TO SELECTED EDGE
        # ==========================================

        road_width = None
        road_label = None
        label_distance = None


        if best_geometry_match is not None:

            edge_index = best_geometry_match[
                "edge_index"
            ]


            a = source_boundary[
                edge_index
            ]

            b = source_boundary[
                (
                    edge_index + 1
                )
                %
                len(source_boundary)
            ]


            for label in road_labels:

                distance = self._point_segment_distance(
                    label["position"],
                    a,
                    b
                )


                if (
                    label_distance is None
                    or
                    distance < label_distance
                ):

                    label_distance = distance
                    road_width = label["width"]
                    road_label = label["value"]


        # ==========================================
        # FINAL RESULT
        # ==========================================

        if best_geometry_match is None:

            return {

                "detected":
                    False,

                "confirmed":
                    False,

                "edge_index":
                    None,

                "road_width":
                    None,

                "confidence":
                    0.0

            }


        confidence = 0.9


        if road_width is not None:

            confidence = 0.95


        return {

            "detected":
                True,

            "confirmed":
                True,

            "method":
                "geometry_and_annotation",

            "edge_index":
                best_geometry_match[
                    "edge_index"
                ],

            "road_layer":
                best_geometry_match[
                    "road_layer"
                ],

            "road_width":
                road_width,

            "road_label":
                road_label,

            "road_offset":
                round(
                    best_geometry_match[
                        "distance"
                    ],
                    3
                ),

            "edge_angle":
                round(
                    best_geometry_match[
                        "edge_angle"
                    ],
                    3
                ),

            "road_angle":
                round(
                    best_geometry_match[
                        "road_angle"
                    ],
                    3
                ),

            "parallel_error":
                round(
                    best_geometry_match[
                        "angle_difference"
                    ],
                    3
                ),

            "label_distance":
                round(
                    label_distance,
                    3
                )
                if label_distance is not None
                else None,

            "confidence":
                confidence

        }


    def _parse_road_width(
        self,
        value
    ):

        import re


        match = re.search(
            r"(\d+(?:\.\d+)?)\s*[mM]",
            value
        )


        if not match:

            return None


        return float(
            match.group(1)
        )



    def _point_segment_distance(
        self,
        point,
        start,
        end
    ):

        px = float(
            point[0]
        )

        py = float(
            point[1]
        )


        x1 = float(
            start[0]
        )

        y1 = float(
            start[1]
        )


        x2 = float(
            end[0]
        )

        y2 = float(
            end[1]
        )


        dx = x2 - x1
        dy = y2 - y1


        length_sq = (
            dx * dx
            +
            dy * dy
        )


        if length_sq == 0:

            return math.hypot(
                px - x1,
                py - y1
            )


        t = (

            (
                (px - x1) * dx
                +
                (py - y1) * dy
            )

            /
            length_sq

        )


        t = max(
            0.0,
            min(
                1.0,
                t
            )
        )


        nearest_x = (
            x1
            +
            t * dx
        )

        nearest_y = (
            y1
            +
            t * dy
        )


        return math.hypot(

            px - nearest_x,
            py - nearest_y

        )


    def _segment_angle(
        self,
        start,
        end
    ):

        dx = (
            float(end[0])
            -
            float(start[0])
        )

        dy = (
            float(end[1])
            -
            float(start[1])
        )


        return math.degrees(
            math.atan2(
                dy,
                dx
            )
        )



    def _parallel_angle_difference(
        self,
        angle_a,
        angle_b
    ):

        difference = abs(
            angle_a
            -
            angle_b
        )


        difference = (
            difference
            %
            180.0
        )


        if difference > 90.0:

            difference = (
                180.0
                -
                difference
            )


        return difference

    def _detect_adjacency(
        self,
        site_intelligence,
        geometry,
        access
    ):

        boundary = site_intelligence.get(
            "boundary",
            []
        )

        origin = site_intelligence.get(
            "origin",
            {}
        )


        ox = float(
            origin.get(
                "x",
                0.0
            )
        )

        oy = float(
            origin.get(
                "y",
                0.0
            )
        )


        source_boundary = [

            [
                float(p["x"]) + ox,
                float(p["y"]) + oy
            ]

            for p in boundary

        ]


        labels = [

            item

            for item in geometry.get(
                "text",
                []
            )

            if (
                item.get("layer") == "CODE"
                and
                str(
                    item.get(
                        "value",
                        ""
                    )
                ).strip().isdigit()
            )

        ]


        results = []


        access_edge = access.get(
            "edge_index"
        )


        for edge_index in range(
            len(source_boundary)
        ):

            a = source_boundary[
                edge_index
            ]

            b = source_boundary[
                (
                    edge_index + 1
                )
                %
                len(source_boundary)
            ]


            if edge_index == access_edge:

                results.append(
                    {

                        "edge_index":
                            edge_index,

                        "type":
                            "road",

                        "road_width":
                            access.get(
                                "road_width"
                            ),

                        "confirmed":
                            True,

                        "confidence":
                            access.get(
                                "confidence",
                                0.0
                            )

                    }
                )

                continue


            dx = (
                b[0] - a[0]
            )

            dy = (
                b[1] - a[1]
            )


            length_sq = (
                dx * dx
                +
                dy * dy
            )


            length = math.sqrt(
                length_sq
            )


            if length == 0:

                continue


            midpoint_x = (
                a[0] + b[0]
            ) / 2.0

            midpoint_y = (
                a[1] + b[1]
            ) / 2.0


            outward_x = (
                dy / length
            )

            outward_y = (
                -dx / length
            )


            candidates = []


            for label in labels:

                position = label.get(
                    "position"
                )


                if not position:

                    continue


                px = float(
                    position[0]
                )

                py = float(
                    position[1]
                )


                vx = (
                    px - midpoint_x
                )

                vy = (
                    py - midpoint_y
                )


                outward_distance = (

                    vx * outward_x
                    +
                    vy * outward_y

                )


                if outward_distance <= 0:

                    continue


                projection = (

                    (
                        (px - a[0]) * dx
                        +
                        (py - a[1]) * dy
                    )

                    /
                    length_sq

                )


                if not (
                    0.0
                    <= projection
                    <= 1.0
                ):

                    continue


                candidates.append(
                    {

                        "parcel_id":
                            str(
                                label.get(
                                    "value"
                                )
                            ).strip(),

                        "outward_distance":
                            outward_distance,

                        "projection":
                            projection

                    }
                )


            if candidates:

                selected = min(

                    candidates,

                    key=lambda item:
                        item[
                            "outward_distance"
                        ]

                )


                results.append(
                    {

                        "edge_index":
                            edge_index,

                        "type":
                            "neighbor_parcel",

                        "parcel_id":
                            selected[
                                "parcel_id"
                            ],

                        "confirmed":
                            True,

                        "outward_distance":
                            round(
                                selected[
                                    "outward_distance"
                                ],
                                3
                            ),

                        "projection":
                            round(
                                selected[
                                    "projection"
                                ],
                                3
                            ),

                        "confidence":
                            0.9

                    }
                )


            else:

                results.append(
                    {

                        "edge_index":
                            edge_index,

                        "type":
                            "unknown",

                        "confirmed":
                            False,

                        "confidence":
                            0.0

                    }
                )


        return results



    # ---------------------------------

    def _detect_north(
        self,
        geometry
    ):

        candidates = []


        for item in geometry.get(
            "text",
            []
        ):

            value = str(
                item.get(
                    "value",
                    ""
                )
            ).strip()


            if value.upper() == "N":

                candidates.append(
                    {

                        "type":
                            item.get(
                                "type"
                            ),

                        "value":
                            value,

                        "position":
                            item.get(
                                "position"
                            ),

                        "layer":
                            item.get(
                                "layer"
                            )

                    }
                )


        return {

            "detected":
                False,

            "confirmed":
                False,

            "direction":
                None,

            "angle":
                None,

            "reference":
                "north_marker_without_vector"
                if candidates
                else None,

            "candidates":
                candidates

        }