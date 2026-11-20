class ArchitecturalKnowledgeReasoner:


    VERSION = "1.0"



    def __init__(self):

        print(
            "🧠 ARCHITECTURAL KNOWLEDGE REASONER v1.0 ONLINE"
        )



    # ==================================================
    # HELPERS
    # ==================================================

    def append_unique(
        self,
        target,
        value
    ):

        if value not in target:

            target.append(value)



    # ==================================================
    # APPLY
    # ==================================================

    def apply(
        self,
        intent
    ):


        knowledge = intent.get(
            "knowledge",
            {}
        )


        if not knowledge:

            return intent



        # ==================================================
        # REQUIRED SPACES
        # ==================================================

        for space in knowledge.get(
            "required_spaces",
            []
        ):

            self.append_unique(
                intent["spaces"],
                space
            )



        # ==================================================
        # OPTIONAL SPACES
        # ==================================================

        optional_spaces = knowledge.get(
            "optional_spaces",
            []
        )


        for space in optional_spaces:


            self.append_unique(
                intent["spaces"],
                space
            )



        # ==================================================
        # RELATIONSHIPS
        # ==================================================

        for relation in knowledge.get(
            "relationships",
            []
        ):

            if relation not in intent["relationships"]:

                intent["relationships"].append(
                    relation
                )



        # ==================================================
        # ZONE GENERATION
        # ==================================================

        for space in intent["spaces"]:


            if space in [
                "lobby",
                "public_circulation",
                "waiting_area"
            ]:

                self.append_unique(
                    intent["zones"]["public"],
                    space
                )



            elif space in [
                "retail",
                "shop",
                "office_room"
            ]:

                self.append_unique(
                    intent["zones"]["commercial"],
                    space
                )



            elif space in [
                "parking",
                "storage",
                "mechanical_room"
            ]:

                self.append_unique(
                    intent["zones"]["service"],
                    space
                )



            elif space in [
                "bedroom",
                "private_room"
            ]:

                self.append_unique(
                    intent["zones"]["private"],
                    space
                )



        return intent