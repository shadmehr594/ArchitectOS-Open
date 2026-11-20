class VisionBIMReasoner:


    def __init__(self):

        print(
            "🏗️ Vision BIM Reasoner v69 ACTIVE"
        )



    def analyze(
        self,
        context
    ):


        elements = []



        if "elements" in context:

            elements = context.get(
                "elements",
                []
            )


        elif "nodes" in context:

            elements = context.get(
                "nodes",
                []
            )


        elif "bim" in context:

            bim = context.get(
                "bim",
                {}
            )

            elements = bim.get(
                "elements",
                []
            )



        structural_elements = []

        architectural_elements = []

        insights = []



        for element in elements:


            # پشتیبانی از string id

            if isinstance(
                element,
                str
            ):


                element_id = element


                if "wall" in element.lower():

                    structural_elements.append(
                        element_id
                    )


                elif "floor" in element.lower():

                    structural_elements.append(
                        element_id
                    )


                elif "opening" in element.lower():

                    architectural_elements.append(
                        element_id
                    )


                else:

                    insights.append(
                        f"Unknown element: {element_id}"
                    )


                continue



            category = element.get(
                "category",
                ""
            )


            element_id = element.get(
                "id",
                "unknown"
            )



            if category in [

                "Wall",
                "Floor",
                "Structure"

            ]:

                structural_elements.append(
                    element_id
                )



            elif category in [

                "Opening",
                "Window",
                "Door"

            ]:

                architectural_elements.append(
                    element_id
                )



            else:

                insights.append(
                    f"Unknown element detected: {element_id}"
                )



        if structural_elements:

            insights.append(
                "Basic structural system detected"
            )



        if architectural_elements:

            insights.append(
                "Architectural openings detected"
            )



        return {


            "engine":

            "vision_bim_reasoner_v69",



            "analysis":

            {


                "elements_count":

                len(elements),



                "structural_elements":

                structural_elements,



                "architectural_elements":

                architectural_elements,



                "insights":

                insights

            },



            "bim_reasoning_ready":

            True

        }