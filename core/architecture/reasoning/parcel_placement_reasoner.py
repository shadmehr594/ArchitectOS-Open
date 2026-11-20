import math

class ParcelPlacementReasoner:

    VERSION = "1.0"


    def __init__(self):

        print(
            f"📍 PARCEL PLACEMENT REASONER v{self.VERSION} ONLINE"
        )


    def resolve(
        self,
        site_geometry_intent,
        parcel_fit_evaluation,
        spaces
    ):

        site_geometry_intent = (
            site_geometry_intent
            if isinstance(
                site_geometry_intent,
                dict
            )
            else {}
        )

        parcel_fit_evaluation = (
            parcel_fit_evaluation
            if isinstance(
                parcel_fit_evaluation,
                dict
            )
            else {}
        )

        spaces = (
            spaces
            if isinstance(
                spaces,
                list
            )
            else []
        )


        result = {

            "status":
                "pending",

            "target_parcel":
                site_geometry_intent.get(
                    "target_parcel"
                ),

            "reference_floor":
                parcel_fit_evaluation.get(
                    "reference_floor"
                ),

            "access_edge_index":
                site_geometry_intent.get(
                    "access_edge_index"
                ),

            "access_edge":
                None,

            "anchor_space":
                None,

            "translation":
                {
                    "dx": 0.0,
                    "dy": 0.0
                },

            "translated_envelope":
                None,

            "containment_status":
                "pending",

            "rotation":
                0.0,

            "rotation_applied":
                False,

            "translation_applied":
                False,

            "setback_applied":
                False,

            "placement_strategy":
                None,

            "reason":
                None
        }


        # ==============================================
        # FIT VALIDATION
        # ==============================================

        if (
            parcel_fit_evaluation.get(
                "fit"
            )
            is not True
        ):

            result[
                "reason"
            ] = "parcel_fit_not_confirmed"

            return result


        building_envelope = parcel_fit_evaluation.get(
            "building_envelope",
            {}
        )


        if not isinstance(
            building_envelope,
            dict
        ):

            result[
                "reason"
            ] = "building_envelope_unavailable"

            return result


        parcel_boundary = (
            site_geometry_intent.get("buildable_boundary")
            or site_geometry_intent.get("parcel_boundary")
        )


        if not (
            isinstance(
                parcel_boundary,
                list
            )
            and len(
                parcel_boundary
            ) >= 3
        ):

            result[
                "reason"
            ] = "parcel_boundary_unavailable"

            return result


        access_edge_index = site_geometry_intent.get(
            "access_edge_index"
        )


        if not isinstance(
            access_edge_index,
            int
        ):

            result[
                "reason"
            ] = "access_edge_unresolved"

            return result


        if not (
            0
            <=
            access_edge_index
            <
            len(
                parcel_boundary
            )
        ):

            result[
                "reason"
            ] = "access_edge_index_invalid"

            return result


        edge_start = parcel_boundary[
            access_edge_index
        ]

        edge_end = parcel_boundary[
            (
                access_edge_index
                +
                1
            )
            %
            len(
                parcel_boundary
            )
        ]


        if not (
            isinstance(
                edge_start,
                (list, tuple)
            )
            and len(
                edge_start
            ) >= 2
            and isinstance(
                edge_end,
                (list, tuple)
            )
            and len(
                edge_end
            ) >= 2
        ):

            result[
                "reason"
            ] = "access_edge_geometry_invalid"

            return result


        edge_start_x = float(
            edge_start[0]
        )

        edge_start_y = float(
            edge_start[1]
        )

        edge_end_x = float(
            edge_end[0]
        )

        edge_end_y = float(
            edge_end[1]
        )


        result[
            "access_edge"
        ] = {

            "start":
                [
                    edge_start_x,
                    edge_start_y
                ],

            "end":
                [
                    edge_end_x,
                    edge_end_y
                ],

            "dx":
                edge_end_x
                -
                edge_start_x,

            "dy":
                edge_end_y
                -
                edge_start_y
        }


        # ==============================================
        # ENTRANCE ANCHOR
        # ==============================================

        entrance = None


        for space in spaces:

            if not isinstance(
                space,
                dict
            ):

                continue


            name = str(
                space.get(
                    "name",
                    ""
                )
            ).lower()


            if name not in [
                "entrance",
                "main_entrance"
            ]:

                continue


            preferred_edge_index = space.get(
                "preferred_edge_index"
            )


            if (
                preferred_edge_index
                ==
                access_edge_index
            ):

                entrance = space

                break


        if entrance is None:

            result[
                "reason"
            ] = "entrance_access_anchor_unavailable"

            return result


        entrance_x = entrance.get(
            "x"
        )

        entrance_y = entrance.get(
            "y"
        )


        if not isinstance(
            entrance_x,
            (int, float)
        ):

            result[
                "reason"
            ] = "entrance_x_unresolved"

            return result


        if not isinstance(
            entrance_y,
            (int, float)
        ):

            result[
                "reason"
            ] = "entrance_y_unresolved"

            return result


        result[
            "anchor_space"
        ] = entrance.get(
            "name"
        )


        # ==============================================
        # ACCESS EDGE PLACEMENT
        #
        # v1.0 supports axis-aligned access edges only.
        #
        # No rotation is invented.
        # No setback is invented.
        #
        # Tangential placement is centered along the
        # access edge while normal placement keeps the
        # entrance aligned with the access boundary.
        # ==============================================

        edge_dx = (
            edge_end_x
            -
            edge_start_x
        )

        edge_dy = (
            edge_end_y
            -
            edge_start_y
        )


        min_x = float(
            building_envelope.get(
                "min_x"
            )
        )

        min_y = float(
            building_envelope.get(
                "min_y"
            )
        )

        max_x = float(
            building_envelope.get(
                "max_x"
            )
        )

        max_y = float(
            building_envelope.get(
                "max_y"
            )
        )


        building_width = (
            max_x
            -
            min_x
        )

        building_depth = (
            max_y
            -
            min_y
        )


        parcel_x_values = [
            float(
                point[0]
            )
            for point in parcel_boundary
        ]

        parcel_y_values = [
            float(
                point[1]
            )
            for point in parcel_boundary
        ]


        parcel_min_x = min(
            parcel_x_values
        )

        parcel_max_x = max(
            parcel_x_values
        )

        parcel_min_y = min(
            parcel_y_values
        )

        parcel_max_y = max(
            parcel_y_values
        )

        # ----------------------------------------------
        # OBLIQUE ACCESS EDGE / REAL PARCEL
        # ----------------------------------------------
        # Preserve the layout's entrance position along its source facade and
        # map that same normalized position to the proven parcel access edge.
        # This is a rigid architectural transform, not a midpoint fallback.
        if abs(edge_dx) >= 1e-9 and abs(edge_dy) >= 1e-9:
            edge_length = math.hypot(edge_dx, edge_dy)
            if edge_length + 1e-9 < building_width:
                result["reason"] = "access_edge_shorter_than_building_frontage"
                return result
            parameter = (float(entrance_x) - min_x) / building_width if building_width > 1e-9 else None
            if parameter is None or parameter < -1e-9 or parameter > 1.0 + 1e-9:
                result["reason"] = "entrance_anchor_outside_source_facade"
                return result
            target_x = edge_start_x + parameter * edge_dx
            target_y = edge_start_y + parameter * edge_dy
            angle = math.degrees(math.atan2(edge_dy, edge_dx))
            radians = math.radians(angle); cosine, sine = math.cos(radians), math.sin(radians)
            source_x, source_y = float(entrance_x), min_y
            corners = [(min_x,min_y),(max_x,min_y),(max_x,max_y),(min_x,max_y)]
            transformed = []
            for x, y in corners:
                rx, ry = x-source_x, y-source_y
                transformed.append([rx*cosine-ry*sine+target_x, rx*sine+ry*cosine+target_y])
            if not all(self._inside_or_edge(point, parcel_boundary) for point in transformed):
                result["reason"] = "rigid_access_edge_placement_outside_parcel"
                result["translated_envelope"] = transformed
                return result
            result.update({
                "status": "resolved", "containment_status": "resolved",
                "rotation": angle, "rotation_applied": True,
                "translation_applied": True, "setback_applied": False,
                "translation": {"dx": target_x-source_x, "dy": target_y-source_y},
                "transform": {"source_pivot": {"x": source_x, "y": source_y},
                              "target_pivot": {"x": target_x, "y": target_y}},
                "translated_envelope": transformed,
                "placement_strategy": "entrance_parameter_mapped_to_oblique_access_edge",
                "reason": "rigid_transform_contained_in_real_parcel",
            })
            return result


        # ----------------------------------------------
        # HORIZONTAL ACCESS EDGE
        # ----------------------------------------------

        if abs(
            edge_dy
        ) < 1e-9:

            target_min_x = (
                parcel_min_x
                +
                (
                    (
                        parcel_max_x
                        -
                        parcel_min_x
                    )
                    -
                    building_width
                )
                /
                2.0
            )


            dx = (
                target_min_x
                -
                min_x
            )


            if abs(
                edge_start_y
                -
                parcel_min_y
            ) < 1e-9:

                dy = (
                    edge_start_y
                    -
                    min_y
                )

                placement_strategy = (
                    "access_edge_anchored_horizontal_min_side"
                )

            elif abs(
                edge_start_y
                -
                parcel_max_y
            ) < 1e-9:

                dy = (
                    edge_start_y
                    -
                    max_y
                )

                placement_strategy = (
                    "access_edge_anchored_horizontal_max_side"
                )

            else:

                result[
                    "reason"
                ] = "horizontal_access_edge_not_on_parcel_envelope"

                return result


        # ----------------------------------------------
        # VERTICAL ACCESS EDGE
        # ----------------------------------------------

        elif abs(
            edge_dx
        ) < 1e-9:

            target_min_y = (
                parcel_min_y
                +
                (
                    (
                        parcel_max_y
                        -
                        parcel_min_y
                    )
                    -
                    building_depth
                )
                /
                2.0
            )


            dy = (
                target_min_y
                -
                min_y
            )


            if abs(
                edge_start_x
                -
                parcel_min_x
            ) < 1e-9:

                dx = (
                    edge_start_x
                    -
                    min_x
                )

                placement_strategy = (
                    "access_edge_anchored_vertical_min_side"
                )

            elif abs(
                edge_start_x
                -
                parcel_max_x
            ) < 1e-9:

                dx = (
                    edge_start_x
                    -
                    max_x
                )

                placement_strategy = (
                    "access_edge_anchored_vertical_max_side"
                )

            else:

                result[
                    "reason"
                ] = "vertical_access_edge_not_on_parcel_envelope"

                return result


        else:

            placement_strategy = (
                "access_edge_aligned_non_axis_rotation"
            )

            # ==============================================
            # NON-AXIS-ALIGNED ACCESS EDGE v1.1
            #
            # Align the building local X axis with the
            # confirmed access-edge tangent.
            #
            # Rotation is derived entirely from parcel
            # geometry. No arbitrary angle is introduced.
            # ==============================================

            edge_length = math.hypot(
                edge_dx,
                edge_dy
            )


            if edge_length <= 1e-9:

                result[
                    "reason"
                ] = "access_edge_length_invalid"

                return result

            # ==============================================
            # ACCESS-EDGE BUILDING AXIS SELECTION v1.0
            #
            # Select which local building dimension can
            # actually fit along the confirmed road edge.
            #
            # No parcel-specific orientation is hardcoded.
            # ==============================================

            width_fits_access_edge = (
                building_width
                <=
                edge_length
                +
                1e-9
            )

            depth_fits_access_edge = (
                building_depth
                <=
                edge_length
                +
                1e-9
            )


            if width_fits_access_edge:

                access_alignment_axis = "width"

            elif depth_fits_access_edge:

                access_alignment_axis = "depth"

            else:

                result[
                    "reason"
                ] = (
                    "building_frontage_dimensions_exceed_access_edge"
                )

                result[
                    "access_edge_length"
                ] = edge_length

                result[
                    "building_width"
                ] = building_width

                result[
                    "building_depth"
                ] = building_depth

                return result


            result[
                "access_alignment_axis"
            ] = access_alignment_axis

            result[
                "access_edge_length"
            ] = edge_length


            tangent_angle = math.atan2(
                edge_dy,
                edge_dx
            )


            if access_alignment_axis == "width":

                # Local X axis follows the road tangent.
                edge_angle = tangent_angle

                normal_building_dimension = (
                    building_depth
                )

            else:

                # Local Y axis follows the road tangent.
                # Therefore local X is rotated 90 degrees
                # from the tangent and extends inward.
                edge_angle = (
                    tangent_angle
                    +
                    math.pi
                    /
                    2.0
                )

                normal_building_dimension = (
                    building_width
                )


            rotation_degrees = math.degrees(
                edge_angle
            )


            building_center_x = (
                min_x
                +
                max_x
            ) / 2.0

            building_center_y = (
                min_y
                +
                max_y
            ) / 2.0


            parcel_edge_center_x = (
                edge_start_x
                +
                edge_end_x
            ) / 2.0

            parcel_edge_center_y = (
                edge_start_y
                +
                edge_end_y
            ) / 2.0


            cos_angle = math.cos(
                edge_angle
            )

            sin_angle = math.sin(
                edge_angle
            )


            local_corners = [

                (min_x, min_y),

                (max_x, min_y),

                (max_x, max_y),

                (min_x, max_y)

            ]


            rotated_corners = []


            for corner_x, corner_y in local_corners:

                relative_x = (
                    corner_x
                    -
                    building_center_x
                )

                relative_y = (
                    corner_y
                    -
                    building_center_y
                )


                rotated_x = (
                    relative_x
                    *
                    cos_angle
                    -
                    relative_y
                    *
                    sin_angle
                )

                rotated_y = (
                    relative_x
                    *
                    sin_angle
                    +
                    relative_y
                    *
                    cos_angle
                )


                rotated_corners.append(
                    [
                        rotated_x,
                        rotated_y
                    ]
                )


            rotated_min_x = min(
                point[0]
                for point in rotated_corners
            )

            rotated_max_x = max(
                point[0]
                for point in rotated_corners
            )

            rotated_min_y = min(
                point[1]
                for point in rotated_corners
            )

            rotated_max_y = max(
                point[1]
                for point in rotated_corners
            )


            rotated_width = (
                rotated_max_x
                -
                rotated_min_x
            )

            rotated_depth = (
                rotated_max_y
                -
                rotated_min_y
            )


            # ==============================================
            # INWARD ACCESS-EDGE ANCHOR v1.1
            #
            # Parcel polygon orientation determines the
            # interior normal.
            #
            # CCW polygon  -> left normal is inward.
            # CW polygon   -> right normal is inward.
            #
            # Building center is offset inward by half of
            # its local depth so the access-facing side
            # lies on the confirmed road edge.
            # ==============================================

            signed_area_twice = 0.0


            for point_index in range(
                len(
                    parcel_boundary
                )
            ):

                point_a = parcel_boundary[
                    point_index
                ]

                point_b = parcel_boundary[
                    (
                        point_index
                        +
                        1
                    )
                    %
                    len(
                        parcel_boundary
                    )
                ]


                signed_area_twice += (
                    float(
                        point_a[0]
                    )
                    *
                    float(
                        point_b[1]
                    )
                    -
                    float(
                        point_b[0]
                    )
                    *
                    float(
                        point_a[1]
                    )
                )


            tangent_x = (
                edge_dx
                /
                edge_length
            )

            tangent_y = (
                edge_dy
                /
                edge_length
            )


            if signed_area_twice > 0.0:

                inward_normal_x = (
                    -tangent_y
                )

                inward_normal_y = (
                    tangent_x
                )

                parcel_orientation = "CCW"

            else:

                inward_normal_x = (
                    tangent_y
                )

                inward_normal_y = (
                    -tangent_x
                )

                parcel_orientation = "CW"


            inward_offset = (
                normal_building_dimension
                /
                2.0
            )


            target_center_x = (
                parcel_edge_center_x
                +
                inward_normal_x
                *
                inward_offset
            )

            target_center_y = (
                parcel_edge_center_y
                +
                inward_normal_y
                *
                inward_offset
            )


            dx = (
                target_center_x
                -
                building_center_x
            )

            dy = (
                target_center_y
                -
                building_center_y
            )


            translated_rotated_corners = []


            for rotated_x, rotated_y in rotated_corners:

                translated_rotated_corners.append(
                    [
                        rotated_x
                        +
                        target_center_x,

                        rotated_y
                        +
                        target_center_y
                    ]
                )


            result[
                "parcel_orientation"
            ] = parcel_orientation

            result[
                "inward_normal"
            ] = {

                "x":
                    inward_normal_x,

                "y":
                    inward_normal_y
            }

            result[
                "inward_offset"
            ] = inward_offset

            # ==============================================
            # RESOLVED ROTATION CONTRACT
            # ==============================================

            result[
                "rotation"
            ] = rotation_degrees

            result[
                "rotation_applied"
            ] = True

            result[
                "rotated_footprint"
            ] = translated_rotated_corners

            result[
                "transform"
            ] = {

                "type":
                    "rigid_2d",

                "source_pivot":
                    {
                        "x":
                            building_center_x,

                        "y":
                            building_center_y
                    },

                "target_pivot":
                    {
                        "x":
                            target_center_x,

                        "y":
                            target_center_y
                    },

                "rotation_degrees":
                    rotation_degrees,

                "rotation_radians":
                    edge_angle,

                "translation":
                    {
                        "dx":
                            dx,

                        "dy":
                            dy
                    },

                "coordinate_mode":
                    "parcel_local",

                "source":
                    "parcel_placement_reasoner"

            }


        # ==============================================
        # TRANSLATED / ROTATED ENVELOPE
        # ==============================================

        if result.get(
            "rotation_applied"
        ):

            rotated_footprint = result.get(
                "rotated_footprint",
                []
            )


            translated_min_x = min(
                point[0]
                for point in rotated_footprint
            )

            translated_max_x = max(
                point[0]
                for point in rotated_footprint
            )

            translated_min_y = min(
                point[1]
                for point in rotated_footprint
            )

            translated_max_y = max(
                point[1]
                for point in rotated_footprint
            )


        else:

            translated_min_x = (
                min_x
                +
                dx
            )

            translated_max_x = (
                max_x
                +
                dx
            )

            translated_min_y = (
                min_y
                +
                dy
            )

            translated_max_y = (
                max_y
                +
                dy
            )


        translated_envelope = {

            "min_x":
                translated_min_x,

            "min_y":
                translated_min_y,

            "max_x":
                translated_max_x,

            "max_y":
                translated_max_y,

            "width":
                translated_max_x
                -
                translated_min_x,

            "depth":
                translated_max_y
                -
                translated_min_y
        }


        # ==============================================
        # POLYGON CONTAINMENT GUARD v1.1
        #
        # A placement may only become resolved when the
        # actual transformed building footprint is inside
        # the real parcel polygon.
        #
        # Bounding-box containment is not sufficient for
        # non-axis-aligned parcels.
        # ==============================================

        tolerance = 1e-9


        def point_on_segment(
            point_x,
            point_y,
            start_x,
            start_y,
            end_x,
            end_y
        ):

            cross = (
                (
                    point_y
                    -
                    start_y
                )
                *
                (
                    end_x
                    -
                    start_x
                )
                -
                (
                    point_x
                    -
                    start_x
                )
                *
                (
                    end_y
                    -
                    start_y
                )
            )


            if abs(
                cross
            ) > tolerance:

                return False


            dot = (
                (
                    point_x
                    -
                    start_x
                )
                *
                (
                    end_x
                    -
                    start_x
                )
                +
                (
                    point_y
                    -
                    start_y
                )
                *
                (
                    end_y
                    -
                    start_y
                )
            )


            if dot < -tolerance:

                return False


            segment_length_squared = (
                (
                    end_x
                    -
                    start_x
                )
                ** 2
                +
                (
                    end_y
                    -
                    start_y
                )
                ** 2
            )


            if (
                dot
                >
                segment_length_squared
                +
                tolerance
            ):

                return False


            return True


        def point_in_polygon(
            point,
            polygon
        ):

            point_x = float(
                point[0]
            )

            point_y = float(
                point[1]
            )


            inside = False


            for edge_index in range(
                len(
                    polygon
                )
            ):

                start = polygon[
                    edge_index
                ]

                end = polygon[
                    (
                        edge_index
                        +
                        1
                    )
                    %
                    len(
                        polygon
                    )
                ]


                start_x = float(
                    start[0]
                )

                start_y = float(
                    start[1]
                )

                end_x = float(
                    end[0]
                )

                end_y = float(
                    end[1]
                )


                if point_on_segment(
                    point_x,
                    point_y,
                    start_x,
                    start_y,
                    end_x,
                    end_y
                ):

                    return True


                intersects = (
                    (
                        start_y
                        >
                        point_y
                    )
                    !=
                    (
                        end_y
                        >
                        point_y
                    )
                )


                if not intersects:

                    continue


                intersection_x = (
                    (
                        end_x
                        -
                        start_x
                    )
                    *
                    (
                        point_y
                        -
                        start_y
                    )
                    /
                    (
                        end_y
                        -
                        start_y
                    )
                    +
                    start_x
                )


                if (
                    point_x
                    <
                    intersection_x
                ):

                    inside = not inside


            return inside


        if (
            result.get(
                "rotation_applied"
            )
            and isinstance(
                result.get(
                    "rotated_footprint"
                ),
                list
            )
        ):

            containment_footprint = result.get(
                "rotated_footprint"
            )

        else:

            containment_footprint = [

                [
                    translated_min_x,
                    translated_min_y
                ],

                [
                    translated_max_x,
                    translated_min_y
                ],

                [
                    translated_max_x,
                    translated_max_y
                ],

                [
                    translated_min_x,
                    translated_max_y
                ]

            ]


        corner_containment = [

            point_in_polygon(
                point,
                parcel_boundary
            )

            for point in containment_footprint

        ]


        contained = all(
            corner_containment
        )


        result[
            "footprint_containment"
        ] = {

            "mode":
                "polygon",

            "corner_results":
                corner_containment,

            "contained_corner_count":
                sum(
                    1
                    for value in corner_containment
                    if value
                ),

            "corner_count":
                len(
                    corner_containment
                )

        }


        result[
            "translated_envelope"
        ] = translated_envelope


        result[
            "containment_status"
        ] = (
            "contained_in_parcel_polygon"
            if contained
            else "outside_parcel_polygon"
        )


        result[
            "translation"
        ] = {

            "dx":
                dx,

            "dy":
                dy
        }


        if not contained:

            result[
                "translation_applied"
            ] = False

            result[
                "placement_strategy"
            ] = placement_strategy

            result[
                "status"
            ] = "placement_rejected"

            result[
                "reason"
            ] = "transformed_building_footprint_exceeds_parcel_polygon"

            return result


        result[
            "translation_applied"
        ] = True


        result[
            "placement_strategy"
        ] = placement_strategy


        result[
            "status"
        ] = "resolved"


        result[
            "reason"
        ] = "building_anchored_to_confirmed_access_edge"


        return result

    @staticmethod
    def _inside_or_edge(point, polygon):
        x, y = float(point[0]), float(point[1])
        inside = False
        previous = len(polygon) - 1
        for index, current_point in enumerate(polygon):
            x1, y1 = float(current_point[0]), float(current_point[1])
            x0, y0 = float(polygon[previous][0]), float(polygon[previous][1])
            cross = abs((x1-x0)*(y-y0) - (y1-y0)*(x-x0))
            edge_length = math.hypot(x1-x0, y1-y0)
            if cross <= 1e-6 * max(edge_length, 1.0) and min(x0,x1)-1e-6 <= x <= max(x0,x1)+1e-6 and min(y0,y1)-1e-6 <= y <= max(y0,y1)+1e-6:
                return True
            if (y1 > y) != (y0 > y) and x < (x0-x1)*(y-y1)/(y0-y1)+x1:
                inside = not inside
            previous = index
        return inside
