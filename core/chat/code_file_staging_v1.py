# -*- coding: utf-8 -*-
"""CODER-05B — STAGED CODE FILE PROPOSAL WITH EXPLICIT APPROVAL.

The existing writer (``project_code_file_writer_v1``) already owns the
filesystem rules. This module adds the MISSING connection between generated
source and that writer: a proposal the user can review, and an approval that is
a genuine user action rather than a model string.

Rules
-----
* Staging NEVER writes. It validates, computes the digest, checks the syntax
  and renders a preview/diff.
* Approval writes the STAGED bytes — never a regenerated version.
* Approval is single-use, project-bound and content-bound (the digest is
  recorded with the proposal).
* A proposal whose target already exists requires a separate overwrite
  confirmation.
* ``approval_source="model"`` can never approve: a model-generated string is
  not a user action.
* All filesystem safety is delegated to the existing writer; this module adds
  no second write path.

CODER-REPAIR-01 — repairing a PENDING proposal
----------------------------------------------
A pending proposal used to be unrecoverable: the creation route refuses to
overwrite it (correctly), so a user who could see the defect had no way to ask
for a fix short of discarding the draft and regenerating the whole file.

``replace_staged_file`` closes that gap without weakening the guard:

* the repair BASE is the server-owned pending proposal — never conversation
  history, never a browser-supplied source;
* the base is bound by project, actor, session, digest AND revision, so a
  proposal that changed while the model was generating cannot be repaired;
* the candidate is validated against the base with ``infer_changed_scope``:
  exactly ONE function/method body may differ, and imports, module-level code,
  class structure, other functions and decorators must be byte-identical;
* every rejection leaves the original proposal untouched;
* a successful replacement issues a NEW capability bound to the NEW digest, so
  the previous save approval cannot write the new bytes;
* it grants NO execution, NO packaging and NO consent authority.

No execution, no import of the staged source, no shell, no packaging.
"""

import ast
from copy import deepcopy
import hashlib
import os
import re
import secrets
import time
import threading

CONTRACT = "CodeFileStagingV1"
VERSION = "1.0"

STATUS_AWAITING_APPROVAL = "awaiting_approval"
STATUS_WRITTEN = "written"
STATUS_REJECTED = "rejected"

#: CODER-REPAIR-01 — a validated repair REPLACES the pending proposal. It is
#: still unsaved: the replacement is staged, not written.
STATUS_REPLACED = "replaced"

REPAIR_ORIGIN = "coder_repair"

APPROVAL_BLOCKED_MODEL_TEXT = "approval_source_not_user"

CODE_SUBDIR = "code"
MAX_PREVIEW_CHARS = 1200

#: Explicit approval vocabulary. Both languages are accepted because the
#: assistant is bilingual; this is a UI vocabulary, not an architectural rule.
#:
#: CODER-STAGING-ACTION-SAFETY-01 — a bare "تأیید" is deliberately absent. It
#: is the NOUN used by status lines ("تأیید عملکردی"), by refusals
#: ("تأیید نمی‌کنم") and by questions ("آیا تأیید می‌کنی؟"). Only an ACTION
#: form grants anything.
_APPROVAL_MARKERS = (
    "تأیید می\u200cکنم", "تایید می\u200cکنم",
    "تأیید می کنم", "تایید می کنم",
    "ذخیره کن", "ذخیره کنید", "بله ذخیره", "ثبت کن",
    "approve", "approved", "confirm", "save it", "save the file", "yes, save",
)

# A no-pending turn needs a stricter discriminator than the pending proposal's
# approval vocabulary: "save the file" can also be a genuine new creation
# request. These markers unambiguously refer to an approval/rejection action
# and therefore terminate the turn even after a proposal was consumed.
_EXPLICIT_APPROVAL_TURN_MARKERS = (
    "تأیید می\u200cکنم", "تایید می\u200cکنم",
    "تأیید می کنم", "تایید می کنم",
    "approve", "approved", "confirm", "yes, save",
)

_EXPLICIT_REJECTION_TURN_MARKERS = (
    "رد کن", "ردش کن", "لغو کن", "انصراف", "reject", "cancel the file",
    "don't save", "do not save",
)

_NEW_CREATION_TURN_MARKERS = (
    "create", "make a new", "new file", "بساز", "ایجاد کن", "فایل جدید",
)

# ==========================================================
# ACTION vs MENTION — ONE approval/rejection classifier
#
# Measured 2026-10-26 in project_5893d83b: an isolated-verification request
# containing «عدد ۵ را وارد کن» was answered with «پیش‌نویس ... رد شد».
# «وارد کن» ENDS WITH «رد کن», and the classifier was a substring test.
#
# Approving or rejecting is a privileged state change, so it is selected ONLY
# from an explicit, affirmative, current command. Everything else is a MENTION
# and authorises nothing.
# ==========================================================

#: Characters that make up a word. A marker must not match INSIDE a longer
#: word: «وارد کن» contains «رد کن» as a suffix and «رد کنم» as a prefix.
_WORD_CHARS = "A-Za-z0-9_\u0621-\u064a\u066e-\u06d3\u200c"

#: A functional-verification STATUS is not consent vocabulary.
_STATUS_PHRASES = (
    "تأیید عملکردی", "تایید عملکردی", "تأیید نشده", "تایید نشده",
    "تأییدنشده", "تاییدنشده", "تأیید شده", "تایید شده",
    "functional verification",
)

#: Quoted spans are mentions: a command inside quotes is being discussed.
_QUOTED_SPAN = re.compile(r"`[^`]*`|\"[^\"]*\"|«[^»]*»|\u201c[^\u201d]*\u201d")

#: A question asks ABOUT the action; it does not perform it.
_INTERROGATIVE_MARKERS = (
    "آیا", "?", "؟", "should i", "shall i", "do i need", "can i ", "may i ",
)

#: A deferred or conditional mention does not act now.
_DEFERRED_MARKERS = (
    "بعد از بررسی", "پس از بررسی", "بعد از اینکه", "پس از اینکه",
    "بعداً", "بعدا", "در آینده", "فعلاً", "فعلا", "شاید", "ممکن است",
    "وقتی که", "در صورت", "اگر ",
    "later", "tomorrow", "after i", "after you", "will confirm",
    "will approve", "once i", "not yet", "هنوز",
)

#: English negation that can precede a marker ("do not approve").
_EN_NEGATIONS = ("not ", "n't ", "no ", "never ", "without ", "don't ", "do not ")

#: Bare approval vocabulary — enough to recognise that the user is TALKING
#: about approval, never enough to grant it.
_APPROVAL_MENTIONS = ("تأیید", "تایید", "approve", "confirm")


