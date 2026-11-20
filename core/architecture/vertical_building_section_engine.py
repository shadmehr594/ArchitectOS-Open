"""
ArchitectOS Vertical Building Section Engine v1.0

Architectural source of truth for:
- floor elevations
- variable floor heights
- basement
- commercial floors
- pilotis
- roof level
- roof extensions
- elevator/stair headroom

Structural systems must consume this data.
"""
from copy import deepcopy

from .floor_type_resolver_v1 import CanonicalFloorTypeResolverV1


class VerticalBuildingSectionEngine:


    VERSION = "1.0"


    def __init__(self):

        print(
            "🏢 Vertical Building Section Engine v1.0 ACTIVE"
        )


    # ==================================================
    # MAIN GENERATOR
    # ==================================================

    def generate(
        self,
        building_program,
        architectural_intent=None
    ):

        architectural_intent = architectural_intent if isinstance(architectural_intent, dict) else {}

        result = {

            "version":
                self.VERSION,

            "levels":
                [],

            "roof_level":
                0,

            "vertical_extensions":
                [],

            "total_height":
                0

        }


        current_z = 0.0

        result[
            "floor_elevations"
        ] = {}

        result["site_datum"] = (
            dict(architectural_intent.get("site_datum", {}))
            if isinstance(architectural_intent.get("site_datum"), dict)
            else {}
        )
        finished_floor_contract = architectural_intent.get("finished_floor", {})
        floor_build_up = (
            finished_floor_contract.get("floor_build_up", {})
            if isinstance(finished_floor_contract, dict)
            else {}
        )
        result["floor_build_up_status"] = (
            floor_build_up.get("status", "unresolved")
            if isinstance(floor_build_up, dict)
            else "unresolved"
        )


        floors = self.resolve_floors(
            building_program
        )


        for floor in floors:

            if not isinstance(
                floor,
                dict
            ):

                continue


            floor_name = floor.get(
                "name"
            )


            height = self.resolve_height(
                floor
            )


            if not floor_name:

                continue


            explicit_bottom = floor.get("bottom", floor.get("elevation"))
            finished_floor = architectural_intent.get("finished_floor", {})
            if (
                floor_name == "F1"
                and isinstance(finished_floor, dict)
                and isinstance(finished_floor.get("elevation"), (int, float))
            ):
                explicit_bottom = float(finished_floor["elevation"])
            explicit_top = floor.get("top")
            if isinstance(explicit_bottom, (int, float)):
                bottom = float(explicit_bottom)
            elif floor.get("type") == "basement" and height is not None:
                bottom = -float(height)
            else:
                bottom = current_z
            top = (float(explicit_top) if isinstance(explicit_top, (int, float))
                   else bottom + height if height is not None and bottom is not None else None)

            result["floor_elevations"][floor_name] = bottom


            level = {

                "name":
                    floor_name,

                "type":
                    floor.get(
                        "type"
                    ),

                "bottom":
                    bottom,

                "top":
                    top,

                "height":
                    height,

                "height_source":
                    floor.get(
                        "height_source"
                    ),

                "height_status":
                    "resolved" if height is not None else "unresolved"

            }

            for key in ("type_status", "type_source", "type_evidence"):
                if key in floor:
                    level[key] = deepcopy(floor[key]) if key == "type_evidence" else floor[key]

            if floor.get("type") == "mezzanine" or floor.get("is_mezzanine"):
                level["level_role"] = floor.get("level_role", "mezzanine")
                level["is_mezzanine"] = True

            if floor_name == "F1" and isinstance(finished_floor, dict) and finished_floor:
                level["finished_floor"] = dict(finished_floor)
                level["finished_floor_elevation"] = finished_floor.get("elevation")
                level["floor_build_up_status"] = result["floor_build_up_status"]
                # The level datum is the architectural finished-floor datum.
                # Structural slab bottom/top remain a separate unresolved
                # construction question when no build-up/thickness evidence exists.
                level["structural_slab_elevation_status"] = (
                    "unresolved"
                    if result["floor_build_up_status"] == "unresolved"
                    else "requires_structural_slab_contract"
                )


            result["levels"].append(
                level
            )


            if floor.get("type") != "basement" and top is not None and current_z is not None:
                current_z = max(current_z, top)
            elif floor.get("type") != "basement" and top is None:
                current_z = None



        result["roof_level"] = current_z
        result["roof_level_status"] = "resolved" if current_z is not None else "unresolved"


        result["vertical_extensions"] = (
            self.generate_extensions(
                building_program
            )
        )


        result["total_height"] = (
            current_z +
            sum(
                x.get(
                    "height",
                    0
                )
                for x in result["vertical_extensions"]
            )
        ) if current_z is not None else None


        return result


    # ==================================================
    # FLOOR CONTRACT NORMALIZATION
    # ==================================================

    def resolve_floors(
        self,
        building_program
    ):

        if not isinstance(
            building_program,
            dict
        ):

            return []


        explicit_floors = building_program.get(
            "floors"
        )


        if isinstance(
            explicit_floors,
            list
        ) and explicit_floors:

            return explicit_floors


        vertical_organization = (
            building_program.get(
                "vertical_organization",
                {}
            )
        )

        floor_heights = (
            building_program.get(
                "floor_heights",
                {}
            )
        )


        if not isinstance(
            vertical_organization,
            dict
        ):

            vertical_organization = {}


        if not isinstance(
            floor_heights,
            dict
        ):

            floor_heights = {}


        floors = []


        for floor_name in (
            vertical_organization.keys()
        ):

            height = floor_heights.get(
                floor_name
            )


            try:

                height = float(
                    height
                )

            except (
                TypeError,
                ValueError
            ):

                height = None


            floor_type_resolution = CanonicalFloorTypeResolverV1().resolve(
                floor_name, building_program
            )
            floor_type = floor_type_resolution["type"]
            if height is not None and height <= 0:
                height = None


            floors.append(
                {

                    "name":
                        floor_name,

                    "type":
                        floor_type,

                    "height":
                        height,

                    "height_source":
                        (
                            building_program.get(
                                "floor_configuration",
                                {}
                            ).get(
                                "source"
                            )
                            if isinstance(
                                building_program.get(
                                    "floor_configuration"
                                ),
                                dict
                            )
                            else None
                        ) or ("explicit_floor_height" if height is not None else "unresolved_missing_height_evidence"),

                    "type_status": floor_type_resolution["status"],

                    "type_source": floor_type_resolution["source"],

                    "type_evidence": floor_type_resolution["evidence"]

                }
            )


        return sorted(
            floors,
            key=lambda item: (
                0 if item.get("type") == "basement"
                else 2 if item.get("type") == "mezzanine"
                else 1
            ),
        )

    # ==================================================
    # HEIGHT KNOWLEDGE
    # ==================================================

    def resolve_height(
        self,
        floor
    ):


        if floor.get(
            "height"
        ):

            return floor["height"]



        return None



    # ==================================================
    # ROOF EXTENSIONS
    # ==================================================

    def generate_extensions(
        self,
        building_program
    ):


        extensions = []


        vertical = building_program.get(
            "vertical_elements",
            []
        )


        for element in vertical:


            element_type = element.get(
                "type"
            )


            if element_type == "stairs":

                extensions.append({

                    "type":
                        "stair_headroom",

                    "height":
                        2.8

                })


            elif element_type == "elevator_machine_room":

                extensions.append({

                    "type":
                        "elevator_headroom",

                    "height":
                        element.get(
                            "height",
                            1.0
                        )

                })


            elif element_type == "hydraulic_elevator":

                extensions.append({

                    "type":
                        "hydraulic_system",

                    "height":
                        0.0

                })


        return extensions
