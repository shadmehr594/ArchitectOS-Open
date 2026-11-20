# tests/test_coder_quality_gate_tier1_v1.py
"""CODER QUALITY GATE — Tier 1 (static only, no execution).

The failure this prevents: a staged draft was described as «آماده شد» with
«نحو (syntax): معتبر», which reads as "the application works". Measured on the
real candidate ``cb6772f0…``: syntax VALID, yet the C button appended the
letter "C", ``5 + × 2 =`` produced 7, and Numpad did nothing.

Tier 1 therefore reports THREE separate verdicts:

  syntax          PASS / FAIL          (parsing only)
  static_review   PASS / WARN / FAIL   (a few PROVABLE source defects)
  functional      NOT_RUN              (never inferred; needs authorized Tier 2)

Fixtures are the REAL model outputs, not synthetic look-alikes.
"""
from __future__ import annotations

import ast
import hashlib
import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import pytest

from core.chat.code_quality_review_v1 import (
    FUNCTIONAL_NOT_RUN,
    STATIC_FAIL,
    STATIC_PASS,
    STATIC_WARN,
    build_quality_block,
    describe_quality,
    extract_acceptance_requirements,
    review_source,
)

_FIXTURES = os.path.join(_PROJECT_ROOT, "tests", "fixtures", "coder_quality")


def _fixture(name: str) -> str:
    with open(os.path.join(_FIXTURES, name), encoding="utf-8") as handle:
        return handle.read()


@pytest.fixture(scope="module")
def real_b76a4003() -> str:
    return _fixture("real_defective_b76a4003.py")


@pytest.fixture(scope="module")
def real_cb6772f0() -> str:
    return _fixture("real_defective_cb6772f0.py")


@pytest.fixture(scope="module")
def clean_control() -> str:
    return _fixture("clean_control.py")


@pytest.fixture(scope="module")
def real_request() -> str:
    return _fixture("real_request_cb6772f0.txt")


# ---------------------------------------------------------------------------
# 1. The fixtures really are the model's bytes
# ---------------------------------------------------------------------------

class TestFixtureIntegrity:

    def test_real_candidate_digest_is_preserved(self, real_cb6772f0) -> None:
        digest = hashlib.sha256(real_cb6772f0.rstrip("\n").encode()).hexdigest()
        assert digest == (
            "cb6772f04214a87734c970ba5d7a641c0ef70c3b708144bbb3e7fbeef059c633"
        )

    def test_earlier_candidate_digest_is_preserved(self, real_b76a4003) -> None:
        digest = hashlib.sha256(real_b76a4003.rstrip("\n").encode()).hexdigest()
        assert digest.startswith("b76a4003")

    def test_both_candidates_are_syntactically_valid(self, real_cb6772f0, real_b76a4003) -> None:
        """The whole point: valid syntax says nothing about behaviour."""
        ast.parse(real_cb6772f0)
        ast.parse(real_b76a4003)


# ---------------------------------------------------------------------------
# 2. Real-defect detection
# ---------------------------------------------------------------------------

class TestRealDefectDetection:

    def test_latest_candidate_is_flagged_for_rounding(self, real_cb6772f0) -> None:
        review = review_source(real_cb6772f0)
        assert review["static_review"] == STATIC_WARN
        rules = [item["rule"] for item in review["findings"]]
        assert "round_precision_loss" in rules

    def test_rounding_finding_points_at_the_real_line(self, real_cb6772f0) -> None:
        review = review_source(real_cb6772f0)
        finding = next(
            item for item in review["findings"]
            if item["rule"] == "round_precision_loss"
        )
        assert finding["severity"] == "WARN"
        assert finding["line"] == 129
        assert "round(x, 10)" in finding["message"]

    def test_earlier_candidate_produces_no_definite_failure(self, real_b76a4003) -> None:
        """It has real defects, but none that are statically PROVABLE — the gate
        must not invent one (that would be a false positive)."""
        review = review_source(real_b76a4003)
        assert review["static_review"] in (STATIC_PASS, STATIC_WARN)
        assert all(item["severity"] != "FAIL" for item in review["findings"])


