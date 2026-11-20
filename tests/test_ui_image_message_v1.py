"""R4_PHOTO_UI_FINAL_CLOSURE_V1 - focused UI test for image-response text.

Runs `handleChatResponse()` in the REAL page (headless Chrome over CDP) with
synthetic payloads, so the test exercises the shipped renderer rather than a
copy of it. No chat request is made and no model or render boundary is touched:
`loadAssets()` / `newestAsset()` are stubbed and `renderCard()` is wrapped by a
counting spy.

The module skips when the UI gateway is not running.
"""

import json
import os
import subprocess
import time
import urllib.request

import pytest

websocket = pytest.importorskip("websocket")

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
UI = os.environ.get("ARCHITECTOS_UI_URL", "http://127.0.0.1:3000/")
PORT = 9231
PROFILE = os.path.join(os.environ.get("TEMP", r"C:\Windows\Temp"), "arch_cdp_uitest")

CONFIRM = ("\u062a\u0631\u0627\u0632 \u0631\u0646\u06af \u0639\u06a9\u0633 "
           "\u06a9\u0645\u06cc \u06af\u0631\u0645\u200c\u062a\u0631 \u0634\u062f. "
           "\u0627\u062c\u0632\u0627\u06cc \u0645\u0639\u0645\u0627\u0631\u06cc "
           "\u0628\u0627\u0632\u0633\u0627\u0632\u06cc \u06cc\u0627 "
           "\u062c\u0627\u0628\u0647\u200c\u062c\u0627 \u0646\u0634\u062f\u0646\u062f.")


def _ui_ready():
    try:
        with urllib.request.urlopen(UI + "status", timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _ui_ready(), reason="ArchitectOS UI gateway is not running"
)


