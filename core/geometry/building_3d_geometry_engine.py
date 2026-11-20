class Building3DGeometryEngine:


    def __init__(self):

        print(
            "🏢 3D Building Geometry Engine v27.8 ACTIVE"
        )



    def generate(
        self,
        bim_model,
        config=None
    ):


        config = config or {}


        height_default = config.get(
            "floor_height",
            3
        )


        objects = []


        elements = bim_model.get(
            "elements",
            []
        )



        for element in elements:


            element_type = element.get(
                "type"
            )


            props = element.get(
                "properties",
                {}
            )



            # -------------------
            # Wall geometry
            # -------------------

            if element_type == "IfcWall":


                objects.append(

                    {

                        "type":
                        "wall_mesh",


                        "geometry":

                        {

                            "length":
                            props.get(
                                "length",
                                0
                            ),


                            "height":
                            props.get(
                                "height",
                                height_default
                            ),


                            "thickness":
                            props.get(
                                "thickness",
                                0.2
                            )

                        },


                        "material":
                        props.get(
                            "material",
                            "concrete"
                        )

                    }

                )



            # -------------------
            # Window void
            # -------------------

            elif element_type == "IfcWindow":


                objects.append(

                    {

                        "type":
                        "window_void",


                        "geometry":

                        {

                            "width":
                            props.get(
                                "width",
                                0
                            ),


                            "height":
                            props.get(
                                "height",
                                0
                            )

                        }

                    }

                )



            # -------------------
            # Space volume
            # -------------------

            elif element_type == "IfcSpace":


                objects.append(

                    {

                        "type":
                        "space_volume",


                        "name":
                        props.get(
                            "name",
                            "unknown"
                        ),


                        "geometry":

                        {

                            "height":
                            height_default

                        }

                    }

                )



            # -------------------
            # Roof
            # -------------------

            elif element_type == "IfcRoof":


                objects.append(

                    {

                        "type":
                        "roof_surface",


                        "geometry":

                        {

                            "level":
                            "top"

                        }

                    }

                )



        return {


            "engine":
            "building_3d_geometry_v27.8",


            "status":
            "generated",


            "objects":
            objects,


            "statistics":

            {

                "objects":
                len(objects)

            },


            "3d_ready":
            True

        }