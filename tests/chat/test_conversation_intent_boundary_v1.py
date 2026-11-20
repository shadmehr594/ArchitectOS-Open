# ==========================================================
# CONVERSATION_INTENT_BOUNDARY_V1 — unit tests
#
# Pure, deterministic classifier tests. No LLM, no network, no
# ChatArchitect construction.
# ==========================================================

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:

    sys.path.insert(0, str(ROOT))


from core.chat.conversation_intent_boundary_v1 import (  # noqa: E402
    classify_conversation_intent,
    GENERAL_CONVERSATION,
    ARCHITECTURE_CONVERSATION,
    TEACHING,
)


def _intent(text):
    return classify_conversation_intent(text)["intent"]


# ---- GENERAL_CONVERSATION ---------------------------------

GENERAL_CASES = [
    "سلام خوبی؟",
    "خودت رو معرفی کن",
    "لطفاً خودت رو معرفی کن",
    "اسمت چیه؟",
    "تو کی هستی؟",
    "تو چه کارهایی می تونی انجام بدی؟",
    "بیا یکم حرف بزنیم",
    "بیا درباره آشپزی حرف بزنیم",
    "نه، منظورم این نبود",
    "بیخیال اون موضوع",
    "Hello, how are you?",
    "Introduce yourself.",
    "Who are you?",
]


def test_general_conversation():

    for text in GENERAL_CASES:

        assert _intent(text) == GENERAL_CONVERSATION, text


# ---- ARCHITECTURE_CONVERSATION ----------------------------

ARCHITECTURE_CASES = [
    "بیا درباره معماری حرف بزنیم",
    "معماری مدرن رو دوست داری؟",
    "پلان باز چه مزایایی داره؟",
    "نور طبیعی توی طراحی خونه چقدر مهمه؟",
    "به نظرت آشپزخونه جزیره ای خوبه؟",
    "Let's talk about architecture.",
    "What are the benefits of an open floor plan?",
]


def test_architecture_conversation():

    for text in ARCHITECTURE_CASES:

        assert _intent(text) == ARCHITECTURE_CONVERSATION, text


# ---- TEACHING ---------------------------------------------

TEACHING_CASES = [
    "می‌خوام یه نکته معماری بهت یاد بدم",
    "این قانون رو یاد بگیر",
    "این رو به دانشت اضافه کن",
    "یادت باشه در طراحی من آشپزخانه باید کنار حیاط خلوت باشه",
    "می‌خوام این اصل رو برای طراحی‌های بعدی حفظ کنی",
    "I am going to teach you a design rule.",
    "Remember this rule for future designs.",
    "من بهت معماری یاد میدم",
]


def test_teaching():

    for text in TEACHING_CASES:

        assert _intent(text) == TEACHING, text


# ---- BOUNDARY / ADVERSARIAL -------------------------------

def test_declarative_opinion_is_not_teaching():

    assert _intent(
        "به نظرم آشپزخونه باید نزدیک ناهارخوری باشه"
    ) != TEACHING


def test_architecture_statement_is_not_teaching():

    assert _intent(
        "آشپزخونه بهتره نور طبیعی داشته باشه"
    ) != TEACHING


def test_correction_is_not_teaching():

    assert _intent("این رو قبول ندارم") == GENERAL_CONVERSATION

    assert _intent("اصلاحش کن") == GENERAL_CONVERSATION


def test_asking_assistant_to_teach_is_not_teaching():

    # The user is the LEARNER, not the teacher.
    assert _intent("معماری رو بهم یاد بده") != TEACHING


# ---- KEY REGRESSION ---------------------------------------

def test_self_introduction_is_general():

    for text in (
        "خودت رو معرفی کن",
        "لطفاً خودت رو معرفی کن",
        "Introduce yourself.",
        "Who are you?",
    ):

        result = classify_conversation_intent(text)

        assert result["intent"] == GENERAL_CONVERSATION, text

        assert result["is_teaching"] is False, text


# ---- NON-STICKY / SOURCE ----------------------------------

def test_source_is_current_turn():

    result = classify_conversation_intent(
        "خودت رو معرفی کن", previous_intent="TEACHING"
    )

    assert result["source"] == "current_turn"

    assert result["sticky_override"] is False


def test_previous_teaching_does_not_stick():

    # Even told the previous intent was TEACHING, a self-introduction
    # resolves to GENERAL_CONVERSATION.
    result = classify_conversation_intent(
        "راستی خودت رو معرفی کن", previous_intent="TEACHING"
    )

    assert result["intent"] == GENERAL_CONVERSATION


# ---- AUDITABLE SHAPE --------------------------------------

def test_decision_shape():

    result = classify_conversation_intent("خودت رو معرفی کن")

    for key in (
        "contract", "version", "intent", "confidence",
        "signals", "reason", "source",
        "raw_transcript", "interpreted_utterance",
        "is_teaching", "is_architecture", "is_general",
    ):

        assert key in result, key

    assert result["contract"] == "ConversationIntentBoundaryV1"


def test_raw_transcript_preserved():

    raw = "بیا یکمی راجب مماری صحبت کنیم"

    result = classify_conversation_intent(raw)

    assert result["raw_transcript"] == raw
