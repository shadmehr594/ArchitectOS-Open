# ==========================================================
# ArchitectOS User Profile Memory v4
# Persistent Structured User Understanding Layer
# ==========================================================


import json
import os
import time



class UserProfileMemory:


    VERSION = "v4.0"



    def __init__(self):

        self.file = os.path.join(
            os.path.dirname(__file__),
            "user_profile.json"
        )


        self.profile = self.load()


        print(
            "👤 USER PROFILE MEMORY v4 ONLINE"
        )



    # ======================================================
    # LOAD
    # ======================================================

    def load(self):

        if not os.path.exists(self.file):

            return self.default_profile()


        try:

            with open(
                self.file,
                "r",
                encoding="utf-8"
            ) as f:

                data = json.load(f)


                if isinstance(data, dict):

                    return data


        except Exception:

            pass


        return self.default_profile()



    # ======================================================
    # DEFAULT
    # ======================================================

    def default_profile(self):

        return {

            "user": {},

            "family": {},

            "preferences": {

                "domains": [],

                "styles": [],

                "response_mode": "normal"

            },

            "projects": {

                "active_projects": []

            },

            "interests": [],

            "metadata": {

                "created": time.time()

            }

        }



    # ======================================================
    # SAVE
    # ======================================================

    def save(self):

        with open(
            self.file,
            "w",
            encoding="utf-8"
        ) as f:


            json.dump(
                self.profile,
                f,
                ensure_ascii=False,
                indent=2
            )



    # ======================================================
    # UPDATE v4
    # Supports:
    #
    # update(section,key,value)
    # update(dict)
    #
    # ======================================================

    def update(
        self,
        section,
        key=None,
        value=None
    ):


        # ----------------------------------
        # FULL PROFILE MERGE
        # ----------------------------------

        if isinstance(
            section,
            dict
        ):


            self.merge(
                section
            )


            self.save()

            return True



        # ----------------------------------
        # SINGLE VALUE UPDATE
        # ----------------------------------

        if section not in self.profile:

            self.profile[section] = {}



        self.profile[section][key] = value


        self.profile["metadata"] = {

            "updated":
                time.time()

        }


        self.save()


        return True



    # ======================================================
    # MERGE PROFILE
    # ======================================================

    def merge(
        self,
        data
    ):


        # ==========================================
        # NORMALIZE USER NAME FORMAT
        # user_name -> user.name
        # ==========================================

        if "user_name" in data:

            self.profile.setdefault(
                "user",
                {}
            )

            self.profile["user"]["name"] = (
                data["user_name"]
            )



        for section, values in data.items():


            if section in (
                "metadata",
                "user_name"
            ):

                continue



            if isinstance(
                values,
                dict
            ):


                current = self.profile.setdefault(
                    section,
                    {}
                )


                for key, value in values.items():

                    current[key] = value



            elif isinstance(
                values,
                list
            ):


                current = self.profile.setdefault(
                    section,
                    []
                )


                for item in values:

                    if item not in current:

                        current.append(item)



        self.profile["metadata"] = {

            "updated":
                time.time()

        }



    # ======================================================
    # GET
    # ======================================================

    def get_profile(
        self
    ):

        return self.profile



    # ======================================================
    # SUMMARY
    # ======================================================

    def summary(
        self
    ):


        return {

            "user":

                len(
                    self.profile.get(
                        "user",
                        {}
                    )
                ),


            "family":

                len(
                    self.profile.get(
                        "family",
                        {}
                    )
                ),


            "preferences":

                len(
                    self.profile.get(
                        "preferences",
                        {}
                    )
                ),


            "projects":

                len(
                    self.profile.get(
                        "projects",
                        {}
                    )
                ),


            "interests":

                len(
                    self.profile.get(
                        "interests",
                        []
                    )
                )

        }



# ==========================================================
# SINGLETON
# ==========================================================


user_profile_memory = UserProfileMemory()