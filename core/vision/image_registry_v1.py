# ==========================================================
# ArchitectOS Image Registry v1
#
# VISION_IMAGE_REGISTRY_04
#
# Session-scoped registry of every image the chat can refer to:
# user uploads, text-to-image renders, image-to-image results and
# any other produced asset.
#
# Guarantees
#   - strict session isolation (no cross-session leakage)
#   - sequential ordinal numbering per session (1-based)
#   - last_render / last_uploaded / active_image always resolvable
#   - provenance preserved (path, source_type, parent, attachment)
#   - bounded memory (oldest non-active records evicted first)
#
# In-memory by default.
#
# PROJECT_WORKSPACE_UI_06
#   Persistence is now possible WITHOUT changing this contract:
#   a project layer may attach a write-through persistence callback
#   (`attach_persistence`) and hydrate a session bucket
#   (`hydrate`) on project open.  With no callback attached the
#   behaviour is byte-for-byte identical to Phase 04.
# ==========================================================


from __future__ import annotations


import threading
import time
import uuid


CONTRACT = "ImageRegistryV1"
VERSION = "1.0"


SOURCE_TYPES = (
    "uploaded",
    "text_to_image",
    "image_to_image",
    "render",
    "other",
)


# Source types that count as a "render" for last_render lookups.
RENDER_SOURCE_TYPES = ("text_to_image", "image_to_image", "render")


DEFAULT_SESSION_KEY = "__default__"

MAX_SESSIONS = 512

MAX_IMAGES_PER_SESSION = 200


def normalize_session_key(session_id):

    if session_id is None:

        return DEFAULT_SESSION_KEY

    key = str(session_id).strip()

    if not key:

        return DEFAULT_SESSION_KEY

    return key[:128]



