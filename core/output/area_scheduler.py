class AreaScheduler:

    def __init__(self):

        print(
            "📐 Area Scheduler Engine v21.2 ACTIVE"
        )


    def room_area(self, room_type):

        areas = {

            "living": 24,
            "kitchen": 10,
            "bedroom": 14,
            "bathroom": 5,

            "parking": 45,
            "entrance": 8,
            "stairs": 8,

            "garden": 30,

            "green_roof": 40,
            "terrace": 20,

            "vertical_core": 8,
            "storage": 5

        }

        return areas.get(
            room_type,
            5
        )


    def generate(
        self,
        spatial,
        plan
    ):


        schedule = {}

        total_built = 0


        floors = spatial.get(
            "floors",
            {}
        )


        for floor_name, floor_data in floors.items():

            floor_schedule = {}

            spaces = floor_data.get(
                "spaces",
                []
            )


            floor_total = 0


            for space in spaces:


                # استخراج نوع فضا

                room_type = space.lower()


                area = 0


                for key in [
                    "living",
                    "kitchen",
                    "bedroom",
                    "bathroom",
                    "parking",
                    "entrance",
                    "stairs",
                    "garden",
                    "green_roof",
                    "terrace",
                    "core"
                ]:

                    if key in room_type:

                        area = self.room_area(
                            key
                        )

                        break


                if area == 0:

                    area = 5


                floor_schedule[space] = area

                floor_total += area


            schedule[floor_name] = {

                "spaces":
                    floor_schedule,

                "total_area":
                    floor_total
            }


            total_built += floor_total



        site = plan.get(
            "site",
            {}
        )


        site_area = site.get(
            "area",
            0
        )


        coverage = 0


        if site_area:

            coverage = round(
                total_built / site_area,
                2
            )



        return {


            "engine":
                "area_scheduler_v21.2",


            "status":
                "generated",


            "area_schedule":
                schedule,


            "metrics":{

                "site_area":
                    site_area,

                "built_area":
                    total_built,

                "coverage_ratio":
                    coverage
            }

        }