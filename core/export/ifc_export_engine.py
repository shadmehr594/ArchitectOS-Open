import os
from datetime import datetime
from collections import Counter, defaultdict


try:
    import ifcopenshell
    import ifcopenshell.guid
    from ifcopenshell.util.placement import get_local_placement

except Exception:
    ifcopenshell = None
    get_local_placement = None


print("######## IFC EXPORT ENGINE v28 LOADED ########")


class IFCExportEngine:

    VERSION = "28.0"


    def __init__(self):

        print(
            f"🏗️ IFC Export Engine v{self.VERSION} ACTIVE"
        )


    # ==================================================
    # CONFIGURATION
    # ==================================================

    def get_building_config(
        self,
        bim_model
    ):

        config = bim_model.get(
            "building_config",
            {}
        )


        if not isinstance(
            config,
            dict
        ):

            config = {}

        # ==========================================
        # ARCHITECTURE-FIRST FLOOR HEIGHT RESOLUTION
        #
        # Priority:
        # 1. explicit building_config.floor_height
        # 2. first authoritative architectural level
        # 3. legacy fallback
        # ==========================================

        resolved_floor_height = config.get(
            "floor_height"
        )


        if not isinstance(
            resolved_floor_height,
            (int, float)
        ):

            level_config = config.get(
                "level_config",
                {}
            )


            if isinstance(
                level_config,
                dict
            ):

                for level_data in level_config.values():

                    if not isinstance(
                        level_data,
                        dict
                    ):

                        continue


                    candidate_height = level_data.get(
                        "height",
                        level_data.get(
                            "floor_height",
                            level_data.get("column_height")
                        )
                    )


                    if isinstance(
                        candidate_height,
                        (int, float)
                    ) and candidate_height > 0:

                        resolved_floor_height = float(
                            candidate_height
                        )

                        break


        if not isinstance(
            resolved_floor_height,
            (int, float)
        ):

            levels = config.get(
                "levels",
                []
            )


            if isinstance(
                levels,
                list
            ):

                for level_data in levels:

                    if not isinstance(
                        level_data,
                        dict
                    ):

                        continue


                    candidate_height = level_data.get(
                        "height"
                    )


                    if isinstance(
                        candidate_height,
                        (int, float)
                    ) and candidate_height > 0:

                        resolved_floor_height = float(
                            candidate_height
                        )

                        break


        if not isinstance(
            resolved_floor_height,
            (int, float)
        ):

            resolved_floor_height = 3.0


        return {

            "floors":
                config.get(
                    "floors",
                    1
                ),

            "floor_height":
                resolved_floor_height,

            "wall_height":
                config.get(
                    "wall_height",
                    3.0
                ),

            "door_height":
                config.get(
                    "door_height",
                    2.1
                ),

            "door_width":
                config.get(
                    "door_width",
                    0.9
                ),

            "window_height":
                config.get(
                    "window_height",
                    1.5
                ),

            "window_width":
                config.get(
                    "window_width",
                    1.2
                ),

            # ==========================================
            # ARCHITECTURE-FIRST LEVEL CONTRACT
            # ==========================================

            "levels":
                list(
                    config.get(
                        "levels",
                        []
                    )
                    or []
                ),

            "level_config":
                dict(
                    config.get(
                        "level_config",
                        {}
                    )
                    or {}
                ),

            "architectural_authority":
                bool(
                    config.get(
                        "architectural_authority",
                        False
                    )
                )

        }


    # ==================================================
    # LEVEL MANAGEMENT
    # ==================================================

    def normalize_level(
        self,
        level
    ):

        if level is None:

            return "F1"


        if isinstance(
            level,
            int
        ):

            return f"F{level}"


        if isinstance(
            level,
            str
        ):

            normalized = level.strip()


            if not normalized:

                return "F1"


            upper_level = normalized.upper()


            # ------------------------------------------
            # LEGACY IFC LEVEL SUPPORT
            # ------------------------------------------

            if upper_level.startswith(
                "F"
            ):

                suffix = upper_level[
                    1:
                ]


                if suffix.isdigit():

                    return upper_level


            if normalized.isdigit():

                return (
                    f"F{normalized}"
                )


            # ------------------------------------------
            # ARCHITECTURE-FIRST LEVEL SUPPORT
            #
            # Preserve authoritative semantic floor names:
            #
            # ground_floor
            # upper_floor
            # roof_level
            # basement
            # ...
            #
            # Do NOT collapse unknown semantic floors to F1.
            # ------------------------------------------

            return normalized


        return str(
            level
        )



    def level_to_elevation(
        self,
        level,
        floor_height=3.2
    ):

        if not level:
            return 0.0


        if isinstance(level, str):

            if level.startswith("F"):

                try:

                    floor_number = int(
                        level.replace(
                            "F",
                            ""
                        )
                    )

                    return (
                        floor_number - 1
                    ) * floor_height


                except Exception:

                    return 0.0


        return 0.0


    # ==================================================
    # ARCHITECTURE-FIRST LEVEL ELEVATION
    # ==================================================

    def resolve_storey_elevation(
        self,
        level,
        building_config,
        floor_height=3.2
    ):

        if not isinstance(
            building_config,
            dict
        ):

            building_config = {}


        # ------------------------------------------
        # PRIORITY 1
        # AUTHORITATIVE LEVEL CONFIG
        # ------------------------------------------

        level_config = building_config.get(
            "level_config",
            {}
        )


        if isinstance(
            level_config,
            dict
        ):

            level_data = level_config.get(
                level
            )


            if isinstance(
                level_data,
                dict
            ):

                base_z = level_data.get(
                    "bottom",
                    level_data.get("base_z")
                )


                if isinstance(
                    base_z,
                    (int, float)
                ):

                    return float(
                        base_z
                    )


        # ------------------------------------------
        # PRIORITY 2
        # ARCHITECTURAL LEVEL LIST
        # ------------------------------------------

        levels = building_config.get(
            "levels",
            []
        )


        if isinstance(
            levels,
            list
        ):

            for level_data in levels:

                if not isinstance(
                    level_data,
                    dict
                ):

                    continue


                if (
                    level_data.get(
                        "name"
                    )
                    !=
                    level
                ):

                    continue


                elevation = level_data.get(
                    "bottom",
                    level_data.get("elevation")
                )


                if isinstance(
                    elevation,
                    (int, float)
                ):

                    return float(
                        elevation
                    )


        # ------------------------------------------
        # PRIORITY 3
        # LEGACY F1 / F2 / F3
        # ------------------------------------------

        return self.level_to_elevation(
            level,
            floor_height
        )


    # ======================
    # ELEMENT Z RESOLVER
    # ======================

    def resolve_element_z(
        self,
        data,
        floor_height
    ):

        print(
            "====== RESOLVE Z DEBUG ======",
            {
                "id": data.get("id"),
                "level_before": data.get("level"),
                "floor_height": floor_height,
                "z_input": data.get("z"),
                "base_z": data.get("base_z"),
                "top_z": data.get("top_z")
            }
        )


        # Element is relative to IfcBuildingStorey
        # Storey already carries elevation

        local_z = data.get(
            "local_z",
            0.0
        )
        


        print(
            "FINAL LOCAL Z RESULT:",
            local_z
        )


        return local_z


    def resolve_element_local_z(
        self,
        data,
        storey_elevation,
    ):
        """Convert authoritative world Z to one storey-relative offset."""
        if not isinstance(data, dict):
            data = {}

        explicit_local_z = data.get("local_z")
        if isinstance(explicit_local_z, (int, float)):
            return float(explicit_local_z)

        world_z = data.get("z", data.get("base_z", data.get("bottom")))
        if isinstance(world_z, (int, float)) and isinstance(
            storey_elevation,
            (int, float),
        ):
            return float(world_z) - float(storey_elevation)

        return 0.0

    # ==================================================
    # EXPORT ENTRY
    # ==================================================

    def export(
        self,
        bim_model,
        output_path=None
    ):


        if ifcopenshell is None:

            raise RuntimeError(
                "IfcOpenShell is not installed."
            )


        elements = bim_model.get(
            "bim_elements",
            []
        )


        # ==================================================
        # LEGACY IFC ENTITY INPUT SUPPORT
        # ==================================================

        if not elements:

            legacy_entities = bim_model.get(
                "ifc_entities",
                []
            )


            for index, item in enumerate(legacy_entities):

                geometry = item.get(
                    "geometry",
                    {}
                )

                elements.append(
                    {
                        "id": f"legacy_{index}",

                        "ifc_type": item.get(
                            "entity"
                        ),

                        "level": item.get(
                            "level"
                        ),

                        "data": geometry,

                        # legacy geometry compatibility
                        **geometry
                    }
                )


        print(
            "\n====== RAW BIM ELEMENT LEVEL CHECK ======"
        )

        for e in elements:

            if e.get("ifc_type") in [
                "IfcStair",
                "IfcTransportElement",
                "IfcBuildingElementProxy"
            ]:

                print(
                    {
                        "type": e.get("ifc_type"),
                        "level": e.get("level"),
                        "data": e.get("data")
                    }
                )

        print(
            "=========================================="
        )

        print(
            "\n====== IFC INPUT TYPE COUNT DEBUG ======"
        )

        print(
            Counter(
                e.get("ifc_type")
                for e in elements
            )
        )

        print(
            "TOTAL BIM ELEMENTS:",
            len(elements)
        )

        print(
            "========================================"
        )


        print(
            "\n====== BIM ELEMENT DIMENSION CONTRACT DEBUG ======"
        )

        for e in elements:

            if e.get("ifc_type") in [
                "IfcColumn",
                "IfcBeam"
            ]:

                data = e.get(
                    "data",
                    {}
                )

                print(
                    {
                        "id": e.get("id"),
                        "type": e.get("ifc_type"),
                        "level": e.get("level"),
                        "x": data.get("x"),
                        "y": data.get("y"),
                        "z": data.get("z"),
                        "width": data.get("width"),
                        "depth": data.get("depth"),
                        "height": data.get("height"),
                        "start": data.get("start"),
                        "end": data.get("end")
                    }
                )


        print(
            "================================================="
        )

        print(
            "\n====== BIM BEAM DUPLICATION CHECK ======"
        )

        seen = {}

        for e in elements:

            if e.get("id","").startswith("beam_"):

                beam_id = e.get("id")

                if beam_id in seen:

                    print(
                        "DUPLICATE BEAM:",
                        beam_id,
                        {
                            "old": seen[beam_id],
                            "new": e
                        }
                    )

                else:

                    seen[beam_id] = e


        print(
            "TOTAL UNIQUE BEAMS:",
            len(seen)
        )


        print(
            "TOTAL BEAM ELEMENTS:",
            len(
                [
                    e for e in elements
                    if e.get("id","").startswith("beam_")
                ]
            )
        )


        print(
            "======================================"
        )


        print("\n====== COLUMN BIM INPUT DEBUG ======")

        for e in elements:
            data = e.get("data", {})

            if e.get("id") in [
                "column_001",
                "column_040",
                "column_080"
            ]:
                print({
                    "id": e.get("id"),
                    "level": e.get("level"),
                    "data": data
                })


        print("\n====== COLUMN BIM RANGE DEBUG ======")

        for e in elements:
            if e.get("id", "").startswith("column_"):
                print(
                    e.get("id"),
                    e.get("level"),
                    e.get("data", {}).get("x"),
                    e.get("data", {}).get("y"),
                    e.get("data", {}).get("z")
                )

        print("\n====== BEAM BIM RANGE DEBUG ======")

        for e in elements:
            if e.get("id", "").startswith("beam_"):
                print(
                    e.get("id"),
                    e.get("level"),
                    e.get("data", {}).get("z"),
                    e.get("data", {}).get("start"),
                    e.get("data", {}).get("end")
                )


        config = self.get_building_config(
            bim_model
        )

        if not elements and not bim_model.get("levels") and not config.get("level_config"):
            raise RuntimeError(
                "ifc_export_unresolved: no BIM elements or authoritative level evidence"
            )


        print(
            "\n====== IFC BIM MODEL KEYS DEBUG ======"
        )

        print(
            bim_model.keys()
        )

        print(
            "\n====== IFC BUILDING CONFIG RAW ======"
        )

        print(
            bim_model.get(
                "building_config"
            )
        )

        print(
            "======================================"
        )

        print(
            "===== BIM MODEL BUILDING CONFIG DEBUG ====="
        )

        print(
            bim_model.get(
                "building_config"
            )
        )


        floor_height = config["floor_height"]


        print(
            "\n====== IFC EXPORT CONFIG ======"
        )


        print(
            config
        )


        # ==================================================
        # IFC WORLD Z HELPER
        # ==================================================

        def get_world_z(product):

            z = 0.0

            placement = product.ObjectPlacement

            while placement:

                if placement.RelativePlacement:

                    coords = (
                        placement
                        .RelativePlacement
                        .Location
                        .Coordinates
                    )

                    z += float(
                        coords[2]
                    )

                placement = placement.PlacementRelTo

            return z

        # ==================================================
        # IFC ELEMENT EXPORT
        # ==================================================

        print("\n====== IFC ELEMENT LEVEL DEBUG ======")

        for e in elements[:50]:

            print(
                e.get("type"),
                "LEVEL=",
                e.get("level"),
                "DATA_LEVEL=",
                e.get("data", {}).get("level")
                if isinstance(e.get("data"), dict)
                else None
            )

        print("====================================")


        # ==================================================
        # BEFORE NORMALIZATION
        # ==================================================

        print("\n====== BEFORE IFC LEVEL NORMALIZATION ======")

        for element in elements:

            if element.get("ifc_type") in [
                "IfcBeam",
                "IfcColumn"
            ]:

                print({
                        "id": element.get("id"),
                        "ifc_type": element.get("ifc_type"),
                        "level": element.get("level"),
                        "data_level": element.get("data", {}).get("level"),
                        "z": element.get("z"),
                        "data_z": element.get("data", {}).get("z")
                    })


        print("\n====== AFTER IFC LEVEL NORMALIZATION ======")

        for element in elements:

            if element.get("ifc_type") in [
                "IfcBeam",
                "IfcColumn"
            ]:

                print({
                    "id": element.get("id"),
                    "ifc_type": element.get("ifc_type"),
                    "level": element.get("level"),
                    "data_level": element.get("data",{}).get("level"),
                    "z": element.get("z"),
                    "data_z": element.get("data",{}).get("z")  
                })

        print("============================================")


        # ----------------------------------------------
        # NORMALIZE ELEMENT LEVELS
        # ----------------------------------------------

        for element in elements:


            if not isinstance(
                element,
                dict
            ):
                continue


            data = element.get(
                "data",
                {}
            )


            data["level"] = self.normalize_level(
                data.get("level")
            )


            element["data"] = data



        print(
            "\n====== IFC LEVEL DEBUG ======"
        )


        print(
            Counter(
                e.get(
                    "data",
                    {}
                ).get(
                    "level"
                )

                for e in elements
            )
        )


        print("\n====== AFTER IFC LEVEL NORMALIZATION ======")

        for element in elements:

            if element.get("ifc_type") in [
                "IfcBeam",
                "IfcColumn"
            ]:

                print({
                    "id": element.get("id"),
                    "ifc_type": element.get("ifc_type"),
                    "level": element.get("level"),
                    "data_level": element.get(
                        "data",
                        {}
                    ).get("level"),
                    "z": element.get("z"),
                    "data_z": element.get(
                        "data",
                        {}
                    ).get("z")
                })

        print("===========================================")

        print("\n========== STATIC LEVEL TEST ==========")

        for e in elements:

            data = e.get(
                "data",
                {}
            )

            if e.get("id") in [
                "wall_001",
                "column_001",
                "beam_001",
                "slab_001",
                "wall_009",
                "column_040",
                "beam_050",
                "slab_002",
                "wall_018",
                "column_080",
                "beam_100",
                "slab_003"
            ]:

                print(
                    {
                        "id": e.get("id"),
                        "type": e.get("ifc_type"),
                        "level": data.get("level"),
                        "z": data.get("z"),
                        "x": data.get("x"),
                        "y": data.get("y")
                    }
                )

        print("======================================")



        # ==================================================
        # CREATE IFC FILE
        # ==================================================


        model = ifcopenshell.file(
            schema="IFC4"
        )


        print(
            "✅ IFC FILE INITIALIZED"
        )



        # ==================================================
        # OWNER HISTORY
        # ==================================================


        person = model.create_entity(
            "IfcPerson"
        )


        organization = model.create_entity(
            "IfcOrganization",
            Name="ArchitectOS"
        )


        person_org = model.create_entity(
            "IfcPersonAndOrganization",
            ThePerson=person,
            TheOrganization=organization
        )


        application = model.create_entity(
            "IfcApplication",
            ApplicationDeveloper=organization,
            Version=self.VERSION,
            ApplicationFullName="ArchitectOS",
            ApplicationIdentifier="ArchitectOS"
        )


        owner_history = model.create_entity(
            "IfcOwnerHistory",
            OwningUser=person_org,
            OwningApplication=application
        )



        # ==================================================
        # WORLD COORDINATE SYSTEM
        # ==================================================


        origin = model.create_entity(
            "IfcCartesianPoint",
            Coordinates=(
                0.0,
                0.0,
                0.0
            )
        )


        z_axis = model.create_entity(
            "IfcDirection",
            DirectionRatios=(
                0.0,
                0.0,
                1.0
            )
        )


        x_axis = model.create_entity(
            "IfcDirection",
            DirectionRatios=(
                1.0,
                0.0,
                0.0
            )
        )


        world_placement = model.create_entity(
            "IfcAxis2Placement3D",
            Location=origin,
            Axis=z_axis,
            RefDirection=x_axis
        )



        context = model.create_entity(
            "IfcGeometricRepresentationContext",
            ContextIdentifier="Body",
            ContextType="Model",
            CoordinateSpaceDimension=3,
            Precision=0.00001,
            WorldCoordinateSystem=world_placement
        )




        project_placement = model.create_entity(
            "IfcLocalPlacement",
            RelativePlacement=world_placement
        )



        # ==================================================
        # IFC ROOT TREE
        # ==================================================


        project = model.create_entity(
            "IfcProject",
            GlobalId=ifcopenshell.guid.new(),
            OwnerHistory=owner_history,
            Name="ArchitectOS Project"
        )


        site = model.create_entity(
            "IfcSite",
            GlobalId=ifcopenshell.guid.new(),
            OwnerHistory=owner_history,
            Name="Site",
            ObjectPlacement=project_placement
        )


        building = model.create_entity(
            "IfcBuilding",
            GlobalId=ifcopenshell.guid.new(),
            OwnerHistory=owner_history,
            Name="Building",
            ObjectPlacement=project_placement
        )



        print(
            "✅ IFC ROOT STRUCTURE CREATED"
        )
        # ==================================================
        # PLACEMENT HELPERS
        # ==================================================

        def create_local_placement(
            x,
            y,
            z=0.0,
            rotation=0.0,
            placement_parent=None
        ):


            import math


            point = model.create_entity(
                "IfcCartesianPoint",
                Coordinates=(
                    float(x or 0),
                    float(y or 0),
                    float(z or 0)
                )
            )


            axis = model.create_entity(
                "IfcDirection",
                DirectionRatios=(
                    0.0,
                    0.0,
                    1.0
                )
            )


            angle = math.radians(
                float(rotation or 0)
            )


            ref_direction = model.create_entity(
                "IfcDirection",
                DirectionRatios=(
                    math.cos(angle),
                    math.sin(angle),
                    0.0
                )
            )

            print(
                "\n====== IFC PLACEMENT INPUT TRACE ======"
            )

            print(
                {
                    "x": x,
                    "y": y,
                    "z": z,
                    "level": level
                }
            )

            print(
                "======================================="
            )


            placement_axis = model.create_entity(
                "IfcAxis2Placement3D",
                Location=point,
                Axis=axis,
                RefDirection=ref_direction
            )


            print( 
                "LOCAL PLACEMENT DEBUG:", 
                { 
                    "x": x, 
                    "y": y, 
                    "z": z, 
                    "rotation": rotation, 
                    "parent": placement_parent 
                } 
            )


            print(
                "\n====== PRODUCT PLACEMENT INPUT DEBUG ======"
            )

            print(
                {
                    "x": x,
                    "y": y,
                    "z": z,
                    "rotation": rotation,
                    "level": level
                }
            )

            print(
                "==========================================="
            )


            placement = model.create_entity(
                "IfcLocalPlacement",
                PlacementRelTo=(
                    placement_parent
                    if placement_parent
                    else project_placement
                ),
                RelativePlacement=placement_axis
            )


            print(
                "FINAL IFC LOCAL PLACEMENT:",
                placement.RelativePlacement.Location.Coordinates
            )


            if placement.PlacementRelTo:

                print(
                    "PARENT PLACEMENT:",
                    placement.PlacementRelTo.RelativePlacement.Location.Coordinates
                )

            print(
                "\n====== PLACEMENT INPUT FINAL CHECK ======"
            )

            print(
                {
                    "point":
                        point,
                    "parent":
                        placement_parent,
                    "result":
                        placement.RelativePlacement.Location.Coordinates
                }
            )

            print(
                "=========================================="
            )


            return placement



        def create_product_placement(
            x,
            y,
            z=0.0,
            rotation=0.0,
            level="F1"
        ):    
            

            print(
                "\n====== PRODUCT PLACEMENT INPUT ======"
            )

            print(
                {
                    "x": x,
                    "y": y,
                    "z": z,
                    "rotation": rotation,
                    "level": level
                }
            )

            print(
                "======================================"
            )


            print(
                "######## USING DEBUGGED IFC EXPORT ENGINE ########"
            )


            print(
                "CALLER TRACE LEVEL DEBUG:",
                {
                    "level": level,
                    "storeys": list(storeys.keys())
                }
            )


            print(
                "\n====== CREATE PRODUCT PLACEMENT STOREYS DEBUG ======"
            )

            print(
                "REQUESTED LEVEL:",
                level
            )

            print(
                "AVAILABLE STOREYS:",
                list(storeys.keys())
            )

            storey_z = (
                storeys[level]
                .ObjectPlacement
                .RelativePlacement
                .Location
                .Coordinates[2]
            )


            print(
                "===== CREATE PRODUCT PLACEMENT DEBUG =====",
                {
                    "x": x,
                    "y": y,
                    "z_input": z,
                    "rotation": rotation,
                    "level": level,
                    "storey_z": storey_z
                }
            )

       
            print(
                "PRODUCT PLACEMENT INPUT:",
                {
                    "level": level,
                    "x": x,
                    "y": y,
                    "local_z": z,
                    "storey_z": storey_z
                }
            )


            print(
                "PRODUCT PLACEMENT FINAL DEBUG:",
                {
                    "level": level,
                    "local_z": z,
                    "storey_elevation":
                        storeys[level].Elevation,
                    "storey_xyz":
                        storeys[level]
                        .ObjectPlacement
                        .RelativePlacement
                        .Location
                        .Coordinates
                }
            )


            print(
                "CREATE PRODUCT PLACEMENT CALL:",
                {
                    "x": x,
                    "y": y,
                    "z": z,
                    "rotation": rotation,
                    "level": level
                }
            )


            print(
                "===== FINAL PRODUCT PLACEMENT TRACE ====="
            )

            print(
                {
                    "level": level,
                    "input_xyz": (x,y,z),
                    "parent_storey": 
                        storeys[level].Name,
                    "parent_z":
                        storeys[level]
                        .ObjectPlacement
                        .RelativePlacement
                        .Location
                        .Coordinates[2]
                }
            )

            print(
                "=========================================="
            )

            print(
                "\n====== BEFORE CREATE LOCAL PLACEMENT ======"
            )

            print(
                {
                    "level": level,
                    "x": x,
                    "y": y,
                    "z_received": z,
                    "rotation": rotation,
                    "storey_z": storey_z,
                    "parent": storeys[level]
                    .ObjectPlacement
                    .RelativePlacement
                    .Location
                    .Coordinates
                }
            )

            print(
                "==========================================="
            )


            placement = create_local_placement(
                x,
                y,
                z,
                rotation,
                storeys[level].ObjectPlacement
            )


            print(
                "\n====== FUNCTION CREATE PLACEMENT RETURN ======"
            )

            print(
                {
                    "level": level,
                    "xyz":
                        placement
                        .RelativePlacement
                        .Location
                        .Coordinates
                        if placement
                        else None,

                    "parent":
                        placement.PlacementRelTo
                        if placement
                        else None
                }
            )

            print(
                "=============================================="
            )


            print(
                "\n====== PRODUCT PLACEMENT OUTPUT ======"
            )

            print(
                {
                    "location":
                        placement.RelativePlacement.Location.Coordinates
                    if placement.RelativePlacement
                    else None
                }
            )

            print(
                "======================================"
            )


            return placement    



        # ==================================================
        # IFC STOREYS
        # ==================================================


        storeys = {}


        levels = bim_model.get(
            "levels",
            []
        )

        if not levels:

            levels = sorted(
                set(
                    e.get(
                        "data",
                        {}
                    ).get(
                        "level",
                        "F1"
                    )
                    for e in elements
                )
            )

        requested_levels = levels


        if not requested_levels:

            requested_levels = levels


        if not requested_levels:


            floor_count = config.get(
                "floors",
                1
            )


            requested_levels = [

                f"F{i}"

                for i in range(
                    1,
                    floor_count + 1
                )

            ]



        # remove duplicates

        requested_levels = list(
            dict.fromkeys(
                [
                    self.normalize_level(level)

                    for level in requested_levels

                ]
            )
        )


        print(
            "FINAL STOREY LEVELS:",
            requested_levels
        )


        print(
            "\n====== IFC STOREY GENERATION ======"
        )


        print(
            requested_levels
        )


        print(
            "REQUESTED IFC LEVELS:",
            requested_levels
        )


        for level in requested_levels:


            print(
                "\n====== STOREY LOOP ITERATION ======"
            )

            print(
                "CURRENT LEVEL:",
                level
            )

            print(
                "CURRENT STOREYS BEFORE CREATE:",
                list(storeys.keys())
            )


            print(
                "===== STOREY HEIGHT INPUT DEBUG =====",
                {
                    "level": level,
                    "floor_height": floor_height
                }
            )


            elevation = self.resolve_storey_elevation(
                level,
                config,
                floor_height
            )

            print(
                "ARCHITECTURE-FIRST STOREY ELEVATION RESOLVED:",
                {
                    "level":
                        level,

                    "elevation":
                        elevation,

                    "level_config":
                        config.get(
                            "level_config",
                            {}
                        ).get(
                            level
                        )
                }
            )


            print(
                "STOREY CREATE INPUT:",
                {
                    "level": level,
                    "elevation": elevation,
                    "floor_height": floor_height
                }
            )


            storey = model.create_entity(
                "IfcBuildingStorey",

                GlobalId=
                    ifcopenshell.guid.new(),

                OwnerHistory=
                    owner_history,

                Name=
                    f"Level {level}",

                Elevation=
                    elevation,

                ObjectPlacement=
                    create_local_placement(
                        0,
                        0,
                        elevation
                    )
            )


            print("\n====== IFC STOREY ELEVATION DEBUG ======")

            for storey_level, existing_storey in storeys.items():

                print(
                    {
                        "level": storey_level,
                        "name": existing_storey.Name,
                        "elevation": existing_storey.Elevation,
                        "placement":
                            existing_storey
                            .ObjectPlacement
                            .RelativePlacement
                            .Location
                            .Coordinates
                    }
                )

            print("========================================")



            print(
                "STOREY Z DEBUG:",
                {
                    "name": storey.Name,
                    "z":
                    storey.ObjectPlacement
                    .RelativePlacement
                    .Location
                    .Coordinates
                }
            )


            storeys[level] = storey

            print(
                "STOREYS AFTER INSERT:",
                list(storeys.keys())
            )


            print(
                "STOREY CREATED:",
                {
                    "level": level,
                    "Elevation": storey.Elevation,
                    "Placement":
                        storey.ObjectPlacement
                        .RelativePlacement
                        .Location
                        .Coordinates
                }
            )


            print("\n====== STOREY DEBUG ======")

            for storey_level, existing_storey in storeys.items():
                print(
                    {
                        "level": storey_level,
                        "Elevation": existing_storey.Elevation,
                        "Placement":
                            existing_storey
                            .ObjectPlacement
                            .RelativePlacement
                            .Location
                            .Coordinates
                    }
                )

            print("==========================")



            print("\n====== IFC STOREY ELEVATION DEBUG ======")

            for level_name, storey in storeys.items():
                print(
                    "STOREY:",
                    level_name,
                    "|",
                    storey.Name,
                    "Elevation=",
                    storey.Elevation
                )

            print("========================================")


            print(
                "STOREYS CREATED:",
                list(storeys.keys())
            )


            print(
                "CREATED STOREY:",
                level,
                "Z=",
                elevation
            )


            print("\n====== STOREY WORLD DEBUG ======")

            for storey_level, existing_storey in storeys.items():

                print(
                    {
                        "level": storey_level,
                        "Elevation": existing_storey.Elevation,
                        "Placement":
                            existing_storey.ObjectPlacement
                            .RelativePlacement
                            .Location
                            .Coordinates
                    }
                )

            print("===============================")



        # ==================================================
        # PROJECT RELATIONSHIPS
        # ==================================================


        model.create_entity(
            "IfcRelAggregates",
            GlobalId=ifcopenshell.guid.new(),
            RelatingObject=project,
            RelatedObjects=[
                site
            ]
        )


        model.create_entity(
            "IfcRelAggregates",
            GlobalId=ifcopenshell.guid.new(),
            RelatingObject=site,
            RelatedObjects=[
                building
            ]
        )


        model.create_entity(
            "IfcRelAggregates",
            GlobalId=ifcopenshell.guid.new(),
            RelatingObject=building,
            RelatedObjects=list(
                storeys.values()
            )
        )


        print(
            "✅ IFC STOREYS READY"
        )



        # ==================================================
        # PRODUCT STORAGE
        # ==================================================

        products = []

        product_levels = {}

        ifc_entity_registry = {}



        from core.bim.geometry.ifc_geometry_provider import (
            IFCGeometryProvider
        )


        geometry_provider = IFCGeometryProvider(
            model,
            owner_history,
            context
        )


        print(
            "✅ IFC GEOMETRY PROVIDER CONNECTED"
        )
        # ==================================================
        # IFC ELEMENT EXPORT
        # ==================================================

        print("\n====== IFC ELEMENT LEVEL DEBUG ======")

        for e in elements[:50]:

            print(
                e.get("type"),
                "LEVEL=",
                e.get("level"),
                "DATA_LEVEL=",
                e.get("data", {}).get("level")
                if isinstance(e.get("data"), dict)
                else None
            )

        print("====================================")


        print("\n====== IFC INPUT STRUCTURAL Z DEBUG ======")

        for element in elements:

            if element.get("ifc_type") in [
                "IfcColumn",
                "IfcBeam"
            ]:

                print(
                    {
                        "id": element.get("id"),
                        "ifc_type": element.get("ifc_type"),
                        "level": element.get("level"),
                        "data_level": element.get("data", {}).get("level"),
                        "z": element.get("z"),
                        "data_z": element.get("data", {}).get("z")
                    }
                )

        print("==========================================")


        for element in elements:


            ifc_type = element.get(
                "ifc_type"
            )
            


            data = element.get(
                "data",
                {}
            )


            level = self.normalize_level(
                data.get("level")
            )


            data["level"] = level

            print(
                "\n====== FINAL IFC ELEMENT INPUT DEBUG ======"
            )

            print(
                {
                    "id": element.get("id"),
                    "type": element.get("ifc_type"),
                    "level": level,
                    "element_z": element.get("z"),
                    "data_z": data.get("z"),
                    "base_z": data.get("base_z"),
                    "top_z": data.get("top_z"),
                    "local_z": data.get("local_z"),
                    "resolved_z": self.resolve_element_z(
                        data,
                        floor_height
                    )
                }
            )

            print(
                "============================================"
            )



            # ==================================================
            # WALL
            # ==================================================

            print(
                "WALL ORIGINAL DATA:",
                element
            )

            print(
                "====== IFC WALL EXPORT INPUT ======"
            )

            print(
                {
                    "id": element.get("id"),
                    "start": element.get("start"),
                    "end": element.get("end"),
                    "dx": element.get("dx"),
                    "dy": element.get("dy"),
                    "level": element.get("level")
                }
            )

            print(
                "=================================="
            )

            if ifc_type == "IfcWall":


                start = data.get(
                    "start",
                    [0, 0]
                )


                end = data.get(
                    "end",
                    [0, 0]
                )


                print(
                    "GEOMETRY WALL DEBUG:",
                    {
                        "id": element.get("id"),
                        "level": level,
                        "x": data.get("x"),
                        "y": data.get("y"),
                        "z": data.get("z"),
                        "start": start,
                        "end": end
                    }
                )


                print(
                    "GEOMETRY INPUT Z DEBUG:",
                    {
                        "id": element.get("id"),
                        "type": "IfcWall",
                        "level": data.get("level"),
                        "x": data.get("x"),
                        "y": data.get("y"),
                        "z": data.get("z")
                    }
                )


                print("\n====== WALL IFC INPUT DEBUG ======")

                print(
                    "WALL:",
                    data
                )

                print(
                    "WALL KEYS:",
                    data.keys()
                )

                print(
                    "START:",
                    data.get("start")
                )

                print(
                    "END:",
                    data.get("end")
                )

                print(
                    "LENGTH:",
                    data.get("length")
                )

                print(
                    "================================="
                )


                print("\n====== EXPORT WALL INPUT TRACE ======")

                print(
                    {
                        "id": element.get("id"),
                        "level": element.get("level"),
                        "data": element.get("data")
                    }
                )

                print(
                    "===================================="
                )


                print(
                    "\n====== IFC WALL ELEMENT BEFORE PROVIDER ======"
                )

                print(
                    {
                        "id": element.get("id"),
                        "level": element.get("level"),
                        "z": element.get("z"),
                        "start": element.get("start"),
                        "end": element.get("end"),
                        "data": element.get("data")
                    }
                )

                print(
                    "=============================================="
                )



                wall_geometry_data = dict(
                    data
                )

                wall_geometry_data.update(
                    {
                        "id": element.get("id"),
                        "level": element.get("level"),
                        "z": element.get("z"),
                        "start": element.get("start"),
                        "end": element.get("end")
                    }
                )


                print(
                    "\n====== WALL DATA FINAL BEFORE PROVIDER ======"
                )

                print(
                    wall_geometry_data
                )

                print(
                    "=============================================="
                )


                print(
                    "\n====== WALL BEFORE PROVIDER DIRECTION CHECK ======"
                )

                print(
                    {
                        "id": element.get("id"),
                        "start": element.get("start"),
                        "end": element.get("end"),
                        "level": element.get("level"),
                        "data": element.get("data")
                    }
                )

                print(
                    "=================================================="
                )


                print(
                    "\n====== CURRENT WALL BEFORE PROVIDER ======"
                )

                print(
                    {
                        "id": wall_geometry_data.get("id"),
                        "start": wall_geometry_data.get("start"),
                        "end": wall_geometry_data.get("end"),
                        "level": wall_geometry_data.get("level"),
                        "type": wall_geometry_data.get("type")
                    }
                )

                print(
                    "==========================================="
                )

                print(
                    "\n====== WALL AXIS DISTRIBUTION BEFORE PROVIDER ======"
                )

                for w in elements:

                    if w.get("type") in [
                        "IfcWall",
                        "wall"
                    ]:

                        s = w.get("start")
                        e = w.get("end")

                        if s and e:

                            print(
                                {
                                    "id": w.get("id"),
                                    "start": s,
                                    "end": e,
                                    "dx": e[0]-s[0],
                                    "dy": e[1]-s[1],
                                    "level": w.get("level")
                                }
                            )

                print(
                    "====================================================="
                )


                print(
                    "\n====== WALL BEFORE GEOMETRY PROVIDER ======"
                )

                print(
                    element
                )

                print(
                    "============================================"
                )

                # ==========================================
                # WALL GEOMETRY FALLBACK FROM ELEMENT DATA
                # ==========================================

                if element.get(
                    "geometry"
                ):


                    geometry = element.get(
                        "geometry"
                    )


                    wall_geometry_data["start"] = geometry.get(
                        "start"
                    )


                    wall_geometry_data["end"] = geometry.get(
                        "end"
                    )


                    wall_geometry_data["height"] = geometry.get(
                        "height"
                    )


                    wall_geometry_data["thickness"] = geometry.get(
                        "thickness"
                    )


                geometry = geometry_provider.create_wall_geometry(
                    wall_geometry_data
                )

                print(
                    "\n====== WALL GEOMETRY BEFORE PLACEMENT ======"
                )

                print(
                    geometry
                )

                print(
                    "============================================"
                )

                print(
                    "WALL GEOMETRY DEBUG:",
                    element.get("id"),
                    "LEVEL=",
                    level,
                    "DATA Z=",
                    data.get("z"),
                    "PLACEMENT ELEV=",
                    self.level_to_elevation(level, floor_height)
                )


                print(
                    "\n====== WALL BEFORE IFC PLACEMENT ======"
                )

                print(
                    {
                        "start": element.get("start"),
                        "end": element.get("end"),
                        "level": element.get("level"),
                        "x": data.get("x", 0),
                        "y": data.get("y", 0),
                        "z": data.get("z", 0)
                    }
                )
 
                print(
                    "========================================"
                )

                print(
                    "\n====== WALL GEOMETRY EXTENT BEFORE IFC ======"
                )

                print(
                    {
                        "id": element.get("id"),
                        "start": start,
                        "end": end,
                        "length": data.get("length"),
                        "width": data.get("width"),
                        "x": data.get("x"),
                        "y": data.get("y")
                    }
                )

                print(
                    "============================================="
                )

                print(
                    "\n====== WALL PLACEMENT INPUT ======"
                )

                print(
                    {
                        "id": element.get("id"),
                        "level": data.get("level"),
                        "x": data.get("x"),
                        "y": data.get("y"),
                        "z": data.get("z"),
                        "elevation": self.level_to_elevation(
                            level,
                            floor_height
                        )
                    }
                )

                print(
                    "=================================="
                )

                print(
                    "\n====== WALL FINAL PLACEMENT INPUT ======"
                )

                print(
                    {
                        "id": element.get("id"),
                        "level": level,
                        "element_z": data.get("z"),
                        "x": data.get("x"),
                        "y": data.get("y")
                    }
                )

                print(
                    "========================================="
                )

                print(
                    "\n====== WALL OBJECT PLACEMENT SOURCE DEBUG ======"
                )

                print(
                    {
                        "id": element.get("id"),
                        "data_x": data.get("x"),
                        "data_y": data.get("y"),
                        "data_z": data.get("z"),
                        "start": element.get("start"),
                        "end": element.get("end"),
                        "level": data.get("level", level),

                        "geometry_position":
                            geometry.Items[0].Position.Location.Coordinates
                            if geometry
                            and hasattr(geometry, "Items")
                            and geometry.Items
                            and geometry.Items[0].Position
                            else None
                    }
                )

                print(
                    "==============================================="
                )

                print(
                    "\n====== WALL GEOMETRY INTERNAL POSITION DEBUG ======"
                )

                geometry_position = None

                try:

                    if geometry is not None:

                        representations = geometry.Representations

                        print(
                            "REPRESENTATIONS:",
                            len(representations)
                        )

                        if representations:

                            representation = representations[0]

                            print(
                                "REPRESENTATION:",
                                representation
                            )

                            print(
                                "ITEMS:",
                                len(representation.Items)
                            )

                            if representation.Items:

                                solid = representation.Items[0]

                                print(
                                    "SOLID:",
                                    solid
                                )

                                print(
                                    "SOLID TYPE:",
                                    solid.is_a()
                                )

                                if solid.Position:

                                    geometry_position = (
                                        solid
                                        .Position
                                        .Location
                                        .Coordinates
                                    )

                except Exception as e:

                    print(
                        "GEOMETRY POSITION DEBUG ERROR:",
                        repr(e)
                    )


                print(
                    {
                        "id": element.get("id"),
                        "data_x": data.get("x"),
                        "data_y": data.get("y"),
                        "data_z": data.get("z"),
                        "start": element.get("start"),
                        "end": element.get("end"),
                        "level": data.get("level", level),
                        "geometry_position": geometry_position
                    }
                )

                print(
                    "===================================================="
                )

                print(
                    "\n====== WALL FINAL COORDINATE HANDOFF ======"
                )

                print(
                    {
                        "id": element.get("id"),

                        "source_start":
                            element.get("start"),

                        "source_end":
                            element.get("end"),

                        "data_start":
                            data.get("start"),

                        "data_end":
                            data.get("end"),

                        "data_x":
                            data.get("x"),

                        "data_y":
                            data.get("y"),

                        "data_z":
                            data.get("z"),

                        "geometry":
                            geometry,

                        "geometry_solid_position":
                            geometry.Representations[0]
                            .Items[0]
                            .Position
                            .Location
                            .Coordinates
                    }
                )

                print(
                    "============================================="
                )


                wall_local_z = self.resolve_element_local_z(
                    data,
                    storeys[data.get("level", level)].Elevation,
                )

                wall = model.create_entity(
                    "IfcWall",

                    GlobalId=
                        ifcopenshell.guid.new(),

                    OwnerHistory=
                        owner_history,

                    Name=
                        element.get("id"),

                    ObjectPlacement=
                        create_product_placement(
                            data.get("x",0),
                            data.get("y",0),
                            wall_local_z,
                            0,
                            data.get("level", level)
                        ),

                    Representation=
                        geometry
                )


                matrix = get_local_placement(
                    wall.ObjectPlacement
                )


                print(
                    "\n====== WALL GEOMETRY + PRODUCT PLACEMENT COMBINED TEST ======"
                )

                print(
                    {
                        "id": element.get("id"),
                        "source_start": element.get("start"),
                        "source_end": element.get("end"),

                    "geometry_solid_position":
                        geometry.Representations[0]
                        .Items[0]
                        .Position
                        .Location
                        .Coordinates
                        if geometry
                        and geometry.Representations
                        and geometry.Representations[0].Items
                        else None,

                    "product_x":
                        data.get("x", 0),

                    "product_y":
                        data.get("y", 0),

                    "product_z":
                        data.get("z", 0),

                    "level":
                        level
                    }
                )

                print(
                    "=============================================================="
                )

                print(
                    "====== WALL WORLD PLACEMENT DEBUG ======"
                )

                print(
                    "WALL:",
                    wall.Name
                )

                print(
                    "LEVEL:",
                    level
                )

                print(
                    "WORLD LOCATION:",
                    matrix[:,3]
                )

                print(
                    "========================================="
                )


                products.append(
                    wall
                )


                print("\n========== STATIC IFC LEVEL TEST ==========")

                for p in products:

                    if p.Name in [
                        "wall_001",
                        "wall_009",
                        "wall_018",
                        "column_001",
                        "column_040",
                        "column_080",
                        "beam_001",
                        "beam_050",
                        "beam_100",
                        "slab_001",
                        "slab_002",
                        "slab_003",
                        "door_001",
                        "window_001"
                    ]:

                        c = (
                            p.ObjectPlacement
                            .RelativePlacement
                            .Location
                            .Coordinates
                        )

                        print(
                            {
                                "id": p.Name,
                                "type": p.is_a(),
                                "XYZ": c
                            }
                        )

                print("==========================================")


                print(
                    "PLACEMENT RESULT:",
                    {
                        "id": wall.Name,
                        "type": wall.is_a(),
                        "level": level,
                        "placement_xyz":
                        wall.ObjectPlacement
                        .RelativePlacement
                        .Location
                        .Coordinates
                        if wall.ObjectPlacement
                        else None
                    }
                )


                product_levels[
                    wall.id()
                ] = level



                print(
                    "CREATED WALL:",
                    element.get("id"),
                    level
                )



            # ==================================================
            # COLUMN
            # ==================================================

            elif ifc_type == "IfcColumn":


                print(
                    "IFC COLUMN PLACEMENT:",
                    data.get("level"),
                    "RAW Z:",
                    data.get("z"),
                    "NORMALIZED LEVEL:",
                    level
                )


                print(
                    "GEOMETRY INPUT Z DEBUG:",
                    {
                        "id": element.get("id"),
                        "type": "IfcColumn",
                        "level": data.get("level"),
                        "x": data.get("x"),
                        "y": data.get("y"),
                        "z": data.get("z")
                    }
                )


                print("\n====== IFC EXPORT INPUT COLUMN ======")

                print({
                    "id": element.get("id"),
                    "level": element.get("level"),
                    "z": element.get("z"),
                    "data_z": element.get(
                        "data",
                        {}
                    ).get("z"),
                    "height": element.get(
                        "data",
                        {}
                    ).get("height")
                })

                print(
                    "====== COLUMN XY SIZE DEBUG ======"
                )

                print(
                    {
                        "id": element.get("id"),
                        "x": data.get("x"),
                        "y": data.get("y"),
                        "size": data.get("size"),
                        "height": data.get("height")
                    }
                )

                print(
                    "=================================="
                )

                print(
                    "====== IFC COLUMN BEFORE PROVIDER ======",
                    {
                        "id": element.get("id"),
                        "level": element.get("level"),
                        "z": element.get("z"),
                        "data_z": element.get("data", {}).get("z"),
                        "height": element.get("height"),
                        "data": element.get("data")
                    }
                )

                print(
                    "\n====== IFC COLUMN FINAL INPUT DEBUG ======"
                )

                print(
                    {
                        "id": element.get("id"),
                        "x": data.get("x"),
                        "y": data.get("y"),
                        "width": data.get("width"),
                        "depth": data.get("depth"),
                        "height": data.get("height"),
                        "level": data.get("level")
                    }
                )

                print(
                    "=========================================="
                )

                print(
                    "\n====== IFC ENGINE COLUMN FINAL INPUT ======"
                )

                print(
                    {
                        "id": element.get("id"),
                        "x": data.get("x"),
                        "y": data.get("y"),
                        "width": data.get("width"),
                        "depth": data.get("depth"),
                        "level": data.get("level")
                    }
                )

                print(
                    "============================================"
                )


                column_geometry_data = dict(data)
                column_geometry_data["z"] = 0.0
                geometry = geometry_provider.create_column_geometry(
                    column_geometry_data
                )

                print(
                    "FINAL IFC COLUMN XYZ:",
                    {
                        "id": element.get("id"),
                        "X": data.get("x"),
                        "Y": data.get("y"),
                        "Z": data.get("z"),
                        "level": level
                    }
                )


                print(
                    "\n========== FINAL IFC COLUMN XYZ =========="
                )

                print(
                    {
                        "id": element.get("id"),
                        "level": level,
                        "x": data.get("x"),
                        "y": data.get("y"),
                        "Z": data.get("z")
                    }
                )

                print(
                    "=========================================="
                )


                print(
                    "COLUMN FINAL IFC PLACEMENT:",
                    {
                        "id": element.get("id"),
                        "level": level,
                        "x": data.get("x"),
                        "y": data.get("y"),
                        "z": data.get("z")
                    }
                )

                print(
                    "FINAL COLUMN INPUT BEFORE IFC:",
                    {
                        "id": element.get("id"),
                        "level": level,
                        "x": data.get("x"),
                        "y": data.get("y"),
                        "z": data.get("z")
                    }
                )


                print(
                    "BEFORE RESOLVE DEBUG:",
                    {
                        "element_id": element.get("id"),
                        "element_level": element.get("level"),
                        "data_level": data.get("level"),
                        "data": data
                    }
                )


                element_z = 0.0


                print(
                    "COLUMN RESOLVED Z DEBUG:",
                    {
                        "id": element.get("id"),
                        "level": level,
                        "resolved_z": element_z,
                        "storey_z":
                            storeys[level]
                            .ObjectPlacement
                            .RelativePlacement
                            .Location
                            .Coordinates[2]
                    }
                )


                print("\n====== COLUMN XY TRACE ======")

                print(
                    {
                        "id": element.get("id"),
                        "level": level,
                        "x": data.get("x", 0),
                        "y": data.get("y", 0),
                        "z": element_z
                    }
                )
                print("=============================\n")

                print(
                    "\n====== COLUMN PLACEMENT INPUT DEBUG ======"
                )

                print(
                    {
                        "id": element.get("id"),
                        "level": level,
                        "data_z": data.get("z"),
                        "resolved_z": self.resolve_element_z(
                            data,
                            floor_height
                        ),
                        "x": data.get("x"),
                        "y": data.get("y")
                    }
                )

                print(
                    "=========================================="
                )

                print(
                    "\n====== ELEMENT Z BEFORE COLUMN PLACEMENT ======"
                )

                print(
                    {
                        "id": element.get("id"),
                        "level": level,
                        "data_z": data.get("z"),
                        "base_z": data.get("base_z"),
                        "top_z": data.get("top_z"),
                        "element_z": element_z,
                        "resolved_z": self.resolve_element_z(
                            data,
                            floor_height
                        )
                    }
                )

                print(
                    "==============================================="
                )


                column_local_z = self.resolve_element_local_z(
                    data,
                    storeys[level].Elevation,
                )

                placement = create_product_placement(
                    data.get(
                        "x",
                        0
                    ),

                    data.get(
                        "y",
                        0
                    ),

                    column_local_z,

                    0,

                    level

                )

                print("\n====== COLUMN FINAL PLACEMENT TRACE ======")
                print(
                    {
                        "id": element.get("id"),
                        "level": level,
                        "x": data.get("x"),
                        "y": data.get("y"),
                        "z": element_z,
                        "height": data.get("height")
                    }
                )
                print("==========================================\n")


                print(
                    "GEOMETRY VS PLACEMENT CHECK",
                    {
                        "id": element.get("id"),
                        "level": level,

                        "storey_z":
                            storeys[level]
                            .ObjectPlacement
                            .RelativePlacement
                            .Location
                            .Coordinates[2],
 
                        "placement":
                            placement
                            .RelativePlacement
                            .Location
                            .Coordinates
                    }
                )

                print(
                    "===== COLUMN DOUBLE Z CHECK =====",
                    {
                        "id": element.get("id"),
                        "level": element.get("level"),
                        "input_z": element.get("z"),
                        "geometry_z":
                            element.get("data", {}).get("z"),
                        "data":
                            element.get("data")
                    }
                )

                print(
                    "====== COLUMN PLACEMENT OBJECT DEBUG ======",
                    {
                        "id": element.get("id"),
                        "placement_xyz":
                            placement.RelativePlacement.Location.Coordinates
                            if placement and placement.RelativePlacement
                            else None,
                        "placement_parent":
                            placement.PlacementRelTo
                            if placement
                            else None
                    }
                )


                column = model.create_entity(
                    "IfcColumn",

                    GlobalId=
                        ifcopenshell.guid.new(),

                    OwnerHistory=
                        owner_history,

                    Name=
                        element.get("id"),

                    ObjectPlacement=
                        placement,

                    Representation=
                        geometry
                )


                print(
                    "\n====== FINAL IFC COLUMN CHECK ======"
                )

                print(
                    {
                        "name": column.Name,

                        "placement":
                            column.ObjectPlacement
                            .RelativePlacement
                            .Location
                            .Coordinates,

                        "representation":
                            column.Representation
                    }
                )

                print(
                    "===================================="
                )


                print(
                    "\n====== COLUMN CREATED PLACEMENT DEBUG ======"
                )

                print(
                    {
                        "id": column.Name,
                        "level": level,

                        "local_xyz":
                            column.ObjectPlacement
                            .RelativePlacement
                            .Location
                            .Coordinates
                            if column.ObjectPlacement
                            and column.ObjectPlacement.RelativePlacement
                            else None,

                        "has_parent":
                            column.ObjectPlacement.PlacementRelTo
                            is not None,

                        "world_z":
                            get_world_z(column)
                    }
                )

                print(
                    "=============================================="
                )



                print(
                    "\n====== IFC WORLD PLACEMENT DEBUG ======"
                )


                placement = column.ObjectPlacement


                print(
                    "IFC EXPORT COLUMN INPUT:",
                    {
                        "id": element.get("id"),
                        "level": element.get("level"),
                        "z": element.get("data",{}).get("z"),
                        "placement_z":
                            placement.RelativePlacement.Location.Coordinates
                            if placement and placement.RelativePlacement
                            else None
                    }
                )

                

                while placement:

                    print(
                        {
                            "object": column.Name,
                            "placement": placement,
                            "relative":
                                placement.RelativePlacement.Location.Coordinates
                                if placement.RelativePlacement
                                else None,
                            "parent":
                                placement.PlacementRelTo
                        }
                    )

                    placement = placement.PlacementRelTo


                print(
                    "========================================"
                )


                print(
                    "COLUMN FINAL IFC PLACEMENT:",
                    {
                        "id": column.Name,
                        "placement":
                            column.ObjectPlacement.RelativePlacement.Location.Coordinates
                            if column.ObjectPlacement
                            else None,

                        "parent":
                            column.ObjectPlacement.PlacementRelTo
                            if column.ObjectPlacement
                            else None
                    } 
                )


                products.append(
                    column
                )


                print(
                    "WORLD Z CHECK:",
                    {
                        "id": column.Name,
                        "level": level,
                        "world_z": get_world_z(column)
                    }
                )


                print("\n========== STATIC IFC LEVEL TEST ==========")

                for p in products:

                    if p.Name in [
                        "wall_001",
                        "wall_009",
                        "wall_018",
                        "column_001",
                        "column_040",
                        "column_080",
                        "beam_001",
                        "beam_050",
                        "beam_100",
                        "slab_001",
                        "slab_002",
                        "slab_003",
                        "door_001",
                        "window_001"
                    ]:

                        c = (
                            p.ObjectPlacement
                            .RelativePlacement
                            .Location
                            .Coordinates
                        )

                        print(
                            {
                                "id": p.Name,
                                "type": p.is_a(),
                                "XYZ": c
                            }
                        )

                print("==========================================")


                print(
                    "PLACEMENT RESULT:",
                    {
                        "id": column.Name,
                        "type": column.is_a(),
                        "level": level,
                        "placement_xyz":
                        column.ObjectPlacement
                        .RelativePlacement
                        .Location
                        .Coordinates
                        if column.ObjectPlacement
                        else None
                    }
                )


                product_levels[
                    column.id()
                ] = level



                print(
                    "CREATED COLUMN:",
                    element.get("id"),
                    level
                )
            

            # ==================================================
            # BEAM
            # ==================================================

            elif ifc_type == "IfcBeam":


                print(
                    "\n====== IFC EXPORT ENGINE BEAM INPUT ======"
                )

                print(
                    {
                        "id": element.get("id"),
                        "level": element.get("level"),
                        "data": element.get("data"),
                    }
                )


                start = data.get(
                    "start",
                    [0, 0]
                )


                end = data.get(
                    "end",
                    [0, 0]
                )


                import math


                rotation = math.degrees(
                    math.atan2(
                        end[1] - start[1],
                        end[0] - start[0]
                    )
                )


                print(
                    "========== IFC BEAM INPUT ==========",
                    {
                        "id": element.get("id"),
                        "level": element.get("level"),
                        "start": element.get("start"),
                        "end": element.get("end"),
                        "z": element.get("z"),
                        "data": element.get("data")
                    }
                )


                print(
                    "GEOMETRY INPUT Z DEBUG:",
                    {
                        "id": element.get("id"),
                        "type": "IfcBeam",
                        "level": data.get("level"),
                        "x": data.get("x"),
                        "y": data.get("y"),
                        "z": data.get("z"),
                        "start": data.get("start"),
                        "end": data.get("end")
                    }
                )


                print("\n========== RAW BEAM DATA FROM BIM ==========")
                print(data)
                print("============================================")


                beam_geometry_data = dict(data)

                print(
                    "\n========== Z TRACE AFTER COPY =========="
                )

                print(
                    "DATA OBJECT:",
                    data
                )

                print(
                    "DATA Z:",
                    data.get("z")
                )

                print(
                    "DATA ELEVATION:",
                    data.get("elevation")
                )

                print(
                    "COPIED OBJECT:",
                    beam_geometry_data
                )

                print(
                    "COPIED Z:",
                    beam_geometry_data.get("z")
                )

                print(
                    "COPIED ELEVATION:",
                    beam_geometry_data.get("elevation")
                )

                print(
                    "SAME Z:",
                    data.get("z") == beam_geometry_data.get("z")
                )

                print(
                    "========================================"
                )

                beam_geometry_data = dict(data)


                beam_height = data.get(
                    "height",
                    0.4
                )


                floor_top_z = data.get(
                    "top_z",
                    data.get(
                        "z",
                        0.0
                    )
                )


                print(
                    "\n====== BEAM Z CALCULATION DEBUG ======"
                )

                print(
                    {
                        "id": data.get("id"),
                        "level": data.get("level"),
                        "raw_z": data.get("z"),
                        "base_z": data.get("base_z"),
                        "top_z": data.get("top_z"),
                        "height": data.get("height"),
                        "calculated_beam_z": (
                            floor_top_z - beam_height
                        )
                    }
                )

                print(
                    "======================================"
                )


                beam_geometry_data["z"] = (
                    data.get(
                        "z",
                        0.0
                    )
                )

                beam_geometry_data["elevation"] = (
                    beam_geometry_data["z"]
                )


                print(
                    "BEAM GEOMETRY DATA BEFORE PROVIDER:",
                    {
                        "id": element.get("id"),
                        "original_data": data,
                        "provider_input": beam_geometry_data
                    }
                )


                print(
                    "BEAM GEOMETRY DATA BEFORE PROVIDER:",
                    {
                        "id": element.get("id"),
                        "original_data": data,
                        "provider_input": beam_geometry_data
                    }
                )


                print(
                    "BEAM GEOMETRY CALL:",
                    {
                        "start": data.get("start"),
                        "end": data.get("end"),
                        "z": data.get("z"),
                        "level": data.get("level")
                    }
                )


                print("\n========== BEAM GEOMETRY DATA BEFORE PROVIDER ==========")
                print(beam_geometry_data)
                print("========================================================\n")


                print("\n====== IFC EXPORT INPUT BEAM ======")

                print({
                    "id": element.get("id"),
                    "level": element.get("level"),
                    "z": element.get("z"),
                    "data_z": element.get(
                        "data",
                        {}
                    ).get("z"),
                    "start": element.get(
                        "data",
                        {}
                    ).get("start"),
                    "end": element.get(
                        "data",
                        {}
                    ).get("end")
                })


                print(
                    "\n========== FINAL IFC BEAM INPUT =========="
                )

                print(
                    {
                        "id": data.get("id"),
                        "level": data.get("level"),
                        "start": data.get("start"),
                        "end": data.get("end"),
                        "z": data.get("z"),
                        "elevation": data.get("elevation")
                    }
                )

                print(
                    "=========================================="
                )


                print(
                    "\n====== FINAL BEAM PROVIDER INPUT ======"
                )

                print({
                    "id": element.get("id"),
                    "source_level": element.get("level"),
                    "data_level": data.get("level"),
                    "source_z": element.get("z"),
                    "data_z": data.get("z"),
                    "provider_z": beam_geometry_data.get("z"),
                    "start": beam_geometry_data.get("start"),
                    "end": beam_geometry_data.get("end")
                })

                print("========================================")


                print("\n====== BEFORE BEAM GEOMETRY PROVIDER ======")

                print(
                    {
                        "id": element.get("id"),
                        "element_level": element.get("level"),
                        "data_level": data.get("level"),
                        "element_z": element.get("z"),
                        "data_z": data.get("z"),
                    }
                )

                print("============================================")


                print(
                    "====== IFC ENGINE BEAM INPUT ======",
                    {
                        "id": element.get("id"),
                        "level": element.get("level"),
                        "z": element.get("z"),
                        "data_z": element.get("data", {}).get("z"),
                        "start": element.get("data", {}).get("start"),
                        "end": element.get("data", {}).get("end")
                    } 
                )


                print(
                    "====== IFC ENGINE BEAM BEFORE PROVIDER ======",
                    {
                        "id": element.get("id"),
                        "level": element.get("level"),
                        "z": element.get("z"),
                        "data": element.get("data")
                    }
                )
 

                geometry = geometry_provider.create_beam_geometry(
                    beam_geometry_data
                )

                print("\n====== AFTER BEAM GEOMETRY PROVIDER ======")

                print(
                    geometry
                )

                print("==========================================")

                print(
                    "\n====== BEAM GEOMETRY REPRESENTATION DEBUG ======"
                )

                print({
                    "id": element.get("id"),
                    "geometry_type": type(geometry),
                    "geometry": geometry
                })

                print("===============================================")


                print(
                    "BEAM GEOMETRY AFTER PROVIDER:",
                    {
                        "id": element.get("id"),
                        "geometry": geometry
                    }
                )


                beam_level = self.normalize_level(
                    data.get(
                        "level",
                        "F1"
                    )
                )


                print(
                    "\n====== BEAM XY CONNECTION DEBUG ======"
                )

                print(
                    {
                        "id": element.get("id"),
                        "level": beam_level,
                        "start": start,
                        "end": end,
                        "length": (
                            ((end[0]-start[0])**2 +
                             (end[1]-start[1])**2)
                            **0.5
                        )
                    }
                )

                print(
                    "======================================"
                )


                print(
                    "\n====== BEAM Z RESOLUTION BEFORE PLACEMENT ======"
                )

                print(
                    {
                        "id": element.get("id"),
                        "level": beam_level,
                        "data_z": data.get("z"),
                        "base_z": data.get("base_z"),
                        "top_z": data.get("top_z"),
                        "resolve_z": self.resolve_element_z(
                            data,
                            floor_height
                        )
                    }
                )

                print(
                    "================================================="
                )


                beam_elevation = data.get(
                    "z",
                    0.0
                )


                print(
                    "IFC BEAM PLACEMENT:",
                    {
                        "id": element.get("id"),
                        "level": beam_level,
                        "raw_z": data.get("z"),
                        "final_z": beam_elevation,
                        "start": start,
                        "end": end
                    }
                )

                print(
                    "FINAL IFC BEAM LOCAL XYZ:",
                    {
                        "id": element.get("id"),
                        "local_z": 0,
                        "storey": beam_level,
                        "storey_elevation": beam_elevation
                    }
                )


                print(
                    "\n========== FINAL IFC BEAM XYZ =========="
                )

                print(
                    {
                        "id": element.get("id"),
                        "level": beam_level,
                        "start": start,
                        "end": end,
                        "Z": beam_elevation
                    }
                )

                print(
                    "========================================="
                )

                print(
                    "BEAM PARENT CHECK:",
                    {
                        "project": project_placement,
                        "placement_z": beam_elevation,
                        "level": beam_level
                    }
                )

                print(
                    "FINAL BEAM INPUT BEFORE IFC:",
                    {
                        "id": element.get("id"),
                        "level": beam_level,
                        "start": start,
                        "end": end,
                        "local_z": 0,
                        "storey_level": beam_level,
                        "original_beam_elevation": beam_elevation
                    }
                )


                print(
                    "BEAM PRODUCT PLACEMENT INPUT:",
                    {
                        "id": element.get("id"),
                        "level": element.get("level"),
                        "data_z": element.get("data", {}).get("z"),
                        "x": element.get("data", {}).get("start"),
                        "y": element.get("data", {}).get("end"),
                    }
                )



                print(
                    "\n====== BEFORE BEAM PRODUCT PLACEMENT ======"
                )

                print({
                    "id": element.get("id"),
                    "beam_level": beam_level,
                    "beam_elevation": beam_elevation,
                    "start": start,
                    "end": end,
                    "rotation": rotation,
                    "placement_z_argument": 0
                })

                print("============================================")

                print("\n====== BEAM XY TRACE ======")
                print(
                    {
                        "id": element.get("id"),
                        "level": beam_level,
                        "start": start,
                        "end": end,
                        "z": beam_elevation
                    }
                )
                print("===========================\n")


                print(
                    "\n====== BEAM FINAL Z DECISION DEBUG ======"
                )

                print(
                    {
                        "id": element.get("id"),
                        "level": level,
                        "storey_elevation":
                            storeys[level].Elevation,
                        "data_z":
                            data.get("z"),
                        "element_z":
                            locals().get("element_z"),
                        "beam_local_z_before_placement":
                            (
                                locals().get("element_z") - storeys[level].Elevation
                                if locals().get("element_z") is not None
                                else None
                            )
                     }
                )

                print(
                    "=========================================="
                )


                print(
                    "\n====== BEAM ELEMENT Z TRACE ======"
                )

                print(
                    {
                        "id": element.get("id"),
                        "element_root_z": element.get("z"),
                        "data_z": data.get("z"),
                        "data_local_z": data.get("local_z"),
                        "data_base_z": data.get("base_z"),
                        "level": level
                    }
                )

                print(
                    "=================================="
                )


                print(
                    "\n====== FINAL BEAM PLACEMENT ARGUMENT ======",
                    {
                        "id": element.get("id"),
                        "level": beam_level,
                        "x": start[0],
                        "y": start[1],
                        "z_argument": beam_elevation,
                        "storey_z": storeys[beam_level]
                        .ObjectPlacement
                        .RelativePlacement
                        .Location
                        .Coordinates[2]
                    }
                )
                print("============================================")


                print(
                    "\n====== BEAM LOCAL Z CONVERSION DEBUG ======"
                )

                storey_elevation = (
                    storeys[beam_level]
                    .ObjectPlacement
                    .RelativePlacement
                    .Location
                    .Coordinates[2]
                )

                beam_world_z = data.get(
                    "z",
                    0.0
                )

                beam_local_z = self.resolve_element_local_z(
                    data,
                    storey_elevation,
                )

                print(
                    {
                        "id": element.get("id"),
                        "level": beam_level,
                        "beam_world_z": beam_world_z,
                        "storey_elevation": storey_elevation,
                        "beam_local_z": beam_local_z
                    }
                )

                print(
                    "=========================================="
                )

                print(
                    "\n====== BEAM LOCAL Z CALCULATION ======"
                )

                storey_z = (
                    storeys[beam_level]
                    .ObjectPlacement
                    .RelativePlacement
                    .Location
                    .Coordinates[2]
                )

                beam_world_z = data.get(
                    "z",
                    0.0
                )

                beam_local_z = self.resolve_element_local_z(
                    data,
                    storey_z,
                )

                print(
                    "\n====== FINAL BEAM LOCAL Z BEFORE PLACEMENT ======"
                )

                print(
                    {
                        "id": element.get("id"),
                        "level": beam_level,
                        "world_z": beam_world_z,
                        "storey_z": storey_z,
                        "calculated_local_z": beam_local_z
                    }
                )

                print(
                    "================================================="
                )


                local_placement = create_product_placement(
                    start[0],
                    start[1],
                    beam_local_z,
                    rotation,
                    beam_level
                )

                print(
                    "\n====== CREATE PRODUCT PLACEMENT RESULT DEBUG ======"
                )

                print(
                    {
                        "beam": element.get("id"),
                        "level": beam_level,
                        "input_local_z": beam_local_z,
                        "placement_xyz":
                            local_placement
                            .RelativePlacement
                            .Location
                            .Coordinates
                            if local_placement
                            else None,

                        "placement_parent":
                            local_placement.PlacementRelTo
                            if local_placement
                            else None,

                        "parent_xyz":
                            local_placement.PlacementRelTo
                            .RelativePlacement
                            .Location
                            .Coordinates
                            if local_placement
                            and local_placement.PlacementRelTo
                            else None
                    }
                )

                print(
                    "===================================================="
                )

                print(
                    "\n====== CREATE PRODUCT PLACEMENT DEBUG ======"
                )

                print(
                    {
                        "beam": element.get("id"),
                        "level": beam_level,
                        "placement": local_placement,
                        "xyz":
                            local_placement
                            .RelativePlacement
                            .Location
                            .Coordinates
                            if local_placement
                            else None,
                        "parent":
                            local_placement.PlacementRelTo
                            if local_placement
                            else None
                    }
                )

                print(
                    "============================================"
                )


                print(
                    "\n====== CREATED BEAM LOCAL PLACEMENT ======"
                )

                print({
                    "id": element.get("id"),
                    "level": beam_level,
                    "placement_xyz":
                        local_placement.RelativePlacement
                        .Location
                        .Coordinates
                        if local_placement
                        and local_placement.RelativePlacement
                        else None,
                    "parent":
                        local_placement.PlacementRelTo
                        if local_placement
                        else None
                })

                print("===========================================")


                print(
                    "\n====== BEAM PARENT STOREY Z DEBUG ======"
                )

                parent = local_placement.PlacementRelTo

                print({
                    "beam": element.get("id"),
                    "level": beam_level,
                    "parent_xyz":
                        parent.RelativePlacement
                        .Location
                        .Coordinates
                        if parent
                        and parent.RelativePlacement
                        else None
                })

                print("========================================")


                print(
                    "FINAL BEAM INPUT BEFORE IFC:",
                    {
                        "id": element.get("id"),
                        "level": beam_level,
                        "start": start,
                        "end": end,
                        "local_z": 0,
                        "storey_z":
                        storeys[beam_level]
                        .ObjectPlacement
                        .RelativePlacement
                        .Location
                        .Coordinates[2]
                    }
                )


                print(
                    "FINAL LOCAL PLACEMENT BEFORE IFC:",
                    local_placement
                    .RelativePlacement
                    .Location
                    .Coordinates
                )

                print(
                    "\n====== FINAL BEAM CREATION INPUT ======"
                )

                print(
                    {
                        "id": element.get("id"),
                        "level": beam_level,
                        "local_placement":
                            local_placement.RelativePlacement.Location.Coordinates,

                        "parent_type":
                            local_placement.PlacementRelTo.is_a()
                            if local_placement.PlacementRelTo
                            else None,

                        "parent_location":
                            local_placement.PlacementRelTo.RelativePlacement.Location.Coordinates
                            if local_placement.PlacementRelTo
                            and local_placement.PlacementRelTo.RelativePlacement
                            else None
                    }
                )

                print(
                    "======================================="
                )

                print(
                    "\n====== FINAL IFC BEFORE CREATE ENTITY ======"
                )

                print(
                    {
                        "id": element.get("id"),
                        "level": beam_level,
                        "local_xyz":
                            local_placement
                            .RelativePlacement
                            .Location
                            .Coordinates,

                        "parent_xyz":
                            local_placement
                            .PlacementRelTo
                            .RelativePlacement
                            .Location
                            .Coordinates
                            if local_placement.PlacementRelTo
                            else None
                    }
                )

                print(
                    "============================================"
                )

                print(
                    "\n====== BEAM REPRESENTATION Z DEBUG ======"
                )

                print(
                    {
                        "beam": element.get("id"),
                        "representation": geometry,
                        "provider_input":
                            beam_geometry_data
                    }
                )

                print(
                    "========================================="
                )

                print(
                    "\n====== FINAL BEAM ENTITY INPUT ======"
                )

                print(
                    {
                        "id": element.get("id"),
                        "level": beam_level,
                        "placement_xyz":
                            local_placement
                            .RelativePlacement
                            .Location
                            .Coordinates

                    }
                )

                print(
                    "====================================="
                )

                print(
                    "\n====== BEFORE BEAM IFC PLACEMENT ======"
                )

                print(
                    {
                        "id": element.get("id"),
                        "start": data.get("start"),
                        "end": data.get("end"),
                        "x": data.get("x"),
                        "y": data.get("y"),
                        "z": data.get("z"),
                        "rotation": data.get("rotation"),
                        "level": data.get("level")
                    }
                )

                print(
                    "========================================"
                )

                start = data.get(
                    "start",
                    [0,0]
                )

                end = data.get(
                    "end",
                    [0,0]
                )


                beam_x = start[0]
                beam_y = start[1]


                beam_rotation = 0.0


                if start[0] == end[0] and start[1] != end[1]:

                    beam_rotation = 90.0


                print(
                    "\n====== BEAM PLACEMENT RESOLUTION DEBUG ======"
                )

                print(
                    {
                        "id": element.get("id"),
                        "start": start,
                        "end": end,
                        "beam_x": beam_x,
                        "beam_y": beam_y,
                        "rotation": beam_rotation
                    }
                )

                print(
                    "=============================================="
                )


                beam = model.create_entity(
                    "IfcBeam",

                    GlobalId=
                        ifcopenshell.guid.new(),

                    OwnerHistory=
                        owner_history,

                    Name=
                        element.get("id"),

                    ObjectPlacement=
                        local_placement,

                    Representation=
                        geometry
                )

                matrix = get_local_placement(
                    beam.ObjectPlacement
                )

                print(
                    "\n====== BEAM CONTAINMENT DEBUG ======"
                )

                print(
                    {
                        "beam": beam.Name,
                        "level": beam_level,
                        "storey_exists":
                            beam_level in storeys,
                        "storey_name":
                            storeys[beam_level].Name
                            if beam_level in storeys
                            else None
                    }
                )

                print(
                    "===================================="
                )


                print(
                    "\n====== CREATED BEAM STOREY DEBUG ======"
                )

                print(
                    {
                        "beam": beam.Name,
                        "placement":
                            beam.ObjectPlacement
                            .RelativePlacement
                            .Location
                            .Coordinates,

                        "parent":
                            beam.ObjectPlacement
                            .PlacementRelTo
                            .RelativePlacement
                            .Location
                            .Coordinates
                            if beam.ObjectPlacement.PlacementRelTo
                            else None
                    }
                )

                print(
                    "========================================"
                )

                print(
                    "====== BEAM WORLD PLACEMENT DEBUG ======"
                )

                print(
                    "BEAM:",
                    beam.Name
                )

                print(
                    "LEVEL:",
                    level
                )

                print(
                    "WORLD LOCATION:",
                    matrix[:,3]
                )

                print(
                    "========================================="
                )
                


                print(
                    "BEAM WORLD Z CHECK:",
                    {
                        "id": beam.Name,
                        "level": beam_level,
                        "world_z": get_world_z(beam)
                    }
                )


                print(
                    "\n====== IFC WORLD PLACEMENT DEBUG ======"
                )


                placement = beam.ObjectPlacement


                while placement:

                    print(
                        {
                            "object": beam.Name,

                            "relative":
                                placement.RelativePlacement.Location.Coordinates
                                if placement.RelativePlacement
                                else None,

                            "parent":
                                placement.PlacementRelTo
                        }
                    )

                    placement = placement.PlacementRelTo


                print(
                    "========================================"
                )


                print(
                    "BEAM WORLD Z CHECK AFTER CREATE:",
                    {
                        "id": beam.Name,
                        "level": beam_level,
                        "relative":
                            beam.ObjectPlacement
                            .RelativePlacement
                            .Location
                            .Coordinates,
                        "world_z":
                            get_world_z(beam)
                    }
                )


                print(
                    "\n====== FINAL CREATED IFC BEAM DEBUG ======"
                )

                print(
                    {
                        "id": beam.Name,
                        "placement": beam.ObjectPlacement,
                        "local_xyz":
                            beam.ObjectPlacement
                            .RelativePlacement
                            .Location
                            .Coordinates,

                        "parent":
                            beam.ObjectPlacement
                            .PlacementRelTo,

                        "parent_xyz":
                            beam.ObjectPlacement
                            .PlacementRelTo
                            .RelativePlacement
                            .Location
                            .Coordinates
                            if beam.ObjectPlacement.PlacementRelTo
                            else None
                    }
                )

                print(
                    "=========================================="
                )


                print(
                    "\n====== CREATED BEAM PLACEMENT CHECK ======"
                )

                print(
                    {
                        "id": beam.Name,
                        "placement":
                            beam.ObjectPlacement
                            .RelativePlacement
                            .Location
                            .Coordinates
                    }
                )

                print(
                    "==========================================="
                )


                print(
                    "REF DIRECTION:",
                    beam.ObjectPlacement
                    .RelativePlacement
                    .RefDirection
                )

                print(
                    "AXIS:",
                    beam.ObjectPlacement
                    .RelativePlacement
                    .Axis
                )


                products.append(
                    beam
                )

                print(
                    "\n====== BEAM STOREY RELATION DEBUG ======"
                )

                print(
                    {
                        "beam": beam.Name,
                        "registered_level":
                            product_levels.get(
                                beam.id()
                            ),
                        "placement_parent":
                            beam.ObjectPlacement
                            .PlacementRelTo
                    }
                )

                print(
                    "========================================"
                )


                print("\n========== STATIC IFC LEVEL TEST ==========")

                for p in products:

                    if p.Name in [
                        "wall_001",
                        "wall_009",
                        "wall_018",
                        "column_001",
                        "column_040",
                        "column_080",
                        "beam_001",
                        "beam_050",
                        "beam_100",
                        "slab_001",
                        "slab_002",
                        "slab_003",
                        "door_001",
                        "window_001"
                    ]:

                        c = (
                            p.ObjectPlacement
                            .RelativePlacement
                            .Location
                            .Coordinates
                        )

                        print(
                            {
                                "id": p.Name,
                                "type": p.is_a(),
                                "XYZ": c
                            }
                        )

                print("==========================================")


                print(
                    "PLACEMENT RESULT:",
                    {
                        "id": beam.Name,
                        "type": beam.is_a(),
                        "level": beam_level,
                        "placement_xyz":
                        beam.ObjectPlacement
                        .RelativePlacement
                        .Location
                        .Coordinates
                        if beam.ObjectPlacement
                        else None
                    }
                )

                print(
                    "BEAM LEVEL REGISTER:",
                    {
                        "id": beam.Name,
                        "level": beam_level
                    }
                )


                product_levels[
                    beam.id()
                ] = beam_level



                print(
                    "CREATED BEAM:",
                    element.get("id"),
                    beam_level,
                    "Z=",
                    beam_elevation
                )



            # ==================================================
            # SLAB
            # ==================================================

            elif ifc_type == "IfcSlab":
            
                print(
                    "SLAB BEFORE PLACEMENT STOREYS:",
                    list(storeys.keys()),
                    "LEVEL:",
                    level
                )

                print(
                    "GEOMETRY INPUT Z DEBUG:",
                    {
                        "id": element.get("id"),
                        "type": "IfcSlab",
                        "level": data.get("level"),
                        "x": data.get("x"),
                        "y": data.get("y"),
                        "z": data.get("z")
                    }
                )


                slab_geometry_data = dict(data)
                slab_geometry_data["z"] = 0.0
                geometry = geometry_provider.create_slab_geometry(
                    slab_geometry_data
                )

                print(
                    "SLAB FINAL IFC PLACEMENT:",
                    {
                        "id": element.get("id"),
                        "level": level,
                        "x": data.get("x"),
                        "y": data.get("y"),
                        "z": data.get("z")
                    }
                )


                slab_local_z = self.resolve_element_local_z(
                    data,
                    storeys[level].Elevation,
                )

                local_placement = create_product_placement(
                    data.get("x",0),
                    data.get("y",0),
                    slab_local_z,
                    0,
                    level
                )


                slab = model.create_entity(
                    "IfcSlab",

                    GlobalId=
                        ifcopenshell.guid.new(),

                    OwnerHistory=
                        owner_history,

                    Name=
                        element.get("id"),

                    ObjectPlacement=
                        local_placement,

                    Representation=
                        geometry
                )


                print(
                    "SLAB Z DEBUG:",
                    {
                        "id": slab.Name,
                        "level": level,
                        "xyz":
                        slab.ObjectPlacement
                        .RelativePlacement
                        .Location
                        .Coordinates
                    }
                )


                print(
                    "\n====== SLAB WORLD PLACEMENT DEBUG ======"
                )

                placement = slab.ObjectPlacement

                while placement:

                    print(
                        {
                            "object": slab.Name,
                            "relative":
                                placement.RelativePlacement.Location.Coordinates
                                if placement.RelativePlacement
                                else None,
                            "parent":
                                placement.PlacementRelTo
                        }
                    )

                    placement = placement.PlacementRelTo


                print(
                    "========================================"
                )


                products.append(
                    slab
                )


                print("\n========== STATIC IFC LEVEL TEST ==========")

                for p in products:

                    if p.Name in [
                        "wall_001",
                        "wall_009",
                        "wall_018",
                        "column_001",
                        "column_040",
                        "column_080",
                        "beam_001",
                        "beam_050",
                        "beam_100",
                        "slab_001",
                        "slab_002",
                        "slab_003",
                        "door_001",
                        "window_001"
                    ]:

                        c = (
                            p.ObjectPlacement
                            .RelativePlacement
                            .Location
                            .Coordinates
                        )

                        print(
                            {
                                "id": p.Name,
                                "type": p.is_a(),
                                "XYZ": c
                            }
                        )

                print("==========================================")


                print(
                    "PLACEMENT RESULT:",
                    {
                        "id": slab.Name,
                        "type": slab.is_a(),
                        "level": level,
                        "placement_xyz":
                        slab.ObjectPlacement
                        .RelativePlacement
                        .Location
                        .Coordinates
                        if slab.ObjectPlacement
                        else None
                    }
                )


                product_levels[
                    slab.id()
                ] = level



                print(
                    "CREATED SLAB:",
                    element.get("id"),
                    level
                )

            

            elif ifc_type == "IfcRamp":

                storey_elevation = storeys[level].Elevation
                ramp_data = dict(data)
                centerline_3d = ramp_data.get("centerline_3d") or ramp_data.get("geometry") or []
                ramp_data["centerline_3d"] = [
                    [point[0], point[1], float(point[2]) - float(storey_elevation)]
                    for point in centerline_3d
                    if isinstance(point, (list, tuple)) and len(point) >= 3
                ]
                representation = geometry_provider.create_vehicle_ramp_geometry(ramp_data)
                local_placement = create_product_placement(0, 0, 0, 0, level)
                ramp = model.create_entity(
                    "IfcRamp",
                    GlobalId=ifcopenshell.guid.new(),
                    OwnerHistory=owner_history,
                    Name=element.get("id", data.get("access_id", "ArchitectOS Vehicle Ramp")),
                    ObjectPlacement=local_placement,
                    Representation=representation,
                    Tag=data.get("access_id"),
                )
                products.append(ramp)
                product_levels[ramp.id()] = level

            elif ifc_type == "IfcStair":

                print(
                    "🏗️ IFC EXPORT STAIR"
                )


                stair_data = dict(data)
                storey_elevation = float(storeys[level].Elevation or 0.0)

                def localize_path(path):
                    return [
                        [float(point[0]), float(point[1]),
                         float(point[2]) - storey_elevation]
                        for point in path or []
                        if isinstance(point, (list, tuple)) and len(point) >= 3
                    ]

                stair_data["centerline"] = localize_path(
                    stair_data.get("centerline") or stair_data.get("walking_line")
                )
                geometry = geometry_provider.create_stair_geometry({"data": stair_data})
                local_placement = create_product_placement(0, 0, 0, 0, level)

                print(
                    "STAIR GEOMETRY DEBUG:",
                    geometry
                )


                stair = model.create_entity(

                    "IfcStair",

                    GlobalId=
                        ifcopenshell.guid.new(),

                    OwnerHistory=
                        owner_history,

                    Name=
                        stair_data.get(
                            "stair_id",
                            "ArchitectOS Stair"
                        ),

                    ObjectPlacement=
                        local_placement,

                    Representation=
                        geometry,

                    Tag=stair_data.get("stair_id")

                )


                products.append(stair)

                product_levels[
                    stair.id()
                ] = level

                complete_flights = [
                    flight for flight in stair_data.get("flights", [])
                    if isinstance(flight, dict)
                    and flight.get("centerline")
                    and isinstance(flight.get("riser_count"), int)
                    and isinstance(flight.get("tread_count"), int)
                    and flight.get("riser_height") is not None
                    and flight.get("tread_depth") is not None
                ]
                if complete_flights and len(complete_flights) == stair_data.get("flight_count"):
                    flight_entities = []
                    for flight_data in complete_flights:
                        local_flight = dict(flight_data)
                        local_flight["centerline"] = localize_path(flight_data["centerline"])
                        flight_representation = geometry_provider.create_stair_flight_geometry(local_flight)
                        flight_entity = model.create_entity(
                            "IfcStairFlight",
                            GlobalId=ifcopenshell.guid.new(),
                            OwnerHistory=owner_history,
                            Name=flight_data.get("flight_id"),
                            ObjectPlacement=create_product_placement(0, 0, 0, 0, level),
                            Representation=flight_representation,
                            Tag=flight_data.get("flight_id"),
                            NumberOfRisers=flight_data.get("riser_count"),
                            NumberOfTreads=flight_data.get("tread_count"),
                            RiserHeight=flight_data.get("riser_height"),
                            TreadLength=flight_data.get("tread_depth"),
                        )
                        flight_entities.append(flight_entity)
                        products.append(flight_entity)
                        product_levels[flight_entity.id()] = level
                    model.create_entity(
                        "IfcRelAggregates",
                        GlobalId=ifcopenshell.guid.new(),
                        OwnerHistory=owner_history,
                        RelatingObject=stair,
                        RelatedObjects=flight_entities,
                    )

                print(
                    "PRODUCTS LIST AFTER STAIR APPEND:",
                    len(products)
                    )

                print(
                    "LAST PRODUCT:",
                    products[-1].is_a(),
                    products[-1].id()
                )


                print(
                    "====== STAIR PRODUCT REGISTER DEBUG ======"
                )

                print(
                    {
                        "type": stair.is_a(),
                        "id": stair.id(),
                        "guid": stair.GlobalId,
                        "placement": stair.ObjectPlacement,
                        "representation": stair.Representation
                    }
                )

                print(
                    "MODEL TYPE DEBUG:",
                    type(model)
                )

                if hasattr(model, "__len__"):
                    print(
                        "MODEL OBJECT DEBUG:",
                        model
                    )

                    print(
                        "MODEL TYPE DEBUG:",
                        type(model)
                    )

                    print(
                        "MODEL MODULE DEBUG:",
                        type(model).__module__
                    )

                    try:
                        print(
                            "MODEL ENTITY COUNT:",
                            len(model)
                        )

                    except Exception as e:

                        print(
                            "MODEL LEN FAILED:",
                            e
                        )

                        try:
                            print(
                                "MODEL BY_TYPE COUNT:",
                                len(model.by_type("IfcProduct"))
                            )

                        except Exception as e2:

                            print(
                                "MODEL BY_TYPE FAILED:",
                                e2
                            )


                    print(
                        "=========================================="
                    )
                else:
                    print(
                        "MODEL HAS NO LEN"
                    )


                print(
                    "=========================================="
                )

                
            elif ifc_type == "IfcTransportElement":

                print(
                    "🛗 IFC EXPORT TRANSPORT ELEMENT"
                )


                geometry = geometry_provider.create_transport_geometry(

                    element

                )


                x, y = element.get(
                    "geometry",
                    [[0,0]]
                )[0]


                local_placement = create_product_placement(
                    x,
                    y,
                    level=element.get(
                        "level",
                        "F1"
                    )
                )

                print(
                    "TRANSPORT GEOMETRY DEBUG:",
                    geometry
                )


                transport = model.create_entity(

                    "IfcTransportElement",

                    GlobalId=
                        ifcopenshell.guid.new(),

                    OwnerHistory=
                        owner_history,

                    Name=
                        element.get(
                            "name",
                            "ArchitectOS Transport"
                        ),

                    ObjectPlacement=
                        local_placement,

                    Representation=
                        geometry

                )

                products.append(transport)

                product_levels[
                    transport.id()
                ] = level

            elif ifc_type == "IfcBuildingElementProxy":

                print(
                    "🛗 IFC EXPORT PROXY ELEMENT"
                )


                if data.get("type") == "vehicle_driveway":
                    driveway_data = dict(data)
                    storey_elevation = storeys[level].Elevation
                    driveway_data["start_z"] = float(data.get("start_z", storey_elevation)) - float(storey_elevation)
                    driveway_data["end_z"] = float(data.get("end_z", data.get("start_z", storey_elevation))) - float(storey_elevation)
                    geometry = geometry_provider.create_driveway_geometry(driveway_data)
                else:
                    geometry = geometry_provider.create_proxy_geometry(element)


                source_points = data.get("polygon") or element.get("geometry", [[0,0]])
                x, y = source_points[0][:2]


                local_placement = create_product_placement(
                    0 if data.get("type") == "vehicle_driveway" else x,
                    0 if data.get("type") == "vehicle_driveway" else y,
                    level=element.get(
                        "level",
                        "F1"
                    )
                )

                print(
                    "PROXY GEOMETRY DEBUG:",
                    geometry
                )


                proxy = model.create_entity(

                    "IfcBuildingElementProxy",

                    GlobalId=
                        ifcopenshell.guid.new(),

                    OwnerHistory=
                        owner_history,

                    Name=
                        data.get("access_id") if data.get("type") == "vehicle_driveway" else element.get(
                            "name",
                            "ArchitectOS Vertical Core"
                        ),

                    ObjectPlacement=
                        local_placement,

                    Representation=
                        geometry

                )

                products.append(proxy)

                product_levels[
                    proxy.id()
                ] = level

            # ==================================================
            # DOOR
            # ==================================================

            elif ifc_type == "IfcDoor":


                print(
                    "GEOMETRY INPUT Z DEBUG:",
                    {
                        "id": element.get("id"),
                        "type": "IfcDoor",
                        "level": data.get("level"),
                        "x": data.get("x"),
                        "y": data.get("y"),
                        "z": data.get("z")
                    }
                )


                geometry = geometry_provider.create_door_geometry(
                    data
                )

                print(
                    "DOOR GEOMETRY DEBUG:",
                    element.get("id"),
                    "LEVEL=",
                    level,
                    "DATA=",
                    data
                )


                door = model.create_entity(
                    "IfcDoor",

                    GlobalId=
                        ifcopenshell.guid.new(),

                    OwnerHistory=
                        owner_history,

                    Name=
                        element.get("id"),

                    ObjectPlacement=
                        create_product_placement(
                            data.get("x",0),
                            data.get("y",0),
                            0,
                            data.get("rotation",0),
                            level
                        ),

                    Representation=
                        geometry
                )


                products.append(
                    door
                )


                print("\n========== STATIC IFC LEVEL TEST ==========")

                for p in products:

                    if p.Name in [
                        "wall_001",
                        "wall_009",
                        "wall_018",
                        "column_001",
                        "column_040",
                        "column_080",
                        "beam_001",
                        "beam_050",
                        "beam_100",
                        "slab_001",
                        "slab_002",
                        "slab_003",
                        "door_001",
                        "window_001"
                    ]:

                        c = (
                            p.ObjectPlacement
                            .RelativePlacement
                            .Location
                            .Coordinates
                        )

                        print(
                            {
                                "id": p.Name,
                                "type": p.is_a(),
                                "XYZ": c
                            }
                        )

                print("==========================================")


                print(
                    "PLACEMENT RESULT:",
                    {
                        "id": door.Name,
                        "type": door.is_a(),
                        "level": level,
                        "placement_xyz":
                        door.ObjectPlacement
                        .RelativePlacement
                        .Location
                        .Coordinates
                        if door.ObjectPlacement
                        else None
                    }
                )


                ifc_entity_registry[
                    element.get("id")
                ] = door


                product_levels[
                    door.id()
                ] = level



                print(
                    "CREATED DOOR:",
                    element.get("id"),
                    level
                )



            # ==================================================
            # WINDOW
            # ==================================================

            elif ifc_type == "IfcWindow":


                print(
                    "GEOMETRY INPUT Z DEBUG:",
                    {
                        "id": element.get("id"),
                        "type": "IfcWindow",
                        "level": data.get("level"),
                        "x": data.get("x"),
                        "y": data.get("y"),
                        "z": data.get("z")
                    }
                )


                geometry = geometry_provider.create_window_geometry(
                    data
                )

                print(
                    "WINDOW GEOMETRY DEBUG:",
                    element.get("id"),
                    "LEVEL=",
                    level,
                    "DATA=",
                    data
                )


                print(
                    "RESOLVED ELEMENT Z:",
                    {
                        "id": element.get("id"),
                        "level": level,
                        "old_z": data.get("z"),
                        "new_z": data.get("z", 0)
                    }
                )


                window = model.create_entity(
                    "IfcWindow",

                    GlobalId=
                        ifcopenshell.guid.new(),

                    OwnerHistory=
                        owner_history,

                    Name=
                        element.get("id"),

                    ObjectPlacement=
                        create_product_placement(
                            data.get("x",0),
                            data.get("y",0),
                            0,
                            data.get("rotation",0),
                            level
                        ),

                    Representation=
                        geometry
                )


                products.append(
                    window
                )


                print("\n========== STATIC IFC LEVEL TEST ==========")

                for p in products:

                    if p.Name in [
                        "wall_001",
                        "wall_009",
                        "wall_018",
                        "column_001",
                        "column_040",
                        "column_080",
                        "beam_001",
                        "beam_050",
                        "beam_100",
                        "slab_001",
                        "slab_002",
                        "slab_003",
                        "door_001",
                        "window_001"
                    ]:

                        c = (
                            p.ObjectPlacement
                            .RelativePlacement
                            .Location
                            .Coordinates
                        )

                        print(
                            {
                                "id": p.Name,
                                "type": p.is_a(),
                                "XYZ": c
                            }
                        )

                print("==========================================")


                print(
                    "PLACEMENT RESULT:",
                    {
                        "id": window.Name,
                        "type": window.is_a(),
                        "level": level,
                        "placement_xyz":
                        window.ObjectPlacement
                        .RelativePlacement
                        .Location
                        .Coordinates
                        if window.ObjectPlacement
                        else None
                    }
                )


                ifc_entity_registry[
                    element.get("id")
                ] = window


                product_levels[
                    window.id()
                ] = level



                print(
                    "CREATED WINDOW:",
                    element.get("id"),
                    level
                )


        # ==================================================
        # PRODUCT PLACEMENT DEBUG
        # ==================================================

        print("\n====== IFC PRODUCT PLACEMENT DEBUG ======")

        for product in products:

            if product.is_a() in [
                "IfcWall",
                "IfcDoor",
                "IfcWindow"
            ]:

                placement = product.ObjectPlacement

                coords = None

                if (
                    placement
                    and placement.RelativePlacement
                    and placement.RelativePlacement.Location
                ):
                    coords = (
                        placement
                        .RelativePlacement
                        .Location
                        .Coordinates
                    )

                print(
                    product.is_a(),
                    "|",
                    product.Name,
                    "| Z=",
                    coords[2] if coords else None,
                    "| XYZ=",
                    coords
                )

        print("========================================")



        # ==================================================
        # OPENING RELATIONSHIPS
        # ==================================================


        walls = [
            e for e in elements
            if e.get("ifc_type") == "IfcWall"
        ]


        doors = [
            e for e in elements
            if e.get("ifc_type") == "IfcDoor"
        ]


        windows = [
            e for e in elements
            if e.get("ifc_type") == "IfcWindow"
        ]



        wall_entities = {

            entity.Name:
                entity

            for entity in products

            if entity.is_a(
                "IfcWall"
            )

        }



        def find_host_wall(
            x,
            y,
            level
        ):

            print("\n====== WALL GENERATION SOURCE DEBUG ======")

            for w in walls:

                start = w.get("start")
                end = w.get("end")


                print(
                    {
                        "id": w.get("id"),
                        "start": start,
                        "end": end,
                        "dx":
                            (
                                end[0] - start[0]
                                if start and end
                                else None
                            ),
                        "dy":
                            (
                                end[1] - start[1]
                                if start and end
                                else None
                            )
                    }
                )

            print("==========================================")

            print("\n====== IFC FILTER WALL AXIS CHECK ======")

            for w in walls:

                start = w.get("start")
                end = w.get("end")

                if start and end:

                    dx = end[0] - start[0]
                    dy = end[1] - start[1]

                    print(
                        {
                            "id": w.get("id"),
                            "start": start,
                            "end": end,
                            "dx": dx,
                            "dy": dy
                        }
                    )

            print("========================================")

            print(
                "\n====== RAW BIM WALLS BEFORE IFC FILTER ======"
            )

            for w in walls:
                print(
                    {
                        "id": w.get("id"),
                        "start": w.get("start"),
                        "end": w.get("end"),
                        "level": w.get("level")
                    }
                )

            print(
                "=============================================="
            )

            x_axis_count = 0
            y_axis_count = 0

            for w in walls:

                s = w.get("start")
                e = w.get("end")

                if s and e:

                    dx = e[0] - s[0]
                    dy = e[1] - s[1]

                    if abs(dx) > abs(dy):
                        x_axis_count += 1

                    else:
                        y_axis_count += 1


            print(
                "====== WALL AXIS SUMMARY ======"
            )

            print(
                {
                    "X_AXIS_WALLS": x_axis_count,
                    "Y_AXIS_WALLS": y_axis_count
                }
            )

            print(
                "==============================="
            )


            for wall in walls:


                data = wall.get(
                    "data",
                    {}
                )


                if self.normalize_level(
                    data.get("level")
                ) != level:

                    continue


                start = data.get(
                    "start",
                    [0,0]
                )


                end = data.get(
                    "end",
                    [0,0]
                )


                min_x = min(
                    start[0],
                    end[0]
                )

                max_x = max(
                    start[0],
                    end[0]
                )


                min_y = min(
                    start[1],
                    end[1]
                )

                max_y = max(
                    start[1],
                    end[1]
                )


                if (
                    min_x - 0.5 <= x <= max_x + 0.5
                    and
                    min_y - 0.5 <= y <= max_y + 0.5
                ):

                    return wall



            return None




        for opening in doors + windows:


            data = opening.get(
                "data",
                {}
            )


            level = self.normalize_level(
                data.get("level")
            )


            x = data.get(
                "x",
                0
            )


            y = data.get(
                "y",
                0
            )


            entity = ifc_entity_registry.get(
                opening.get("id")
            )


            if not entity:
                continue



            host = find_host_wall(
                x,
                y,
                level
            )



            if host:


                host_entity = wall_entities.get(
                    host.get("id")
                )


                if host_entity:


                    opening_entity = model.create_entity(
                        "IfcOpeningElement",

                        GlobalId=
                            ifcopenshell.guid.new(),

                        OwnerHistory=
                            owner_history,

                        Name=
                            f"Opening_{opening.get('id')}",

                        ObjectPlacement=
                            create_product_placement(
                                x,
                                y,
                                0,
                                0,
                                level
                            )

                    )


                    model.create_entity(
                        "IfcRelVoidsElement",

                        GlobalId=
                            ifcopenshell.guid.new(),

                        OwnerHistory=
                            owner_history,

                        RelatingBuildingElement=
                            host_entity,

                        RelatedOpeningElement=
                            opening_entity

                    )



                    model.create_entity(
                        "IfcRelFillsElement",

                        GlobalId=
                            ifcopenshell.guid.new(),

                        OwnerHistory=
                            owner_history,

                        RelatingOpeningElement=
                            opening_entity,

                        RelatedBuildingElement=
                            entity

                    )


                    print(
                        "OPENING CONNECTED:",
                        opening.get("id"),
                        "->",
                        host.get("id")
                    )

                    print(
                        "PRODUCT LEVELS BEFORE CONTAINMENT:"
                    )


                    print(
                        Counter(
                            product_levels.values()
                        )
                    )

                    



        # ==================================================
        # STOREY CONTAINMENT
        # ==================================================


        print("\n====== IFC PRODUCT PLACEMENT DEBUG ======")

        for p in products:

            placement = p.ObjectPlacement

            if placement:
                rel = placement.RelativePlacement

                if rel and rel.Location:
                    print(
                        p.is_a(),
                        "|",
                        p.Name,
                        "| XYZ=",
                        rel.Location.Coordinates
                    )

        print("========================================")


        print("\n====== PRODUCTS BEFORE STOREY RELATION DEBUG ======")

        print(
            "PRODUCT COUNT:",
            len(products)
        )

        for product in products[:20]:

            print(
                {
                    "id": product.id(),
                    "type": product.is_a(),
                    "level": product_levels.get(
                         product.id()
                    )
                }
            )


        storey_products = defaultdict(
            list
        )


        for product in products:


            level = product_levels.get(
                product.id(),
                "F1"
            )


            level = self.normalize_level(
                level
            )


            if level in storeys:

                storey_products[level].append(
                    product
                )



        for level, items in storey_products.items():

            print(
                "\nRELATION DEBUG:",
                level,
                len(items)
            )

            print(
                Counter(
                    x.is_a()
                    for x in items
                )
            )

            print(
                [
                    (
                        x.is_a(),
                        x.Name,
                        x.id()
                    )
                    for x in items[:5]
                ]
            )


            if not items:
                continue

            print(
                "\n====== IFC STOREY CONTAINMENT DEBUG ======"
            )

            for rel in model.by_type(
                "IfcRelContainedInSpatialStructure"
            ):

                related = [
                    obj.Name
                    for obj in rel.RelatedElements
                    if obj.is_a() in [
                        "IfcBeam",
                        "IfcColumn"
                    ]
                ]

                if "beam_002" in related:

                    print(
                        {
                            "relation": rel,
                            "structure":
                                rel.RelatingStructure.Name,
                            "elements":
                                related[:10]
                        }
                    )

            print(
                "=========================================="
            )


            # ==========================
            # CREATE IFC RELATIONS
            # ========================== 


            model.create_entity(
                "IfcRelContainedInSpatialStructure",

                GlobalId=
                    ifcopenshell.guid.new(),

                OwnerHistory=
                    owner_history,

                RelatedElements=
                    items,

                RelatingStructure=
                    storeys[level]

            )


            print(
                "\n====== IFC STOREY CONTAINMENT DEBUG ======"
            )

            for rel in model.by_type(
                "IfcRelContainedInSpatialStructure"
            ):

                related = [
                    obj.Name
                    for obj in rel.RelatedElements
                    if obj.is_a() in [
                        "IfcBeam",
                        "IfcColumn"
                    ]
                ]

                if "beam_002" in related:

                    print(
                        {
                            "structure":
                                rel.RelatingStructure.Name,

                            "elements":
                                related[:10]
                        }
                    )

            print(
                "=========================================="
            )



            print(
                "\n====== IFC CONTAINMENT CREATED ======"
            )

            print(
                "STOREY:",
                level
            )

            print(
                "STOREY NAME:",
                storeys[level].Name
            )

            print(
                "STOREY ELEVATION:",
                storeys[level].Elevation
            )

            for item in items[:10]:

                print(
                    {
                        "id": item.Name,
                        "type": item.is_a(),
                        "parent_storey": level
                    }
                )

            print(
                "====================================="
            )


            print(
                "STOREY CONTENT:",
                level,
                len(items)
            )


            print("\n====== IFC STOREY ELEVATION DEBUG ======")

        for storey in model.by_type("IfcBuildingStorey"):

            print(
                "STOREY:",
                storey.Name,
                "ELEVATION:",
                storey.Elevation
            )

        print("========================================")

        if storeys:
            print(
                "STOREY PLACEMENTS:",
                {
                    storey_level: storey.ObjectPlacement.RelativePlacement.Location.Coordinates
                    for storey_level, storey in storeys.items()
                }
            )
        else:
            print("STOREY PLACEMENTS: unresolved (no authoritative levels)")

        print(
            "==================================="
        )



        # ==================================================
        # WRITE IFC
        # ==================================================

        if output_path:

            self.output_path = output_path

        else:

            self.output_path = os.path.join(
                "exports",
                "ArchitectOS_Project.ifc"
            )


        export_dir = os.path.dirname(os.path.abspath(self.output_path))


        os.makedirs(
            export_dir,
            exist_ok=True
        )


        print("\n====== WALL WORLD PLACEMENT DEBUG ======")

        for wall in model.by_type("IfcWall")[:20]:

            matrix = get_local_placement(
                wall.ObjectPlacement
            )

            print(
                wall.Name,
                "WORLD Z:",
                matrix[2][3]
            )

        print("========================================")


        print("\n====== COLUMN PLACEMENT DEBUG ======")

        for column in list(model.by_type("IfcColumn"))[:10]:

            placement = column.ObjectPlacement

            print(
                "COLUMN:",
                column.Name,
                "LEVEL:",
                column.ContainedInStructure[0].RelatingStructure.Name
                if column.ContainedInStructure
                else None,
                "PLACEMENT:",
                placement.RelativePlacement.Location.Coordinates
            )

        print("====================================")



        print("\n====== BEAM WORLD PLACEMENT DEBUG ======")

        for beam in model.by_type("IfcBeam"):

            matrix = get_local_placement(
                beam.ObjectPlacement
            )


            # find storey
            print("\n====== BEAM WORLD Z VERIFY ======")

            for beam in model.by_type("IfcBeam"):

                matrix = get_local_placement(
                    beam.ObjectPlacement
                )

                print(
                    {
                        "id": beam.Name,
                        "world_xyz": tuple(matrix[:,3])
                    }
                )

                print(
                    "WORLD Z:",
                    matrix[2,3]
                )


            print("================================")


            print(
                "========== BEAM LEVEL WORLD Z VERIFY =========="
            )


            print(
                {
                    "id": beam.Name,
                    "world_z": matrix[2, 3],
                    "placement": beam.ObjectPlacement
                }
            )


            print(
                "WORLD Z:",
                matrix[2, 3]
            )


            print(
                "==============================================="
            )


        print("========================================")


        print("\n====== STRUCTURAL CONNECTION DEBUG ======")

        print(
            "STRUCTURAL GRAPH KEYS:",
            bim_model.get(
                "structural_graph",
                {}
            ).keys()
        )

        print(
            "STRUCTURAL REASONING:",
            bim_model.get(
                "structural_reasoning"
            )
        )

        print(
            "STRUCTURAL DECISION:",
            bim_model.get(
                "structural_decision"
            )
        )

        print("=========================================")


        print("\n====== IFC WORLD PLACEMENT DEBUG ======")


        for element in model.by_type("IfcColumn")[:10]:

            matrix = get_local_placement(
                element.ObjectPlacement
            )

            print(
                element.Name,
                "WORLD Z:",
                matrix[2][3]
            )

        print("======================================")



        ifc_path = self.output_path

        # ==========================
        # CHECK CONTAINMENT
        # ==========================

        print(
            "\n====== BEAM CONTAINMENT DEBUG ======"
        )

        for beam in model.by_type("IfcBeam"):

            if beam.Name in [
                "beam_001",
                "beam_002",
                "beam_BX-F3-1-0"
            ]:

                storey_name = None

                if beam.ContainedInStructure:

                    storey_name = (
                        beam.ContainedInStructure[0]
                        .RelatingStructure
                        .Name
                    )

                print(
                    {
                        "beam": beam.Name,
                        "storey": storey_name,
                        "world_z": get_world_z(beam)
                    }
                )

        print(
            "====================================="
        )


        # 3
        # World placement


        print(
            "\n====== BEFORE IFC WRITE WORLD Z ======"
        )

        print(
            "\n====== FINAL IFC OBJECT PLACEMENT CHECK ======"
        )


        for obj in model.by_type("IfcBeam")[:3]:

            print(
                {
                    "type": obj.is_a(),
                    "name": obj.Name,
                    "placement":
                        obj.ObjectPlacement
                        .RelativePlacement
                        .Location
                        .Coordinates
                        if obj.ObjectPlacement
                        else None
                }
            )


        for obj in model.by_type("IfcColumn")[:3]:

            print(
                {
                    "type": obj.is_a(),
                    "name": obj.Name,
                    "placement":
                        obj.ObjectPlacement
                        .RelativePlacement
                        .Location
                        .Coordinates
                        if obj.ObjectPlacement
                        else None
                }
            )


        print(
            "=============================================="
        )

        beam = next(
            (
                b for b in model.by_type("IfcBeam")
                if b.Name == "beam_002"
            ),
            None
        )


        if beam:

            print(
                {
                    "name": beam.Name,
                    "world_matrix":
                        get_local_placement(
                            beam.ObjectPlacement
                        )
                }
            )

        else:

            print(
                "DEBUG BEAM beam_002 NOT FOUND"
            )

        print(
            "======================================"
        )

        print(
            "\n====== BEFORE IFC WRITE PLACEMENT CHECK ======"
        )

        for obj in model.by_type("IfcBeam")[:3]:

            print(
                {
                    "name": obj.Name,
                    "placement":
                        obj.ObjectPlacement
                        .RelativePlacement
                        .Location
                        .Coordinates
                }
            )


        for obj in model.by_type("IfcColumn")[:3]:

            print(
                {
                    "name": obj.Name,
                    "placement":
                        obj.ObjectPlacement
                        .RelativePlacement
                        .Location
                        .Coordinates
                }
            )

        print(
            "=============================================="
        )


        # 4

        print(
            "\n====== FINAL IFC WRITE PATH DEBUG ======"
        )

        print(
            "output_path:",
            output_path
        )

        print(
            "self.output_path:",
            self.output_path
        )

        print(
            "ifc_path:",
            ifc_path
        )

        print(
            "========================================"
        )

        model.write(
            ifc_path
        )

        print(
            "\n====== RELOAD IFC WORLD Z CHECK ======"
        )


        test_model = ifcopenshell.open(
            ifc_path
        )


        for beam in test_model.by_type("IfcBeam"):

            if beam.Name in [
                "beam_001",
                "beam_002",
                "beam_BX-F3-1-0"
            ]:

                matrix = get_local_placement(
                    beam.ObjectPlacement
                )

                print(
                    {
                        "name": beam.Name,
                        "world_z": matrix[2][3]
                    }
                )


        print(
            "======================================"
        )


        print("\n====== IFC WORLD Z VALIDATION ======")

        for element in (
            model.by_type("IfcColumn")[:10]
            +
            model.by_type("IfcBeam")[:10]
            +
            model.by_type("IfcWall")[:10]
        ):

            placement = element.ObjectPlacement

            print(
                element.is_a(),
                "|",
                element.Name,
                "| LOCAL:",
                placement.RelativePlacement.Location.Coordinates
            )

        print("====================================")


        print(
            "✅ IFC CREATED:",
            ifc_path
        )



        # ==================================================
        # IFC SUMMARY
        # ==================================================


        summary = {


            "IfcBuildingStorey":

                [
                    {
                        "id": storey.Name,
                        "level": level,
                        "elevation": storey.Elevation
                    }

                    for level, storey
                    in storeys.items()
                ],



            "IfcWall":

                [
                    e for e in elements
                    if e.get("ifc_type")
                    ==
                    "IfcWall"
                ],



            "IfcColumn":

                [
                    e for e in elements
                    if e.get("ifc_type")
                    ==
                    "IfcColumn"
                ],



            "IfcBeam":

                [
                    e for e in elements
                    if e.get("ifc_type")
                    ==
                    "IfcBeam"
                ],



            "IfcSlab":

                [
                    e for e in elements
                    if e.get("ifc_type")
                    ==
                    "IfcSlab"
                ],



            "IfcDoor":

                [
                    e for e in elements
                    if e.get("ifc_type")
                    ==
                    "IfcDoor"
                ],



            "IfcWindow":

                [
                    e for e in elements
                    if e.get("ifc_type")
                    ==
                    "IfcWindow"
                ]

        }



        return {


            "engine":
                f"ifc_export_v{self.VERSION}",


            "status":
                "exported",


            "format":
                "IFC4",


            "path":
                ifc_path,


            "real_ifc":
                True,


            "created":
                datetime.now().isoformat(),


            "ifc_model":
                {
                    "entities":
                        summary
                }

        }
