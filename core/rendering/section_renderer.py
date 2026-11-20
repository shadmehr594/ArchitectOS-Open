class SectionRenderer:


    def __init__(self):

        print(
            "✂️ Section Renderer Engine v25.3 ACTIVE"
        )


    def render(
        self,
        section_data,
        metadata=None
    ):


        sections = {}

        source = section_data.get(
            "sections",
            {}
        )


        for name, section in source.items():

            elements = []


            for item in section.get(
                "elements",
                []
            ):

                element = {

                    "type":
                    item.get(
                        "type",
                        "unknown"
                    )

                }


                if "name" in item:

                    element["name"] = (
                        item["name"]
                    )


                if "material" in item:

                    element["material"] = (
                        item["material"]
                    )


                if "height" in item:

                    element["height"] = (
                        item["height"]
                    )


                if "opening_type" in item:

                    element["opening_type"] = (
                        item["opening_type"]
                    )


                elements.append(
                    element
                )


            sections[name] = {

                "levels":
                section.get(
                    "levels",
                    1
                ),

                "elements":
                elements

            }


        return {

            "engine":
            "section_renderer_v25.3",


            "status":
            "rendered",


            "view":
            "section",


            "sections":
            sections,


            "metadata_integrated":
            metadata is not None

        }