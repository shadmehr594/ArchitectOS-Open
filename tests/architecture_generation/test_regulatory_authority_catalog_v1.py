import hashlib
import json
import pytest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "core/architecture/contracts/parcel2_occupancy_research_authority_v1.json"
MINAB_PDF = ROOT / "core/architecture/authorities/minab/minab_detailed_plan_volume_4_regulations_spring_1400.pdf"

pytestmark = pytest.mark.skipif(
    not MINAB_PDF.is_file(),
    reason=(
        "Local regulatory PDF is not bundled with the public repository. "
        "Supply it locally under core/architecture/authorities/local/ to run this authority check."
    ),
)


def test_canonical_minab_reference_matches_registry_hash_and_size():
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    record = next(x for x in registry["records"] if x.get("document_title_fa") == "طرح تفصیلی شهر میناب، جلد 4، ضوابط و مقررات")
    data = MINAB_PDF.read_bytes()
    assert record["canonical_path"] == str(MINAB_PDF.relative_to(ROOT)).replace("\\", "/")
    assert len(data) == record["byte_size"] == 6890828
    assert hashlib.sha256(data).hexdigest().upper() == record["sha256"]


def test_minab_and_national_sources_are_mandatory_but_fail_closed():
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    assert registry["mandatory_authority_families"] == [
        "Iran National Building Regulations", "Minab Detailed Plan Volume 4 Regulations Spring 1400"]
    policy = registry["resolution_policy"]
    assert policy["both_authority_families_must_be_checked"] is True
    assert policy["clause_and_page_required"] is True
    assert policy["parcel_applicability_required"] is True
    assert policy["conflicts_fail_closed"] is True
    minab = next(x for x in registry["records"] if x.get("document_title_fa"))
    assert minab["final_approval_status"].startswith("unresolved")
    assert minab["applicability_to_parcel_2"].startswith("unresolved")
