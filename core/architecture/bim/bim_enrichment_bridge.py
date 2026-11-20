"""
ArchitectOS BIM Enrichment Bridge V2.1

Architecture-driven BIM enrichment layer.

Pipeline:

Architectural Intelligence
        |
        v
Architectural Geometry
        |
        v
Architectural To BIM
        |
        v
BIM Enrichment
        |
        v
IFC Mapping

Design Principle
----------------
This layer MUST preserve architectural decisions.

It must NOT invent:

- floor levels
- dimensions
- structural dimensions
- wall thicknesses
- slab thicknesses
- roof forms
- opening relations
- circulation logic

When architectural information is unavailable,
the value remains unresolved instead of being
replaced by a hardcoded architectural decision.
"""


class BIMEnrichmentBridge:

    VERSION = "2.1"

    def __init__(
        self,
        context=None
    ):

        print(
            f"BIM ENRICHMENT BRIDGE v{self.VERSION} ONLINE"
        )

        self.context = context or {}

    # ======================================
    # MAIN ENRICHMENT
    # ======================================

    def enrich(
        self,
        bim_data
    ):

        if not isinstance(
            bim_data,
            dict
        ):

            return {
                "bim_elements": [],
                "element_count": 0,
                "source": "bim_enrichment_v2.1"
            }

        elements = bim_data.get(
            "bim_elements",
            []
        )

        enriched_elements = []

        for element in elements:

            if not isinstance(
                element,
                dict
            ):
                continue

            enriched = self._enrich_element(
                element
            )

            enriched_elements.append(
                enriched
            )

        return {

            "bim_elements":
                enriched_elements,

            "element_count":
                len(
                    enriched_elements
                ),

            "source":
                "bim_enrichment_v2.1"

        }

    # ======================================
    # ELEMENT ENRICHMENT
    # ======================================

    def _enrich_element(
        self,
        element
    ):

        element_type = element.get(
            "type"
        )

        geometry = self._merge_geometry(
            element
        )

        level = self.resolve_level(
            element,
            geometry
        )

        semantic_role = (
            self.resolve_semantic_role(
                element
            )
        )

        enriched = {

            # --------------------------------
            # IFC / BIM identity
            # --------------------------------

            "type":
                element_type,

            "name":
                element.get(
                    "name"
                ),

            "level":
                level,

            # --------------------------------
            # REAL GEOMETRY
            # --------------------------------

            "geometry":
                geometry,

            # --------------------------------
            # ARCHITECTURAL GEOMETRY INTENT
            # --------------------------------

            "geometry_intent":
                self.geometry_intent(
                    element,
                    geometry
                ),

            # --------------------------------
            # ARCHITECTURAL SEMANTICS
            # --------------------------------

            "semantic_role":
                semantic_role,

            # --------------------------------
            # MATERIALS
            # --------------------------------

            "material_layer":
                self.resolve_material(
                    element
                ),

            # --------------------------------
            # PROVENANCE
            # --------------------------------

            "source":
                element.get(
                    "source",
                    "architectural_intelligence"
                )

        }

        # ==================================
        # PRESERVE ADDITIONAL ARCHITECTURAL
        # DATA
        # ==================================

        reserved = {

            "type",
            "name",
            "level",
            "geometry",
            "geometry_intent",
            "role",
            "semantic_role",
            "material",
            "material_layer",
            "source"

        }

        for key, value in element.items():

            if key in reserved:
                continue

            if key not in enriched:

                enriched[key] = value

        return enriched

    # ======================================
    # GEOMETRY MERGING
    # ======================================

    def _merge_geometry(
        self,
        element
    ):

        geometry = {}

        # ----------------------------------
        # Base geometry
        # ----------------------------------

        source_geometry = element.get(
            "geometry"
        )

        if isinstance(
            source_geometry,
            dict
        ):

            geometry.update(
                source_geometry
            )

        # ----------------------------------
        # Existing geometry intent
        # ----------------------------------

        intent = element.get(
            "geometry_intent"
        )

        if isinstance(
            intent,
            dict
        ):

            for key, value in intent.items():

                if value is None:
                    continue

                if key not in geometry:

                    geometry[key] = value

        # ----------------------------------
        # Explicit architectural geometry
        # fields
        # ----------------------------------

        geometry_fields = (

            "height",
            "width",
            "depth",
            "length",
            "thickness",
            "x",
            "y",
            "z",
            "position",
            "rotation",
            "alignment",
            "profile",
            "shape",
            "roof_form",
            "continuity",
            "elevation",
            "floor",
            "space",
            "opening_type",
            "facade_relation"

        )

        for field in geometry_fields:

            value = element.get(
                field
            )

            if value is not None:

                geometry[field] = value

        return geometry

    # ======================================
    # LEVEL RESOLUTION
    # ======================================

    def resolve_level(
        self,
        element,
        geometry=None
    ):

        geometry = (
            geometry
            if isinstance(
                geometry,
                dict
            )
            else {}
        )

        # ----------------------------------
        # Explicit BIM level
        # ----------------------------------

        level = element.get(
            "level"
        )

        if level:

            return level

        # ----------------------------------
        # Explicit architectural floor
        # ----------------------------------

        floor = element.get(
            "floor"
        )

        if floor:

            return floor

        # ----------------------------------
        # Geometry floor
        # ----------------------------------

        floor = geometry.get(
            "floor"
        )

        if floor:

            return floor

        # ----------------------------------
        # Geometry level
        # ----------------------------------

        level = geometry.get(
            "level"
        )

        if level:

            return level

        # ----------------------------------
        # No inference
        # ----------------------------------

        return None

    # ======================================
    # SEMANTIC ROLE
    # ======================================

    def resolve_semantic_role(
        self,
        element
    ):

        role = element.get(
            "semantic_role"
        )

        if role:

            return role

        role = element.get(
            "role"
        )

        if role:

            return role

        return "architectural_element"

    # ======================================
    # GEOMETRY INTENT
    # ======================================

    def geometry_intent(
        self,
        element,
        geometry=None
    ):

        geometry = (
            geometry
            if isinstance(
                geometry,
                dict
            )
            else {}
        )

        element_type = element.get(
            "type"
        )

        # ==================================
        # WALL
        # ==================================

        if element_type == "IfcWall":

            return {

                "category":
                    "boundary",

                "height":
                    geometry.get(
                        "height"
                    ),

                "thickness":
                    geometry.get(
                        "thickness"
                    ),

                "alignment":
                    geometry.get(
                        "alignment"
                    )

            }

        # ==================================
        # SLAB
        # ==================================

        if element_type == "IfcSlab":

            return {

                "category":
                    "floor_system",

                "thickness":
                    geometry.get(
                        "thickness"
                    ),

                "level":
                    geometry.get(
                        "level",
                        geometry.get(
                            "floor"
                        )
                    ),

                "elevation":
                    geometry.get(
                        "elevation"
                    )

            }

        # ==================================
        # WINDOW
        # ==================================

        if element_type == "IfcWindow":

            return {

                "category":
                    "opening",

                "opening":
                    True,

                "facade_relation":
                    geometry.get(
                        "facade_relation"
                    ),

                "opening_type":
                    geometry.get(
                        "opening_type"
                    )

            }

        # ==================================
        # DOOR
        # ==================================

        if element_type == "IfcDoor":

            return {

                "category":
                    "opening",

                "opening":
                    True,

                "opening_type":
                    geometry.get(
                        "opening_type"
                    ),

                "space":
                    geometry.get(
                        "space"
                    )

            }

        # ==================================
        # COLUMN
        # ==================================

        if element_type == "IfcColumn":

            return {

                "category":
                    "structural_support",

                "profile":
                    geometry.get(
                        "profile"
                    ),

                "height":
                    geometry.get(
                        "height"
                    )

            }

        # ==================================
        # ROOF
        # ==================================

        if element_type == "IfcRoof":

            return {

                "category":
                    "top_closure",

                "form":
                    geometry.get(
                        "roof_form",
                        geometry.get(
                            "shape"
                        )
                    ),

                "height":
                    geometry.get(
                        "height"
                    )

            }

        # ==================================
        # STAIR
        # ==================================

        if element_type == "IfcStair":

            return {

                "category":
                    "vertical_circulation",

                "continuity":
                    geometry.get(
                        "continuity"
                    )

            }

        # ==================================
        # SPACE
        # ==================================

        if element_type == "IfcSpace":

            return {

                "category":
                    "architectural_space",

                "shape":
                    geometry.get(
                        "shape"
                    ),

                "height":
                    geometry.get(
                        "height"
                    )

            }

        # ==================================
        # GENERIC
        # ==================================

        return {

            "category":
                "architectural_element"

        }

    # ======================================
    # MATERIAL
    # ======================================

    def resolve_material(
        self,
        element
    ):

        # ----------------------------------
        # Existing material layers
        # ----------------------------------

        material_layer = element.get(
            "material_layer"
        )

        if isinstance(
            material_layer,
            list
        ):

            return material_layer

        # ----------------------------------
        # Single material
        # ----------------------------------

        material = element.get(
            "material"
        )

        if material:

            return [

                {

                    "material":
                        material,

                    "role":
                        "finish"

                }

            ]

        # ----------------------------------
        # Unresolved material
        # ----------------------------------

        return []

    # ======================================
    # CONTEXT ACCESS
    # ======================================

    def context_value(
        self,
        key,
        default=None
    ):

        return self.context.get(
            key,
            default
        )


# ==========================================
# BACKWARD COMPATIBILITY
# ==========================================

BIMEnrichmentBridgeV2 = BIMEnrichmentBridge