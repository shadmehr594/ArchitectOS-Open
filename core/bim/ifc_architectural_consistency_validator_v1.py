import ifcopenshell



class IFCArchitecturalConsistencyValidatorV1:


    VERSION = "1.0"



    def __init__(self):

        print(
            "🏛 IFC Architectural Consistency Validator v1.0 ACTIVE"
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


            "doors":
                model.by_type(
                    "IfcDoor"
                ),


            "windows":
                model.by_type(
                    "IfcWindow"
                ),


            "storeys":
                model.by_type(
                    "IfcBuildingStorey"
                )

        }



        inventory = {}


        for key, value in elements.items():

            inventory[key] = len(value)



        geometry_errors = []

        placement_errors = []

        naming_errors = []



        # ==========================================
        # GEOMETRY
        # ==========================================


        geometry_categories = [

            "walls",

            "doors",

            "windows"

        ]


        for category in geometry_categories:

            for element in elements[category]:


                if not element.Representation:


                    geometry_errors.append(

                        {

                            "element":
                                element.Name,

                            "category":
                                category,

                            "issue":
                                "missing_geometry"

                        }

                    )



        # ==========================================
        # PLACEMENT
        # ==========================================


        for category, items in elements.items():

            for element in items:


                if not element.ObjectPlacement:


                    placement_errors.append(

                        {

                            "element":
                                element.Name,

                            "category":
                                category,

                            "issue":
                                "missing_placement"

                        }

                    )



        # ==========================================
        # NAME CHECK
        # ==========================================


        for category, items in elements.items():

            for element in items:


                if not element.Name:


                    naming_errors.append(

                        {

                            "category":
                                category,

                            "issue":
                                "missing_name"

                        }

                    )



        checks = {


            "geometry":
                len(geometry_errors)
                == 0,


            "placement":
                len(placement_errors)
                == 0,


            "naming":
                len(naming_errors)
                == 0,


            "architectural_elements":
                (
                    inventory["walls"] > 0
                    and
                    inventory["doors"] > 0
                    and
                    inventory["windows"] > 0
                )

        }



        passed = all(
            checks.values()
        )



        score = 100


        if geometry_errors:

            score -= 30


        if placement_errors:

            score -= 30


        if naming_errors:

            score -= 10



        result = {


            "engine":
                "IFC_ARCHITECTURAL_CONSISTENCY_VALIDATOR_V1",


            "version":
                self.VERSION,


            "file":
                ifc_path,


            "inventory":
                inventory,


            "checks":
                checks,


            "errors":
                {

                    "geometry":
                        geometry_errors,


                    "placement":
                        placement_errors,


                    "naming":
                        naming_errors

                },


            "architectural_health":
                {

                    "score":
                        score,


                    "status":
                        (
                            "healthy"
                            if passed
                            else
                            "warning"
                        )

                },


            "status":
                (
                    "passed"
                    if passed
                    else
                    "failed"
                )

        }



        return result