# -*- coding: utf-8 -*-
"""CHAT-02B — Persian RTL + Markdown rendering in the chat transcript.

The renderer lives in `ui/static/app.js` between two stable sentinel
comments. This suite extracts exactly that block, runs it in a real headless
browser (Playwright + Chrome) against a minimal page, and asserts the
rendering contract. No ArchitectOS server is required.

Skipped automatically when Playwright/Chrome is unavailable, so the suite
never becomes a hard dependency of a unit run.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "ui" / "static" / "app.js"
STYLE_CSS = ROOT / "ui" / "static" / "style.css"

START = "// CHAT-02B — SAFE RTL-AWARE RICH TEXT"
END = "// OPERATION_VISIBILITY_UI_01"

playwright_api = pytest.importorskip(
    "playwright.sync_api", reason="playwright is not installed")


def _el_helper_source():
    """`messageNode` uses the shared `el()` helper, defined earlier in the
    file. Extract it verbatim so the harness runs the real code."""
    source = APP_JS.read_text(encoding="utf-8")
    start = source.index("function el(tag, className, text) {")
    end = source.index("\n}", start) + 2
    return source[start:end]


def _renderer_source():
    source = APP_JS.read_text(encoding="utf-8")
    start = source.index(START)
    end = source.index(END, start)
    return _el_helper_source() + "\n" + source[start:end]


def _css_block():
    css = STYLE_CSS.read_text(encoding="utf-8")
    start = css.index("CHAT-02B — RTL-AWARE RICH TEXT")
    return css[start:start + 1400]


# ==========================================================
# STATIC CONTRACT (no browser needed)
# ==========================================================

def test_renderer_block_exists_and_is_extractable():
    src = _renderer_source()
    assert "function renderRichText" in src
    assert "function messageNode" in src


def test_renderer_never_uses_innerHTML():
    src = _renderer_source()
    code = "\n".join(
        line for line in src.splitlines() if not line.strip().startswith("//")
    )
    assert "innerHTML" not in code
    assert "outerHTML" not in code
    assert "insertAdjacentHTML" not in code
    assert "document.write" not in code


def test_assistant_bubble_is_built_from_the_renderer():
    src = _renderer_source()
    assert 'if (role === "assistant")' in src
    assert "bubble.appendChild(renderRichText(body))" in src


def test_css_gives_the_bubble_block_layout_and_marker_side():
    css = _css_block()
    assert "white-space: normal" in css          # blocks carry the lines
    assert "padding-inline-start" in css          # marker follows direction
    assert ".msg-bubble li" in css


# ==========================================================
# RENDERED CONTRACT (headless Chrome, no server)
# ==========================================================

SAMPLES = {
    "fa_ordered": "۱. **پیرنگ‌پردازی دقیق:** توضیح فارسی\n۲. **تعلیق داستان (Suspense):** توضیح فارسی",
    "en_ordered": "1. **Logical Consistency** — plot\n2. **Subtle Clues** — hints",
    "fa_bullets": "- **نکته اول:** توضیح\n- **نکته دوم:** توضیح",
    "fa_para": "این یک پاراگراف فارسی است.",
    "en_para": "This is an English paragraph.",
    "mixed": "در متن **Suspense** به معنی تعلیق است.",
    "rule": "بند اول\n\n***\n\nبند دوم",
    "injection": '<img src=x onerror="window.__PWNED=1"><script>window.__PWNED=1</script> **bold**',
}

PAGE = """<!DOCTYPE html><html><head><meta charset="utf-8">
<style>%s</style></head><body>
<div id="host"></div>
</body></html>"""


@pytest.fixture(scope="module")
def rendered():
    from playwright.sync_api import sync_playwright

    html = PAGE % _css_block()
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="chrome", headless=True)
        except Exception as exc:                      # pragma: no cover
            pytest.skip("no Chrome available: %s" % exc)
        page = browser.new_page(viewport={"width": 1000, "height": 900})
        page.set_content(html)
        page.add_script_tag(content=_renderer_source())
        page.evaluate("""(samples) => {
            const host = document.getElementById('host');
            Object.keys(samples).forEach((k) => {
                const node = messageNode('assistant', samples[k]);
                node.id = 'p_' + k;
                host.appendChild(node);
            });
        }""", SAMPLES)
        data = page.evaluate("""(keys) => {
            const out = {};
            keys.forEach((k) => {
                const bubble = document.querySelector('#p_' + k + ' .msg-bubble');
                const list = bubble.querySelector('ol, ul');
                const p = bubble.querySelector('p');
                out[k] = {
                    strong: bubble.querySelectorAll('strong').length,
                    li: bubble.querySelectorAll('li').length,
                    ol: bubble.querySelectorAll('ol').length,
                    ul: bubble.querySelectorAll('ul').length,
                    hr: bubble.querySelectorAll('hr').length,
                    img: bubble.querySelectorAll('img').length,
                    script: bubble.querySelectorAll('script').length,
                    listDir: list ? list.getAttribute('dir') : null,
                    listPadRight: list ? getComputedStyle(list).paddingRight : null,
                    listPadLeft: list ? getComputedStyle(list).paddingLeft : null,
                    pDir: p ? p.getAttribute('dir') : null,
                    text: bubble.textContent,
                };
            });
            out.pwned = !!window.__PWNED;
            return out;
        }""", list(SAMPLES.keys()))
        browser.close()
    return data


def test_persian_ordered_list_is_rtl_with_right_side_marker(rendered):
    r = rendered["fa_ordered"]
    assert r["ol"] == 1 and r["li"] == 2
    assert r["listDir"] == "rtl"
    assert float(r["listPadRight"].replace("px", "")) > 0     # marker side
    assert float(r["listPadLeft"].replace("px", "")) == 0


def test_english_ordered_list_stays_ltr(rendered):
    r = rendered["en_ordered"]
    assert r["ol"] == 1 and r["li"] == 2
    assert r["listDir"] == "ltr"
    assert float(r["listPadLeft"].replace("px", "")) > 0
    assert float(r["listPadRight"].replace("px", "")) == 0


def test_persian_unordered_list_is_rtl(rendered):
    r = rendered["fa_bullets"]
    assert r["ul"] == 1 and r["li"] == 2
    assert r["listDir"] == "rtl"


def test_bold_is_rendered_and_asterisks_are_gone(rendered):
    assert rendered["fa_ordered"]["strong"] == 2
    assert rendered["en_ordered"]["strong"] == 2
    for key in ("fa_ordered", "en_ordered", "fa_bullets", "mixed"):
        assert "**" not in rendered[key]["text"], key


def test_direction_is_detected_per_block(rendered):
    assert rendered["fa_para"]["pDir"] == "rtl"
    assert rendered["en_para"]["pDir"] == "ltr"
    assert rendered["mixed"]["pDir"] == "rtl"      # first strong char wins


def test_thematic_break_is_not_left_as_asterisks(rendered):
    assert rendered["rule"]["hr"] == 1
    assert "***" not in rendered["rule"]["text"]


def test_untrusted_text_cannot_inject_markup(rendered):
    r = rendered["injection"]
    assert r["img"] == 0
    assert r["script"] == 0
    assert rendered["pwned"] is False
    assert "onerror" in r["text"]                  # shown as literal text
    assert r["strong"] == 1                        # the safe part still renders
