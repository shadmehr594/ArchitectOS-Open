# ==================================================
# ArchitectOS BIM Geometry Cleanup Post Processor v107.1
# ==================================================

class GeometryCleanupPostProcessor:

    VERSION = "107.1"


    def __init__(self):

        print(
            "🧹 Geometry Cleanup Post Processor v107.1 ACTIVE"
        )


    # ==================================================
    # CLEAN BIM MODEL AFTER GENERATION
    # ==================================================

    def clean(self, model):

        removed = []

        cleaned = {}


        for key, elements in model.items():

            if not isinstance(elements, list):

                cleaned[key] = elements
                continue


            valid_elements = []

            seen = set()


            for element in elements:


                element_id = element.get(
                    "id"
                )


                # ----------------------------------
                # DUPLICATE DETECTION
                # ----------------------------------

                signature = str(element)


                if signature in seen:

                    removed.append({

                        "id": element_id,

                        "reason":
                        "duplicate_geometry"

                    })

                    continue


                seen.add(signature)



                # ----------------------------------
                # ZERO LENGTH BEAM DETECTION
                # SUPPORT:
                # 1) direct start/end
                # 2) BIM data.start/end
                # ----------------------------------

                if element.get("type") == "beam":


                    data = element.get(
                        "data",
                        {}
                    )


                    start = element.get(
                        "start",
                        data.get("start")
                    )


                    end = element.get(
                        "end",
                        data.get("end")
                    )


                    if start is not None and end is not None:


                        if start == end:


                            removed.append({

                                "id": element_id,

                                "reason":
                                "invalid_geometry"

                            })

                            continue



                valid_elements.append(
                    element
                )


            cleaned[key] = valid_elements



        return {


            "engine":
            f"geometry_cleanup_post_v{self.VERSION}",


            "status":
            "completed",


            "removed":
            removed,


            "cleaned_model":
            cleaned

        }