# ---------------------------------------------------------------------------
# 3. False-positive safeguards
# ---------------------------------------------------------------------------

class TestFalsePositiveSafeguards:

    def test_clean_control_produces_no_findings(self, clean_control) -> None:
        review = review_source(clean_control)
        assert review["static_review"] == STATIC_PASS
        assert review["findings"] == []

    def test_empty_source_is_not_reviewed(self) -> None:
        review = review_source("   ")
        assert review["static_review"] is None
        assert review["reason"] == "empty_source"

    def test_unparseable_source_does_not_raise(self) -> None:
        review = review_source("def broken(:\n")
        assert review["static_review"] is None
        assert review["reason"] == "syntax_error"

    def test_round_with_many_digits_is_not_flagged(self) -> None:
        """round(x, 12) is not a precision hazard for ordinary magnitudes."""
        review = review_source("value = round(1.234, 12)\n")
        assert review["findings"] == []

    def test_shell_false_is_not_flagged(self) -> None:
        source = "import subprocess\nsubprocess.run(['ls'], shell=False)\n"
        assert review_source(source)["findings"] == []


# ---------------------------------------------------------------------------
# 4. The rules that produce definite FAIL
# ---------------------------------------------------------------------------

class TestDefiniteFailures:

    def test_eval_is_a_definite_failure(self) -> None:
        review = review_source("result = eval(user_text)\n")
        assert review["static_review"] == STATIC_FAIL
        assert review["findings"][0]["rule"] == "no_eval_exec"
        assert review["findings"][0]["severity"] == "FAIL"

    def test_exec_is_a_definite_failure(self) -> None:
        review = review_source("exec(payload)\n")
        assert review["static_review"] == STATIC_FAIL

    def test_mutable_default_is_a_definite_failure(self) -> None:
        review = review_source("def collect(item, bucket=[]):\n    bucket.append(item)\n")
        assert review["static_review"] == STATIC_FAIL
        assert review["findings"][0]["rule"] == "mutable_default_argument"

    def test_swallowed_exception_is_only_a_warning(self) -> None:
        """A heuristic concern must never be reported as a definite defect."""
        source = "def f():\n    try:\n        work()\n    except Exception:\n        pass\n"
        review = review_source(source)
        assert review["static_review"] == STATIC_WARN
        assert review["findings"][0]["severity"] == "WARN"

    def test_shell_true_is_only_a_warning(self) -> None:
        source = "import subprocess\nsubprocess.run('ls', shell=True)\n"
        review = review_source(source)
        assert review["static_review"] == STATIC_WARN


# ---------------------------------------------------------------------------
# 5. Functional verification can never be inferred
# ---------------------------------------------------------------------------

class TestFunctionalNeverInferred:

    @pytest.mark.parametrize(
        "fixture_name",
        ["real_defective_b76a4003.py", "real_defective_cb6772f0.py", "clean_control.py"],
    )
    def test_functional_is_always_not_run(self, fixture_name) -> None:
        source = _fixture(fixture_name)
        quality = build_quality_block(source, True, None, [])
        assert quality["functional"] == FUNCTIONAL_NOT_RUN
        assert quality["functional"] != "PASS"

    def test_static_pass_never_becomes_functional_pass(self, clean_control) -> None:
        quality = build_quality_block(clean_control, True, None, [])
        assert quality["static_review"] == STATIC_PASS
        assert quality["syntax"] == "PASS"
        assert quality["functional"] == FUNCTIONAL_NOT_RUN

    def test_syntax_failure_is_reported_separately(self) -> None:
        quality = build_quality_block("def broken(:\n", False, {"message": "boom"}, [])
        assert quality["syntax"] == "FAIL"
        assert quality["syntax_error"]["message"] == "boom"
        assert quality["functional"] == FUNCTIONAL_NOT_RUN

    def test_quality_block_states_the_limitation(self, clean_control) -> None:
        quality = build_quality_block(clean_control, True, None, [])
        assert "NOT been run" in quality["note"]


# ---------------------------------------------------------------------------
# 6. Acceptance criteria are echoed, never scored
# ---------------------------------------------------------------------------

