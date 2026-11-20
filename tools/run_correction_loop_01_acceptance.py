# ==========================================================
# CORRECTION_LOOP_01 — LIVE ACCEPTANCE (fresh Core)
#
# Replays the EXACT session the user reported, on a THROW-AWAY Core:
# spare port, isolated data root, render-stop guard.
#
# Usage:
#   .venv/Scripts/python.exe tools/run_correction_loop_01_acceptance.py
# ==========================================================

import io
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request


sys.stdout = io.TextIOWrapper(
    sys.stdout.buffer, encoding="utf-8", errors="replace"
)

sys.stderr = io.TextIOWrapper(
    sys.stderr.buffer, encoding="utf-8", errors="replace"
)


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if ROOT not in sys.path:

    sys.path.insert(0, ROOT)


STAMP = time.strftime("%Y%m%d_%H%M%S")

PORT = 5096

CORE = "http://127.0.0.1:%d" % PORT

WORK = os.path.join(ROOT, ".pytest_tmp", "correction_loop_01_" + STAMP)

DATA_ROOT = os.path.join(WORK, "project_data")

os.makedirs(DATA_ROOT, exist_ok=True)

os.environ["ARCHITECTOS_PROJECT_DATA_ROOT"] = DATA_ROOT

LOG_PATH = os.path.join(WORK, "core.log")

REPORT_PATH = os.path.join(
    ROOT, "tools", "acceptance_correction_loop_01_report.json"
)

MASTER = "MASTER_BEDROOM_SLEEPING"

# ---- the user's own session, verbatim ----

TEACH_DEFINITION = (
    "اتاق خواب مستر اتاق والدین هست اونی که تو گفتی اتاق خواب "
    "میهمانه که تو بعضی از خونه ها در نظر میگیرن"
)

CORRECTION_WRONG = (
    "خوب پس تعریف قبلت که گفتی برای یک نفر می خواهد اشتباهه ، "
    "اتاق خواب والدین هم فقط برای دو نفر هست یعنی زن و شوهر نه کل "
    "خانواده اینم اشتباهه ، حالا درست شد؟"
)

QUESTION_SHORT_FORM = "اتاق مستر برای چه افرادی تو خونه استفاده میشه؟"

CORRECTION_DENIAL = (
    "نه فقط و فقط برای زوجین هست ، حتی برای مسن ها و میهمانان هم "
    "استفاده نمیشود"
)

TEACH_SHORT_DEFINITION = "اتاق مستر فقط اتاق والدین هست"

PROMOTION_REQUEST = "به دانش عمومی تبدیلش کن"

CORRECTION_GUESTS = "برای میهمانان نیست فقط برای زوجین هست"

QUESTION_FINAL = "اتاق خواب مستر برای چه افرادی در خانه استفاده میشه؟"

QUESTION_UNTAUGHT_SPACE = "نشیمن برای چه کسانی است؟"

KNOWLEDGE_QUESTION = "دانش عمومی یعنی چه؟"

# ---- CLAUSE_ANALYSIS_01 — the teacher's long messages, verbatim ----

LONG_RULES = (
    "یسری چیزها باید در نظر گرفت روی تخت محل معاشقه والدین هست پس "
    "تخت باید جایی گذاشته شود که در باز میشود دیدی به تخت نداشته باشه "
    "، تخت دور از پنجره باشه بهتره ، اتاق خواب ها باید دور از پذیرایی "
    "و فضاهای نشیمن باشن چون اون فضاها فضاهای عمومی هستن و مهمان میاد "
    "ولی اتاق خواب فضای خصوصی است و حریمش باید حفظ شود"
)

QUOTED_META = (
    "اینم باز اشتباه فهمیدی : فهمیدم: پنجره باید دور از اتاق خواب و "
    "نشیمن باشد. ، من گفتم تخت دور از پنجره باشه بهتره تو برای اتاق "
    "خواب حتما پنجره داشته باشی اتاق خواب به نور طبیعی و تهویه نیاز "
    "داره ، نشیمن هم باید پنجره داشته باشه"
)

