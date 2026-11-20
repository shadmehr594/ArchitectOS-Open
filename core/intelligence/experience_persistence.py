# ==================================================
# ArchitectOS Experience Persistence Bridge v61.1
# ==================================================


class ExperiencePersistence:


    VERSION = (
        "architectos_experience_persistence_v61.1"
    )


    def __init__(self):

        print(
            "💾 ArchitectOS Experience Persistence v61.1 ACTIVE"
        )

        self.memory_store = []



    # ==================================================
    # STORE EXPERIENCE
    # ==================================================

    def store_experience(
        self,
        experience
    ):


        if not experience:

            return {

                "status":
                "empty_experience"

            }


        if isinstance(
            experience,
            dict
        ):

            experiences = experience.get(
                "experiences",
                []
            )

        else:

            experiences = experience



        if isinstance(
            experiences,
            list
        ):

            self.memory_store.extend(
                experiences
            )


        return {

            "status":
            "stored",

            "memory_nodes":
            len(self.memory_store)

        }



    # ==================================================
    # ADAPTER COMPATIBLE STORE
    # ==================================================

    def store(
        self,
        experience
    ):

        return self.store_experience(
            experience
        )



    # ==================================================
    # RECALL EXPERIENCE
    # ==================================================

    def recall(
        self,
        data=None
    ):


        return {

            "engine":
            self.VERSION,


            "experiences":
            self.memory_store,


            "memory_nodes":
            len(self.memory_store),


            "learned_patterns":
            len(self.memory_store)

        }