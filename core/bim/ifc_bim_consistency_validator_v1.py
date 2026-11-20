import ifcopenshell


class IFCBIMConsistencyValidatorV1:


    VERSION = "1.0"



    def __init__(self):

        print(
            "🧩 IFC BIM Consistency Validator v1.0 ACTIVE"
        )



    def validate(
        self,
        ifc_path
    ):


        model = ifcopenshell.open(
            ifc_path
        )



        elements = {

            "walls":
                model.by_type(
                    "IfcWall"
                ),

            "columns":
                model.by_type(
                    "IfcColumn"
                ),

            "beams":
                model.by_type(
                    "IfcBeam"
                ),

            "slabs":
                model.by_type(
                    "IfcSlab"
                ),

            "doors":
                model.by_type(
                    "IfcDoor"
                ),

            "windows":
                model.by_type(
                    "IfcWindow"
                )

        }



        inventory = {}

        for key, value in elements.items():

            inventory[key] = len(value)



        # ==========================================
        # GEOMETRY CONSISTENCY
        # ==========================================


        geometry_errors = []


        for category, items in elements.items():

            for element in items:


                if not element.Representation:


                    geometry_errors.append(

                        {
                            "element":
                                element.Name,

                            "issue":
                                "missing_geometry"

                        }

                    )



        # ==========================================
        # PLACEMENT CONSISTENCY
        # ==========================================


        placement_errors = []


        for category, items in elements.items():

            for element in items:


                if not element.ObjectPlacement:


                    placement_errors.append(

                        {
                            "element":
                                element.Name,

                            "issue":
                                "missing_placement"

                        }

                    )



        # ==========================================
        # STRUCTURE CHECK
        # ==========================================


        structural_present = (

            inventory["columns"] > 0
            and
            inventory["beams"] > 0

        )



        result = {


            "engine":
                "IFC_BIM_CONSISTENCY_VALIDATOR_V1",


            "version":
                self.VERSION,


            "file":
                ifc_path,


            "inventory":
                inventory,


            "checks":

                {


                    "geometry":
                        len(geometry_errors)
                        == 0,


                    "placement":
                        len(placement_errors)
                        == 0,


                    "structural_model":
                        structural_present

                },


            "errors":

                {

                    "geometry":
                        geometry_errors,


                    "placement":
                        placement_errors

                }

        }



        passed = (

            result["checks"]["geometry"]
            and
            result["checks"]["placement"]

        )



        if structural_present:

            result["bim_status"] = "complete"


        else:

            result["bim_status"] = "missing_structure"



        result["status"] = (

            "passed"
            if passed
            else
            "failed"

        )



        return result