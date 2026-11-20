# ==================================================
# ArchitectOS BIM Evolution Connector v101
# ==================================================


class ArchitectOSBIMEvolutionConnector:


    VERSION = "101.0"



    def __init__(
        self,
        bim_pipeline=None
    ):


        print(
            "🏗️ ArchitectOS BIM Evolution Connector v101.0 ACTIVE"
        )


        self.bim_pipeline = bim_pipeline



    def process(
        self,
        evolution_result
    ):


        updates = (
            evolution_result
            .get(
                "execution",
                {}
            )
            .get(
                "bim_updates",
                []
            )
        )


        results = []


        for update in updates:


            results.append(
                self._apply_update(
                    update
                )
            )


        return {


            "engine":
            f"architectos_bim_evolution_connector_v{self.VERSION}",


            "status":
            "completed",


            "applied_updates":
            results

        }



    def _apply_update(
        self,
        update
    ):


        module = update.get(
            "module"
        )


        action = update.get(
            "action"
        )


        if self.bim_pipeline:


            if hasattr(
                self.bim_pipeline,
                "process"
            ):

                return self.bim_pipeline.process(
                    update
                )


        return {


            "module":
            module,


            "action":
            action,


            "status":
            "applied"

        }