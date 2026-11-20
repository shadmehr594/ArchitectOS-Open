class BIMExportEngine:

    def export(self, graph, spatial, site=None):

        return {
            "ifc": self._build_ifc(graph, spatial),
            "dxf": self._build_dxf(spatial),
            "revit_ready": self._revit_structure(graph, spatial),
            "meta": self._meta(site, graph)
        }

    # ======================
    # IFC EXPORT (CORE BIM)
    # ======================
    def _build_ifc(self, graph, spatial):

        elements = []

        for floor, data in spatial.items():

            if not isinstance(data, dict):
                continue

            nodes = data.get(
                "nodes",
                {}
            )

            for node, props in nodes.items():

                if not isinstance(props, dict):
                    continue

                elements.append({
                    "type": self._infer_type(node),
                    "name": node,
                    "location": {
                        "x": props["x"],
                        "y": props["y"],
                        "z": props.get("z", 0)
                    },
                    "size": {
                        "w": props["w"],
                        "h": props["h"],
                        "d": props.get("h", 3)
                    }
                })

        return {
            "schema": "IFC4-SIMPLIFIED",
            "elements": elements
        }

    # ======================
    # DXF EXPORT (2D LAYERS)
    # ======================
    def _build_dxf(self, spatial):

        layers = {
            "walls": [],
            "rooms": [],
            "core": []
        }

        for floor, data in spatial.items():

            if not isinstance(data, dict):
                continue

            nodes = data.get(
                "nodes",
                {}
            )

            for node, props in nodes.items():

                if not isinstance(props, dict):
                    continue

                if "Wall" in node or "Bedroom" in node:
                    layers["walls"].append(self._line(props))

                if "Living" in node or "Kitchen" in node:
                    layers["rooms"].append(self._rect(props))

                if "Core" in node:
                    layers["core"].append(self._point(props))

        return {
            "format": "DXF-SIMPLIFIED",
            "layers": layers
        }

    # ======================
    # REVIT STRUCTURE MAP
    # ======================
    def _revit_structure(self, graph, spatial):

        return {
            "levels": list(spatial.keys()),
            "families": self._map_families(graph),
            "rooms": self._extract_rooms(graph),
            "structure_ready": True
        }

    # ======================
    # TYPE INFERENCE
    # ======================
    def _infer_type(self, node):

        if "Bedroom" in node:
            return "Room"

        if "Kitchen" in node:
            return "Room"

        if "Core" in node:
            return "StructuralCore"

        if "Ramp" in node:
            return "Circulation"

        return "Generic"

    # ======================
    # HELPERS
    # ======================
    def _line(self, props):
        return {
            "type": "line",
            "start": (props["x"], props["y"]),
            "end": (props["x"] + props["w"], props["y"])
        }

    def _rect(self, props):
        return {
            "type": "rect",
            "x": props["x"],
            "y": props["y"],
            "w": props["w"],
            "h": props["h"]
        }

    def _point(self, props):
        return {
            "type": "point",
            "x": props["x"],
            "y": props["y"]
        }

    def _map_families(self, graph):

        families = []

        if not isinstance(graph, dict):
            return families


        for key, value in graph.items():

            if isinstance(value, list):

                for item in value:

                    if isinstance(item, str):

                        families.append(
                            item.split("-")[-1]
                        )

                    elif isinstance(item, dict):

                        families.append(
                            item.get(
                                "type",
                                item.get(
                                    "category",
                                    "Generic"
                                )
                            )
                        )


            elif isinstance(value, dict):

                families.append(
                    value.get(
                        "type",
                        value.get(
                            "category",
                            key
                        )
                    )
                )


        return list(set(families))

    def _extract_rooms(self, graph):

        rooms = []

        if not isinstance(graph, dict):
            return rooms


        for key, value in graph.items():


            if isinstance(value, list):

                for item in value:


                    if isinstance(item, str):

                        if (
                            "Bedroom" in item
                            or "Living" in item
                            or "Room" in item
                        ):

                            rooms.append(item)



                    elif isinstance(item, dict):

                        category = str(
                            item.get(
                                "type",
                                item.get(
                                    "category",
                                    ""
                                )
                            )
                        )


                        if category.lower() in [
                            "room",
                            "bedroom",
                            "living"
                        ]:

                            rooms.append(
                                item.get(
                                    "id",
                                    category
                                )
                            )



            elif isinstance(value, dict):

                category = str(
                    value.get(
                        "type",
                        value.get(
                            "category",
                            ""
                        )
                    )
                )


                if category.lower() in [
                    "room",
                    "bedroom",
                    "living"
                ]:

                    rooms.append(
                        value.get(
                            "id",
                            key
                        )
                    )



        return list(set(rooms))



    def _meta(self, site, graph):

        return {

            "site_type":
                site.get("type") if site else None,


            "node_count":
                len(graph.get("elements", []))
                if isinstance(graph, dict)
                else 0,


            "engine":
                "BIMExportEngine v53"

        }

# =====================================================
# BIM EXPORT INTELLIGENCE WRAPPER v53
# =====================================================


class BIMExportIntelligenceEngine(BIMExportEngine):


    def __init__(self):

        print(
            "📦 BIM Export Intelligence Engine v53.0 ACTIVE"
        )



    def build(
        self,
        graph
    ):


        print(
            "▶️ BUILD BIM EXPORT v53"
        )



        spatial = graph.get(
            "spatial",
            {}
        )



        result = self.export(

            graph,

            spatial

        )



        result["engine"] = (
            "bim_export_v53.0"
        )



        result["statistics"] = {


            "levels":

                len(
                    spatial
                ),


            "rooms":

                len(
                    graph.get(
                        "rooms",
                        {}
                    ).get(
                        "rooms",
                        []
                    )
                ),


            "clashes":

                len(
                    graph.get(
                        "clashes",
                        {}
                    ).get(
                        "clashes",
                        []
                    )
                )

        }



        print(
            f"📦 LEVELS EXPORTED: {result['statistics']['levels']}"
        )


        print(
            f"🚪 ROOMS EXPORTED: {result['statistics']['rooms']}"
        )


        print(
            f"💥 CLASHES EXPORTED: {result['statistics']['clashes']}"
        )



        return result