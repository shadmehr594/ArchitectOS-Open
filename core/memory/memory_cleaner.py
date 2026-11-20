# ==========================================================
# ArchitectOS Memory Cleaner v30
# Structured Conversation Memory Normalizer
# ==========================================================


import ast



class MemoryCleaner:


    VERSION = "v30"



    def __init__(self):

        print(
            "🧹 MEMORY CLEANER v30 ONLINE"
        )



    # ======================================================
    # CLEAN SINGLE MESSAGE
    # ======================================================

    def clean(
        self,
        message
    ):


        if message is None:

            return ""



        # direct text

        if isinstance(
            message,
            str
        ):


            text = message.strip()



            # try parse dict string

            if text.startswith("{") and text.endswith("}"):


                try:

                    data = ast.literal_eval(
                        text
                    )


                    if isinstance(
                        data,
                        dict
                    ):


                        if "result" in data:

                            return str(
                                data["result"]
                            )


                        if "message" in data:

                            return str(
                                data["message"]
                            )


                except Exception:

                    pass



            return text



        # dictionary

        if isinstance(
            message,
            dict
        ):


            if "result" in message:

                return str(
                    message["result"]
                )


            if "message" in message:

                return str(
                    message["message"]
                )



        return str(message)



    # ======================================================
    # CLEAN HISTORY
    # ======================================================

    def clean_history(
        self,
        history
    ):


        cleaned = []



        for item in history:


            if not isinstance(
                item,
                dict
            ):

                continue



            cleaned.append({

                "text":
                    self.clean(
                        item.get(
                            "message"
                        )
                    ),


                "type":
                    item.get(
                        "type",
                        "chat"
                    ),


                "timestamp":
                    item.get(
                        "timestamp",
                        0
                    )

            })



        return cleaned