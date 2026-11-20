import json
import uuid
import os


class ProductionExportEngine:

    VERSION = "2.0"


    def __init__(
        self,
        export_dir="exports"
    ):

        self.export_dir = export_dir

        os.makedirs(
            export_dir,
            exist_ok=True
        )


        print(
            f"📦 Production Export Engine v{self.VERSION} ACTIVE"
        )



    # ======================
    # MAIN EXPORT PIPELINE
    # ======================

    def export(
        self,
        bim_state,
        output_dir=None,
    ):

        if output_dir:
            self.export_dir = output_dir

        os.makedirs(self.export_dir, exist_ok=True)

        export_id = str(
            uuid.uuid4()
        )


        normalized = (
            self._normalize_state(
                bim_state
            )
        )


        ifc_file = (
            self._export_ifc(
                normalized,
                export_id
            )
        )


        dxf_file = (
            self._export_dxf(
                normalized,
                export_id
            )
        )


        render_data = (
            self._export_render(
                normalized,
                export_id
            )
        )


        return {

            "id":
            export_id,


            "engine":
            f"production_export_v{self.VERSION}",


            "status":
            "completed",


            "ifc":
            ifc_file,


            "dxf":
            dxf_file,


            "render":
            render_data

        }



    # ======================
    # NORMALIZER
    # ======================

    def _normalize_state(
        self,
        bim_state
    ):


        spatial = (
            bim_state.get(
                "spatial",
                {}
            )
        )


        normalized_spatial = (
            self._normalize_spatial(
                spatial
            )
        )


        result = dict(
            bim_state
        )


        result["spatial"] = (
            normalized_spatial
        )


        return result



    # ======================
    # SPATIAL NORMALIZER
    # ======================

    def _normalize_spatial(
        self,
        spatial
    ):


        # Already compatible

        if isinstance(
            spatial,
            dict
        ):


            if all(

                isinstance(v, dict)
                and "nodes" in v

                for v in spatial.values()

            ):

                return spatial



        nodes = {}

        level_name = "LEVEL_0"


        # New FullBIMPipeline format

        for level in spatial.get(
            "levels",
            []
        ):

            level_name = (
                level.get(
                    "name",
                    "LEVEL_0"
                )
            )


            spaces = (
                level.get(
                    "spaces",
                    []
                )
            )


            level_name = (
                level.get(
                    "name",
                    "LEVEL_0"
                )
            )


            spaces = (
                level.get(
                    "spaces",
                    []
                )
            )


            for index, space in enumerate(
                spaces
            ):


                nodes[space] = {

                    "x":
                    index * 5,


                    "y":
                    0,


                    "w":
                    5,


                    "h":
                    5,


                    "connections":
                    []

                }



        return {

            level_name:
            {

                "nodes":
                nodes

            }

        }



    # ======================
    # IFC EXPORT
    # ======================

    def _export_ifc(
        self,
        bim,
        export_id
    ):


        ifc_data = {


            "type":
            "IFC_MODEL",


            "buildings":
            bim.get(
                "bim",
                {}
            ),


            "structure":
            bim.get(
                "structure",
                {}
            ),


            "bim_elements":
            bim.get(
                "bim_elements",
                []
            ),


            "metadata":

            {

                "author":
                "ArchitectOS",


                "export_id":
                export_id

            }

        }



        path = os.path.join(
            self.export_dir,
            f"{export_id}.ifc.json"
        )



        with open(
            path,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                ifc_data,
                f,
                indent=2,
                ensure_ascii=False
            )


        return path



    # ======================
    # DXF EXPORT
    # ======================

    def _export_dxf(
        self,
        bim,
        export_id
    ):


        spatial = (
            bim.get(
                "spatial",
                {}
            )
        )


        dxf_data = {


            "type":
            "DXF_LIKE",


            "layers":
            []

        }



        for floor, data in spatial.items():


            layer = {


                "floor":
                floor,


                "entities":
                []

            }



            for node, props in data.get(
                "nodes",
                {}
            ).items():


                layer["entities"].append(

                    {

                        "type":
                        "POINT",


                        "x":
                        props.get(
                            "x",
                            0
                        ),


                        "y":
                        props.get(
                            "y",
                            0
                        ),


                        "label":
                        node

                    }

                )



            dxf_data["layers"].append(
                layer
            )



        path = os.path.join(
            self.export_dir,
            f"{export_id}.dxf.json"
        )



        with open(
            path,
            "w",
            encoding="utf-8"
        ) as f:


            json.dump(
                dxf_data,
                f,
                indent=2,
                ensure_ascii=False
            )



        return path



    # ======================
    # COMFYUI RENDER BRIDGE
    # ======================

    def _export_render(
        self,
        bim,
        export_id
    ):


        prompt = {


            "positive":
            "ultra realistic architectural render, modern building, cinematic lighting, BIM accurate",


            "negative":
            "low quality, distorted geometry",


            "bim_reference":
            bim.get(
                "spatial",
                {}
            )

        }



        path = os.path.join(
            self.export_dir,
            f"{export_id}_render.json"
        )



        with open(
            path,
            "w",
            encoding="utf-8"
        ) as f:


            json.dump(
                prompt,
                f,
                indent=2,
                ensure_ascii=False
            )



        return {


            "prompt_file":
            path,


            "workflow":
            "comfyui_ready"

        }
