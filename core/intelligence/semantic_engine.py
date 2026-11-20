class SemanticEngine:

    VERSION = "38.0"

    def __init__(self):
        print("🧠 BIM Semantic Engine v38.0 ACTIVE")


    def analyze_element(self, element):

        element_type = element.get("type")

        semantic = {
            "id": element.get("id"),
            "type": element_type,
            "system": self.detect_system(element_type),
            "semantic_role": self.detect_role(element_type),
            "behavior": self.detect_behavior(element_type)
        }

        return semantic


    def detect_system(self, element_type):

        structural = [
            "column",
            "beam",
            "slab",
            "wall"
        ]

        if element_type in structural:
            return "structural"

        return "architectural"


    def detect_role(self, element_type):

        roles = {

            "column":
            "vertical_load_bearing",

            "beam":
            "horizontal_load_transfer",

            "slab":
            "floor_load_distribution",

            "wall":
            "spatial_boundary"

        }

        return roles.get(
            element_type,
            "unknown"
        )


    def detect_behavior(self, element_type):

        behaviors = {

            "column":
            "compression",

            "beam":
            "bending",

            "slab":
            "surface_load",

            "wall":
            "enclosure"

        }

        return behaviors.get(
            element_type,
            "undefined"
        )


    def process(self, elements):

        output = []

        for element in elements:
            output.append(
                self.analyze_element(element)
            )

        return {

            "engine":
            f"semantic_engine_v{self.VERSION}",

            "status":
            "completed",

            "elements":
            output
        }