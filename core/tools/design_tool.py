from core.tools.base import BaseTool
import re
import inspect

from core.spatial.spatial_engine import SpatialLayoutEngine
from core.site.site_engine import SiteEngine
from core.zoning.zoning_rule_engine import ZoningRuleEngine
from core.site.architectural_site_contract import ArchitecturalSiteContract


from core.structure.structural_grid_engine import (
    StructuralGridEngine
)

from core.architecture.brain.architectural_brain import (
    ArchitecturalBrain
)

from core.architecture.drawing.plan_drawing_service_v1 import (
    PlanDrawingServiceV1
)


print("\n====== CALLER TRACE ======")

for frame in inspect.stack()[:8]:
    print(
        frame.filename,
        "::",
        frame.function,
        "::",
        frame.lineno
    )

print("==========================")


class DesignTool(BaseTool):

    name = "design"

    def __init__(self):

        self.architectural_brain = (
            ArchitecturalBrain()
        )


    # ======================
    # SITE PARSER
    # ======================
    def extract_site(self, state: str):

        state = (state or "").lower()

        if "polygon" in state:
            return {
                "type": "polygon",
                "points": [
                    (0, 0),
                    (10, 0),
                    (10, 10),
                    (0, 10)
                ]
            }

        if "utm" in state:
            return {
                "type": "utm",
                "zone": 40,
                "easting": 500000,
                "northing": 3950000,
                "approx_area": 1200
            }


        return {
            "type": "rect",
            "width": 12,
            "height": 10
        }



    def extract_dimensions(self, text):

        match = re.findall(
            r"(\d+)\s*[x*]\s*(\d+)",
            (text or "").lower()
        )

        return (
            int(match[0][0]),
            int(match[0][1])
        ) if match else (16, 16)



    # ======================
    # FLOOR MODEL
    # ======================
    def build_functional_floors(
        self,
        context=None
    ):

        if context:

            program = context.get(
                "building_program",
                {}
            )

            floors = program.get(
                "floors"
            )

            if floors:

                print(
                    "\n====== USING PLANNER FLOORS ======"
                )

                print(
                    floors
                )

                print(
                    "=================================="
                )

                return floors

        return [

            {
                "name": "F1",
                "type": "parking"
            },

            {
                "name": "F2",
                "type": "single_unit",
                "bedrooms": 3
            },

            {
                "name": "F3",
                "type": "multi_unit_roof",
                "units": 1,
                "bedrooms_per_unit": 2
            }

        ]



    # ======================
    # GRAPH ENGINE
    # ======================
    def build_graph(self, floor):

        f = floor["name"]


        if floor["type"] == "parking":

            return {

                f"{f}-Ramp":
                    [
                        f"{f}-Parking-Spaces"
                    ],

                f"{f}-Parking-Spaces":
                    [
                        f"{f}-Ramp"
                    ]

            }



        if floor["type"] == "single_unit":

            graph = {

                f"{f}-Living":
                    [
                        f"{f}-Kitchen",
                        f"{f}-Circulation"
                    ],

                f"{f}-Kitchen":
                    [
                        f"{f}-Living"
                    ],

                f"{f}-Circulation":
                    []

            }


            circulation = f"{f}-Circulation"


            for i in range(floor["bedrooms"]):

                room = f"{f}-Bedroom-{i+1}"

                graph[circulation].append(room)

                graph[room] = [
                    circulation
                ]


            return graph



        if floor["type"] == "multi_unit_roof":

            graph = {}

            cores = []


            for u in range(floor["units"]):

                uid = f"{f}-Unit-{u+1}"


                graph[f"{uid}-Living"] = [

                    f"{uid}-Kitchen",

                    f"{uid}-Circulation"

                ]


                graph[f"{uid}-Kitchen"] = [

                    f"{uid}-Living"

                ]


                circulation = f"{uid}-Circulation"


                graph[circulation] = []


                cores.append(circulation)


                for i in range(floor["bedrooms_per_unit"]):

                    room = f"{uid}-Bedroom-{i+1}"

                    graph[circulation].append(room)

                    graph[room] = [

                        circulation

                    ]


            graph[f"{f}-Core-Stair"] = cores

            graph[f"{f}-Roof-Terrace"] = [

                f"{f}-Core-Stair"

            ]


            return graph



        return {}
    # ======================
    # SPATIAL ENGINE (STEP 42)
    # ======================
    def build_spatial(
        self,
        floors,
        width,
        height
    ):

        print(
            "\n====== SPATIAL ENGINE INPUT DEBUG ======"
        )

        print(
            {
                "width": width,
                "height": height,
                "floors": floors
            }
        )

        print(
            "========================================="
        )


        engine = SpatialLayoutEngine()


        print(
            "\n====== SPATIAL ENGINE METHODS DEBUG ======"
        )

        print(
            dir(engine)
        )

        print(
            "ENGINE FILE:",
            engine.__class__.__module__
        )

        print(
            "ENGINE CLASS:",
            engine.__class__
        )

        print(
            "=========================================="
        )


        print(
            "\n====== SPATIAL ENGINE CONFIG DEBUG ======"
        )

        print(
            "ENGINE UNIT:",
            engine.unit
        )

        print(
            "ENGINE TYPE:",
            type(engine)
        )

        print(
            "=========================================="
        )

        spatial_output = {}


        for floor in floors:

            graph = self.build_graph(
                floor
            )

            print(
                "\n====== GRAPH DEBUG ======"
            )

            print(
                "FLOOR:",
                floor["name"]
            )

            for k,v in graph.items():
                print(
                    k,
                    v
                )

            print(
                "========================="
            )

            print("\n====== RAW FLOOR LAYOUT CHECK ======")

            result = engine.layout(
                graph=graph,
                floor_name=floor["name"],
                width=width,
                height=height
            )

            print(
                "LEVEL:",
                floor["name"]
            )

            print(
                "RESULT KEYS:",
                result.keys()
            )   

            print(
                "WALL COUNT:",
                len(result.get("walls", []))
            )

            print(
                "FIRST WALL:",
                result.get("walls", [])[:1]
            )

            print(
                "====================================")


            spatial_output[floor["name"]] = result


            spatial_output[floor["name"]] = engine.layout(
                graph=graph,
                floor_name=floor["name"],
                width=width,
                height=height
            )

        print(
            "\n====== FINAL SPATIAL OUTPUT DEBUG ======"
        )

        for level, data in spatial_output.items():

            print(
                {
                    "level": level,
                    "width": data.get("width"),
                    "height": data.get("height")
                }
            )

        print(
            "========================================"
        )


        return spatial_output



    # ======================
    # SITE ENGINE (STEP 46)
    # ======================
    def build_site(
        self,
        state,
        context=None
    ):

        # ==================================================
        # REAL CAD SITE FIRST
        #
        # CADImportEngine already resolves the authoritative
        # parcel into a local-normalized architectural site.
        #
        # Do not rebuild or approximate it from text when
        # real CAD site intelligence is available.
        # ==================================================

        cad_data = None

        if isinstance(
            context,
            dict
        ):

            cad_data = context.get(
                "cad"
            )


        if isinstance(
            cad_data,
            dict
        ):

            cad_site = cad_data.get(
                "site"
            )

            if (
                isinstance(
                    cad_site,
                    dict
                )
                and
                cad_site.get(
                    "type"
                )
                in {
                    "polygon",
                    "rect",
                    "utm",
                    "dxf"
                }
            ):

                site = dict(
                    cad_site
                )

                print(
                    "\n🗺 REAL CAD SITE SELECTED"
                )

                print(
                    "SOURCE:",
                    site.get(
                        "source"
                    )
                )

                print(
                    "TARGET PARCEL:",
                    site.get(
                        "target_parcel"
                    )
                )

                print(
                    "COORDINATE SYSTEM:",
                    site.get(
                        "coordinate_system"
                    )
                )

                print(
                    "POINTS:",
                    site.get(
                        "points"
                    )
                )

                print(
                    "BBOX:",
                    site.get(
                        "bbox"
                    )
                )

                print(
                    "AREA:",
                    site.get(
                        "area"
                    )
                )

                print(
                    "========================================"
                )

                normalized_site = (
                    ArchitecturalSiteContract().normalize(
                        site
                    )
                )

                # ------------------------------------------
                # PRESERVE CAD SITE INTELLIGENCE
                #
                # ArchitecturalSiteContract currently
                # normalizes architectural geometry but
                # does not know the complete CAD metadata.
                # Preserve authoritative evidence here.
                # ------------------------------------------

                normalized_site[
                    "source"
                ] = site.get(
                    "source"
                )

                normalized_site[
                    "target_parcel"
                ] = site.get(
                    "target_parcel"
                )

                normalized_site[
                    "coordinate_system"
                ] = site.get(
                    "coordinate_system"
                )

                normalized_site[
                    "origin"
                ] = site.get(
                    "origin"
                )

                normalized_site[
                    "area"
                ] = site.get(
                    "area"
                )

                normalized_site[
                    "bbox"
                ] = site.get(
                    "bbox"
                )

                normalized_site[
                    "site_intelligence"
                ] = cad_data.get(
                    "site_intelligence"
                )

                # ------------------------------------------
                # PRESERVE CAD SITE CONSTRAINT CONTRACT
                #
                # SiteConstraintExtractor returns:
                #
                # {
                #     "status": "ready",
                #     "site_id": ...,
                #     "constraints": {
                #         "boundary": ...,
                #         "area": ...,
                #         "access": ...,
                #         "north": ...,
                #         "adjacency": [...]
                #     }
                # }
                #
                # Do NOT call list(...) on this dictionary.
                # Preserve the architectural generic
                # constraints list separately from the
                # authoritative CAD site-edge evidence.
                # ------------------------------------------

                cad_constraints = cad_data.get(
                    "constraints"
                )


                site_constraints = {}


                if isinstance(
                    cad_constraints,
                    dict
                ):

                    nested_constraints = (
                        cad_constraints.get(
                            "constraints"
                        )
                    )


                    if isinstance(
                        nested_constraints,
                        dict
                    ):

                        site_constraints = dict(
                            nested_constraints
                        )


                    normalized_site[
                        "site_constraint_status"
                    ] = cad_constraints.get(
                        "status"
                    )


                    normalized_site[
                        "site_id"
                    ] = cad_constraints.get(
                        "site_id"
                    )


                normalized_site[
                    "site_constraints"
                ] = site_constraints


                # Preserve ArchitecturalSiteContract generic
                # constraint collection independently.
                generic_constraints = normalized_site.get(
                    "constraints",
                    []
                )


                if not isinstance(
                    generic_constraints,
                    list
                ):

                    generic_constraints = []


                normalized_site[
                    "constraints"
                ] = generic_constraints

                normalized_site[
                    "parcel"
                ] = cad_data.get(
                    "parcel"
                )

                print(
                    "\n🗺 NORMALIZED REAL CAD SITE CONTRACT"
                )

                print(
                    normalized_site
                )

                return normalized_site

        # ==================================================
        # FALLBACK SITE
        #
        # Used only when no real CAD site exists.
        # ==================================================

        site_engine = SiteEngine()

        site = site_engine.load(
            self.extract_site(
                state
            )
        )

        print(
            "\n🗺 FALLBACK SITE BEFORE CONTRACT"
        )

        print(
            "TYPE:",
            type(
                site
            )
        )

        if isinstance(
            site,
            dict
        ):

            print(
                "KEYS:",
                list(
                    site.keys()
                )
            )

        print(
            "DATA:",
            site
        )

        site = ArchitecturalSiteContract().normalize(
            site
        )

        print(
            "\n🗺 NORMALIZED FALLBACK SITE CONTRACT"
        )

        print(
            site
        )

        return site


    # ======================
    # ZONING ENGINE (STEP 48)
    # ======================
    def run_zoning(
        self,
        site,
        width,
        height
    ):

        zoning = ZoningRuleEngine()

        building_plan = {

            "width":
                width,

            "depth":
                height

        }

        result = zoning.validate(

            site=site,

            building_plan=building_plan

        )

        print(
            "\n====== ZONING RESULT ======"
        )

        print(
            "REQUESTED BUILDING SIZE:",
            {
                "width": width,
                "depth": height
            }
        )

        print(
            "RESULT:",
            result
        )

        print(
            "==========================="
        )

        return result

    def _structural_space_type(
        self,
        node_id,
        node
    ):

        node_type = node.get(
            "type"
        )

        if isinstance(
            node_type,
            str
        ) and node_type:

            return node_type.lower()

        name = str(
            node_id
        ).lower()

        if (
            "core-stair" in name
            or
            "staircase" in name
            or
            "stairs" in name
            or
            "stair" in name
        ):
            return "stairs"

        if (
            "elevator" in name
            or
            "lift" in name
        ):
            return "elevator"

        if (
            "duct" in name
            or
            "shaft" in name
        ):
            return "duct"

        if (
            "public-circulation" in name
            or
            "public_circulation" in name
        ):
            return "public_circulation"

        if (
            "circulation" in name
            or
            "corridor" in name
        ):
            return "corridor"

        if "ramp" in name:
            return "ramp"

        if "living" in name:
            return "living"

        if "kitchen" in name:
            return "kitchen"

        if "bedroom" in name:
            return "bedroom"

        if "parking" in name:
            return "parking"

        if "terrace" in name:
            return "terrace"

        return "space"

    



    # ======================
    # STEP 49 — ADAPTIVE STRUCTURAL INTELLIGENCE
    # ======================
    def build_structural_grid(
        self,
        spatial_output,
        floors,
        width,
        height,
        context=None
    ):

        """
        Convert architectural spatial output into the
        StructuralGridEngine v2 contract.

        Structural topology is generated once for the
        whole building.

        This function does NOT create a fixed structural
        grid and does NOT use SpatialLayoutEngine.unit.
        """

        print(
            "\n====== ADAPTIVE STRUCTURAL GRID INPUT ======"
        )

        print(
            "BUILDING SIZE:",
            {
                "width": width,
                "depth": height
            }
        )

        spaces = []

        for floor_name, floor_data in spatial_output.items():

            nodes = floor_data.get(
                "nodes",
                {}
            )

            if not isinstance(
                nodes,
                dict
            ):
                continue

            for node_id, node in nodes.items():

                if not isinstance(
                    node,
                    dict
                ):
                    continue

                x = node.get(
                    "x"
                )

                y = node.get(
                    "y"
                )

                w = node.get(
                    "w"
                )

                h = node.get(
                    "h"
                )

                if None in [
                    x,
                    y,
                    w,
                    h
                ]:
                    continue

                semantic_type = self._structural_space_type(
                    node_id,
                    node
                )

                spaces.append(
                    {
                        "name":
                            node_id,

                        "type":
                            semantic_type,

                        "level":
                            floor_name,

                        "bounds":
                            [
                                x,
                                y,
                                w,
                                h
                            ]
                    }
                )

        # ==================================================
        # ARCHITECTURAL GEOMETRY -> STRUCTURE CONTEXT BRIDGE
        # v1.0
        #
        # ArchitecturalGeometry is the authoritative
        # architecture-first geometry contract when present.
        #
        # IMPORTANT:
        # - legacy spatial spaces are preserved for now
        # - parcel-local / rotated geometry is NOT flattened
        #   into the old rectangular structural coordinate
        #   model
        # - StructuralGridEngine will consume this explicit
        #   contract in the next stage
        # ==================================================

        architectural_geometry = {}


        if isinstance(
            context,
            dict
        ):

            context_architectural_geometry = context.get(
                "architectural_geometry"
            )


            if isinstance(
                context_architectural_geometry,
                dict
            ):

                architectural_geometry = (
                    context_architectural_geometry
                )


            if not architectural_geometry:

                design_model = context.get(
                    "design_model"
                )


                if design_model is not None:

                    model_architectural_geometry = getattr(
                        design_model,
                        "architectural_geometry",
                        None
                    )


                    if isinstance(
                        model_architectural_geometry,
                        dict
                    ):

                        architectural_geometry = (
                            model_architectural_geometry
                        )


        architectural_spaces = []


        if isinstance(
            architectural_geometry,
            dict
        ):

            for architectural_space in architectural_geometry.get(
                "spaces",
                []
            ):

                if not isinstance(
                    architectural_space,
                    dict
                ):

                    continue


                footprint = architectural_space.get(
                    "footprint"
                )


                architectural_spaces.append(
                    {
                        "name":
                            architectural_space.get(
                                "name"
                            ),

                        "floor":
                            architectural_space.get(
                                "floor"
                            ),

                        "type":
                            architectural_space.get(
                                "type"
                            ),

                        "protected_zone":
                            bool(
                                architectural_space.get(
                                    "protected_zone",
                                    False
                                )
                            ),

                        "placement_scope":
                            architectural_space.get(
                                "placement_scope"
                            ),

                        "access_requirement":
                            architectural_space.get(
                                "access_requirement"
                            ),

                        "coordinate_mode":
                            architectural_space.get(
                                "resolved_coordinate_mode",
                                architectural_space.get(
                                    "coordinate_mode"
                                )
                            ),

                        "geometry_status":
                            architectural_space.get(
                                "geometry_status"
                            ),

                        "footprint":
                            (
                                dict(
                                    footprint
                                )
                                if isinstance(
                                    footprint,
                                    dict
                                )
                                else None
                            ),

                        "width":
                            architectural_space.get(
                                "width"
                            ),

                        "depth":
                            architectural_space.get(
                                "depth"
                            )
                    }
                )


        print(
            "\n====== ARCHITECTURAL GEOMETRY STRUCTURE BRIDGE ======"
        )

        print(
            "ARCHITECTURAL GEOMETRY AVAILABLE:",
            bool(
                architectural_geometry
            )
        )

        print(
            "ARCHITECTURAL GEOMETRY SPACE COUNT:",
            len(
                architectural_spaces
            )
        )

        print(
            "PROTECTED ARCHITECTURAL SPACE COUNT:",
            len(
                [
                    space
                    for space in architectural_spaces
                    if space.get(
                        "protected_zone"
                    )
                ]
            )
        )

        print(
            "COORDINATE FRAME:",
            architectural_geometry.get(
                "coordinate_frame"
            )
            if isinstance(
                architectural_geometry,
                dict
            )
            else None
        )

        print(
            "====================================================="
        )

        architectural_model = {

            "building": {
                "width":
                    width,

                "depth":
                    height
            },

            # ----------------------------------------------
            # LEGACY STRUCTURAL INPUT
            #
            # Preserved until StructuralGridEngine becomes
            # fully polygon / rigid-transform aware.
            # ----------------------------------------------

            "spaces":
                spaces,

            # ----------------------------------------------
            # ARCHITECTURE-FIRST CONTRACT
            # ----------------------------------------------

            "architectural_spaces":
                architectural_spaces,

            "architectural_geometry":
                architectural_geometry,

            "coordinate_frame":
                (
                    dict(
                        architectural_geometry.get(
                            "coordinate_frame",
                            {}
                        )
                    )
                    if isinstance(
                        architectural_geometry.get(
                            "coordinate_frame"
                        ),
                        dict
                    )
                    else {}
                ),

            "parcel_placement":
                (
                    dict(
                        architectural_geometry.get(
                            "parcel_placement",
                            {}
                        )
                    )
                    if isinstance(
                        architectural_geometry.get(
                            "parcel_placement"
                        ),
                        dict
                    )
                    else {}
                ),

            "architecture_first":
                bool(
                    architectural_spaces
                )
        }

        vertical_section = {
            "levels": []
        }

        for floor in floors or []:

            if not isinstance(
                floor,
                dict
            ):
                continue

            level_data = {
                "name":
                    floor.get(
                        "name"
                    ),

                "type":
                    floor.get(
                        "type"
                    )
            }

            if floor.get(
                "height"
            ) is not None:

                level_data[
                    "height"
                ] = floor.get(
                    "height"
                )

            vertical_section[
                "levels"
            ].append(
                level_data
            )

        print(
            "ARCHITECTURAL SPACE COUNT:",
            len(
                spaces
            )
        )

        print(
            "STRUCTURAL LEVEL COUNT:",
            len(
                vertical_section[
                    "levels"
                ]
            )
        )

        print(
            "============================================"
        )

        engine = StructuralGridEngine()

        result = engine.build(
            architectural_model,
            vertical_section
        )

        print(
            "\n====== ADAPTIVE STRUCTURAL GRID RESULT ======"
        )

        print(
            "GRID TYPE:",
            result.get(
                "grid_type"
            )
        )

        print(
            "COLUMN COUNT:",
            len(
                result.get(
                    "columns",
                    []
                )
            )
        )

        print(
            "BEAM COUNT:",
            len(
                result.get(
                    "beams",
                    []
                )
            )
        )

        print(
            "PROTECTED ZONE COUNT:",
            len(
                result.get(
                    "protected_zones",
                    []
                )
            )
        )

        print(
            "=============================================="
        )

        return result
    # ======================
    # PIPELINE
    # ======================
    def execute(self, state, context=None):

        print(
            "\n====== DESIGN TOOL EXECUTE START ======"
        )


        state = state or ""

        # ==================================================
        # ARCHITECTURAL BRAIN -> DESIGN TOOL BRIDGE v1.0
        #
        # ArchitecturalBrain is the authoritative source for:
        #
        # - architectural program
        # - floor-aware layout
        # - protected zones
        # - parcel-aware placement
        # - architectural geometry
        # - material / facade / roof intelligence
        #
        # The resulting model is injected into the SAME
        # runtime context consumed by the legacy DesignTool.
        #
        # Structure must consume this contract instead of
        # rebuilding architectural meaning independently.
        # ==================================================

        if not isinstance(
            context,
            dict
        ):

            context = {}


        architectural_intent = context.get(
            "architectural_intent",
            {}
        )


        if not isinstance(
            architectural_intent,
            dict
        ):

            architectural_intent = {}


        architectural_model = None

        # ---------------------------------------------------------------
        # GENERATOR-SELECTION BOUNDARY (smallest routing boundary).
        #
        # HouseDiffusion is the locked PRIMARY ArchitectOS plan generator
        # under HOUSE_DIFFUSION_GENERATION_POLICY_V1.  The internal
        # rule-based synthesis branch may run here ONLY as an explicit,
        # recorded fallback - never as the normal primary source and never
        # silently.  Any other role raises
        # PRIMARY_GENERATOR_BYPASS_DETECTED.
        # ---------------------------------------------------------------
        from core.architecture.routing.generation_policy_guard_v1 import (
            ROLE_EXPLICIT_FALLBACK,
            guard_internal_plan_generation,
        )

        generation_metadata = guard_internal_plan_generation(
            invocation_role=ROLE_EXPLICIT_FALLBACK,
            source="DesignTool.execute",
        )

        context["plan_generation"] = generation_metadata

        try:

            architectural_model = (
                self.architectural_brain.design(
                    architectural_intent
                )
            )

        except Exception as error:

            print(
                "ARCHITECTURAL BRAIN DESIGN ERROR:",
                error
            )


        if architectural_model is not None:

            context[
                "design_model"
            ] = architectural_model


            architectural_geometry = getattr(
                architectural_model,
                "architectural_geometry",
                None
            )


            if isinstance(
                architectural_geometry,
                dict
            ):

                context[
                    "architectural_geometry"
                ] = architectural_geometry


            geometry_intent = getattr(
                architectural_model,
                "geometry_intent",
                None
            )


            if isinstance(
                geometry_intent,
                dict
            ):

                context[
                    "geometry_intent"
                ] = geometry_intent


            spatial_contract = getattr(
                architectural_model,
                "spatial_contract",
                None
            )


            if isinstance(
                spatial_contract,
                dict
            ):

                context[
                    "spatial_contract"
                ] = spatial_contract

            vertical_section = getattr(
                architectural_model,
                "vertical_section",
                None
            )

            if isinstance(vertical_section, dict):
                context["vertical_section"] = vertical_section


            layout = getattr(
                architectural_model,
                "layout",
                None
            )


            if layout is not None:

                context[
                    "layout"
                ] = layout


            model_building_program = getattr(
                architectural_model,
                "building_program",
                None
            )


            if (
                isinstance(
                    model_building_program,
                    dict
                )
                and
                model_building_program
            ):

                context[
                    "building_program"
                ] = model_building_program


            # ==================================================
            # PLAN DRAWING BRIDGE v1.0
            #
            # Additive only. Translates the already-resolved
            # ArchitecturalPlanModel into a renderable plan
            # artefact using the existing plan-to-scene adapter
            # and the existing SVG/PDF renderers.
            #
            # This bridge never invents geometry, coordinates,
            # dimensions, or labels. Rooms whose upstream
            # footprint is unresolved stay pending. It never
            # mutates the design model or the design context.
            # ==================================================

            try:

                plan_drawing = (
                    PlanDrawingServiceV1().render(
                        architectural_model
                    )
                )

            except Exception as plan_error:

                print(
                    "PLAN DRAWING BRIDGE ERROR:",
                    plan_error
                )

                plan_drawing = {
                    "status": "unavailable",
                    "type": "plan_drawing",
                    "reason": f"bridge_failed: {plan_error}"
                }


            context[
                "plan_drawing"
            ] = plan_drawing


        print(
            "\n====== ARCHITECTURAL BRAIN DESIGN BRIDGE ======"
        )

        print(
            "DESIGN MODEL AVAILABLE:",
            architectural_model is not None
        )

        print(
            "ARCHITECTURAL GEOMETRY AVAILABLE:",
            isinstance(
                context.get(
                    "architectural_geometry"
                ),
                dict
            )
        )

        print(
            "GEOMETRY INTENT AVAILABLE:",
            isinstance(
                context.get(
                    "geometry_intent"
                ),
                dict
            )
        )

        print(
            "SPATIAL CONTRACT AVAILABLE:",
            isinstance(
                context.get(
                    "spatial_contract"
                ),
                dict
            )
        )

        if isinstance(
            context.get(
                "architectural_geometry"
            ),
            dict
        ):

            print(
                "ARCHITECTURAL GEOMETRY KEYS:",
                context[
                    "architectural_geometry"
                ].keys()
            )

            print(
                "ARCHITECTURAL SPACE COUNT:",
                len(
                    context[
                        "architectural_geometry"
                    ].get(
                        "spaces",
                        []
                    )
                )
            )

            print(
                "PROTECTED ARCHITECTURAL SPACES:",
                [
                    (
                        space.get(
                            "floor"
                        ),
                        space.get(
                            "name"
                        )
                    )
                    for space
                    in context[
                        "architectural_geometry"
                    ].get(
                        "spaces",
                        []
                    )
                    if isinstance(
                        space,
                        dict
                    )
                    and space.get(
                        "protected_zone"
                    )
                ]
            )

        print(
            "==============================================="
        )

        print(
            "\n====== DESIGN TOOL CONTEXT DEBUG ======"
        )

        print(
            context
        )

        print(
            "======================================"
        )


        site = self.build_site(
            state,
            context=context
        )


        width, height = self.extract_dimensions(
            state
        )


        zoning_result = self.run_zoning(
            site,
            width,
            height
        )


        cad_data = None

        if context:

            cad_data = context.get(
                "cad"
            )


        if cad_data:

            print(
                "\n====== CAD CONTEXT CONNECTED ======"
            )

            print(
                cad_data.keys()
            )

            print(
                "PARCEL:",
                cad_data.get("parcel")
            )

            print(
                "===================================="
            )

        print("RAW DESIGN STATE:")
        print(state)


        print(
            "\n====== ARCHITECTURAL CONTEXT DEBUG ======"
        )

        if isinstance(
            context,
            dict
        ):

            print(
                "CONTEXT KEYS:",
                context.keys()
            )

            for context_key in [
                "architectural_intent",
                "building_program",
                "architectural_geometry",
                "geometry_intent",
                "spatial_contract",
                "layout",
                "spatial_layout",
                "design_model",
                "cad",
                "site_analysis"
            ]:

                context_value = context.get(
                    context_key
                )

                if context_value is not None:

                    print(
                        "CONTEXT CONTRACT:",
                        context_key,
                        "TYPE:",
                        type(
                            context_value
                        ).__name__
                    )

                    if isinstance(
                        context_value,
                        dict
                    ):

                        print(
                            "CONTEXT CONTRACT KEYS:",
                            context_key,
                            context_value.keys()
                        )

        print(
            "CONTEXT:",
            context
        )

        if context:

            print(
                "ARCHITECTURAL INTENT:",
                context.get(
                    "architectural_intent"
                )
            )

            print(
                "BUILDING PROGRAM:",
                context.get(
                    "building_program"
                )
            )

        print(
            "=========================================="
        )
        

        floors = self.build_functional_floors(
            context
        )

        print(
            "FINAL FLOORS SOURCE:",
            floors
        )


        full_graph = {}

        for floor in floors:

            graph = self.build_graph(
                floor
            )


            for k, v in graph.items():

                full_graph[
                    f"{floor['name']}::{k}"
                ] = v


        print("BUILD DIMENSIONS:", width, height)

        spatial_output = self.build_spatial(
            floors,
            width,
            height
        )


        print(
            "\n====== SPATIAL OUTPUT CHECK ======"
        )

        print(
            spatial_output
        )

        print(
            "================================="
        )



        structural_grid = self.build_structural_grid(
            spatial_output,
            floors,
            width,
            height,
            context=context
        )


        print(
            "\n====== FINAL GRID BEFORE BIM ======"
        )


        print(
            "\n====== FINAL STRUCTURAL INTELLIGENCE ======"
        )

        print(
            "TYPE:",
            structural_grid.get(
                "grid_type"
            )
        )

        print(
            "COLUMNS:",
            len(
                structural_grid.get(
                    "columns",
                    []
                )
            )
        )

        print(
            "BEAMS:",
            len(
                structural_grid.get(
                    "beams",
                    []
                )
            )
        )

        print(
            "LEVELS:",
            structural_grid.get(
                "levels",
                []
            )
        )

        print(
            "============================================"
        )



        return {

            "type": "design",

            "site": site,

            "zoning": zoning_result,

            "graph": full_graph,

            "spatial": spatial_output,

            "geometry": context.get("architectural_geometry", {}),

            "architectural_geometry": context.get("architectural_geometry", {}),

            "geometry_intent": context.get("geometry_intent", {}),

            "vertical_section": context.get("vertical_section", {}),

            "spatial_contract": context.get("spatial_contract", {}),

            "architecture_first": bool(context.get("architectural_geometry")),

            "plan_drawing": context.get("plan_drawing"),

            "structural_grid": structural_grid

        }
