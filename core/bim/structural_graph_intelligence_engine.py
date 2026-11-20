class StructuralGraphIntelligenceEngine:

    VERSION = "106.0"


    def __init__(self):

        print(
            "🏗️ Structural Graph Intelligence Engine v106.0 ACTIVE"
        )


    def analyze(self, elements):

        columns = []
        beams = []


        for element in elements:

            if element.get("ifc_type") == "IfcColumn":
                columns.append(element)


            elif element.get("ifc_type") == "IfcBeam":
                beams.append(element)



        load_paths = []
        column_stats = {}


        for column in columns:

            cdata = column.get(
                "data",
                {}
            )

            cx = cdata.get("x", 0)
            cy = cdata.get("y", 0)


            connected_beams = []


            for beam in beams:

                bdata = beam.get(
                    "data",
                    {}
                )


                start = tuple(
                    bdata.get(
                        "start",
                        (0, 0)
                    )
                )


                end = tuple(
                    bdata.get(
                        "end",
                        (0, 0)
                    )
                )


                if (
                    (cx, cy) == start
                    or
                    (cx, cy) == end
                ):


                    connected_beams.append(
                        beam["id"]
                    )


                    load_paths.append({

                        "from":
                        beam["id"],


                        "to":
                        column["id"],


                        "type":
                        "load_transfer",


                        "direction":
                        "vertical",


                        "behavior":
                        "gravity"

                    })



            importance = 0


            if len(connected_beams) > 0:

                importance = round(
                    min(
                        len(connected_beams) / 5,
                        1
                    ),
                    2
                )


            column_stats[column["id"]] = {

                "supported_beams":
                connected_beams,


                "beam_count":
                len(connected_beams),


                "importance":
                importance

            }



        critical_elements = []


        for cid, data in column_stats.items():

            if data["importance"] >= 0.8:

                critical_elements.append(cid)



        return {


            "engine":
            f"structural_graph_v{self.VERSION}",


            "nodes":

            {

                "columns":
                len(columns),


                "beams":
                len(beams)

            },


            "load_paths":
            load_paths,


            "column_analysis":
            column_stats,


            "critical_elements":
            critical_elements,


            "relationship_count":
            len(load_paths),


            "risk_status":
            "analyzed",


            "status":
            "completed"

        }