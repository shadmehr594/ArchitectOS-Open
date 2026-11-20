"""Regression tests for ARCHITECTOS_LOCAL_CHAT_UPLOAD_ACCEPTANCE_V1.

Each test locks a defect that was REPRODUCED on the live local stack
(UI 3000 -> Core API 5000 -> ChatArchitect -> Ollama) and then repaired.
No test here asserts a hardcoded answer: every one exercises the real
function that failed.
"""

import json
from io import BytesIO
from pathlib import Path

import pytest
from werkzeug.datastructures import FileStorage

from config import runtime_config as RC
from core.chat.chat_attachment import ChatAttachmentServiceV1
from core.chat.handlers.image_handler import (
    ImageHandler,
    _image_upload_rejection,
)
from core.chat.response_contract import envelope_status_for


# ==========================================================
# fixtures / fakes
# ==========================================================

class _FakeState:

    def __init__(self):
        self.data = {}
        self.messages = []

    def update(self, values):
        self.data.update(values)

    def add_message(self, role, text, attachments=None):
        self.messages.append(
            {"role": role, "text": text, "attachments": attachments or []}
        )


class _FakeImageBridge:

    def __init__(self):
        self.paths = []

    def process_upload(self, project, path):
        self.paths.append(Path(path))
        return {"asset": {"filename": Path(path).name, "status": "ready"}}


def _service(tmp_path):
    return ChatAttachmentServiceV1(
        {
            "user_media": tmp_path / "user_media",
            "comfy_output": tmp_path / "comfy_output",
            "architectos_output": tmp_path / "outputs",
            "architectos_export": tmp_path / "exports",
        }
    )


def _handler(service):
    handler = ImageHandler.__new__(ImageHandler)
    handler.attachment_service = service
    handler.image_bridge = _FakeImageBridge()
    handler._state = _FakeState()
    return handler


def _png(name="building.png"):
    return FileStorage(
        stream=BytesIO(b"\x89PNG\r\n\x1a\n" + b"0" * 32),
        filename=name,
        content_type="image/png",
    )


# ==========================================================
# D0 — a partial root map must not crash the attachment service
# ==========================================================

def test_partial_root_map_is_tolerated(tmp_path):
    """Every accessor uses roots.get(); construction must not KeyError."""

    service = ChatAttachmentServiceV1({"user_media": tmp_path / "only"})

    assert service.roots.get("project_media") is None
    # an absent root is reported as "unavailable", not raised
    assert service.attachment_for_path(
        tmp_path / "only" / "x.png", root_key="project_media", source="t"
    ) is None


# ==========================================================
# D1 — the image handler must not own the user-turn record
# ==========================================================

def test_upload_only_records_no_user_turn(tmp_path):
    """The request boundary owns the user turn; a second write duplicated it."""

    handler = _handler(_service(tmp_path))

    result = handler.handle_image_upload_only(_png())

    assert result["status"] == "waiting_for_instruction"
    assert handler.state.messages == []


def test_upload_only_accepts_prestored_path_without_copying(tmp_path):
    """A boundary-stored image is reused, not stored a second time."""

    service = _service(tmp_path)
    handler = _handler(service)

    stored = service.save_upload(_png("boundary.png"), kind="image")
    assert stored["status"] == "ready"
    attachment = service.public_attachment(stored["attachment"])
    before = sorted(p.name for p in service.roots["user_media"].iterdir())

    result = handler.handle_image_upload_only(
        {"path": stored["path"], "attachment": attachment}
    )

    after = sorted(p.name for p in service.roots["user_media"].iterdir())

    assert result["status"] == "waiting_for_instruction"
    assert after == before, "the pre-stored upload must not be copied again"
    # the boundary's own attachment (with its servable URL) is carried through
    assert result["attachments"][0]["url"] == attachment["url"]
    assert result["attachments"][0]["id"] == attachment["id"]
    assert handler.state.messages == []


# ==========================================================
# D5 — a rejected upload must never read as a success
# ==========================================================

