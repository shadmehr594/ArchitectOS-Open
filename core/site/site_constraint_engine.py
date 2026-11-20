"""
ArchitectOS Site Constraint Engine v1.0

Applies basic architectural regulations
before spatial planning.

Features:
- Coverage ratio
- FAR / density
- Floor count
- Height limit
- Buildable validation
"""


class SiteConstraintEngine:

    VERSION = "1.0"


    def __init__(self):

        print(
            f"📐 Site Constraint Engine v{self.VERSION} ACTIVE"
        )


    # ==================================================
    # COVERAGE
    # ==================================================

    def calculate_coverage(
        self,
        site_area,
        coverage_ratio
    ):

        return site_area * coverage_ratio



    # ==================================================
    # DENSITY
    # ==================================================

    def calculate_floor_area(
        self,
        site_area,
        far
    ):

        return site_area * far



    # ==================================================
    # BUILDING FLOORS
    # ==================================================

    def calculate_floors(
        self,
        total_floor_area,
        buildable_area
    ):

        if buildable_area <= 0:
            return 0


        floors = total_floor_area / buildable_area


        return int(
            floors + 0.99
        )



    # ==================================================
    # MAIN ANALYSIS
    # ==================================================

    def analyze(
        self,
        site_analysis,
        rules
    ):


        site_area = site_analysis.get(
            "site",
            {}
        ).get(
            "area",
            0
        )


        buildable = site_analysis.get(
            "buildable_zone",
            {}
        ).get(
            "buildable_area",
            site_area
        )


        coverage_ratio = rules.get(
            "coverage",
            0.6
        )


        far = rules.get(
            "far",
            2.0
        )


        max_height = rules.get(
            "max_height",
            18
        )


        floor_height = rules.get(
            "floor_height",
            3.2
        )


        footprint = self.calculate_coverage(
            buildable,
            coverage_ratio
        )


        total_area = self.calculate_floor_area(
            site_area,
            far
        )


        floors = self.calculate_floors(
            total_area,
            footprint
        )


        max_floors_by_height = int(
            max_height / floor_height
        )


        if floors > max_floors_by_height:

            floors = max_floors_by_height



        result = {


            "site_area":
                site_area,


            "buildable_area":
                buildable,


            "allowed_footprint":
                footprint,


            "allowed_floor_area":
                total_area,


            "allowed_floors":
                floors,


            "max_height":
                max_height

        }



        print(
            "\n====== CONSTRAINT ANALYSIS ======"
        )


        print(
            "SITE AREA:",
            site_area
        )


        print(
            "FOOTPRINT:",
            footprint
        )


        print(
            "TOTAL FLOOR AREA:",
            total_area
        )


        print(
            "FLOORS:",
            floors
        )


        return result