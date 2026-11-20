# ==========================================================
# IFC QUALITY VALIDATOR V2
# ARCHITECTOS BIM IFC HEALTH CHECK
# ==========================================================


import os


try:

    import ifcopenshell


except Exception:

    ifcopenshell = None



class IFCQualityValidatorV2:


    VERSION = "2.2"



    def __init__(self):

        print(
            "🔍 IFC Quality Validator v2.0 ACTIVE"
        )



    # ======================================================
    # MAIN VALIDATION
    # ======================================================


    def validate(
        self,
        ifc_path
    ):


        checks = {}


        result = {


            "engine":
                "IFC_QUALITY_VALIDATOR_V2",


            "version":
                self.VERSION,


            "file":
                ifc_path,


            "checks":
                checks

        }



        # ==============================================
        # FILE CHECK
        # ==============================================


        file_exists = (

            os.path.exists(
                ifc_path
            )

        )


        checks["file_exists"] = file_exists



        if not file_exists:

            result["status"] = "failed"

            return result



        # ==============================================
        # IFC REOPEN
        # ==============================================


        if ifcopenshell is None:

            checks["ifcopenshell"] = False

            result["status"] = "failed"

            return result



        try:

            model = ifcopenshell.open(
                ifc_path
            )


            checks["reopen"] = True



        except Exception as e:


            checks["reopen"] = False


            result["error"] = str(e)


            result["status"] = "failed"


            return result



        # ==============================================
        # IFC CORE ENTITIES
        # ==============================================


        checks["IfcProject"] = (

            len(
                model.by_type(
                    "IfcProject"
                )
            ) > 0

        )


        checks["IfcContext"] = (

            len(
                model.by_type(
                    "IfcGeometricRepresentationContext"
                )
            ) > 0

        )


        checks["IfcBuilding"] = (

            len(
                model.by_type(
                    "IfcBuilding"
                )
            ) > 0

        )


        # ==============================================
        # GEOMETRY QUALITY CHECK V2.1
        # ==============================================


        geometry_errors = []


        geometry_types = [

            "IfcWall",

            "IfcColumn",

            "IfcBeam",

            "IfcSlab",

            "IfcDoor",

            "IfcWindow",

            "IfcRoof"

        ]


        for geometry_type in geometry_types:


            for element in model.by_type(
                geometry_type
            ):


                if (
                    not element.Representation
                    or
                    not element.Representation.Representations
                ):


                    geometry_errors.append(

                        {

                            "element": element.Name,

                            "ifc_class": geometry_type,

                            "issue": "missing_representation"

                        }

                    )



        checks["geometry_representation"] = (

            len(geometry_errors)
            ==
            0

        )


        result["geometry_errors"] = geometry_errors


        # ==============================================
        # PLACEMENT QUALITY CHECK V2.1
        # ==============================================


        placement_errors = []


        for element in (

            model.by_type("IfcWall")
            +
            model.by_type("IfcColumn")
            +
            model.by_type("IfcBeam")
            +
            model.by_type("IfcSlab")

        ):


            if not element.ObjectPlacement:


                placement_errors.append(

                    {

                        "element": element.Name,

                        "issue": "missing_object_placement"

                    }

                )



        checks["placement"] = (

            len(placement_errors)
            ==
            0

        )


        result["placement_errors"] = placement_errors


        # ==============================================
        # PLACEMENT CHAIN VALIDATION V2.2
        # ==============================================

        placement_chain_errors = []


        for element in (
            model.by_type("IfcWall")
            +
            model.by_type("IfcColumn")
            +
            model.by_type("IfcBeam")
            +
            model.by_type("IfcSlab")
        ):

            placement = element.ObjectPlacement


            if not placement:
                continue


            if not placement.RelativePlacement:

                placement_chain_errors.append(
                    {
                        "element": element.Name,
                        "issue": "missing_relative_placement"
                    }
                )


        checks["placement_chain"] = (
            len(placement_chain_errors) == 0
        )


        result["placement_chain_errors"] = (
            placement_chain_errors
        )



        # ==============================================
        # GEOMETRY CONTENT VALIDATION V2.2
        # ==============================================

        geometry_content_errors = []


        for element_type in geometry_types:

            for element in model.by_type(element_type):

                if not element.Representation:
                    continue


                representations = (
                    element.Representation.Representations
                )


                if not representations:

                    geometry_content_errors.append(
                        {
                            "element": element.Name,
                            "issue": "empty_representation"
                        }
                    )

                    continue


                for representation in representations:

                    if not representation.Items:

                        geometry_content_errors.append(
                            {
                                "element": element.Name,
                                "issue": "empty_shape_items"
                            }
                        )


        checks["geometry_content"] = (
            len(geometry_content_errors) == 0
        )


        result["geometry_content_errors"] = (
            geometry_content_errors
        )



        # ==============================================
        # MODEL STATISTICS
        # ==============================================


        result["statistics"] = {


            "storeys":
                len(
                    model.by_type(
                        "IfcBuildingStorey"
                    )
                ),


            "walls":
                len(
                    model.by_type(
                        "IfcWall"
                    )
                ),


            "columns":
                len(
                    model.by_type(
                        "IfcColumn"
                    )
                ),


            "beams":
                len(
                    model.by_type(
                        "IfcBeam"
                    )
                ),


            "slabs":
                len(
                    model.by_type(
                        "IfcSlab"
                    )
                ),


            "doors":
                len(
                    model.by_type(
                        "IfcDoor"
                    )
                ),


            "windows":
                len(
                    model.by_type(
                        "IfcWindow"
                    )
                )

        }



        # ==============================================
        # FINAL STATUS
        # ==============================================


        passed = all(
            checks.values()
        )


        score = (
            int(
                (
                    sum(checks.values())
                    /
                    len(checks)
                )
                *
                100
            )
        )


        result["health"] = {

            "score": score,

            "geometry":
                "passed"
                if checks.get("geometry_representation")
                else
                "failed",

            "placement":
                "passed"
                if checks.get("placement")
                else
                "failed",

            "geometry_content":
                "passed"
                if checks.get("geometry_content")
                else
                "failed",

            "placement_chain":
                "passed"
                if checks.get("placement_chain")
                else
                "failed"
        }


        result["status"] = (

            "passed"
            if passed
            else
            "failed"

        )


        return result