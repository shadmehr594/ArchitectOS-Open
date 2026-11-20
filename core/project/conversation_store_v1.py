# ==========================================================
# ArchitectOS Conversation Store v1
#
# PROJECT_WORKSPACE_UI_06 — persistent chat history
#
# Persists a project's conversation so that after an application
# restart / Windows restart / power loss the user can continue the
# previous work instead of facing an empty in-memory registry.
#
# Stored per project:
#   <project>/conversations/chat.json
#
# Design
#   - atomic write (temp + os.replace) on every save
#   - non-JSON-safe values are stringified, never dropped silently
#   - the message list is capped, matching ConversationState
#   - restore is additive: it hydrates an existing ConversationState
# ==========================================================


from __future__ import annotations


import copy
import hashlib
import os
import time


from core.project.project_workspace_v1 import (
    project_workspace,
    atomic_write_json,
    read_json,
)


CONTRACT = "ConversationStoreV1"
VERSION = "1.0"


CONVERSATION_FILE = "chat.json"

MAX_MESSAGES = 100

MATERIAL_REVIEW_KEY = "material_correction_reviews"
MATERIAL_REVIEW_ERROR_KEY = "material_correction_review_restore_errors"
MATERIAL_REVIEW_CONTRACT = "ArchitecturalMaterialCorrectionReviewCarrierV1"
MATERIAL_REVIEW_VERSION = "1.0"
MATERIAL_REVIEW_STATES = (
    "pending_review",
    "rejected",
    "refinement_requested",
)


# Keys that must never be persisted (runtime objects).
_BLOCKED_KEYS = (
    "file_object",
    "file_storage",
)


def _sanitize(value, depth=0):

    if depth > 8:

        return str(value)

    if value is None or isinstance(value, (bool, int, float, str)):

        return value

    if isinstance(value, dict):

        out = {}

        for key, item in value.items():

            if key in _BLOCKED_KEYS:

                continue

            out[str(key)] = _sanitize(item, depth + 1)

        return out

    if isinstance(value, (list, tuple)):

        return [_sanitize(item, depth + 1) for item in value]

    return str(value)


