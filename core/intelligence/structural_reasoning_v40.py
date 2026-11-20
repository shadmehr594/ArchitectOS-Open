"""
ArchitectOS BIM
Structural Reasoning Engine v40

Purpose:
- Validate structural logic
- Detect invalid geometry
- Build basic load path reasoning
"""


class StructuralReasoningEngine:

    VERSION = "40.0"


    def __init__(self):

        self.issues = []
        self.load_paths = []


    def process(self, project):

        # Pipeline sends direct BIM element list
        if isinstance(project, list):

            project = {
                "bim_elements": project
            }


        return self.analyze(project)



    def analyze(self, bim):

        self.issues = []
        self.load_paths = []


        elements = bim.get(
            "bim_elements",
            []
        )


        columns = [
            e for e in elements
            if e.get("ifc_type") == "IfcColumn"
        ]


        beams = [
            e for e in elements
            if e.get("ifc_type") == "IfcBeam"
        ]


        self.check_geometry(
            beams
        )


        self.build_load_paths(
            columns,
            beams
        )


        return {

            "engine":
                "structural_reasoning_v40.0",

            "status":
                "completed",

            "issues":
                self.issues,

            "load_paths":
                self.load_paths
        }



    def check_geometry(self, beams):

        for beam in beams:

            data = beam.get(
                "data",
                {}
            )


            start = data.get(
                "start"
            )


            end = data.get(
                "end"
            )


            if start == end:

                self.issues.append({

                    "element":
                        beam.get("id"),

                    "type":
                        "zero_length_beam",

                    "severity":
                        "high",

                    "message":
                        "Beam has identical start and end points"

                })



    def build_load_paths(
        self,
        columns,
        beams
    ):


        for column in columns:

            connected = []


            cdata = column.get(
                "data",
                {}
            )


            cx = cdata.get(
                "x"
            )

            cy = cdata.get(
                "y"
            )


            for beam in beams:


                bdata = beam.get(
                    "data",
                    {}
                )


                start = bdata.get(
                    "start"
                )


                end = bdata.get(
                    "end"
                )


                if (
                    (cx, cy) == start
                    or
                    (cx, cy) == end
                ):

                    connected.append(
                        beam.get("id")
                    )



            self.load_paths.append({

                "from":
                    column.get("id"),

                "type":
                    "column_to_beam",

                "supports":
                    connected

            })