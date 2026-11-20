# core/chat/code_quality_review_v1.py
"""CodeQualityReviewV1 — honest, static-only quality reporting for staged code.

WHY THIS EXISTS
---------------
Staging used to expose exactly one semantic property: ``ast.parse`` succeeded.
The reply then said «پیش‌نویس … آماده شد» + «نحو (syntax): معتبر», which reads
as "the application works". It does not. Measured on the real candidate
``cb6772f0…`` (project_f043688f): syntax VALID, yet the C button appended the
letter "C" to the number, ``5 + × 2 =`` produced 7, and Numpad keys did
nothing — none of which syntax can see.

This module separates the three questions that were being conflated:

* ``syntax``     — does it parse?            (already computed by staging)
* ``static_review`` — do a few PROVABLE source-level defects exist?
* ``functional`` — does it actually behave?  **NOT_RUN** until an authorized
  isolated test has really executed. Never inferred from the other two.

It also carries the user's own acceptance criteria as
``unverified_requirements``: echoed verbatim, never scored.

DESIGN LIMITS (deliberate)
--------------------------
* Static analysis here is AST-only and small. It does NOT attempt to prove GUI
  behaviour, callback wiring or state-machine semantics — those are not
  statically provable without heuristics, and a heuristic "PASS" would be a new
  kind of false confidence.
* ``FAIL`` is reserved for defects that are certain from the syntax tree alone.
  Anything arguable is ``WARN``.
* Nothing here executes, imports, rewrites or re-hashes the staged source.
"""

from __future__ import annotations

import ast
import re

CONTRACT = "CodeQualityReviewV1"
VERSION = "1.0"

SYNTAX_PASS = "PASS"
SYNTAX_FAIL = "FAIL"

STATIC_PASS = "PASS"
STATIC_WARN = "WARN"
STATIC_FAIL = "FAIL"

FUNCTIONAL_NOT_RUN = "NOT_RUN"

SEVERITY_FAIL = "FAIL"
SEVERITY_WARN = "WARN"

#: Maximum acceptance items retained. A request is not a test suite; this is a
#: prompt-sized echo, not a spec.
MAX_REQUIREMENTS = 20

#: Each retained requirement is clamped so one pasted essay cannot bloat the
#: staged reply.
MAX_REQUIREMENT_CHARS = 300


# ==========================================================
# ACCEPTANCE-CRITERIA ECHO
# ==========================================================

# "۱." / "1." / "1)" / "1-" at the start of a line.
_NUMBERED_ITEM_RE = re.compile(
    r"^\s*(?:[0-9]{1,2}|[\u06F0-\u06F9]{1,2})\s*[.)\-\u2013]\s+(.{3,})$"
)

# "- item" / "* item" / "• item"
_BULLET_ITEM_RE = re.compile(r"^\s*[-\*\u2022]\s+(.{3,})$")

# A bold/heading line is a section title, not an acceptance item.
_HEADING_RE = re.compile(r"^\s*(?:\*\*.+\*\*|#+\s+.+)\s*:?\s*$")


def extract_acceptance_requirements(text):
    """Enumerated acceptance items from the user's request, VERBATIM.

    The user routinely writes the acceptance list themselves ("۱. …", "۲. …",
    "`2 + 3 × 4 =` باید `20` بدهد"). That list is the only real definition of
    "correct" available, so it is carried with the proposal instead of being
    discarded. Nothing is interpreted, scored or reworded — a static reviewer
    cannot verify behaviour, and pretending otherwise is exactly the failure
    this module exists to prevent.
    """

    if not isinstance(text, str) or not text.strip():

        return []

    items = []

    for raw_line in text.splitlines():

        line = raw_line.strip()

        if not line or _HEADING_RE.match(line):

            continue

        match = _NUMBERED_ITEM_RE.match(line) or _BULLET_ITEM_RE.match(line)

        if not match:

            continue

        item = match.group(1).strip()

        if not item:

            continue

        if len(item) > MAX_REQUIREMENT_CHARS:

            item = item[:MAX_REQUIREMENT_CHARS].rstrip() + "…"

        if item not in items:

            items.append(item)

        if len(items) >= MAX_REQUIREMENTS:

            break

    return items


# ==========================================================
# STATIC RULES — small, high-confidence, program-agnostic
# ==========================================================

