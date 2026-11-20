# ==========================================================
# ArchitectOS Teaching Foundation v1
#
# PHASE 08 — CONVERSATIONAL INTERACTION AND TEACHING FOUNDATION
#
# This is the ONE deterministic pre-routing layer that the canonical
# ChatArchitect calls.  It is NOT a second assistant.
#
# It does NOT create:
#   - a second LLM
#   - a second memory
#   - a second conversation history
#   - a parallel assistant / tutor
#
# It DOES:
#   - classify the conversational turn (08B)
#   - record teaching CANDIDATES, never knowledge (08C)
#   - answer teach-back requests honestly (08D)
#   - resolve the reply language from canonical project state (08E)
#   - declare the future execution boundary (08G)
#
# It never renders, never calls ComfyUI and never generates images.
# ==========================================================


from __future__ import annotations


import time


from core.conversation.turn_semantics_v1 import (
    classify_turn,
    TURN_CORRECTION,
    TURN_TEACHING_STATEMENT,
    TURN_CONFIRMATION_REQUEST,
    TURN_OFFER_TO_TEACH,
    # TEACHING SESSION STATE FIX — read-only knowledge reflection
    TURN_KNOWLEDGE_REFLECTION,
    # TEACHING_QUESTION_RETRIEVAL — a question about a taught space
    TURN_QUESTION,
    # CORRECTION_LOOP_01 — definitional-space-statement recovery
    TURN_NORMAL_CONVERSATION,
    match_form,
    PERSIAN_COPULA_TOKENS,
    MIN_COPULA_DEFINITION_TOKENS,
)

from core.conversation.teaching_candidate_v1 import (
    build_candidate,
    new_turn_id,
    teaching_candidate_store,
)

from core.conversation.teaching_meaning_v1 import (
    extract_meaning,
    entity_display,
    # TEACHING_CONTEXT_01 — the single source for "is this a space id?"
    is_space_id,
)

from core.conversation.teach_back_v1 import (
    build_teach_back,
    build_acknowledgement,
    build_teaching_elicitation,
    # TEACHING_QUESTION_RETRIEVAL
    build_grounded_answer,
)

# CORRECTION_LOOP_01 — an explicit request to PROMOTE a note to permanent
# knowledge must be refused honestly, never handed to the LLM.
from core.conversation.promotion_boundary_v1 import (
    is_promotion_request,
    build_promotion_refusal,
)

# CLAUSE_ANALYSIS_01 — one long message is not one statement.
from core.conversation.clause_analysis_v1 import (
    knowledge_clauses,
)

# TEACHING CONTENT CAPTURE V1 — an offer that ALSO carries its content
# in the SAME turn must be captured immediately instead of eliciting
# content the teacher has already supplied. Additive, deterministic,
# and it does NOT touch the classifier, the boundary or the ladder.
from core.conversation.teaching_content_extraction_v1 import (
    content_after_preamble,
    has_embedded_content,
)

# VISION_REPORT_LANGUAGE_01 — "say it in Persian" is a request about the
# REPLY, not about architecture.
from core.conversation.language_switch_v1 import (
    detect_language_request,
    build_language_switch,
)

from core.conversation.conversation_language_v1 import (
    resolve_conversation_language,
    is_persian,
)

from core.conversation.execution_boundary_v1 import (
    capability_for_turn,
    is_action_turn,
    phase_08_execution_implemented,
)

# TEACHING SESSION STATE FIX — read-only knowledge reflection.
from core.conversation.knowledge_reflection_v1 import (
    knowledge_reflection,
)

# Candidates belong to a REAL project. A bare session id (for example a
# legacy in-process test session) must never create a project folder.
from core.project.project_workspace_v1 import project_workspace


CONTRACT = "TeachingFoundationV1"
VERSION = "1.0"


# Turn kinds answered deterministically by this layer.
_SHORT_CIRCUIT_KINDS = (
    TURN_CONFIRMATION_REQUEST,
    TURN_TEACHING_STATEMENT,
    TURN_CORRECTION,
    # PHASE 09 — a teaching intent is answered with a clarifying question
    # and must NEVER be routed to EXECUTE.
    TURN_OFFER_TO_TEACH,
    # TEACHING SESSION STATE FIX — "what do you already know?" is
    # answered READ-ONLY from the existing corpus. It must never reach
    # the frozen pipeline and never create a candidate.
    TURN_KNOWLEDGE_REFLECTION,
)


