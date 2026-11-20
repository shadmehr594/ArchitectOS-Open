# ==================================================
# ArchitectOS Design Action Executor v1.2
# Applies ExecutionBridge actions to Design
# Preserves Spatial + Geometry Contract
# ==================================================

from copy import deepcopy


class DesignActionExecutor:

    VERSION = "1.2"


    def __init__(self):

        print(
            f"⚙️ Design Action Executor v{self.VERSION} ACTIVE"
        )


    # ==================================================
    # ENTRY
    # ==================================================

    def apply(
        self,
        design,
        actions
    ):

        design = deepcopy(
            design or {}
        )


        print("\n====== ACTION EXECUTOR INPUT ======")

        print(
            "keys:",
            design.keys()
        )

        print(
            "spatial:",
            design.get("spatial")
        )


        actions = actions or []


        # =============================================
        # PRESERVE GEOMETRY CONTRACT
        # =============================================

        if not isinstance(
            design.get("geometry"),
            dict
        ):

            design["geometry"] = {}


        geometry = design["geometry"]


        geometry.setdefault(
            "rooms",
            []
        )

        geometry.setdefault(
            "floors",
            []
        )

        geometry.setdefault(
            "levels",
            []
        )

        geometry.setdefault(
            "walls",
            []
        )

        geometry.setdefault(
            "doors",
            []
        )

        geometry.setdefault(
            "windows",
            []
        )


        print("\n====== EXECUTION GEOMETRY ======")

        print(
            "rooms:",
            len(
                geometry["rooms"]
            )
        )

        print(
            "walls:",
            len(
                geometry["walls"]
            )
        )

        print(
            "doors:",
            len(
                geometry["doors"]
            )
        )

        print(
            "windows:",
            len(
                geometry["windows"]
            )
        )


        applied = []

        ignored = []


        for action in actions:


            if not isinstance(
                action,
                dict
            ):

                continue


            if self._apply_action(
                design,
                action
            ):

                applied.append(
                    action
                )

            else:

                ignored.append(
                    action
                )


        # =============================================
        # OUTPUT DEBUG
        # =============================================

        print(
            "\n====== ACTION EXECUTOR OUTPUT DEBUG ======"
        )


        print(
            "design keys:",
            design.keys()
        )


        print(
            "spatial exists:",
            bool(
                design.get("spatial")
            )
        )


        geo = design.get(
            "geometry",
            {}
        )


        print(
            "rooms:",
            len(
                geo.get(
                    "rooms",
                    []
                )
            )
        )


        print(
            "walls:",
            len(
                geo.get(
                    "walls",
                    []
                )
            )
        )


        return {

            "engine":
            f"design_action_executor_v{self.VERSION}",


            "status":
            "completed",


            "design":
            design,


            "applied_actions":
            applied,


            "ignored_actions":
            ignored

        }



    # ==================================================
    # ACTION ROUTER
    # ==================================================

    def _apply_action(
        self,
        design,
        action
    ):

        module = action.get(
            "module",
            ""
        )


        if module == "facade":

            return self._facade(
                design,
                action
            )


        if module == "roof":

            return self._roof(
                design,
                action
            )


        if module == "materials":

            return self._materials(
                design,
                action
            )


        if module == "structure":

            return self._structure(
                design,
                action
            )


        if module == "site":

            return self._site(
                design,
                action
            )


        if module == "adaptive_reuse":

            return self._adaptive_reuse(
                design,
                action
            )


        if module == "bim":

            return self._bim(
                design,
                action
            )


        if module == "adaptive_reuse":

            return self._adaptive_reuse(
                design,
                action
            )


        if module == "bim":

            return self._bim(
                design,
                action
            )


        if module == "adaptive_reuse":

            return self._adaptive_reuse(
                design,
                action
            )


        if module == "bim":

            return self._bim(
                design,
                action
            )


        return False



    # ==================================================
    # MODULES
    # ==================================================

    def _facade(self, design, action):

        design.setdefault(
            "facade",
            {}
        )[

            action.get("action")

        ] = action.get(
            "parameters",
            {}
        )

        return True



    def _roof(self, design, action):

        design.setdefault(
            "roof",
            {}
        )[

            action.get("action")

        ] = action.get(
            "parameters",
            {}
        )

        return True



    def _materials(self, design, action):

        design.setdefault(
            "materials",
            {}
        )[

            action.get("action")

        ] = action.get(
            "parameters",
            {}
        )

        return True



    def _structure(self, design, action):

        design.setdefault(
            "structure",
            {}
        ).setdefault(
            "actions",
            []
        ).append(
            action
        )

        return True



    def _site(self, design, action):

        design.setdefault(
            "site",
            {}
        ).setdefault(
            "actions",
            []
        ).append(
            action
        )

        return True


    def _adaptive_reuse(
        self,
        design,
        action
    ):

        design.setdefault(
            "adaptive_reuse",
            {}
        ).setdefault(
            "actions",
            []
        ).append(
            action
        )

        return True



    def _bim(
        self,
        design,
        action
    ):

        design.setdefault(
            "bim",
            {}
        ).setdefault(
            "actions",
            []
        ).append(
            action
        )

        return True


    # ==================================================
    # ADAPTIVE REUSE
    # ==================================================

    def _adaptive_reuse(
        self,
        design,
        action
    ):

        design.setdefault(
            "adaptive_reuse",
            {}
        ).setdefault(
            "actions",
            []
        ).append(
            action
        )

        return True

    def _bim(
        self,
        design,
        action
    ):

        design.setdefault(
            "bim",
            {}
        ).setdefault(
            "actions",
            []
        ).append(
        action
        )

        return True



    # ==================================================
    # BIM MODIFICATION PLAN
    # ==================================================

    def _bim(
        self,
        design,
        action
    ):

        design.setdefault(
            "bim",
            {}
        ).setdefault(
            "modification_plan",
            []
        ).append(
            action
        )

        return True