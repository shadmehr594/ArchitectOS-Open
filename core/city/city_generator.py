import random


class CityGenerator:

    def generate_city(self, blocks=5):

        city = {
            "blocks": [],
            "roads": [],
            "meta": {}
        }

        for i in range(blocks):

            block = self._generate_block(i)
            city["blocks"].append(block)

        city["roads"] = self._generate_roads(blocks)

        city["meta"] = {
            "blocks": blocks,
            "type": "procedural_city_v1"
        }

        return city

    # ======================
    # BLOCK GENERATION
    # ======================
    def _generate_block(self, index):

        return {
            "id": f"BLOCK_{index}",
            "buildings": [
                self._generate_building()
                for _ in range(random.randint(3, 6))
            ]
        }

    # ======================
    # BUILDING GENERATION
    # ======================
    def _generate_building(self):

        return {
            "height": random.randint(2, 10),
            "footprint": random.randint(30, 120),
            "type": random.choice(["residential", "commercial"])
        }

    # ======================
    # ROAD SYSTEM
    # ======================
    def _generate_roads(self, blocks):

        roads = []

        for i in range(blocks - 1):

            roads.append({
                "from": f"BLOCK_{i}",
                "to": f"BLOCK_{i+1}",
                "type": "main_road"
            })

        return roads