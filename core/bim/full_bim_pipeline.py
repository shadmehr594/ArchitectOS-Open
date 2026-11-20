import copy
from collections import Counter
from core.site.site_engine import SiteEngine
from core.zoning.zoning_rule_engine import ZoningRuleEngine
from core.structure.structural_element_engine import StructuralElementEngine
from core.bim.revit_export_engine import RevitExportEngine
from core.bim.ifc_intelligence_engine import IFCIntelligenceEngine


from core.bim.geometry_cleanup_post_processor_v107 import (
    GeometryCleanupPostProcessor
)


from core.bim.structural_graph_intelligence_engine import (
    StructuralGraphIntelligenceEngine
)


from core.intelligence.structural_reasoning_v40 import (
    StructuralReasoningEngine
)


from core.intelligence.structural_decision_pipeline_v66 import (
    StructuralDecisionPipeline
)


from core.intelligence.structural_learning_engine_v67 import (
    StructuralLearningEngine
)


from core.bim.structural_geometry_normalizer_v108 import (
    StructuralGeometryNormalizer
)


from core.bim.bim_geometry_contract_normalizer import (
    BIMGeometryContractNormalizer
)


from core.export.export_orchestrator import (
    ExportOrchestrator
)


from core.bim.bim_export_validator import (
    BIMExportValidator
)


from core.geometry.geometry_adapter import (
    GeometryAdapter
)


from core.bim.semantic_bim_engine import (
    SemanticBIMEngine
)


from core.asset.asset_resolver import (
    AssetResolver
)



