import os
import uuid
from copy import deepcopy
from datetime import datetime


from core.export.production_export_engine import (
    ProductionExportEngine
)

from core.export.ifc_export_engine import (
    IFCExportEngine
)

from core.export.cad_exporter import (
    CADExporter
)

from core.export.revit_package_generator import (
    RevitPackageGenerator
)

from core.export.revit_build_plan_generator import (
    RevitBuildPlanGenerator
)

from core.export.revit_adapter import (
    RevitAdapter
)



# ==========================================
# OPTIONAL DWG CONVERTER
# ==========================================

try:

    from core.export.dwg.dwg_converter import (
        DWGConverter
    )

except Exception:

    DWGConverter = None



class ExportOrchestrator:


    VERSION = "1.3"

    @staticmethod
    def create_run_id(label=None):
        prefix = "".join(
            character for character in str(label or "run")
            if character.isalnum() or character in {"-", "_"}
        ).strip("-_") or "run"
        return (
            prefix
            + "_"
            + datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            + "_"
            + uuid.uuid4().hex[:8]
        )



    def __init__(self):

        print(
            f"🚀 Export Orchestrator v{self.VERSION} ACTIVE"
        )


        self.production = (
            ProductionExportEngine()
        )


        self.ifc = (
            IFCExportEngine()
        )


        self.cad = (
            CADExporter()
        )


        self.dwg_converter = DWGConverter() if DWGConverter is not None else None



        self.revit = (
            RevitPackageGenerator()
        )


        self.revit_build_plan = (
            RevitBuildPlanGenerator()
        )


        self.revit_adapter = (
            RevitAdapter()
        )




    # ==========================================
    # CAD NORMALIZER
    # ==========================================

    def _normalize_cad_input(
        self,
        spatial
    ):


        if not spatial:

            return {
                "nodes": {}
            }



        if "nodes" in spatial:

            return spatial



        nodes = {}



        for level in spatial.get(
            "levels",
            []
        ):


            for index, space in enumerate(
                level.get(
                    "spaces",
                    []
                )
            ):


                nodes[space] = {


                    "x":
                        index * 5,


                    "y":
                        0,


                    "w":
                        5,


                    "h":
                        5,


                    "connections":
                        []

                }



        return {

            "nodes":
                nodes

        }




    # ==========================================
    # BIM ELEMENT CONTRACT
    # ==========================================

    def _build_bim_elements(
        self,
        bim_state
    ):


        elements = []


        geometry = bim_state.get(
            "geometry",
            {}
        )


        structure = bim_state.get(
            "structure",
            {}
        )



        def collect(
            items,
            prefix,
            ifc_type
        ):


            for index,item in enumerate(items):


                print(
                    "COLLECT BIM ELEMENT:",
                    ifc_type,
                    item
                )


                elements.append({


                    "id":
                        f"{prefix}_{index}",


                    "type":
                        ifc_type,


                    "ifc_type":
                        ifc_type,


                    "data":
                        item

                })


        print(
            "COLLECT BIM ELEMENT:",
            ifc_type,
            item
        )




        collect(
            geometry.get(
                "walls",
                []
            ),
            "wall",
            "IfcWall"
        )



        collect(
            geometry.get(
                "floors",
                []
            ),
            "slab",
            "IfcSlab"
        )



        collect(
            geometry.get(
                "doors",
                []
            ),
            "door",
            "IfcDoor"
        )



        collect(
            geometry.get(
                "windows",
                []
            ),
            "window",
            "IfcWindow"
        )



        collect(
            geometry.get(
                "rooms",
                []
            ),
            "space",
            "IfcSpace"
        )



        collect(
            structure.get(
                "columns",
                []
            ),
            "column",
            "IfcColumn"
        )



        collect(
            structure.get(
                "beams",
                []
            ),
            "beam",
            "IfcBeam"
        )


        return elements




    # ==========================================
    # EXPORT PIPELINE
    # ==========================================

    def export(
        self,
        bim_state,
        output_dir="exports"
    ):


        # ==================================
        # EXPORT SESSION ROUTER
        # ==================================

        session = (
            bim_state.get(
                "export_session",
                "DEFAULT"
            )
        )


        session_dirs = {

            "ARCHITECTURE_ONLY_DXF":
                "ARCHITECTURE_ONLY_DXF",

            "DESIGN_TO_BIM_REAL_GEOMETRY":
                "DESIGN_TO_BIM_REAL_GEOMETRY",

            "DEFAULT":
                "DEFAULT"

        }


        folder = session_dirs.get(
            session,
            "DEFAULT"
        )


        output_dir = os.path.join(
            output_dir,
            folder,
            self.create_run_id(bim_state.get("run_id")),
        )

        output_dir = os.path.abspath(output_dir)

        bim_state["run_id"] = os.path.basename(output_dir)


        os.makedirs(
            output_dir,
            exist_ok=True
        )


        print(
            "\n====== EXPORT SESSION ROUTER ======"
        )


        print(
            "OUTPUT DIR:",
            os.path.abspath(
                output_dir
            )
        )

        print(
            "=================================="
        )


        print(
            "📦 EXPORT PIPELINE START"
        )


        # ==========================
        # BUILDING CONFIG BRIDGE
        # ==========================

        if "building_config" not in bim_state:

            bim_state["building_config"] = {

                "floors":
                    len(
                        set(
                            e.get("level")
                            for e in bim_state.get(
                                "bim_elements",
                                []
                            )
                            if e.get("level")
                        )
                    ),

                "floor_height":
                    3.2,

                "wall_height":
                    3.2,

                "door_height":
                    2.1,

                "door_width":
                    0.9,

                "window_height":
                    1.5,

                "window_width":
                    1.2

            }


        print(
            "\n====== BUILDING CONFIG BRIDGE ======"
        )

        print(
            bim_state["building_config"]
        )



        result = {


            "engine":
                f"EXPORT_ORCHESTRATOR_v{self.VERSION}",


            "created":
                datetime.now().isoformat(),


            "status":
                "started"

            ,"run_id": bim_state["run_id"]

            ,"output_dir": os.path.abspath(output_dir)

        }


        print("\n====== EXPORT ORCHESTRATOR INPUT DEBUG ======")

        print(
            "BIM STATE KEYS:",
            bim_state.keys()
        )


        print(
            "BIM ELEMENT COUNT:",
            len(
                bim_state.get(
                    "bim_elements",
                    []
                )
            )
        )


        if "ifc_model" in bim_state:

            print(
                "IFC MODEL KEYS:",
                bim_state["ifc_model"].keys()
            )


        print(
            "GEOMETRY INPUT TYPES:",
            {
                k: type(v)
                for k,v in bim_state.get(
                    "geometry",
                    {}
                ).items()
            }
        )


        print(
            "GEOMETRY COUNTS:",
            {
                k: len(v)
                for k,v in bim_state.get(
                    "geometry",
                    {}
                ).items()
                if isinstance(v,list)
            }
        )


        print("\n====== EXPORT ORCHESTRATOR INPUT DEBUG ======")

        print(
            "BIM STATE KEYS:",
            bim_state.keys()
        )


        if "ifc_model" in bim_state:

            print(
                "IFC MODEL KEYS:",
                bim_state["ifc_model"].keys()
            )


            print(
                "IFC ENTITY TOTAL:",
                sum(
                    len(v)
                    for v in bim_state["ifc_model"].get(
                        "entities",
                        {}
                    ).values()
                    if isinstance(v,list)
                )
            )


        print(
            "BIM ELEMENT COUNT:",
            len(
                bim_state.get(
                    "bim_elements",
                    []
                )
            )
        )




        # ==================================
        # IFC
        # ==================================

        try:

            print(
                "\n====== CALL IFC EXPORT ENGINE ======"
            )

            print("\n====== STRUCTURE SOURCE BEFORE IFC ======")

            bim_elements = bim_state.get(
                "bim_elements",
                []
            )

            

            print("\n====== BEFORE IFC ENGINE BIM Z TRACE ======")

            for element in bim_elements:
                if element.get("ifc_type") in [
                    "IfcBeam",
                    "IfcColumn"
                ]:
                    print(
                        {
                            "id": element.get("id"),
                            "ifc": element.get("ifc_type"),
                            "level": element.get("level"),
                            "z": element.get("z")
                        }
                    )

            print("==========================================")

            print(
                "STRUCTURE SOURCE COUNT:",
                len(bim_elements)
            )


            for e in bim_elements:

                if not isinstance(e, dict):
                    continue

                if e.get("ifc_type") in [
                    "IfcBeam",
                    "IfcColumn"
                ]:
                    print(
                        "STRUCTURE SOURCE:",
                        e.get("id"),
                        e.get("ifc_type"),
                        e.get("data")
                    )


            print("\n====== STRUCTURE SOURCE BEFORE IFC ======")

            beam_count = 0
            column_count = 0

            for e in bim_elements:

                if e.get("ifc_type") == "IfcBeam":

                    beam_count += 1

                    if beam_count <= 10:
                        print(
                            "BEAM:",
                            {
                                "id": e.get("id"),
                                "data": e.get("data")
                            }
                        )


                if e.get("ifc_type") == "IfcColumn":

                    column_count += 1

                    if column_count <= 10:
                        print(
                            "COLUMN:",
                            {
                                "id": e.get("id"),
                                "data": e.get("data")
                            }
                        )


            print(
                "TOTAL STRUCTURE BEFORE IFC:",
                {
                    "beams": beam_count,
                    "columns": column_count
                }
            )

            print(
                "BIM ELEMENT COUNT:",
                len(
                    bim_state.get(
                        "bim_elements",
                        []
                    )
                )
            )

            print("\n====== STRUCTURE SOURCE BEFORE IFC ======")

            bim_elements = bim_state.get(
                "bim_elements",
                []
            )

            print(
                "STRUCTURE SOURCE COUNT:",
                len(bim_elements)
            )


            for e in bim_elements:

                if not isinstance(e, dict):
                    continue

                if e.get("ifc_type") in [
                    "IfcBeam",
                    "IfcColumn"
                ]:

                    print(
                        "STRUCTURE SOURCE:",
                        e.get("id"),
                        e.get("ifc_type"),
                        e.get("data")
                    )

            from collections import Counter

            print(
                "FINAL BIM TYPES:",
                Counter(
                    e.get("ifc_type")
                    for e in bim_elements
                )
            )


            for e in bim_elements:

                if e.get("ifc_type") in [
                    "IfcWall",
                    "IfcDoor",
                    "IfcWindow",
                    "IfcSlab"
                ]:

                    print(
                        e.get("ifc_type"),
                        e.get("id"),
                        e.get("data")
                    )


            print("\n====== BIM ELEMENT LEVEL BEFORE IFC ======")

            for e in bim_elements:

                if e.get("ifc_type") in [
                    "IfcWall",
                    "IfcDoor",
                    "IfcWindow",
                    "IfcSlab",
                    "IfcBeam",
                    "IfcColumn"
                ]:

                    print(
                        e.get("ifc_type"),
                        e.get("id"),
                        "LEVEL=",
                        e.get("data", {}).get("level")
                    )


            from collections import Counter

            print("\n====== BIM TYPE COUNT BEFORE IFC ======")

            print(
                Counter(
                    e.get("ifc_type")
                    for e in bim_elements
                )
            )


            print("\n====== BIM LEVEL COUNT BEFORE IFC ======")

            print(
                Counter(
                    e.get("data", {}).get("level")
                    for e in bim_elements
                )
            )


            print("\n====== BIM ELEMENT LEVEL BEFORE IFC ======")

            for e in bim_elements:

                if e.get("ifc_type") in [
                    "IfcWall",
                    "IfcDoor",
                    "IfcWindow",
                    "IfcSlab"
                ]:

                    print(
                        e.get("ifc_type"),
                        e.get("id"),
                        "LEVEL=",
                        e.get("data", {}).get("level")
                    )

            print("====================================")


            # ==================================================
            # BIM GEOMETRY DEBUG
            # ==================================================

            print("\n====== BIM GEOMETRY DEBUG ======")

            for e in bim_elements:

                if e.get("ifc_type") in [
                    "IfcWall",
                    "IfcSlab"
                ]:

                    print(
                        e.get("ifc_type"),
                        e.get("id"),
                        e.get("data")
                    )

            print("================================")


            # ==================================================
            # IFC EXPORT
            # ==================================================

            ifc_result = self.ifc.export(
                bim_state,
                output_path=os.path.join(output_dir, "ArchitectOS_Project.ifc")
            )


            print("\n====== IFC OBJECT ID DEBUG ======")

            print(
                "IFC RESULT ID:",
                id(ifc_result)
            )

            print(
                "IFC RESULT KEYS:",
                ifc_result.keys()
            )

            print(
                "HAS PATH:",
                "path" in ifc_result
            )

            print(
                "HAS IFC_MODEL:",
                "ifc_model" in ifc_result
            )

            print(
                "IFC RESULT PATH FIELDS:",
                {
                    "path": ifc_result.get("path"),
                    "file": ifc_result.get("file"),
                    "filepath": ifc_result.get("filepath"),
                    "output": ifc_result.get("output")
                }
            )

            print("\n====== IFC RESULT FULL DEBUG ======")

            print(type(ifc_result))

            print(ifc_result)

            result["ifc"] = ifc_result

            print(
                "\n====== AFTER IFC RESULT STORE ======"
            )

            print(
                "RESULT KEYS:",
                result.keys()
            )

            print(
                "RESULT IFC:",
                result.get("ifc")
            )

            print(
                "\n====== AFTER IFC RESULT KEYS ======"
            )

            print(
                result.keys()
            )

            print(
                result["ifc"]
            )

            print("\n====== AFTER IFC RESULT STORE DEBUG ======")

            print(
                "RESULT IFC ID:",
                id(result["ifc"])
            )

            print(
                "RESULT IFC KEYS:",
                result["ifc"].keys()
            )

            print(
                "AFTER IFC RESULT KEYS:",
                result.keys()
            )

            print("\n====== RESULT IFC STORE DEBUG ======")

            print(
                result.get("ifc")
            )


            print(
                "IFC ENGINE RETURN TYPE:",
                type(ifc_result)
            )


            if isinstance(ifc_result, dict):

                print(
                    "IFC ENGINE KEYS:",
                    ifc_result.keys()
                )

                print(
                    "IFC STATUS:",
                    ifc_result.get("status")
                )

                print(
                    "IFC PATH:",
                    ifc_result.get("path")
                )

                print(
                    "IFC MODEL COUNT:",
                    sum(
                        len(v)
                        for v in ifc_result.get(
                            "entities",
                            {}
                        ).values()
                        if isinstance(v,list)
                    )
                )


                # ==============================
                # REAL IFC FILE CONTENT DEBUG
                # ==============================

                ifc_path = (
                    ifc_result.get("path")
                    or
                    ifc_result.get("file")
                    or
                    ifc_result.get("filepath")
                )


                print(
                    "DEBUG IFC PATH BEFORE CHECK:",
                    ifc_path
                )


                if ifc_path and os.path.exists(ifc_path):


                    with open(
                        ifc_path,
                        "r",
                        errors="ignore"
                    ) as f:

                        content = f.read()


                    for token in [
                        "IFCWALL",
                        "IFCCOLUMN",
                        "IFCBEAM",
                        "IFCSLAB",
                        "IFCDOOR",
                        "IFCWINDOW",
                        "IFCOPENINGELEMENT",
                        "IFCRELVOIDSELEMENT",
                        "IFCRELFILLSELEMENT"
                    ]:

                        print(
                            token,
                            token in content.upper()
                        )


                    print(
                        "IFC TEXT LENGTH:",
                        len(content)
                    )


                    import re


                    entity_count = len(
                        re.findall(
                            r"=IFC[A-Z0-9_]+",
                            content.upper()
                        )
                    )


                    print(
                        "REAL IFC ENTITY COUNT:",
                        entity_count
                    )


                else:

                    print(
                        "⚠️ IFC FILE DOES NOT EXIST OR PATH MISSING"
                    )



        except Exception as e:

            import traceback

            print(
                "\n====== IFC EXPORT FAILED ======"
            )

            print(
                traceback.format_exc()
            )

            result["ifc"] = {

                "status":
                    "failed",

                "error":
                    str(e)

            }

            raise




        # ==================================
        # DXF / CAD
        # ==================================

        dxf_file = os.path.join(
            output_dir,
            "ArchitectOS_Project_ARCHITECTURE_ONLY.dxf"
        )


        try:

            # ==================================
            # RESTORE ARCHITECTURAL GEOMETRY
            # ==================================

            if not bim_state.get("geometry"):

                project_geometry = (
                    bim_state
                    .get(
                        "project",
                        {}
                    )
                    .get(
                        "geometry",
                        {}
                    )
                )

                if project_geometry:

                    print(
                        "\n====== RESTORE GEOMETRY FROM PROJECT ======"
                    )

                    print(
                        "PROJECT GEOMETRY KEYS:",
                        project_geometry.keys()
                    )

                    bim_state["geometry"] = (
                        project_geometry
                    )

            # ==================================


            spatial = (

                self._normalize_cad_input(

                    bim_state.get(
                        "spatial",
                        {}
                    )

                )

            )

            print(
                "\n====== CAD GEOMETRY INPUT ======"
            )

            geometry = bim_state.get(
                "geometry",
                {}
            )

            # The parcel/courtyard contract lives under site, while the CAD
            # writer consumes architectural geometry. Preserve the source and
            # expose the parcel as an external-space plan layer for drafting.
            geometry = deepcopy(geometry) if isinstance(geometry, dict) else {}
            if not geometry.get("external_spaces"):
                site_contract = bim_state.get("site", {})
                if not isinstance(site_contract, dict):
                    site_contract = {}
                building_strategy = site_contract.get("building_strategy", {})
                if not isinstance(building_strategy, dict):
                    building_strategy = {}
                parcel_boundary = (
                    building_strategy.get("parcel_boundary")
                    or site_contract.get("parcel_boundary")
                    or site_contract.get("boundary")
                )
                if isinstance(parcel_boundary, list) and len(parcel_boundary) >= 3:
                    geometry["external_spaces"] = [
                        {
                            "name": "yard",
                            "type": "yard",
                            "footprint": {"points": deepcopy(parcel_boundary)},
                            "source": "site.building_strategy.parcel_boundary",
                        }
                    ]

            print(
                "WALLS:",
                len(
                    geometry.get(
                        "walls",
                        []
                    )
                )
            )

            print(
                "ROOMS:",
                len(
                    geometry.get(
                        "rooms",
                        []
                    )
                )       
            )

            print(
                "DOORS:",
                len(
                    geometry.get(
                        "doors",
                        []
                    )
                )
            )

            print(
                "WINDOWS:",
                len(
                    geometry.get(
                        "windows",
                        []
                    )
                )
            )

            print(
                "FLOORS:",
                len(
                    geometry.get(
                        "floors",
                        []
                    )
                )
            )

            print(
                "=============================="
            )

            print("\n====== CAD INPUT DEBUG ======")

            print(
                "BIM STATE KEYS:",
                bim_state.keys()
            )

            print(
                "GEOMETRY OBJECT:",
                bim_state.get("geometry")
            )

            print(
                "GEOMETRY TYPE:",
                type(
                    bim_state.get("geometry")
                )
            )

            print("==============================")


            result["cad"] = (



                self.cad.export(

                    spatial,

                    geometry,

                    bim_state.get(
                        "structure",
                        {}
                    ),

                    output=dxf_file

                )

            )



        except Exception as e:


            result["cad"] = {

                "status":
                    "failed",

                "error":
                    str(e)

            }


            print(
                "\n====== AFTER CAD DEBUG ======"
            )

            print(
                result.keys()
            )

            print(
                result.get("ifc")
            )




        # ==================================
        # DWG
        # ==================================

        dwg_file = os.path.join(
            output_dir,
            "ArchitectOS_Project.dwg"
        )



        try:


            if self.dwg_converter:


                result["dwg"] = (

                    self.dwg_converter.convert(

                        dxf_file,

                        dwg_file

                    )

                )


            else:


                result["dwg"] = {


                    "status":
                        "pending",


                    "format":
                        "DWG",


                    "source":
                        dxf_file,


                    "message":
                        "DWG Converter unavailable"

                }



        except Exception as e:


            result["dwg"] = {

                "status":
                    "failed",

                "error":
                    str(e)

            }




        # ==================================
        # REVIT
        # ==================================

        try:


            revit_package = (

                self.revit.build(
                    bim_state
                )

            )


            result["revit"] = (
                revit_package
            )



            build_plan = (

                self.revit_build_plan.build({

                    "elements":
                        revit_package.get(
                            "elements",
                            []
                        ),


                    "families":
                        revit_package.get(
                            "families",
                            {}
                        ),


                    "levels":
                        revit_package.get(
                            "levels",
                            {}
                        ),


                    "type_materials":
                        revit_package.get(
                            "type_materials",
                            {}
                        )

                })

            )



            result["revit_build_plan"] = (
                build_plan
            )


            result["revit_adapter"] = (

                self.revit_adapter.convert(
                    build_plan
                )

            )



        except Exception as e:


            result["revit"] = {

                "status":
                    "failed",

                "error":
                    str(e)

            }

            print(
                "\n====== AFTER REVIT DEBUG ======"
            )

            print(
                result.keys()
            )

            print(
                "IFC STILL EXISTS:",
                "ifc" in result
            )




        # ==================================
        # PRODUCTION EXPORT
        # ==================================

        try:


            result["production"] = (

                self.production.export(
                    bim_state,
                    output_dir=output_dir,
                )

            )


        except Exception as e:


            result["production"] = {

                "status":
                    "failed",

                "error":
                    str(e)

            }



        # ==================================
        # EXPORT SUMMARY
        # ==================================

        result["summary"] = {

            "ifc":
                result.get(
                    "ifc",
                    {}
                ).get(
                    "status"
                ),


            "cad":
                (
                    result.get(
                        "cad",
                        {}
                    ).get(
                        "status"
                    )
                    or
                    result.get(
                        "cad",
                        {}
                    ).get(
                        "file",
                        {}
                    ).get(
                        "status"
                    )
                ),


            "dwg":
                result.get(
                    "dwg",
                    {}
                ).get(
                    "status"
                ),


            "revit":
                result.get(
                    "revit",
                    {}
                ).get(
                    "status"
                ),


            "production":
                result.get(
                    "production",
                    {}
                ).get(
                    "status"
                ),


            "validated":

                (
                    result.get(
                        "dwg",
                        {}
                    ).get(
                        "validated",
                        False
                    )
                    or
                    os.path.exists(
                        result.get(
                            "dwg",
                            {}
                        ).get(
                            "file",
                            ""
                        )
                    )
                )

        }


        result["status"] = (
            "completed"
        )


        print(
            "✅ EXPORT PIPELINE COMPLETE"
        )


        print("\n====== FINAL EXPORT DEBUG ======")

        print(
            "RESULT KEYS:",
            result.keys()
        )


        print(
            "IFC RESULT:"
        )

        print(
            result.get(
                "ifc"
            )
        )


        if isinstance(
            result.get("ifc"),
            dict
        ):

            print(
                "IFC RESULT KEYS:",
                result["ifc"].keys()
            )


            print(
                "IFC PATH:",
                result["ifc"].get(
                    "path"
                )
            )


            print(
                "IFC MODEL TOTAL:",
                sum(
                    len(v)
                    for v in result["ifc"].get(
                        "ifc_model",
                        {}
                    ).get(
                        "entities",
                        {}
                    ).values()
                    if isinstance(v, list)
                )
            )


            print("\n====== EXPORT FINAL STRUCTURE DEBUG ======")

            print(
                "RESULT IFC EXISTS:",
                "ifc" in result
            )

            print(
                "RESULT IFC STATUS:",
                result.get("ifc", {}).get("status")
            )


        return result
