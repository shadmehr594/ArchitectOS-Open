class BIMRelationshipEngine:


    def __init__(self):

        print(
            "🔗 BIM Relationship Engine v37.0 ACTIVE"
        )



    def generate(
        self,
        elements
    ):


        relations=[]


        for e in elements:


            if e.get("level"):


                relations.append({

                    "from":
                        e["id"],

                    "to":
                        e["level"],

                    "type":
                        "belongs_to"

                })



        columns = [

            e for e in elements
            if e.get("bim_type")=="column"

        ]


        beams = [

            e for e in elements
            if e.get("bim_type")=="beam"

        ]


        for column in columns:


            for beam in beams:


                if column.get("level")==beam.get("level"):


                    relations.append({

                        "from":
                            column["id"],

                        "to":
                            beam["id"],

                        "type":
                            "supports"

                    })


        return relations