def _marker_matches(lowered, marker):
    """True when ``marker`` appears as a WHOLE word and is not negated.

    Both boundaries are required. «وارد کن» fails the LEFT boundary and
    «رد کنم» fails the RIGHT one, so neither can be read as «رد کن».
    """

    needle = marker.replace("\u200c", " ").lower()

    pattern = r"(?<![%(chars)s])%(marker)s(?![%(chars)s])" % {
        "chars": _WORD_CHARS,
        "marker": re.escape(needle),
    }

    for match in re.finditer(pattern, lowered, re.IGNORECASE):

        window = lowered[max(0, match.start() - 20):match.start()]

        if any(negation in window for negation in _EN_NEGATIONS):

            continue

        return True

    return False


def _consent_text(text):
    """The part of a turn that may carry an ACTION.

    Quoted spans and functional-verification status phrases are removed first,
    so a quoted command or a status echo can never be read as consent.
    """

    body = _QUOTED_SPAN.sub(" ", str(text or ""))

    lowered = body.lower().replace("\u200c", " ")

    for phrase in _STATUS_PHRASES:

        lowered = lowered.replace(phrase.replace("\u200c", " "), " ")

    return lowered


def mentions_approval(text):
    """True when the turn talks about approval at all. Never authorises it."""

    lowered = str(text or "").lower().replace("\u200c", " ")

    return any(marker in lowered for marker in _APPROVAL_MENTIONS)


def staged_file_action(text):
    """Classify a turn as an EXPLICIT approval/rejection ACTION, or ``None``.

    This does not authorize anything. It only prevents a mention from being
    treated as a command. Authorization still belongs to
    ``approve_staged_file`` and the caller's trust boundary.
    """

    lowered = _consent_text(text)

    if not lowered.strip():

        return None

    # A filename may itself contain words such as ``rejected.py`` or
    # ``approve.py``. An explicit new/create verb wins; those names must not be
    # mistaken for replay actions.
    if any(marker in lowered for marker in _NEW_CREATION_TURN_MARKERS):

        return None

    # A question is a mention.
    if any(marker in lowered for marker in _INTERROGATIVE_MARKERS):

        return None

    rejects = any(
        _marker_matches(lowered, marker)
        for marker in _EXPLICIT_REJECTION_TURN_MARKERS
    )

    approves = any(
        _marker_matches(lowered, marker)
        for marker in _EXPLICIT_APPROVAL_TURN_MARKERS
    )

    if not rejects and not approves:

        return None

    # "بعد از بررسی تأیید می‌کنم" describes a FUTURE action.
    if any(marker in lowered for marker in _DEFERRED_MARKERS):

        return None

    return "reject" if rejects else "approve"

_STAGED = {}
_CAPABILITY_TOKENS = {}
_STAGING_LOCK = threading.RLock()

#: CODER-REPAIR-01 — per-project monotonic counter. It makes "the pending
#: proposal has not changed since I read it" an explicit, checkable fact even
#: when two consecutive proposals happen to carry identical bytes.
_REVISIONS = {}


def reset_staging():
    """Drop every staged proposal (tests and explicit resets)."""
    _STAGED.clear()
    _CAPABILITY_TOKENS.clear()
    _REVISIONS.clear()


def _trusted_binding(authorization, project_id):
    if not isinstance(authorization, dict) or authorization.get("trusted") is not True:
        return None
    actor = str(authorization.get("actor_id") or "")
    session = str(authorization.get("session_id") or "")
    auth_project = str(authorization.get("project_id") or "")
    if not actor or not session or auth_project != str(project_id):
        return None
    return {"actor_id": actor, "session_id": session, "project_id": auth_project}


def _new_capability(project_id, scope, now, ttl):
    token = "stg_" + secrets.token_urlsafe(32)
    _CAPABILITY_TOKENS[project_id] = token
    return token, {
        "scope": scope,
        "issued_at": float(now),
        "expires_at": float(now) + max(1, int(ttl)),
        "token_hash": hashlib.sha256(token.encode("utf-8")).hexdigest(),
    }


def public_approval_capability(project_id, authorization):
    proposal = _STAGED.get(project_id)
    if not isinstance(proposal, dict) or not proposal.get("authorization_binding"):
        return None
    binding = _trusted_binding(authorization, project_id)
    if binding != proposal.get("authorization_binding"):
        return None
    token = _CAPABILITY_TOKENS.get(project_id)
    if not token or proposal.get("capability", {}).get("consumed"):
        return None
    return {
        "token": token,
        "scope": proposal.get("capability", {}).get("scope"),
        "expires_at": proposal.get("capability", {}).get("expires_at"),
        "filename": proposal.get("filename"),
        "digest": proposal.get("digest"),
    }


def _digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sandbox(documents_root, project_id):
    if documents_root:
        return os.path.join(documents_root, CODE_SUBDIR)

    try:
        from core.project.project_workspace_v1 import project_workspace

        return os.path.join(
            project_workspace.subdir(project_id, "documents"), CODE_SUBDIR
        )
    except Exception:
        return None


def _syntax(content):
    try:
        ast.parse(content)
        return True, None
    except SyntaxError as error:
        return False, {
            "line": error.lineno,
            "column": error.offset,
            "message": error.msg,
        }
    except Exception as error:
        return False, {"line": None, "column": None, "message": str(error)}


def _preview(content):
    # Approval messages must show the COMPLETE source so the user can review
    # before confirming.  Truncation belongs in display/UI layers, not in the
    # canonical proposal payload that feeds the approval gate.
    return content


def _diff_against(existing, content):
    import difflib

    return "".join(
        difflib.unified_diff(
            existing.splitlines(keepends=True),
            content.splitlines(keepends=True),
            fromfile="existing",
            tofile="proposed",
        )
    )