class _Page:
    def __init__(self):
        os.makedirs(PROFILE, exist_ok=True)
        self.proc = subprocess.Popen([
            CHROME, "--headless=new", "--remote-debugging-port=%d" % PORT,
            "--user-data-dir=" + PROFILE, "--no-first-run",
            "--no-default-browser-check", "--disable-features=Translate",
            "--window-size=1400,1000", "about:blank",
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        target = None
        for _ in range(60):
            try:
                with urllib.request.urlopen(
                    "http://127.0.0.1:%d/json" % PORT, timeout=5
                ) as r:
                    for t in json.load(r):
                        if t.get("type") == "page":
                            target = t
                            break
                if target:
                    break
            except Exception:
                pass
            time.sleep(0.5)
        if not target:
            raise RuntimeError("no page target")

        self.ws = websocket.create_connection(target["webSocketDebuggerUrl"],
                                              timeout=10800)
        self._id = 0
        self.cmd("Page.enable")
        self.cmd("Runtime.enable")
        self.cmd("Network.enable")
        self.cmd("Network.setCacheDisabled", cacheDisabled=True)
        self.cmd("Page.navigate", url=UI)
        for _ in range(120):
            if self.js("document.readyState") == "complete":
                break
            time.sleep(0.5)
        # handleChatResponse must exist before any case runs
        for _ in range(60):
            if self.js("typeof handleChatResponse === 'function'"):
                break
            time.sleep(0.5)

    def cmd(self, method, **params):
        self._id += 1
        self.ws.send(json.dumps({"id": self._id, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self._id:
                if "error" in msg:
                    raise RuntimeError("%s -> %s" % (method, msg["error"]))
                return msg.get("result", {})

    def js(self, expression):
        return self.cmd("Runtime.evaluate", expression=expression,
                        returnByValue=True, awaitPromise=True) \
            .get("result", {}).get("value")

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass
        self.proc.terminate()


@pytest.fixture(scope="module")
def page():
    p = _Page()
    try:
        yield p
    finally:
        p.close()


def _run(page, payload):
    """Render one payload into a detached container and report the DOM facts."""

    return page.js(
        "(async function(){"
        "window.__renderCardCalls=0;"
        "window.loadAssets=async function(){};"
        "window.newestAsset=function(){return null;};"
        "if(!window.__rcWrapped){"
        "  var o=window.renderCard;"
        "  window.renderCard=function(){window.__renderCardCalls++;return o.apply(this,arguments);};"
        "  window.__rcWrapped=true;"
        "}"
        "var box=document.createElement('div');"
        "box.id='__t';"
        "await handleChatResponse(%s, box);"
        "var bubbles=Array.from(box.querySelectorAll('.msg-assistant .msg-bubble'));"
        "return JSON.stringify({"
        "  cardCalls: window.__renderCardCalls,"
        "  assistantCount: box.querySelectorAll('.msg-assistant').length,"
        "  bubbleTexts: bubbles.map(function(b){return b.innerText;}),"
        "  hasImg: !!box.querySelector('img'),"
        "  injectedTags: box.querySelectorAll('.msg-bubble b, .msg-bubble script, "
        "                 .msg-bubble img[data-x]').length,"
        "  rawHtml: box.innerHTML.indexOf('&lt;b&gt;')>=0"
        "});"
        "})()" % json.dumps(payload)
    )


def _photo_payload(message=CONFIRM):
    return {
        "status": "success",
        "response": {
            "type": "image",
            "status": "success",
            "engine": "photometric_warmth_adjustment_v1",
            "message": message,
            "attachments": [{
                "id": "attachment_x", "kind": "image", "mime_type": "image/png",
                "filename": "photo_warmth_abc.png", "status": "ready",
                "url": "/artifacts/architectos_output/photo_warmth_abc.png",
            }],
        },
    }


# ==========================================================
# A / H / I / J - PHOTO-02 image + confirmation text
# ==========================================================

def test_a_photo02_image_and_confirmation_both_displayed(page):
    data = json.loads(_run(page, _photo_payload()))

    assert data["cardCalls"] == 1, "the image card must still be rendered"
    assert data["hasImg"] is True
    assert data["assistantCount"] == 1, "exactly one assistant message (no duplicate)"
    assert CONFIRM in " ".join(data["bubbleTexts"]), data["bubbleTexts"]


# ==========================================================
# B - ordinary image response with text
# ==========================================================

def test_b_ordinary_image_and_text(page):
    payload = {
        "status": "success",
        "response": {
            "type": "image", "status": "success", "engine": "render_runtime",
            "message": "Here is the rendered facade.",
            "attachments": [{
                "kind": "image", "url": "/artifacts/comfy_output/a.png",
                "filename": "a.png", "status": "ready",
            }],
        },
    }
    data = json.loads(_run(page, payload))

    assert data["cardCalls"] == 1
    assert data["assistantCount"] == 1
    assert "Here is the rendered facade." in " ".join(data["bubbleTexts"])


# ==========================================================
# C - image only, no message -> card only, no empty bubble
# ==========================================================

def test_c_image_without_message_renders_card_only(page):
    payload = _photo_payload(message="")
    data = json.loads(_run(page, payload))

    assert data["cardCalls"] == 1
    assert data["assistantCount"] == 0, "an empty message must not create a bubble"


# ==========================================================
# D - text-only response unchanged
# ==========================================================

def test_d_text_only_unchanged(page):
    payload = {"status": "success",
               "response": {"type": "chat", "status": "success",
                            "message": "Just a sentence."}}
    data = json.loads(_run(page, payload))

    assert data["cardCalls"] == 0
    assert data["assistantCount"] == 1
    assert "Just a sentence." in " ".join(data["bubbleTexts"])


# ==========================================================
# E - error response keeps its message
# ==========================================================

def test_e_error_response_message_preserved(page):
    payload = {"status": "error", "error": "boom",
               "response": {"message": "Something failed."}}
    data = json.loads(_run(page, payload))

    assert data["assistantCount"] == 1
    assert "Something failed." in " ".join(data["bubbleTexts"])


# ==========================================================
# F - multiple attachments keep the existing display policy
# ==========================================================

def test_f_multiple_attachments_keep_policy(page):
    payload = _photo_payload()
    payload["response"]["attachments"].append({
        "kind": "image", "url": "/artifacts/architectos_output/second.png",
        "filename": "second.png", "status": "ready",
    })
    data = json.loads(_run(page, payload))

    # the existing policy renders attachments[0] only
    assert data["cardCalls"] == 1
    assert data["assistantCount"] == 1


# ==========================================================
# G - user-controlled text is displayed, never executed
# ==========================================================

def test_g_message_text_is_not_html(page):
    hostile = "<b>bold?</b><script>window.__pwned=1</script>"
    data = json.loads(_run(page, _photo_payload(message=hostile)))

    assert page.js("window.__pwned === undefined") is True
    assert data["injectedTags"] == 0
    assert data["assistantCount"] == 1
    # the literal text survives as text
    assert "<b>bold?</b>" in " ".join(data["bubbleTexts"])
