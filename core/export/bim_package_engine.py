import os
import json
from datetime import datetime


class BIMPackageEngine:


    def __init__(self):

        print(
            "📦 BIM Package Engine v1.0 ACTIVE"
        )


    def build(
        self,
        runtime_result,
        output_dir="output"
    ):


        os.makedirs(
            output_dir,
            exist_ok=True
        )


        bim = runtime_result.get(
            "bim",
            {}
        )


        intelligence = runtime_result.get(
            "intelligence",
            {}
        )


        package = {


            "engine":
            "bim_package_engine_v1.0",


            "created":
            datetime.now().isoformat(),


            "status":
            "generated",


            "files":
            [

                "project_manifest.json",

                "ifc/project_ifc.json",

                "dxf/layers.json",

                "revit/family_mapping.json",

                "intelligence/data.json"

            ]

        }



        self._write(
            output_dir,
            "project_manifest.json",
            package
        )


        self._write(
            output_dir,
            "ifc/project_ifc.json",
            bim.get(
                "ifc",
                {}
            )
        )


        self._write(
            output_dir,
            "dxf/layers.json",
            bim.get(
                "dxf",
                {}
            )
        )


        self._write(
            output_dir,
            "revit/family_mapping.json",
            bim.get(
                "revit_mapping",
                {}
            )
        )


        self._write(
            output_dir,
            "intelligence/data.json",
            intelligence
        )


        return package



    def _write(
        self,
        root,
        path,
        data
    ):


        full_path = os.path.join(
            root,
            path
        )


        folder = os.path.dirname(
            full_path
        )


        os.makedirs(
            folder,
            exist_ok=True
        )


        with open(
            full_path,
            "w",
            encoding="utf-8"
        ) as file:


            json.dump(
                data,
                file,
                indent=4,
                ensure_ascii=False
            )