def _finding(rule, severity, message, line=None):
    return {
        "rule": rule,
        "severity": severity,
        "message": message,
        "line": line,
    }


def _call_name(node):
    """The bare name of a Call target: ``eval`` / ``os.system`` / ``self.run``."""

    func = node.func

    if isinstance(func, ast.Name):

        return func.id

    if isinstance(func, ast.Attribute):

        parts = [func.attr]

        base = func.value

        while isinstance(base, ast.Attribute):

            parts.append(base.attr)

            base = base.value

        if isinstance(base, ast.Name):

            parts.append(base.id)

        return ".".join(reversed(parts))

    return ""


def _rule_no_eval_exec(tree):
    """FAIL — ``eval()`` / ``exec()`` execute arbitrary source at runtime."""

    findings = []

    for node in ast.walk(tree):

        if not isinstance(node, ast.Call):

            continue

        if _call_name(node) in ("eval", "exec"):

            findings.append(
                _finding(
                    "no_eval_exec",
                    SEVERITY_FAIL,
                    "eval()/exec() executes arbitrary source at runtime and "
                    "cannot be validated statically",
                    getattr(node, "lineno", None),
                )
            )

    return findings


def _rule_mutable_default(tree):
    """FAIL — a mutable default argument is shared across every call."""

    findings = []

    for node in ast.walk(tree):

        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):

            continue

        for default in list(node.args.defaults) + [
            item for item in node.args.kw_defaults if item is not None
        ]:

            mutable = isinstance(default, (ast.List, ast.Dict, ast.Set))

            if not mutable and isinstance(default, ast.Call):

                mutable = _call_name(default) in ("list", "dict", "set")

            if mutable:

                findings.append(
                    _finding(
                        "mutable_default_argument",
                        SEVERITY_FAIL,
                        "function '%s' uses a mutable default argument; it is "
                        "shared across calls" % node.name,
                        getattr(default, "lineno", getattr(node, "lineno", None)),
                    )
                )

    return findings


def _rule_swallowed_exception(tree):
    """WARN — ``except: pass`` / ``except Exception: return`` hides failures."""

    findings = []

    for node in ast.walk(tree):

        if not isinstance(node, ast.ExceptHandler):

            continue

        body = node.body

        swallows = bool(body) and all(
            isinstance(statement, ast.Pass)
            or (isinstance(statement, ast.Return) and statement.value is None)
            or (isinstance(statement, ast.Continue))
            for statement in body
        )

        if swallows:

            findings.append(
                _finding(
                    "swallowed_exception",
                    SEVERITY_WARN,
                    "exception is caught and discarded; a real failure becomes "
                    "invisible to the user and to tests",
                    getattr(node, "lineno", None),
                )
            )

    return findings


def _rule_round_precision(tree):
    """WARN — ``round(x, N)`` with small N maps tiny nonzero values to zero."""

    findings = []

    for node in ast.walk(tree):

        if not isinstance(node, ast.Call):

            continue

        if _call_name(node) != "round":

            continue

        if len(node.args) < 2:

            continue

        digits = node.args[1]

        if not isinstance(digits, ast.Constant):

            continue

        if not isinstance(digits.value, int) or isinstance(digits.value, bool):

            continue

        if 0 <= digits.value <= 10:

            findings.append(
                _finding(
                    "round_precision_loss",
                    SEVERITY_WARN,
                    "round(x, %d) turns any |x| below 5e-%d into 0.0; small "
                    "nonzero results are silently destroyed"
                    % (digits.value, digits.value + 1),
                    getattr(node, "lineno", None),
                )
            )

    return findings


def _rule_shell_true(tree):
    """WARN — ``subprocess(..., shell=True)`` re-introduces shell parsing."""

    findings = []

    for node in ast.walk(tree):

        if not isinstance(node, ast.Call):

            continue

        name = _call_name(node)

        if not name.startswith("subprocess."):

            continue

        for keyword in node.keywords:

            if keyword.arg == "shell" and isinstance(keyword.value, ast.Constant):
                if keyword.value.value is True:

                    findings.append(
                        _finding(
                            "shell_true",
                            SEVERITY_WARN,
                            "%s(..., shell=True) passes a command string "
                            "through the shell" % name,
                            getattr(node, "lineno", None),
                        )
                    )

    return findings


