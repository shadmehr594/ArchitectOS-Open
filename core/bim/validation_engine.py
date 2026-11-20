# ==========================================================
# BIM FINAL VALIDATION ENGINE v1.0
# ARCHITECTOS BIM v56 FINAL
# ==========================================================


class BIMValidationEngine:


    def __init__(self):

        print(
            "🔍 BIM Final Validation Engine v1.0 ACTIVE"
        )



    # ======================================================
    # MAIN VALIDATION
    # ======================================================

    def validate(
        self,
        package
    ):


        checks = {

            "manifest":
            self._check_manifest(package),


            "ifc":
            self._check_ifc(package),


            "dxf":
            self._check_dxf(package),


            "revit":
            self._check_revit(package),


            "intelligence":
            self._check_intelligence(package)

        }



        passed = all(
            checks.values()
        )



        return {


            "engine":
            "bim_validator_v1.0",


            "status":
            "validated"
            if passed
            else
            "failed",



            "checks":
            {

                key:
                "passed"
                if value
                else "failed"

                for key,value
                in checks.items()

            },



            "elements":
            self._count_elements(
                package
            ),



            "bim_closed":
            passed

        }



    # ======================================================
    # CHECKS
    # ======================================================


    def _check_manifest(
        self,
        package
    ):

        return (
            "project_manifest.json"
            in package.get(
                "files",
                []
            )
        )



    def _check_ifc(
        self,
        package
    ):

        return (
            "ifc/project_ifc.json"
            in package.get(
                "files",
                []
            )
        )



    def _check_dxf(
        self,
        package
    ):

        return (
            "dxf/layers.json"
            in package.get(
                "files",
                []
            )
        )



    def _check_revit(
        self,
        package
    ):

        return (
            "revit/family_mapping.json"
            in package.get(
                "files",
                []
            )
        )



    def _check_intelligence(
        self,
        package
    ):

        return (
            "intelligence/data.json"
            in package.get(
                "files",
                []
            )
        )



    # ======================================================
    # ELEMENT COUNT
    # ======================================================


    def _count_elements(
        self,
        package
    ):


        bim = package.get(
            "bim",
            {}
        )


        structure = bim.get(
            "structure",
            {}
        )



        return {


            "columns":
            len(
                structure.get(
                    "columns",
                    []
                )
            ),


            "beams":
            len(
                structure.get(
                    "beams",
                    []
                )
            ),


            "walls":
            len(
                bim.get(
                    "walls",
                    []
                )
            ),


            "openings":
            len(
                bim.get(
                    "openings",
                    []
                )
            )

        }