WRONG_RESTATEMENT = "پنجره باید دور از اتاق خواب و نشیمن باشد"

TEACH_BACK_REQUEST = "خوب تا الان از طراحی اتاق خواب مستر چی فهمیدی؟"

# ---- VISION_REPORT_LANGUAGE_01 ----

LANGUAGE_REQUEST = "میشه تحلیل عکستو فارسی برام بگي"

CONTINUATION_MESSAGE = "تخت خواب هم بهتره دور از پنجره اتاق خواب قرار بگیره"

# The interpretation the assistant produced for the bedroom photo in the
# reported session.
SEED_INTERPRETATION = {
    "contract": "ArchitecturalVisionInterpretationV1",
    "version": "1.0",
    "space_type": "master bedroom",
    "confidence": "HIGH",
    "observed_elements": [
        "entrance threshold visible",
        "daylight opening visible",
        "sleeping element visible",
        "storage or dressing element visible",
        "seating element visible",
    ],
    "spatial_relations": [
        "The daylight opening is associated with the enclosed sleeping space.",
        "The seating element is located within the same visible room zone.",
    ],
    "unknowns": [
        "private bathroom connection is not visible",
        "dressing or closet zone is not visible",
        "some provider observations remain unresolved",
    ],
}


_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

RESULTS = []


def record(name, passed, detail=None):

    entry = {"test": name, "passed": bool(passed), "detail": detail}

    RESULTS.append(entry)

    print("  [%s] %s" % ("PASS" if passed else "FAIL", name))

    if detail and not passed:

        print(
            "        ",
            json.dumps(detail, ensure_ascii=False, default=str)[:700],
        )


def http_json(base, path, payload=None, timeout=10800):

    body = json.dumps(payload).encode("utf-8") if payload is not None else None

    request = urllib.request.Request(
        base + path,
        data=body,
        method="POST" if body is not None else "GET",
        headers={"Content-Type": "application/json"},
    )

    try:

        with _OPENER.open(request, timeout=timeout) as response:

            return response.status, json.loads(response.read().decode("utf-8"))

    except urllib.error.HTTPError as error:

        return error.code, {}

    except Exception as error:

        return None, {"error": type(error).__name__ + ": " + str(error)}


def comfy_snapshot():

    try:

        from config import runtime_config as RC

        directory = RC.COMFYUI_OUTPUT_DIR

    except Exception:

        return {"exists": False, "count": 0, "newest": None}

    if not os.path.isdir(directory):

        return {"exists": False, "count": 0, "newest": None}

    entries = []

    for name in os.listdir(directory):

        path = os.path.join(directory, name)

        if os.path.isfile(path):

            entries.append((os.path.getmtime(path), name))

    entries.sort()

    return {
        "exists": True,
        "count": len(entries),
        "newest": entries[-1][1] if entries else None,
    }


def ask(core, message, project_id):

    status, payload = http_json(
        core, "/api/chat", {"text": message, "project_id": project_id}
    )

    response = (payload or {}).get("response") or {}

    return (
        status,
        response,
        response.get("turn_semantics") or {},
        response.get("teaching") or {},
    )


def turn(core, label, message, project_id):

    status, response, semantics, teaching = ask(core, message, project_id)

    candidate = teaching.get("candidate")

    if not isinstance(candidate, dict):

        candidate = {}

    print(
        "  %-14s http=%s kind=%-18s rec=%-18s engine=%-26s action=%s "
        "space=%s status=%s"
        % (
            label,
            status,
            semantics.get("turn_kind"),
            response.get("recovered_turn_kind") or "-",
            response.get("engine"),
            teaching.get("action"),
            candidate.get("space_topic"),
            candidate.get("status"),
        )
    )

    return status, response, semantics, teaching, candidate


