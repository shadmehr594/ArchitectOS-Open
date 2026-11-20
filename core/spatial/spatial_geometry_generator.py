"""
ArchitectOS Spatial Geometry Generator v2.0

Converts semantic spatial layout
into architectural geometry contract.
"""


class SpatialGeometryGenerator:


    VERSION = "2.0"



    def __init__(self):

        print(
            "🏗 SPATIAL GEOMETRY GENERATOR v2.0 ONLINE"
        )


        self.default_height = 3.2



    # ==================================================
    # SPACE SIZE RULES
    # ==================================================

    def resolve_size(
        self,
        space
    ):


        name = space.get(
            "name",
            ""
        )


        sizes = {


            "living":
                (6,5),


            "kitchen":
                (4,4),


            "dining":
                (4,4),


            "entrance":
                (3,3),


            "guest_room":
                (4,4),


            "stairs":
                (3,4),


            "master_bedroom":
                (5,4),


            "bedroom":
                (4,4),


            "bathroom":
                (3,2),


            "family_lounge":
                (5,4),


            "garden":
                (8,5),


            "parking":
                (6,5)

        }


        return sizes.get(

            name,

            (4,4)

        )



    # ==================================================
    # POSITION RULES
    # ==================================================

    def resolve_position(
        self,
        space,
        index
    ):


        position = space.get(
            "position"
        )


        zone = space.get(
            "zone"
        )



        # public front

        if position == "front":

            return (

                index * 4,

                0

            )



        # private rear

        if position == "rear":

            return (

                index * 4,

                5

            )



        # service

        if zone == "service":

            return (

                0,

                5

            )



        # external

        if zone == "external":

            return (

                index * 6,

                -5

            )



        return (

            index * 4,

            index * 4

        )



    # ==================================================
    # SPACE GEOMETRY
    # ==================================================

    def generate_space_geometry(
        self,
        space,
        index
    ):


        w,h = self.resolve_size(
            space
        )


        x,y = self.resolve_position(
            space,
            index
        )


        return {


            "name":
                space.get(
                    "name"
                ),


            "type":
                "space",


            "level":
                space.get(
                    "level"
                ),


            "zone":
                space.get(
                    "zone"
                ),


            "position":
                space.get(
                    "position"
                ),


            "x":
                x,


            "y":
                y,


            "w":
                w,


            "h":
                h,


            "height":
                self.default_height


        }



    # ==================================================
    # FLOOR
    # ==================================================

    def generate_floor_geometry(
        self,
        floor
    ):


        spaces = []


        for index, space in enumerate(

            floor.get(
                "spaces",
                []
            )

        ):


            spaces.append(

                self.generate_space_geometry(

                    space,

                    index

                )

            )



        return {

            "level":

                floor.get("level"),


            "nodes":

            {

                space["name"]:
                    space

                for space in spaces

            },


            "spaces":

                spaces

        }



    # ==================================================
    # BUILDING
    # ==================================================

    def generate(
        self,
        plan
    ):


        building = plan.get(
            "building",
            {}
        )


        floors = []



        for floor_name, floor in building.items():


            geometry = self.generate_floor_geometry(
                floor
            )


            geometry["name"] = floor_name


            floors.append(
                geometry
            )



        return {


            "geometry_model":
            {


                "floors":

                    floors


            },


            "metadata":
            {


                "engine":

                    "Spatial Geometry Generator",


                "version":

                    self.VERSION


            }

        }