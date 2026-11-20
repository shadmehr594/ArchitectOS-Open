class ParcelFitReasoner:

    VERSION = "1.0"


    def __init__(self):

        print(
            f"📐 PARCEL FIT REASONER v{self.VERSION} ONLINE"
        )


    def evaluate(
        self,
        site_geometry_intent,
        floor_geometry_intent
    ):

        site_geometry_intent = (
            site_geometry_intent
            if isinstance(
                site_geometry_intent,
                dict
            )
            else {}
        )

        floor_geometry_intent = (
            floor_geometry_intent
            if isinstance(
                floor_geometry_intent,
                list
            )
            else []
        )


        result = {

            "status":
                "pending",

            "fit":
                None,

            "evaluation_mode":
                None,

            "target_parcel":
                site_geometry_intent.get(
                    "target_parcel"
                ),

            "reference_floor":
                None,

            "parcel_envelope":
                None,

            "building_envelope":
                None,

            "clearance":
                None,

            "rotation_applied":
                False,

            "translation_applied":
                False,

            "reason":
                None
        }


        # ==============================================
        # PARCEL GEOMETRY VALIDATION
        # ==============================================

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
            ] = "parcel_geometry_unavailable"

            return result


        parcel_points = []


        for point in parcel_boundary:

            if not (
                isinstance(
                    point,
                    (list, tuple)
                )
                and len(
                    point
                ) >= 2
            ):

                continue


            x = point[0]
            y = point[1]


            if not isinstance(
                x,
                (int, float)
            ):

                continue


            if not isinstance(
                y,
                (int, float)
            ):

                continue


            parcel_points.append(
                (
                    float(x),
                    float(y)
                )
            )


        if len(
            parcel_points
        ) < 3:

            result[
                "reason"
            ] = "parcel_geometry_invalid"

            return result


        parcel_min_x = min(
            point[0]
            for point in parcel_points
        )

        parcel_min_y = min(
            point[1]
            for point in parcel_points
        )

        parcel_max_x = max(
            point[0]
            for point in parcel_points
        )

        parcel_max_y = max(
            point[1]
            for point in parcel_points
        )


        parcel_width = (
            parcel_max_x
            -
            parcel_min_x
        )

        parcel_depth = (
            parcel_max_y
            -
            parcel_min_y
        )


        result[
            "parcel_envelope"
        ] = {

            "min_x":
                parcel_min_x,

            "min_y":
                parcel_min_y,

            "max_x":
                parcel_max_x,

            "max_y":
                parcel_max_y,

            "width":
                parcel_width,

            "depth":
                parcel_depth
        }


        # ==============================================
        # BUILDING FOOTPRINT SELECTION
        #
        # First resolved building floor is treated as
        # footprint reference.
        #
        # No floor identity is invented.
        # ==============================================

        reference_floor = None


        for floor_geometry in floor_geometry_intent:

            if not isinstance(
                floor_geometry,
                dict
            ):

                continue


            envelope = floor_geometry.get(
                "envelope"
            )


            if not isinstance(
                envelope,
                dict
            ):

                continue


            if (
                floor_geometry.get(
                    "geometry_status"
                )
                !=
                "resolved_metric_envelope"
            ):

                continue


            reference_floor = floor_geometry

            break


        if reference_floor is None:

            result[
                "reason"
            ] = "building_metric_envelope_unavailable"

            return result


        building_envelope = reference_floor.get(
            "envelope",
            {}
        )


        building_width = building_envelope.get(
            "width"
        )

        building_depth = building_envelope.get(
            "depth"
        )


        if not isinstance(
            building_width,
            (int, float)
        ):

            result[
                "reason"
            ] = "building_width_unresolved"

            return result


        if not isinstance(
            building_depth,
            (int, float)
        ):

            result[
                "reason"
            ] = "building_depth_unresolved"

            return result


        building_width = float(
            building_width
        )

        building_depth = float(
            building_depth
        )


        result[
            "reference_floor"
        ] = reference_floor.get(
            "floor"
        )


        result[
            "building_envelope"
        ] = dict(
            building_envelope
        )


        # ==============================================
        # AXIS-ALIGNED FIT FEASIBILITY
        #
        # This is dimensional feasibility only.
        #
        # It does NOT prove polygon containment for
        # irregular parcels.
        #
        # No rotation / translation / setback.
        # ==============================================

        width_clearance = (
            parcel_width
            -
            building_width
        )

        depth_clearance = (
            parcel_depth
            -
            building_depth
        )


        fit_tolerance = 1e-9

        fits_axis_aligned = (

            width_clearance >= -fit_tolerance

            and

            depth_clearance >= -fit_tolerance

        )


        result[
            "clearance"
        ] = {

            "width":
                width_clearance,

            "depth":
                depth_clearance
        }


        result[
            "evaluation_mode"
        ] = "axis_aligned_envelope_feasibility"


        result[
            "fit"
        ] = bool(
            fits_axis_aligned
        )


        if fits_axis_aligned:

            result[
                "status"
            ] = "fit_feasible"

            result[
                "reason"
            ] = (
                "building_envelope_fits_within_parcel_envelope_without_rotation"
            )

        else:

            result[
                "status"
            ] = "fit_not_feasible"

            result[
                "reason"
            ] = (
                "building_envelope_exceeds_parcel_envelope_without_rotation"
            )


        return result
