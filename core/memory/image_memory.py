# ==========================================================
# ArchitectOS Image Memory v53
# Last Generated Image Resolver
# ==========================================================


import os
import json



MEMORY_FILE = os.path.join(
    os.path.dirname(__file__),
    "image_memory.json"
)



class ImageMemory:


    def __init__(self):

        self.data = {

            "last_image": None

        }


        self.load()


        print(
            "🖼️ Image Memory v53 ACTIVE"
        )



    # ======================================================
    # LOAD
    # ======================================================

    def load(self):

        if os.path.exists(
            MEMORY_FILE
        ):

            try:

                with open(
                    MEMORY_FILE,
                    "r",
                    encoding="utf-8"
                ) as f:

                    self.data = json.load(f)


            except:

                pass



    # ======================================================
    # SAVE
    # ======================================================

    def save(self):

        with open(
            MEMORY_FILE,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                self.data,
                f,
                indent=4
            )



    # ======================================================
    # UPDATE
    # ======================================================

    def update_image(
        self,
        image_path
    ):


        self.data["last_image"] = image_path

        self.save()


        print(
            "🧠 IMAGE MEMORY UPDATED:",
            image_path
        )



    # ======================================================
    # GET LAST IMAGE
    # ======================================================

    def get_last_image(self):


        image = self.data.get(
            "last_image"
        )


        if image and os.path.exists(image):

            return image


        return None





image_memory = ImageMemory()