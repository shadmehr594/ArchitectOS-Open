import os
import json
from datetime import datetime

from core.export.revit_type_material_mapper import (
    RevitTypeMaterialMapper
)



class RevitPackageGenerator:


    VERSION = "1.3"



    def __init__(self):

        print(
            f"🏢 Revit Package Generator v{self.VERSION} ACTIVE"
        )



    # ==========================================
    # BUILD PACKAGE
    # ==========================================

    def build(
        self,
        runtime_result,
        output_dir="architectos_revit_package"
    ):


        os.makedirs(
            output_dir,
            exist_ok=True
        )



        # ===============================
        # INPUT DATA
        # ===============================


        bim = runtime_result.get(
            "bim",
            {}
        )


        elements = runtime_result.get(
            "bim_elements",
            []
        )



        families = (

            runtime_result.get(
                "revit_families",
                {}
            )

            or

            bim.get(
                "revit_mapping",
                {}
            )

        )



        if not families:

            families = bim.get(
                "revit_mapping",
                {}
            )



        levels = runtime_result.get(
            "spatial",
            {}
        )


        if "nodes" in levels:

            levels = {
                "LEVEL_0": levels
            }



        # ===============================
        # TYPE + MATERIAL MAPPING
        # ===============================


        mapper = RevitTypeMaterialMapper()


        type_materials = mapper.map(
            elements
        )



        # ===============================
        # PACKAGE MANIFEST
        # ===============================


        package = {


            "engine":

                f"revit_package_generator_v{self.VERSION}",



            "created":

                datetime.now().isoformat(),



            "status":

                "generated",



            "files":[

                "elements.json",

                "families.json",

                "types.json",

                "levels.json",

                "revit_manifest.json"

            ],



            "statistics":{


                "total_elements":

                    len(
                        elements
                    ),



                "families":

                    len(
                        families
                    )
                    if isinstance(
                        families,
                        dict
                    )
                    else 0,



                "types":

                    len(
                        type_materials.get(
                            "elements",
                            {}
                        )
                    )

            },



            "elements":

                elements,



            "families":

                families,



            "type_materials":

                type_materials,



            "levels":

                levels


        }



        # ===============================
        # WRITE FILES
        # ===============================


        self._write(

            output_dir,

            "elements.json",

            elements

        )



        self._write(

            output_dir,

            "families.json",

            families

        )



        self._write(

            output_dir,

            "types.json",

            type_materials

        )



        self._write(

            output_dir,

            "levels.json",

            levels

        )



        self._write(

            output_dir,

            "revit_manifest.json",

            package

        )



        return package




    # ==========================================
    # WRITE JSON
    # ==========================================


    def _write(
        self,
        root,
        filename,
        data
    ):


        path = os.path.join(

            root,

            filename

        )



        with open(

            path,

            "w",

            encoding="utf-8"

        ) as f:


            json.dump(

                data,

                f,

                indent=4,

                ensure_ascii=False

            )