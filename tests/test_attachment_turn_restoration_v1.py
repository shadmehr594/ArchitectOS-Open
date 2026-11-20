# -*- coding: utf-8 -*-
"""CHAT-02C.2 — IMAGE AND ATTACHMENT TRANSCRIPT RESTORATION.

An image-only turn has no text, so the transcript skipped it entirely. This
suite locks down the repair on both sides:

* the backend transcript projection, which must pass attachments through the
  EXISTING public allowlist and keep every turn project-scoped;
* the frontend renderer, which must draw a bubble for a turn that has only an
  attachment, and must refuse to turn an untrusted path into an <img>.

The browser cases extract the real renderer block from `ui/static/app.js` and
run it in headless Chrome against a minimal page — no server required.
"""

import json
import os
from pathlib import Path

import pytest

from core.chat.chat_attachment import chat_attachment_service
from core.project.project_session_v1 import project_session
from core.project.project_workspace_v1 import project_workspace

ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "ui" / "static" / "app.js"

START = "// CHAT-02B — SAFE RTL-AWARE RICH TEXT"
END = "// OPERATION_VISIBILITY_UI_01"

IMAGE_ATT = {
    "id": "attachment_abc123",
    "kind": "image",
    "mime_type": "image/png",
    "filename": "stored_name.png",
    "display_name": "fixture.png",
    "url": "/artifacts/user_media/abc_fixture.png",
    "thumbnail_url": "/artifacts/user_media/abc_fixture.png",
    "size_bytes": 1234,
    "source": "user_upload",
    "status": "ready",
    "metadata": {},
    # internal resolution data that must NOT reach the client
    "storage_root": "user_media",
    "relative_path": "abc_fixture.png",
}

LEGACY_ATT = {"kind": "image", "display_name": "old_fixture.png"}


def _png_1x1():
    """A minimal valid 1x1 PNG, built locally (no fixture file, no AI image)."""
    import struct
    import zlib

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    raw = b"\x00" + bytes([200, 60, 60])
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b""))


PNG_1X1 = _png_1x1()


def _source(path):
    lines = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith("#") or s.startswith("//"):
            continue
        if "#" in line:
            line = line.split("#", 1)[0]
        lines.append(line)
    return "\n".join(lines)


def _renderer_source():
    source = APP_JS.read_text(encoding="utf-8")
    helper_start = source.index("function el(tag, className, text) {")
    helper_end = source.index("\n}", helper_start) + 2
    start = source.index(START)
    end = source.index(END, start)
    return source[helper_start:helper_end] + "\n" + source[start:end]


# ==========================================================
# BACKEND — PROJECT-SCOPED, SANITIZED, NON-WRITING
# ==========================================================

@pytest.fixture()
def temp_projects(monkeypatch):
    import shutil
    import uuid

    root = ROOT / ".pytest_tmp" / "attachment_restoration" / uuid.uuid4().hex
    root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(project_workspace, "projects_root", str(root))
    monkeypatch.setattr(project_workspace, "trash_root", str(root / "_trash"))
    os.makedirs(project_workspace.trash_root, exist_ok=True)
    try:
        yield root
    finally:
        shutil.rmtree(str(root), ignore_errors=True)


def _write(root, project_id, messages):
    pdir = os.path.join(str(root), project_id, "conversations")
    os.makedirs(pdir, exist_ok=True)
    path = os.path.join(pdir, "chat.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"contract": "ConversationStoreV1", "version": "1.0",
                   "project_id": project_id, "message_count": len(messages),
                   "messages": messages, "ui": {}}, fh, ensure_ascii=False)
    return path


MIXED = [
    {"role": "user", "text": "text only", "attachments": []},
    {"role": "assistant", "text": "reply", "attachments": []},
    {"role": "user", "text": "", "attachments": [IMAGE_ATT]},        # image-only
    {"role": "user", "text": "caption", "attachments": [IMAGE_ATT]},  # text + image
    {"role": "user", "text": "", "attachments": [LEGACY_ATT]},        # legacy, no url
    {"role": "assistant", "text": "reply2", "attachments": []},
]


def test_image_only_turn_is_returned_with_its_attachment(temp_projects):
    _write(temp_projects, "p1", MIXED)
    out = project_session.transcript("p1")
    assert len(out) == 6
    assert out[2]["text"] == "" and len(out[2]["attachments"]) == 1
    assert out[2]["attachments"][0]["kind"] == "image"


def test_chronological_order_is_preserved(temp_projects):
    _write(temp_projects, "p1", MIXED)
    out = project_session.transcript("p1")
    assert [e["role"] for e in out] == [
        "user", "assistant", "user", "user", "user", "assistant"]
    assert out[3]["text"] == "caption"


