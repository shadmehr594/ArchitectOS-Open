# -*- coding: utf-8 -*-
"""ARCHITECTOS startup → trusted-local bootstrap handoff.

Offline tests for the integration that was broken: the Windows entry points
opened a bare ``http://127.0.0.1:3000`` and guessed at token files, so the
browser never obtained a trusted session. The launcher already owns the token;
these tests pin that the URL comes from it, and only when the services it
started actually share that trust domain.
"""

import os
import sys
import tokenize

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from launcher import trusted_ui_url  # noqa: E402

UI = "http://127.0.0.1:3000"
TOKEN = "t" * 48
START_BAT = os.path.join(ROOT, "START_ARCHITECTOS.bat")
OPEN_BAT = os.path.join(ROOT, "OPEN_ARCHITECTOS_UI.bat")
LAUNCHER = os.path.join(ROOT, "launcher.py")

_NON_CODE = frozenset({
    tokenize.COMMENT, tokenize.STRING, tokenize.NL, tokenize.NEWLINE,
    tokenize.INDENT, tokenize.DEDENT, tokenize.ENCODING, tokenize.ENDMARKER,
})


def _read(path):
    with open(path, encoding="utf-8", errors="replace") as handle:
        return handle.read()


# -- the URL builder ----------------------------------------------------
def test_token_goes_in_the_fragment_not_the_query():
    url = trusted_ui_url(UI, TOKEN, True)
    assert url == UI + "/#local-bootstrap=" + TOKEN
    # a fragment is never sent to the server, so the token stays out of logs
    assert "?" not in url
    assert url.split("#", 1)[1].startswith("local-bootstrap=")


def test_no_url_when_services_were_not_started_by_this_launch():
    """The core safety property: never advertise a token to a foreign trust domain."""
    assert trusted_ui_url(UI, TOKEN, False) is None


def test_no_url_for_a_missing_or_short_token():
    assert trusted_ui_url(UI, "", True) is None
    assert trusted_ui_url(UI, None, True) is None
    assert trusted_ui_url(UI, "short", True) is None


def test_no_url_without_a_ui_url():
    assert trusted_ui_url("", TOKEN, True) is None
    assert trusted_ui_url(None, TOKEN, True) is None


def test_trailing_slash_is_not_doubled():
    assert trusted_ui_url(UI + "/", TOKEN, True) == UI + "/#local-bootstrap=" + TOKEN


# -- the launcher never persists the token ------------------------------
def test_launcher_does_not_write_the_bootstrap_token():
    offenders = []
    with open(LAUNCHER, "rb") as handle:
        for token in tokenize.tokenize(handle.readline):
            if token.type in _NON_CODE:
                continue
            line = token.line
            if "_LOCAL_BOOTSTRAP_TOKEN" in line and (
                "write" in line or "open(" in line or "json.dump" in line
            ):
                offenders.append(line.strip())
    assert not offenders, "token persisted to disk: %s" % (offenders,)


# -- the Windows entry points ------------------------------------------
def test_open_ui_no_longer_opens_a_bare_url():
    text = _read(OPEN_BAT)
    assert 'start "" "%UI_URL%"' not in text, (
        "a bare UI URL would open a page without a trusted session")
    assert "launcher.py --open-ui" in text


def test_open_ui_asks_before_restarting_live_services():
    text = _read(OPEN_BAT)
    assert "choice /c YN" in text, "restart must be an explicit user choice"
    assert "--restart" in text


def test_open_ui_does_not_guess_at_token_files():
    text = _read(OPEN_BAT).lower()
    for guess in ("runtime.env", "bootstrap_token", "local_bootstrap_token"):
        assert guess not in text, "startup still guesses at a token file: %s" % guess


def test_start_passes_open_ui_to_the_launcher():
    text = _read(START_BAT)
    assert "launcher.py --open-ui" in text
    assert "runtime.env" not in text.lower()
