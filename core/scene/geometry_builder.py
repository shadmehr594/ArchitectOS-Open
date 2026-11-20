class GeometryMeshBuilder:


    def __init__(self):

        print(
            "🏗️ Geometry Mesh Builder v33.0 ACTIVE"
        )


    def build(self, state):

        return self.generate(state)



    def create_box_mesh(
        self,
        length,
        depth,
        height,
        origin=(0,0,0)
    ):

        x, y, z = origin


        vertices = [

            [x, y, z],
            [x + length, y, z],
            [x + length, y + depth, z],
            [x, y + depth, z],

            [x, y, z + height],
            [x + length, y, z + height],
            [x + length, y + depth, z + height],
            [x, y + depth, z + height]

        ]


        faces = [

            [0,1,2,3],
            [4,7,6,5],
            [0,4,5,1],
            [1,5,6,2],
            [2,6,7,3],
            [4,0,3,7]

        ]


        return {

            "vertices": vertices,

            "faces": faces,

            "mesh_type": "box"

        }



    def generate(self, project):


        facade = project.get(
            "facade_result",
            {}
        )


        facade_walls = facade.get(
            "walls",
            []
        )


        facade_openings = facade.get(
            "openings",
            []
        )


        config = (
            project
            .get("facade", {})
            .get("config", {})
            .get("building", {})
        )


        width = config.get(
            "width",
            10
        )


        depth = config.get(
            "depth",
            10
        )


        floor_height = config.get(
            "floor_height",
            3
        )


        floors_count = project.get(
            "floors",
            1
        )



        walls = []



        for index, wall in enumerate(facade_walls):


            facade_name = wall.get(
                "facade"
            )


            length = wall.get(
                "length",
                10
            )


            height = wall.get(
                "height",
                floor_height
            )


            thickness = wall.get(
                "thickness",
                0.2
            )


            mesh = self.create_box_mesh(
                length,
                thickness,
                height
            )


            walls.append(

                {

                    "id":
                    facade_name,


                    "object_id":
                    f"wall_{index}",


                    "type":
                    "wall_mesh",


                    "length":
                    length,


                    "height":
                    height,


                    "thickness":
                    thickness,


                    "vertices":
                    mesh["vertices"],


                    "faces":
                    mesh["faces"],


                    "mesh_type":
                    mesh["mesh_type"],


                    "mesh_ready":
                    True

                }

            )



        openings = []



        for opening in facade_openings:


            openings.append(

                {

                    "type":
                    opening.get(
                        "type",
                        "window"
                    ),


                    "facade":
                    opening.get(
                        "facade"
                    ),


                    "width":
                    opening.get(
                        "width",
                        1
                    ),


                    "height":
                    opening.get(
                        "height",
                        1
                    ),


                    "operation":
                    "boolean_cut",


                    "mesh_ready":
                    True

                }

            )



        floors = []



        for level in range(
            floors_count
        ):


            mesh = self.create_box_mesh(

                width,

                depth,

                0.2,

                (
                    0,
                    0,
                    level * floor_height
                )

            )


            floors.append(

                {

                    "level":
                    level,


                    "mesh_type":
                    "floor_slab",


                    "vertices":
                    mesh["vertices"],


                    "faces":
                    mesh["faces"],


                    "mesh_ready":
                    True

                }

            )



        project["geometry_result"] = {


            "engine":
            "geometry_mesh_builder_v33.0",


            "status":
            "generated",


            "building":
            {

                "width":
                width,


                "depth":
                depth,


                "floors":
                floors_count

            },


            "walls":
            walls,


            "openings":
            openings,


            "floors":
            floors,


            "mesh_ready":
            True

        }



        return project