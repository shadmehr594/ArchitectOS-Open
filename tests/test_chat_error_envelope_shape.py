# ==========================================================
# CHAT ERROR ENVELOPE SHAPE — CONTRACT / REGRESSION TESTS
#
# Covers the defect found by the CHAT RUNTIME DEBUG checkpoint:
#
#   app.py `chat_api` returned a DIFFERENT envelope shape on its
#   failure branch than on its success branch.
#
#     success -> {status, response, input, outputs, project_id,
#                 strategy, save_state}
#     failure -> {status, error}          <-- no `response`
#
#   The UI reads `payload.response.message`, so a server-side failure
#   rendered the RAW Python exception string as the assistant's chat
#   reply — observed live as
#     "'Brain' object has no attribute '_chat_response'"
#   and the turn was silently dropped from the conversation store.
#
# The contract pinned here: a failure envelope must be a SUPERSET of
# the success envelope (so no consumer loses a key), may add only the
# `error` diagnostic, and must never expose a raw exception as the
# user-facing `response.message`.
#
# Run either way:
#   .venv/Scripts/python.exe -m pytest tests/test_chat_error_envelope_shape.py
#   .venv/Scripts/python.exe tests/test_chat_error_envelope_shape.py
# ==========================================================


import json
import os
import sys
import tempfile


ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

if ROOT not in sys.path:

    sys.path.insert(0, ROOT)


_TEMP_ROOT = os.path.join(
    tempfile.gettempdir(), "architectos_chat_error_envelope"
)

os.environ["ARCHITECTOS_PROJECT_DATA_ROOT"] = _TEMP_ROOT

os.environ.setdefault(
    "ARCHITECTOS_PROJECTS_ROOT", os.path.join(_TEMP_ROOT, "projects")
)

os.environ.setdefault(
    "ARCHITECTOS_PROJECT_TRASH_ROOT", os.path.join(_TEMP_ROOT, "trash")
)

# Render-stop guard: acceptance must never reach ComfyUI.
os.environ["ARCHITECTOS_COMFY_PORT"] = "9"


import app as appmod  # noqa: E402


_RESULTS = []


def _check(name, passed, detail=None):

    _RESULTS.append((name, bool(passed), detail))

    return bool(passed)


def _probe():

    """Return (success_payload, failure_payload) from the real endpoint."""

    client = appmod.app.test_client()

    created = client.post(
        "/api/projects", json={"name": "Envelope Contract"}
    )

    project_id = (
        (created.get_json() or {}).get("project") or {}
    ).get("project_id")

    ok = client.post(
        "/api/chat",
        json={"text": "امروز هوا خوبه", "project_id": project_id},
    )

    original = appmod.chat.handle

    def _boom(*args, **kwargs):

        raise RuntimeError("injected failure — envelope contract")

    appmod.chat.handle = _boom

    try:

        bad = client.post(
            "/api/chat",
            json={"text": "امروز هوا خوبه", "project_id": project_id},
        )

    finally:

        appmod.chat.handle = original

    return ok.get_json() or {}, bad.get_json() or {}


# ==========================================================
# THE CONTRACT
# ==========================================================

def test_failure_envelope_is_a_superset_of_success_envelope():

    ok, bad = _probe()

    missing = sorted(set(ok.keys()) - set(bad.keys()))

    return _check(
        "failure envelope carries every success-path key",
        not missing,
        {"missing": missing, "success": sorted(ok.keys())},
    )


def test_only_the_error_diagnostic_is_added():

    ok, bad = _probe()

    extra = sorted(set(bad.keys()) - set(ok.keys()))

    return _check(
        "the only extra failure-path key is `error`",
        extra == ["error"],
        {"extra": extra},
    )


def test_failure_envelope_exposes_response_message():

    _ok, bad = _probe()

    response = bad.get("response") or {}

    return _check(
        "failure envelope exposes response.message",
        bool(response.get("message")),
        {"response": response},
    )


def test_failure_never_shows_a_raw_exception_as_the_reply():

    _ok, bad = _probe()

    response = bad.get("response") or {}

    message = str(response.get("message") or "")

    return _check(
        "response.message never leaks the raw exception",
        "injected failure" not in message
        and "Traceback" not in message
        and "AttributeError" not in message,
        {"message": message},
    )


def test_failure_keeps_the_diagnostic_and_the_error_status():

    _ok, bad = _probe()

    response = bad.get("response") or {}

    return _check(
        "status stays error and the diagnostic is preserved",
        bad.get("status") == "error"
        and response.get("type") == "chat_error"
        and "injected failure" in str(bad.get("error") or ""),
        {
            "status": bad.get("status"),
            "type": response.get("type"),
            "error": bad.get("error"),
        },
    )


def test_failure_envelope_does_not_start_anything():

    _ok, bad = _probe()

    response = bad.get("response") or {}

    return _check(
        "failure envelope requests no render and learns nothing",
        response.get("render_requested") is False
        and response.get("permanent_learning") is False,
        {"response": response},
    )


# ==========================================================
# RUNNER
# ==========================================================

def main():

    print("\n" + "=" * 70)
    print("CHAT ERROR ENVELOPE SHAPE — CONTRACT TESTS")
    print("=" * 70)

    for name, function in sorted(
        (name, value)
        for name, value in globals().items()
        if name.startswith("test_") and callable(value)
    ):

        try:

            function()

        except Exception as error:

            _check(
                name,
                False,
                {"exception": type(error).__name__ + ": " + str(error)},
            )

    failed = [item for item in _RESULTS if not item[1]]

    for name, passed, detail in _RESULTS:

        print("  [%s] %s" % ("PASS" if passed else "FAIL", name))

        if not passed:

            print(
                "        ",
                json.dumps(detail, ensure_ascii=False, default=str)[:420],
            )

    print("-" * 70)
    print("  %d/%d PASS" % (len(_RESULTS) - len(failed), len(_RESULTS)))
    print("=" * 70 + "\n")

    return 0 if not failed else 1


if __name__ == "__main__":

    sys.exit(main())