#: Ordered so reports are stable. Each rule is independent and cheap.
_STATIC_RULES = (
    _rule_no_eval_exec,
    _rule_mutable_default,
    _rule_swallowed_exception,
    _rule_round_precision,
    _rule_shell_true,
)


def review_source(source):
    """Static review of ``source``. Returns findings + a static verdict.

    Never executes or imports the source. A source that does not parse yields
    ``static_review = None`` because static review is meaningless without a
    tree — syntax owns that verdict.
    """

    if not isinstance(source, str) or not source.strip():

        return {"static_review": None, "findings": [], "reason": "empty_source"}

    try:

        tree = ast.parse(source)

    except SyntaxError:

        return {"static_review": None, "findings": [], "reason": "syntax_error"}

    except Exception:

        return {"static_review": None, "findings": [], "reason": "unparseable"}

    findings = []

    for rule in _STATIC_RULES:

        try:

            findings.extend(rule(tree))

        except Exception:

            # A broken rule must never fail the staging contract.
            continue

    if any(item["severity"] == SEVERITY_FAIL for item in findings):

        verdict = STATIC_FAIL

    elif findings:

        verdict = STATIC_WARN

    else:

        verdict = STATIC_PASS

    return {"static_review": verdict, "findings": findings, "reason": None}


# ==========================================================
# QUALITY BLOCK
# ==========================================================

def build_quality_block(source, syntax_valid, syntax_error=None, requirements=None):
    """The three separate verdicts plus the unverified acceptance list.

    ``functional`` is ALWAYS ``NOT_RUN``. It is not a placeholder to be filled
    in later by inference: only an authorized isolated execution may change it,
    and that is Tier 2, which does not exist yet.
    """

    review = review_source(source)

    if syntax_valid is True:

        syntax_verdict = SYNTAX_PASS

    elif syntax_valid is False:

        syntax_verdict = SYNTAX_FAIL

    else:

        syntax_verdict = None

    return {
        "contract": CONTRACT,
        "version": VERSION,
        "syntax": syntax_verdict,
        "syntax_error": syntax_error if syntax_verdict == SYNTAX_FAIL else None,
        "static_review": review["static_review"],
        "functional": FUNCTIONAL_NOT_RUN,
        "findings": review["findings"],
        "unverified_requirements": list(requirements or []),
        "note": (
            "Static review cannot prove behaviour. Functional verification has "
            "NOT been run; no PASS may be inferred from syntax or static "
            "analysis."
        ),
    }


def describe_quality(quality):
    """Short, truthful lines for the user-facing staged reply (Persian)."""

    if not isinstance(quality, dict):

        return []

    lines = []

    syntax = quality.get("syntax")

    if syntax == SYNTAX_PASS:

        lines.append("نحو (syntax): معتبر")

    elif syntax == SYNTAX_FAIL:

        error = quality.get("syntax_error") or {}

        lines.append(
            "نحو (syntax): نامعتبر — %s" % (error.get("message") or "unknown")
        )

    static = quality.get("static_review")

    if static == STATIC_PASS:

        lines.append("بازبینی ایستا (static): بی‌ایراد")

    elif static == STATIC_WARN:

        lines.append("بازبینی ایستا (static): هشدار — موارد زیر را ببینید")

    elif static == STATIC_FAIL:

        lines.append("بازبینی ایستا (static): ایراد قطعی پیدا شد")

    else:

        lines.append("بازبینی ایستا (static): انجام نشد")

    for finding in quality.get("findings") or []:

        lines.append(
            "  • [%s] %s (خط %s)"
            % (
                finding.get("severity"),
                finding.get("message"),
                finding.get("line") if finding.get("line") is not None else "?",
            )
        )

    lines.append(
        "تأیید عملکردی (functional): اجرا نشده (NOT_RUN) — درستی رفتار "
        "برنامه تأیید نشده است و از معتبر بودن نحو نتیجه‌گیری نمی‌شود."
    )

    requirements = quality.get("unverified_requirements") or []

    if requirements:

        lines.append("")
        lines.append("معیارهای تأییدشدهٔ شما (هنوز تأیید نشده‌اند):")

        for index, item in enumerate(requirements, start=1):

            lines.append("  %d. %s" % (index, item))

    return lines