def stage_code_file(
    project_id,
    filename,
    content,
    documents_root=None,
    origin=None,
    authorization=None,
    now=None,
    approval_ttl_seconds=300,
    requirements=None,
):
    """Validate and stage ONE source file. Never writes.

    CODER QUALITY GATE (Tier 1) — ``requirements`` are the user's own
    enumerated acceptance criteria, echoed verbatim into the proposal's
    ``quality`` block. They are annotations only: ``content`` and ``digest``
    are computed from the ORIGINAL bytes and are never rewritten by review.
    """

    from core.chat.project_code_file_writer_v1 import (
        MAX_CODE_FILE_BYTES,
        validate_code_filename,
        validate_project_id,
    )

    proposal = {
        "contract": CONTRACT,
        "version": VERSION,
        "project_id": str(project_id) if project_id else None,
        "filename": filename,
        "status": STATUS_REJECTED,
        "reason": None,
        "writes_performed": 0,
        "content": None,
        "digest": None,
        "preview": None,
        "diff": None,
        "target_exists": False,
        "requires_overwrite_confirmation": False,
        "syntax_valid": None,
        "syntax_error": None,
        "quality": None,
        "approval_token": None,
        "origin": origin,
    }

    if not isinstance(project_id, str) or not project_id.strip():
        proposal["reason"] = "missing_project_context"
        return proposal

    if not validate_project_id(project_id):
        proposal["reason"] = "invalid_project_id"
        return proposal

    ok, reason = validate_code_filename(filename)

    if not ok:
        proposal["reason"] = reason
        return proposal

    if not isinstance(content, str) or not content.strip():
        proposal["reason"] = "empty_source"
        return proposal

    if len(content.encode("utf-8")) > MAX_CODE_FILE_BYTES:
        proposal["reason"] = "file_too_large"
        return proposal

    syntax_valid, syntax_error = _syntax(content)

    sandbox = _sandbox(documents_root, project_id)
    target_exists = False
    diff = None

    if sandbox:
        target = os.path.join(sandbox, filename)
        if os.path.isfile(target):
            target_exists = True
            try:
                existing = open(target, "r", encoding="utf-8", errors="replace").read()
                diff = _diff_against(existing, content)
            except Exception:
                diff = None

    digest = _digest(content)

    # CODER QUALITY GATE (Tier 1) — three SEPARATE verdicts. The review reads
    # the original source and never alters it: ``content``, ``preview`` and
    # ``digest`` above stay byte-exact. ``functional`` is NOT_RUN by contract
    # and cannot be inferred from the other two.
    try:

        from core.chat.code_quality_review_v1 import build_quality_block

        quality = build_quality_block(
            content, syntax_valid, syntax_error, requirements
        )

    except Exception:

        # A review failure must never block staging; it reports honestly as
        # "not performed" instead of pretending the code is fine.
        quality = None

    current = time.time() if now is None else float(now)
    binding = _trusted_binding(authorization, project_id)
    token = "stg_" + secrets.token_hex(16)
    capability = None
    if authorization is not None:
        if binding is None:
            proposal["reason"] = "trusted_authorization_required"
            return proposal
        token, capability = _new_capability(
            project_id, "save", current, approval_ttl_seconds
        )
        capability.update({"filename": filename, "digest": digest})

    proposal.update(
        {
            "status": STATUS_AWAITING_APPROVAL,
            "reason": None,
            "content": content,
            "digest": digest,
            "preview": _preview(content),
            "diff": diff,
            "target_exists": target_exists,
            "requires_overwrite_confirmation": target_exists,
            "syntax_valid": syntax_valid,
            "syntax_error": syntax_error,
            "quality": quality,
            "approval_token": token,
            "authorization_binding": binding,
            "capability": capability,
        }
    )

    # CODER-REPAIR-01 — every stored proposal carries its revision, so a repair
    # can prove it is editing the proposal it actually read.
    #
    # The revision bump and the store write MUST be one critical section. When
    # the bump was locked but the assignment was not, a concurrent staging
    # could interleave between them and leave ``revision`` describing bytes
    # that were no longer stored — which is exactly the invariant the repair
    # compare-and-swap depends on. Measured: two writers produced a stored
    # revision from one writer and stored content from the other.
    with _STAGING_LOCK:

        revision = int(_REVISIONS.get(project_id, 0)) + 1
        _REVISIONS[project_id] = revision

        proposal["revision"] = revision

        # The stored proposal is private mutable state. Callers receive a
        # detached projection so preview/UI code cannot alter the bytes later
        # approved.
        stored = deepcopy(proposal)
        if binding:
            stored["approval_token"] = None
        _STAGED[project_id] = stored

    return deepcopy(proposal)


def pending_proposal(project_id):
    proposal = _STAGED.get(project_id)
    return deepcopy(proposal) if isinstance(proposal, dict) else None


def _expresses_approval(text):
    """True only for an affirmative, current approval ACTION.

    CODER-STAGING-ACTION-SAFETY-01 — this used to be a substring test over
    ``_APPROVAL_MARKERS``, so "تأیید عملکردی" (a status), "تأیید نمی‌کنم" (a
    refusal) and "بعد از بررسی تأیید می‌کنم" (a future intention) all counted
    as consent. It now shares the ONE classifier with ``staged_file_action``,
    so a mention can never reach the writer.
    """

    return staged_file_action(text) == "approve"


