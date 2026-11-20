# ==================================================
# ArchitectOS File -> BIM Integration Bridge v1.0
# File Context -> BIM Project Contract
# ==================================================


class FileBIMBridge:

    VERSION = "1.0"


    def __init__(self):

        print(
            f"🔗 File BIM Bridge v{self.VERSION} ACTIVE"
        )


    # ==================================================
    # EXTRACT ENTITIES FROM CAD LAYERS
    # ==================================================

    def _extract_entities_from_layers(
        self,
        layers
    ):

        entities = []

        if not isinstance(layers, dict):
            return entities


        for layer_name, items in layers.items():

            if not isinstance(items, list):
                continue


            for item in items:

                if isinstance(item, dict):

                    entity = dict(item)

                    entity["layer"] = layer_name

                    entities.append(
                        entity
                    )


        return entities



    # ==================================================
    # GEOMETRY NORMALIZER
    # ==================================================

    def _normalize_geometry(
        self,
        context
    ):

        context = context or {}


        geometry = (

            context.get(
                "raw_geometry",
                {}
            )

            or

            context.get(
                "geometry",
                {}
            )

            or

            context.get(
                "cad",
                {}
            )

            or

            context.get(
                "cad_data",
                {}
            )

            or

            {}

        )


        if not isinstance(
            geometry,
            dict
        ):

            geometry = {}



        layers = (

            geometry.get(
                "layers",
                {}
            )

            or

            context.get(
                "layers",
                {}
            )

            or

            {}

        )



        entities = (

            geometry.get(
                "entities",
                []
            )

            or

            self._extract_entities_from_layers(
                layers
            )

        )



        if not isinstance(
            entities,
            list
        ):

            entities = []



        walls = []

        doors = []

        windows = []



        for entity in entities:


            if not isinstance(
                entity,
                dict
            ):

                continue



            entity_type = str(

                entity.get(
                    "type",
                    ""
                )

            ).upper()



            layer = str(

                entity.get(
                    "layer",
                    ""
                )

            ).upper()



            if "WALL" in layer:


                walls.append(
                    entity
                )


            elif entity_type in [

                "LINE",

                "LWPOLYLINE",

                "POLYLINE"

            ]:


                walls.append(
                    entity
                )


            elif "DOOR" in layer:


                doors.append(
                    entity
                )


            elif "WINDOW" in layer:


                windows.append(
                    entity
                )



        print(
            "🔎 BIM BRIDGE GEOMETRY:",
            {
                "layers":
                    list(
                        layers.keys()
                    )
                    if isinstance(layers, dict)
                    else [],

                "entities":
                    len(entities),

                "walls":
                    len(walls),

                "doors":
                    len(doors),

                "windows":
                    len(windows)

            }
        )



        return {


            "layers":

                layers,


            "entities":

                entities,


            "walls":

                walls,


            "doors":

                doors,


            "windows":

                windows

        }



    # ==================================================
    # NORMALIZE FILE CONTEXT
    # ==================================================

    def prepare_bim_project(
        self,
        file_result
    ):

        file_result = file_result or {}


        context = file_result.get(
            "context",
            {}
        )


        geometry = self._normalize_geometry(
            context
        )


        return {


            "source":

                "ArchitectOS File Intelligence",



            "file_type":

                file_result.get(
                    "type",
                    "unknown"
                ),



            "site":

                context.get(
                    "site",
                    {}
                ),



            "geometry":

                geometry,



            "spatial":

                context.get(
                    "spatial",
                    {}
                ),



            "graph":

                context.get(
                    "graph",
                    {}
                ),



            "structural_grid":

                context.get(
                    "structural_grid",
                    {}
                )

        }



    # ==================================================
    # CONNECT TO BIM PIPELINE
    # ==================================================

    def run_bim(
        self,
        file_result
    ):


        from core.bim.full_bim_pipeline import (

            FullBIMPipeline

        )



        print(
            "DEBUG FILE RESULT KEYS:",
            file_result.keys()
        )


        print(
            "DEBUG CONTEXT:",
            file_result.get(
                "context"
            )
        )


        print(
            "RAW GEOMETRY DEBUG:",
            file_result.get("context", {}).get("raw_geometry")
        )


        project = self.prepare_bim_project(
            file_result
        )



        pipeline = FullBIMPipeline()



        result = pipeline.generate(
            project
        )



        return {


            "bridge":

                f"FileBIMBridge_v{self.VERSION}",



            "status":

                "completed",



            "input_project":

                project,



            "bim_result":

                result

        }