class ConversationStore:

    VERSION = VERSION

    def __init__(self):

        print("💬 CONVERSATION STORE v1.0 ONLINE (persistent)")

    # ======================================================
    # PATHS
    # ======================================================

    def path(self, project_id):

        return os.path.join(
            project_workspace.subdir(project_id, "conversations"),
            CONVERSATION_FILE
        )

    # ======================================================
    # SAVE
    # ======================================================

    def build_material_correction_review_carrier(
        self,
        *,
        project_id,
        session_id,
        message_ref,
        message_text,
        connection,
        attachment_ids=None,
    ):
        """Build one non-executable, non-confirming durable review carrier."""

        correction = (connection or {}).get("material_correction") or {}
        review = correction.get("confirmation_review") or {}
        candidate = correction.get("knowledge_candidate")
        observed = (connection or {}).get("observed_facts") or {}
        provenance = observed.get("provenance") or {}
        user_correction = correction.get("user_correction") or {}

        review_id = review.get("review_id") if isinstance(review, dict) else None
        image_id = provenance.get("image_id") if isinstance(provenance, dict) else None
        correction_text = user_correction.get("verbatim")

        if (
            (connection or {}).get("status")
            != "MATERIAL_CORRECTION_PENDING_CONFIRMATION"
            or correction.get("status") != "PENDING_CONFIRMATION"
            or not isinstance(candidate, dict)
            or not isinstance(review, dict)
            or review.get("contract") != "ArchitecturalKnowledgeReviewV1"
            or review.get("state") != "pending_review"
            or review.get("human_confirmed") is not False
            or review.get("candidate") != candidate
            or not isinstance(review_id, str)
            or not review_id.strip()
            or not isinstance(observed, dict)
            or not isinstance(provenance, dict)
            or not isinstance(image_id, str)
            or not image_id.strip()
            or user_correction.get("source") != "USER_CORRECTION"
            or not isinstance(correction_text, str)
            or not correction_text.strip()
            or str(message_text or "").strip() != correction_text.strip()
            or not str(project_id or "").strip()
            or not str(session_id or "").strip()
            or not str(message_ref or "").strip()
        ):
            raise ValueError("material correction review carrier is not grounded")

        attachments = []
        for value in attachment_ids or []:
            text = str(value or "").strip()
            if text and text not in attachments:
                attachments.append(text)

        record = {
            "contract": MATERIAL_REVIEW_CONTRACT,
            "version": MATERIAL_REVIEW_VERSION,
            "review_id": review_id,
            "knowledge_candidate": copy.deepcopy(candidate),
            "confirmation_review": copy.deepcopy(review),
            "original_correction_text": correction_text,
            "user_correction": copy.deepcopy(user_correction),
            "original_observation": copy.deepcopy(observed),
            "observation_provenance": copy.deepcopy(provenance),
            "previous_observation": copy.deepcopy(
                correction.get("previous_observation")
            ),
            "corrected_material": copy.deepcopy(
                correction.get("corrected_material")
            ),
            "spatial_grounding": copy.deepcopy(
                correction.get("spatial_grounding")
            ),
            "execution_capability": copy.deepcopy(
                (connection or {}).get("execution_capability")
            ),
            "origin": {
                "project_id": str(project_id),
                "message_ref": str(message_ref),
                "session_id": str(session_id),
                "conversation_identity_kind": "PROJECT_BOUND_SESSION",
                "separate_conversation_id": None,
                "image_identity": {
                    "image_id": image_id,
                    "attachment_ids": attachments,
                },
            },
            "lifecycle": {
                "state": "pending_review",
                "human_confirmed": False,
                "admitted": False,
            },
            "authentication": {
                "status": "AUTHENTICATED_CONFIRMATION_ACTOR_UNAVAILABLE",
                "confirmation_enabled": False,
            },
            "captured_at": time.time(),
        }
        return self._validate_material_correction_review(
            record, expected_project_id=str(project_id)
        )

    def _validate_material_correction_review(
        self,
        record,
        *,
        expected_project_id=None,
        expected_session_id=None,
    ):
        if not isinstance(record, dict):
            raise ValueError("material review record must be a dict")
        if (
            record.get("contract") != MATERIAL_REVIEW_CONTRACT
            or record.get("version") != MATERIAL_REVIEW_VERSION
        ):
            raise ValueError("material review carrier contract is invalid")

        review_id = record.get("review_id")
        candidate = record.get("knowledge_candidate")
        review = record.get("confirmation_review")
        origin = record.get("origin")
        lifecycle = record.get("lifecycle")
        observed = record.get("original_observation")
        provenance = record.get("observation_provenance")
        authentication = record.get("authentication")

        if (
            not isinstance(review_id, str)
            or not review_id.strip()
            or not isinstance(candidate, dict)
            or not isinstance(review, dict)
            or review.get("contract") != "ArchitecturalKnowledgeReviewV1"
            or review.get("review_id") != review_id
            or review.get("candidate") != candidate
            or not isinstance(origin, dict)
            or not isinstance(lifecycle, dict)
            or not isinstance(observed, dict)
            or not isinstance(provenance, dict)
            or observed.get("provenance") != provenance
        ):
            raise ValueError("material review identity is malformed")

        project_id = origin.get("project_id")
        if (
            not isinstance(project_id, str)
            or not project_id.strip()
            or (
                expected_project_id is not None
                and project_id != str(expected_project_id)
            )
            or not isinstance(origin.get("message_ref"), str)
            or not origin.get("message_ref").strip()
            or not isinstance(origin.get("session_id"), str)
            or not origin.get("session_id").strip()
            or (
                expected_session_id is not None
                and origin.get("session_id") != str(expected_session_id)
            )
            or origin.get("conversation_identity_kind")
            != "PROJECT_BOUND_SESSION"
            or origin.get("separate_conversation_id") is not None
        ):
            raise ValueError("material review project or message binding is invalid")

        image_identity = origin.get("image_identity")
        image_id = provenance.get("image_id")
        if (
            not isinstance(image_identity, dict)
            or not isinstance(image_id, str)
            or not image_id.strip()
            or image_identity.get("image_id") != image_id
            or not isinstance(image_identity.get("attachment_ids"), list)
        ):
            raise ValueError("material review image binding is invalid")

        state = lifecycle.get("state")
        if (
            state not in MATERIAL_REVIEW_STATES
            or review.get("state") != state
            or review.get("human_confirmed") is not False
            or lifecycle.get("human_confirmed") is not False
            or lifecycle.get("admitted") is not False
        ):
            raise ValueError("material review lifecycle is not restorable")

        user_correction = record.get("user_correction")
        if (
            not isinstance(user_correction, dict)
            or user_correction.get("source") != "USER_CORRECTION"
            or record.get("original_correction_text")
            != user_correction.get("verbatim")
            or authentication
            != {
                "status": "AUTHENTICATED_CONFIRMATION_ACTOR_UNAVAILABLE",
                "confirmation_enabled": False,
            }
            or "confirmed_by" in record
        ):
            raise ValueError("material review correction or authentication is invalid")

        return copy.deepcopy(record)

    def _validated_material_correction_reviews(
        self, records, project_id, session_id=None, messages=None
    ):
        if records is None:
            return [], []
        if not isinstance(records, list):
            return [], ["material_correction_reviews_not_a_list"]

        ordered = []
        by_id = {}
        conflicts = set()
        errors = []
        for index, item in enumerate(records):
            try:
                record = self._validate_material_correction_review(
                    item,
                    expected_project_id=str(project_id),
                    expected_session_id=session_id,
                )
                if messages is not None:
                    if not isinstance(messages, list):
                        raise ValueError("material review message list is invalid")
                    message_index = self.resolve_ref(
                        messages, record["origin"]["message_ref"]
                    )
                    if message_index is None:
                        raise ValueError("material review message reference is missing")
                    message = messages[message_index]
                    if (
                        not isinstance(message, dict)
                        or message.get("role") != "user"
                        or str(message.get("text") or "").strip()
                        != record["original_correction_text"].strip()
                    ):
                        raise ValueError("material review message binding is invalid")
                    message_attachment_ids = [
                        str(attachment.get("id"))
                        for attachment in (message.get("attachments") or [])
                        if isinstance(attachment, dict)
                        and attachment.get("id") is not None
                    ]
                    if (
                        record["origin"]["image_identity"]["attachment_ids"]
                        != message_attachment_ids
                    ):
                        raise ValueError("material review attachment binding is invalid")
            except ValueError as exc:
                errors.append("record_%d:%s" % (index, str(exc)))
                continue

            review_id = record["review_id"]
            if review_id in by_id:
                if by_id[review_id] != record:
                    conflicts.add(review_id)
                    errors.append(
                        "record_%d:duplicate_review_identity_conflict" % index
                    )
                continue
            by_id[review_id] = record
            ordered.append(review_id)

        return [by_id[key] for key in ordered if key not in conflicts], errors

    def remember_material_correction_review(
        self,
        conversation_state,
        record,
        *,
        project_id=None,
        session_id=None,
    ):
        state = getattr(conversation_state, "state", conversation_state)
        if not isinstance(state, dict):
            raise ValueError("conversation state is unavailable")

        origin = record.get("origin") if isinstance(record, dict) else None
        origin_project_id = (
            origin.get("project_id") if isinstance(origin, dict) else None
        )
        trusted_project_id = (
            str(project_id) if project_id is not None else origin_project_id
        )
        trusted_session_id = (
            str(session_id)
            if session_id is not None
            else (origin.get("session_id") if isinstance(origin, dict) else None)
        )
        valid = self._validate_material_correction_review(
            record,
            expected_project_id=trusted_project_id,
            expected_session_id=trusted_session_id,
        )
        current, errors = self._validated_material_correction_reviews(
            state.get(MATERIAL_REVIEW_KEY),
            trusted_project_id,
            trusted_session_id,
            state.get("messages"),
        )
        if errors:
            state[MATERIAL_REVIEW_ERROR_KEY] = list(errors)

        for existing in current:
            if existing["review_id"] == valid["review_id"]:
                if existing != valid:
                    raise ValueError("material review identity already has other data")
                state[MATERIAL_REVIEW_KEY] = current
                return copy.deepcopy(existing)

        current.append(valid)
        state[MATERIAL_REVIEW_KEY] = current
        return copy.deepcopy(valid)

    def material_correction_reviews(
        self, project_id, pending_only=False, session_id=None
    ):
        payload = self.load(project_id)
        records, _errors = self._validated_material_correction_reviews(
            payload.get(MATERIAL_REVIEW_KEY),
            project_id,
            session_id,
            payload.get("messages"),
        )
        if pending_only:
            records = [
                item for item in records
                if item.get("lifecycle", {}).get("state") == "pending_review"
            ]
        return copy.deepcopy(records)
    def save(self, project_id, state, extra=None, session_id=None):

        messages = []

        ui = {}

        if isinstance(state, dict):

            raw_messages = state.get("messages")

            if isinstance(raw_messages, list):

                messages = _sanitize(raw_messages[-MAX_MESSAGES:])

            ui = _sanitize(state.get("ui") or {})

        material_reviews, material_review_errors = (
            self._validated_material_correction_reviews(
                state.get(MATERIAL_REVIEW_KEY) if isinstance(state, dict) else None,
                project_id,
                session_id,
                messages,
            )
        )

        payload = {

            "contract": CONTRACT,
            "version": VERSION,

            "project_id": project_id,

            "updated_at": time.time(),

            "message_count": len(messages),
            "messages": messages,

            "ui": ui,

            MATERIAL_REVIEW_KEY: _sanitize(material_reviews),
            MATERIAL_REVIEW_ERROR_KEY: _sanitize(material_review_errors),
        }

        if isinstance(extra, dict):

            payload.update(_sanitize(extra))

        atomic_write_json(self.path(project_id), payload)

        return payload

    # ======================================================
    # LOAD
    # ======================================================

    def load(self, project_id):

        payload = read_json(self.path(project_id), default=None)

        if not isinstance(payload, dict):

            return {

                "contract": CONTRACT,
                "version": VERSION,

                "project_id": project_id,
                "message_count": 0,
                "messages": [],
                "ui": {},
            }

        return payload

    # ======================================================
    # HYDRATE / APPEND
    # ======================================================

    def hydrate(self, project_id, conversation_state, session_id=None):

        """Restore persisted messages into a ConversationState."""

        if conversation_state is None:

            return 0

        payload = self.load(project_id)

        messages = payload.get("messages") or []

        state = getattr(conversation_state, "state", None)

        if not isinstance(state, dict):

            return 0

        if messages:

            state["messages"] = list(messages)

        if payload.get("ui"):

            state.setdefault("ui", {}).update(payload["ui"])

        material_reviews, material_review_errors = (
            self._validated_material_correction_reviews(
                payload.get(MATERIAL_REVIEW_KEY),
                project_id,
                session_id,
                messages,
            )
        )
        state[MATERIAL_REVIEW_KEY] = material_reviews
        state[MATERIAL_REVIEW_ERROR_KEY] = list(
            payload.get(MATERIAL_REVIEW_ERROR_KEY) or []
        ) + material_review_errors

        state["restored_from_disk"] = True

        state["restored_at"] = time.time()

        return len(messages)

    def append_message(
        self,
        project_id,
        role,
        text="",
        attachments=None,
        state=None,
    ):

        payload = self.load(project_id)

        messages = payload.get("messages") or []

        messages.append(_sanitize({
            "role": role,
            "text": str(text or ""),
            "attachments": attachments or [],
            "at": time.time(),
        }))

        payload["messages"] = messages[-MAX_MESSAGES:]

        payload["message_count"] = len(payload["messages"])

        payload["updated_at"] = time.time()

        payload.setdefault("contract", CONTRACT)

        payload.setdefault("version", VERSION)

        payload["project_id"] = project_id

        atomic_write_json(self.path(project_id), payload)

        return payload

    def clear(self, project_id):

        return self.save(project_id, {"messages": []})


    # ======================================================
    # SENT_MESSAGE_EDIT_V1 — STABLE TURN IDENTITY
    #
    # `turn_seq` is a per-project MONOTONIC COUNTER, not an array
    # index. It is persisted in `next_turn_seq` and never reused, so
    # the 100-message retention cap can drop an old message without
    # ever making a surviving message's identity ambiguous.
    #
    # Messages written before this change have no `turn_seq`. They are
    # NEVER rewritten: a deterministic content reference is derived at
    # read time instead, so historical conversations stay byte-stable.
    # ======================================================

    def message_ref(self, messages, index):
        """A stable wire reference for `messages[index]`.

        - a sequenced message   -> "seq:<n>"
        - a legacy message      -> "legacy:<hash>"

        The legacy hash is (role, text, occurrence-of-that-exact-pair),
        so two messages with IDENTICAL text still resolve to different
        references. It is not an array index and needs no migration.
        """

        if not isinstance(messages, list) or not (0 <= index < len(messages)):

            return None

        entry = messages[index]

        if not isinstance(entry, dict):

            return None

        seq = entry.get("turn_seq")

        if isinstance(seq, int) and not isinstance(seq, bool):

            return "seq:%d" % seq

        role = str(entry.get("role") or "")

        text = str(entry.get("text") or "")

        occurrence = 0

        for earlier in messages[:index]:

            if (
                isinstance(earlier, dict)
                and str(earlier.get("role") or "") == role
                and str(earlier.get("text") or "") == text
            ):

                occurrence += 1

        digest = hashlib.sha1(
            ("%s\x00%s\x00%d" % (role, text, occurrence)).encode("utf-8")
        ).hexdigest()[:16]

        return "legacy:" + digest

    def resolve_ref(self, messages, ref):
        """Index of the message `ref` points at, or None.

        Resolution re-derives every reference from the CURRENT stored
        list, so it stays correct after the retention cap drops older
        messages and after a process restart.
        """

        if not isinstance(messages, list) or not isinstance(ref, str):

            return None

        for index in range(len(messages)):

            if self.message_ref(messages, index) == ref:

                return index

        return None

    def active_prefix(self, messages, index):
        """The valid history BEFORE `index`.

        A message marked `superseded_by` was invalidated by an earlier
        revision and is NOT active conversational context, so it is
        excluded even though it is still stored and still visible.
        """

        prefix = []

        for entry in messages[:index]:

            if not isinstance(entry, dict):

                continue

            if entry.get("superseded_by") is not None:

                continue

            role = entry.get("role")

            if role not in ("user", "assistant"):

                continue

            prefix.append({"role": role, "text": str(entry.get("text") or "")})

        return prefix

    def _next_turn_seq(self, payload):

        current = payload.get("next_turn_seq")

        if isinstance(current, int) and not isinstance(current, bool):

            return current

        # First use on an existing project: continue after the highest
        # sequence already present, else start at 1.
        highest = 0

        for entry in payload.get("messages") or []:

            if isinstance(entry, dict):

                seq = entry.get("turn_seq")

                if isinstance(seq, int) and not isinstance(seq, bool):

                    highest = max(highest, seq)

        return highest + 1

    def append_turn(self, project_id, role, text, attachments=None, extra=None):
        """Append ONE message with a fresh `turn_seq` and persist atomically.

        Deliberately does NOT go through `save()`: that rebuilds the
        payload from a ConversationState and would drop `next_turn_seq`,
        `last_revision_nonce` and every `revises` / `superseded_by` mark.
        """

        payload = self.load(project_id)

        messages = payload.get("messages")

        if not isinstance(messages, list):

            messages = []

        seq = self._next_turn_seq(payload)

        entry = {
            "role": role,
            "text": str(text or ""),
            "attachments": attachments or [],
            "at": time.time(),
            "turn_seq": seq,
        }

        if isinstance(extra, dict):

            entry.update(_sanitize(extra))

        messages.append(_sanitize(entry))

        payload["messages"] = messages[-MAX_MESSAGES:]

        payload["message_count"] = len(payload["messages"])

        payload["next_turn_seq"] = seq + 1

        payload["updated_at"] = time.time()

        payload.setdefault("contract", CONTRACT)

        payload["version"] = VERSION

        payload["project_id"] = project_id

        atomic_write_json(self.path(project_id), payload)

        return payload, seq

    def mark_superseded(self, project_id, from_index, superseded_by, to_index=None):
        """Mark the messages in [from_index, to_index) as superseded.

        `to_index` is REQUIRED by the revision path: the newly appended
        revision messages also sit after `from_index`, and they must stay
        active. The text, attachments and timestamps are untouched, so the
        old branch remains fully recoverable — it is simply no longer
        ACTIVE context.
        """

        payload = self.load(project_id)

        messages = payload.get("messages")

        if not isinstance(messages, list):

            return payload

        stop = len(messages) if to_index is None else max(0, min(int(to_index), len(messages)))

        changed = 0

        for entry in messages[from_index:stop]:

            if isinstance(entry, dict) and entry.get("superseded_by") is None:

                entry["superseded_by"] = superseded_by

                changed += 1

        if changed:

            payload["messages"] = messages

            payload["updated_at"] = time.time()

            atomic_write_json(self.path(project_id), payload)

        return payload

    def set_last_revision_nonce(self, project_id, nonce):

        payload = self.load(project_id)

        payload["last_revision_nonce"] = nonce

        payload["updated_at"] = time.time()

        atomic_write_json(self.path(project_id), payload)

        return payload



conversation_store = ConversationStore()
