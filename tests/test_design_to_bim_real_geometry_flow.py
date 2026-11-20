from core.tools.design_tool import DesignTool
from core.integration.design_bim_bridge import DesignBIMBridge
from core.bim.design_geometry_adapter import DesignGeometryAdapter
from core.bim.full_bim_pipeline import FullBIMPipeline


def test_design_to_bim_real_geometry_flow():

    print(
        "\nDESIGN -> BIM REAL GEOMETRY FLOW TEST START"
    )


    # ======================================
    # STEP 1
    # DESIGN ONLY
    # ======================================

    design_tool = DesignTool()

    design_result = design_tool.execute(
        state="modern villa 12x10"
    )

    print("\n========== DESIGN SPATIAL ==========")
    print(design_result.get("spatial"))

    spatial_debug = design_result.get(
        "spatial",
        {}
    )

    print(
        "\n========== DESIGN SPATIAL CONTRACT =========="
    )

    print(
        "SPATIAL TYPE:",
        type(spatial_debug).__name__
    )

    if isinstance(
        spatial_debug,
        dict
    ):

        print(
            "SPATIAL KEYS:",
            list(
                spatial_debug.keys()
            )
        )

        for floor_name, floor_data in spatial_debug.items():

            print(
                "FLOOR:",
                floor_name,
                "TYPE:",
                type(
                    floor_data
                ).__name__
            )

            if isinstance(
                floor_data,
                dict
            ):

                print(
                    "FLOOR KEYS:",
                    list(
                        floor_data.keys()
                    )
                )

                nodes = floor_data.get(
                    "nodes"
                )

                print(
                    "NODES TYPE:",
                    type(
                        nodes
                    ).__name__
                )

                if isinstance(
                    nodes,
                    dict
                ):

                    print(
                        "NODE COUNT:",
                        len(
                            nodes
                        )
                    )

                    if nodes:

                        first_node_id = next(
                            iter(
                                nodes
                            )
                        )

                        print(
                            "FIRST NODE ID:",
                            first_node_id
                        )

                        print(
                            "FIRST NODE:",
                            nodes[
                                first_node_id
                            ]
                        )

            break

    print(
        "============================================="
    )


    assert design_result is not None

    assert (
        design_result.get("type")
        ==
        "design"
    )


    print("Design layer validated")



    # ======================================
    # STEP 2
    # DESIGN GEOMETRY ADAPTER
    # ======================================

    adapter = DesignGeometryAdapter()


    print(
        "DEBUG DESIGN SPATIAL:",
        design_result.get("spatial")
    )


    geometry_result = adapter.convert(
        {
            "spatial":
            design_result.get(
                "spatial",
                {}
            )
        }
    )


    print("\n========== ADAPTER RESULT ==========")
    print(geometry_result)


    print(
        "DEBUG ADAPTER GEOMETRY:",
        geometry_result
    )



    geometry = geometry_result.get(
        "geometry"
    )


    assert geometry is not None


    assert (
        "rooms"
        in geometry
    )


    # ======================================
    # OPENINGS VALIDATION
    # USE ADAPTER OUTPUT
    # ======================================

    print(
        "Geometry contract generated"
    )


    print(
        "DEBUG DOOR COUNT:",
        len(
            geometry.get(
                "doors",
                []
            )
        )
    )


    print(
        "DEBUG WINDOW COUNT:",
        len(
            geometry.get(
                "windows",
                []
            )
        )
    )


    assert len(
        geometry.get("doors", [])
    ) > 0


    assert len(
        geometry.get("windows", [])
    ) > 0


    print(
        "Geometry contract generated"
    )


    print(
        "DEBUG DOOR COUNT:",
        len(
            geometry.get(
                "doors",
                []
            )
        )
    )


    print(
        "DEBUG WINDOW COUNT:",
        len(
            geometry.get(
                "windows",
                []
            )
        )
    )



    # ======================================
    # STEP 3
    # BRIDGE
    # ======================================

    bridge = DesignBIMBridge()


    bim_project = bridge.prepare_bim_project(
        {
            **design_result,

            "geometry":
            geometry
        }
    )

    bim_project["export_session"] = (
        "DESIGN_TO_BIM_REAL_GEOMETRY"
    )


    print("\n========== BIM PROJECT GEOMETRY ==========")
    print(bim_project.get("geometry"))


    print(
        "DEBUG BIM PROJECT GEOMETRY:",
        bim_project.get("geometry")
    )


    assert (
        "geometry"
        in bim_project
    )


    print(
        "BIM project contract created"
    )



    # ======================================
    # STEP 4
    # FULL BIM
    # ======================================

    pipeline = FullBIMPipeline()

    bim_project["export_session"] = (
        "DESIGN_TO_BIM_REAL_GEOMETRY"
    )


    result = pipeline.run(
        bim_project
    )

    print("\n========== FULL BIM RESULT KEYS ==========")
    print(result.keys())


    print("\n========== FULL BIM RESULT ==========")
    print(result)


    assert result is not None


    assert (
        result.get("status")
        ==
        "completed"
    )


    # ======================================
    # ADAPTIVE STRUCTURAL CONTRACT
    # ======================================

    source_grid = bim_project.get(
        "structural_grid",
        {}
    )

    final_structure = result.get(
        "structure",
        {}
    )

    print(
        "\n====== ADAPTIVE STRUCTURAL CONTRACT ======"
    )

    print(
        "GRID TYPE:",
        source_grid.get(
            "grid_type"
        )
    )

    print(
        "SOURCE COLUMN COUNT:",
        len(
            source_grid.get(
                "columns",
                []
            )
        )
    )

    print(
        "SOURCE BEAM COUNT:",
        len(
            source_grid.get(
                "beams",
                []
            )
        )
    )

    print(
        "FINAL STRUCTURE KEYS:",
        final_structure.keys()
    )

    assert (
        source_grid.get(
            "grid_type"
        )
        ==
        "adaptive"
    )

    assert source_grid.get(
        "columns"
    )

    assert source_grid.get(
        "beams"
    )

    assert final_structure

    # --------------------------------------
    # COLUMN CONTRACT
    # --------------------------------------

    source_columns = {
        column.get("id"):
        column

        for column in source_grid.get(
            "columns",
            []
        )

        if column.get("id")
    }

    final_columns = final_structure.get(
        "columns",
        []
    )

    assert isinstance(
        final_columns,
        list
    )

    assert final_columns

    assert final_columns

    print(
        "\n====== STRUCTURAL COLUMN ID CONTRACT DEBUG ======"
    )

    print(
        "SOURCE COLUMN IDS:",
        list(
            source_columns.keys()
        )[:10]
    )

    print(
        "FINAL COLUMN COUNT:",
        len(
            final_columns
        )
    )

    for column in final_columns[:10]:

        print(
            {
                "id":
                    column.get(
                        "id"
                    ),

                "source_id":
                    column.get(
                        "source_id"
                    ),

                "x":
                    column.get(
                        "x"
                    ),

                "y":
                    column.get(
                        "y"
                    ),

                "level":
                    column.get(
                        "level"
                    ),

                "reference":
                    column.get(
                        "reference"
                    ),

                "width":
                    column.get(
                        "width"
                    ),

                "depth":
                    column.get(
                        "depth"
                    )
            }
        )

    print(
        "================================================="
    )


    print(
        "\n====== FINAL STRUCTURE COLUMN RAW DEBUG ======"
    )

    print(
        "SOURCE IDS:",
        list(
            source_columns.keys()
        )
    )

    print(
        "FINAL COLUMN SAMPLE:"
    )

    for column in final_columns[:8]:

        print(
            column
        )

    print(
        "=============================================="
    )

    matched_columns = 0

    for column in final_columns:

        source_id = column.get(
            "source_id"
        )

        source_column = source_columns.get(
            source_id
        )

        if not source_column:
            continue

        matched_columns += 1

        assert (
            column.get("x")
            ==
            source_column.get("x")
        )

        assert (
            column.get("y")
            ==
            source_column.get("y")
        )

        assert (
            column.get("width")
            ==
            source_column.get("width")
        )

        assert (
            column.get("depth")
            ==
            source_column.get("depth")
        )

        assert (
            column.get("reference")
            ==
            "corner"
        )

    assert matched_columns > 0

    # --------------------------------------
    # BEAM CONTRACT
    # --------------------------------------

    source_beams = {
        beam.get("id"):
        beam

        for beam in source_grid.get(
            "beams",
            []
        )

        if beam.get("id")
    }

    final_beams = final_structure.get(
        "beams",
        []
    )

    assert isinstance(
        final_beams,
        list
    )

    assert final_beams

    assert final_beams

    matched_beams = 0

    for beam in final_beams:

        source_id = beam.get(
            "source_id"
        )

        source_beam = source_beams.get(
            source_id
        )

        if not source_beam:
            continue

        matched_beams += 1

        assert (
            tuple(
                beam.get("start")
            )
            ==
            tuple(
                source_beam.get("start")
            )
        )

        assert (
            tuple(
                beam.get("end")
            )
            ==
            tuple(
                source_beam.get("end")
            )
        )

        assert (
            beam.get("orientation")
            ==
            source_beam.get(
                "orientation"
            )
        )

        assert (
            beam.get("width")
            ==
            source_beam.get("width")
        )

        assert (
            beam.get("depth")
            ==
            source_beam.get("depth")
        )

        assert (
            beam.get("reference")
            ==
            "corner"
        )

    assert matched_beams > 0

    # --------------------------------------
    # 3D LEVEL CONTRACT
    # --------------------------------------

    column_levels = set()

    for column in final_columns:

        level_name = column.get(
            "level"
        )

        assert level_name is not None

        column_levels.add(
            level_name
        )

        assert column.get(
            "z"
        ) is not None

        assert column.get(
            "height"
        ) is not None

        assert column.get(
            "top_z"
        ) is not None

        assert (
            column.get("top_z")
            ==
            column.get("z")
            +
            column.get("height")
        )

    beam_levels = set()

    for beam in final_beams:

        level_name = beam.get(
            "level"
        )

        assert level_name is not None

        beam_levels.add(
            level_name
        )

        assert beam.get(
            "z"
        ) is not None

        assert beam.get(
            "width"
        ) is not None

        assert beam.get(
            "depth"
        ) is not None

    print(
        "COLUMN LEVELS:",
        sorted(
            column_levels
        )
    )

    print(
        "BEAM LEVELS:",
        sorted(
            beam_levels
        )
    )

    assert column_levels

    assert beam_levels

    # ======================================
    # OPENING VALIDATION
    # ======================================

    bim_elements = result.get(
        "bim_elements",
        []
    )


    ifc_types = [

        element.get(
            "ifc_type"
        )

        for element in bim_elements

    ]


    print(
        "DEBUG IFC TYPES:",
        set(ifc_types)
    )


    assert (
        "IfcDoor"
        in ifc_types
    )


    assert (
        "IfcWindow"
        in ifc_types
    )


    print(
        "BIM pipeline validated"
    )


    print(
        "\nDESIGN → BIM REAL GEOMETRY FLOW PASSED"
    )