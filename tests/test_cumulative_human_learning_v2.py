import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"core/architecture/learning"))
from cumulative_human_learning_v2 import *

def c(): return fresh_candidate_03()
def test_01_bath_court_fails():
    x=c(); x["connections"]=[e for e in x["connections"] if "court" not in (e["a"],e["b"])]+[{"a":"family_bath","b":"court","type":"DOOR"}]; assert "COURTYARD_ACCESS_THROUGH_WET_SPACE" in validate(x)["failure_codes"]
def test_02_wc_court_fails():
    x=c(); x["connections"]=[e for e in x["connections"] if "court" not in (e["a"],e["b"])]+[{"a":"guest_wc","b":"court","type":"DOOR"}]; assert "COURTYARD_ACCESS_THROUGH_WET_SPACE" in validate(x)["failure_codes"]
def test_03_bed_court_fails():
    x=c(); x["connections"]=[e for e in x["connections"] if "court" not in (e["a"],e["b"])]+[{"a":"master","b":"court","type":"DOOR"}]; assert "COURTYARD_ACCESS_THROUGH_PRIVATE_DESTINATION" in validate(x)["failure_codes"]
def test_04_neutral_court_passes(): assert validate(c())["checks"]["courtyard_from_neutral"]
def test_05_court_area_fails():
    x=c(); next(r for r in x["rooms"] if r["id"]=="court")["area_m2"]=11.99; assert "HABITABLE_COURTYARD_AREA_BELOW_12M2" in validate(x)["failure_codes"]
def test_06_court_width_fails():
    x=c(); r=next(r for r in x["rooms"] if r["id"]=="court"); r["bbox"]=[4.7,16.2,7.69,20.22]; r["area_m2"]=12.0198; assert "HABITABLE_COURTYARD_WIDTH_BELOW_3M" in validate(x)["failure_codes"]
def test_07_guest_wc_public_transition(): assert validate(c())["checks"]["guest_wc_without_sleeping_zone"]
def test_08_family_bath_private_hall(): assert validate(c())["checks"]["family_bath_from_private_hall"]
def test_09_bath_not_passage(): assert validate(c())["checks"]["bath_not_courtyard_passage"]
def test_10_open_transition(): assert validate(c())["checks"]["wide_open_transition"]
def test_11_transition_door_fails():
    x=c(); e=next(e for e in x["connections"] if e["type"]=="WIDE_OPEN_TRANSITION"); e.update(type="DOOR",leaf=True,swing=True); assert "UNNECESSARY_PUBLIC_PRIVATE_TRANSITION_DOOR" in validate(x)["failure_codes"]
def test_12_duct_intents(): assert validate(c())["checks"]["wet_spaces_have_duct_intent"]
def test_13_bath_clearance_fails():
    x=c(); x["fixtures"]["family_bath"]["overlap"]=True; assert "BATH_FUNCTIONAL_CLEARANCE_FAIL" in validate(x)["failure_codes"]
def test_14_wc_clearance_fails():
    x=c(); x["fixtures"]["guest_wc"]["approach_clear"]=False; assert "WC_FUNCTIONAL_CLEARANCE_FAIL" in validate(x)["failure_codes"]
def test_15_pattern_bonus_not_mandatory(): assert validate(c())["checks"]["distributor_pattern_not_mandatory"]
def test_16_arrival_complete(): assert validate(c())["checks"]["arrival_sequence_complete"]
def test_17_canopy_provenance(): assert validate(c())["checks"]["canopy_user_rule"]
def test_18_yard_spot_level():
    x=c(); y=next(v for v in x["levels"] if v["target"]=="yard"); assert contains(x["yard"]["bbox"],y["point"])
def test_19_courtyard_spot_level():
    x=c(); y=next(v for v in x["levels"] if v["target"]=="court"); court=next(r for r in x["rooms"] if r["id"]=="court"); assert contains(court["bbox"],y["point"])
def test_20_ffl_spot_level():
    x=c(); y=next(v for v in x["levels"] if v["target"]=="building"); assert contains(x["building"]["bbox"],y["point"])
def test_21_furniture_semantics(): assert validate(c())["checks"]["semantic_furniture_distinct"]
def test_22_previous_learning_active():
    ids={x["id"] for x in cumulative_learning_items() if x["active"]}; assert {f"HL-{i:03d}" for i in range(1,16)} <= ids
def test_23_negative_precedent(): assert negative_precedent_02()["POST_HUMAN_EFFECTIVE_READINESS"]=="FAIL"
