from core.cad.cad_import_engine import CADImportEngine


def test_site_to_design_intent():

    print("\n=== SITE TO DESIGN INTENT TEST ===\n")


    # -----------------------------------
    # 1) LOAD CAD
    # -----------------------------------

    engine = CADImportEngine()

    result = engine.load(
        {
            "file_object":
                r"tests\data\site_polygon_test.dxf"
        }
    )


    assert result["parcel"]["status"] == "ready"


    print("✓ Parcel extracted")



    # -----------------------------------
    # 2) SITE INTELLIGENCE
    # -----------------------------------

    site = result["site_intelligence"]


    assert site["status"] == "ready"


    print("✓ Site Intelligence ready")


    print(
        "Site ID:",
        site["site_id"]
    )


    print(
        "Area:",
        site["area"]
    )


    print(
        "Boundary:",
        site["boundary"]
    )



    # -----------------------------------
    # 3) CONSTRAINTS
    # -----------------------------------

    constraints = result["constraints"]


    assert constraints["status"] == "ready"


    print("✓ Constraints generated")


    print(
        "Access:",
        constraints["constraints"]["access"]
    )


    print(
        "North:",
        constraints["constraints"]["north"]
    )



    # -----------------------------------
    # 4) DESIGN INTENT INPUT CONTRACT
    # -----------------------------------

    design_context = {


        "site":

            site,


        "constraints":

            constraints,


        "request":

            {

                "type":
                    "residential",

                "style":
                    "modern"

            }

    }



    assert "site" in design_context

    assert "constraints" in design_context


    print(
        "✓ Design Intent Context created"
    )


    print("\n=== TEST PASSED ===\n")



if __name__ == "__main__":

    test_site_to_design_intent()