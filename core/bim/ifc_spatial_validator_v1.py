# ==========================================================
# IFC SPATIAL VALIDATOR V1
# ARCHITECTOS BIM SPATIAL STRUCTURE CHECK
# ==========================================================


import ifcopenshell



class IFCSpatialValidatorV1:


    VERSION = "1.0"



    def __init__(self):

        print(
            "🏗 IFC Spatial Validator v1.0 ACTIVE"
        )



    # ======================================================
    # VALIDATE IFC SPATIAL STRUCTURE
    # ======================================================


    def validate(
        self,
        ifc_path
    ):


        result = {


            "engine":
                "IFC_SPATIAL_VALIDATOR_V1",


            "version":
                self.VERSION,


            "file":
                ifc_path,


            "checks": {},


            "errors": []

        }



        model = ifcopenshell.open(
            ifc_path
        )



        errors = result["errors"]



        # ==============================================
        # PROJECT
        # ==============================================


        project_exists = (

            len(
                model.by_type(
                    "IfcProject"
                )
            )
            >
            0

        )


        result["checks"]["project"] = project_exists



        if not project_exists:

            errors.append(
                {
                    "issue":
                        "missing_project"
                }
            )



        # ==============================================
        # SITE
        # ==============================================


        site_exists = (

            len(
                model.by_type(
                    "IfcSite"
                )
            )
            >
            0

        )


        result["checks"]["site"] = site_exists



        if not site_exists:

            errors.append(
                {
                    "issue":
                        "missing_site"
                }
            )



        # ==============================================
        # BUILDING
        # ==============================================


        building_exists = (

            len(
                model.by_type(
                    "IfcBuilding"
                )
            )
            >
            0

        )


        result["checks"]["building"] = building_exists



        if not building_exists:

            errors.append(
                {
                    "issue":
                        "missing_building"
                }
            )



        # ==============================================
        # STOREYS
        # ==============================================


        storeys = model.by_type(
            "IfcBuildingStorey"
        )


        storeys_valid = (

            len(storeys)
            >
            0

        )


        result["checks"]["storeys"] = storeys_valid



        if not storeys_valid:

            errors.append(
                {
                    "issue":
                        "missing_storeys"
                }
            )



        # ==============================================
        # ELEMENT ASSIGNMENT
        # ==============================================


        orphan_elements = []



        elements = (

            model.by_type("IfcWall")

            +

            model.by_type("IfcColumn")

            +

            model.by_type("IfcBeam")

            +

            model.by_type("IfcSlab")

            +

            model.by_type("IfcDoor")

            +

            model.by_type("IfcWindow")

        )



        for element in elements:


            assigned = False



            for rel in model.by_type(
                "IfcRelContainedInSpatialStructure"
            ):


                if element in rel.RelatedElements:

                    assigned = True

                    break



            if not assigned:

                orphan_elements.append(

                    {

                        "element":
                            element.Name,

                        "issue":
                            "not_assigned_to_storey"

                    }

                )



        result["checks"]["assignments"] = (

            len(orphan_elements)
            ==
            0

        )


        if orphan_elements:

            errors.extend(
                orphan_elements
            )



        # ==============================================
        # SCORE
        # ==============================================


        checks = result["checks"]


        score = int(

            (

                sum(checks.values())

                /

                len(checks)

            )

            *

            100

        )



        result["spatial_health"] = {


            "score":
                score,


            "project":
                "passed"
                if checks["project"]
                else
                "failed",


            "site":
                "passed"
                if checks["site"]
                else
                "failed",


            "building":
                "passed"
                if checks["building"]
                else
                "failed",


            "storeys":
                "passed"
                if checks["storeys"]
                else
                "failed",


            "assignments":
                "passed"
                if checks["assignments"]
                else
                "failed"

        }



        result["status"] = (

            "passed"

            if not errors

            else

            "failed"

        )



        return result