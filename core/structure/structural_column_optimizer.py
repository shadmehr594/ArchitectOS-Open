print("USING structural_column_optimizer.py ColumnOptimizer")


class StructuralColumnOptimizer:


    VERSION = "1.0"


    def __init__(self):

        print(
            "🏗️ Structural Column Optimizer v1.0 ACTIVE"
        )



    def optimize(
        self,
        columns,
        architectural_model
    ):


        spaces = architectural_model.get(
            "spaces",
            []
        )


        protected = self._extract_protected_zones(
            spaces
        )


        result = []


        for column in columns:


            point = {

                "x": column.get("x"),

                "y": column.get("y")

            }


            if self._inside_protected_zone(
                point,
                protected
            ):

                continue


            result.append(
                column
            )


        result = self._remove_duplicate_columns(
            result
        )


        result = self._reduce_redundant_columns(
            result
        )


        return result



    # ------------------------------------------
    # PROTECTED ARCHITECTURAL ZONES
    # ------------------------------------------

    def _extract_protected_zones(
        self,
        spaces
    ):


        zones = []


        for space in spaces:


            if space.get("type") in [

                "stairs",
                "elevator",
                "duct",
                "corridor"

            ]:


                zones.append(
                    space.get(
                        "bounds"
                    )
                )


        return zones



    # ------------------------------------------
    # POINT CHECK
    # ------------------------------------------

    def _inside_protected_zone(
        self,
        point,
        zones
    ):


        x = point["x"]

        y = point["y"]


        for zone in zones:


            if not zone:
                continue


            bx, by, w, h = zone


            if (

                bx <= x <= bx+w

                and

                by <= y <= by+h

            ):

                return True


        return False



    # ------------------------------------------
    # DUPLICATE CLEANUP
    # ------------------------------------------

    def _remove_duplicate_columns(
        self,
        columns
    ):


        result = []

        seen = set()


        for column in columns:


            key = (

                column["x"],

                column["y"]

            )


            if key in seen:

                continue


            seen.add(key)


            result.append(
                column
            )


        return result



    # ------------------------------------------
    # SIMPLE STRUCTURAL REDUCTION
    # ------------------------------------------

    def _reduce_redundant_columns(
        self,
        columns
    ):


        optimized = []


        for column in columns:


            keep = True


            for existing in optimized:


                dx = abs(
                    column["x"]
                    -
                    existing["x"]
                )


                dy = abs(
                    column["y"]
                    -
                    existing["y"]
                )


                if dx < 1 and dy < 1:

                    keep = False

                    break


            if keep:

                optimized.append(
                    column
                )


        return optimized