class TestRequirementEcho:

    def test_real_request_yields_its_own_criteria(self, real_request) -> None:
        items = extract_acceptance_requirements(real_request)
        assert len(items) >= 5

    def test_scenarios_are_preserved_verbatim(self, real_request) -> None:
        items = extract_acceptance_requirements(real_request)
        joined = "\n".join(items)
        # The user's own acceptance examples must survive unchanged.
        assert "5 + 2 = 7" in joined
        assert "2 + 3 × 4 = 20" in joined
        assert "5 + × 2 = 10" in joined

    def test_no_pass_fail_is_attached_to_a_requirement(self, real_request) -> None:
        items = extract_acceptance_requirements(real_request)
        for item in items:
            assert "PASS" not in item
            assert "FAIL" not in item

    def test_plain_prose_yields_nothing(self) -> None:
        assert extract_acceptance_requirements("یک ویلای دو طبقه بساز") == []

    def test_requirements_are_capped(self) -> None:
        text = "\n".join("%d. item %d" % (i, i) for i in range(1, 60))
        assert len(extract_acceptance_requirements(text)) <= 20


# ---------------------------------------------------------------------------
# 7. Staging integration — annotations never rewrite the source
# ---------------------------------------------------------------------------

class TestStagingIntegration:

    def test_quality_is_attached_without_rewriting_bytes(
        self, tmp_path, monkeypatch, real_cb6772f0, real_request
    ) -> None:
        from core.chat import code_file_staging_v1 as staging
        from core.project.project_workspace_v1 import project_workspace

        documents = tmp_path / "documents"
        documents.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(
            project_workspace, "subdir", lambda project_id, name: str(documents)
        )
        staging.reset_staging()

        try:
            proposal = staging.stage_code_file(
                project_id="project_quality_gate",
                filename="app.py",
                content=real_cb6772f0,
                documents_root=str(documents),
                origin="coder_model",
                requirements=extract_acceptance_requirements(real_request),
            )

            assert proposal["status"] == "awaiting_approval"

            # Byte-exact preservation: review is annotation only.
            assert proposal["content"] == real_cb6772f0
            assert proposal["digest"] == hashlib.sha256(
                real_cb6772f0.encode("utf-8")
            ).hexdigest()

            quality = proposal["quality"]
            assert quality["syntax"] == "PASS"
            assert quality["static_review"] == STATIC_WARN
            assert quality["functional"] == FUNCTIONAL_NOT_RUN
            assert len(quality["unverified_requirements"]) >= 5

            # Staging still never writes.
            assert proposal["writes_performed"] == 0
            assert not (documents / "code" / "app.py").exists()
        finally:
            staging.reset_staging()

    def test_staging_without_requirements_still_reports_not_run(
        self, tmp_path, monkeypatch, clean_control
    ) -> None:
        from core.chat import code_file_staging_v1 as staging
        from core.project.project_workspace_v1 import project_workspace

        documents = tmp_path / "documents"
        documents.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(
            project_workspace, "subdir", lambda project_id, name: str(documents)
        )
        staging.reset_staging()

        try:
            proposal = staging.stage_code_file(
                project_id="project_quality_gate2",
                filename="app.py",
                content=clean_control,
                documents_root=str(documents),
                origin="coder_model",
            )
            assert proposal["quality"]["functional"] == FUNCTIONAL_NOT_RUN
            assert proposal["quality"]["unverified_requirements"] == []
        finally:
            staging.reset_staging()


# ---------------------------------------------------------------------------
# 8. The user-facing reply states the limitation
# ---------------------------------------------------------------------------

class TestReplyHonesty:

    def test_reply_lines_include_not_run(self, real_cb6772f0, real_request) -> None:
        quality = build_quality_block(
            real_cb6772f0, True, None, extract_acceptance_requirements(real_request)
        )
        lines = "\n".join(describe_quality(quality))
        assert "NOT_RUN" in lines
        assert "اجرا نشده" in lines
        # The static warning and the requirement echo are both visible.
        assert "بازبینی ایستا" in lines
        assert "معیارهای تأییدشدهٔ شما" in lines

    def test_static_pass_still_reports_not_run(self, clean_control) -> None:
        quality = build_quality_block(clean_control, True, None, [])
        lines = "\n".join(describe_quality(quality))
        assert "بی‌ایراد" in lines
        assert "NOT_RUN" in lines

    def test_no_claim_of_functional_success(self, clean_control) -> None:
        quality = build_quality_block(clean_control, True, None, [])
        lines = "\n".join(describe_quality(quality))
        for forbidden in ("تأیید عملکردی (functional): تأیید شد", "functionally ready"):
            assert forbidden not in lines