def test_attachments_are_sanitized_through_the_public_allowlist(temp_projects):
    _write(temp_projects, "p1", MIXED)
    att = project_session.transcript("p1")[2]["attachments"][0]
    assert att["url"] == IMAGE_ATT["url"]
    assert att["kind"] == "image"
    # internal resolution data must never leave the server
    assert "storage_root" not in att
    assert "relative_path" not in att


def test_public_attachment_drops_internal_and_raw_payloads():
    safe = chat_attachment_service.public_attachment({
        "id": "x", "kind": "voice", "url": None,
        "storage_root": "user_media", "relative_path": "a/b.webm",
        "audio_bytes": "AAAA", "stt_model": "whisper",
    })
    for leaked in ("storage_root", "relative_path", "audio_bytes"):
        assert leaked not in safe
    assert safe["kind"] == "voice"


def test_legacy_attachment_without_a_url_is_still_returned(temp_projects):
    _write(temp_projects, "p1", MIXED)
    att = project_session.transcript("p1")[4]["attachments"][0]
    assert att["display_name"] == "old_fixture.png"
    assert att.get("url") is None      # never invented


def test_multiple_attachments_keep_their_order(temp_projects):
    _write(temp_projects, "p1", [
        {"role": "user", "text": "", "attachments": [
            {"kind": "image", "display_name": "one.png", "url": "/artifacts/user_media/1.png"},
            {"kind": "image", "display_name": "two.png", "url": "/artifacts/user_media/2.png"},
            {"kind": "image", "display_name": "three.png", "url": "/artifacts/user_media/3.png"},
        ]},
    ])
    atts = project_session.transcript("p1")[0]["attachments"]
    assert [a["display_name"] for a in atts] == ["one.png", "two.png", "three.png"]


def test_attachments_are_project_scoped(temp_projects):
    _write(temp_projects, "A", MIXED)
    _write(temp_projects, "B", [{"role": "user", "text": "", "attachments": [
        {"kind": "image", "display_name": "b-only.png",
         "url": "/artifacts/user_media/b.png"}]}])
    a = project_session.transcript("A")
    b = project_session.transcript("B")
    assert all(x["display_name"] != "b-only.png"
               for e in a for x in e["attachments"])
    assert b[0]["attachments"][0]["display_name"] == "b-only.png"


def test_transcript_still_never_writes(temp_projects):
    path = _write(temp_projects, "p1", MIXED)
    before = Path(path).read_bytes()
    project_session.transcript("p1")
    project_session.transcript("p1")
    assert Path(path).read_bytes() == before


# ==========================================================
# FRONTEND — SOURCE CONTRACT
# ==========================================================

def test_attachment_renderer_exists_and_uses_img_only():
    src = _source(APP_JS)
    assert "function attachmentPreview(" in src
    assert 'el("img", "attach-image")' in src


def test_renderer_never_uses_innerHTML():
    src = _source(APP_JS)
    assert "innerHTML" not in src
    assert "insertAdjacentHTML" not in src
    assert "document.write" not in src


def test_message_node_renders_attachments_even_without_text():
    src = _source(APP_JS)
    start = src.index("function messageNode(")
    body = src[start:start + 900]
    assert "attachmentNodes(attachments)" in body


def test_load_conversation_no_longer_skips_empty_text_with_attachments():
    src = _source(APP_JS)
    start = src.index("async function loadConversation")
    body = src[start:src.index("function ", start + 10)]
    assert "if (!text.trim() && !attachments.length) return;" in body
    assert "messageNode(role, text, attachments)" in body


def test_status_row_reports_attachment_availability():
    src = _source(APP_JS)
    start = src.index("async function loadConversation")
    body = src[start:src.index("function ", start + 10)]
    assert "unavailable" in body


def test_live_path_renders_a_captionless_image_turn_too():
    src = _source(APP_JS)
    assert "liveAttachments" in src
    assert 'if (text || liveAttachments.length)' in src


# ==========================================================
# FRONTEND — RENDERED CONTRACT (headless Chrome, no server)
# ==========================================================

