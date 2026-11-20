class KnowledgeMergeEngine:


    VERSION = "1.1"



    def __init__(self):

        print(
            "🧠 KNOWLEDGE MERGE ENGINE v1.1 ONLINE"
        )



    # ==================================================
    # HELPERS
    # ==================================================

    def add_unique(
        self,
        target,
        value
    ):

        if value not in target:

            target.append(value)



    # ==================================================
    # ZONE GENERATOR
    # ==================================================

    def generate_zones(
        self,
        intent
    ):


        if "zones" not in intent:

            intent["zones"] = {
                "public": [],
                "semi_public": [],
                "private": [],
                "service": [],
                "commercial": [],
                "external": []
            }



        for space in intent.get(
            "spaces",
            []
        ):


            # --------------------------
            # Public
            # --------------------------

            if space in [

                "lobby",
                "public_circulation",
                "food_court",
                "waiting_area",
                "reception"

            ]:

                self.add_unique(
                    intent["zones"]["public"],
                    space
                )



            # --------------------------
            # Commercial
            # --------------------------

            elif space in [

                "retail",
                "shop",
                "office_room",
                "store"

            ]:

                self.add_unique(
                    intent["zones"]["commercial"],
                    space
                )



            # --------------------------
            # Service
            # --------------------------

            elif space in [

                "parking",
                "storage",
                "service_core",
                "mechanical_room",
                "electrical_room"

            ]:

                self.add_unique(
                    intent["zones"]["service"],
                    space
                )


            # --------------------------
            # Semi Public
            # --------------------------

            elif space in [

                "living_room",
                "dining",
                "family_room"

            ]:

                self.add_unique(
                    intent["zones"]["semi_public"],
                    space
                )



            # --------------------------
            # Private
            # --------------------------

            elif space in [

                "bedroom",
                "private_room",
                "master_bedroom"

            ]:

                self.add_unique(
                    intent["zones"]["private"],
                    space
                )

            elif space in [
                "living_room",
                "dining"
            ]:
                self.add_unique(
                    intent["zones"]["semi_public"],
                    space
                )



        return intent



    # ==================================================
    # MERGE KNOWLEDGE
    # ==================================================

    def merge(
        self,
        intent
    ):


        knowledge = intent.get(
            "knowledge",
            {}
        )


        # اگر knowledge وجود ندارد
        # فقط zone ها را بساز

        if knowledge:


            # ==================================================
            # REQUIRED SPACES
            # ==================================================

            for space in knowledge.get(
                "required_spaces",
                []
            ):

                self.add_unique(
                    intent["spaces"],
                    space
                )



            # ==================================================
            # OPTIONAL SPACES
            # ==================================================
            #
            # ARCHITECTURAL_REQUIREMENT_GROUNDING_V1 — an OPTIONAL space is a
            # design suggestion the knowledge base offers, not a requirement
            # the user stated. Promoting it into `intent["spaces"]` made a bare
            # "villa" request assert a POOL and a TERRACE, because
            # `PromptBuilder` renders that field as "functional spaces
            # including …". The evidence stays available in
            # `intent["knowledge"]["optional_spaces"]`; a user-named space is
            # still added by the resolver's SPACE DETECTION.


            # ==================================================
            # RELATIONSHIPS
            # ==================================================

            if "relationships" not in intent:

                intent["relationships"] = []



            for relation in knowledge.get(
                "relationships",
                []
            ):


                if relation not in intent["relationships"]:

                    intent["relationships"].append(
                        relation
                    )



            # ==================================================
            # CATEGORY
            # ==================================================

            if knowledge.get(
                "category"
            ):

                intent["category"] = (
                    knowledge["category"]
                )



        # ==================================================
        # ZONE UPDATE
        # ==================================================

        intent = self.generate_zones(
            intent
        )



        return intent