# ---------------------------------------------------------------------------
# 9. Tier 1 must not touch execution, saving or the model
# ---------------------------------------------------------------------------

class TestScopeGuard:

    def test_module_imports_only_the_standard_parser(self) -> None:
        """Tier 1 must stay static: AST + regex, nothing that can execute."""
        tree = ast.parse(_fixture_module_source())

        imported = set()

        for node in ast.walk(tree):

            if isinstance(node, ast.Import):

                imported.update(alias.name.split(".")[0] for alias in node.names)

            elif isinstance(node, ast.ImportFrom):

                if node.module:

                    imported.add(node.module.split(".")[0])

        assert imported <= {"ast", "re", "__future__"}, (
            "unexpected imports in the static reviewer: %s" % sorted(imported)
        )

    def test_module_calls_no_execution_or_write_helper(self) -> None:
        tree = ast.parse(_fixture_module_source())

        called = set()

        for node in ast.walk(tree):

            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):

                called.add(node.func.id)

        for forbidden in (
            "eval",
            "exec",
            "compile",
            "__import__",
            "approve_staged_file",
            "create_project_code_file",
            "stage_code_file",
        ):

            assert forbidden not in called, (
                "Tier 1 must not call %r" % forbidden
            )

    def test_review_does_not_mutate_the_source_string(self, real_cb6772f0) -> None:
        before = hashlib.sha256(real_cb6772f0.encode()).hexdigest()
        review_source(real_cb6772f0)
        build_quality_block(real_cb6772f0, True, None, ["x"])
        after = hashlib.sha256(real_cb6772f0.encode()).hexdigest()
        assert before == after


def _fixture_module_source() -> str:
    path = os.path.join(
        _PROJECT_ROOT, "core", "chat", "code_quality_review_v1.py"
    )
    with open(path, encoding="utf-8") as handle:
        return handle.read()


# ---------------------------------------------------------------------------
# 10. The ASSEMBLED reply — the contract the user actually reads
# ---------------------------------------------------------------------------

class TestAssembledReply:

    def test_staged_reply_never_claims_functional_readiness(
        self, tmp_path, monkeypatch, real_cb6772f0, real_request
    ) -> None:
        from core.chat.chat_architect import ChatArchitect
        from core.chat import code_file_staging_v1 as staging
        from core.project.project_workspace_v1 import project_workspace

        session = "project_quality_reply"
        documents = tmp_path / "documents"
        documents.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(
            project_workspace, "subdir", lambda project_id, name: str(documents)
        )
        staging.reset_staging()

        chat = object.__new__(ChatArchitect)
        chat.context = {
            "trusted_local_authorization": {
                "trusted": True,
                "actor_id": "local_user",
                "session_id": "sess_quality",
                "project_id": session,
            }
        }
        chat._generate_code_with_coder = (
            lambda text: real_cb6772f0
        )

        try:
            message = chat._authorized_code_file_creation(real_request, session)

            assert isinstance(message, str) and message

            # The three verdicts are visible.
            assert "نحو (syntax): معتبر" in message
            assert "بازبینی ایستا" in message
            assert "NOT_RUN" in message

            # The user's own criteria are echoed as UNVERIFIED.
            assert "معیارهای تأییدشدهٔ شما" in message

            # The old wording that read as "the app works" must be gone.
            assert "آماده شد" not in message

            # Integrity: the staged bytes are unchanged by the review.
            pending = staging.pending_proposal(session)
            assert pending["content"] == real_cb6772f0
            assert pending["digest"] == hashlib.sha256(
                real_cb6772f0.encode("utf-8")
            ).hexdigest()
            assert not (documents / "code" / "app.py").exists()
        finally:
            staging.reset_staging()
