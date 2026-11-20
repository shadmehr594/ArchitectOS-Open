# ==========================================================
# ArchitectOS Conversation Memory v25
# Conversation Storage + Write Back Layer
# ==========================================================


import time

from .memory_cleaner import MemoryCleaner



class ConversationMemory:


    VERSION = "v25"



    def __init__(self):


        self.messages = []


        print(
            "🧠 CONVERSATION MEMORY v25 ONLINE"
        )



    # ======================================================
    # ADD MESSAGE
    # ======================================================

    def add(
        self,
        message,
        message_type="chat",
        session_id=None
    ):


        item = {

            "type":
                message_type,

            "message":
                message,

            "timestamp":
                time.time(),

            # GENERAL_CONVERSATION_CONTINUITY_V1 — this store is ONE
            # in-process list shared by every session. Tagging each turn with
            # its session lets `history()` return a single conversation
            # instead of a cross-session jumble. `None` keeps the old
            # behaviour for every existing caller.
            "session_id":
                session_id

        }


        self.messages.append(
            item
        )


        return item



    # ======================================================
    # HISTORY
    # ======================================================

    def history(
        self,
        limit=20,
        session_id=None
    ):


        if session_id is None:

            return self.messages[-limit:]


        scoped = [

            item

            for item in self.messages

            if isinstance(item, dict)
            and item.get("session_id") == session_id

        ]


        return scoped[-limit:]



    # ======================================================
    # REPLACE ONE SESSION  (SENT_MESSAGE_EDIT_V1)
    #
    # This store is an in-process CACHE, not the source of truth: the
    # persisted transcript in `chat.json` is. A message revision rebuilds
    # exactly one session's history from the PERSISTED prefix, so the
    # model can never inherit a downstream branch that no longer applies
    # — and, after a restart (when this store is empty), it recovers the
    # context that actually exists on disk instead of starting blind.
    #
    # Only entries carrying the SAME session_id are removed, so two
    # projects can never affect each other.
    # ======================================================

    def replace_session(
        self,
        session_id,
        entries
    ):

        if session_id is None:

            return 0


        self.messages = [

            item

            for item in self.messages

            if not (
                isinstance(item, dict)
                and item.get("session_id") == session_id
            )

        ]


        added = 0


        for item in (entries or []):

            if not isinstance(item, dict):

                continue

            role = item.get("role")

            if role not in ("user", "assistant"):

                continue

            self.add(
                str(item.get("text") or ""),
                role,
                session_id=session_id
            )

            added += 1


        return added



    # ======================================================
    # CLEAR
    # ======================================================

    def clear(
        self
    ):


        self.messages = []



        return True





# ==========================================================
# Conversation Write Back
# ==========================================================


class ConversationWriteBack:


    VERSION = "v1"



    def __init__(
        self,
        memory_manager
    ):


        self.memory = memory_manager


        print(
            "🧠 CONVERSATION WRITE-BACK v1 ONLINE"
        )



    def store(
        self,
        user,
        assistant,
        session_id=None
    ):
        """Persist one user/assistant pair as PLAIN TEXT.

        CONVERSATION_CONTINUITY_V3 — the canonical write boundary.

        Callers used to hand this method `str(response)`, i.e. the whole
        response envelope (`{'type': 'chat', 'engine': ..., 'result': ...}`),
        so memory held serialized envelopes instead of what the assistant
        actually said. Every later reader then had to guess the shape back
        out of a Python repr (and `MemoryCleaner.clean` still does that as a
        fallback for historical rows).

        Normalising HERE, at the single writer, fixes every call site at once
        - including the five in `chat_architect` and any future caller - and
        keeps the stored contract ("message" is text) honest. `MemoryCleaner`
        is reused rather than reimplemented; it already knows how to reduce a
        dict or a dict-string to its message text.
        """

        cleaner = MemoryCleaner()

        user_text = cleaner.clean(user)

        assistant_text = cleaner.clean(assistant)

        try:


            self.memory.save_conversation(
                user_text,
                "user",
                session_id=session_id
            )


            self.memory.save_conversation(
                assistant_text,
                "assistant",
                session_id=session_id
            )


            return True



        except Exception as e:


            print(
                "❌ WRITE-BACK ERROR:",
                repr(e)
            )


            return False





# ==========================================================
# FACTORY
# ==========================================================


def create_writeback(
    memory_manager
):


    return ConversationWriteBack(
        memory_manager
    )