def approve_staged_file(
    project_id,
    approval_text,
    documents_root=None,
    approval_source="user",
    overwrite_confirmed=False,
    authorization=None,
    approval_token=None,
    now=None,
):
    """Write the STAGED bytes after a genuine user approval."""

    outcome = {
        "contract": CONTRACT,
        "project_id": str(project_id) if project_id else None,
        "status": "failed",
        "reason": None,
        "filename": None,
        "relative_path": None,
        "digest": None,
        "bytes_written": 0,
        "verified_on_disk": False,
        "writes_performed": 0,
    }

    proposal = _STAGED.get(project_id)

    if not isinstance(proposal, dict):
        outcome["reason"] = "no_pending_proposal"
        return outcome

    outcome["filename"] = proposal.get("filename")

    binding = proposal.get("authorization_binding")
    if binding:
        supplied = _trusted_binding(authorization, project_id)
        if supplied is None:
            outcome["reason"] = "trusted_authorization_required"
            return outcome
        if supplied.get("actor_id") != binding.get("actor_id"):
            outcome["reason"] = "approval_actor_mismatch"
            return outcome
        if supplied.get("session_id") != binding.get("session_id"):
            outcome["reason"] = "approval_session_mismatch"
            return outcome
        capability = proposal.get("capability") or {}
        current = time.time() if now is None else float(now)
        if current > float(capability.get("expires_at") or 0):
            outcome["reason"] = "approval_capability_expired"
            return outcome
        if (
            capability.get("filename") != proposal.get("filename")
            or capability.get("digest") != proposal.get("digest")
        ):
            outcome["reason"] = "approval_capability_binding_mismatch"
            return outcome
        token_hash = hashlib.sha256(str(approval_token or "").encode("utf-8")).hexdigest()
        if not secrets.compare_digest(token_hash, str(capability.get("token_hash") or "")):
            outcome["reason"] = "approval_capability_invalid"
            return outcome

    # Content and digest are a single approval unit. This catches in-process
    # corruption/tampering before the writer is called and consumes the broken
    # proposal so a later approval cannot retry unknown bytes.
    if (
        not isinstance(proposal.get("content"), str)
        or _digest(proposal.get("content")) != proposal.get("digest")
    ):
        _STAGED.pop(project_id, None)
        outcome["reason"] = "staged_content_integrity_failed"
        return outcome

    # A model string can never approve, regardless of its wording.
    if approval_source != "user":
        outcome["reason"] = APPROVAL_BLOCKED_MODEL_TEXT
        return outcome

    if not _expresses_approval(approval_text):
        outcome["reason"] = "approval_not_expressed"
        return outcome

    if proposal.get("requires_overwrite_confirmation") and not overwrite_confirmed:
        outcome["reason"] = "overwrite_confirmation_required"
        return outcome

    if binding and proposal.get("target_exists") and (proposal.get("capability") or {}).get("scope") != "overwrite":
        token, capability = _new_capability(project_id, "overwrite", time.time() if now is None else float(now), 300)
        capability.update({
            "filename": proposal.get("filename"),
            "digest": proposal.get("digest"),
        })
        proposal["capability"] = capability
        _STAGED[project_id] = proposal
        outcome["reason"] = "overwrite_capability_required"
        outcome["approval_capability"] = public_approval_capability(project_id, authorization)
        return outcome

    # Atomically claim an authorized capability immediately before the sole
    # writer call. This closes the concurrent replay window: at most one
    # request can cross this point, even if two valid signed requests arrive
    # at the same time. A failed filesystem write still consumes the one-shot
    # capability; the user must stage again rather than replay authority.
    if binding:
        with _STAGING_LOCK:
            live = _STAGED.get(project_id)
            live_capability = (live or {}).get("capability") or {}
            if not isinstance(live, dict) or live_capability.get("consumed"):
                outcome["reason"] = "approval_capability_consumed"
                return outcome
            token_hash = hashlib.sha256(str(approval_token or "").encode("utf-8")).hexdigest()
            if not secrets.compare_digest(
                token_hash, str(live_capability.get("token_hash") or "")
            ):
                outcome["reason"] = "approval_capability_invalid"
                return outcome
            live_capability["consumed"] = True
            live["capability"] = live_capability
            _STAGED[project_id] = live

    from core.chat.project_code_file_writer_v1 import create_project_code_file

    written = create_project_code_file(
        project_id=project_id,
        filename=proposal["filename"],
        content=proposal["content"],
        overwrite=bool(proposal.get("target_exists")),
        documents_root=documents_root,
    )

    if not (written.get("verified_on_disk") and written.get("status") in ("created", "overwritten")):
        outcome["reason"] = written.get("reason") or "write_failed"
        return outcome

    outcome.update(
        {
            "status": STATUS_WRITTEN,
            "reason": None,
            "relative_path": written.get("relative_path"),
            "digest": proposal["digest"],
            "bytes_written": written.get("bytes_written"),
            "verified_on_disk": True,
            "writes_performed": 1,
        }
    )

    # single use
    _STAGED.pop(project_id, None)
    _CAPABILITY_TOKENS.pop(project_id, None)

    return outcome


def reject_staged_file(project_id, reason=None, authorization=None,
                       approval_token=None, now=None):
    """Discard a pending proposal after a correctly bound user asks for it.

    Rejection is a DISCARD, never a grant: it writes nothing, imports nothing
    and executes nothing. It therefore must not depend on the write-approval
    capability still being unexpired.

    Requiring a live capability here produced an unrecoverable pending state.
    Once ``expires_at`` had passed, the proposal could not be approved (correct
    -- expiry guards the write) and could not be rejected either, while
    ``_authorized_code_file_creation`` refuses to stage a new proposal while
    one is pending. The user was locked out of their own project.

    What still gates rejection is the caller's identity, not the clock:
    ``_trusted_binding`` demands a trusted-local authorization whose actor,
    session AND project all match the proposal's binding, so a foreign session
    or a different project cannot discard someone else's proposal. ``now`` and
    ``approval_token`` stay in the signature for call-site compatibility;
    neither authorises anything on this path.
    """
    proposal = _STAGED.get(project_id)
    if isinstance(proposal, dict) and proposal.get("authorization_binding"):
        binding = proposal.get("authorization_binding")
        supplied = _trusted_binding(authorization, project_id)
        if supplied is None:
            return {"contract": CONTRACT, "project_id": project_id, "status": "failed", "reason": "trusted_authorization_required", "filename": proposal.get("filename"), "writes_performed": 0}
        if supplied.get("actor_id") != binding.get("actor_id"):
            return {"contract": CONTRACT, "project_id": project_id, "status": "failed", "reason": "approval_actor_mismatch", "filename": proposal.get("filename"), "writes_performed": 0}
        if supplied.get("session_id") != binding.get("session_id"):
            return {"contract": CONTRACT, "project_id": project_id, "status": "failed", "reason": "approval_session_mismatch", "filename": proposal.get("filename"), "writes_performed": 0}
        # Deliberately NO expiry check and NO write-token check on this path.
        # Expiry protects the WRITE (approve_staged_file keeps both checks); a
        # discard needs no write authority, and demanding one only stranded
        # proposals that had outlived their 300 s window.
    with _STAGING_LOCK:
        live = _STAGED.get(project_id)
        if isinstance(live, dict) and (live.get("capability") or {}).get("consumed"):
            return {"contract": CONTRACT, "project_id": project_id, "status": "failed", "reason": "approval_capability_consumed", "filename": live.get("filename"), "writes_performed": 0}
        proposal = _STAGED.pop(project_id, None)
        _CAPABILITY_TOKENS.pop(project_id, None)

    return {
        "contract": CONTRACT,
        "project_id": project_id,
        "status": "rejected",
        "reason": reason,
        "filename": (proposal or {}).get("filename"),
        "writes_performed": 0,
    }


# ==========================================================
# CODER-REPAIR-01 — TRUSTED REPAIR OF THE PENDING PROPOSAL
#
# The repair BASE is the server-owned pending proposal. The repair SCOPE is
# decided by the server from the candidate it actually received, never by the
# model and never by the browser. Every refusal preserves the base.
# ==========================================================

REPAIR_CONTRACT = "CodeFileRepairV1"
REPAIR_VERSION = "1.0"

