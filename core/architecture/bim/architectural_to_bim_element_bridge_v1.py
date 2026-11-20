"""
ArchitectOS Architectural To BIM Element Bridge v1.2

Converts architectural geometry output
into semantic BIM elements.

Design Principle
----------------
Architectural level/floor information must be
preserved exactly as provided by Architectural
Geometry.

This layer MUST NOT invent:

- floor levels
- elevations
- dimensions
- structural dimensions
- architectural geometry

Level provenance:
    architectural_geometry
        ↓
    BIM element
        ↓
    BIM enrichment
        ↓
    IFC mapping
        ↓
    IFC geometry
        ↓
    IFC containment
"""


class ArchitecturalToBIMElementBridgeV1:

    VERSION = "1.2"

    def __init__(self):

        print(
            f"🔗 ARCHITECTURAL TO BIM ELEMENT BRIDGE v{self.VERSION} ONLINE"
        )

    # ======================================
    # MAIN CONVERSION
    # ======================================

    def convert(
        self,
        architectural_geometry
    ):

        elements = []

        if not isinstance(
            architectural_geometry,
            dict
        ):
            return {
                "bim_elements": [],
                "element_count": 0,
                "source":
                    "architectural_to_bim_element_bridge"
            }

        # ==================================
        # SPACES → IFC SPACE
        # ==================================

        for space in architectural_geometry.get(
            "spaces",
            []
        ):

            if not isinstance(
                space,
                dict
            ):
                continue

            elements.append(
                {
                    "type":
                        "IfcSpace",

                    "name":
                        space.get(
                            "name"
                        ),

                    "level":
                        self.resolve_level(
                            space
                        ),

                    "role":
                        "architectural_space",

                    "geometry":
                        space
                }
            )

        # ==================================
        # PHYSICAL WALLS → IFC WALL
        #
        # ArchitecturalGeometry is now
        # authoritative at physical-wall level.
        #
        # Shared room boundaries have already
        # been deduplicated into one physical
        # wall by ArchitecturalPhysicalWallResolver.
        #
        # IMPORTANT:
        # Do not recreate walls from semantic
        # per-space boundaries here.
        # ==================================

        for wall in architectural_geometry.get(
            "physical_walls",
            []
        ):

            if not isinstance(
                wall,
                dict
            ):
                continue

            wall_id = wall.get(
                "wall_id"
            )

            wall_type = wall.get(
                "wall_type"
            )

            spaces = wall.get(
                "spaces",
                []
            )

            elements.append(
                {
                    "type":
                        "IfcWall",

                    "name":
                        (
                            str(
                                wall_id
                            )
                            if wall_id
                            else "ArchitecturalWall"
                        ),

                    "level":
                        self.resolve_level(
                            wall
                        ),

                    "role":
                        (
                            wall_type
                            or "architectural_wall"
                        ),

                    "geometry":
                        wall,

                    "source":
                        "architectural_physical_wall",

                    "wall_id":
                        wall_id,

                    "wall_type":
                        wall_type,

                    "spaces":
                        list(
                            spaces
                        )
                        if isinstance(
                            spaces,
                            list
                        )
                        else [],

                    "topology_status":
                        wall.get(
                            "topology_status"
                        ),

                    "coordinate_mode":
                        wall.get(
                            "coordinate_mode"
                        )
                }
            )

        # ==================================
        # OPENINGS → IFC WINDOW
        # ==================================

        for opening in architectural_geometry.get(
            "openings",
            []
        ):

            if not isinstance(
                opening,
                dict
            ):
                continue

            elements.append(
                {
                    "type":
                        "IfcWindow",

                    "name":
                        str(
                            opening.get(
                                "space",
                                "Opening"
                            )
                        )
                        + "_Opening",

                    "level":
                        self.resolve_level(
                            opening
                        ),

                    "role":
                        "opening",

                    "geometry":
                        opening
                }
            )

        # ==================================
        # DOORS
        # ==================================

        for door in architectural_geometry.get(
            "doors",
            []
        ):

            if not isinstance(
                door,
                dict
            ):
                continue

            elements.append(
                {
                    "type":
                        "IfcDoor",

                    "name":
                        str(
                            door.get(
                                "space",
                                "Door"
                            )
                        )
                        + "_Door",

                    "level":
                        self.resolve_level(
                            door
                        ),

                    "role":
                        "opening",

                    "geometry":
                        door
                }
            )

        # ==================================
        # SLABS
        # ==================================

        for slab in architectural_geometry.get(
            "slabs",
            []
        ):

            if not isinstance(
                slab,
                dict
            ):
                continue

            elements.append(
                {
                    "type":
                        "IfcSlab",

                    "name":
                        str(
                            slab.get(
                                "space",
                                "Slab"
                            )
                        )
                        + "_Slab",

                    "level":
                        self.resolve_level(
                            slab
                        ),

                    "role":
                        "floor_system",

                    "geometry":
                        slab
                }
            )

        # ==================================
        # ROOFS
        # ==================================

        for roof in architectural_geometry.get(
            "roofs",
            []
        ):

            if not isinstance(
                roof,
                dict
            ):
                continue

            elements.append(
                {
                    "type":
                        "IfcRoof",

                    "name":
                        roof.get(
                            "name",
                            "Roof"
                        ),

                    "level":
                        self.resolve_level(
                            roof
                        ),

                    "role":
                        "roof",

                    "geometry":
                        roof
                }
            )

        # ==================================
        # VERTICAL ELEMENTS
        # ==================================

        for vertical in architectural_geometry.get(
            "vertical_geometry",
            []
        ):

            if not isinstance(
                vertical,
                dict
            ):
                continue

            elements.append(
                {
                    "type":
                        self.resolve_vertical_type(
                            vertical.get(
                                "type"
                            )
                        ),

                    "name":
                        vertical.get(
                            "name"
                        ),

                    "level":
                        self.resolve_level(
                            vertical
                        ),

                    "role":
                        "vertical_circulation",

                    "geometry":
                        vertical
                }
            )

        # ==================================
        # RETURN BIM
        # ==================================

        return {
            "bim_elements":
                elements,

            "element_count":
                len(
                    elements
                ),

            "source":
                "architectural_to_bim_element_bridge"
        }

    # ======================================
    # LEVEL RESOLUTION
    # ======================================

    def resolve_level(
        self,
        item
    ):

        if not isinstance(
            item,
            dict
        ):
            return None

        # ----------------------------------
        # Explicit level
        # ----------------------------------

        level = item.get(
            "level"
        )

        if level is not None:
            return level

        # ----------------------------------
        # Architectural floor
        # ----------------------------------

        floor = item.get(
            "floor"
        )

        if floor is not None:
            return floor

        # ----------------------------------
        # Nested geometry metadata
        # ----------------------------------

        geometry = item.get(
            "geometry"
        )

        if isinstance(
            geometry,
            dict
        ):

            level = geometry.get(
                "level"
            )

            if level is not None:
                return level

            floor = geometry.get(
                "floor"
            )

            if floor is not None:
                return floor

        # ----------------------------------
        # No invented fallback
        # ----------------------------------

        return None

    # ======================================
    # VERTICAL TYPE RESOLUTION
    # ======================================

    def resolve_vertical_type(
        self,
        geometry_type
    ):

        mapping = {

            "stair_geometry":
                "IfcStair",

            "vertical_shaft":
                "IfcTransportElement",

            "ramp_geometry":
                "IfcRamp",

            "accessible_ramp_geometry":
                "IfcRamp",

            "vehicle_ramp_geometry":
                "IfcRamp",

            "vehicle_ramp":
                "IfcRamp"

        }

        return mapping.get(
            geometry_type,
            "IfcBuildingElementProxy"
        )
