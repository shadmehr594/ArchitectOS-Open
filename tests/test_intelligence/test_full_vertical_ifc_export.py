import os
import ifcopenshell


from core.export.ifc_export_engine import (
    IFCExportEngine
)



def test_full_vertical_ifc_export():

    print(
        "\n🔗 FULL VERTICAL IFC EXPORT v1.0 ACTIVE"
    )


    # ======================================
    # MOCK VERTICAL BIM ELEMENTS
    # ======================================

    bim_model = {

        "bim_elements":

        [

            {

                "id":
                    "stair_001",

                "name":
                    "Main Escape Stair",

                "ifc_type":
                    "IfcStair",

                "level":
                    "F1",

                "geometry":

                [

                    [0, 10],
                    [4, 14]

                ],

                "properties":

                {

                    "Function":
                        "Escape Route"

                }

            },


            {

                "id":
                    "escalator_001",

                "name":
                    "Shopping Escalator",

                "ifc_type":
                    "IfcTransportElement",

                "level":
                    "F1",

                "geometry":

                [

                    [5, 5],
                    [11.4, 6]

                ],

                "properties":

                {

                    "System":
                        "escalator"

                }

            },


            {

                "id":
                    "elevator_core_001",

                "name":
                    "Elevator Core",

                "ifc_type":
                    "IfcBuildingElementProxy",

                "level":
                    "F1",

                "geometry":

                [

                    [10, 10],
                    [14, 14]

                ],

                "properties":

                {

                    "Function":
                        "Vertical Accessibility"

                }

            }

        ]

    }



    print(
        "\nINPUT VERTICAL ELEMENTS:"
    )


    for e in bim_model["bim_elements"]:

        print(
            e["ifc_type"]
        )



    # ======================================
    # IFC EXPORT
    # ======================================

    exporter = IFCExportEngine()


    result = exporter.export(
        bim_model
    )


    assert result["real_ifc"] is True


    ifc_path = result["path"]


    assert os.path.exists(
        ifc_path
    )


    print(
        "\nIFC FILE:",
        ifc_path
    )



    # ======================================
    # IFC VERIFY
    # ======================================

    model = ifcopenshell.open(
        ifc_path
    )


    stairs = model.by_type(
        "IfcStair"
    )


    transports = model.by_type(
        "IfcTransportElement"
    )


    proxies = model.by_type(
        "IfcBuildingElementProxy"
    )


    print(
        "\n===== IFC VERTICAL CHECK ====="
    )


    print(
        "STAIRS:",
        len(stairs)
    )


    print(
        "TRANSPORT:",
        len(transports)
    )


    print(
        "VERTICAL CORE:",
        len(proxies)
    )



    assert len(stairs) == 1

    assert len(transports) == 1

    assert len(proxies) == 1



    print(
        "\n✅ FULL VERTICAL IFC EXPORT PASSED"
    )



if __name__ == "__main__":

    test_full_vertical_ifc_export()