class TeachingFoundationV1:

    CONTRACT = CONTRACT
    VERSION = VERSION

    def __init__(self, store=None):

        self.store = store or teaching_candidate_store

        print(
            "\U0001f9e0 TEACHING FOUNDATION v1.0 ONLINE "
            "(understand, do not learn)"
        )

    # ======================================================
    # TURN OBSERVATION
    # ======================================================

    def observe_turn(
        self,
        text,
        raw_text=None,
        session_id=None,
        context=None,
        input_type=None,
        language=None,
    ):

        """Classify a turn, resolve language, record a candidate.

        Returns an observation dict.  `short_circuit` is True only for
        turns this layer answers itself (teach-back, teaching,
        correction).
        """

        context = context if isinstance(context, dict) else {}

        started = time.time()

        turn_id = new_turn_id()

        raw = str(raw_text if raw_text is not None else text or "")

        # ---- language (08E) ----
        voice_meta = context.get("voice_meta") or {}

        resolved_input_type = (
            input_type
            or context.get("input_type")
            or ("voice" if voice_meta else "text")
        )

        language_decision = resolve_conversation_language(

            project_id=session_id,

            explicit=(
                context.get("reply_language")
                or context.get("response_language")
            ),

            text=raw or text,

            stt_language=(
                context.get("stt_language")
                or voice_meta.get("detected_language")
            ),

            input_type=resolved_input_type,

            persist=bool(session_id),
        )

        reply_language = language_decision.get("language")

        # ---- turn semantics (08B) ----
        semantics = classify_turn(
            text if text is not None else raw,
            language=reply_language,
        )

        turn_kind = semantics.get("turn_kind")

        # ==================================================
        # CORRECTION_LOOP_01 — DEFINITIONAL SPACE STATEMENT RECOVERY
        #
        # "اتاق خواب مستر اتاق والدین هست اونی که تو گفتی ..." IS a
        # definition of a space, but the copula rule requires the copula
        # to be the LAST token, so the classifier saw
        # NORMAL_CONVERSATION and the turn gate dropped the user's
        # PRIMARY teaching sentence — proven from their own session
        # (`project_e89fe613`), where no candidate was ever created for
        # it and the assistant answered with the generic LLM instead.
        #
        # The CLASSIFIER IS NOT MODIFIED. This layer only decides whether
        # to record a turn the deterministic classifier cannot see, and
        # it says so explicitly in `recovered_turn_kind`.
        # ==================================================

        recovered_turn_kind = None

        # ==================================================
        # TEACHING CONTENT CAPTURE V1
        #
        # THE DEFECT (real manual browser test): the teacher announces
        # the teaching intent AND supplies the actual content in the
        # SAME turn —
        #
        #   "میخوام یه نکته آموزشی رو بهت بگم اگه آشپزخونه به حیاط
        #    خلوت نزدیکتر باشه برای طراحیمون بهتره"
        #
        # `turn_semantics_v1` classifies it OFFER_TO_TEACH — rung 0 of
        # the precedence ladder — and returns EARLY, before the
        # TEACHING_STATEMENT rung this sentence ALSO satisfies
        # (measured: `normative=True`). OFFER_TO_TEACH therefore cannot
        # produce a candidate, the candidate block below is skipped, and
        # the assistant then asks for content the user has ALREADY
        # given.
        #
        # The CLASSIFIER IS NOT MODIFIED. This layer only asks ONE
        # deterministic question of the turn the classifier already
        # called a teaching offer:
        #
        #   does the SAME turn ALSO carry a real proposition?
        #
        #   A) PURE OFFER  "میخوام یه نکته بهت یاد بدم"
        #      -> no proposition; elicit, exactly as today.
        #   B) OFFER+CONTENT  "میخوام یه نکته بهت یاد بدم: آشپزخونه
        #      بهتره نزدیک حیاط خلوت باشه"
        #      -> capture the content NOW through the existing
        #         candidate/confirmation flow.
        #
        # `offer_content` keeps the teacher's OWN wording of the
        # proposition, with the preamble removed. It is NEVER persisted
        # before the existing confirmation contract has run.
        # ==================================================

        offer_content = None

        if (
            turn_kind == TURN_OFFER_TO_TEACH
            and not context.get("image")
        ):

            offer_content = content_after_preamble(raw or text)

            if offer_content:

                # The turn IS a teaching statement that also happened to
                # open with an offer. Recover it the SAME way the
                # definitional recovery already does, so every existing
                # consumer sees a coherent turn kind — and the reason is
                # reported honestly in `offer_content_recovered`.
                recovered_turn_kind = TURN_TEACHING_STATEMENT

        if (
            not semantics.get("may_produce_candidate")
            and turn_kind == TURN_NORMAL_CONVERSATION
            and not context.get("image")
            and self._definitional_space(raw or text)
        ):

            recovered_turn_kind = TURN_TEACHING_STATEMENT

        effective_turn_kind = recovered_turn_kind or turn_kind

        # ---- capability boundary (08G) ----
        capability = capability_for_turn(effective_turn_kind)

        # ---- teaching candidates (08C + CLAUSE_ANALYSIS_01) ----
        candidate = None

        candidates = []

        meaning = None

        candidate_persisted = False

        clause_count = None

        if semantics.get("may_produce_candidate") or recovered_turn_kind:

            # ==================================================
            # TEACHING CONTENT CAPTURE V1 — THE SOURCE STATEMENT
            #
            # When the turn was an OFFER+CONTENT, the candidate must be
            # built from the EXTRACTED PROPOSITION, not from the whole
            # announcement — otherwise the preamble ("میخوام یه نکته
            # آموزشی رو بهت بگم") would be parsed as if it were part of
            # the rule. Every other path keeps the EXACT previous
            # behaviour: the full raw text.
            # ==================================================

            source_text = offer_content if offer_content else (raw or text)

            # ==================================================
            # TEACHING_CONTEXT_01 — ACTIVE ARCHITECTURAL TOPIC
            #
            # A teaching conversation must keep its statements attached
            # to the active space. The context is assembled from what is
            # already available: an explicit `active_topic` supplied by
            # the caller, otherwise the most recent resolved space in
            # THIS project's own teaching history.
            #
            # Project-scoped, additive, and NOT a global memory: the
            # source is the teaching candidate store that already
            # exists.
            # ==================================================

            teaching_context = self._teaching_context(
                session_id, context
            )

            # ==================================================
            # CLAUSE_ANALYSIS_01 — ONE CANDIDATE PER KNOWLEDGE CLAUSE
            #
            # A single message can carry SEVERAL rules plus the reasons
            # for them. Treating it as ONE statement reduced the user's
            # four master-bedroom rules to a single wrong triple
            # ("پنجره باید دور از اتاق خواب و نشیمن باشد") and lost the
            # rest. The teacher's words: "کل جملات رو میگیره ... کلی
            # میگیره همه چیز رو".
            #
            # A message with fewer than two knowledge clauses keeps the
            # EXACT previous behaviour (one candidate, full text).
            # ==================================================

            clauses = knowledge_clauses(source_text)

            if len(clauses) >= 2:

                plan = [
                    (clause["text"], clause) for clause in clauses
                ]

                clause_count = len(plan)

            else:

                plan = [(source_text, None)]

            for position, (statement, clause) in enumerate(plan):

                built = build_candidate(
                    statement,
                    project_id=session_id,
                    source_turn_id=turn_id,
                    source_type=resolved_input_type,
                    language=reply_language,
                    turn_kind=effective_turn_kind,
                    context=teaching_context,
                    clause_role=(clause or {}).get("role"),
                    clause_index=(
                        position if clause_count else None
                    ),
                    clause_count=clause_count,
                    source_statement=(
                        source_text if clause_count else None
                    ),
                    rationale=(clause or {}).get("rationale"),
                )

                if built is None:

                    continue

                if session_id and self._is_real_project(session_id):

                    try:

                        persisted = self.store.record(
                            session_id, built,
                            turn_kind=effective_turn_kind
                        )

                        if persisted:

                            built = persisted

                            candidate_persisted = True

                    except Exception as error:

                        print(
                            "PHASE 08 CANDIDATE PERSIST ERROR:",
                            error
                        )

                candidates.append(built)

            if candidates:

                candidate = candidates[0]

            meaning = extract_meaning(
                plan[0][0],
                turn_kind=effective_turn_kind,
                context=teaching_context,
            )

        # ---- short circuit decision ----
        #
        # TEACHING_QUESTION_RETRIEVAL — `short_circuit` is now decided
        # AFTER the grounded-answer attempt below, because a QUESTION
        # short-circuits only when teaching knowledge actually exists
        # for the space it refers to.
        has_image = bool(context.get("image"))

        # ---- teaching-intent elicitation topic ----
        #
        # TEACHING CONTENT CAPTURE V1 — the elicitation is for a turn
        # that is STILL an OFFER, i.e. the classifier's OWN verdict
        # (`turn_kind`), NOT the recovered one. When the offer carried
        # real content, `recovered_turn_kind` promoted it to
        # TEACHING_STATEMENT and this block is skipped, so the turn can
        # never both capture a candidate AND ask "what did you want to
        # teach me?".
        teaching_topic = None

        teaching_space = None

        teaching_diagram = None

        # PHASE 12 — a PROGRAM topic is neither one space nor a diagram
        teaching_program = None

        if turn_kind == TURN_OFFER_TO_TEACH and not recovered_turn_kind:

            teaching_space = self._extract_teaching_space(
                raw or text, reply_language
            )

            # PHASE 11 — a DIAGRAM topic is not a single space
            teaching_diagram = self._extract_teaching_diagram(
                raw or text, reply_language
            )

            # PHASE 12 — a PROGRAM topic is not a single space either
            teaching_program = self._extract_teaching_program(
                raw or text, reply_language
            )

            teaching_topic = self._extract_teaching_topic(
                raw or text, reply_language
            )

        # ==================================================
        # TEACHING SESSION STATE FIX — READ-ONLY KNOWLEDGE REFLECTION
        #
        # The user is asking what the assistant ALREADY knows. Resolved
        # here, where the raw user text is still available, and rendered
        # READ-ONLY from the existing corpus. No candidate, no teaching
        # storage, no promotion, no lesson, no curriculum.
        # ==================================================

        reflection = None

        if turn_kind == TURN_KNOWLEDGE_REFLECTION:

            try:

                reflection = knowledge_reflection.reflect(
                    raw or text, reply_language
                )

            except Exception as error:

                print(
                    "TEACHING SESSION STATE REFLECTION ERROR:",
                    type(error).__name__,
                    error,
                )

                reflection = None

        # ==================================================
        # TEACHING_QUESTION_RETRIEVAL
        #
        # A QUESTION about a space that HAS teacher-recorded knowledge
        # is answered from that knowledge — never from the generic LLM.
        # When the space has NO recorded teaching, `grounded` stays None
        # and the turn falls through exactly as before.
        #
        # Read-only: nothing is created, stored, promoted or learned.
        # ==================================================

        grounded = None

        if turn_kind == TURN_QUESTION:

            grounded = self._grounded_answer(
                raw or text, reply_language, session_id
            )

        # ==================================================
        # CORRECTION_LOOP_01 — KNOWLEDGE PROMOTION BOUNDARY
        #
        # The teacher asked for a received note to become permanent
        # knowledge. Phase 08 does not implement promotion, and the
        # briefs forbid doing it silently. Without this boundary the
        # request classified as INSTRUCTION (not short-circuited), fell
        # through to the generic LLM, and the LLM FABRICATED a
        # promotion from an unrelated memory.
        #
        # Read-only: nothing is stored, promoted or learned. It fires
        # only on an explicit two-part request, and only for a turn this
        # layer would otherwise hand to the LLM.
        # ==================================================

        promotion = None

        if (
            turn_kind not in _SHORT_CIRCUIT_KINDS
            and is_promotion_request(raw or text)
        ):

            promotion = build_promotion_refusal(reply_language)

        # ==================================================
        # VISION_REPORT_LANGUAGE_01 — AN EXPLICIT LANGUAGE REQUEST
        #
        # "میشه تحلیل عکستو فارسی برام بگی" is a request about the REPLY
        # LANGUAGE, not about architecture. It used to be classified
        # NORMAL_CONVERSATION, fall through to the generic LLM, and the
        # LLM then treated "عکستو فارسی" as an ARCHITECTURAL TERM —
        # inventing a whole discussion of it. Answered here instead:
        # the project's last image interpretation is re-rendered in the
        # requested language. Read-only, deterministic, no LLM.
        # ==================================================

        language_request = None

        if (
            turn_kind not in _SHORT_CIRCUIT_KINDS
            and promotion is None
            and not has_image
        ):

            requested_language = detect_language_request(raw or text)

            if requested_language:

                # An explicit request LOCKS the project's reply language.
                language_decision = resolve_conversation_language(

                    project_id=session_id,

                    explicit=requested_language,

                    text=raw or text,

                    input_type=resolved_input_type,

                    persist=bool(session_id),
                )

                reply_language = language_decision.get("language")

                analysis = self._last_vision_analysis(session_id)

                language_request = build_language_switch(

                    reply_language,

                    interpretation=analysis,

                    project_id=session_id,

                    image_analysis_available=bool(analysis),
                )

        # A QUESTION short-circuits ONLY when a grounded answer exists.
        short_circuit = (
            (
                effective_turn_kind in _SHORT_CIRCUIT_KINDS
                or grounded is not None
                or promotion is not None
                or language_request is not None
            )
            and not has_image
        )

        response = None

        if short_circuit:

            response = self.build_response({

                "turn_id": turn_id,
                "turn_kind": effective_turn_kind,
                # CORRECTION_LOOP_01 — honesty about the recovery
                "classifier_turn_kind": turn_kind,
                "recovered_turn_kind": recovered_turn_kind,
                # TEACHING CONTENT CAPTURE V1 — honest provenance
                "offer_content_recovered": bool(offer_content),
                "offer_content": offer_content,
                "semantics": semantics,
                "candidate": candidate,
                # CLAUSE_ANALYSIS_01 — every clause of the message
                "candidates": candidates,
                "clause_count": clause_count,
                "meaning": meaning,
                "language": reply_language,
                "language_decision": language_decision,
                "session_id": session_id,
                "capability": capability,
                # PHASE 10 — the elicitation needs the topic + space
                "teaching_topic": teaching_topic,
                "teaching_space": teaching_space,
                # PHASE 11 — diagram topic
                "teaching_diagram": teaching_diagram,
                # PHASE 12 — program topic
                "teaching_program": teaching_program,
                # TEACHING SESSION STATE FIX — read-only reflection
                "reflection": reflection,
                # TEACHING_QUESTION_RETRIEVAL — grounded question answer
                "grounded": grounded,
                # CORRECTION_LOOP_01 — promotion boundary
                "promotion": promotion,
                # VISION_REPORT_LANGUAGE_01 — an explicit language request
                "language_request": language_request,
            })

        return {

            "contract": CONTRACT,
            "version": VERSION,

            "turn_id": turn_id,

            "turn_kind": effective_turn_kind,

            # CORRECTION_LOOP_01 — the classifier's OWN verdict is never
            # overwritten: it is reported next to the recovered one, so a
            # consumer can always see exactly what happened.
            "classifier_turn_kind": turn_kind,

            "recovered_turn_kind": recovered_turn_kind,

            # TEACHING CONTENT CAPTURE V1 — the offer carried its own
            # content, so it was captured instead of elicited.
            # `offer_content` is the extracted proposition in the
            # teacher's own wording (preamble removed).
            "offer_content_recovered": bool(offer_content),

            "offer_content": offer_content,

            "confidence": semantics.get("confidence"),

            "semantics": semantics,

            "capability": capability,

            "is_action_turn": is_action_turn(effective_turn_kind),

            "language": reply_language,

            "language_decision": language_decision,

            "candidate": candidate,

            "candidate_persisted": candidate_persisted,

            # CLAUSE_ANALYSIS_01 — one long message becomes one candidate
            # per knowledge clause; `candidate` stays the FIRST one for
            # every existing consumer.
            "candidates": candidates,

            "clause_count": clause_count,

            "teaching_topic": teaching_topic,

            "teaching_space": teaching_space,

            # PHASE 11 — diagram topic
            "teaching_diagram": teaching_diagram,

            # PHASE 12 — program topic
            "teaching_program": teaching_program,

            # TEACHING SESSION STATE FIX — read-only reflection
            "reflection": reflection,

            # TEACHING_QUESTION_RETRIEVAL — grounded question answer
            "grounded": grounded,

            # CORRECTION_LOOP_01 — promotion boundary
            "promotion": promotion,

            # VISION_REPORT_LANGUAGE_01 — an explicit language request
            "language_request": language_request,

            "meaning": meaning,

            "short_circuit": bool(short_circuit),

            "response": response,

            "input_type": resolved_input_type,

            "project_id": session_id,

            "execution_implemented_by_phase_08": (
                phase_08_execution_implemented()
            ),

            # Phase 08 never renders.
            "render_requested": False,

            "seconds": round(time.time() - started, 4),
        }

    # ======================================================
    # RESPONSE BUILDING
    # ======================================================

    def _is_real_project(self, project_id):

        """True only for a project that actually exists on disk."""

        if not project_id:

            return False

        try:

            return bool(project_workspace.exists(project_id))

        except Exception:

            return False

    # ======================================================
    # TEACHING_CONTEXT_01 — ACTIVE ARCHITECTURAL TOPIC
    # ======================================================

    def _last_space_topic(self, project_id):

        """The most recent resolved architectural space in THIS project.

        Read from the project's own teaching candidates. Project-scoped
        and persisted — deliberately not a global memory.
        """

        if not project_id:

            return None

        try:

            candidates = self.store.candidates(project_id)

        except Exception:

            return None

        for candidate in reversed(candidates or []):

            value = (candidate or {}).get("space_topic")

            if value:

                return value

        return None

    def _teaching_context(self, project_id, context):

        """Smallest additive teaching context for meaning resolution.

        An `active_topic` supplied by the caller wins; otherwise the
        topic is inherited from this project's teaching history.
        """

        teaching_context = dict(context) if isinstance(context, dict) else {}

        if is_space_id(teaching_context.get("active_topic")):

            return teaching_context

        inherited = self._last_space_topic(project_id)

        if inherited:

            teaching_context["active_topic"] = inherited

        return teaching_context

    # ======================================================
    # TEACHING_QUESTION_RETRIEVAL
    # ======================================================

    def _question_space(self, text):

        """The architectural space a question refers to, or None.

        Reuses the canonical corpus scanner (`space_query_v1.scan_spaces`)
        — longest-match, non-overlapping, position-ordered.
        """

        try:

            from core.curriculum.space_query_v1 import scan_spaces

            mentions = scan_spaces(text)

        except Exception:

            return None

        return mentions[0][0] if mentions else None

    # ======================================================
    # CORRECTION_LOOP_01 — DEFINITIONAL SPACE STATEMENT RECOVERY
    # ======================================================

    def _definitional_space(self, text):

        """The space a copular definition is about, or None.

        The classifier's copula rule requires the copula to be the LAST
        token, so a definition with a TRAILING CLAUSE
        ("اتاق خواب مستر اتاق والدین هست اونی که تو گفتی ...") is not
        seen as definitional at all.

        THREE parts are required here, so an ordinary sentence is never
        captured:
          - at least MIN_COPULA_DEFINITION_TOKENS tokens
          - a Persian copula ANYWHERE in the sentence
          - the sentence NAMES a known corpus space (canonical scanner)

        "امروز هوا سرد است و باران می بارد" names no space -> None.
        """

        try:

            form = match_form(text)

        except Exception:

            return None

        tokens = [token for token in form.split(" ") if token]

        if len(tokens) < MIN_COPULA_DEFINITION_TOKENS:

            return None

        if not any(token in PERSIAN_COPULA_TOKENS for token in tokens):

            return None

        return self._question_space(form)

    # ======================================================
    # VISION_REPORT_LANGUAGE_01 — THE LAST IMAGE INTERPRETATION
    # ======================================================

    def _last_vision_analysis(self, project_id):

        """The project's last architectural image interpretation, or None.

        Read-only. `_is_real_project` is checked first, so a bare session
        id can never materialise a project folder.
        """

        if not project_id or not self._is_real_project(project_id):

            return None

        try:

            from core.vision.vision_analysis_store_v1 import (
                vision_analysis_store,
            )

            return vision_analysis_store.load(project_id)

        except Exception as error:

            print(
                "VISION ANALYSIS LOAD ERROR:",
                type(error).__name__,
                error,
            )

            return None

    def _grounded_answer(self, text, language, project_id):
        """Answer from the teaching store, or None to keep the LLM path.

        None means this space has NO teacher-recorded knowledge, so the
        turn must behave exactly as it did before.

        ARCHITECTURAL_KNOWLEDGE_STRUCTURER_V1 — read-only integration
        point. AFTER the retrieval and BEFORE the answer is returned, the
        same records are turned into an architectural structure for the
        space and its answer style is appended. It replaces nothing: the
        grounded list is still there, and a failure here can never break
        the answer.
        """

        space_topic = self._question_space(text)

        if not space_topic or not project_id:

            return None

        try:

            grounded = build_grounded_answer(

                project_id=project_id,

                space_topic=space_topic,

                language=language,

                store=self.store,
            )

        except Exception as error:

            print(
                "TEACHING QUESTION RETRIEVAL ERROR:",
                type(error).__name__,
                error,
            )

            return None

        return self._attach_architectural_knowledge(
            grounded, space_topic, language, project_id
        )

    def _attach_architectural_knowledge(
        self, grounded, space_topic, language, project_id
    ):
        """Add the structured view of the SAME records. Read-only.

        Additive only: the grounded answer keeps its own text, and the
        structure is attached next to it. Nothing is stored, learned or
        rendered, and any failure leaves the answer exactly as it was.
        """

        if not grounded:

            return grounded

        try:

            from core.knowledge.architectural_knowledge_structurer_v1 import (
                structure_space_knowledge,
                render_structured_answer,
            )

            structure = structure_space_knowledge(

                project_id=project_id,

                space_id=space_topic,

                language=language,

                store=self.store,
            )

        except Exception as error:

            print(
                "ARCHITECTURAL KNOWLEDGE STRUCTURER ERROR:",
                type(error).__name__,
                error,
            )

            return grounded

        if not structure:

            return grounded

        grounded["architectural_knowledge"] = structure

        try:

            block = render_structured_answer(structure, language)

        except Exception:

            block = ""

        if block:

            grounded["result"] = (
                (grounded.get("result") or "") + "\n\n" + block
            )

        return grounded

    # ======================================================
    # PHASE 09 — TEACHING TOPIC EXTRACTION
    # ======================================================

    def _extract_teaching_topic(self, text, language="fa"):

        """Deterministic topic for the elicitation question.

        PHASE 10 — the curriculum space registry (82 spaces) is tried
        first; it is richer than the Phase 08 entity lexicon. If it does
        not recognise anything, the original Phase 08 path is used
        unchanged.
        """

        space = self._extract_teaching_space(text, language)

        if space and (space.get("alias") or space.get("name")):

            # Echo the words the user actually used, so the question
            # reads naturally ("کدام بخش آشپزخانه ...").
            return space.get("alias") or space.get("name")

        try:

            meaning = extract_meaning(text)

        except Exception:

            return None

        entities = meaning.get("entities") or []

        if not entities:

            return None

        lang = "fa" if str(language or "").startswith("fa") else "en"

        return entity_display(entities[0], lang)

    # ======================================================
    # PHASE 10 — SPACE TOPIC RESOLUTION
    # ======================================================

    def _extract_teaching_space(self, text, language="fa"):

        try:

            from core.curriculum.space_curriculum_v1 import (
                space_curriculum,
            )

            return space_curriculum.resolve_space_topic(text, language)

        except Exception as error:

            print(
                "PHASE 10 SPACE TOPIC ERROR:",
                type(error).__name__,
                error,
            )

            return None

    # ======================================================
    # PHASE 11 — DIAGRAM TOPIC RESOLUTION
    # ======================================================

    def _extract_teaching_diagram(self, text, language="fa"):

        try:

            from core.curriculum.diagram_curriculum_v1 import (
                diagram_curriculum,
            )

            return diagram_curriculum.resolve_diagram_topic(
                text, language
            )

        except Exception as error:

            print(
                "PHASE 11 DIAGRAM TOPIC ERROR:",
                type(error).__name__,
                error,
            )

            return None


    # ======================================================
    # PHASE 12 — PROGRAM TOPIC RESOLUTION
    # ======================================================

    def _extract_teaching_program(self, text, language="fa"):

        try:

            from core.curriculum.program_curriculum_v1 import (
                program_curriculum,
            )

            return program_curriculum.resolve_program_topic(
                text, language
            )

        except Exception as error:

            print(
                "PHASE 12 PROGRAM TOPIC ERROR:",
                type(error).__name__,
                error,
            )

            return None


    def build_response(self, observation):

        """Chat-shaped response produced by the SAME assistant."""

        turn_kind = observation.get("turn_kind")

        language = observation.get("language") or "en"

        semantics = observation.get("semantics") or {}

        candidate = observation.get("candidate")

        project_id = observation.get("session_id")

        if turn_kind == TURN_QUESTION and observation.get("grounded"):

            # ==================================================
            # TEACHING_QUESTION_RETRIEVAL
            #
            # The question refers to a space that HAS teacher-recorded
            # knowledge, so the answer comes from that knowledge — not
            # from the generic LLM. Read-only: nothing is created.
            # ==================================================

            grounded = observation.get("grounded") or {}

            text = grounded.get("result") or ""

            teaching = {
                "action": "answer_from_teaching_memory",
                "grounded_answer": grounded,
                "space_topic": grounded.get("space_topic"),
                "source": grounded.get("source"),
                "provenance": grounded.get("provenance"),
                "recorded": grounded.get("recorded"),
                "candidate": None,
                "permanent_learning": False,
                "routed_to_execute": False,
                "llm_used": False,
            }

        elif turn_kind == TURN_KNOWLEDGE_REFLECTION:

            # ==================================================
            # TEACHING SESSION STATE FIX — READ-ONLY REFLECTION
            #
            # The user asked what the assistant ALREADY knows. Answer
            # from the existing corpus and change nothing:
            #   no candidate, no teaching storage, no promotion,
            #   no lesson, no curriculum, no render.
            # ==================================================

            reflection = observation.get("reflection") or {}

            text = reflection.get("result") or ""

            teaching = {
                "action": "reflect_existing_knowledge",
                "mode": "READ_ONLY_KNOWLEDGE_REFLECTION",
                "reflection": reflection,
                "topic": reflection.get("topic"),
                "space_id": reflection.get("space_id"),
                "has_existing_knowledge": reflection.get(
                    "has_existing_knowledge"
                ),
                "read_only": True,
                "user_as_teacher": None,
                "candidate": None,
                "permanent_learning": False,
                "routed_to_execute": False,
                "lesson_started": False,
            }

        elif turn_kind == TURN_CONFIRMATION_REQUEST:

            teach_back = build_teach_back(
                project_id=project_id,
                language=language,
                store=self.store,
            )

            text = teach_back.get("result") or ""

            teaching = {
                "action": "teach_back",
                "teach_back": teach_back,
            }

        elif turn_kind == TURN_OFFER_TO_TEACH:

            # PHASE 09 — ELICITATION.
            # PHASE 10 — when the topic is a known architectural space the
            # SPACE aspects are used instead of the generic ones.
            # Ask which aspect is being taught. No candidate is created,
            # nothing is learned, and this turn is never routed to
            # EXECUTE.
            topic = observation.get("teaching_topic")

            aspects = None

            aspect_set = "generic"

            try:

                from core.curriculum.space_curriculum_v1 import (
                    space_curriculum,
                )

                aspects = space_curriculum.aspects_for_topic(
                    observation.get("teaching_space") or topic,
                    language,
                )

                if aspects:

                    aspect_set = "space"

            except Exception as error:

                print("PHASE 10 SPACE ASPECTS ERROR:", error)

            # PHASE 11 — a DIAGRAM topic uses the diagram aspects.
            # The aspects were resolved in observe_turn, where the raw
            # user text is still available.
            if not aspects and observation.get("teaching_diagram"):

                diagram = observation.get("teaching_diagram") or {}

                aspects = diagram.get("aspects")

                if aspects:

                    aspect_set = "diagram"

                    topic = diagram.get("topic_label") or topic

            # PHASE 12 — a PROGRAM topic uses the program aspects.
            # Checked AFTER space and diagram so those two older paths
            # stay exactly as they were.
            if not aspects and observation.get("teaching_program"):

                program = observation.get("teaching_program") or {}

                aspects = program.get("aspects")

                if aspects:

                    aspect_set = "program"

                    topic = program.get("topic_label") or topic

            # ==================================================
            # TEACHER ROLE RESPONSE FIX
            #
            # ROLE RESOLUTION (presentation only).
            #
            # `teaching_intent_direction` is a PRESENTATION hint: its
            # only consumer in the whole codebase is the call below.
            # It defaults to `user_requests_teaching` whenever the
            # sentence carries no explicit offer marker, which
            # mis-labelled a plain teaching-session opener
            # ("میخوایم اولین جلسه آموزش معماری رو شروع کنیم" — "we want
            # to start the first architecture teaching session") as the
            # user wanting to LEARN, so the reply thanked them for
            # wanting to learn and then asked them which aspect they
            # wanted to TEACH.
            #
            # The deterministic discriminator is `teach_request`: the
            # explicit imperative ("یاد بده" / "teach me"). ONLY that
            # means the user is the learner. Every other teaching intent
            # is the speaker offering to teach.
            #
            # Nothing here changes classification: `turn_kind`, the
            # precedence ladder and the turn gate are untouched, and
            # turn_semantics_v1.py is not modified by this fix.
            # ==================================================

            _features = semantics.get("features") or {}

            _explicit_learn_request = bool(
                _features.get("teach_request")
            )

            # An explicit offer marker keeps its own verdict; the
            # override below only fires for a "requests" verdict that has
            # no explicit request imperative behind it.
            _already_an_offer = (
                semantics.get("teaching_intent_direction")
                == "user_offers_to_teach"
            )

            user_as_teacher = (
                _already_an_offer or not _explicit_learn_request
            )

            elicitation_direction = (
                "user_offers_to_teach"
                if user_as_teacher
                else "user_requests_teaching"
            )

            elicitation = build_teaching_elicitation(
                topic=topic,
                language=language,
                direction=elicitation_direction,
                aspects=aspects,
            )

            text = elicitation.get("result") or ""

            teaching = {
                "action": "elicit_teaching_aspect",
                "elicitation": elicitation,
                # TEACHER ROLE RESPONSE FIX — explicit role contract.
                "user_as_teacher": user_as_teacher,
                "assistant_as_learner": user_as_teacher,
                "space_topic": observation.get("teaching_space"),
                "diagram_topic": observation.get("teaching_diagram"),
                "program_topic": observation.get("teaching_program"),
                "aspect_set": aspect_set,
                "candidate": None,
                "permanent_learning": False,
                "routed_to_execute": False,
            }

        elif observation.get("promotion"):

            # ==================================================
            # CORRECTION_LOOP_01 — KNOWLEDGE PROMOTION BOUNDARY
            #
            # The teacher asked for permanent knowledge. This build does
            # not implement promotion, so the answer states that plainly
            # instead of inventing one. Read-only: nothing is stored,
            # promoted or learned, and the LLM is never called.
            # ==================================================

            promotion = observation.get("promotion") or {}

            text = promotion.get("result") or ""

            teaching = {
                "action": "refuse_knowledge_promotion",
                "mode": "READ_ONLY_PROMOTION_BOUNDARY",
                "promotion": promotion,
                "promotion_requested": True,
                "promotion_implemented": promotion.get(
                    "promotion_implemented", False
                ),
                "promoted": False,
                "read_only": True,
                "candidate": None,
                "permanent_learning": False,
                "routed_to_execute": False,
                "llm_used": False,
            }

        elif observation.get("language_request"):

            # ==================================================
            # VISION_REPORT_LANGUAGE_01
            #
            # The teacher asked for the reply in another language. The
            # project's last image interpretation is re-rendered in that
            # language — the same contract, nothing invented, and the
            # LLM is never called.
            # ==================================================

            request = observation.get("language_request") or {}

            text = request.get("result") or ""

            teaching = {
                "action": "switch_reply_language",
                "language_request": request,
                "requested_language": request.get("requested_language"),
                "re_rendered_analysis": request.get(
                    "re_rendered_analysis"
                ),
                "candidate": None,
                "permanent_learning": False,
                "routed_to_execute": False,
                "llm_used": False,
            }

        else:

            text = build_acknowledgement(
                turn_kind,
                meaning=observation.get("meaning"),
                language=language,
                candidate=candidate,
                # CLAUSE_ANALYSIS_01 — show EVERY clause that was captured
                candidates=observation.get("candidates"),
            )

            teaching = {
                "action": (
                    "record_correction"
                    if turn_kind == TURN_CORRECTION
                    else "record_teaching_statement"
                ),
                "candidate": candidate,
                "candidates": observation.get("candidates") or [],
                "clause_count": observation.get("clause_count"),
                "permanent_learning": False,
            }

        return {

            "type": "chat",

            "engine": "architectos_turn_semantics",

            "status": "success",

            "result": text,

            "session_id": project_id,

            "language": {
                "input_language": (
                    "persian" if is_persian(language) else "english"
                ),
                "output_language": (
                    "persian" if is_persian(language) else "english"
                ),
                "guard_status": "validated",
                "corrected": False,
                "decision": observation.get("language_decision"),
            },

            "turn_semantics": semantics,

            # CORRECTION_LOOP_01 — reported at the API boundary too, so a
            # consumer can always distinguish the classifier's verdict
            # from the turn the teaching layer acted on.
            "classifier_turn_kind": observation.get(
                "classifier_turn_kind"
            ),

            "recovered_turn_kind": observation.get(
                "recovered_turn_kind"
            ),

            "teaching": teaching,

            "capability": observation.get("capability"),

            "render_handoff": {
                "compiled_render_prompt": "",
                "compiled_prompt_source": "none",
                "render_runtime_received_prompt": None,
            },

            "render_requested": False,
        }

    # ======================================================
    # READ-ONLY SURFACE (used by the API + acceptance)
    # ======================================================

    def teach_back(self, project_id=None, language="en"):

        return build_teach_back(
            project_id=project_id,
            language=language,
            store=self.store,
        )

    def candidates(self, project_id=None, status=None, domain=None):

        if not project_id:

            return []

        return self.store.candidates(
            project_id, status=status, domain=domain
        )

    def learned_count(self, project_id=None):

        if not project_id:

            return 0

        return self.store.learned_count(project_id)

    def status(self, project_id=None):

        return {

            "contract": CONTRACT,
            "version": VERSION,

            "one_assistant": True,
            "second_llm": False,
            "second_memory": False,
            "second_conversation_history": False,
            "parallel_assistant": False,

            "permanent_learning_implemented": False,

            # PHASE 09
            "teaching_intent_supported": True,
            "elicitation_implemented": True,
            "knowledge_promotion_implemented": False,

            "project_id": project_id,

            "candidate_count": (
                self.store.count(project_id) if project_id else 0
            ),

            "learned_count": self.learned_count(project_id),

            "render_requested": False,
            "comfy_invoked": False,
            "image_generation": False,
        }


teaching_foundation = TeachingFoundationV1()