class ImageRegistryV1:

    VERSION = VERSION

    def __init__(self):

        self._sessions = {}

        self._lock = threading.RLock()

        # PROJECT_WORKSPACE_UI_06 — optional write-through hook.
        # None -> Phase 04 in-memory behaviour, unchanged.
        self._persist_callback = None

        print(
            "🗃️ IMAGE REGISTRY v1.0 ONLINE (session-scoped)"
        )


    # ======================================================
    # PROJECT PERSISTENCE BRIDGE  (PROJECT_WORKSPACE_UI_06)
    # ======================================================

    def attach_persistence(self, callback):

        """Register a write-through callback: callback(session_key)."""

        self._persist_callback = callback

        return callback

    def detach_persistence(self):

        self._persist_callback = None

    def _notify(self, session_key):

        callback = self._persist_callback

        if callback is None:

            return

        try:

            callback(session_key)

        except Exception as error:

            print("⚠️ IMAGE REGISTRY PERSIST ERROR:", error)

    def snapshot(self, session_id):

        """Deep-ish copy of one session bucket (for persistence)."""

        with self._lock:

            key, bucket = self._bucket(session_id)

            return key, [dict(record) for record in bucket]

    def hydrate(self, session_id, records):

        """Replace a session bucket from persisted records.

        Ordinals and the active flag are restored verbatim so that
        "عکس اول" / "رندر قبلی" keep resolving after a restart.
        """

        if not isinstance(records, (list, tuple)):

            return []

        with self._lock:

            key = normalize_session_key(session_id)

            bucket = []

            for record in records:

                if not isinstance(record, dict):

                    continue

                item = dict(record)

                item.setdefault("contract", CONTRACT)
                item.setdefault("version", VERSION)
                item.setdefault("session_id", key)

                if not item.get("image_id"):

                    item["image_id"] = "img_" + uuid.uuid4().hex[:12]

                if not isinstance(item.get("ordinal"), int):

                    item["ordinal"] = len(bucket) + 1

                item["active"] = bool(item.get("active"))

                bucket.append(item)

            self._sessions[key] = bucket

            return [self._public(r) for r in bucket]


    # ======================================================
    # INTERNAL
    # ======================================================

    def _bucket(self, session_id):

        key = normalize_session_key(session_id)

        bucket = self._sessions.get(key)

        if bucket is None:

            if len(self._sessions) >= MAX_SESSIONS:

                self._sessions.pop(
                    next(iter(self._sessions))
                )

            bucket = []

            self._sessions[key] = bucket

        return key, bucket


    def _find(self, bucket, image_id):

        for record in bucket:

            if record.get("image_id") == image_id:

                return record

        return None


    @staticmethod
    def _public(record):

        return dict(record) if isinstance(record, dict) else None


    # ======================================================
    # REGISTER
    # ======================================================

    def register(
        self,
        session_id,
        *,
        path=None,
        source_type="other",
        label=None,
        parent_image_id=None,
        asset=None,
        attachment=None,
        analysis=None,
        analysis_status="pending",
        make_active=True,
    ):
        """Add one image to the session registry."""

        if source_type not in SOURCE_TYPES:

            source_type = "other"


        with self._lock:

            key, bucket = self._bucket(session_id)


            record = {

                "contract": CONTRACT,
                "version": VERSION,

                "image_id": "img_" + uuid.uuid4().hex[:12],

                "session_id": key,

                "ordinal": len(bucket) + 1,

                "source_type": source_type,

                "path": path,

                "asset": asset,

                "attachment": attachment,

                "created_at": time.time(),

                "label": label,

                "parent_image_id": parent_image_id,

                "analysis_status": analysis_status,

                "analysis": analysis,

                "active": False,

            }


            if make_active:

                for existing in bucket:

                    existing["active"] = False

                record["active"] = True


            bucket.append(record)


            # bounded: evict oldest non-active first
            while len(bucket) > MAX_IMAGES_PER_SESSION:

                for index, existing in enumerate(bucket):

                    if not existing.get("active"):

                        bucket.pop(index)

                        break

                else:

                    break


            self._notify(key)

            return self._public(record)


    # ======================================================
    # LOOKUP
    # ======================================================

    def list(self, session_id):

        with self._lock:

            key, bucket = self._bucket(session_id)

            return [self._public(r) for r in bucket]


    def count(self, session_id):

        with self._lock:

            key, bucket = self._bucket(session_id)

            return len(bucket)


    def get(self, session_id, image_id):

        with self._lock:

            key, bucket = self._bucket(session_id)

            record = self._find(bucket, image_id)

            return self._public(record)


    def active(self, session_id):

        with self._lock:

            key, bucket = self._bucket(session_id)

            for record in reversed(bucket):

                if record.get("active"):

                    return self._public(record)

            return None


    def by_ordinal(self, session_id, ordinal):

        try:

            ordinal = int(ordinal)

        except (TypeError, ValueError):

            return None


        with self._lock:

            key, bucket = self._bucket(session_id)

            for record in bucket:

                if record.get("ordinal") == ordinal:

                    return self._public(record)

            return None


    def last(self, session_id, source_types=None):

        with self._lock:

            key, bucket = self._bucket(session_id)

            for record in reversed(bucket):

                if source_types and record.get("source_type") not in source_types:

                    continue

                return self._public(record)

            return None


    def last_render(self, session_id):

        return self.last(
            session_id,
            source_types=RENDER_SOURCE_TYPES
        )


    def last_uploaded(self, session_id):

        return self.last(
            session_id,
            source_types=("uploaded",)
        )


    # ======================================================
    # MUTATION
    # ======================================================

    def set_active(self, session_id, image_id):

        with self._lock:

            key, bucket = self._bucket(session_id)

            target = self._find(bucket, image_id)

            if target is None:

                return None

            for record in bucket:

                record["active"] = record is target

            self._notify(key)

            return self._public(target)


    def set_analysis(
        self,
        session_id,
        image_id,
        analysis,
        status=None,
    ):

        with self._lock:

            key, bucket = self._bucket(session_id)

            target = self._find(bucket, image_id)

            if target is None:

                return None

            target["analysis"] = analysis

            target["analysis_status"] = (
                status
                if status is not None
                else (analysis or {}).get("analysis_status", "unknown")
            )

            self._notify(key)

            return self._public(target)


    def reset(self, session_id):

        with self._lock:

            key = normalize_session_key(session_id)

            self._sessions.pop(key, None)

            self._notify(key)

            return []


    def update_record(self, session_id, image_id, fields):

        """Patch one record in place (PROJECT_WORKSPACE_UI_06).

        Used by the project layer to re-point an asset at its managed
        project-scoped copy. Public behaviour is unchanged when unused.
        """

        if not isinstance(fields, dict):

            return None

        with self._lock:

            key, bucket = self._bucket(session_id)

            target = self._find(bucket, image_id)

            if target is None:

                return None

            for field, value in fields.items():

                if field in ("image_id", "contract", "version"):

                    continue

                target[field] = value

            self._notify(key)

            return self._public(target)


    # ======================================================
    # DIAGNOSTICS
    # ======================================================

    def sessions(self):

        with self._lock:

            return sorted(self._sessions.keys())


    def session_count(self):

        with self._lock:

            return len(self._sessions)



# ==========================================================
# SINGLETON
# ==========================================================

image_registry = ImageRegistryV1()
