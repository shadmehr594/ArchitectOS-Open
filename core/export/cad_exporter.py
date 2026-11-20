import os

from core.export.dwg.dwg_writer import (
    DWGWriter
)


class CADExporter:

    VERSION = "44.1"


    def __init__(
        self,
        scale=100
    ):

        self.scale = scale

        self.dwg = DWGWriter()

        print(
            f"📐 CAD Exporter v{self.VERSION} ACTIVE"
        )


    # ======================
    # MAIN EXPORT FUNCTION
    # ======================

    def export(
        self,
        spatial_data,
        geometry=None,
        structure=None,
        output="exports/ArchitectOS_Project.dxf"
    ):

        print("\n====== CAD FILE TRACE ======")
        print("FINAL OUTPUT PATH:")
        print(output)
        print("ABS PATH:")
        print(os.path.abspath(output))
        print("============================")

        print("\n====== CAD EXPORT SESSION ======")
        print("OUTPUT FILE:", output)
        print("GEOMETRY OBJECT ID:", id(geometry))

        if geometry:

            print(
                "GEOMETRY KEYS:",
                geometry.keys()
            )

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

        else:

            print(
                "GEOMETRY IS EMPTY"
            )


        print(
            "================================"
        )


        print("\n====== CAD EXPORTER INPUT DEBUG ======")

        print(
            "GEOMETRY TYPE:",
            type(geometry)
        )


        if geometry:

            print(
                "GEOMETRY KEYS:",
                geometry.keys()
            )

            print(
                "WALL COUNT INPUT:",
                len(
                    geometry.get(
                        "walls",
                        []
                    )
                )
            )

            print(
                "ROOM COUNT INPUT:",
                len(
                    geometry.get(
                        "rooms",
                        []
                    )
                )
            )


        print(
            "======================================"
        )

        print("\n====== REAL CAD GEOMETRY TRACE ======")

        for key in [
            "walls",
            "doors",
            "windows",
            "rooms",
            "floors"
        ]:

            items = geometry.get(key, [])

            print(
                key.upper(),
                "COUNT:",
                len(items)
            )


        if geometry.get("walls"):
            print(
                "FIRST WALL:",
                geometry["walls"][0]
            )


        if geometry.get("doors"):
            print(
                "FIRST DOOR:",
                geometry["doors"][0]
            )


        if geometry.get("windows"):
            print(
                "FIRST WINDOW:",
                geometry["windows"][0]
            )


        print("====================================")


        nodes = spatial_data.get(
            "nodes",
            {}
        )


        layers = {

            "WALLS": [],
            "DOORS": [],
            "TEXT": []

        }


        # ======================
        # SPATIAL FALLBACK WALLS
        # ======================

        for name, n in nodes.items():


            x = n["x"] * self.scale
            y = n["y"] * self.scale
            w = n["w"] * self.scale
            h = n["h"] * self.scale


            walls = [

                ((x,y),(x+w,y)),

                ((x+w,y),(x+w,y+h)),

                ((x+w,y+h),(x,y+h)),

                ((x,y+h),(x,y))

            ]


            for w1,w2 in walls:

                layers["WALLS"].append({

                    "type":"LINE",
                    "start":w1,
                    "end":w2

                })


            layers["TEXT"].append({

                "type":"TEXT",

                "position":(
                    x+5,
                    y+5
                ),

                "value":name

            })


        cad_result = {

            "version":
                "R14-like",

            "layers":
                layers,

            "meta":{

                "unit_scale":
                    self.scale,

                "format":
                    f"CAD_EXPORT_ENGINE_v{self.VERSION}"

            }

        }


        # ======================
        # REAL DXF WRITE
        # ======================

        if geometry is not None:


            print(
                "\n====== DWG EXPORT CLEAN CHECK ======"
            )


            print(
                "OUTPUT:",
                output
            )


            print(
                "LAYERS BEFORE WRITE:",
                {
                    k: len(v)
                    for k,v in layers.items()
                }
            )


            print(
                "GEOMETRY PASSED TO DWG:"
            )


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
                "===================================="
            )


            dxf_result = self.dwg.export(

                geometry,

                structure or {},

                output=output

            )


            cad_result["file"] = dxf_result


        return cad_result