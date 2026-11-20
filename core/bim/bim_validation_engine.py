class BIMValidationEngine:


    def __init__(self):

        print(
            "✅ BIM Validation & Consistency Engine v27.6 ACTIVE"
        )



    def validate(
        self,
        ifc_model,
        config=None
    ):


        config = config or {}



        mode = config.get(
            "mode",
            "advisory"
        )


        errors = []

        warnings = []



        entities = (

            ifc_model
            .get(
                "ifc",
                {}
            )
            .get(
                "entities",
                []
            )

        )



        if not entities:


            errors.append(

                {

                    "type":
                    "empty_model",

                    "message":
                    "no BIM entities found"

                }

            )



        validated = []



        for entity in entities:


            entity_type = entity.get(
                "type"
            )


            guid = entity.get(
                "guid"
            )


            properties = entity.get(
                "properties",
                {}

            )


            # GUID check

            if not guid:


                errors.append(

                    {

                        "type":
                        "missing_guid",

                        "entity":
                        entity_type

                    }

                )



            # element checks

            if entity_type == "IfcWall":


                if not properties.get(
                    "length"
                ):

                    warnings.append(

                        {

                            "rule":
                            "wall_length",

                            "message":
                            "wall length missing"

                        }

                    )



            if entity_type == "IfcWindow":


                if not properties.get(
                    "width"
                ):

                    warnings.append(

                        {

                            "rule":
                            "window_width",

                            "message":
                            "window width missing"

                        }

                    )



            if entity_type == "IfcSpace":


                if not properties.get(
                    "name"
                ):

                    warnings.append(

                        {

                            "rule":
                            "space_name",

                            "message":
                            "space name missing"

                        }

                    )



            validated.append(

                {

                    "type":
                    entity_type,

                    "status":
                    "valid"

                }

            )



        score = 100


        score -= len(errors) * 20

        score -= len(warnings) * 5



        if score < 0:

            score = 0



        return {


            "engine":
            "bim_validation_v27.6",


            "status":
            "validated",


            "mode":
            mode,


            "score":
            score,


            "errors":
            errors,


            "warnings":
            warnings,


            "validated_entities":
            validated,


            "ready_for_export":
            len(errors) == 0

        }