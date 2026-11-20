# ==================================================
# ArchitectOS BIM Geometry Cleanup Engine v106
# ==================================================

class GeometryCleanupEngine:

    VERSION = "106.0"


    def __init__(self):

        print(
            "🧹 BIM Geometry Cleanup Engine v106.0 ACTIVE"
        )


    # ==================================================
    # MAIN CLEAN
    # ==================================================

    def process(self, bim_data):

        cleaned = {}

        removed = []


        for key, elements in bim_data.items():

            if not isinstance(elements, list):

                cleaned[key] = elements
                continue


            cleaned[key] = []


            for element in elements:


                if self._is_invalid(element):

                    removed.append(
                        {
                            "id": element.get("id"),
                            "reason": "invalid_geometry"
                        }
                    )

                    continue



                if self._is_duplicate(
                    cleaned[key],
                    element
                ):

                    removed.append(
                        {
                            "id": element.get("id"),
                            "reason": "duplicate"
                        }
                    )

                    continue



                cleaned[key].append(element)



        return {

            "engine":
            f"geometry_cleanup_v{self.VERSION}",


            "status":
            "completed",


            "removed":
            removed,


            "cleaned_model":
            cleaned

        }



    # ==================================================
    # VALIDATION
    # ==================================================

    def _is_invalid(self, element):


        if element.get("type") != "beam":
            return False


        start = element.get(
            "start"
        )

        end = element.get(
            "end"
        )


        if start and end:

            if start == end:
                return True


        return False



    # ==================================================
    # DUPLICATE CHECK
    # ==================================================

    def _is_duplicate(
        self,
        existing,
        element
    ):


        for item in existing:


            if (
                item.get("type")
                ==
                element.get("type")
                and
                item.get("start")
                ==
                element.get("start")
                and
                item.get("end")
                ==
                element.get("end")
            ):

                return True


        return False