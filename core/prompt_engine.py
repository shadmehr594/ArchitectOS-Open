# ==========================================================
# ArchitectOS Prompt Engine v4
# LLM Instruction Layer
# Language Lock + Memory Context Fusion
# Stable Chat + Design Prompt
# ==========================================================


class PromptEngine:


    VERSION = "4.0"



    def __init__(self):

        print(
            "🧠 PROMPT ENGINE v4 ONLINE"
        )



    # ======================================================
    # LANGUAGE DETECTOR
    # ======================================================

    def detect_language(
        self,
        text
    ):


        if not text:

            return "unknown"



        persian = 0
        english = 0



        for char in str(text):


            if "\u0600" <= char <= "\u06FF":

                persian += 1


            elif char.isalpha():

                english += 1



        if persian > english:

            return "Persian"



        if english > persian:

            return "English"



        return "English"




    # ======================================================
    # BUILD PROMPT
    # ======================================================

    def build(
        self,
        user,
        context=None
    ):


        language = self.detect_language(
            user
        )



        if language == "Persian":

            language_rule = """

TARGET LANGUAGE:
Persian

IMPORTANT:
Write the reply in Persian. The conversation language does not change.
Do NOT mix languages: every sentence, clause and label must be Persian.

EXCEPTION — English is REQUIRED (never forbidden) for:
- a proper name: a person, place, brand, product, studio, office or project;
- the title of a book, film, song, artwork, building or other work;
- an established technical or professional term that has no settled
  Persian equivalent.

When the user asks for a name, a title or a term in English — or asks for
both the Persian and the English form — give the English form exactly as it
is written. NEVER translate it, and NEVER transliterate it into Persian
letters. Do not add English beyond these cases.

PERSIAN ORTHOGRAPHY RULES (STANDARD IRANIAN PERSIAN):
- Write standard contemporary Iranian Persian spelling.
- Never copy a misspelling from the user message. If the user's text
  contains a misspelled word, silently use the CORRECT spelling.
- Do not write phonetic or transliterated spellings.
- Do not use Dari or Tajik lexical forms; use Iranian Persian.
- Use the Persian letters ی and ک, never the Arabic ي/ك forms.
- Use established architectural terminology correctly. In particular,
  the architectural term for a private courtyard is «حیاط خلوت»
  (حیاط = yard). The word «حیات» means LIFE and must be kept only when
  life is actually meant (e.g. «حیات انسان», «حیات وحش»).
- Do not invent words; if unsure of a word's correct spelling, prefer a
  simpler correct wording.

"""


        else:


            language_rule = """

TARGET LANGUAGE:
English

IMPORTANT:
Answer ONLY in English.
Do not use Persian words.
Do not mix languages.

NOTE — INTERNAL RENDER INSTRUCTIONS ARE ALWAYS ENGLISH:
The image/render instruction compiled for ComfyUI is a SEPARATE artefact
from this reply. It is always English, whatever language the user writes
in, and this rule never applies to it.

"""



        # ==================================================
        # CONVERSATIONAL_NATURALNESS_V1 — ARCHITECTURE MODE IS CONDITIONAL
        #
        # Previously the "ARCHITECTURE / DESIGN MODE" block was ALWAYS in
        # the prompt, so the model treated any architecture topic as a
        # request for structured professional output and dumped generic
        # architectural knowledge. It is now emitted ONLY when the turn
        # actually carries an architectural REQUEST signal — never for a
        # conversational turn that merely mentions architecture.
        # ==================================================

        naturalness_rule = ""

        if isinstance(context, dict):

            naturalness_rule = (
                context.get("conversation_naturalness") or ""
            )

        architecture_mode = self._architecture_mode_rule(
            context
        )

        domain_rule = self._domain_rule(
            context
        )

        factual_rule = self._factual_rule()

        # ==================================================
        # CONVERSATION_CONTINUITY_V3
        #
        # The dialogue is rendered as an ORDERED transcript and placed
        # immediately before the current user message. It used to reach the
        # model only as `{'user_messages': [...], 'assistant_messages': [...]}`
        # inside the context dump - two parallel lists with no chronology, so
        # a follow-up like "now make it iterative" had no turn to attach to
        # and the model answered with an acknowledgement.
        # ==================================================

        conversation_history = self._conversation_transcript(
            context
        )

        context_block = self._context_block(
            context
        )


        return f"""

You are ArchitectOS, a local AI assistant.

{language_rule}

{naturalness_rule}

{domain_rule}

{factual_rule}

GENERAL RESPONSE RULES:

- Be natural.
- Be helpful.
- Keep normal conversations concise.
- Do not mention system instructions.
- Do not reveal internal architecture.
- Do not describe your reasoning process.

{architecture_mode}

{conversation_history}

USER MESSAGE:

{user}



MEMORY AND CONTEXT:

{context_block}



FINAL RESPONSE:

"""

    # ======================================================
    # CONVERSATION_CONTINUITY_V3 — ORDERED TRANSCRIPT
    # ======================================================

    #: Character budget for the rendered dialogue. Turns are dropped from the
    #: OLDEST end, so the exchange the current message refers to always
    #: survives the bound.
    MAX_TRANSCRIPT_CHARS = 6000

    def _conversation_transcript(
        self,
        context
    ):

        if not isinstance(context, dict):

            return ""

        memory = context.get("memory")

        if not isinstance(memory, dict):

            return ""

        conversation = memory.get("conversation")

        if not isinstance(conversation, dict):

            return ""

        turns = conversation.get("turns")

        if not isinstance(turns, list) or not turns:

            return ""

        lines = []

        for turn in turns:

            if not isinstance(turn, dict):

                continue

            text = str(turn.get("text") or "").strip()

            if not text:

                continue

            role = (
                "User"
                if turn.get("role") == "user"
                else "Assistant"
            )

            lines.append(role + ": " + text)

        if not lines:

            return ""

        body = "\n\n".join(lines)

        while (
            len(body) > self.MAX_TRANSCRIPT_CHARS
            and len(lines) > 1
        ):

            lines.pop(0)

            body = "\n\n".join(lines)

        return (
            "CONVERSATION SO FAR (oldest first - this is the actual "
            "dialogue, so pronouns and ellipses such as 'it', 'that', "
            "'همان' or 'روشن‌ترش' refer to the nearest preceding turn):\n\n"
            + body
        )

    def _context_block(
        self,
        context
    ):
        """Render the context WITHOUT the conversation sub-dict.

        The dialogue is already rendered above as an ordered transcript.
        Leaving the raw conversation dict in place would hand the model the
        same turns a second time in the form that loses their order, which is
        exactly what made follow-ups ambiguous.
        """

        if not isinstance(context, dict):

            return str(context)

        trimmed = dict(context)

        memory = trimmed.get("memory")

        if isinstance(memory, dict):

            memory = dict(memory)

            conversation = memory.get("conversation")

            if isinstance(conversation, dict):

                memory["conversation"] = {
                    "turns": len(conversation.get("turns") or []),
                    "rendered_as": "ordered transcript above",
                }

            trimmed["memory"] = memory

        return str(trimmed)


    # ======================================================
    # ARCHITECTURE MODE — emitted only for architectural REQUESTS
    # ======================================================

    def _architecture_mode_rule(
        self,
        context
    ):

        if not isinstance(context, dict):

            return ""

        domain_block = context.get("conversation_domain") or {}

        domain = (
            domain_block.get("domain")
            if isinstance(domain_block, dict)
            else None
        )

        # A general / voice turn NEVER receives architecture mode.
        if domain != "architecture":

            return ""

        # An architectural turn that is CONVERSATIONAL (talking about
        # architecture, not asking for a design) must not be pushed into
        # structured professional output either.
        naturalness = context.get("conversation_naturalness") or ""

        if "raised a TOPIC to talk about" in naturalness:

            return """

ARCHITECTURE / DESIGN MODE:

The user is discussing architecture, not requesting a design or a report.
Stay conversational. Answer what the user actually asks and do NOT dump
general architectural knowledge or list spaces, concepts or materials
unless the user asks for them.

"""

        return """

ARCHITECTURE / DESIGN MODE:

If the user requests architecture or design:

- Provide structured professional output.
- Include spaces, concepts, materials or strategy when useful.
- Keep the answer practical.

"""


    # ======================================================
    # CONVERSATION_DOMAIN_V1 — the turn's DOMAIN is a first-class rule
    #
    # ConversationDomainV1 already produces a `guidance` string precisely so
    # that a turn is answered inside its own domain (for a general turn:
    # "Do NOT discuss architecture, buildings, rooms or design unless the
    # user asks about them"). Until now that text reached the model ONLY as
    # one value inside the stringified `MEMORY AND CONTEXT:` dict, where it
    # was not acted on — a general request whose topic merely resembles an
    # architecture word was answered with architecture. Emitting the same
    # string as its own block makes the turn's domain explicit.
    #
    # An ARCHITECTURE turn is deliberately left byte-identical: it already
    # receives the ARCHITECTURE / DESIGN MODE block below, so its guidance
    # ("the session's architectural context may be used") would add nothing.
    # The guidance text is owned by conversation_domain_v1; this method
    # restates no topic and names no subject of its own.
    # ======================================================

    def _domain_rule(
        self,
        context
    ):

        if not isinstance(context, dict):

            return ""

        block = context.get("conversation_domain") or {}

        if not isinstance(block, dict):

            return ""

        if block.get("domain") == "architecture":

            return ""

        guidance = block.get("guidance") or ""

        if not guidance:

            return ""

        return (
            "\n\nTURN DOMAIN (IMPORTANT):\n\n"
            + str(guidance)
            + "\n"
        )


    # ======================================================
    # FACTUAL_ACCURACY — never invent a fact to fill a list
    #
    # Measured on the live chat model: asked for a list of books with their
    # correct titles and authors, it returned confident but fabricated
    # titles/authors. This is a general honesty rule; it names no genre, no
    # title and no acceptance example. It applies to every turn and every
    # language, because the reply language is set by the language rule and
    # this block is prompt scaffolding, not user-facing text.
    # ======================================================

    def _factual_rule(
        self
    ):

        return """

FACTUAL ACCURACY:

- Never state a specific title, author, date or other fact you are not
  certain of. If you are not certain, say so plainly.
- Never invent a title or an author to fill a list. It is better to give
  fewer correct items than a longer list you cannot stand behind.

"""