SAMPLES = {
    "text_only": {"text": "salam", "att": None},
    "image_only": {"text": "", "att": {"kind": "image",
                                       "display_name": "ok.png",
                                       "url": "/artifacts/user_media/ok.png"}},
    "text_image": {"text": "caption", "att": {"kind": "image",
                                              "display_name": "ok.png",
                                              "url": "/artifacts/user_media/ok.png"}},
    "legacy": {"text": "", "att": {"kind": "image", "display_name": "old.png"}},
    "traversal": {"text": "", "att": {"kind": "image",
                                      "display_name": "evil.png",
                                      "url": "/artifacts/user_media/../../secret.png"}},
    "absolute": {"text": "", "att": {"kind": "image", "display_name": "evil.png",
                                     "url": "http://evil.example/x.png"}},
    "javascript": {"text": "", "att": {"kind": "image", "display_name": "evil.png",
                                       "url": "javascript:alert(1)"}},
    "non_artifact": {"text": "", "att": {"kind": "image", "display_name": "evil.png",
                                         "url": "/etc/passwd"}},
    "not_image_kind": {"text": "", "att": {"kind": "voice", "display_name": "v.webm",
                                           "url": "/artifacts/user_media/v.webm"}},
    "multi": {"text": "", "att": [
        {"kind": "image", "display_name": "1.png", "url": "/artifacts/user_media/1.png"},
        {"kind": "image", "display_name": "2.png", "url": "/artifacts/user_media/2.png"},
    ]},
    "injection_name": {"text": "", "att": {
        "kind": "image", "display_name": "<img src=x onerror=\"window.__PWNED=1\">",
        "url": None}},
}


@pytest.fixture(scope="module")
def rendered():
    playwright_api = pytest.importorskip("playwright.sync_api")
    with playwright_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="chrome", headless=True)
        except Exception as exc:                      # pragma: no cover
            pytest.skip("no Chrome available: %s" % exc)
        page = browser.new_page(viewport={"width": 1000, "height": 900})
        # The harness has no ArchitectOS server, so serve a 1x1 PNG for any
        # artifact URL. A <base> is required: without it the page has no
        # origin, a relative `/artifacts/...` src never becomes a request,
        # and every <img> would fall through to the onerror placeholder.
        page.route("**/artifacts/**", lambda route: route.fulfill(
            status=200, content_type="image/png", body=PNG_1X1))
        page.set_content(
            "<!DOCTYPE html><html><head><base href='http://127.0.0.1:9/'>"
            "</head><body><div id='host'></div></body></html>")
        page.add_script_tag(content=_renderer_source())
        page.evaluate("""(samples) => {
            const host = document.getElementById('host');
            Object.keys(samples).forEach((k) => {
                const s = samples[k];
                const atts = s.att === null ? [] : (Array.isArray(s.att) ? s.att : [s.att]);
                const node = messageNode('user', s.text, atts);
                node.id = 'p_' + k;
                host.appendChild(node);
            });
        }""", SAMPLES)
        data = page.evaluate("""(keys) => {
            const out = {};
            keys.forEach((k) => {
                const bubble = document.querySelector('#p_' + k + ' .msg-bubble');
                out[k] = {
                    text: bubble.textContent.trim(),
                    imgs: bubble.querySelectorAll('img.attach-image').length,
                    placeholders: bubble.querySelectorAll('.attach-missing').length,
                    previews: bubble.querySelectorAll('.attach-turn').length,
                    injected: bubble.querySelectorAll('img:not(.attach-image),script').length,
                };
            });
            out.pwned = !!window.__PWNED;
            return out;
        }""", list(SAMPLES.keys()))
        browser.close()
    return data


def test_text_only_turn_still_renders(rendered):
    assert rendered["text_only"]["text"] == "salam"
    assert rendered["text_only"]["previews"] == 0


def test_image_only_turn_renders_a_bubble_with_an_image(rendered):
    r = rendered["image_only"]
    assert r["imgs"] == 1
    assert r["placeholders"] == 0
    assert r["text"] == ""          # no invented text


def test_text_plus_image_renders_both(rendered):
    r = rendered["text_image"]
    assert r["imgs"] == 1
    assert "caption" in r["text"]


def test_legacy_record_without_a_url_shows_a_placeholder(rendered):
    r = rendered["legacy"]
    assert r["imgs"] == 0
    assert r["placeholders"] == 1
    assert "unavailable" in r["text"]


@pytest.mark.parametrize("key", ["traversal", "absolute", "javascript", "non_artifact"])
def test_untrusted_paths_never_become_an_image(rendered, key):
    r = rendered[key]
    assert r["imgs"] == 0, "%s produced an <img>" % key
    assert r["placeholders"] == 1


def test_non_image_kind_is_not_rendered_as_an_image(rendered):
    assert rendered["not_image_kind"]["imgs"] == 0


def test_multiple_attachments_all_render_in_order(rendered):
    assert rendered["multi"]["previews"] == 2
    assert rendered["multi"]["imgs"] == 2


def test_attachment_name_cannot_inject_markup(rendered):
    r = rendered["injection_name"]
    assert r["injected"] == 0
    assert rendered["pwned"] is False
    assert "onerror" in r["text"]      # shown as literal text