#: Reasons a repair is refused. Each one leaves ``_STAGED`` untouched.
REPAIR_NO_PENDING = "no_pending_proposal"
REPAIR_NOT_PENDING = "proposal_not_pending"
REPAIR_BINDING_MISMATCH = "repair_binding_mismatch"
REPAIR_BASE_CHANGED = "repair_base_changed"
REPAIR_INTEGRITY = "staged_content_integrity_failed"
REPAIR_CONSUMED = "approval_capability_consumed"
REPAIR_EMPTY = "empty_candidate"
REPAIR_SYNTAX = "candidate_syntax_invalid"
REPAIR_NO_OP = "no_op_candidate"
REPAIR_IMPORTS = "imports_changed"
REPAIR_OUTSIDE = "source_outside_scope_changed"
REPAIR_MULTI = "multiple_scopes_changed"
REPAIR_SCOPE = "repair_scope_mismatch"
REPAIR_SIGNATURE = "candidate_signature_changed"
REPAIR_STATIC = "candidate_static_review_failed"
REPAIR_STATIC_UNAVAILABLE = "candidate_static_review_unavailable"
REPAIR_REVISION_REQUIRED = "repair_revision_required"

#: The only verdicts the quality-review contract may return. Anything else is
#: an unmet precondition, not an absence of findings.
STATIC_VERDICTS = ("PASS", "WARN", "FAIL")

#: ``failure_source`` values. A repair request must say whether the failure is
#: something the user reported or something an isolated run proved.
FAILURE_USER_REPORTED = "user_reported"
FAILURE_DOCKER_VERIFIED = "docker_verified"


def _raw_lines(text):
    """Split on the ONLY sequences Python treats as line endings.

    ``str.splitlines`` also splits on ``\\v``, ``\\f``, ``\\x85``, ``\\u2028``
    and ``\\u2029``, which can legally appear INSIDE a string literal. Splitting
    there would desynchronise our line indices from ``ast`` line numbers and
    silently mis-scope a span. This splits on ``\\r\\n``, ``\\r`` and ``\\n``
    only, and keeps the terminators so nothing is lost.
    """

    lines = []
    index = 0
    start = 0
    length = len(text)

    while index < length:

        char = text[index]

        if char == "\r":

            if index + 1 < length and text[index + 1] == "\n":
                lines.append(text[start:index + 2])
                index += 2
            else:
                lines.append(text[start:index + 1])
                index += 1

            start = index

        elif char == "\n":

            lines.append(text[start:index + 1])
            index += 1
            start = index

        else:

            index += 1

    if start < length:

        lines.append(text[start:])

    return lines


def _qualified_functions(tree):
    """Every module-level function and class method, in source order.

    Nested functions are deliberately NOT separate scopes: they live inside the
    span of the function that contains them, so changing one is still a change
    to exactly one scope.
    """

    spans = []

    def _walk(body, prefix):

        for node in body:

            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):

                spans.append((prefix + node.name, node))

            elif isinstance(node, ast.ClassDef):

                _walk(node.body, prefix + node.name + ".")

    _walk(tree.body, "")

    return spans


def _span_text(source, node):
    """The EXACT bytes of one function span, terminators included.

    No normalisation: a repair may rewrite this text, so it is the only place
    where a byte difference is authorised.
    """

    lines = _raw_lines(str(source))

    start = max(0, int(node.lineno) - 1)

    end = int(node.end_lineno)

    return "".join(lines[start:end])


def _skeleton(source, spans):
    """The source with every function span replaced by its qualified name.

    Two sources share a skeleton when the ONLY thing that differs between them
    is the text inside those spans. Everything outside a span is compared
    BYTE-FOR-BYTE, terminators included: a trailing space on an unrelated
    import, a CRLF-to-LF conversion, a reformatted blank line or a moved
    statement all break the skeleton, while an edited function body does not.

    An earlier version normalised trailing whitespace and line endings before
    comparing. That silently authorised exactly the edits the scope check
    exists to refuse — measured: a candidate that fixed the target method AND
    stripped a trailing space from an unrelated ``import`` line was accepted,
    and so was a whole-file CRLF conversion.
    """

    lines = _raw_lines(str(source))

    out = []

    cursor = 0

    for name, node in spans:

        start = max(0, int(node.lineno) - 1)

        end = int(node.end_lineno)

        if start < cursor:

            continue

        out.extend(lines[cursor:start])
        out.append("\x00%s\x00" % name)
        cursor = end

    out.extend(lines[cursor:])

    return "".join(out)


def _declaration_end_line(node):
    """The 1-based line on which a function's ``def`` header ends.

    Derived from the SIGNATURE's own AST positions — parameters, their
    defaults, ``*args``/``**kwargs`` and the return annotation — and never
    from ``body[0].lineno``.

    Using the first body STATEMENT as the header end was a real defect: a body
    that opens with comments has its first statement several lines below the
    ``def``, so those comments were folded into the "declaration". Measured on
    the live draft of 2026-10-26 (``Calculator.on_operator``, ``def`` on line
    16, comment on 17, first statement on 18): editing ONLY that comment
    produced ``candidate_signature_changed`` for an otherwise untouched
    function.
    """

    end = int(node.lineno)

    parts = []

    arguments = node.args

    parts.extend(arguments.posonlyargs)
    parts.extend(arguments.args)
    parts.extend(arguments.kwonlyargs)

    if arguments.vararg is not None:
        parts.append(arguments.vararg)

    if arguments.kwarg is not None:
        parts.append(arguments.kwarg)

    parts.extend(item for item in arguments.defaults if item is not None)
    parts.extend(item for item in arguments.kw_defaults if item is not None)

    if node.returns is not None:
        parts.append(node.returns)

    for part in parts:

        position = getattr(part, "end_lineno", None)

        if not isinstance(position, int):
            position = getattr(part, "lineno", None)

        if isinstance(position, int) and position > end:

            end = position

    return end


def _signature(source, node):
    """Everything a BODY-ONLY repair may not touch.

    Name, positional/keyword arguments, annotations, defaults, ``*args`` /
    ``**kwargs``, the return annotation and the decorators are compared
    structurally, so ``def target(self):`` -> ``def target(self, x=None):`` is
    a signature change even though it sits inside the authorised span.

    A multi-line declaration is additionally compared as exact text, which
    catches pure reformatting of the ``def`` line. That text ends at the last
    line of the HEADER (``_declaration_end_line``), so ordinary comments at
    the start of the body are body text, not declaration text.

    A one-line function (``def f(self): return 1``) shares its declaration line
    with its body, so the textual part is skipped there and the structural
    comparison alone decides — otherwise every legitimate one-line repair would
    be refused.
    """

    lines = _raw_lines(str(source))

    decorators = tuple(
        "".join(lines[item.lineno - 1:item.end_lineno])
        for item in node.decorator_list
    )

    declaration = ""

    first_body = node.body[0].lineno if node.body else node.lineno

    if first_body > node.lineno:

        header_end = min(_declaration_end_line(node), first_body - 1)

        # A closing ``)`` / ``:`` that sits on its own line belongs to the
        # header, not to the body.
        while header_end < first_body - 1 and header_end < len(lines):

            stripped = lines[header_end].strip()

            if stripped.startswith(")") or stripped.startswith(":"):

                header_end += 1
                continue

            break

        declaration = "".join(lines[node.lineno - 1:header_end])

    return (
        type(node).__name__,
        node.name,
        ast.dump(node.args),
        ast.dump(node.returns) if node.returns is not None else None,
        getattr(node, "type_comment", None),
        decorators,
        declaration,
    )


