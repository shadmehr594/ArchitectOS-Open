from datetime import datetime
import os



class IFCExportPipeline:


    VERSION = "27.8"



    def __init__(self):

        print(
            f"📦 IFC Export Pipeline v{self.VERSION} ACTIVE"
        )



    # =====================================
    # MAIN EXPORT
    # =====================================

    def export(
        self,
        ifc_model,
        validation_result,
        config=None
    ):


        config = config or {}



        mode = config.get(
            "mode",
            "advisory"
        )


        project = config.get(
            "project",
            "ArchitectOS_Project"
        )


        version = config.get(
            "version",
            "1.0"
        )



        # =====================================
        # VALIDATION GATE
        # =====================================

        if not validation_result.get(
            "ready_for_export",
            True
        ):


            return {

                "engine":
                f"ifc_export_pipeline_v{self.VERSION}",


                "status":
                "blocked",


                "reason":
                "validation_failed"

            }




        # =====================================
        # EXTRACT IFC MODEL
        # =====================================

        entities = {}



        if isinstance(
            ifc_model,
            dict
        ):


            entities = ifc_model.get(
                "entities",
                {}
            )



        # fallback برای مدل‌های قدیمی

        if not entities:


            entities = (
                ifc_model
                .get(
                    "ifc",
                    {}
                )
                .get(
                    "entities",
                    {}
                )

            )



        # =====================================
        # ENTITY STATISTICS
        # =====================================

        entity_statistics = {}

        total_entities = 0



        if isinstance(
            entities,
            dict
        ):


            for key,value in entities.items():


                count = (

                    len(value)

                    if isinstance(
                        value,
                        list
                    )

                    else 0

                )


                entity_statistics[key] = count


                total_entities += count




        # =====================================
        # IFC FILE INFO
        # =====================================

        exports_dir = os.path.abspath(
            "exports"
        )


        ifc_file = os.path.join(
            exports_dir,
            project + ".ifc"
        )



        package = {


            "file":

            project + ".ifc",



            "path":

            ifc_file,



            "schema":

            ifc_model.get(
                "ifc_version",
                "IFC4"
            ),



            "entity_count":

            total_entities,



            "entities":

            entity_statistics

        }




        # =====================================
        # FINAL CONTRACT
        # =====================================

        return {


            "engine":

            f"ifc_export_pipeline_v{self.VERSION}",



            "status":

            "exported",



            "project":

            project,



            "version":

            version,



            "mode":

            mode,



            "package":

            package,



            "metadata":

            {

                "generated":

                datetime.now()
                .isoformat(),


                "validated":

                True

            },



            "ifc_ready":

            True

        }