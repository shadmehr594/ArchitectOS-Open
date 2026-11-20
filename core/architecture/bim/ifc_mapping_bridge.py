"""
ArchitectOS IFC Mapping Bridge V2.1

Maps enriched BIM elements into IFC semantic elements.

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
        |
        v
IFC Geometry Intent


Design Principle
----------------
This bridge is a semantic mapper.

It MUST NOT invent architectural decisions.

It preserves:

- architectural type
- element identity
- level
- geometry
- geometry intent
- semantic role
- material information
- architectural metadata

No hardcoded:

- levels
- dimensions
- elevations
- wall thickness
- slab thickness
- roof form
- structural dimensions
"""


class IFCMappingBridge:

    VERSION = "2.1"


    def __init__(
        self,
        context=None
    ):

        print(
            f"🔗 IFC MAPPING BRIDGE v{self.VERSION} ONLINE"
        )

        self.context = context or {}


    # ======================================
    # MAIN MAPPING
    # ======================================

    def map(
        self,
        bim_enriched
    ):

        if not isinstance(
            bim_enriched,
            dict
        ):

            return {

                "ifc_elements": [],

                "element_count": 0,

                "source":
                    "ifc_mapping_v2.1"

            }


        elements = bim_enriched.get(
            "bim_elements",
            []
        )


        ifc_elements = []


        for element in elements:

            if not isinstance(
                element,
                dict
            ):
                continue


            mapped = (
                self._map_element(
                    element
                )
            )


            if mapped:

                ifc_elements.append(
                    mapped
                )


        return {

            "ifc_elements":
                ifc_elements,

            "element_count":
                len(
                    ifc_elements
                ),

            "source":
                "ifc_mapping_v2.1"

        }


    # ======================================
    # ELEMENT MAPPING
    # ======================================

    def _map_element(
        self,
        element
    ):

        element_type = element.get(
            "type"
        )


        name = element.get(
            "name"
        )


        level = element.get(
            "level"
        )


        geometry = self._resolve_geometry(
            element
        )


        semantic_role = (
            self._resolve_semantic_role(
                element
            )
        )


        material = (
            self.extract_material(
                element
            )
        )


        metadata = (
            self._build_metadata(
                element,
                semantic_role
            )
        )


        mapped = {

            # --------------------------------
            # IFC identity
            # --------------------------------

            "ifc_class":
                element_type,

            "name":
                name,

            "level":
                level,

            # --------------------------------
            # Architectural geometry
            # --------------------------------

            "geometry":
                geometry,

            "geometry_intent":
                (
                    dict(
                        element.get(
                            "geometry_intent"
                        )
                    )
                    if isinstance(
                        element.get(
                            "geometry_intent"
                        ),
                        dict
                    )
                    else {}
                ),

            # --------------------------------
            # Material
            # --------------------------------

            "material":
                material,

            # --------------------------------
            # Semantic role
            # --------------------------------

            "semantic_role":
                semantic_role,

            # --------------------------------
            # Semantic metadata
            # --------------------------------

            "metadata":
                metadata

        }


        # ==================================
        # PRESERVE ADDITIONAL ARCHITECTURAL
        # CONTRACT DATA
        #
        # IFC Mapping is a semantic mapping
        # layer. It must not discard resolved
        # architectural identity / topology.
        # ==================================

        reserved = {

            "type",
            "name",
            "level",

            "geometry",
            "geometry_intent",

            "material",
            "material_layer",

            "role",
            "semantic_role",

            "metadata"

        }


        for key, value in element.items():

            if key in reserved:

                continue


            if key not in mapped:

                mapped[key] = value


        return mapped

    # ======================================
    # GEOMETRY
    # ======================================

    def _resolve_geometry(
        self,
        element
    ):

        geometry = {}


        # ----------------------------------
        # Primary geometry
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
        # Geometry intent
        # ----------------------------------

        geometry_intent = (
            element.get(
                "geometry_intent"
            )
        )


        if isinstance(
            geometry_intent,
            dict
        ):

            for key, value in (
                geometry_intent.items()
            ):

                if value is None:
                    continue


                if key not in geometry:

                    geometry[key] = value


        # ----------------------------------
        # Preserve explicit architectural
        # fields
        # ----------------------------------

        architectural_fields = (

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


        for field in architectural_fields:

            value = element.get(
                field
            )


            if value is None:
                continue


            geometry[field] = value


        return geometry


    # ======================================
    # MATERIAL
    # ======================================

    def extract_material(
        self,
        element
    ):

        layers = element.get(
            "material_layer"
        )


        if isinstance(
            layers,
            list
        ):

            return layers


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


        return []


    # ======================================
    # SEMANTIC ROLE
    # ======================================

    def _resolve_semantic_role(
        self,
        element
    ):

        semantic_role = element.get(
            "semantic_role"
        )


        if semantic_role:

            return semantic_role


        role = element.get(
            "role"
        )


        if role:

            return role


        return self._detect_role(
            element
        )


    # ======================================
    # ROLE DETECTION
    # ======================================

    def _detect_role(
        self,
        element
    ):

        element_type = element.get(
            "type"
        )


        if element_type == "IfcSpace":

            return "architectural_space"


        if element_type == "IfcWall":

            return "wall"


        if element_type == "IfcSlab":

            return "floor_system"


        if element_type == "IfcWindow":

            return "opening"


        if element_type == "IfcDoor":

            return "opening"


        if element_type == "IfcStair":

            return "vertical_circulation"


        if element_type == "IfcRoof":

            return "roof"


        if element_type == "IfcColumn":

            return "structural_support"


        if element_type == "IfcBeam":

            return "structural_frame"


        return "architectural_element"


    # ======================================
    # METADATA
    # ======================================

    def _build_metadata(
        self,
        element,
        semantic_role
    ):

        metadata = {

            "source":
                element.get(
                    "source",
                    "architectural_intelligence"
                ),

            "architectural_role":
                semantic_role,

            "semantic_role":
                semantic_role

        }


        # ----------------------------------
        # Preserve original metadata
        # ----------------------------------

        original_metadata = (
            element.get(
                "metadata"
            )
        )


        if isinstance(
            original_metadata,
            dict
        ):

            for key, value in (
                original_metadata.items()
            ):

                if value is None:
                    continue


                metadata[key] = value


        return metadata
