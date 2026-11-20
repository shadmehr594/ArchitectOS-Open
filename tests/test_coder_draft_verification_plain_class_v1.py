"""
test_coder_draft_verification_plain_class_v1.py

Focused acceptance for the plain-class scenario pack and shape-aware selection.

Does NOT run Docker, execute user drafts, or touch the live staging store.
Uses child-process harness runs with a known-safe fixture.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import textwrap

import pytest

from core.execution import draft_verification_v1 as dv


# ==========================================================
# FIXTURE: a plain Calculator class (no Tkinter)
# ==========================================================

CALCULATOR_SOURCE = textwrap.dedent(
    r"""
    class Calculator:
        def __init__(self):
            self.operand1 = 0
            self.operand2 = 0
            self.operator = ""
            self.result = 0
            self.errors = []

        def on_digit(self, digit):
            if self.operator:
                self.operand2 = self.operand2 * 10 + int(digit)
            else:
                self.operand1 = self.operand1 * 10 + int(digit)

        def on_operator(self, op):
            self.operator = op

        def on_equals(self):
            if self.operator == "+":
                self.result = self.operand1 + self.operand2
            elif self.operator == "*":
                self.result = self.operand1 * self.operand2
            else:
                self.result = self.operand1

        def display_value(self):
            return str(self.result)
    """
).strip()


def _build_harness(source: str, scenarios: list, digest: str | None = None):
    """Assemble a runnable harness string from the module template."""
    app_sha256 = digest or hashlib.sha256(source.encode("utf-8")).hexdigest()
    return (
        dv._HARNESS_TEMPLATE
        .replace("__APP_SOURCE__", json.dumps(source, ensure_ascii=False))
        .replace("__APP_SHA256__", json.dumps(app_sha256))
        .replace("__SCENARIOS__", json.dumps(scenarios, ensure_ascii=False))
    )


def _run_harness(source: str, scenarios: list, digest: str | None = None, tmp_path=None):
    """Run the harness in a child Python process; return parsed payload."""
    harness = _build_harness(source, scenarios, digest)
    if tmp_path is not None:
        draft_path = tmp_path / "trusted_fixture.py"
        harness = harness.replace(
            'path = "/tmp/architectos_draft.py"',
            "path = " + repr(str(draft_path)),
        )
    proc = subprocess.run(
        [sys.executable, "-c", harness],
        cwd=str(tmp_path) if tmp_path else None,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            "Harness died: rc=%d\nstdout=%r\nstderr=%r"
            % (proc.returncode, proc.stdout, proc.stderr)
        )
    payload, reason = dv.parse_harness_output(proc.stdout, proc.stderr)
    if reason is not None:
        raise RuntimeError("Harness parse reason: %s" % reason)
    return payload


# ==========================================================
# Tests: shape detection
# ==========================================================

class TestImportsTkinter:
    def test_detects_tkinter_import(self) -> None:
        assert dv._imports_tkinter("import tkinter\n") is True

    def test_detects_tkinter_from_import(self) -> None:
        assert dv._imports_tkinter("from tkinter import Tk\n") is True

    def test_detects_tkinter_submodule(self) -> None:
        assert dv._imports_tkinter("import tkinter.ttk\n") is True

    def test_rejects_plain_class(self) -> None:
        assert dv._imports_tkinter(CALCULATOR_SOURCE) is False

    def test_tolerates_unparseable(self) -> None:
        # Keeps the established Tk pack for safety
        assert dv._imports_tkinter("class X (\n") is True


class TestScenarioSelection:
    def test_tkinter_program_gets_default_pack(self) -> None:
        pack = dv.scenarios_for_source("import tkinter\n")
        assert isinstance(pack, list)
        assert len(pack) == 16
        names = {s["name"] for s in pack}
        assert "arithmetic_add" in names

    def test_plain_class_gets_plain_pack(self) -> None:
        pack = dv.scenarios_for_source(CALCULATOR_SOURCE)
        assert isinstance(pack, list)
        assert len(pack) == 5
        names = [s["name"] for s in pack]
        assert names == [
            "plain_instantiate",
            "plain_digit_sets_operand1",
            "plain_operator_keeps_operand1",
            "plain_operator_change_keeps_operand1",
            "plain_digit_sets_operand2",
        ]

    def test_project_reader_passed_through(self) -> None:
        def fake_reader(pid):
            return {"content": CALCULATOR_SOURCE}

        pack = dv.scenarios_for_project("p1", staging_reader=fake_reader)
        assert len(pack) == 5
        assert pack[1]["name"] == "plain_digit_sets_operand1"


# ==========================================================
# Tests: harness actions for plain class
# ==========================================================

class TestPlainClassHarnessActions:
    def test_plain_instantiate(self, tmp_path) -> None:
        payload = _run_harness(CALCULATOR_SOURCE, [
            {"name": "plain_instantiate", "steps": []}
        ], tmp_path=tmp_path)
        assert payload["ok"] is True
        assert payload["app_sha256"] == hashlib.sha256(CALCULATOR_SOURCE.encode("utf-8")).hexdigest()
        assert payload["scenarios"][0]["status"] == "PASS"

    def test_digit_sets_operand1(self, tmp_path) -> None:
        payload = _run_harness(CALCULATOR_SOURCE, [
            {
                "name": "plain_digit_sets_operand1",
                "steps": [
                    {"action": "call", "method": "on_digit", "args": [5]},
                    {"action": "expect_attr", "name": "operand1", "value": 5},
                ],
            }
        ], tmp_path=tmp_path)
        assert payload["scenarios"][0]["status"] == "PASS"

    def test_operator_keeps_operand1(self, tmp_path) -> None:
        payload = _run_harness(CALCULATOR_SOURCE, [
            {
                "name": "plain_operator_keeps_operand1",
                "steps": [
                    {"action": "call", "method": "on_digit", "args": [5]},
                    {"action": "call", "method": "on_operator", "args": ["+"]},
                    {"action": "expect_attr", "name": "operand1", "value": 5},
                ],
            }
        ], tmp_path=tmp_path)
        assert payload["scenarios"][0]["status"] == "PASS"

    def test_operator_change_keeps_operand1_and_sets_operator(self, tmp_path) -> None:
        payload = _run_harness(CALCULATOR_SOURCE, [
            {
                "name": "plain_operator_change_keeps_operand1",
                "steps": [
                    {"action": "call", "method": "on_digit", "args": [5]},
                    {"action": "call", "method": "on_operator", "args": ["+"]},
                    {"action": "call", "method": "on_operator", "args": ["*"]},
                    {"action": "expect_attr", "name": "operand1", "value": 5},
                    {"action": "expect_attr", "name": "operator", "value": "*"},
                ],
            }
        ], tmp_path=tmp_path)
        r = payload["scenarios"][0]
        assert r["status"] == "PASS"

    def test_digit_sets_operand2(self, tmp_path) -> None:
        payload = _run_harness(CALCULATOR_SOURCE, [
            {
                "name": "plain_digit_sets_operand2",
                "steps": [
                    {"action": "call", "method": "on_digit", "args": [5]},
                    {"action": "call", "method": "on_operator", "args": ["+"]},
                    {"action": "call", "method": "on_digit", "args": [2]},
                    {"action": "expect_attr", "name": "operand2", "value": 2},
                ],
            }
        ], tmp_path=tmp_path)
        assert payload["scenarios"][0]["status"] == "PASS"

    def test_attribute_mismatch_fails(self, tmp_path) -> None:
        payload = _run_harness(CALCULATOR_SOURCE, [
            {
                "name": "plain_wrong_expectation",
                "steps": [
                    {"action": "call", "method": "on_digit", "args": [5]},
                    {"action": "expect_attr", "name": "operand1", "value": 99},
                ],
            }
        ], tmp_path=tmp_path)
        r = payload["scenarios"][0]
        assert r["status"] == "FAIL"
        assert "attribute mismatch" in r["detail"]
        assert r["expected"] == 99
        assert r["actual"] == 5

    def test_missing_method_is_not_supported(self, tmp_path) -> None:
        payload = _run_harness(CALCULATOR_SOURCE, [
            {
                "name": "plain_missing_method",
                "steps": [
                    {"action": "call", "method": "on_clear", "args": []},
                ],
            }
        ], tmp_path=tmp_path)
        r = payload["scenarios"][0]
        assert r["status"] == "NOT_SUPPORTED"
        assert "method_not_found:on_clear" in r["detail"]

    def test_missing_attribute_is_not_supported(self, tmp_path) -> None:
        payload = _run_harness(CALCULATOR_SOURCE, [
            {
                "name": "plain_missing_attribute",
                "steps": [
                    {"action": "expect_attr", "name": "nonexistent", "value": 0},
                ],
            }
        ], tmp_path=tmp_path)
        r = payload["scenarios"][0]
        assert r["status"] == "NOT_SUPPORTED"
        assert "attribute_not_found:nonexistent" in r["detail"]


# ==========================================================
# Tests: full plain-class scenario pack end-to-end in harness
# ==========================================================

class TestPlainClassScenarioPack:
    def test_all_five_scenarios_pass(self, tmp_path) -> None:
        scenarios = dv.plain_class_scenarios()
        payload = _run_harness(CALCULATOR_SOURCE, scenarios, tmp_path=tmp_path)
        assert payload["ok"] is True
        for r in payload["scenarios"]:
            assert r["status"] == "PASS", (
                "scenario %s failed: %s" % (r["name"], r.get("detail"))
            )

    def test_digest_mismatch_is_rejected(self, tmp_path) -> None:
        scenarios = dv.plain_class_scenarios()
        harness = _build_harness(CALCULATOR_SOURCE, scenarios, digest="a" * 64)
        draft_path = tmp_path / "trusted_fixture.py"
        harness = harness.replace(
            'path = "/tmp/architectos_draft.py"',
            "path = " + repr(str(draft_path)),
        )
        proc = subprocess.run(
            [sys.executable, "-c", harness],
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert proc.returncode == 0
        payload, reason = dv.parse_harness_output(proc.stdout, proc.stderr)
        assert payload is not None
        assert payload["ok"] is False
        assert payload["reason"] == "staged_source_digest_mismatch"
