"""ORIGINAL_IMAGE_EVIDENCE_REUSE_V1 — focused acceptance.

A re-upload of a byte-identical file must reuse the persisted analysis from the
SAME project instead of re-running the vision boundary — and must refuse to
reuse anything it cannot prove is the same content, the same project, and still
compatible.

No model inference runs here: the provider is stubbed unavailable so that any
fall-through is visible as a non-reused result.
"""

import copy
import json
import os

import pytest
from PIL import Image

from core.vision import image_session_v1
from core.vision.image_registry_v1 import image_registry

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ASSETS = os.path.join(
    ROOT, "data", "projects", "project_7b6016d9", "assets.json"
)

ORIGINAL_ID = "img_967f09b9a599"
EMPTY_ID = "img_56432314d057"

SOURCE_SHA256 = (
    "8052c743189202425e37e41bf82b3681d2aebcb155ee2c7d73f585c1cb64c872"
)

SESSION = "reuse_v1_acceptance"


class _NoInference:
    """The real provider's IDENTITY, without any inference.

    The compatibility rule compares `vision_cache_identity`; a stub with a
    different identity would (correctly) be treated as a changed vision
    configuration and refuse reuse, so the identity must be the real one. Only
    the generation call is neutralised.
    """

    def __init__(self, identity, name, model):
        self._identity = identity
        self.name = name
        self.model = model
        self.endpoint = "stub"

    def is_available(self):
        return True

    def analyze(self, payload):
        # An empty, unstructured response — never a model call.
        return ""

    def cache_identity(self):
        return self._identity


@pytest.fixture(autouse=True)
def isolated(monkeypatch):

    real = image_session_v1.provider()

    identity = getattr(real, "cache_identity", None)

    identity = identity() if callable(identity) else {
        "provider": getattr(real, "name", "unknown"),
        "model": getattr(real, "model", "unknown"),
        "adapter": "legacy-provider-v1",
    }

    stub = _NoInference(
        identity, getattr(real, "name", "unknown"), getattr(real, "model", "unknown")
    )

    monkeypatch.setattr(
        image_session_v1, "provider", lambda: stub, raising=False
    )

    # The local plan reader runs OCR over the full-resolution JPEG; a test that
    # falls through must not spend minutes doing it. The reuse decision is made
    # BEFORE this is reached, so stubbing it cannot mask a reuse failure.
    monkeypatch.setattr(
        image_session_v1,
        "read_local_plan",
        lambda path: {
            "contract": "LocalPlanReadingV1",
            "status": "unavailable",
            "provider_independent": True,
            "labels": [],
            "openings": [],
            "reason": "stubbed_for_test",
        },
        raising=False,
    )

    image_registry.reset(SESSION)

    yield

    image_registry.reset(SESSION)


@pytest.fixture(scope="module")
def records():

    if not os.path.isfile(ASSETS):
        pytest.skip("persisted project analysis is not present")

    with open(ASSETS, encoding="utf-8") as handle:
        payload = json.load(handle)

    found = {
        record["image_id"]: record
        for record in payload.get("registry_records") or []
    }

    if ORIGINAL_ID not in found or EMPTY_ID not in found:
        pytest.skip("the two source records are not present")

    return found


def _seed(session, records, *, analysis=True, pipeline=None):
    """Register the analysed original and return its record."""

    source = records[ORIGINAL_ID]
    stored = copy.deepcopy(source["analysis"])

    if pipeline is not None:
        stored["evidence_pipeline"] = pipeline

    return image_registry.register(
        session,
        path=source["path"],
        source_type="uploaded",
        analysis=stored if analysis else None,
        analysis_status=source["analysis_status"] if analysis else "pending",
        make_active=False,
    )


def _upload(session, records, path=None, source_type="uploaded"):
    """Register the re-uploaded file."""

    return image_registry.register(
        session,
        path=path or records[EMPTY_ID]["path"],
        source_type=source_type,
        make_active=True,
    )


# ==========================================================
# A — same JPEG, same project, compatible analysis: reused
# ==========================================================

def test_A_identical_content_in_the_same_project_is_reused(records):

    _seed(SESSION, records)

    record = _upload(SESSION, records)

    result = image_session_v1.analyze_record(SESSION, record["image_id"])

    assert result.get("reused_from_image_id")
    assert result.get("reuse_reason") == "identical_content_same_project"
    assert result.get("source_hash") == SOURCE_SHA256

    elements = (result.get("element_evidence") or {}).get("elements") or []

    assert len(elements) == 18


def test_A_the_reused_analysis_is_persisted_on_the_new_record(records):

    _seed(SESSION, records)

    record = _upload(SESSION, records)

    image_session_v1.analyze_record(SESSION, record["image_id"])

    stored = image_registry.get(SESSION, record["image_id"])

    assert stored.get("analysis")
    assert stored.get("analysis_status") == "ANALYZED_WITH_UNCERTAINTY"


