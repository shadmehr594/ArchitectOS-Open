from core.architecture.reasoning.site_access_evidence_derivation_v1 import (
    SiteAccessEvidenceDerivationV1,
)


class SiteReasoner:


    VERSION = "1.0"


    def __init__(self):

        print(
            "🌍 SITE REASONER v1.0 ONLINE"
        )


    def analyze(
        self,
        site
    ):


        analysis = {


            "site_conditions": [],


            "building_strategy": {},


            "open_space_strategy": {},


            "climate_response": {},


            "access_strategy": {}

        }

        # ==================================================
        # ARCHITECTURAL SITE CONTRACT CONSUMER
        #
        # Consume normalized real-parcel intelligence without
        # converting it back into legacy site assumptions.
        # ==================================================

        source_type = site.get(
            "source_type"
        )

        site_source = site.get(
            "source"
        )

        target_parcel = site.get(
            "target_parcel"
        )

        coordinate_system = site.get(
            "coordinate_system"
        )

        boundary = site.get(
            "boundary",
            {}
        )

        site_area = site.get(
            "area"
        )

        site_intelligence = site.get(
            "site_intelligence",
            {}
        )

        constraints = site.get(
            "constraints",
            []
        )

        site_constraints = site.get(
            "site_constraints",
            {}
        )

        parcel = site.get(
            "parcel",
            {}
        )


        if not isinstance(
            boundary,
            dict
        ):

            boundary = {}


        if not isinstance(
            site_intelligence,
            dict
        ):

            site_intelligence = {}


        if not isinstance(
            constraints,
            list
        ):

            constraints = []

        if not isinstance(
            site_constraints,
            dict
        ):

            site_constraints = {}


        if not isinstance(
            parcel,
            dict
        ):

            parcel = {}


        # ----------------------------------------------
        # REAL PARCEL EVIDENCE
        # ----------------------------------------------

        if (
            site_source == "parcel"
            or source_type == "polygon"
        ):

            analysis[
                "site_conditions"
            ].append(
                "real parcel geometry available"
            )


        if target_parcel is not None:

            analysis[
                "building_strategy"
            ][
                "target_parcel"
            ] = target_parcel


        if coordinate_system:

            analysis[
                "building_strategy"
            ][
                "coordinate_system"
            ] = coordinate_system


        if boundary.get(
            "type"
        ) == "polygon":

            points = boundary.get(
                "points",
                []
            )

            if isinstance(
                points,
                list
            ) and len(points) >= 3:

                analysis[
                    "building_strategy"
                ][
                    "parcel_boundary"
                ] = points


                analysis[
                    "building_strategy"
                ][
                    "parcel_geometry_status"
                ] = "resolved"


        if site_area is not None:

            analysis[
                "building_strategy"
            ][
                "parcel_area"
            ] = site_area


        # ----------------------------------------------
        # ROAD ACCESS EVIDENCE
        # ----------------------------------------------

        road_access = site_intelligence.get(
            "road_access"
        )


        if isinstance(
            road_access,
            dict
        ):

            analysis[
                "access_strategy"
            ][
                "road_access"
            ] = dict(
                road_access
            )


            road_width = road_access.get(
                "width"
            )


            if road_width is not None:

                analysis[
                    "access_strategy"
                ][
                    "road_width"
                ] = road_width


                analysis[
                    "site_conditions"
                ].append(
                    "road access width available"
                )

        pedestrian_candidates = site.get("pedestrian_access_candidates", [])
        if not isinstance(pedestrian_candidates, list):
            pedestrian_candidates = []
        if pedestrian_candidates:
            analysis["access_strategy"]["pedestrian_access_candidates"] = [
                dict(candidate) for candidate in pedestrian_candidates
                if isinstance(candidate, dict)
            ]

        # Preserve architecture-first pedestrian design inputs.  SiteReasoner
        # does not design geometry; it only carries explicit project evidence
        # to the later design reasoner.
        for key in (
            "pedestrian_access_width",
            "pedestrian_access_preference",
            "confirmed_road_access_edges",
            "setbacks",
            "setback_zones",
            "protected_zones",
            "pedestrian_conflict_zones",
            "vehicle_access_zones",
            "vehicle_circulation_zones",
            "parking_access_zones",
        ):
            if key in site:
                value = site.get(key)
                analysis["access_strategy"][key] = (
                    dict(value) if isinstance(value, dict)
                    else list(value) if isinstance(value, list)
                    else value
                )


        # ----------------------------------------------
        # EXPLICIT SITE CONSTRAINTS
        # ----------------------------------------------

        neighbor_constraints = []


        for constraint in constraints:

            if not isinstance(
                constraint,
                dict
            ):

                continue


            if constraint.get(
                "type"
            ) == "neighbor":

                neighbor_constraints.append(
                    dict(
                        constraint
                    )
                )


        if neighbor_constraints:

            analysis[
                "building_strategy"
            ][
                "neighbor_constraints"
            ] = neighbor_constraints


        # ----------------------------------------------
        # PRESERVE RAW PARCEL EVIDENCE
        # ----------------------------------------------

        if parcel:

            analysis[
                "building_strategy"
            ][
                "parcel"
            ] = dict(
                parcel
            )

        # Publish deterministic, geometry-bound access evidence before any
        # downstream design selection.  The primitive never chooses a point.
        derivation_input = dict(site)
        derivation_input.setdefault(
            "parcel_boundary", analysis["building_strategy"].get("parcel_boundary")
        )
        access_evidence = SiteAccessEvidenceDerivationV1().derive(
            derivation_input,
            site.get("program_requirements", {}),
            site.get("regulatory_separation_evidence", {}),
            site.get("parking_hypotheses", {}),
        )
        analysis["building_strategy"]["site_access_evidence"] = access_evidence
        if access_evidence.get("parcel_edges"):
            analysis["building_strategy"]["derived_parcel_edges"] = list(
                access_evidence["parcel_edges"]
            )
        if access_evidence.get("road_frontages"):
            analysis["access_strategy"]["derived_road_frontages"] = list(
                access_evidence["road_frontages"]
            )

        # ==================================================
        # PARCEL EDGE INTELLIGENCE v1.0
        #
        # Consume authoritative CAD edge evidence produced by:
        #
        # SiteConstraintExtractor
        #     -> access
        #     -> adjacency
        #     -> north
        #
        # IMPORTANT:
        #
        # edge_index is geometric identity.
        #
        # It must NOT be converted into north / south /
        # east / west unless geographic orientation is
        # independently resolved.
        # ==================================================

        parcel_edges = []


        constraint_access = site_constraints.get(
            "access",
            {}
        )


        if not isinstance(
            constraint_access,
            dict
        ):

            constraint_access = {}


        adjacency = site_constraints.get(
            "adjacency",
            []
        )


        if not isinstance(
            adjacency,
            list
        ):

            adjacency = []


        north_evidence = site_constraints.get(
            "north",
            {}
        )


        if not isinstance(
            north_evidence,
            dict
        ):

            north_evidence = {}


        # ----------------------------------------------
        # ACCESS EDGE
        # ----------------------------------------------

        if constraint_access.get(
            "confirmed"
        ):

            access_edge_index = (
                constraint_access.get(
                    "edge_index"
                )
            )


            road_width = (
                constraint_access.get(
                    "road_width"
                )
            )


            if access_edge_index is not None:

                analysis[
                    "access_strategy"
                ][
                    "access_edge_index"
                ] = access_edge_index


            if road_width is not None:

                analysis[
                    "access_strategy"
                ][
                    "road_width"
                ] = road_width


                if (
                    "road access width available"
                    not in analysis[
                        "site_conditions"
                    ]
                ):

                    analysis[
                        "site_conditions"
                    ].append(
                        "road access width available"
                    )


            analysis[
                "access_strategy"
            ][
                "access_status"
            ] = "resolved_from_cad"


        # ----------------------------------------------
        # EDGE RELATIONSHIPS
        # ----------------------------------------------

        for edge_relation in adjacency:

            if not isinstance(
                edge_relation,
                dict
            ):

                continue


            edge_index = edge_relation.get(
                "edge_index"
            )


            relation_type = edge_relation.get(
                "type"
            )


            if edge_index is None:

                continue


            parcel_edge = {

                "edge_index":
                    edge_index,

                "relation":
                    relation_type,

                "confirmed":
                    bool(
                        edge_relation.get(
                            "confirmed",
                            False
                        )
                    ),

                "confidence":
                    edge_relation.get(
                        "confidence"
                    )

            }


            if relation_type == "road":

                parcel_edge[
                    "road_width"
                ] = edge_relation.get(
                    "road_width"
                )


            elif relation_type == "neighbor_parcel":

                parcel_edge[
                    "parcel_id"
                ] = edge_relation.get(
                    "parcel_id"
                )


                parcel_edge[
                    "privacy_constraint"
                ] = True


            parcel_edges.append(
                parcel_edge
            )


        # ----------------------------------------------
        # PRESERVE PARCEL EDGE CONTRACT
        # ----------------------------------------------

        if parcel_edges:

            analysis[
                "building_strategy"
            ][
                "parcel_edges"
            ] = parcel_edges


            analysis[
                "building_strategy"
            ][
                "parcel_edge_status"
            ] = "resolved"


        # ----------------------------------------------
        # NEIGHBOR PARCEL INDEX
        # ----------------------------------------------

        neighbor_parcels = []


        for parcel_edge in parcel_edges:

            if (
                parcel_edge.get(
                    "relation"
                )
                !=
                "neighbor_parcel"
            ):

                continue


            parcel_id = parcel_edge.get(
                "parcel_id"
            )


            if (
                parcel_id is not None
                and
                parcel_id not in neighbor_parcels
            ):

                neighbor_parcels.append(
                    parcel_id
                )


        if neighbor_parcels:

            analysis[
                "building_strategy"
            ][
                "neighbor_parcels"
            ] = neighbor_parcels


            analysis[
                "site_conditions"
            ].append(
                "neighbor parcel edge constraints available"
            )


        # ----------------------------------------------
        # NORTH / GEOGRAPHIC ORIENTATION EVIDENCE
        #
        # A marker without a confirmed vector is evidence,
        # but is NOT enough to assign cardinal directions
        # to parcel edges.
        # ----------------------------------------------

        if north_evidence:

            analysis[
                "building_strategy"
            ][
                "north_evidence"
            ] = dict(
                north_evidence
            )


            if north_evidence.get(
                "confirmed"
            ):

                analysis[
                    "building_strategy"
                ][
                    "geographic_orientation_status"
                ] = "resolved"

            else:

                analysis[
                    "building_strategy"
                ][
                    "geographic_orientation_status"
                ] = "unresolved"



        # --------------------------------------
        # Orientation
        # --------------------------------------

        orientation = site.get(
            "orientation",
            {}
        )


        south = None
        orientation_angle = None


        if isinstance(
            orientation,
            dict
        ):

            south = orientation.get(
                "south"
            )


        elif isinstance(
            orientation,
            (int, float)
        ):

            orientation_angle = float(
                orientation
            )

            analysis[
                "site_conditions"
            ].append(

                "parcel orientation angle available; geographic north/south unresolved"

            )


        if south:


            analysis[
                "site_conditions"
            ].append(

                "south side identified as important orientation"

            )


            analysis[
                "open_space_strategy"
            ][
                "preferred_location"
            ] = "south"


        if orientation_angle is not None:

            analysis[
                "building_strategy"
            ][
                "parcel_orientation_angle"
            ] = orientation_angle


        # --------------------------------------
        # Neighbors
        # --------------------------------------

        neighbors = site.get(
            "neighbors",
            {}
        )


        if neighbors.get(
            "east"
        ):

            analysis[
                "site_conditions"
            ].append(

                "east boundary requires privacy consideration"

            )


        if neighbors.get(
            "west"
        ):

            analysis[
                "site_conditions"
            ].append(

                "west boundary requires privacy consideration"

            )


        # --------------------------------------
        # Access
        # --------------------------------------

        access = site.get(
            "access",
            {}
        )


        if access.get(
            "main_access"
        ):


            analysis[
                "access_strategy"
            ][
                "main_entry"
            ] = access[
                "main_access"
            ]



        # --------------------------------------
        # Climate
        # --------------------------------------

        climate = site.get(
            "climate",
            {}
        )


        if climate.get(
            "type"
        ) == "hot_dry":


            analysis[
                "climate_response"
            ] = {


                "strategy":

                    "controlled solar exposure and shaded outdoor spaces"


            }



        # --------------------------------------
        # Building Placement Logic
        # --------------------------------------

        analysis[
            "building_strategy"
        ].setdefault(
            "approach",
            "building placement should respond to orientation, access and privacy"
        )


        return analysis
