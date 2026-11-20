"""
ArchitectOS Architectural Site Contract v1.1

Normalizes site intelligence data
for architectural reasoning pipeline.
"""


from core.site.site_intelligence_contract import (
    SiteIntelligenceContract
)


class ArchitecturalSiteContract:


    VERSION = "1.1"


    def __init__(self):

        print(
            f"🏛 Architectural Site Contract v{self.VERSION} ACTIVE"
        )

        self.site_contract = (
            SiteIntelligenceContract()
        )


    # ==================================================
    # NORMALIZE SITE
    # ==================================================

    def normalize(
        self,
        site
    ):


        # ----------------------------------------------
        # EMPTY INPUT
        # ----------------------------------------------

        if not site:

            return {

                "type":
                    "architectural_site",

                "boundary":
                    {},

                "access":
                    {},

                "orientation":
                    {},

                "constraints":
                    [],

                "semantic":
                {

                    "architectural":
                        True,

                    "normalized":
                        True

                }

            }


        # ----------------------------------------------
        # SAFETY CHECK
        # ----------------------------------------------

        if not isinstance(site, dict):

            raise TypeError(
                "ArchitecturalSiteContract.normalize expects dict input"
            )


        # ----------------------------------------------
        # NORMALIZED CONTRACT
        # ----------------------------------------------

        source_type = site.get(
            "type"
        )

        boundary = site.get(
            "boundary"
        )

        if not boundary:

            if source_type == "rect":

                bounds = site.get(
                    "bounds"
                )

                if bounds:

                    boundary = {
                        "type": "rect",
                        "bounds": bounds
                    }

                else:

                    boundary = {}

            elif source_type == "polygon":

                boundary = {
                    "type": "polygon",
                    "points": site.get(
                        "points",
                        []
                    ),
                    "bbox": site.get(
                        "bbox"
                    )
                }

            else:

                boundary = {}


        access = site.get(
            "access"
        )

        if not access:

            access = {}

            if site.get(
                "street_edge"
            ) is not None:

                access[
                    "street_edge"
                ] = site.get(
                    "street_edge"
                )


        constraints = list(
            site.get(
                "constraints",
                []
            )
        )


        contract = {

            "type":
                "architectural_site",

            "source_type":
                source_type,

            "boundary":
                boundary,

            "buildable_area":
                site.get(
                    "buildable_area"
                ),

            "coverage_limit":
                site.get(
                    "coverage_limit"
                ),

            "setbacks":
                site.get(
                    "setbacks",
                    {}
                ),

            "access":
                access,

            "orientation":
                site.get(
                    "orientation",
                    {}
                ),

            "constraints":
                constraints,

            "semantic":
            {

                "architectural":
                    True,

                "normalized":
                    True

            }

        }


        return contract


    # ==================================================
    # VALIDATE
    # ==================================================

    def validate(
        self,
        contract
    ):


        if not isinstance(
            contract,
            dict
        ):

            return False


        required = [

            "type",

            "boundary",

            "constraints"

        ]


        for item in required:

            if item not in contract:

                return False



        return (
            contract["type"]
            ==
            "architectural_site"
        )



    # ==================================================
    # DEBUG SUMMARY
    # ==================================================

    def summary(
        self,
        contract
    ):


        return {

            "type":
                contract.get(
                    "type"
                ),

            "boundary":
                bool(
                    contract.get(
                        "boundary"
                    )
                ),

            "constraints":
                len(
                    contract.get(
                        "constraints",
                        []
                    )
                ),

            "normalized":
                contract.get(
                    "semantic",
                    {}
                ).get(
                    "normalized",
                    False
                )

        }