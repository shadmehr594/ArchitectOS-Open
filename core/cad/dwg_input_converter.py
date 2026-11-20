import os
import shutil
import subprocess
import tempfile


class DWGInputConverter:

    VERSION = "1.0"


    def __init__(self):

        print(
            f"DWG Input Converter v{self.VERSION} ACTIVE"
        )

        self.oda = self._find_oda_converter()


    # ==================================================
    # FIND ODA FILE CONVERTER
    # ==================================================

    def _find_oda_converter(self):

        candidates = [

            shutil.which(
                "ODAFileConverter"
            ),

            r"C:\Program Files\ODA\ODAFileConverter 27.1.0\ODAFileConverter.EXE"

        ]


        for path in candidates:

            if path and os.path.exists(path):

                return path


        return None


    # ==================================================
    # CONVERT DWG -> DXF
    # ==================================================

    def convert(
        self,
        dwg_file,
        output_dxf
    ):

        dwg_file = os.path.abspath(
            dwg_file
        )

        output_dxf = os.path.abspath(
            output_dxf
        )


        if not os.path.exists(
            dwg_file
        ):

            return {

                "status":
                    "failed",

                "error":
                    f"DWG not found: {dwg_file}"

            }


        if not self.oda:

            return {

                "status":
                    "failed",

                "error":
                    "ODA File Converter not found"

            }


        output_folder = os.path.dirname(
            output_dxf
        )

        os.makedirs(
            output_folder,
            exist_ok=True
        )


        # ODA works directory-to-directory.
        # Use isolated temporary folders so unrelated
        # DWG files cannot be converted accidentally.

        with tempfile.TemporaryDirectory() as temp_root:

            input_folder = os.path.join(
                temp_root,
                "input"
            )

            converted_folder = os.path.join(
                temp_root,
                "output"
            )

            os.makedirs(
                input_folder,
                exist_ok=True
            )

            os.makedirs(
                converted_folder,
                exist_ok=True
            )


            source_name = os.path.basename(
                dwg_file
            )

            temp_dwg = os.path.join(
                input_folder,
                source_name
            )


            shutil.copy2(
                dwg_file,
                temp_dwg
            )


            try:

                subprocess.run(

                    [

                        self.oda,

                        input_folder,

                        converted_folder,

                        "ACAD2018",

                        "DXF",

                        "0",

                        "1",

                        "*.dwg"

                    ],

                    check=True

                )


            except subprocess.CalledProcessError as e:

                return {

                    "status":
                        "failed",

                    "error":
                        f"ODA conversion failed with code {e.returncode}"

                }


            expected_name = (
                os.path.splitext(
                    source_name
                )[0]
                +
                ".dxf"
            )

            generated_dxf = os.path.join(
                converted_folder,
                expected_name
            )


            if not os.path.exists(
                generated_dxf
            ):

                dxf_files = [

                    name

                    for name in os.listdir(
                        converted_folder
                    )

                    if name.lower().endswith(
                        ".dxf"
                    )

                ]


                if len(dxf_files) != 1:

                    return {

                        "status":
                            "failed",

                        "error":
                            "Converted DXF file not found",

                        "files":
                            dxf_files

                    }


                generated_dxf = os.path.join(
                    converted_folder,
                    dxf_files[0]
                )


            shutil.copy2(
                generated_dxf,
                output_dxf
            )


        if not os.path.exists(
            output_dxf
        ):

            return {

                "status":
                    "failed",

                "error":
                    "DXF output missing after conversion"

            }


        return {

            "status":
                "converted",

            "engine":
                "ODA File Converter",

            "source":
                "DWG",

            "target":
                "DXF",

            "file":
                output_dxf,

            "size":
                os.path.getsize(
                    output_dxf
                )

        }