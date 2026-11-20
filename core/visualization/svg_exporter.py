class SVGExporter:


    def __init__(self):

        print(
            "🎨 SVG Export Engine v22.5 ACTIVE"
        )


    def export(
        self,
        drawing
    ):

        svg = []

        svg.append(
            "<svg>"
        )


        for floor,data in drawing.get(
            "floors",
            {}
        ).items():

            for room in data.get(
                "rooms",
                []
            ):

                svg.append(
                    f"""
                    <rect
                    x="{room['x']}"
                    y="{room['y']}"
                    width="{room['width']}"
                    height="{room['depth']}"
                    />
                    """
                )


        svg.append(
            "</svg>"
        )


        return {

            "engine":
                "svg_exporter_v22.5",

            "status":
                "exported",

            "svg":
                "\n".join(svg)
        }