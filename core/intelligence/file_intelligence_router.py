# ==================================================
# ArchitectOS File Intelligence Router v1.0
# File Input -> CAD / BIM / Document Context
# ==================================================


import os


class FileIntelligenceRouter:

    VERSION = "1.0"


    def __init__(self):

        print(
            f"📁 File Intelligence Router v{self.VERSION} ACTIVE"
        )


    # ==================================================
    # MAIN ENTRY
    # ==================================================

    def process(
        self,
        file_path,
        file_data=None
    ):

        extension = self._extension(
            file_path
        )


        if extension in [
            ".dxf",
            ".dwg"
        ]:

            if file_data is None:

                file_data = {

                    "file_object":
                        file_path

                }


            return self._process_cad(
                file_data,
                extension
            )


        elif extension == ".ifc":

            return self._process_ifc(
                file_data,
                extension
            )


        elif extension == ".rvt":

            return self._process_rvt(
                file_data,
                extension
            )


        elif extension == ".pdf":

            return {

                "source":
                "file",


                "type":
                "document",


                "extension":
                extension,


                "status":
                "document_context",


                "context":
                {}

            }


        return {

            "source":
            "file",


            "type":
            "unknown",


            "extension":
            extension,


            "status":
            "unsupported",


            "context":
            {}

        }



    # ==================================================
    # CAD HANDLER
    # ==================================================

    def _process_cad(
        self,
        file_data,
        extension
    ):


        from core.cad.cad_import_engine import (
            CADImportEngine
        )

        print("\n====== CAD ROUTER INPUT DEBUG ======")

        print(
            "FILE DATA:",
            file_data
        )

        print(
            "FILE OBJECT:",
            file_data.get("file_object")
            if isinstance(file_data, dict)
            else None
        )

        print(
            "EXTENSION:",
            extension
        )

        print(
            "===================================="
        )


        engine = CADImportEngine()


        result = engine.load(
            file_data or {}
        )

        print(
            "\n====== CAD IMPORT RESULT DEBUG ======"
        )

        print(type(result))

        print(result)

        print(
            "====================================="
        )


        return {

            "source":
            "file",


            "type":
            "cad",


            "extension":
            extension,


            "status":
            "completed",


            "context":
            result

        }



    # ==================================================
    # IFC HANDLER
    # ==================================================

    def _process_ifc(
        self,
        file_data,
        extension
    ):


        from core.ifc.ifc_import_adapter import (
            IFCImportAdapter
        )


        adapter = IFCImportAdapter()


        result = adapter.load(
            file_data or {}
        )


        return {

            "source":
            "file",


            "type":
            "ifc",


            "extension":
            extension,


            "status":
            "completed",


            "context":
            result

        }



    # ==================================================
    # RVT HANDLER
    # ==================================================

    def _process_rvt(
        self,
        file_data,
        extension
    ):


        from core.bim.rvt_import_adapter import (
            RVTImportAdapter
        )


        adapter = RVTImportAdapter()


        result = adapter.load(
            file_data or {}
        )


        return {

            "source":
            "file",


            "type":
            "rvt",


            "extension":
            extension,


            "status":
            "completed",


            "context":
            result

        }



    # ==================================================
    # UTILS
    # ==================================================

    def _extension(
        self,
        file_path
    ):

        if not file_path:

            return ""


        return os.path.splitext(
            file_path
        )[1].lower()