class FullBIMPipeline:


    VERSION = "52.7"



    def __init__(self):


        print(
            "🏗️ Full BIM Pipeline v52.7 ACTIVE"
        )



        self.ifc_engine = (
            IFCIntelligenceEngine()
        )



        self.geometry_cleanup = (
            GeometryCleanupPostProcessor()
        )



        self.structural_geometry_normalizer = (
            StructuralGeometryNormalizer()
        )



        self.structural_graph_engine = (
            StructuralGraphIntelligenceEngine()
        )



        self.structural_reasoning = (
            StructuralReasoningEngine()
        )



        self.structural_decision_pipeline = (
            StructuralDecisionPipeline()
        )



        self.structural_learning_engine = (
            StructuralLearningEngine()
        )



        self.geometry_contract_normalizer = (
            BIMGeometryContractNormalizer()
        )



        self.export_orchestrator = (
            ExportOrchestrator()
        )



        self.geometry_adapter = (
            GeometryAdapter()
        )



        self.semantic_engine = (
            SemanticBIMEngine()
        )



        self.asset_resolver = (
            AssetResolver()
        )
    # ==================================================
    # ENTRY
    # ==================================================

    def generate(
        self,
        project=None
    ):

        return self.run(
            project
        )



    # ==================================================
    # PIPELINE
    # ==================================================

    def run(
        self,
        project=None
    ):


        print(
            "▶ BIM PIPELINE START"
        )



        # ==========================
        # SITE
        # ==========================

        try:


            if (
                project
                and project.get("site")
            ):

                site = project["site"]

                print(
                    "🏞 USING IMPORTED SITE"
                )


            else:


                site = SiteEngine().load(
                    {
                        "type": "rect",
                        "width": 12,
                        "height": 10
                    }
                )


                print(
                    "🏞 USING DEFAULT SITE"
                )



        except Exception:


            site = {

                "type":
                    "rectangular_site",

                "width":
                    12,

                "height":
                    10,

                "status":
                    "generated"

            }



        # ==========================
        # ZONING
        # ==========================

        try:


            zoning = ZoningRuleEngine().validate(

                site=site,


                building_plan={

                    "footprint":
                        60,


                    "height":
                        3

                }

            )



        except Exception as error:


            zoning = {


                "valid":
                    True,


                "status":
                    "fallback",


                "error":
                    str(error)

            }
        # ==========================
        # SPATIAL
        # ==========================

        project_spatial = {}

        if isinstance(
            project,
            dict
        ):

            project_spatial = project.get(
                "spatial",
                {}
            )


        if isinstance(
            project_spatial,
            dict
        ) and project_spatial:

            spatial = project_spatial

            print(
                "\n====== RAW SPATIAL DEBUG ======"
            )

            print(
                spatial
            )

            print(
                "SPATIAL FLOOR KEYS:",
                list(
                    spatial.keys()
                )
            )

            print(
                "🏠 USING IMPORTED SPATIAL"
            )


        else:

            # ==================================================
            # ARCHITECTURE-FIRST STRUCTURAL FLOOR CARRIER
            #
            # FullBIMPipeline must not regenerate architectural
            # spatial topology.
            #
            # When a resolved floor_structural_systems contract
            # already exists, only create the minimum floor
            # carrier required by StructuralElementEngine.
            #
            # This does NOT create rooms, layout or structure.
            # ==================================================

            project_grid = {}

            if isinstance(
                project,
                dict
            ):

                project_grid = project.get(
                    "structural_grid",
                    {}
                )


            if not isinstance(
                project_grid,
                dict
            ):

                project_grid = {}


            floor_structural_systems = project_grid.get(
                "floor_structural_systems",
                {}
            )


            if (
                isinstance(
                    floor_structural_systems,
                    dict
                )
                and floor_structural_systems
            ):

                spatial = {

                    floor_name: {
                        "nodes": {}
                    }

                    for floor_name, floor_system
                    in floor_structural_systems.items()

                    if isinstance(
                        floor_system,
                        dict
                    )
                }


                print(
                    "\n====== ARCHITECTURE-FIRST SPATIAL CARRIER ======"
                )

                print(
                    "SOURCE:",
                    "floor_structural_systems"
                )

                print(
                    "FLOORS:",
                    list(
                        spatial.keys()
                    )
                )

                print(
                    "NOTE:",
                    "NO SPATIAL TOPOLOGY REGENERATION"
                )

                print(
                    "================================================"
                )


            else:

                spatial = {}

                print(
                    "\n====== EMPTY SPATIAL CONTRACT ======"
                )

                print(
                    "No imported spatial and no "
                    "floor_structural_systems available."
                )

                print(
                    "No legacy spatial regeneration performed."
                )

                print(
                    "===================================="
                )




        # ==========================
        # STRUCTURE GEOMETRY INPUT
        # ==========================

        if (
            project
            and project.get("geometry")
        ):


            geometry = project.get(
                "geometry"
            )

            print("\n====== SOURCE ROOMS BEFORE BIM GEOMETRY ======")

            for node, props in geometry.get("nodes", {}).items():
                print(
                    node,
                    props.get("x"),
                    props.get("y"),
                    props.get("w"),
                    props.get("h")
                )

            print("==============================================")


            print(
                "\n====== RAW GEOMETRY ROOMS LEVEL DEBUG ======"
            )

            for room in geometry.get(
                "rooms",
                []
            )[:20]:

                print(
                    room.get("id"),
                    room.get("level"),
                    room
                )


            print(
                "📐 USING DESIGN GEOMETRY INPUT"
            )


            print(
                "DEBUG GEOMETRY KEYS:",
                geometry.keys()
            )


            print(
                "DEBUG GEOMETRY WALL COUNT:",
                len(
                    geometry.get(
                        "walls",
                        []
                    )
                )
            )


            print(
                "\n====== RAW WALL SIZE DEBUG BEFORE NORMALIZER ======"
            )


            for wall in geometry.get(
                "walls",
                []
            )[:10]:

                print(
                    {
                        "id": wall.get("id"),
                        "start": wall.get("start"),
                        "end": wall.get("end"),
                        "x": wall.get("x"),
                        "y": wall.get("y"),
                        "width": wall.get("width"),
                        "length": wall.get("length"),
                        "level": wall.get("level")
                    }
                )


            print(
                "==================================================="
            )


            print(
                "DEBUG GEOMETRY FLOOR COUNT:",
                len(
                    geometry.get(
                        "floors",
                        []
                    )
                )
            )


            print(
                "DEBUG DOOR INPUT:",
                len(
                    geometry.get(
                        "doors",
                        []
                    )
                )
            )

            print(
                "DEBUG WINDOW INPUT:",
                len(
                    geometry.get(
                        "windows",
                        []
                    )
                )
            )



        else:


            geometry = {


                "rooms":[


                    {

                        "x":
                            0,

                        "y":
                            0,

                        "w":
                            5,

                        "h":
                            5,

                        "height":
                            3.2

                    },


                    {

                        "x":
                            5,

                        "y":
                            0,

                        "w":
                            5,

                        "h":
                            5,

                        "height":
                            3.2

                    }


                ],


                "floors":[]

            }



            print(
                "📐 USING BIM FALLBACK GEOMETRY"
            )
        # ==========================
        # BIM GEOMETRY CONTRACT NORMALIZATION
        # ==========================

        print(
            "\n====== RAW ROOMS BEFORE NORMALIZER SIZE DEBUG ======"
        )

        for room in geometry.get(
            "rooms",
            []
        )[:20]:

            print(
                {
                    "id": room.get("id"),
                    "level": room.get("level"),
                    "x": room.get("x"),
                    "y": room.get("y"),
                    "w": room.get("w"),
                    "h": room.get("h")
                }
            )

        print(
            "===================================================="
        )

        geometry = (
            self.geometry_contract_normalizer.normalize(
                geometry
            )
        )

        print("\n====== NORMALIZED GEOMETRY EXTENT DEBUG ======")

        xs = []
        ys = []

        for w in geometry.get("walls", []):

            for p in [
                w.get("start"),
                w.get("end")
            ]:

                if p:
                    xs.append(p[0])
                    ys.append(p[1])


        print(
            "WALL EXTENTS:",
            {
                "min_x": min(xs) if xs else None,
                "max_x": max(xs) if xs else None,
                "min_y": min(ys) if ys else None,
                "max_y": max(ys) if ys else None,
            }
        )


        print(
            "ROOM SAMPLE AFTER NORMALIZER:"
        )

        for r in geometry.get("rooms", [])[:5]:

            print(r)


        print("==============================================")


        print("\n====== WALLS ENTERING FULL BIM PIPELINE ======")

        for w in geometry.get("walls", [])[:50]:

            dx = w["end"][0] - w["start"][0]
            dy = w["end"][1] - w["start"][1]

            print(
                {
                    "start": w.get("start"),
                    "end": w.get("end"),
                    "dx": dx,
                    "dy": dy,
                    "level": w.get("level")
                }
            )

        print("==============================================")

        print("\n====== WALL AFTER NORMALIZER ======")

        for w in geometry.get("walls", [])[:30]:
            print(
                w.get("start"),
                "---->",
                w.get("end"),
                "level=",
                w.get("level")
            )

        print("===================================")

        print(
            "\n====== POST NORMALIZER ROOM GEOMETRY TRACE ======"
        )

        for room in geometry.get(
            "rooms",
            []
        )[:20]:

            print(
                {
                    "id": room.get("id"),
                    "level": room.get("level"),
                    "x": room.get("x"),
                    "y": room.get("y"),
                    "w": room.get("w"),
                    "h": room.get("h"),
                    "height": room.get("height")
                }
            )

        print(
            "================================================="
        )


        print(
            "\n====== WALL EXTENTS DEBUG ======"
        )

        min_x = 999999
        max_x = -999999
        min_y = 999999
        max_y = -999999


        for wall in geometry.get(
            "walls",
            []
        ):

            start = wall.get(
                "start"
            )

            end = wall.get(
                "end"
            )


            if start and end:

                min_x = min(
                    min_x,
                    start[0],
                    end[0]
                )

                max_x = max(
                    max_x,
                    start[0],
                    end[0]
                )

                min_y = min(
                    min_y,
                    start[1],
                    end[1]
                )

                max_y = max(
                    max_y,
                    start[1],
                    end[1]
                )


        print(
            {
                "min_x": min_x,
                "max_x": max_x,
                "min_y": min_y,
                "max_y": max_y
            }
        )

        print(
            "==============================="
        )


        print(
            "\n====== ROOM LEVEL AFTER NORMALIZER DEBUG ======"
        )

        for room in geometry.get("rooms", [])[:20]:

            print(
                {
                    "id": room.get("id"),
                    "level": room.get("level"),
                    "x": room.get("x"),
                    "y": room.get("y"),
                    "w": room.get("w"),
                    "h": room.get("h"),
                    "height": room.get("height")
                }
            )

        print(
            "=============================================="
        )


        print(
            "\n========== GEOMETRY AFTER NORMALIZER =========="
        )


        print(
            "rooms :",
            len(
                geometry.get(
                    "rooms",
                    []
                )
            )
        )


        print(
            "walls :",
            len(
                geometry.get(
                    "walls",
                    []
                )
            )
        )


        print(
            "doors :",
            len(
                geometry.get(
                    "doors",
                    []
                )
            )
        )


        print(
            "windows :",
            len(
                geometry.get(
                    "windows",
                    []
                )
            )
        )



        print(
            "\n====== WALL AFTER NORMALIZER SIZE DEBUG ======"
        )


        for wall in geometry.get(
            "walls",
            []
        )[:10]:

            print(
                {
                    "id": wall.get("id"),
                    "start": wall.get("start"),
                    "end": wall.get("end"),
                    "x": wall.get("x"),
                    "y": wall.get("y"),
                    "width": wall.get("width"),
                    "length": wall.get("length"),
                    "level": wall.get("level")
                }
            )


        print(
            "==============================================="
        )



        if geometry.get(
            "doors"
        ):

            print(
                "FIRST DOOR:",
                geometry["doors"][0]
            )



        if geometry.get(
            "windows"
        ):

            print(
                "FIRST WINDOW:",
                geometry["windows"][0]
            )





        # ==========================
        # CAD / DESIGN GEOMETRY DETECTION
        # ==========================

        if geometry.get(
            "entities"
        ):

            print(
                "📐 IMPORTED CAD GEOMETRY"
            )

            geometry = self._convert_cad_geometry(
                geometry
            )


        else:

            # ==============================================
            # ARCHITECTURE-FIRST GEOMETRY PRESENCE CHECK
            #
            # ArchitecturalGeometryEngine / DesignBIMBridge
            # may provide an authoritative physical geometry
            # contract without legacy "rooms".
            #
            # Presence of any real architectural geometry
            # must prevent BIM fallback replacement.
            # ==============================================

            architectural_geometry_available = any(
                bool(
                    geometry.get(
                        key
                    )
                )
                for key in (
                    "rooms",
                    "spaces",
                    "walls",
                    "physical_walls",
                    "doors",
                    "windows",
                    "openings",
                    "floors",
                    "slabs",
                    "floor_geometry",
                    "vertical_geometry",
                    "slab_openings"
                )
            )


            if architectural_geometry_available:

                print(
                    "📐 ARCHITECTURE-FIRST DESIGN GEOMETRY"
                )

                print(
                    {
                        "rooms":
                            len(
                                geometry.get(
                                    "rooms",
                                    []
                                )
                            ),

                        "spaces":
                            len(
                                geometry.get(
                                    "spaces",
                                    []
                                )
                            ),

                        "walls":
                            len(
                                geometry.get(
                                    "walls",
                                    []
                                )
                            ),

                        "doors":
                            len(
                                geometry.get(
                                    "doors",
                                    []
                                )
                            ),

                        "windows":
                            len(
                                geometry.get(
                                    "windows",
                                    []
                                )
                            ),

                        "floors":
                            len(
                                geometry.get(
                                    "floors",
                                    []
                                )
                            )
                    }
                )


            else:

                geometry = {

                    "rooms": [

                        {
                            "x":
                                0,

                            "y":
                                0,

                            "w":
                                5,

                            "h":
                                5,

                            "height":
                                3.2
                        },

                        {
                            "x":
                                5,

                            "y":
                                0,

                            "w":
                                5,

                            "h":
                                5,

                            "height":
                                3.2
                        }

                    ],

                    "floors":
                        []

                }


                print(
                    "📐 USING BIM FALLBACK GEOMETRY"
                )
        # ==========================
        # STRUCTURE
        # ==========================


        print(
            "DEBUG GEOMETRY BEFORE STRUCTURE WALLS:",
            len(
                geometry.get(
                    "walls",
                    []
                )
            )
        )


        print("\n====== ROOM LEVEL BEFORE STRUCTURE ======")

        for r in geometry.get("rooms", [])[:10]:
            print(
                r.get("id"),
                r.get("level"),
                r
            )

        print("\n====== STRUCTURAL SOURCE DEBUG ======")

        print(
            "rooms:",
            len(geometry.get("rooms", []))
        )

        print(
            "structural_grid:",
            geometry.get("structural_grid")
        )

        print(
            "spatial:",
            geometry.get("spatial", {}).keys()
        )

        print(
            "room levels:",
            Counter(
                r.get("level")
                for r in geometry.get("rooms", [])
            )
        )

        print("====================================")


        print("\n######## REAL STRUCTURE CALL DEBUG ########")

        print(
            "ROOM COUNT BEFORE STRUCTURE:",
            len(
                geometry.get(
                    "rooms",
                    []
                )
            )
        )

        print(
            "ROOM SAMPLE BEFORE STRUCTURE:",
            geometry.get(
                "rooms",
                []
            )[:3]
        )

        print(
            "GEOMETRY KEYS:",
            geometry.keys()
        )

        print("########################################")


        # ==========================
        # STRUCTURE GENERATION
        # ==========================

        print(
            "\n====== STRUCTURE FLAG DEBUG ======"
        )

        print(
            "GENERATE STRUCTURE:",
            project.get(
                "generate_structure",
                False
            )
        )

        print(
            "=================================="
        )


        print(
            "\n====== STRUCTURE ENGINE INPUT CHECK ======"
        )

        print(
            "ROOM COUNT:",
            len(
                geometry.get(
                    "rooms",
                    []
                )
            )
        )


        for r in geometry.get(
            "rooms",
            []
        )[:10]:

            print(
                "ROOM:",
                r
            )


        print(
            "STRUCTURAL GRID:",
            geometry.get(
                "structural_grid"
            )
        )


        print(
            "GEOMETRY KEYS:",
            geometry.keys()
        )


        print(
            "=========================================="
        )


        print(
            "\n====== PROJECT STRUCTURE FLAG DEBUG ======"
        )

        print(
            "PROJECT KEYS:",
            project.keys()
        )

        print(
            "GENERATE STRUCTURE VALUE:",
            project.get("generate_structure")
        )

        print(
            "PROJECT:",
            project
        )

        print(
            "=========================================="
        )


        structure = {}

        import inspect

        print(
            "STRUCTURE CALLER TRACE"
        )

        for frame in inspect.stack()[:5]:
            print(
                frame.filename,
                frame.function,
                frame.lineno
            )

        print("\n====== PROJECT LEVEL CONFIG CHECK ======")

        print(
            "PROJECT KEYS:",
            project.keys()
        )

        print(
            "PROJECT LEVEL CONFIG:",
            project.get(
                "level_config"
            )
        )

        print("========================================")


        print("\n====== SPATIAL LEVEL CONFIG TRACE ======")

        print(
            geometry.get(
                "spatial"
            )
        )

        print("========================================")


        if project.get(
            "generate_structure",
            True
        ):


            print("\n====== GEOMETRY BEFORE STRUCTURE ENGINE ======")

            print(
                "GEOMETRY KEYS:",
                geometry.keys()
            )

            print(
                "STRUCTURAL GRID:",
                geometry.get("structural_grid")
            )

            print(
                "GEOMETRY ALL KEYS:",
                geometry.keys()
            )

            print(
                "SPATIAL KEYS:",
                geometry.get("spatial", {}).keys()
            )

            print(
                "LEVELS:",
                geometry.get("levels")
            )

            print(
                "LEVEL OBJECT:",
                geometry.get("levels")
            )

            print("==============================================")


            print(
                "PROJECT STRUCTURAL GRID:",
                project.get("structural_grid")
            )

            print(
                "PROJECT SPATIAL:",
                project.get("spatial")
            )

            print("\n====== GEOMETRY ROOM FORMAT CHECK ======")

            for room in geometry.get("rooms", [])[:3]:

                print(room)

            print("========================================")


            print("\n====== GEOMETRY BEFORE STRUCTURE ENGINE ======")

            print(
                "KEYS:",
                geometry.keys()
            )

            print(
                "STRUCTURAL GRID:",
                geometry.get(
                    "structural_grid"
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

            print("==============================================")



            # ======================================
            # INJECT PROJECT SPATIAL INTO GEOMETRY
            # ======================================

            if not geometry.get(
                "spatial"
            ):

                geometry[
                    "spatial"
                ] = spatial
                   


            project_grid = project.get(
                "structural_grid",
                {}
            )


            if isinstance(
                project_grid,
                dict
            ) and project_grid:

                geometry[
                    "structural_grid"
                ] = dict(
                    project_grid
                )


            print("\n====== BEFORE INJECT CHECK ======")

            print(
                "GEOMETRY ID:",
                id(geometry)
            )

            print(
                "PROJECT ID:",
                id(project)
            )

            print(
                "BEFORE:",
                geometry.keys()
            )

        
            print(
                "AFTER:",
                geometry.keys()
            )

            print(
                "INJECTED SPATIAL:",
                geometry.get("spatial")
            )

            print(
                "INJECTED GRID:",
                geometry.get("structural_grid")
            )

            print(
                "================================"
            )

            print(
                "\n====== AUTHORITATIVE STRUCTURAL CONTRACT BEFORE ENGINE ======"
            )

            _runtime_grid = geometry.get(
                "structural_grid",
                {}
            )

            print(
                "GRID TYPE:",
                _runtime_grid.get(
                    "grid_type"
                )
            )

            print(
                "ANCHOR OWNERSHIP:",
                _runtime_grid.get(
                    "anchor_ownership"
                )
            )

            print(
                "MASTER X:",
                _runtime_grid.get(
                    "master_x_anchors"
                )
            )

            print(
                "MASTER Y:",
                _runtime_grid.get(
                    "master_y_anchors"
                )
            )

            print(
                "FLOOR STRUCTURAL SYSTEMS:",
                {
                    floor: {
                        "topology_mode":
                            data.get(
                                "topology_mode"
                            ),
                        "columns":
                            len(
                                data.get(
                                    "columns",
                                    []
                                )
                            ),
                        "beams":
                            len(
                                data.get(
                                    "beams",
                                    []
                                )
                            )
                    }

                    for floor, data in _runtime_grid.get(
                        "floor_structural_systems",
                        {}
                    ).items()

                    if isinstance(
                        data,
                        dict
                    )
                }
            )

            print(
                "==============================================================="
            )

            print(
                "BEFORE STRUCTURAL ELEMENT ENGINE"
            )

            print(
                "GRID:",
                geometry.get("structural_grid")
            )

            print(
                "SPATIAL:",
                geometry.get("spatial")
            )

            print("\n====== BEFORE STRUCTURAL ELEMENT ENGINE CALL ======")

            print(
                "GEOMETRY TYPE:",
                type(geometry)
            )

            print(
                "GEOMETRY KEYS:",
                geometry.keys()
            )

            print(
                "STRUCTURAL GRID:",
                geometry.get("structural_grid")
            )

            print(
                "SPATIAL TYPE:",
                type(geometry.get("spatial"))
            )

            print(
                "SPATIAL FLOORS:",
                geometry.get("spatial", {}).keys()
            )

            print("===================================================")


            print("\n====== LEVEL CONFIG BEFORE STRUCTURE ENGINE ======")

            print(
                geometry.get(
                    "level_config"
                )
            )

            print("==================================================")

            print("\n====== FLOOR DATA CHECK ======")

            print(
                geometry.get(
                    "floors"
                )
            )

            print("================================")


            # ======================================
            # BUILD LEVEL CONFIG
            # ======================================

            if not geometry.get(
                "level_config"
            ):

                # --------------------------------------
                # LEVEL CONFIG SOURCE PRIORITY
                #
                # 1. Project-provided real level config
                # 2. Geometry levels
                # 3. StructuralGridEngine v2 levels
                # --------------------------------------

                project_level_config = project.get(
                    "level_config"
                )

                if project_level_config:

                    geometry[
                        "level_config"
                    ] = copy.deepcopy(
                        project_level_config
                    )

                    print(
                        "\n====== LEVEL CONFIG SOURCE ======"
                    )

                    print(
                        "SOURCE: PROJECT LEVEL CONFIG"
                    )

                    print(
                        geometry[
                            "level_config"
                        ]
                    )

                    print(
                        "================================="
                    )

                else:

                    levels = geometry.get(
                        "levels",
                        []
                    )

                    level_source = (
                        "geometry"
                    )

                    if not levels:

                        structural_grid = geometry.get(
                            "structural_grid",
                            {}
                        )

                        levels = structural_grid.get(
                            "levels",
                            []
                        )

                        level_source = (
                            "structural_grid"
                        )

                    level_config = {}

                    running_base_z = 0.0

                    for level in levels:

                        if not isinstance(
                            level,
                            dict
                        ):
                            continue

                        name = level.get(
                            "name"
                        )

                        if not name:
                            continue

                        # Prefer real architectural
                        # vertical data when available.
                        level_height = level.get(
                            "height"
                        )

                        if level_height is None:

                            level_height = level.get(
                                "column_height"
                            )

                        if level_height is None:

                            # Legacy fallback only.
                            # This is NOT structural
                            # design intelligence.
                            level_height = 3.2

                        explicit_base_z = level.get(
                            "base_z"
                        )

                        if explicit_base_z is None:

                            explicit_base_z = level.get(
                                "elevation"
                            )

                        if explicit_base_z is not None:

                            base_z = explicit_base_z

                        else:

                            base_z = running_base_z

                        beam_z = level.get(
                            "beam_z"
                        )

                        if beam_z is None:

                            beam_z = (
                                base_z
                                +
                                level_height
                            )

                        level_config[
                            name
                        ] = {
                            "base_z":
                                base_z,

                            "column_height":
                                level_height,

                            "beam_z":
                                beam_z
                        }

                        running_base_z = (
                            base_z
                            +
                            level_height
                        )

                    geometry[
                        "level_config"
                    ] = level_config

                    print(
                        "\n====== LEVEL CONFIG SOURCE ======"
                    )

                    print(
                        "SOURCE:",
                        level_source
                    )

                    print(
                        "LEVEL COUNT:",
                        len(
                            levels
                        )
                    )

                    print(
                        "LEVEL CONFIG:",
                        level_config
                    )

                    print(
                        "================================="
                    )



            print(
                "\n====== GENERATED LEVEL CONFIG ======"
            )

            print(
                geometry.get(
                    "level_config"
                )
            )

            print(
                "===================================="
            )

            runtime_structural_grid = geometry.get(
                "structural_grid",
                {}
            )

            print(
                "\n====== RUNTIME GRID BEFORE STRUCTURAL ENGINE ======"
            )

            print(
                "GRID TYPE:",
                runtime_structural_grid.get(
                    "grid_type"
                )
            )

            print(
                "COLUMN IDS:",
                [
                    column.get(
                        "id"
                    )
                    for column in runtime_structural_grid.get(
                        "columns",
                        []
                    )[:10]
                ]
            )

            print(
                "COLUMN SOURCE IDS:",
                [
                    column.get(
                        "source_id"
                    )
                    for column in runtime_structural_grid.get(
                        "columns",
                        []
                    )[:10]
                ]
            )

            print(
                "BEAM IDS:",
                [
                    beam.get(
                        "id"
                    )
                    for beam in runtime_structural_grid.get(
                        "beams",
                        []
                    )[:10]
                ]
            )

            print(
                "===================================================="
            )

            print(
                "\n====== FLOOR STRUCTURAL SYSTEM CONTRACT BEFORE ENGINE ======"
            )

            runtime_structural_grid = geometry.get(
                "structural_grid",
                {}
            )

            floor_structural_systems = runtime_structural_grid.get(
                "floor_structural_systems",
                {}
            )

            print(
                "GRID TYPE:",
                runtime_structural_grid.get(
                    "grid_type"
                )
            )

            print(
                "ANCHOR OWNERSHIP:",
                runtime_structural_grid.get(
                    "anchor_ownership"
                )
            )

            print(
                "MASTER X:",
                runtime_structural_grid.get(
                    "master_x_anchors"
                )
            )

            print(
                "MASTER Y:",
                runtime_structural_grid.get(
                    "master_y_anchors"
                )
            )

            print(
                "FLOOR SYSTEM KEYS:",
                list(
                    floor_structural_systems.keys()
                )
                if isinstance(
                    floor_structural_systems,
                    dict
                )
                else None
            )

            if isinstance(
                floor_structural_systems,
                dict
            ):

                for floor_name, floor_system in (
                    floor_structural_systems.items()
                ):

                    if not isinstance(
                        floor_system,
                        dict
                    ):

                        continue

                    print(
                        "FLOOR SYSTEM:",
                        {
                            "floor":
                                floor_name,

                            "mode":
                                floor_system.get(
                                    "mode"
                                ),

                            "topology_mode":
                                floor_system.get(
                                    "topology_mode"
                                ),

                            "columns":
                                len(
                                    floor_system.get(
                                        "columns",
                                        []
                                    )
                                ),

                            "beams":
                                len(
                                    floor_system.get(
                                        "beams",
                                        []
                                    )
                                ),

                            "removed_columns":
                                len(
                                    floor_system.get(
                                        "removed_columns",
                                        []
                                    )
                                ),

                            "removed_beams":
                                len(
                                    floor_system.get(
                                        "removed_beams",
                                        []
                                    )
                                )
                        }
                    )

            print(
                "==========================================================="
            )


            structure = StructuralElementEngine(
                geometry.get(
                    "structural_grid",
                    {}
                ),
                geometry.get(
                    "level_config",
                    {}
                )
            ).build(
                geometry.get(
                    "spatial",
                    {}
                ).get(
                    "floors",
                    geometry.get("spatial", {})
                )
            )

            print(
                "\n====== FLOOR STRUCTURAL SYSTEM RESULT AFTER ENGINE ======"
            )

            for floor_name, floor_structure in structure.items():

                if not isinstance(
                    floor_structure,
                    dict
                ):

                    continue

                print(
                    "FLOOR RESULT:",
                    {
                        "floor":
                            floor_name,

                        "columns":
                            len(
                                floor_structure.get(
                                    "columns",
                                    []
                                )
                            ),

                        "beams":
                            len(
                                floor_structure.get(
                                    "beams",
                                    []
                                )
                            ),

                        "walls":
                            len(
                                floor_structure.get(
                                    "walls",
                                    []
                                )
                            ),

                        "column_source_ids":
                            [
                                column.get(
                                    "source_id"
                                )
                                for column in floor_structure.get(
                                    "columns",
                                    []
                                )
                            ],

                        "beam_source_ids":
                            [
                                beam.get(
                                    "source_id"
                                )
                                for beam in floor_structure.get(
                                    "beams",
                                    []
                                )
                            ],

                        "column_z":
                            sorted(
                                list(
                                    set(
                                        column.get(
                                            "z"
                                        )
                                        for column in floor_structure.get(
                                            "columns",
                                            []
                                        )
                                    )
                                )
                            ),

                        "beam_z":
                            sorted(
                                list(
                                    set(
                                        beam.get(
                                            "z"
                                        )
                                        for beam in floor_structure.get(
                                            "beams",
                                            []
                                        )
                                    )
                                )
                            )
                    }
                )

            print(
                "========================================================"
            )


            print("\n====== STRUCTURE SOURCE FINAL TRACE ======")

            for level, data in structure.items():

                print("\nLEVEL:", level)

                for c in data.get("columns", [])[:5]:
                    print(
                        "COLUMN:",
                        {
                            "id": c.get("id"),
                            "level": c.get("level"),
                            "z": c.get("z"),
                            "x": c.get("x"),
                            "y": c.get("y")
                        }
                    )


                for b in data.get("beams", [])[:5]:
                    print(
                        "BEAM:",
                        {
                            "id": b.get("id"),
                            "level": b.get("level"),
                            "z": b.get("z"),
                            "start": b.get("start"),
                            "end": b.get("end")
                        }
                    )

            print("==========================================")


            for b in structure.get("beams", [])[:10]:
                print(
                    "BEAM:",
                    {
                        "id": b.get("id"),
                        "level": b.get("level"),
                        "z": b.get("z"),
                        "start": b.get("start"),
                        "end": b.get("end")
                    }
                )

            print("==========================================")


            print("\n====== STRUCTURE ENGINE OUTPUT DEBUG ======")

            for level, data in structure.items():

                print(
                    level,
                    "BEAMS:",
                    len(data.get("beams", []))
                )

            print("==========================================")

            print(
                "AFTER STRUCTURAL ELEMENT ENGINE"
            )

            flat_structure = {
                "columns": [],
                "beams": [],
                "walls": []
            }

            for level, data in structure.items():

                print(
                    "FLATTEN LEVEL:",
                    level,
                    type(data),
                    data.keys() if isinstance(data, dict) else None
                )

                flat_structure["columns"].extend(
                    data.get("columns", [])
                )


                print("\n====== FLAT STRUCTURE COLUMN MERGE DEBUG ======")

                print(
                    "LEVEL:",
                    level
                )

                print(
                    "COLUMNS ADDED:",
                    len(data.get("columns", []))
                )

                print(
                    "TOTAL COLUMNS NOW:",
                    len(flat_structure["columns"])
                )


                print(
                    "==============================================="
                )

                flat_structure["beams"].extend(
                    data.get("beams", [])
                )


                print("\n====== FLAT STRUCTURE BEAM MERGE DEBUG ======")

                print(
                    "LEVEL:",
                    level
                )

                print(
                    "BEAMS ADDED:",
                    len(data.get("beams", []))
                )

                print(
                    "TOTAL BEAMS NOW:",
                    len(flat_structure["beams"])
                )

                print(
                    "============================================="
                )

                flat_structure["walls"].extend(
                    data.get("walls", [])
                )

            print("\n====== STRUCTURE WALL SOURCE AXIS CHECK ======")

            for w in geometry.get("walls", [])[:50]:
                print(
                    {
                        "start": w.get("start"),
                        "end": w.get("end"),
                        "dx": w.get("end")[0] - w.get("start")[0],
                        "dy": w.get("end")[1] - w.get("start")[1],
                        "level": w.get("level")
                    }
                )

            print("==============================================")


            structure = flat_structure

            print("\n====== STRUCTURE OUTPUT WALL AXIS CHECK ======")

            for w in structure.get("walls", [])[:50]:
                print(
                    {
                        "id": w.get("id"),
                        "start": w.get("start"),
                        "end": w.get("end"),
                        "dx": w.get("end")[0] - w.get("start")[0],
                        "dy": w.get("end")[1] - w.get("start")[1],
                        "level": w.get("level")
                    }
                )

            print("==============================================")


            print(
                "STRUCTURE RESULT TYPE:",
                structure.keys()
            )


        print("\n====== STRUCTURE LEVEL DEBUG ======")

        for c in structure.get("columns", [])[:20]:
            print(
                "COLUMN",
                c.get("level"),
                c
            )


        for b in structure.get("beams", [])[:20]:


            print(
                "FULL BIM PIPELINE STRUCTURE BEAM INPUT:",
                {
                    "id": b.get("id"),
                    "start": b.get("start"),
                    "end": b.get("end"),
                    "level": b.get("level"),
                    "z": b.get("z"),
                    "elevation": b.get("elevation")
                }
            )


            print(
                "BEAM",
                b.get("level"),
                b
            )

        print("===================================")

        print("\n====== STRUCTURE INPUT DEBUG ======")

        print(
            "ROOM SAMPLE:",
            geometry.get("rooms", [])[:1]
        )

        print(
            "WALL SAMPLE:",
            geometry.get("walls", [])[:1]
        )

        print(
            "STRUCTURE RESULT:",
            {
                "columns": len(structure.get("columns", [])),
                "beams": len(structure.get("beams", [])),
                "walls": len(structure.get("walls", [])),
                "slabs": len(structure.get("slabs", []))
            }
        )


        print("\n====== FINAL GEOMETRY BEFORE BIM ADAPTER ======")

        print(
            "walls:",
            len(geometry.get("walls", []))
        )

        print("\n====== WALL SAMPLE XY DEBUG ======")

        for w in geometry.get("walls", [])[:20]:
            print(
                w.get("start"),
                "---->",
                w.get("end")
            )

        print("=================================")

        print(
            "doors:",
            len(geometry.get("doors", []))
        )

        print(
            "windows:",
            len(geometry.get("windows", []))
        )

        print(
            "floors:",
            len(geometry.get("floors", []))
        )


        print(
            "STRUCTURE COUNTS:"
        )

        for key in [
            "columns",
            "beams",
            "slabs",
            "walls"
        ]:

            print(
                key,
                len(
                    structure.get(key, [])
                )
            )


        # ==========================
        # BIM ELEMENTS
        # ==========================


        print("\n====== RAW STRUCTURE BEAMS BEFORE ADAPTER ======")

        for beam in structure.get("beams", [])[:10]:


            print(
                "BEAM FULL RAW:",
                beam
            )


            print(
                "RAW BEAM FULL OBJECT:",
                beam
            )

            print(
                {
                    "id": beam.get("id"),
                    "start": beam.get("start"),
                    "end": beam.get("end"),
                    "level": beam.get("level"),
                    "z": beam.get("z")
                }
            )


        print("\n====== GEOMETRY ADAPTER INPUT DEBUG ======")

        print(
            "STRUCTURE TYPE:",
            type(structure)
        )

        print(
            "STRUCTURE KEYS:",
            structure.keys()
            if isinstance(structure, dict)
            else None
        )


        print(
            "GEOMETRY TYPE:",
            type(geometry)
        )

        print(
            "GEOMETRY KEYS:",
            geometry.keys()
            if isinstance(geometry, dict)
            else None
        )


        print(
            "STRUCTURE COLUMNS:",
            len(
                structure.get(
                    "columns",
                    []
                )
            )
            if isinstance(structure, dict)
            else "N/A"
        )


        print(
            "STRUCTURE BEAMS:",
            len(
                structure.get(
                    "beams",
                    []
                )
            )
            if isinstance(structure, dict)
            else "N/A"
        )


        print(
            "GEOMETRY ROOMS:",
            len(
                geometry.get(
                    "rooms",
                    []
                )
            )
            if isinstance(geometry, dict)
            else "N/A"
        )


        print(
            "==========================================")


        print("\n====== STRUCTURE RAW BEFORE ADAPTER ======")

        print(
            "COLUMNS:",
            len(structure.get("columns",[]))
        )

        print(
            "BEAMS:",
            len(structure.get("beams",[]))
        )

        for b in structure.get("beams",[])[:10]:

            print(
                {
                    "level": b.get("level"),
                    "start": b.get("start"),
                    "end": b.get("end"),
                    "z": b.get("z")
                }
            )

        print("==========================================")

        print("\n====== STRUCTURE INPUT TO ADAPTER Z TRACE ======")

        for b in structure.get("beams", []):

            if b.get("level") in [
                "F2",
                "F3"
            ]:

                print(
                    {
                        "id": b.get("id"),
                        "level": b.get("level"),
                        "z": b.get("z")
                    }
                )

        print("==============================================")


        print("\n====== BEFORE GEOMETRY ADAPTER FULL CHECK ======")

        print(
            "STRUCTURE WALLS:",
            len(structure.get("walls", []))
        )

        print(
            "STRUCTURE SLABS:",
            len(structure.get("slabs", []))
        )

        for w in structure.get("walls", [])[:20]:
            print(
                "STRUCT WALL:",
                w
            )


        for s in structure.get("slabs", [])[:10]:
            print(
                "STRUCT SLAB:",
                s
            )

        print("==============================================")


        print("\n====== STRUCTURE BEFORE GEOMETRY ADAPTER FINAL ======")

        print(
            "COLUMN COUNT:",
            len(structure.get("columns", []))
        )

        for c in structure.get("columns", [])[:10]:
            print(
                "COLUMN BEFORE ADAPTER:",
                {
                    "id": c.get("id"),
                    "level": c.get("level"),
                    "z": c.get("z"),
                    "x": c.get("x"),
                    "y": c.get("y")
                }
            )


        print(
            "BEAM COUNT:",
            len(structure.get("beams", []))
        )

        for b in structure.get("beams", [])[:10]:
            print(
                "BEAM BEFORE ADAPTER:",
                {
                    "id": b.get("id"),
                    "level": b.get("level"),
                    "z": b.get("z"),
                    "start": b.get("start"),
                    "end": b.get("end")
                }
            )


        print("====================================================")

        print(
            "\n====== SOURCE ID BEFORE GEOMETRY ADAPTER ======"
        )

        for c in structure.get(
            "columns",
            []
        )[:5]:

            print(
                {
                    "id":
                        c.get(
                            "id"
                        ),

                    "source_id":
                        c.get(
                            "source_id"
                        ),

                    "level":
                        c.get(
                            "level"
                        )
                }
            )

        print(
            "=============================================="
        )


        bim_elements = self.geometry_adapter.build(
            structure,
            geometry
        )

        print(
            "\n====== SOURCE ID AFTER GEOMETRY ADAPTER ======"
        )

        for c in structure.get(
            "columns",
            []
        )[:5]:

            print(
                {
                    "id":
                        c.get(
                            "id"
                        ),

                    "source_id":
                        c.get(
                            "source_id"
                        ),

                    "level":
                        c.get(
                            "level"
                        )
                }
            )

        print(
            "============================================="
        )

        print("\n====== BIM ELEMENT WALL TRACE ======")

        for e in bim_elements:
            if e.get("ifc_type") == "IfcWall":
                print(
                    e.get("data", {}).get("start"),
                    "---->",
                    e.get("data", {}).get("end"),
                    "level=",
                    e.get("data", {}).get("level")
                )

        print("====================================")

        print("\n====== AFTER GEOMETRY ADAPTER XY CHECK ======")

        columns = [
            e for e in bim_elements
            if e.get("ifc_type") == "IfcColumn"
        ]

        print(
            "BIM COLUMN COUNT:",
            len(columns)
        )

        for c in columns[:20]:

            print(
                {
                    "id": c.get("id"),
                    "source_id": c.get("data",{}).get("id"),
                    "level": c.get("data",{}).get("level"),
                    "x": c.get("x"),
                    "y": c.get("y"),
                    "z": c.get("z")
                }
            )


        print("==============================================")

        print("\n====== BIM AFTER GEOMETRY ADAPTER Z CHECK ======")

        for e in bim_elements:

            if e.get("ifc_type") in [
                "IfcColumn",
                "IfcBeam"
            ]:

                print(
                    {
                        "id": e.get("id"),
                        "ifc_type": e.get("ifc_type"),
                        "level": e.get("level"),
                        "data_level": e.get("data", {}).get("level"),
                        "z": e.get("z"),
                        "data_z": e.get("data", {}).get("z")
                    }
                )


        print("\n====== FLAT WALL AXIS TRACE ======")

        for w in structure.get("walls", []):

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
                        "dy": dy,
                        "level": w.get("level")
                    }
                )

        print(
            "TOTAL WALLS:",
            len(structure.get("walls", []))
        )

        print("================================")


        print(
            [
                e.get("id")
                for e in bim_elements
                if e.get("ifc_type") == "IfcBeam"
            ]
        )


        print(
            "\n========== ADAPTER INSTANCE CHECK =========="
        )

        print(
            self.geometry_adapter.__class__,
        )

        print(
            self.geometry_adapter.__class__.__module__
        )

        print(
            "============================================"
        )

        print("\n====== AFTER GEOMETRY ADAPTER ======")

        beam_ids = [
            e.get("id")
            for e in bim_elements
            if e.get("ifc_type") == "IfcBeam"
        ]

        print(
            "BEAM COUNT:",
            len(beam_ids)
        )

        print(
            "UNIQUE:",
            len(set(beam_ids))
        )

        print(
            [
                x for x, c in Counter(beam_ids).items()
                if c > 1
            ]
        )

        print(
            "===================================="
        )


        print("\n====== ADAPTER STRUCTURE LEVEL TRACE ======")

        for e in bim_elements:

            if e.get("ifc_type") in [
                "IfcColumn",
                "IfcBeam"
            ]:

                data = e.get("data",{})

                print({
                    "id": e.get("id"),
                    "ifc": e.get("ifc_type"),
                    "level": e.get("level"),
                    "data_level": data.get("level"),
                    "z": e.get("z"),
                    "data_z": data.get("z"),
                    "source_id": data.get("source_id")
                })

        print("==========================================")



        print("\n====== AFTER GEOMETRY ADAPTER COUNT ======")

        print(
            "TOTAL:",
            len(bim_elements)
        )

        print(
            "IFC TYPES:",
            Counter(
                e.get("ifc_type")
                for e in bim_elements
            )
        )

        print("==========================================")



        
        print(
            "BIM COLUMNS:",
            len([
                e for e in bim_elements
                if e.get("ifc_type") == "IfcColumn"
            ])
        )

        print(
            "BIM BEAMS:",
            len([
                e for e in bim_elements
                if e.get("ifc_type") == "IfcBeam"
            ])
        )

        print(
            "BIM WALLS:",
            len([
                e for e in bim_elements
                if e.get("ifc_type") == "IfcWall"
            ])
        )

        print("============================================")



        # ==========================================
        # ARCHITECTURE-FIRST IFC BUILDING CONFIG
        #
        # Architectural level_config is authoritative.
        # IFC must not recreate storeys from hardcoded
        # floor counts or fixed floor heights.
        # ==========================================

        architectural_level_config = {}

        if (
            project
            and isinstance(
                project.get("level_config"),
                dict
            )
        ):

            architectural_level_config = copy.deepcopy(
                project.get(
                    "level_config",
                    {}
                )
            )


        building_levels = []


        for level_name, level_data in (
            architectural_level_config.items()
        ):

            if not isinstance(
                level_data,
                dict
            ):

                continue


            base_z = level_data.get(
                "bottom",
                level_data.get("base_z")
            )

            top_z = level_data.get("top")

            floor_height = level_data.get(
                "height",
                level_data.get(
                    "floor_height",
                    level_data.get("column_height")
                )
            )


            if not isinstance(
                base_z,
                (int, float)
            ):

                continue


            if not isinstance(
                floor_height,
                (int, float)
            ):

                continue


            building_levels.append(
                {
                    "name":
                        level_name,

                    "elevation":
                        float(
                            base_z
                        ),

                    "height":
                        float(
                            floor_height
                        ),

                    "bottom":
                        float(base_z),

                    "top":
                        float(top_z)
                        if isinstance(top_z, (int, float))
                        else None,

                    "architectural_authority":
                        bool(
                            level_data.get(
                                "architectural_authority",
                                False
                            )
                        ),

                    "height_status":
                        level_data.get(
                            "height_status"
                        ),

                    "height_source":
                        level_data.get(
                            "height_source"
                        )
                }
            )


        building_config = {

            "floors":
                len(
                    building_levels
                ),

            "levels":
                building_levels,

            "level_config":
                architectural_level_config,

            "architectural_authority":
                bool(
                    building_levels
                )

        }


        print(
            "\n====== ARCHITECTURE-FIRST IFC BUILDING CONFIG ======"
        )

        print(
            building_config
        )

        print(
            "===================================================="
        )


        print("\n====== STRUCTURAL SOURCE DEBUG ======")

        for e in bim_elements:

            if e.get("ifc_type") in [
                "IfcColumn",
                "IfcBeam"
            ]:

                data = e.get("data",{})

                print(
                    "STRUCTURAL SOURCE DEBUG:",
                    {
                        "id": e.get("id"),
                        "type": e.get("ifc_type"),
                        "level": data.get("level"),
                        "z": data.get("z"),
                        "height": data.get("height")
                    }
                )



        print(
            "\n====== STRUCTURAL SOURCE DEBUG AFTER GEOMETRY ADAPTER ======"
        )

        for e in bim_elements:

            if e.get("ifc_type") in [
                "IfcColumn",
                "IfcBeam"
            ]:

                data = e.get(
                    "data",
                    {}
                )

                print(
                    "STRUCTURAL SOURCE DEBUG:",
                    {
                        "id": e.get("id"),
                        "type": e.get("ifc_type"),
                        "level": data.get("level"),
                        "z": data.get("z"),
                        "height": data.get("height"),
                        "x": data.get("x"),
                        "y": data.get("y"),
                        "start": data.get("start"),
                        "end": data.get("end")
                    }
                )

        print(
            "========================================================"
        )

        print("\n====== GEOMETRY ADAPTER OUTPUT DEBUG ======")

        print("\n====== BIM ELEMENT LEVEL DEBUG AFTER ADAPTER ======")

        for e in bim_elements[:30]:

            if e.get("ifc_type") in [
                "IfcColumn",
                "IfcBeam"
            ]:

                print(
                    e.get("ifc_type"),
                    e.get("level"),
                    e.get("data", {}).get("level"),
                    e
                )

        print(
            "TOTAL BIM ELEMENTS:",
            len(bim_elements)
        )

        print("\n====== FINAL BIM STRUCTURAL TRACE ======")

        for e in bim_elements:

            if e.get("ifc_type") in [
                "IfcColumn",
                "IfcBeam"
            ]:

                print(
                    e.get("id"),
                    e.get("ifc_type"),
                    e.get("level"),
                    e.get("z"),
                    e.get("data", {}).get("z"),
                    e.get("start"),
                    e.get("end")
                )

        print(
            "TOTAL STRUCTURAL BIM:",
            len([
                e for e in bim_elements
                if e.get("ifc_type") in [
                    "IfcColumn",
                    "IfcBeam"
                ]
            ])
        )

        print("========================================")


        print(
            "IFC TYPES:",
            Counter(
                e.get("ifc_type")
                for e in bim_elements
                if isinstance(e, dict)
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
                    "FOUND NON STRUCTURAL:",
                    e
                )


        print(
            Counter(
                e.get("ifc_type")
                for e in bim_elements
                if isinstance(
                    e,
                    dict
                )
            )
        )


        print("\n====== DESIGN BIM BRIDGE OUTPUT ======")

        for e in bim_elements:

            print(
                e.get("ifc_type")
            )



        # ==========================
        # FINAL BIM BEFORE IFC DEBUG
        # ==========================

        print(
            "\n========== FINAL BIM BEFORE IFC =========="
        )


        print(
            "TOTAL BIM ELEMENTS:",
            len(bim_elements)
        )


        print(
            "IFC TYPES:",
            Counter(
                e.get("ifc_type")
                for e in bim_elements
                if isinstance(e, dict)
            )
        )



        print(
            "\n====== FINAL STRUCTURAL BEFORE IFC ======"
        )


        for e in bim_elements:

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
                        "data_level": data.get("level"),
                        "z": e.get("z"),
                        "data_z": data.get("z"),
                        "x": e.get("x"),
                        "y": e.get("y"),
                        "start": data.get("start"),
                        "end": data.get("end")
                    }
                )


        print(
            "\n====== FINAL STRUCTURAL COUNT ======"
        )


        print(
            "COLUMNS:",
            len(
                [
                    e for e in bim_elements
                    if e.get("ifc_type") == "IfcColumn"
                ]
            )
        )


        print(
            "BEAMS:",
            len(
                [
                    e for e in bim_elements
                    if e.get("ifc_type") == "IfcBeam"
                ]
            )
        )


        print(
            "======================================"
        )

        # ==========================
        # SEMANTIC BIM
        #
        # Architecture-first source:
        # project.geometry.spaces is the authoritative
        # architectural space contract.
        #
        # BIM elements come from GeometryAdapter.
        # ==========================

        semantic_source_geometry = {}

        if (
            project
            and isinstance(
                project.get("geometry"),
                dict
            )
        ):

            semantic_source_geometry = project.get(
                "geometry",
                {}
            )

        elif isinstance(
            geometry,
            dict
        ):

            semantic_source_geometry = geometry


        semantic_rooms = semantic_source_geometry.get(
            "spaces",
            []
        )


        if not isinstance(
            semantic_rooms,
            list
        ) or not semantic_rooms:

            semantic_rooms = semantic_source_geometry.get(
                "rooms",
                []
            )


        if not isinstance(
            semantic_rooms,
            list
        ):

            semantic_rooms = []


        # ------------------------------------------
        # STABLE ARCHITECTURAL ROOM IDENTITY
        #
        # Spaces such as corridor may exist on more
        # than one floor, therefore name alone is
        # not a sufficient semantic identifier.
        # ------------------------------------------

        semantic_room_contract = []


        for room in semantic_rooms:

            if not isinstance(
                room,
                dict
            ):

                continue


            semantic_room = copy.deepcopy(
                room
            )


            floor_name = semantic_room.get(
                "floor",
                semantic_room.get(
                    "level"
                )
            )


            room_name = semantic_room.get(
                "name",
                semantic_room.get(
                    "id"
                )
            )


            if not semantic_room.get(
                "id"
            ):

                if (
                    floor_name
                    and
                    room_name
                ):

                    semantic_room[
                        "id"
                    ] = (
                        f"{floor_name}-{room_name}"
                    )

                elif room_name:

                    semantic_room[
                        "id"
                    ] = str(
                        room_name
                    )


            if (
                semantic_room.get(
                    "level"
                )
                is None
            ):

                semantic_room[
                    "level"
                ] = floor_name


            semantic_room_contract.append(
                semantic_room
            )


        print(
            "\n====== SEMANTIC BIM INPUT CONTRACT ======"
        )

        print(
            "ROOM SOURCE:",
            (
                "architectural_spaces"
                if semantic_source_geometry.get(
                    "spaces"
                )
                else "rooms"
            )
        )

        print(
            "SEMANTIC ROOM COUNT:",
            len(
                semantic_room_contract
            )
        )

        print(
            "SEMANTIC ELEMENT COUNT:",
            len(
                bim_elements
            )
        )

        print(
            "ROOM LEVELS:",
            Counter(
                room.get(
                    "level"
                )
                for room in semantic_room_contract
            )
        )

        print(
            "ELEMENT LEVELS:",
            Counter(
                element.get(
                    "level"
                )
                for element in bim_elements
                if isinstance(
                    element,
                    dict
                )
            )
        )

        print(
            "========================================="
        )


        semantic_bim = self.semantic_engine.build(
            rooms=semantic_room_contract,
            objects=[],
            elements=bim_elements
        )


        print(
            "\n====== SEMANTIC BIM OUTPUT ======"
        )

        print(
            "ROOMS:",
            len(
                semantic_bim.get(
                    "rooms",
                    []
                )
            )
        )

        print(
            "OBJECTS:",
            len(
                semantic_bim.get(
                    "objects",
                    []
                )
            )
        )

        print(
            "ELEMENTS:",
            len(
                semantic_bim.get(
                    "elements",
                    []
                )
            )
        )

        print(
            "RELATIONS:",
            len(
                semantic_bim.get(
                    "relations",
                    []
                )
            )
        )

        print(
            "ELEMENT SEMANTIC TYPES:",
            Counter(
                element.get(
                    "semantic_type"
                )
                for element in semantic_bim.get(
                    "elements",
                    []
                )
            )
        )

        print(
            "================================="
        )


        ifc_model = self.ifc_engine.generate(
            {
                "bim_elements":
                    bim_elements,

                "building_config":
                    building_config
            }
        )


        print("\n====== BEFORE IFC ENGINE INPUT Z CHECK ======")

        for e in bim_elements:

            if e.get("ifc_type") in [
                "IfcColumn",
                "IfcBeam"
            ]:

                print(
                    {
                        "id": e.get("id"),
                        "type": e.get("ifc_type"),
                        "level": e.get("level"),
                        "z": e.get("z"),
                        "data_z": e.get(
                            "data",
                            {}
                        ).get("z")
                    }
                )

        print("============================================")


        print(
            "\n====== IFC MODEL OUTPUT DEBUG ======"
        )

        print(
            "IFC MODEL TYPE:",
            type(ifc_model)
        )

        print(
            "IFC KEYS:",
            ifc_model.keys()
            if isinstance(ifc_model, dict)
            else None
        )


        if isinstance(ifc_model, dict):

            entities = ifc_model.get(
                "entities",
                {}
            )

            print(
                "IFC ENTITY TYPES:",
                entities.keys()
            )

            for key, value in entities.items():

                if isinstance(value, list):

                    print(
                        key,
                        len(value)
                    )


        print("\n====== IFC FLATTEN DEBUG ======")

        ifc_entities = ifc_model.get(
            "entities",
            {}
        )


        flat_ifc_elements = []


        for key, items in ifc_entities.items():

            if isinstance(items, list):

                flat_ifc_elements.extend(items)



        print(
            Counter(
                e.get("IFCType")
                for e in flat_ifc_elements
                if isinstance(e, dict)
            )
        )


        entities = ifc_model.get(
            "entities",
            {}
        )


        print(
            "\n====== IFC OUTPUT DEBUG ======"
        )


        print(
            type(ifc_model)
        )


        print(
            "IFC KEYS:",
            ifc_model.keys()
        )


        print(
            "IFC ENTITY COUNTS:"
        )


        print(
            Counter(
                {
                    k: len(v)
                    for k,v in entities.items()
                    if isinstance(v,list)
                }
            )
        )


        print(
            "TOTAL IFC ELEMENTS:",
            sum(
                len(v)
                for v in entities.values()
                if isinstance(v,list)
            )
        )




        print(
            "\n====== IFC SEMANTIC DEBUG ======"
        )



        for e in bim_elements[:10]:


            print(

                {

                    "id":
                        e.get(
                            "id"
                        ),


                    "ifc":
                        e.get(
                            "ifc_type"
                        ),


                    "semantic":
                        e.get(
                            "semantic_type"
                        ),


                    "role":
                        e.get(
                            "functional_role"
                        )

                }

            )



        # ==========================
        # IFC PRE CHECK
        # ==========================


        print(
            "\n====== BIM OPENINGS DEBUG ======"
        )



        doors = [

            e for e in bim_elements

            if e.get(
                "ifc_type"
            )
            ==
            "IfcDoor"

        ]



        windows = [

            e for e in bim_elements

            if e.get(
                "ifc_type"
            )
            ==
            "IfcWindow"

        ]




        print(
            "BIM DOORS:",
            len(doors)
        )



        print(
            "BIM WINDOWS:",
            len(windows)
        )





        if doors:


            print(
                "FIRST BIM DOOR:",
                doors[0]
            )




        if windows:


            print(
                "FIRST BIM WINDOW:",
                windows[0]
            )


        
        print(
            "\n====== BIM ELEMENT TYPE COUNTS ======"
        )




        print(

            Counter(

                e.get(
                    "ifc_type"
                )

                for e in bim_elements

                if isinstance(
                    e,
                    dict
                )

            )

        )





        print(
            "\n====== BEFORE IFC ELEMENT TYPES =========="
        )



        print(

            Counter(

                e.get(
                    "ifc_type"
                )

                for e in bim_elements

                if isinstance(
                    e,
                    dict
                )

            )

        )
        
        # ==========================
        # STRUCTURAL GRAPH
        # ==========================


        try:


            structural_graph = (

                self.structural_graph_engine.analyze(

                    bim_elements

                )

            )



        except Exception as error:


            structural_graph = {


                "status":
                    "failed",


                "error":
                    str(error)

            }





        # ==========================
        # REVIT EXPORT
        # ==========================


        try:


            exporter = RevitExportEngine()


            # ==========================
            # DEBUG BEFORE EXPORTER INPUT
            # ==========================

            print(
                "\n====== BEFORE EXPORTER INPUT ======"
            )


            beam_ids = [
                e.get("id")
                for e in bim_elements
                if e.get("ifc_type") == "IfcBeam"
            ]


            print(
                "BEAMS BEFORE EXPORT:",
                len(beam_ids)
            )


            print(
                "UNIQUE BEFORE EXPORT:",
                len(set(beam_ids))
            )


            for e in bim_elements:

                if e.get("ifc_type") == "IfcBeam":

                    print(
                        {
                            "id": e.get("id"),
                            "source": e.get("data",{}).get("source_id"),
                            "level": e.get("data",{}).get("level")
                        }
                    )


            print(
                "===================================="
            )


            bim = exporter.export(

                {


                    "bim_elements":
                        bim_elements,


                    "structure":
                        structure,


                    "spatial":
                        spatial


                },


                site

            )



        except Exception as error:


            bim = {


                "status":
                    "failed",


                "error":
                    str(error)

            }
        


        # ==========================
        # FINAL BIM ELEMENT CHECK
        # ==========================

        print("\n====== FINAL PIPELINE INPUT CHECK ======")

        beam_ids = [
            e.get("id")
            for e in bim_elements
            if e.get("ifc_type") == "IfcBeam"
        ]

        print(
            "FINAL BEAMS:",
            len(beam_ids)
        )

        print(
            beam_ids
        )

        print("======================================")

        print("\n====== BEFORE BIM RETURN ======")

        beam_ids = [
            e.get("id")
            for e in bim_elements
            if e.get("ifc_type") == "IfcBeam"
        ]

        print(
            "BEAMS:",
            len(beam_ids)
        )

        print(
            "UNIQUE:",
            len(set(beam_ids))
        )

        print(
            "DUPLICATES:",
            [
                x
                for x, c in Counter(beam_ids).items()
                if c > 1
            ]
        )

        print(
            "================================"
        )


        # FINAL RESULT SAFETY DEFAULTS

        cleanup_result = locals().get(
            "cleanup_result",
            {}
        )

        normalizer_result = locals().get(
            "normalizer_result",
            {}
        )

        asset_elements = locals().get(
            "asset_elements",
            []
        )

        structural_graph = locals().get(
            "structural_graph",
            None
        )

        structural_reasoning = locals().get(
            "structural_reasoning",
            None
        )

        structural_decision = locals().get(
            "structural_decision",
            None
        )

        structural_learning = locals().get(
            "structural_learning",
            None
        )

        semantic_bim = locals().get(
            "semantic_bim",
            {}
        )


        result = {

            "engine":
            f"FULL_BIM_PIPELINE_v{self.VERSION}",


            "status":
            "completed",


            "project":
            project or {},

            "run_id":
            project.get("run_id", "architecture_first"),

            "export_session":
            project.get("export_session", "DEFAULT"),

            "geometry":
            copy.deepcopy(geometry),

            "architectural_geometry":
            copy.deepcopy(project.get("architectural_geometry", geometry)),

            "vertical_section":
            copy.deepcopy(project.get("vertical_section", geometry.get("vertical_section", {}))),

            "geometry_intent":
            copy.deepcopy(project.get("geometry_intent", {})),


            # ==========================================
            # ARCHITECTURE-FIRST BUILDING CONFIG
            #
            # Preserve the authoritative architectural
            # level contract through ExportOrchestrator.
            # ==========================================

            
            "building_config":
            copy.deepcopy(
                building_config
            ),


            "site":
            site,


            "zoning":
            zoning,


            "spatial":
            spatial,


            "structure":
            structure,


            "bim":
            bim,


            "bim_elements":
                bim_elements,


            "geometry_cleanup":
            cleanup_result,


            "structural_geometry_normalizer":
            normalizer_result,


            "ifc_model":
            ifc_model,


            "structural_graph":
            structural_graph,


            "structural_reasoning":
            structural_reasoning,


            "structural_decision":
            structural_decision,


            "structural_learning":
            structural_learning,


            "semantic_bim":
            semantic_bim,


            "assets":
            asset_elements,

        }
        try:


            print("\n====== EXPORT INPUT IFC DEBUG ======")

            export_ifc = result.get(
                "ifc_model",
                {}
            )

            print(
                "EXPORT IFC TYPE:",
                type(export_ifc)
            )


            if isinstance(export_ifc, dict):

                print(
                    "EXPORT IFC KEYS:",
                    export_ifc.keys()
                )


                print(
                    "EXPORT IFC TOTAL:",
                    sum(
                        len(v)
                        for v in export_ifc.get(
                            "entities",
                            {}
                        ).values()
                        if isinstance(v,list)
                    )
                )

            export_result = (
                self.export_orchestrator.export(
                    copy.deepcopy(result)
                )
            )


            print(
                "\n====== EXPORT RESULT DEBUG ======"
            )

            print(
                type(export_result)
            )

            print(
                export_result.keys()
                if isinstance(export_result, dict)
                else None
            )


        except Exception as error:


            export_result = {

                "status":
                "failed",

                "error":
                str(error)

            }



        result["exports"] = export_result
        try:

            validator = BIMExportValidator()


            result["exports"]["validation"] = (

                validator.validate(

                    result,

                    result["exports"]

                )

            )


        except Exception as error:


            result["exports"]["validation"] = {

                "status":
                    "failed",

                "error":
                    str(error)

            }



        return result
