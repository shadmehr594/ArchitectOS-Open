class SiteContextAdapter:


    VERSION = "SITE_CONTEXT_ADAPTER_v1"



    def build(
        self,
        site_intelligence,
        constraints=None
    ):

        if not site_intelligence:

            return {}



        context = {

            "site": {

                "site_id":
                    site_intelligence.get(
                        "site_id"
                    ),


                "area":
                    site_intelligence.get(
                        "area"
                    ),


                "boundary":
                    site_intelligence.get(
                        "boundary",
                        []
                    ),


                "bbox":
                    site_intelligence.get(
                        "bbox",
                        {}
                    ),


                "orientation":
                    site_intelligence.get(
                        "orientation"
                    )

            },


            "site_constraints":

                constraints or {}

        }


        return context