def _top_level_imports(tree):
    """A comparable signature of the module's top-level imports."""

    signature = []

    for node in tree.body:

        if isinstance(node, (ast.Import, ast.ImportFrom)):

            signature.append(ast.dump(node))

    return signature


def resolve_named_targets(source, text):
    """Qualified names defined in ``source`` that the turn names explicitly.

    Only names that already EXIST in the base can be resolved, so a request can
    never introduce a scope the base does not have.
    """

    try:

        spans = _qualified_functions(ast.parse(source))

    except Exception:

        return []

    lowered = str(text or "")

    hits = []

    for name, _node in spans:

        short = name.rsplit(".", 1)[-1]

        pattern = r"(?<![A-Za-z0-9_])%s(?![A-Za-z0-9_])" % re.escape(short)

        if re.search(pattern, lowered):

            hits.append(name)

    return hits


def infer_changed_scope(base_source, candidate_source):
    """``(scope, reason)`` — the ONE function body a candidate changed.

    ``scope`` is the qualified name when exactly one function BODY changed,
    its declaration survived intact, and every byte outside its span is
    identical. Every other outcome returns ``(None, reason)``, so an ambiguous
    candidate can never be installed.
    """

    try:

        base_tree = ast.parse(base_source)

    except Exception:

        return None, "base_source_unparseable"

    try:

        candidate_tree = ast.parse(candidate_source)

    except Exception:

        return None, REPAIR_SYNTAX

    base_spans = _qualified_functions(base_tree)
    candidate_spans = _qualified_functions(candidate_tree)

    if [name for name, _ in base_spans] != [name for name, _ in candidate_spans]:

        # A function/method was added, removed or renamed: the class structure
        # or the module structure changed, which is outside any single scope.
        return None, REPAIR_OUTSIDE

    if _top_level_imports(base_tree) != _top_level_imports(candidate_tree):

        return None, REPAIR_IMPORTS

    if _skeleton(base_source, base_spans) != _skeleton(
        candidate_source, candidate_spans
    ):

        return None, REPAIR_OUTSIDE

    changed = [
        (name, base_node, candidate_node)
        for (name, base_node), (_candidate_name, candidate_node) in zip(
            base_spans, candidate_spans
        )
        if _span_text(base_source, base_node)
        != _span_text(candidate_source, candidate_node)
    ]

    if not changed:

        return None, REPAIR_NO_OP

    if len(changed) > 1:

        return None, REPAIR_MULTI

    name, base_node, candidate_node = changed[0]

    # A body-only repair may not touch the declaration. Signature, annotations,
    # defaults, ``*args``/``**kwargs``, the return annotation, the decorators
    # and (for a multi-line declaration) the exact ``def`` text must survive.
    if _signature(base_source, base_node) != _signature(
        candidate_source, candidate_node
    ):

        return None, REPAIR_SIGNATURE

    return name, None


# ----------------------------------------------------------
# BOUNDED REPAIR REPRESENTATION — splice ONE body into the base
# ----------------------------------------------------------

SPLICE_NO_TARGET = "splice_target_not_found"
SPLICE_MODEL_TARGET_MISSING = "splice_model_target_missing"
SPLICE_ONE_LINE = "splice_one_line_function_unsupported"
SPLICE_INDENT = "splice_body_indentation_mismatch"


def _find_target(spans, target):
    """The span whose qualified name is ``target``, else a unique short match."""

    for name, node in spans:

        if name == target:

            return name, node

    short = str(target).rsplit(".", 1)[-1]

    matches = [(name, node) for name, node in spans if name == short]

    if len(matches) == 1:

        return matches[0]

    return None, None


def _leading_whitespace(line):
    return line[: len(line) - len(line.lstrip())]


def splice_target_body(base_source, target, model_source):
    """Rebuild a candidate from the BASE, taking ONLY ``target``'s body from the model.

    A whole-file model response must reproduce every byte of the file to
    survive the scope check. A draft that embeds a copy of itself — the live
    2026-10-26 draft carried a 20-line ``source_code`` string literal plus a
    module-level ``print(hashlib.sha256(...))`` — makes that practically
    impossible: any drift in that literal is outside every function span, so
    the honest verdict is ``source_outside_scope_changed`` and the user's
    repair never lands.

    This keeps the authoritative base bytes OUTSIDE the span and substitutes
    only the target method's body. It never invents bytes, never applies the
    model's unrelated edits, and REPORTS how much of the model's output it left
    out, so the caller can tell the user instead of discarding silently.

    Returns a dict; ``candidate`` is None unless ``ok`` is True.
    """

    report = {
        "ok": False,
        "reason": None,
        "scope": target,
        "candidate": None,
        "model_changed_outside_scope": False,
        "model_outside_diff_lines": 0,
        "body_lines_replaced": 0,
    }

    try:

        base_tree = ast.parse(base_source)

    except Exception:

        report["reason"] = "base_source_unparseable"
        return report

    base_spans = _qualified_functions(base_tree)

    base_name, base_node = _find_target(base_spans, target)

    if base_node is None:

        report["reason"] = SPLICE_NO_TARGET
        return report

    try:

        model_tree = ast.parse(model_source)

    except Exception:

        report["reason"] = REPAIR_SYNTAX
        return report

    model_spans = _qualified_functions(model_tree)

    _model_name, model_node = _find_target(model_spans, target)

    if model_node is None:

        report["reason"] = SPLICE_MODEL_TARGET_MISSING
        return report

    # The declaration is not taken from the model at all — but if the model
    # changed it, the repair is a signature change and must be refused rather
    # than silently spliced under the base's declaration.
    if _signature(base_source, base_node) != _signature(model_source, model_node):

        report["reason"] = REPAIR_SIGNATURE
        return report

    # A one-line function shares its declaration line with its body, so there
    # is no body span to substitute.
    if base_node.body and base_node.body[0].lineno == base_node.lineno:

        report["reason"] = SPLICE_ONE_LINE
        return report

    if model_node.body and model_node.body[0].lineno == model_node.lineno:

        report["reason"] = SPLICE_ONE_LINE
        return report

    base_lines = _raw_lines(str(base_source))
    model_lines = _raw_lines(str(model_source))

    base_start = _declaration_end_line(base_node)
    model_start = _declaration_end_line(model_node)

    base_body = base_lines[base_start:base_node.end_lineno]
    model_body = model_lines[model_start:model_node.end_lineno]

    if not model_body:

        report["reason"] = REPAIR_EMPTY
        return report

    # The body must already sit at the base's indentation; re-indenting would
    # be inventing structure the model did not produce.
    base_indent = _leading_whitespace(base_body[0]) if base_body else ""
    model_indent = _leading_whitespace(model_body[0])

    if base_indent != model_indent:

        report["reason"] = SPLICE_INDENT
        return report

    candidate = "".join(
        base_lines[:base_start] + model_body + base_lines[base_node.end_lineno:]
    )

    scope, reason = infer_changed_scope(base_source, candidate)

    if scope is None:

        report["reason"] = reason
        return report

    if scope != base_name:

        report["reason"] = REPAIR_SCOPE
        return report

    # What the model asked for OUTSIDE the authorised span, and what was
    # therefore not applied. This is reported to the user, never hidden.
    base_skeleton = _skeleton(base_source, base_spans)
    model_skeleton = _skeleton(model_source, model_spans)

    if base_skeleton != model_skeleton:

        import difflib

        diff_lines = [
            line
            for line in difflib.unified_diff(
                base_skeleton.splitlines(),
                model_skeleton.splitlines(),
                lineterm="",
                n=0,
            )
            if line[:1] in "+-" and not line.startswith(("+++", "---"))
        ]

        report["model_changed_outside_scope"] = True
        report["model_outside_diff_lines"] = len(diff_lines)

    report.update(
        {
            "ok": True,
            "reason": None,
            "scope": scope,
            "candidate": candidate,
            "body_lines_replaced": len(base_body),
        }
    )

    return report


