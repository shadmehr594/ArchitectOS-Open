import json
import os


class SceneExporter:


    def __init__(self):

        print(
            "🎬 Scene Exporter Engine v32.0 ACTIVE"
        )



    def export(self, state):


        export_dir = "outputs"


        os.makedirs(
            export_dir,
            exist_ok=True
        )



        geometry = state.get(
            "geometry_result",
            {}
        )



        geometry_package = {


            "building":
            geometry.get(
                "building",
                {}
            ),


            "walls":
            geometry.get(
                "walls",
                []
            ),


            "floors":
            geometry.get(
                "floors",
                []
            ),


            "openings":
            geometry.get(
                "openings",
                []
            ),


            "mesh_ready":
            geometry.get(
                "mesh_ready",
                False
            )

        }




        scene_package = {


            "project":
            state.get(
                "project",
                "ArchitectOS_Project"
            ),



            "geometry":
            geometry_package,



            "materials":
            state.get(
                "material_result",
                {}
            ),



            "furniture":
            state.get(
                "furniture_result",
                {}
            ),



            "landscape":
            state.get(
                "landscape_result",
                {}
            ),



            "camera":
            state.get(
                "camera_result",
                {}
            ),



            "lighting":
            state.get(
                "lighting_result",
                {}
            )

        }




        json_file = os.path.join(
            export_dir,
            "ArchitectOS_scene.json"
        )




        with open(
            json_file,
            "w",
            encoding="utf-8"
        ) as f:


            json.dump(
                scene_package,
                f,
                indent=4,
                ensure_ascii=False
            )





        state["export_result"] = {



            "engine":
            "scene_exporter_v32.0",



            "status":
            "exported",



            "package":
            {


                "scene_json":
                json_file,



                "geometry":
                {


                    "walls":
                    len(
                        geometry_package["walls"]
                    ),



                    "floors":
                    len(
                        geometry_package["floors"]
                    ),



                    "openings":
                    len(
                        geometry_package["openings"]
                    ),



                    "mesh_ready":
                    geometry_package["mesh_ready"]

                },



                "camera_ready":
                "camera" in scene_package,



                "lighting_ready":
                "lighting" in scene_package


            },



            "export_ready":
            True

        }



        return state