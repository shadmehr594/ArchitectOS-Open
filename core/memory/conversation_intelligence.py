# ==========================================================
# ArchitectOS Conversation Intelligence v29
# Conversation Understanding + Memory Cleaning Layer
# ==========================================================


from .memory_cleaner import MemoryCleaner



class ConversationIntelligence:


    VERSION = "v29"



    def __init__(self):


        self.cleaner = MemoryCleaner()


        print(
            "🧠 CONVERSATION INTELLIGENCE v29 ONLINE"
        )



    # ======================================================
    # ANALYZE
    # ======================================================

    #: CONVERSATION_CONTINUITY_V3 — bound on the ordered transcript that is
    #: rendered into the chat prompt. The store keeps 20 turns; the prompt
    #: only ever needs the recent dialogue, and the newest turn is always
    #: kept regardless of this limit (see `_ordered_turns`).
    MAX_TRANSCRIPT_TURNS = 12

    def _ordered_turns(
        self,
        history
    ):
        """Return the dialogue in CHRONOLOGICAL order.

        `user_messages` and `assistant_messages` are two parallel lists, so
        turn order and role alternation are lost by construction. A follow-up
        such as "now make it iterative" only means something against the
        assistant turn that preceded it, so the order has to be carried
        explicitly.

        The newest turn is always retained, even if it alone exceeds the
        limit, so the immediate referent can never be trimmed away.
        """

        turns = []

        for item in history:

            if not isinstance(item, dict):

                continue

            msg_type = item.get("type", "")

            if msg_type == "user":

                role = "user"

            elif msg_type in ("assistant", "chat"):

                role = "assistant"

            else:

                continue

            text = str(item.get("text") or "").strip()

            if not text:

                continue

            turns.append({
                "role": role,
                "text": text,
            })

        if len(turns) > self.MAX_TRANSCRIPT_TURNS:

            turns = turns[-self.MAX_TRANSCRIPT_TURNS:]

        return turns

    def analyze(
        self,
        history
    ):


        result = {


            "user_messages": [],


            "assistant_messages": [],


            # CONVERSATION_CONTINUITY_V3 — ordered, role-tagged dialogue.
            "turns": [],


            "topics": [],


            "summary": {}

        }



        # ----------------------------------
        # CLEAN HISTORY
        # ----------------------------------

        history = self.cleaner.clean_history(
            history
        )


        # ----------------------------------
        # ORDERED TRANSCRIPT
        #
        # Built from the cleaned history so the text is already plain, and
        # before the legacy parallel lists so both views describe the same
        # turns.
        # ----------------------------------

        result["turns"] = self._ordered_turns(
            history
        )


        for item in history:



            if not isinstance(
                item,
                dict
            ):

                continue



            message = item.get(
                "text",
                ""
            )



            msg_type = item.get(
                "type",
                ""
            )



            # ----------------------------------
            # USER / ASSISTANT SEPARATION
            # ----------------------------------

            if msg_type == "user":


                result["user_messages"].append(
                    message
                )



            elif msg_type in [
                "assistant",
                "chat"
            ]:


                result["assistant_messages"].append(
                    message
                )



            # ----------------------------------
            # TOPIC DETECTION
            # ----------------------------------

            text = message.lower()



            if any(
                x in text
                for x in [
                    "villa",
                    "house",
                    "ویلا",
                    "خانه",
                    "طراحی"
                ]
            ):


                result["topics"].append(
                    "design"
                )



            elif any(
                x in text
                for x in [
                    "image",
                    "draw",
                    "render",
                    "تصویر"
                ]
            ):


                result["topics"].append(
                    "image"
                )



            else:


                result["topics"].append(
                    "chat"
                )



        # ----------------------------------
        # SUMMARY
        # ----------------------------------

        result["summary"] = {


            "user_count":

                len(
                    result["user_messages"]
                ),



            "assistant_count":

                len(
                    result["assistant_messages"]
                ),



            "topic_count":

                len(
                    result["topics"]
                ),



            "last_topic":

                result["topics"][-1]

                if result["topics"]

                else "unknown"

        }



        return result