def _failure_source(proposal):
    """``user_reported`` vs ``docker_verified`` — read back, never inferred.

    A verification record is written by the verification service, not by this
    module. Until one exists FOR THE CURRENT BASE DIGEST, the only honest
    classification is ``user_reported``.
    """

    record = proposal.get("verification")

    if not isinstance(record, dict):

        return FAILURE_USER_REPORTED

    if record.get("source_sha256") != proposal.get("digest"):

        return FAILURE_USER_REPORTED

    if record.get("functional") == "FAIL" or record.get("ok") is False:

        return FAILURE_DOCKER_VERIFIED

    return FAILURE_USER_REPORTED


def _diff_between(base, candidate):
    """Base-to-candidate unified diff for an UNSAVED proposal."""

    import difflib

    return "".join(
        difflib.unified_diff(
            str(base).splitlines(keepends=True),
            str(candidate).splitlines(keepends=True),
            fromfile="base",
            tofile="candidate",
        )
    )


def _quality_block(content, syntax_valid, syntax_error, requirements):
    """The existing three-verdict review, or None when it is unavailable."""

    try:

        from core.chat.code_quality_review_v1 import build_quality_block

        return build_quality_block(
            content, syntax_valid, syntax_error, requirements
        )

    except Exception:

        return None


def _static_review_refusal(quality):
    """``None`` only when the mandatory review ran and did not FAIL.

    A repair may only be installed with a COMPLETE review. An unavailable,
    truncated or unrecognised result is NOT "no findings" — it is an unmet
    precondition, so it must fail closed exactly like a FAIL verdict.

    This is deliberately stricter than ``stage_code_file``, which tolerates
    ``quality=None``: ordinary staging degrades to "review not performed" and
    says so, whereas a repair claims to have confined a change and therefore
    has to prove it.
    """

    if not isinstance(quality, dict):

        return REPAIR_STATIC_UNAVAILABLE

    if quality.get("syntax") != "PASS":

        return REPAIR_STATIC_UNAVAILABLE

    verdict = quality.get("static_review")

    if verdict not in STATIC_VERDICTS:

        return REPAIR_STATIC_UNAVAILABLE

    if not isinstance(quality.get("findings"), list):

        return REPAIR_STATIC_UNAVAILABLE

    if verdict == "FAIL":

        return REPAIR_STATIC

    return None


def repair_base(project_id, authorization=None):
    """The authoritative repair base for the CURRENT pending proposal.

    The bytes and the digest both come from the server-owned store. History is
    never consulted and a caller-supplied base is never accepted.
    """

    outcome = {
        "contract": REPAIR_CONTRACT,
        "version": REPAIR_VERSION,
        "project_id": str(project_id) if project_id else None,
        "ok": False,
        "reason": None,
        "filename": None,
        "content": None,
        "digest": None,
        "revision": None,
        "origin": None,
        "requirements": [],
        "failure_source": FAILURE_USER_REPORTED,
        "writes_performed": 0,
    }

    proposal = _STAGED.get(project_id)

    if not isinstance(proposal, dict):

        outcome["reason"] = REPAIR_NO_PENDING
        return outcome

    outcome["filename"] = proposal.get("filename")
    outcome["revision"] = proposal.get("revision")
    outcome["origin"] = proposal.get("origin")

    binding = proposal.get("authorization_binding")

    if not binding:

        outcome["reason"] = "trusted_authorization_required"
        return outcome

    supplied = _trusted_binding(authorization, project_id)

    # An untrusted caller is a different failure from a trusted caller bound to
    # a different proposal: the first is a missing capability, the second is a
    # cross-identity attempt.
    if supplied is None:

        outcome["reason"] = "trusted_authorization_required"
        return outcome

    if supplied != binding:

        outcome["reason"] = REPAIR_BINDING_MISMATCH
        return outcome

    if proposal.get("status") != STATUS_AWAITING_APPROVAL:

        outcome["reason"] = REPAIR_NOT_PENDING
        return outcome

    if (proposal.get("capability") or {}).get("consumed"):

        outcome["reason"] = REPAIR_CONSUMED
        return outcome

    content = proposal.get("content")

    if not isinstance(content, str) or not content.strip():

        outcome["reason"] = "staged_source_unavailable"
        return outcome

    if _digest(content) != proposal.get("digest"):

        outcome["reason"] = REPAIR_INTEGRITY
        return outcome

    quality = proposal.get("quality") or {}

    outcome.update(
        {
            "ok": True,
            "content": content,
            "digest": proposal.get("digest"),
            "requirements": list(quality.get("unverified_requirements") or []),
            "failure_source": _failure_source(proposal),
        }
    )

    return outcome


