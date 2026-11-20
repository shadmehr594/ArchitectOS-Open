# ==========================================================
# ArchitectOS Chat Runtime v29
# Final Integration Layer
# API Ready Runtime Gateway
# Built on Chat Runtime v28
# Metadata Normalization Layer
# ==========================================================


import uuid
import time

from core.chat.chat_runtime_v28 import ChatRuntimeV28
from core.chat.runtime_response import RuntimeResponse



class ChatRuntimeV29:


    VERSION = "29.0"



    def __init__(self):


        self.runtime = ChatRuntimeV28()


        print(
            "🚀 CHAT RUNTIME v29 ONLINE"
        )



    # ======================================================
    # METADATA NORMALIZATION
    # ======================================================

    def _normalize_metadata(
        self,
        result_metadata,
        session_id,
        request_metadata
    ):


        metadata = {}


        # inherit safe metadata only

        if isinstance(
            result_metadata,
            dict
        ):

            metadata.update(
                result_metadata
            )



        # remove old runtime traces

        metadata.pop(
            "parent_runtime",
            None
        )


        metadata.pop(
            "runtime_version",
            None
        )



        # final v29 contract

        metadata.update(


            {


                "runtime_version":

                    self.VERSION,


                "session_id":

                    session_id,


                "timestamp":

                    time.time(),


                "request":

                    request_metadata


            }


        )


        return metadata




    # ======================================================
    # RUN
    # ======================================================

    def run(
        self,
        user,
        session_id=None,
        metadata=None
    ):


        if session_id is None:


            session_id = str(
                uuid.uuid4()
            )



        if metadata is None:


            metadata = {}



        try:


            result = self.runtime.run(

                user,

                session_id,

                metadata

            )



            if not isinstance(
                result,
                dict
            ):


                result = {


                    "type":

                        "chat",


                    "engine":

                        "runtime",


                    "result":

                        result,


                    "status":

                        "success"


                }




            normalized_metadata = self._normalize_metadata(

                result.get(
                    "metadata",
                    {}
                ),

                session_id,

                metadata

            )




            return RuntimeResponse(


                response_type=result.get(

                    "type",

                    "chat"

                ),


                engine=result.get(

                    "engine",

                    "chat_runtime"

                ),


                result=result.get(

                    "result"

                ),


                metadata=normalized_metadata,


                status=result.get(

                    "status",

                    "success"

                )

            ).json()




        except Exception as e:


            return {


                "type":

                    "error",


                "engine":

                    "chat_runtime_v29",


                "result":

                    str(e),


                "metadata":{


                    "runtime_version":

                        self.VERSION,


                    "session_id":

                        session_id,


                    "timestamp":

                        time.time()


                },


                "status":

                    "failed"


            }





# ==========================================================
# SINGLETON
# ==========================================================


chat_runtime = ChatRuntimeV29()