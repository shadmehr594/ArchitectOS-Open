class DesignAI:

    def __init__(self):
        self.rules = {
            "house": ["living_room", "kitchen", "bathroom", "bedroom", "stairs"],
            "modern": ["open_space", "minimal_walls"],
            "3_floor": ["stairs", "vertical_connectivity"]
        }

    def parse_intent(self, text: str):

        text = text.lower()

        plan = {
            "spaces": [],
            "features": [],
            "style": "unknown"
        }

        # basic keyword detection
        if "house" in text:
            plan["spaces"].extend(self.rules["house"])

        if "modern" in text:
            plan["style"] = "modern"
            plan["features"].append("open_space_design")

        if "3 floor" in text or "3-floor" in text:
            plan["features"].append("multi_level")
            plan["features"].append("stairs_required")

        # remove duplicates
        plan["spaces"] = list(set(plan["spaces"]))
        plan["features"] = list(set(plan["features"]))

        return plan

    def enhance_grid_plan(self, grid, design_plan):

        for floor_id, floor in grid.items():

            floor["ai_design"] = {
                "assigned_spaces": design_plan["spaces"],
                "style": design_plan["style"],
                "features": design_plan["features"]
            }

        return grid