from core.layout.architectural_layout_engine import (
    ArchitecturalLayoutEngine
)
# ==================================================
# ArchitectOS Design Execution Bridge v100
# Decision -> Action -> Design -> BIM
# ==================================================


class ArchitectOSDesignExecutionBridge:


    VERSION = "100.0"



    def __init__(self):

        print(
            f"🔧 ArchitectOS Design Execution Bridge v{self.VERSION} ACTIVE"
        )



    # ==================================================
    # PROCESS
    # ==================================================

    def process(
        self,
        design,
        decisions
    ):


        print("\n====== EXECUTION BRIDGE RAW INPUT TYPE ======")

        print(
            type(design)
        )

        print(
            design
        )


        print("\n====== EXECUTION BRIDGE INPUT ======")
        print(design.keys())
        print("spatial:", design.get("spatial"))
        print("geometry:", design.get("geometry"))


        from core.intelligence.architectural_design_action_executor_v2 import (
            ArchitecturalDesignActionExecutorV2
        )


        action_executor = ArchitecturalDesignActionExecutorV2()


        if isinstance(
            decisions,
            dict
        ):

            actions = action_executor.execute(
                decisions
            )

        else:

            actions = self._convert_decisions(
                decisions
            )



        from core.execution.design_action_executor import (
            DesignActionExecutor
        )


        executor = DesignActionExecutor()


        print("\n====== BEFORE ACTION EXECUTOR ======")

        print(
            "DESIGN KEYS:",
            design.keys()
        )

        print(
            "STRUCTURAL GRID:",
            design.get(
                "structural_grid"
            )
        )

        print(
            "SPATIAL:",
            design.get(
                "spatial"
            )
        )

        print("===================================")



        execution_result = executor.apply(

            design,

            actions

        )


        print("\n====== EXECUTION RESULT DESIGN TRACE ======")

        print(
            "EXECUTION RESULT DESIGN:",
            execution_result.get("design")
        )

        print(
            "DESIGN KEYS:",
            (
                execution_result.get("design", {}).keys()
                if isinstance(
                    execution_result.get("design"),
                    dict
                )
                    else None
            )
        )

        if isinstance(
            execution_result.get("design"),
            dict
        ):

            print(
                "DESIGN STRUCTURAL GRID:",
                execution_result["design"].get(
                    "structural_grid"
                )
            )

            print(
                "DESIGN SPATIAL:",
                execution_result["design"].get(
                    "spatial"
                )
            )

            print(
                "DESIGN GEOMETRY:",
                execution_result["design"].get(
                    "geometry"
                )
            )

        print("============================================")



        from core.integration.design_bim_bridge import (
            DesignBIMBridge
        )


        from core.bim.design_geometry_adapter import (
            DesignGeometryAdapter
        )


        bridge = DesignBIMBridge()



        final_design = execution_result.get(
            "design",
            design
        )

        # The production GOD_CORE result carries architectural intent but does
        # not itself run the architecture-first model.  Resolve that missing
        # boundary here before any legacy spatial adapter is allowed to build
        # room rectangles.  Existing authoritative geometry always wins.
        existing_authoritative = final_design.get("architectural_geometry")
        if not isinstance(existing_authoritative, dict) or not any(
            bool(existing_authoritative.get(key))
            for key in (
                "spaces", "physical_walls", "openings", "slabs",
                "floor_geometry", "vertical_geometry", "site_geometry",
            )
        ):
            architecture_intent = (
                final_design.get("architectural_intent")
                or design.get("architectural_intent")
            )
            if isinstance(architecture_intent, dict) and architecture_intent:
                # ---------------------------------------------------------
                # GENERATOR-SELECTION BOUNDARY (smallest routing boundary).
                #
                # HouseDiffusion is the locked PRIMARY ArchitectOS plan
                # generator under HOUSE_DIFFUSION_GENERATION_POLICY_V1.  The
                # internal rule-based synthesis branch may run here ONLY as an
                # explicit, recorded fallback - never as the normal primary
                # source and never silently.  Any other role raises
                # PRIMARY_GENERATOR_BYPASS_DETECTED.
                # ---------------------------------------------------------
                from core.architecture.routing.generation_policy_guard_v1 import (
                    ROLE_EXPLICIT_FALLBACK,
                    guard_internal_plan_generation,
                )

                generation_metadata = guard_internal_plan_generation(
                    invocation_role=ROLE_EXPLICIT_FALLBACK,
                    source="ArchitectOSDesignExecutionBridge.process",
                )
                final_design["plan_generation"] = generation_metadata

                from core.architecture.brain.architectural_brain import (
                    ArchitecturalBrain,
                )

                architecture_model = ArchitecturalBrain().design(
                    architecture_intent
                )
                resolved_geometry = getattr(
                    architecture_model, "architectural_geometry", None
                )
                if isinstance(resolved_geometry, dict) and resolved_geometry:
                    final_design["architectural_geometry"] = resolved_geometry
                    final_design["geometry"] = resolved_geometry
                    final_design["architecture_first"] = True
                    for key in (
                        "vertical_section", "geometry_intent",
                        "spatial_contract",
                    ):
                        value = getattr(architecture_model, key, None)
                        if isinstance(value, dict):
                            final_design[key] = value


        print("\n====== EXECUTION RESULT STRUCTURAL TRACE ======")

        print(
            "EXECUTION RESULT KEYS:",
            execution_result.keys()
            if isinstance(execution_result, dict)
            else type(execution_result)
        )

        print(
            "EXECUTION RESULT STRUCTURAL GRID:",
            execution_result.get("structural_grid")
            if isinstance(execution_result, dict)
            else None
        )

        print(
            "EXECUTION RESULT GEOMETRY:",
            execution_result.get("geometry")
            if isinstance(execution_result, dict)
            else None
        )

        print("===============================================")


        # ==================================================
        # RESTORE SPATIAL GEOMETRY CONTRACT
        # ==================================================

        if (
            isinstance(final_design, dict)
            and
            "geometry" not in final_design
        ):

            final_design["geometry"] = {}


        if isinstance(final_design, dict):

            if design.get("spatial"):

                final_design["spatial"] = design.get(
                    "spatial"
                )


            if design.get("layout"):

                final_design["layout"] = design.get(
                    "layout"
                )


            if design.get("structural_grid"):

                final_design["structural_grid"] = design.get(
                    "structural_grid"
                )


        print(
            "SPATIAL TYPE:",
            type(
                final_design.get("spatial")
            )
        )


        print(
            "SPATIAL KEYS:",
            final_design.get(
                "spatial",
                {}
            ).keys()
            if isinstance(
                final_design.get("spatial"),
                dict
            )
            else None
        )


        print("\n====== BIM DESIGN CONTRACT ======")

        print(
            "spatial:",
            final_design.get("spatial")
        )

        print(
            "geometry:",
            final_design.get("geometry")
        )


        # ==========================================
        # DESIGN → GEOMETRY CONTRACT
        # ==========================================

        print(
            "\n====== LAYOUT SOURCE DEBUG ======"
        )

        print(
            "LAYOUT:",
            final_design.get(
                "layout"
            )
        )

        print(
            "================================="
        )

        authoritative_geometry = final_design.get("architectural_geometry")
        if not isinstance(authoritative_geometry, dict) or not any(
            bool(authoritative_geometry.get(key))
            for key in (
                "spaces", "physical_walls", "openings", "slabs",
                "floor_geometry", "vertical_geometry"
            )
        ):
            authoritative_geometry = design.get("architectural_geometry")

        authoritative_available = isinstance(authoritative_geometry, dict) and any(
            bool(authoritative_geometry.get(key))
            for key in (
                "spaces", "physical_walls", "openings", "slabs",
                "floor_geometry", "vertical_geometry"
            )
        )
        if authoritative_available:
            final_design["architectural_geometry"] = authoritative_geometry
            final_design["geometry"] = authoritative_geometry
            final_design["architecture_first"] = True

        for contract_key in ("vertical_section", "geometry_intent", "spatial_contract"):
            if design.get(contract_key):
                final_design[contract_key] = design[contract_key]

        layout_engine = ArchitecturalLayoutEngine()


        architectural_layout = (
            layout_engine.generate(
                final_design
            )
        )


        adapter = DesignGeometryAdapter()


        print("\n====== GEOMETRY INPUT DEBUG ======")

        print(
            "ARCHITECTURAL LAYOUT:",
            architectural_layout
        )

        print(
            "=================================="
        )

        if not architectural_layout.get("levels"):

            print(
                "⚠️ ARCHITECTURAL LAYOUT EMPTY"
            )

        geometry_input = {

            "spatial": {}

        }


        for level, spaces in architectural_layout.get(
            "levels",
            {}
        ).items():

            geometry_input["spatial"][level] = {

                "nodes": spaces

            }


        geometry_result = adapter.convert(
            {
                **geometry_input,
                "architectural_geometry": authoritative_geometry,
            }
        )


        final_design["geometry"] = (
            geometry_result.get(
                "geometry",
                {}
            )
        )


        print("\n====== EXECUTION GEOMETRY ======")

        print(
            "rooms:",
            len(
                final_design["geometry"].get(
                    "rooms",
                    []
                )
            )
        )

        print(
            "walls:",
            len(
                final_design["geometry"].get(
                    "walls",
                    []
                )
            )
        )

        print(
            "doors:",
            len(
                final_design["geometry"].get(
                    "doors",
                    []
                )
            )
        )

        print(
            "windows:",
            len(
                final_design["geometry"].get(
                    "windows",
                    []
                )
            )
        )


        print("\n====== FINAL DESIGN BEFORE BIM ======")

        print(
            "keys:",
            final_design.keys()
        )

        print(
            "spatial:",
            final_design.get("spatial")
        )

        print(
            "geometry:",
            final_design.get("geometry")
        )



        bim_result = bridge.run_bim(
            final_design
        )



        print("\n====== DESIGN EXECUTION BRIDGE OUTPUT ======")

        print(
            "FINAL DESIGN STRUCTURAL GRID:",
            final_design.get(
                "structural_grid"
            )
        )

        print(
            "GEOMETRY STRUCTURAL GRID:",
            final_design.get(
                "geometry",
                {}
            ).get(
                "structural_grid"
            )
        )

        print(
            "LOCAL VARIABLES:",
            locals().keys()
        )

        print("============================================")

        print(
            "LOCAL VARIABLES:",
            locals().keys()
        )

        print("============================================")



        return {


            "engine":
            f"architectos_design_execution_bridge_v{self.VERSION}",


            "status":
            "completed",


            "action_count":
            len(actions),


            "actions":
            actions,


            "execution_ready":
            True,


            "execution":
            execution_result,


            "design":
            final_design,


            "bim_result":
            bim_result

        }



    # ==================================================
    # DECISION CONVERTER
    # ==================================================

    def _convert_decisions(
        self,
        decisions
    ):


        actions = []



        if not isinstance(
            decisions,
            list
        ):

            return actions



        for decision in decisions:


            if not isinstance(
                decision,
                dict
            ):

                continue



            # Already action format

            if (
                "module" in decision
                and
                "action" in decision
            ):

                actions.append(
                    decision
                )

                continue



            action = decision.get(
                "action"
            )


            target = decision.get(
                "target"
            )


            reason = decision.get(
                "reason",
                ""
            )



            # ==========================================
            # FACADE
            # ==========================================


            if action == "add_solar_protection":


                actions.append({

                    "module":
                    "facade",


                    "action":
                    "solar_protection",


                    "parameters":
                    {
                        "level":
                        "high"
                    },


                    "reason":
                    reason

                })



            elif action == "add_horizontal_shading":


                actions.append({

                    "module":
                    "facade",


                    "action":
                    "add_shading",


                    "parameters":
                    {
                        "type":
                        "horizontal"
                    },


                    "reason":
                    reason

                })



            # ==========================================
            # MATERIAL
            # ==========================================


            elif action == "prefer_thermal_materials":


                actions.append({

                    "module":
                    "materials",


                    "action":
                    "select_thermal_materials",


                    "parameters":
                    {
                        "strategy":
                        "heat_reduction"
                    },


                    "reason":
                    reason

                })



            # ==========================================
            # ROOF
            # ==========================================


            elif action == "preserve_green_roof":


                actions.append({

                    "module":
                    "roof",


                    "action":
                    "preserve_green_roof",


                    "parameters":
                    {
                        "thermal_strategy":
                        True
                    },


                    "reason":
                    reason

                })



            # ==========================================
            # UNKNOWN PASSTHROUGH
            # ==========================================


            else:


                actions.append({

                    "module":
                    target or "unknown",


                    "action":
                    action,


                    "parameters":
                    {},


                    "reason":
                    reason

                })



        return actions