def test_rejected_upload_carries_truthful_message(tmp_path):
    handler = _handler(_service(tmp_path))

    rejected = FileStorage(
        stream=BytesIO(b"not an image"),
        filename="unsupported.xyz",
        content_type="application/octet-stream",
    )

    result = handler.handle_image_upload_only(rejected)

    assert result["status"] == "error"
    assert result["error"] == "unsupported_image_format"
    assert "پذیرفته نشد" in result["message"]
    # the response adapter's success default must not be reachable here
    assert "دریافت شد" not in result["message"]


def test_rejection_text_is_never_the_success_default():
    for code in ("unsupported_image_format", "invalid_upload_path",
                 "attachment_registration_failed", "some_unknown_code"):
        text = _image_upload_rejection(code)
        assert text
        assert "دریافت شد" not in text


# ==========================================================
# D4 — the chat envelope must report the turn's real outcome
# ==========================================================

@pytest.mark.parametrize(
    "response_status, expected",
    [
        ("error", "error"),
        ("ERROR", "error"),
        (" error ", "error"),
        ("success", "success"),
        ("waiting_for_instruction", "success"),
        ("degraded", "success"),
        ("", "success"),
        (None, "success"),
    ],
)
def test_envelope_status_follows_the_response(response_status, expected):
    assert envelope_status_for({"status": response_status}) == expected


def test_envelope_status_tolerates_a_non_dict_response():
    assert envelope_status_for("plain text") == "success"
    assert envelope_status_for(None) == "success"


# ==========================================================
# J — upload size policy must exist and be bounded
# ==========================================================

def test_upload_size_limit_is_configured_and_positive():
    assert isinstance(RC.MAX_UPLOAD_BYTES, int)
    assert RC.MAX_UPLOAD_BYTES > 0


def test_core_api_installs_the_upload_ceiling():
    """The limit must be on the real Flask app, not only in config.

    Run in a SUBPROCESS: importing `app` constructs the process-wide
    ChatArchitect singleton, which must not leak into the rest of the suite.
    """

    code = (
        "import json;"
        "import app as core_app;"
        "from config import runtime_config as RC;"
        "print(json.dumps({"
        "'max': core_app.app.config.get('MAX_CONTENT_LENGTH'),"
        "'expected': RC.MAX_UPLOAD_BYTES,"
        "'has_413': bool(core_app.app.error_handler_spec[None].get(413))"
        "}))"
    )

    import subprocess
    import sys

    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(Path(__file__).resolve().parents[1]),
        capture_output=True,
        text=True,
        timeout=10800,
    )

    assert proc.returncode == 0, proc.stderr[-2000:]

    payload = json.loads(proc.stdout.strip().splitlines()[-1])

    assert payload["max"] == payload["expected"]
    assert payload["has_413"] is True


def test_oversized_request_is_refused_with_json():
    """A body over the ceiling must be refused with a JSON error, not HTML.

    The ceiling is lowered through its own configuration surface, so the real
    mechanism (config -> app.config -> Werkzeug -> 413 handler) is exercised
    without pushing 64 MiB through the test client.
    """

    code = (
        "import os;"
        "os.environ['ARCHITECTOS_MAX_UPLOAD_BYTES'] = '1024';"
        "import json;"
        "import app as core_app;"
        "from config import runtime_config as RC;"
        "c = core_app.app.test_client();"
        "r = c.post('/chat', data=b'x' * 4096,"
        "           content_type='application/octet-stream');"
        "print(json.dumps({'code': r.status_code,"
        "                  'limit': RC.MAX_UPLOAD_BYTES,"
        "                  'body': r.get_data(as_text=True)}))"
    )

    import subprocess
    import sys

    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(Path(__file__).resolve().parents[1]),
        capture_output=True,
        text=True,
        timeout=10800,
    )

    assert proc.returncode == 0, proc.stderr[-2000:]

    payload = json.loads(proc.stdout.strip().splitlines()[-1])
    body = json.loads(payload["body"])

    assert payload["limit"] == 1024
    assert payload["code"] == 413
    assert body["error"] == "upload_too_large"
    assert body["limit_bytes"] == 1024
    assert "بزرگ" in body["message"]
