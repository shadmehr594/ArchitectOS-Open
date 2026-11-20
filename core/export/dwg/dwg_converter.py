import os
import shutil
import subprocess
import tempfile


class DWGConverter:

    VERSION = "2.3"


    def __init__(self):

        print(
            f"🔄 DWG Converter v{self.VERSION} ACTIVE"
        )

        self.accore = self._find_accoreconsole()

        self.oda = self._find_oda_converter()

    def _find_oda_converter(self):
        discovered = shutil.which("ODAFileConverter")
        if discovered:
            return discovered
        candidates = [
            r"C:\Program Files\ODA\ODAFileConverter 27.1.0\ODAFileConverter.exe",
            r"C:\Program Files\ODA\ODAFileConverter\ODAFileConverter.exe",
        ]
        for path in candidates:
            if os.path.exists(path):
                return path
        return None



    # ==========================================
    # FIND AUTOCAD CORE CONSOLE
    # ==========================================

    def _find_accoreconsole(self):

        candidates = [

            r"C:\Program Files\Autodesk\AutoCAD 2025\accoreconsole.exe",
            r"C:\Program Files\Autodesk\AutoCAD 2024\accoreconsole.exe",
            r"C:\Program Files\Autodesk\AutoCAD 2023\accoreconsole.exe"

        ]


        for path in candidates:

            if os.path.exists(path):

                return path


        return None



    # ==========================================
    # CREATE AUTOCAD SCRIPT
    # ==========================================

    def _create_autocad_script(
        self,
        output
    ):

        output = os.path.abspath(
            output
        )


        script = (
            "_.SAVEAS\n"
            "2018\n"
            f'"{output}"\n'
            "\n"
        )


        fd, path = tempfile.mkstemp(
            suffix=".scr",
            text=True
        )


        with os.fdopen(
            fd,
            "w"
        ) as f:

            f.write(script)


        return path



    # ==========================================
    # VALIDATE DWG
    # ==========================================

    def _validate_dwg(
        self,
        output
    ):

        if not os.path.exists(output):

            return {

                "validated":
                    False,

                "error":
                    "DWG file missing"

            }


        size = os.path.getsize(
            output
        )


        if size < 100:

            return {

                "validated":
                    False,

                "error":
                    "DWG file size invalid"

            }


        return {

            "validated":
                True,

            "size":
                size

        }



    # ==========================================
    # AUTOCAD CONVERSION
    # ==========================================

    def _convert_with_autocad(
        self,
        dxf_file,
        output
    ):


        dxf_file = os.path.abspath(
            dxf_file
        )


        output = os.path.abspath(
            output
        )


        if os.path.exists(output):

            os.remove(
                output
            )


        script = self._create_autocad_script(
            output
        )


        try:

            subprocess.run(
                [
                    self.accore,
                    "/i",
                    dxf_file,
                    "/s",
                    script
                ],
                check=True,
                timeout=10800
            )


            validation = self._validate_dwg(
                output
            )


            if validation["validated"]:

                return {

                    "status":
                        "converted",

                    "engine":
                        "AutoCAD Core Console",

                    "source":
                        "DXF",

                    "target":
                        "DWG",

                    "version":
                        "2018",

                    "validated":
                        True,

                    "size":
                        validation["size"],

                    "file":
                        output,

                    "format":
                        "DWG"

                }


            return {

                "status":
                    "failed",

                "error":
                    validation["error"]

            }



        finally:

            if os.path.exists(script):

                os.remove(
                    script
                )



    # ==========================================
    # ODA CONVERSION
    # ==========================================

    def _convert_with_oda(
        self,
        dxf_file,
        output
    ):


        dxf_file = os.path.abspath(
            dxf_file
        )


        output = os.path.abspath(
            output
        )


        subprocess.run(

            [

                self.oda,

                os.path.dirname(dxf_file),

                os.path.dirname(output),

                "ACAD2018",

                "DWG",

                "0",

                "1",

                "*.dxf"

            ],

            check=True

        )

        generated_output = os.path.join(
            os.path.dirname(dxf_file),
            os.path.splitext(os.path.basename(dxf_file))[0] + ".dwg"
        )
        if (
            os.path.abspath(generated_output) != os.path.abspath(output)
            and os.path.exists(generated_output)
        ):
            if os.path.exists(output):
                os.remove(output)
            shutil.move(generated_output, output)


        validation = self._validate_dwg(
            output
        )


        if validation["validated"]:

            return {

                "status":
                    "converted",

                "engine":
                    "ODA File Converter",

                "source":
                    "DXF",

                "target":
                    "DWG",

                "version":
                    "2018",

                "validated":
                    True,

                "size":
                    validation["size"],

                "file":
                    output,

                "format":
                    "DWG"

            }


        return {

            "status":
                "failed",

            "error":
                validation["error"]

        }



    # ==========================================
    # MAIN CONVERTER
    # ==========================================

    def convert(
        self,
        dxf_file,
        output
    ):


        if not os.path.exists(dxf_file):

            return {

                "status":
                    "failed",

                "error":
                    f"DXF not found: {dxf_file}"

            }



        folder = os.path.dirname(
            os.path.abspath(output)
        )


        os.makedirs(
            folder,
            exist_ok=True
        )



        try:


            # Priority 1
            # AutoCAD Core Console

            if self.accore:
                try:
                    autocad_result = self._convert_with_autocad(dxf_file, output)
                    if autocad_result.get("status") == "converted":
                        return autocad_result
                except Exception:
                    if not self.oda:
                        raise



            # Priority 2
            # ODA

            if self.oda:

                return self._convert_with_oda(
                    dxf_file,
                    output
                )



            return {

                "status":
                    "pending",

                "message":
                    "No DWG conversion engine installed",

                "dxf":
                    dxf_file

            }



        except subprocess.CalledProcessError as e:


            return {

                "status":
                    "failed",

                "error":
                    f"Converter exited with code {e.returncode}"

            }



        except Exception as e:


            return {

                "status":
                    "failed",

                "error":
                    str(e)

            }