# ==========================================================
# B — different project: never reused
# ==========================================================

def test_B_an_identical_file_in_another_project_is_not_reused(records):

    _seed(SESSION, records)

    other = "reuse_v1_other_project"

    image_registry.reset(other)

    try:

        record = _upload(other, records)

        result = image_session_v1.analyze_record(other, record["image_id"])

        assert not result.get("reused_from_image_id")

    finally:

        image_registry.reset(other)


# ==========================================================
# C — different bytes: never reused
# ==========================================================

def test_C_a_different_image_is_not_reused(records, tmp_path):

    _seed(SESSION, records)

    different = tmp_path / "different.png"
    Image.new("RGB", (64, 64), (10, 20, 30)).save(different)

    record = _upload(SESSION, records, path=str(different))

    result = image_session_v1.analyze_record(SESSION, record["image_id"])

    assert not result.get("reused_from_image_id")


# ==========================================================
# D — stale / incompatible analysis: never reused silently
# ==========================================================

def test_D_a_stale_analysis_is_not_reused(records):

    _seed(SESSION, records, pipeline="some-older-pipeline-v0")

    record = _upload(SESSION, records)

    result = image_session_v1.analyze_record(SESSION, record["image_id"])

    assert not result.get("reused_from_image_id")


def test_D_a_record_without_an_analysis_is_not_a_source(records):

    _seed(SESSION, records, analysis=False)

    record = _upload(SESSION, records)

    result = image_session_v1.analyze_record(SESSION, record["image_id"])

    assert not result.get("reused_from_image_id")


# ==========================================================
# E — explicit re-analysis bypasses reuse
# ==========================================================

def test_E_force_reanalysis_does_not_reuse(records):

    _seed(SESSION, records)

    record = _upload(SESSION, records)

    result = image_session_v1.analyze_record(
        SESSION, record["image_id"], force=True
    )

    assert not result.get("reused_from_image_id")


# ==========================================================
# F — source type must match
# ==========================================================

def test_F_a_generated_image_does_not_borrow_an_uploaded_analysis(records):

    _seed(SESSION, records)

    record = _upload(SESSION, records, source_type="image_to_image")

    result = image_session_v1.analyze_record(SESSION, record["image_id"])

    assert not result.get("reused_from_image_id")


# ==========================================================
# G — provenance and uncertainty survive untouched
# ==========================================================

def test_G_provenance_and_uncertainty_are_preserved(records):

    _seed(SESSION, records)

    record = _upload(SESSION, records)

    result = image_session_v1.analyze_record(SESSION, record["image_id"])

    source = records[ORIGINAL_ID]["analysis"]

    assert result.get("provider") == source.get("provider")
    assert result.get("model") == source.get("model")
    assert result.get("analysis_status") == source.get("analysis_status")
    assert result.get("confidence") == source.get("confidence")
    assert result.get("unresolved") == source.get("unresolved")
    assert result.get("evidence_pipeline") == source.get("evidence_pipeline")


def test_G_the_status_is_never_promoted(records):

    _seed(SESSION, records)

    record = _upload(SESSION, records)

    result = image_session_v1.analyze_record(SESSION, record["image_id"])

    assert result.get("analysis_status") != "ANALYZED"


def test_G_image_type_is_not_rewritten(records):

    _seed(SESSION, records)

    record = _upload(SESSION, records)

    result = image_session_v1.analyze_record(SESSION, record["image_id"])

    assert result.get("image_type") == records[ORIGINAL_ID]["analysis"].get(
        "image_type"
    )


def test_G_no_pixel_verified_claim_is_invented(records):

    _seed(SESSION, records)

    record = _upload(SESSION, records)

    result = image_session_v1.analyze_record(SESSION, record["image_id"])

    elements = (result.get("element_evidence") or {}).get("elements") or []

    assert not any(
        item.get("evidence_class") == "PIXEL_VERIFIED" for item in elements
    )


def test_G_the_analysis_names_its_own_record(records):

    _seed(SESSION, records)

    record = _upload(SESSION, records)

    result = image_session_v1.analyze_record(SESSION, record["image_id"])

    assert result.get("image_id") == record["image_id"]
    assert result.get("reused_from_image_id") != record["image_id"]


# ==========================================================
# H — the guard still refuses when there is nothing to reuse
# ==========================================================

def test_H_no_reuse_means_no_evidence(records):

    """With no sibling, the unavailable provider leaves no elements — which is
    exactly the state the architectural evidence guard must refuse."""

    record = _upload(SESSION, records)

    result = image_session_v1.analyze_record(SESSION, record["image_id"])

    elements = (result.get("element_evidence") or {}).get("elements") or []

    assert elements == []
    assert not result.get("reused_from_image_id")
