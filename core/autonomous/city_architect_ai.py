class CityArchitectAI:

    def __init__(self):

        self.city_memory = []

    # ======================
    # GENERATE CITY BLOCK
    # ======================
    def generate_city_block(self, constraints):

        block = {
            "buildings": [],
            "roads": [],
            "parks": []
        }

        density = constraints.get("density", 0.5)

        # buildings
        for i in range(int(density * 10)):

            block["buildings"].append({
                "id": f"B{i}",
                "floors": 3 + i % 5,
                "type": "residential"
            })

        # roads
        block["roads"].append({
            "type": "main_road",
            "width": 12
        })

        # parks
        if density < 0.6:

            block["parks"].append({
                "type": "green_space",
                "area": 200
            })

        return block

    # ======================
    # EVALUATE CITY
    # ======================
    def evaluate_city(self, block):

        score = 100

        if len(block["buildings"]) > 15:
            score -= 20

        if len(block["parks"]) == 0:
            score -= 30

        return {
            "score": score,
            "status": "ok" if score > 70 else "needs improvement"
        }

    # ======================
    # STORE CITY EXPERIENCE
    # ======================
    def store_experience(self, block, evaluation):

        self.city_memory.append({
            "block": block,
            "evaluation": evaluation
        })

    # ======================
    # RUN FULL LOOP
    # ======================
    def run(self, constraints):

        block = self.generate_city_block(constraints)
        evaluation = self.evaluate_city(block)

        self.store_experience(block, evaluation)

        return {
            "city_block": block,
            "evaluation": evaluation
        }