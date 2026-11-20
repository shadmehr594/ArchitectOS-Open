"""
ArchitectOS Architectural Semantic Context V1.2

Single source of truth between
Architectural Geometry and IFC Semantic Builders.

Level ownership is derived from source geometry.
No level is inferred from entity names.
No fixed F1/F2/F3 levels are created.
"""


class ArchitecturalSemanticContextV1:

    VERSION = "1.2"


    def __init__(
        self,
        geometry
    ):

        print(
            f"🧠 ARCHITECTURAL SEMANTIC CONTEXT v{self.VERSION} ONLINE"
        )

        self.geometry = geometry or {}


    # ======================================
    # BUILD CONTEXT
    # ======================================

    def build(self):

        levels = []

        spaces = []

        elements = []

        relationships = []


        # ======================================
        # LEVEL REGISTRY
        # ======================================

        level_registry = {}


        def register_level(
            level,
            source=None
        ):

            if not level:

                return


            if level not in level_registry:

                level_registry[level] = {

                    "level":
                        level,

                    "sources":
                        []

                }


            if source:

                level_registry[level][
                    "sources"
                ].append(
                    source
                )


        # ======================================
        # SPACES
        # ======================================

        for space in self.geometry.get(
            "spaces",
            []
        ):

            if not isinstance(
                space,
                dict
            ):

                continue


            level = (

                space.get(
                    "floor"
                )

                or

                space.get(
                    "level"
                )

            )


            register_level(
                level,
                "space"
            )


            spaces.append({

                "name":
                    space.get(
                        "name"
                    ),

                "level":
                    level,

                "height":
                    space.get(
                        "height"
                    )

            })


        # ======================================
        # WALLS
        # ======================================

        for wall in self.geometry.get(
            "walls",
            []
        ):

            if not isinstance(
                wall,
                dict
            ):

                continue


            level = (

                wall.get(
                    "floor"
                )

                or

                wall.get(
                    "level"
                )

            )


            register_level(
                level,
                "wall"
            )


            elements.append({

                "name":
                    wall.get(
                        "name"
                    ),

                "ifc_class":
                    "IfcWall",

                "level":
                    level

            })


        # ======================================
        # SLABS
        # ======================================

        for slab in self.geometry.get(
            "slabs",
            []
        ):

            if not isinstance(
                slab,
                dict
            ):

                continue


            level = (

                slab.get(
                    "floor"
                )

                or

                slab.get(
                    "level"
                )

            )


            register_level(
                level,
                "slab"
            )


            elements.append({

                "name":
                    slab.get(
                        "name"
                    ),

                "ifc_class":
                    "IfcSlab",

                "level":
                    level

            })


        # ======================================
        # OPENINGS
        # ======================================

        for opening in self.geometry.get(
            "openings",
            []
        ):

            if not isinstance(
                opening,
                dict
            ):

                continue


            level = (

                opening.get(
                    "floor"
                )

                or

                opening.get(
                    "level"
                )

            )


            register_level(
                level,
                "opening"
            )


            elements.append({

                "name":
                    opening.get(
                        "name"
                    ),

                "ifc_class":
                    "IfcWindow",

                "level":
                    level,

                "space":
                    opening.get(
                        "space"
                    ),

                "opening_type":
                    opening.get(
                        "type"
                    )

            })


        # ======================================
        # BOUNDARIES
        # ======================================

        for boundary in self.geometry.get(
            "boundaries",
            []
        ):

            if not isinstance(
                boundary,
                dict
            ):

                continue


            level = (

                boundary.get(
                    "floor"
                )

                or

                boundary.get(
                    "level"
                )

            )


            register_level(
                level,
                "boundary"
            )


            relationships.append({

                "type":
                    "space_boundary",

                "space":
                    boundary.get(
                        "space"
                    ),

                "level":
                    level

            })


        # ======================================
        # EXPLICIT LEVEL DATA
        # ======================================
        #
        # If Architectural Geometry already
        # provides a dedicated "levels" collection,
        # preserve it as the authoritative source.
        #

        source_levels = self.geometry.get(
            "levels",
            []
        )


        if isinstance(
            source_levels,
            list
        ):

            for item in source_levels:

                if isinstance(
                    item,
                    str
                ):

                    register_level(
                        item,
                        "level"
                    )

                elif isinstance(
                    item,
                    dict
                ):

                    level = (

                        item.get(
                            "level"
                        )

                        or

                        item.get(
                            "name"
                        )

                    )


                    register_level(
                        level,
                        "level"
                    )


        # ======================================
        # FINAL LEVEL LIST
        # ======================================

        levels = list(
            level_registry.values()
        )


        # ======================================
        # DEBUG
        # ======================================

        print(
            "\n=== SEMANTIC LEVEL REGISTRY ==="
        )


        for level_data in levels:

            print(
                "LEVEL:",
                level_data["level"],
                "SOURCES:",
                level_data["sources"]
            )


        print(
            "Spaces:",
            len(spaces)
        )


        print(
            "Elements:",
            len(elements)
        )


        print(
            "Levels:",
            len(levels)
        )


        # ======================================
        # RETURN CONTEXT
        # ======================================

        return {

            "levels":
                levels,

            "spaces":
                spaces,

            "elements":
                elements,

            "relationships":
                relationships

        }