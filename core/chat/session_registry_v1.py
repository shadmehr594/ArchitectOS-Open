# ==========================================================
# ArchitectOS Session Registry v1
#
# CHAT_LANGUAGE_02
#
# Problem
#   ConversationState and ArchitecturalConversationContextStore
#   are module-level singletons.  app.py holds ONE ChatArchitect,
#   so every independent HTTP client shared the same conversation
#   state and the same accumulated architectural context.
#
# Scope of this fix (deliberately minimal)
#   - session-keyed in-memory state objects
#   - NO persistence redesign
#   - NO memory-layer redesign
#
# Backward compatibility
#   When no session id is supplied, the legacy global singletons are
#   returned unchanged, so existing single-client behaviour and all
#   existing tests keep working exactly as before.
# ==========================================================


CONTRACT = "SessionRegistryV1"
VERSION = "1.0"


import threading


# Thread-bound current session.
# Flask serves requests on multiple threads, so the "current session"
# must be thread-local, never a plain instance attribute.
_local = threading.local()


# Sentinel used when the caller supplies no session id.
DEFAULT_SESSION_KEY = "__default__"


# Guard against unbounded growth from hostile/random session ids.
MAX_SESSIONS = 512



class SessionRegistry:

    VERSION = VERSION

    def __init__(self):

        self._sessions = {}

        print(
            "🗂️ SESSION REGISTRY v1.0 ONLINE (session-keyed state)"
        )


    # ======================================================
    # KEY NORMALIZATION
    # ======================================================

    @staticmethod
    def normalize_key(session_id):

        if session_id is None:

            return DEFAULT_SESSION_KEY

        key = str(session_id).strip()

        if not key:

            return DEFAULT_SESSION_KEY

        # keep it bounded / filesystem-and-log safe
        if len(key) > 128:

            key = key[:128]

        return key


    # ======================================================
    # RESOLVE
    # ======================================================

    def resolve(self, session_id=None):
        """Return the state bundle for a session id.

        Default session -> legacy global singletons (unchanged
        behaviour).  Any other id -> dedicated per-session objects.
        """

        key = self.normalize_key(session_id)

        if key == DEFAULT_SESSION_KEY:

            from core.chat.conversation_state import conversation_state

            from core.chat.architectural_conversation_context_v1 import (
                architectural_conversation_context,
            )

            return {

                "contract": CONTRACT,
                "session_id": key,

                "isolated": False,

                "conversation_state": conversation_state,

                "architectural_context": architectural_conversation_context,

            }


        bundle = self._sessions.get(key)

        if bundle is None:

            if len(self._sessions) >= MAX_SESSIONS:

                # drop the oldest entry (insertion ordered dict)
                self._sessions.pop(
                    next(iter(self._sessions))
                )

            bundle = self._create_bundle(key)

            self._sessions[key] = bundle


        return bundle


    def _create_bundle(self, key):

        from core.chat.conversation_state import ConversationState

        from core.chat.architectural_conversation_context_v1 import (
            ArchitecturalConversationContextStore,
        )

        return {

            "contract": CONTRACT,
            "session_id": key,

            "isolated": True,

            "conversation_state": ConversationState(),

            "architectural_context": ArchitecturalConversationContextStore(),

        }


    # ======================================================
    # THREAD-BOUND CURRENT SESSION
    # ======================================================

    def begin(self, session_id=None):
        """Bind a session to the current thread for this request."""

        bundle = self.resolve(session_id)

        _local.bundle = bundle

        return bundle


    def end(self):

        _local.bundle = None


    def current(self):

        return getattr(_local, "bundle", None)


    def current_state(self, fallback=None):
        """Conversation state for the current thread's session."""

        bundle = self.current()

        if bundle:

            return bundle["conversation_state"]

        return fallback


    def current_architectural_context(self, fallback=None):
        """Architectural context for the current thread's session."""

        bundle = self.current()

        if bundle:

            return bundle["architectural_context"]

        return fallback


    # ======================================================
    # LIFECYCLE
    # ======================================================

    def reset(self, session_id=None):

        key = self.normalize_key(session_id)

        if key == DEFAULT_SESSION_KEY:

            bundle = self.resolve(key)

            bundle["conversation_state"].state.clear()

            bundle["architectural_context"].reset("session_reset")

            return bundle

        self._sessions.pop(key, None)

        return self.resolve(key)


    def known_sessions(self):

        return list(self._sessions.keys())


    def session_count(self):

        return len(self._sessions)



# ==========================================================
# SINGLETON
# ==========================================================

session_registry = SessionRegistry()