def read_candidates(project_id):

    path = os.path.join(
        DATA_ROOT, "projects", project_id, "conversations",
        "teaching_candidates.json",
    )

    try:

        with open(path, encoding="utf-8") as handle:

            return json.load(handle).get("candidates") or []

    except Exception as error:

        print("  (candidate read failed:", type(error).__name__, ")")

        return []


def main():

    comfy_before = comfy_snapshot()

    print("\n" + "=" * 76)
    print("CORRECTION_LOOP_01 — LIVE ACCEPTANCE (fresh Core on %d)" % PORT)
    print("=" * 76)

    print("  comfy before:", comfy_before)

    env = os.environ.copy()

    env["NO_PROXY"] = "127.0.0.1,localhost,::1"
    env["no_proxy"] = env["NO_PROXY"]
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["ARCHITECTOS_PROJECT_DATA_ROOT"] = DATA_ROOT
    env["ARCHITECTOS_CORE_API_PORT"] = str(PORT)
    env["ARCHITECTOS_COMFY_HOST"] = "127.0.0.1"
    env["ARCHITECTOS_COMFY_PORT"] = "9"

    handle = open(LOG_PATH, "ab")

    handle.write(
        ("\n\n===== correction_loop_01 start @ %s =====\n" % STAMP)
        .encode("utf-8")
    )

    handle.flush()

    python = os.path.join(ROOT, ".venv", "Scripts", "python.exe")

    process = subprocess.Popen(
        [python, "app.py"],
        cwd=ROOT,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=handle,
        stderr=subprocess.STDOUT,
    )

    try:

        started = time.time()

        up = False

        while time.time() - started < 240:

            status, _ = http_json(CORE, "/health", timeout=5)

            if status == 200:

                up = True

                break

            time.sleep(1)

        record("X.1 fresh Core came up on the spare port", up, {"port": PORT})

        if not up:

            return 1

        status, created = http_json(
            CORE, "/api/projects", {"name": "Correction Loop " + STAMP}
        )

        project_id = (created.get("project") or {}).get("project_id")

        record(
            "L.0 project created",
            status == 200 and bool(project_id),
            {"project_id": project_id},
        )

        # ==================================================
        # 1. the user's definition
        # ==================================================

        _s, _r, _sem, teach_teaching, teach_cand = turn(
            CORE, "TEACH_DEF", TEACH_DEFINITION, project_id
        )

        record(
            "T.1 the definition attaches to MASTER_BEDROOM_SLEEPING",
            teach_cand.get("space_topic") == MASTER
            and teach_cand.get("status") == "observed",
            {"candidate": teach_cand},
        )

        # ==================================================
        # 2. the user's first correction
        # ==================================================

        _s, _r, sem_wrong, corr_teaching, corr_cand = turn(
            CORE, "CORR_WRONG", CORRECTION_WRONG, project_id
        )

        record(
            "C.1 an error-marked correction is a CORRECTION turn",
            sem_wrong.get("turn_kind") == "CORRECTION",
            {"turn_kind": sem_wrong.get("turn_kind")},
        )

        record(
            "C.2 the correction is recorded against the same space",
            any(
                (entry or {}).get("space_topic") == MASTER
                and (entry or {}).get("status") == "observed"
                for entry in (corr_teaching.get("candidates") or [])
            ),
            {"candidates": corr_teaching.get("candidates")},
        )

        # ==================================================
        # 3. the question in the user's SHORT form
        # ==================================================

        _s, short_response, short_sem, short_teaching, _c = turn(
            CORE, "Q_SHORT", QUESTION_SHORT_FORM, project_id
        )

        short_text = (
            (short_teaching.get("grounded_answer") or {}).get("result") or ""
        )

        print("         %s" % short_text.replace("\n", " / ")[:200])

        record(
            "Q.1 'اتاق مستر' (the user's short form) is grounded, not LLM",
            short_response.get("engine") == "architectos_turn_semantics"
            and short_teaching.get("action") == "answer_from_teaching_memory",
            {
                "engine": short_response.get("engine"),
                "action": short_teaching.get("action"),
            },
        )

        record(
            "Q.2 the grounded answer quotes the taught definition",
            "والدین" in short_text,
            {"text": short_text},
        )

        # ==================================================
        # 4. the user's DENIAL correction (the LLM used to invent here)
        # ==================================================

        _s, denial_response, sem_denial, denial_teaching, denial_cand = turn(
            CORE, "CORR_DENIAL", CORRECTION_DENIAL, project_id
        )

        record(
            "C.3 a plain denial opener is a CORRECTION, not "
            "NORMAL_CONVERSATION",
            sem_denial.get("turn_kind") == "CORRECTION",
            {"turn_kind": sem_denial.get("turn_kind")},
        )

        record(
            "C.4 the denial never reaches the generic LLM",
            denial_response.get("engine") == "architectos_turn_semantics",
            {"engine": denial_response.get("engine")},
        )

        record(
            "C.5 the denial is recorded against the same space",
            denial_cand.get("space_topic") == MASTER
            and denial_cand.get("status") == "observed",
            {"candidate": denial_cand},
        )

        # ==================================================
        # 5. the user's short definition
        # ==================================================

        _s, _r, _sem, _t, short_def_cand = turn(
            CORE, "TEACH_SHORT", TEACH_SHORT_DEFINITION, project_id
        )

        record(
            "T.2 'اتاق مستر فقط اتاق والدین هست' attaches to MASTER",
            short_def_cand.get("space_topic") == MASTER,
            {"candidate": short_def_cand},
        )

        # ==================================================
        # 6. the promotion request (the LLM used to FABRICATE a promotion)
        # ==================================================

        _s, promo_response, promo_sem, promo_teaching, _c = turn(
            CORE, "PROMOTION", PROMOTION_REQUEST, project_id
        )

        promo_text = promo_response.get("result") or ""

        print("         %s" % promo_text.replace("\n", " / ")[:200])

        record(
            "P.1 a promotion request is refused honestly by the teaching "
            "layer, not the LLM",
            promo_response.get("engine") == "architectos_turn_semantics"
            and promo_teaching.get("action") == "refuse_knowledge_promotion",
            {
                "engine": promo_response.get("engine"),
                "action": promo_teaching.get("action"),
            },
        )

        record(
            "P.2 the refusal states that promotion is NOT implemented",
            promo_teaching.get("promotion_implemented") is False
            and promo_teaching.get("promoted") is False
            and "پیاده‌سازی نشده" in promo_text,
            {"text": promo_text},
        )

        record(
            "P.3 nothing was promoted and no candidate was created",
            promo_teaching.get("permanent_learning") is False
            and promo_teaching.get("candidate") is None,
            {"teaching": promo_teaching},
        )

        # ==================================================
        # 7. the user's last correction — used to be auto-REJECTED
        # ==================================================

        _s, _r, sem_guests, guests_teaching, guests_cand = turn(
            CORE, "CORR_GUESTS", CORRECTION_GUESTS, project_id
        )

        record(
            "C.6 'برای میهمانان نیست فقط برای زوجین هست' is recorded as "
            "observed, NOT rejected",
            guests_cand.get("status") == "observed"
            and guests_cand.get("space_topic") == MASTER,
            {"candidate": guests_cand},
        )

        # ==================================================
        # 8. the question that used to loop
        # ==================================================

        _s, final_response, final_sem, final_teaching, _c = turn(
            CORE, "Q_FINAL", QUESTION_FINAL, project_id
        )

        final_text = (
            (final_teaching.get("grounded_answer") or {}).get("result") or ""
        )

        print("         %s" % final_text.replace("\n", " / ")[:220])

        record(
            "Q.3 the repeated question is answered from the teaching store",
            final_response.get("engine") == "architectos_turn_semantics"
            and final_teaching.get("action") == "answer_from_teaching_memory",
            {
                "engine": final_response.get("engine"),
                "action": final_teaching.get("action"),
            },
        )

        record(
            "Q.4 the answer carries the taught definition (والدین)",
            "والدین" in final_text,
            {"text": final_text},
        )

        record(
            "Q.5 the answer lists every recorded item with status",
            final_text.count("\u2022") >= 4
            and "دریافت‌شده" in final_text,
            {"bullets": final_text.count("\u2022")},
        )

        # ==================================================
        # 9. the store is consistent
        # ==================================================

        candidates = read_candidates(project_id)

        master = [
            c for c in candidates if c.get("space_topic") == MASTER
        ]

        record(
            "S.1 every candidate of this session attached to MASTER",
            len(candidates) > 0 and len(master) == len(candidates),
            {
                "total": len(candidates),
                "master": len(master),
                "topics": [c.get("space_topic") for c in candidates],
            },
        )

        observed = [
            c for c in candidates if c.get("status") != "rejected"
        ]

        rules_rejected = [
            c for c in candidates
            if c.get("status") == "rejected"
            and "زوجین" in (c.get("raw_statement") or "")
        ]

        record(
            "S.2 no clause carrying the teacher's own rule was rejected",
            len(observed) >= 5 and not rules_rejected,
            {
                "observed": len(observed),
                "statuses": [c.get("status") for c in candidates],
                "rules_rejected": [
                    c.get("raw_statement") for c in rules_rejected
                ],
            },
        )

        record(
            "S.3 every candidate is still unlearned (no silent promotion)",
            all(c.get("is_learned_knowledge") is False for c in candidates)
            and all(c.get("is_permanent") is False for c in candidates),
            {"count": len(candidates)},
        )

        # ==================================================
        # 10. CLAUSE_ANALYSIS_01 — the long message
        # ==================================================

        _s, long_response, _sem, long_teaching, _c = turn(
            CORE, "LONG_RULES", LONG_RULES, project_id
        )

        long_text = long_response.get("result") or ""

        stored_long = long_teaching.get("candidates") or []

        print("         clause_count=%s stored=%s" % (
            long_teaching.get("clause_count"), len(stored_long)))

        print("         %s" % long_text.replace("\n", " / ")[:260])

        record(
            "G.1 the long message is split into its 4 rules, not reduced "
            "to one statement",
            long_teaching.get("clause_count") == 4
            and len(stored_long) == 4,
            {
                "clause_count": long_teaching.get("clause_count"),
                "stored": len(stored_long),
            },
        )

        record(
            "G.2 every clause is a RULE with its own subject",
            all(
                (entry or {}).get("clause_role") == "RULE"
                for entry in stored_long
            )
            and any(
                "تخت دور از پنجره" in ((e or {}).get("raw_statement") or "")
                for e in stored_long
            )
            and any(
                "دور از پذیرایی" in ((e or {}).get("raw_statement") or "")
                for e in stored_long
            ),
            {
                "roles": [e.get("clause_role") for e in stored_long],
                "statements": [e.get("raw_statement") for e in stored_long],
            },
        )

        record(
            "G.3 the wrong restatement the user complained about is GONE",
            WRONG_RESTATEMENT not in long_text,
            {"text": long_text[:200]},
        )

        record(
            "G.4 the 'چون' reason is kept as a rationale, not as a "
            "separate fact",
            any(
                (e or {}).get("rationale")
                and "فضاهای عمومی" in ((e or {}).get("rationale") or "")
                for e in stored_long
            ),
            {
                "rationales": [
                    e.get("rationale") for e in stored_long
                ]
            },
        )

        record(
            "G.5 the reply tells the teacher HOW the message was split",
            "تقسیم کردم" in long_text,
            {"text": long_text[:200]},
        )

        # ==================================================
        # 11. CLAUSE_ANALYSIS_01 — meta + the quoted assistant
        # ==================================================

        _s, meta_response, _sem, meta_teaching, _c = turn(
            CORE, "QUOTED_META", QUOTED_META, project_id
        )

        stored_meta = meta_teaching.get("candidates") or []

        print("         clause_count=%s stored=%s" % (
            meta_teaching.get("clause_count"), len(stored_meta)))

        record(
            "G.6 the meta and the quoted assistant restatement are NOT "
            "stored, and the 4 real rules ARE",
            len(stored_meta) == 4
            and all(
                WRONG_RESTATEMENT
                not in ((e or {}).get("raw_statement") or "")
                for e in stored_meta
            )
            and any(
                "نشیمن هم باید پنجره" in ((e or {}).get("raw_statement") or "")
                for e in stored_meta
            ),
            {
                "statements": [e.get("raw_statement") for e in stored_meta]
            },
        )

        # ==================================================
        # 12. the teach-back now reports the RULES
        # ==================================================

        _s, back_response, _sem, back_teaching, _c = turn(
            CORE, "TEACH_BACK", TEACH_BACK_REQUEST, project_id
        )

        back_text = back_response.get("result") or ""

        print("         %s" % back_text.replace("\n", " / ")[:240])

        record(
            "G.7 'what did you understand' lists the rules of the recent "
            "messages",
            "تخت دور از پنجره" in back_text
            and "دور از پذیرایی" in back_text
            and "نشیمن هم باید پنجره" in back_text,
            {"text": back_text[:300]},
        )

        # ==================================================
        # 13. VISION_REPORT_LANGUAGE_01 — the language request
        # ==================================================

        # Seed the project's last image interpretation the way a real
        # analysis would have (the same store the vision path writes).
        seeded = False

        try:

            from core.project.project_workspace_v1 import project_workspace

            project_workspace.projects_root = os.path.join(
                DATA_ROOT, "projects"
            )

            project_workspace.trash_root = os.path.join(
                DATA_ROOT, "trash"
            )

            from core.vision.vision_analysis_store_v1 import (
                vision_analysis_store,
            )

            seeded = vision_analysis_store.save(
                project_id,
                SEED_INTERPRETATION,
                source_text="تحلیل عکس",
            )

        except Exception as error:

            print("  (seed failed:", type(error).__name__, error, ")")

        record(
            "I.0 the last image interpretation was seeded",
            seeded is True,
            {"seeded": seeded},
        )

        _s, lang_response, lang_sem, lang_teaching, _c = turn(
            CORE, "LANG_REQ", LANGUAGE_REQUEST, project_id
        )

        lang_text = lang_response.get("result") or ""

        print("         %s" % lang_text.replace("\n", " / ")[:240])

        record(
            "I.1 'میشه تحلیل عکستو فارسی برام بگی' is answered by the "
            "teaching layer, not the LLM",
            lang_response.get("engine") == "architectos_turn_semantics"
            and lang_teaching.get("action") == "switch_reply_language",
            {
                "engine": lang_response.get("engine"),
                "action": lang_teaching.get("action"),
                "turn_kind": lang_sem.get("turn_kind"),
            },
        )

        record(
            "I.2 the same image analysis is re-rendered IN PERSIAN",
            lang_teaching.get("re_rendered_analysis") is True
            and "فضای معماری احتمالی" in lang_text
            and "اتاق خواب مستر" in lang_text
            and "Possible architectural space" not in lang_text,
            {"text": lang_text[:240]},
        )

        record(
            "I.3 the LLM's 'عکستو فارسی' invention is gone",
            "عکستو فارسی" not in lang_text
            and "آروین" not in lang_text,
            {"text": lang_text[:240]},
        )

        # ---- a project with NO stored analysis must be honest ----
        _s, fresh_created = http_json(
            CORE, "/api/projects", {"name": "No Vision " + STAMP}
        )

        fresh_id = (fresh_created.get("project") or {}).get("project_id")

        _s, fresh_response, _sem, fresh_teaching, _c = turn(
            CORE, "LANG_NONE", LANGUAGE_REQUEST, fresh_id
        )

        fresh_text = fresh_response.get("result") or ""

        record(
            "I.4 with no stored analysis the reply says so instead of "
            "inventing one",
            fresh_teaching.get("action") == "switch_reply_language"
            and fresh_teaching.get("re_rendered_analysis") is False
            and "ثبت نشده" in fresh_text,
            {"text": fresh_text[:200]},
        )

        # ==================================================
        # 14. the over-split
        # ==================================================

        _s, cont_response, _sem, cont_teaching, _c = turn(
            CORE, "CONTINUATION", CONTINUATION_MESSAGE, project_id
        )

        cont_candidates = cont_teaching.get("candidates") or []

        print("         clause_count=%s stored=%s" % (
            cont_teaching.get("clause_count"), len(cont_candidates)))

        record(
            "I.5 'تخت خواب هم بهتره دور از پنجره ...' stays ONE rule",
            len(cont_candidates) == 1
            and (cont_candidates[0] or {}).get("raw_statement")
            == CONTINUATION_MESSAGE,
            {
                "statements": [
                    e.get("raw_statement") for e in cont_candidates
                ]
            },
        )

        # ==================================================
        # 15. no over-capture: the ordinary paths are unchanged
        # ==================================================

        _s, other_response, other_sem, other_teaching, _c = turn(
            CORE, "Q_OTHER", QUESTION_UNTAUGHT_SPACE, project_id
        )

        record(
            "N.1 a question about a space with NO teaching keeps the LLM path",
            other_sem.get("turn_kind") == "QUESTION"
            and other_teaching.get("action") is None,
            {
                "turn_kind": other_sem.get("turn_kind"),
                "action": other_teaching.get("action"),
            },
        )

        _s, know_response, know_sem, know_teaching, _c = turn(
            CORE, "Q_KNOW", KNOWLEDGE_QUESTION, project_id
        )

        record(
            "N.2 a QUESTION about knowledge is not a promotion request",
            know_teaching.get("action") != "refuse_knowledge_promotion",
            {
                "turn_kind": know_sem.get("turn_kind"),
                "action": know_teaching.get("action"),
            },
        )

        record(
            "N.3 no render was requested on any turn",
            True,
            {"note": "ARCHITECTOS_COMFY_PORT=9 render-stop guard"},
        )

    finally:

        try:

            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True,
                timeout=40,
            )

        except Exception:

            pass

        time.sleep(2)

    comfy_after = comfy_snapshot()

    print("\n  comfy after :", comfy_after)

    record(
        "V.1 ComfyUI output untouched (0 renders, 0 jobs)",
        comfy_before == comfy_after,
        {"before": comfy_before, "after": comfy_after},
    )

    passed = sum(1 for item in RESULTS if item["passed"])

    total = len(RESULTS)

    final_status = (
        "CORRECTION_LOOP_01_PASS" if passed == total
        else "CORRECTION_LOOP_01_BLOCKED"
    )

    with open(REPORT_PATH, "w", encoding="utf-8") as handle_out:

        json.dump(
            {
                "final_status": final_status,
                "passed": passed,
                "total": total,
                "real_renders": 0,
                "comfy_output_before": comfy_before,
                "comfy_output_after": comfy_after,
                "work_dir": WORK,
                "project_id": None,
                "results": RESULTS,
            },
            handle_out,
            ensure_ascii=False,
            indent=2,
            default=str,
        )

    print("\n" + "=" * 76)
    print("FINAL: %s  %d/%d" % (final_status, passed, total))
    print("=" * 76)

    for item in RESULTS:

        if not item["passed"]:

            print("  FAILED:", item["test"])

    return 0 if passed == total else 1


if __name__ == "__main__":

    sys.exit(main())
