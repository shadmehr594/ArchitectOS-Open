# ==========================================================
# ArchitectOS Execution Plan v68
# Universal Runtime Contract
# Metadata Aware
# ==========================================================


class ExecutionPlan:


    def __init__(
        self,
        intent,
        workflow=None,
        engine=None,
        parameters=None,
        inputs=None,
        metadata=None
    ):


        self.intent = intent

        self.workflow = workflow

        self.engine = engine

        self.parameters = parameters or {}

        self.inputs = inputs or {}

        # ==================================================
        # RUNTIME METADATA
        # ==================================================

        self.metadata = metadata or {

            "building_type":
                "generic"

        }


        self.status = "created"



    # ======================================================
    # STATUS
    # ======================================================

    def update_status(
        self,
        status
    ):

        self.status = status



    # ======================================================
    # METADATA
    # ======================================================

    def set_metadata(
        self,
        key,
        value
    ):

        self.metadata[key] = value



    def get_metadata(
        self,
        key,
        default=None
    ):

        return self.metadata.get(
            key,
            default
        )



    # ======================================================
    # EXPORT
    # ======================================================

    def to_dict(self):

        return {

            "intent":
                self.intent,

            "workflow":
                self.workflow,

            "engine":
                self.engine,

            "parameters":
                self.parameters,

            "inputs":
                self.inputs,

            "metadata":
                self.metadata,

            "status":
                self.status

        }



    def __repr__(self):

        return str(
            self.to_dict()
        )