def replace_staged_file(
    project_id,
    candidate,
    expected_base_digest,
    authorization=None,
    documents_root=None,
    origin=REPAIR_ORIGIN,
    repair=None,
    requirements=None,
    expected_revision=None,
    now=None,
    approval_ttl_seconds=300,
):
    """Atomically replace the pending proposal with a VALIDATED candidate.

    ``expected_base_digest`` AND ``expected_revision`` are both mandatory: the
    digest binds the bytes, the revision binds the identity of the proposal
    that carries them. Every check runs under the staging lock and BEFORE the
    store is touched, so a rejected candidate leaves the original proposal
    exactly as it was.

    A successful replacement issues a NEW capability bound to the NEW digest:
    the previous save approval cannot write these bytes. No execution,
    packaging or consent authority is granted here.
    """

    outcome = {
        "contract": REPAIR_CONTRACT,
        "version": REPAIR_VERSION,
        "project_id": str(project_id) if project_id else None,
        "status": "rejected",
        "reason": None,
        "filename": None,
        "digest": None,
        "base_digest": None,
        "base_revision": None,
        "scope": None,
        "base_diff": None,
        "syntax_error": None,
        "writes_performed": 0,
        "proposal": None,
    }

    binding = _trusted_binding(authorization, project_id)

    if binding is None:

        outcome["reason"] = "trusted_authorization_required"
        return outcome

    repair = repair if isinstance(repair, dict) else {}

    with _STAGING_LOCK:

        live = _STAGED.get(project_id)

        if not isinstance(live, dict):

            outcome["reason"] = REPAIR_NO_PENDING
            return outcome

        outcome["filename"] = live.get("filename")
        outcome["base_digest"] = live.get("digest")
        outcome["base_revision"] = live.get("revision")

        if live.get("authorization_binding") != binding:

            outcome["reason"] = REPAIR_BINDING_MISMATCH
            return outcome

        if live.get("status") != STATUS_AWAITING_APPROVAL:

            outcome["reason"] = REPAIR_NOT_PENDING
            return outcome

        if (live.get("capability") or {}).get("consumed"):

            outcome["reason"] = REPAIR_CONSUMED
            return outcome

        base = live.get("content")

        if (
            not isinstance(base, str)
            or not base.strip()
            or _digest(base) != live.get("digest")
        ):

            outcome["reason"] = REPAIR_INTEGRITY
            return outcome

        # The caller must have built the candidate from THIS base. A stale
        # digest means the pending proposal changed while the model was
        # generating: the candidate repairs bytes that no longer exist.
        if (
            not isinstance(expected_base_digest, str)
            or expected_base_digest != live.get("digest")
        ):

            outcome["reason"] = REPAIR_BASE_CHANGED
            return outcome

        # The revision is MANDATORY, not optional. A digest alone cannot tell
        # "the proposal I read" from "a different proposal carrying the same
        # bytes", and an omitted revision used to skip this check entirely —
        # a fail-open on the very compare-and-swap the repair depends on.
        if not isinstance(expected_revision, int) or isinstance(
            expected_revision, bool
        ):

            outcome["reason"] = REPAIR_REVISION_REQUIRED
            return outcome

        if live.get("revision") != expected_revision:

            outcome["reason"] = REPAIR_BASE_CHANGED
            return outcome

        if not isinstance(candidate, str) or not candidate.strip():

            outcome["reason"] = REPAIR_EMPTY
            return outcome

        if _digest(candidate) == live.get("digest"):

            outcome["reason"] = REPAIR_NO_OP
            return outcome

        syntax_valid, syntax_error = _syntax(candidate)

        if not syntax_valid:

            outcome["reason"] = REPAIR_SYNTAX
            outcome["syntax_error"] = syntax_error
            return outcome

        scope, scope_reason = infer_changed_scope(base, candidate)

        if scope is None:

            outcome["reason"] = scope_reason
            return outcome

        outcome["scope"] = scope

        # The SERVER owns the scope. A caller-declared target may only NARROW
        # it: when the turn named a function, the inferred scope must be that
        # function, so the model cannot redirect the edit elsewhere.
        requested_target = repair.get("target")

        if requested_target and requested_target != scope:

            outcome["reason"] = REPAIR_SCOPE
            return outcome

        quality = _quality_block(candidate, syntax_valid, syntax_error, requirements)

        review_refusal = _static_review_refusal(quality)

        if review_refusal:

            outcome["reason"] = review_refusal
            return outcome

        base_diff = _diff_between(base, candidate)

        replaced = stage_code_file(
            project_id=project_id,
            filename=live.get("filename"),
            content=candidate,
            documents_root=documents_root,
            origin=origin,
            authorization=authorization,
            now=now,
            approval_ttl_seconds=approval_ttl_seconds,
            requirements=requirements,
        )

        if replaced.get("status") != STATUS_AWAITING_APPROVAL:

            outcome["reason"] = replaced.get("reason") or "staging_failed"
            return outcome

        stored = _STAGED.get(project_id)

        # The store must hold exactly the bytes that were validated. A mismatch
        # here would mean the digest the user is shown is not the digest that
        # would be written, so the proposal is dropped rather than kept.
        if not isinstance(stored, dict) or stored.get("digest") != _digest(candidate):

            _STAGED.pop(project_id, None)
            outcome["reason"] = "staged_candidate_digest_mismatch"
            return outcome

        stored["scope"] = scope
        stored["base_diff"] = base_diff
        stored["repair"] = {
            "contract": REPAIR_CONTRACT,
            "version": REPAIR_VERSION,
            "base_digest": outcome["base_digest"],
            "base_revision": outcome["base_revision"],
            "target": scope,
            "requested_target": requested_target,
            "failure_source": repair.get("failure_source")
            or FAILURE_USER_REPORTED,
            "user_request": repair.get("user_request"),
            "base_to_candidate_diff": base_diff,
            "candidate_digest": stored.get("digest"),
            # How the candidate was produced. ``spliced_body`` means only the
            # named method's body came from the model and every other byte came
            # from the base; ``model_changed_outside_scope`` records that the
            # model asked for changes that were therefore NOT applied.
            "representation": repair.get("representation") or "whole_file",
            "model_changed_outside_scope": bool(
                repair.get("model_changed_outside_scope")
            ),
            "model_outside_diff_lines": int(
                repair.get("model_outside_diff_lines") or 0
            ),
            "writes_performed": 0,
            "execution_authorized": False,
            "packaging_authorized": False,
        }
        _STAGED[project_id] = stored

        outcome.update(
            {
                "status": STATUS_REPLACED,
                "reason": None,
                "digest": stored.get("digest"),
                "base_diff": base_diff,
                "proposal": deepcopy(stored),
            }
        )

    return outcome
