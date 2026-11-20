# ==================================================
# ArchitectOS Runtime Persistence Adapter v81
# ==================================================

import json
import os


class ArchitectOSRuntimePersistence:


    VERSION = "81.0"



    def __init__(
        self,
        storage_path="storage/architectos_sessions.json"
    ):


        print(
            "💾 ArchitectOS Runtime Persistence v81.0 ACTIVE"
        )


        self.storage_path = storage_path


        self._ensure_storage()



    # ==================================================
    # STORAGE INIT
    # ==================================================

    def _ensure_storage(
        self
    ):


        folder = os.path.dirname(
            self.storage_path
        )


        if folder and not os.path.exists(folder):

            os.makedirs(
                folder
            )


        if not os.path.exists(
            self.storage_path
        ):

            with open(
                self.storage_path,
                "w",
                encoding="utf-8"
            ) as file:

                json.dump(
                    {},
                    file
                )



    # ==================================================
    # SAVE SESSION
    # ==================================================

    def save(
        self,
        session_id,
        data
    ):


        sessions = self.load_all()


        sessions[session_id] = data



        with open(
            self.storage_path,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                sessions,
                file,
                indent=4
            )


        return {

            "status":
            "saved",

            "session":
            session_id

        }



    # ==================================================
    # LOAD SESSION
    # ==================================================

    def load(
        self,
        session_id
    ):


        sessions = self.load_all()


        return sessions.get(

            session_id,

            {}

        )



    # ==================================================
    # LOAD ALL
    # ==================================================

    def load_all(
        self
    ):


        with open(
            self.storage_path,
            "r",
            encoding="utf-8"
        ) as file:

            return json.load(
                file
            )