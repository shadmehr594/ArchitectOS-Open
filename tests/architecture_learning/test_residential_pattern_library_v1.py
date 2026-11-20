import json
from dataclasses import replace
from core.architecture.knowledge.residential_plan_pattern_library_v1 import *
from core.architecture.learning.cumulative_human_learning_v2 import cumulative_learning_items
def ctx(**kw): return replace(SelectionContext(10,24,("SOUTH","NORTH"),"SOUTH",3,daylight_deficit=True,parking_required=True),**kw)
def test_01_ids(): assert {f"P{i:02d}" for i in range(1,19)}=={p["id"] for p in PATTERNS}
def test_02_no_coordinates():
 raw=json.dumps(PATTERNS).lower(); assert not any(x in raw for x in ['"x"','"y"','bbox','polygon','absolute_coordinate'])
 assert all(p["coordinate_policy"]=="NO_COORDINATES" for p in PATTERNS)
def test_03_evidence_relational(): assert "NO_COORDINATES" in REFERENCE_EVIDENCE["source_policy"] and "dimensions" in REFERENCE_EVIDENCE["source_policy"].lower()
def test_04_multi_family(): assert len(ResidentialPatternSelectorV1().select(ctx())["preferred_combinations"])>=3
def test_05_cosmetic_duplicate():
 a={"pattern_ids":["P03"],"nodes":["A","B"],"edges":[["A","B"]],"orientation":"N"}; assert diversity_assessment([a,a|{"orientation":"S"}])["failure_codes"]==["COSMETIC_VARIATION_ONLY"]
def test_06_bifurcation():
 g=next(x for x in ResidentialPatternSelectorV1().compose_grammars(ctx()) if x["grammar_family"]=="ENTRY_BIFURCATION"); assert ["ENTRY_NODE","PUBLIC_BRANCH"] in g["edges"] and ["ENTRY_NODE","PRIVATE_BRANCH"] in g["edges"]
def test_07_dual():
 g=next(x for x in ResidentialPatternSelectorV1().compose_grammars(ctx()) if x["grammar_family"]=="DUAL_THRESHOLD"); assert sum(e[0]=="ARRIVAL" for e in g["edges"])==2
def test_08_distributor(): assert ">=3" in next(p for p in PATTERNS if p["id"]=="P05")["intent"]
def test_09_guest_wc(): assert "excludes SLEEPING_CLUSTER" in next(p for p in PATTERNS if p["id"]=="P11")["access_circulation_grammar"]
def test_10_bath(): assert "PRIVATE_HALL -> FAMILY_BATH" in next(p for p in PATTERNS if p["id"]=="P12")["access_circulation_grammar"]
def test_11_mid_yard(): assert "MULTIPLE_SPACES" in next(p for p in PATTERNS if p["id"]=="P08")["access_circulation_grammar"]
def test_12_no_deficit_no_yard(): assert {"P08","P18"}<={x["pattern_id"] for x in ResidentialPatternSelectorV1().select(ctx(daylight_deficit=False))["excluded_patterns"]}
def test_13_inactive_default(): assert not resolve_daylight_yard_rule(jurisdiction="MINAB")["active"]
def test_14_requires_minab_and_request(): assert not resolve_daylight_yard_rule(jurisdiction="TEHRAN",user_requests_minab_daylight_overlay=True)["active"]
def test_15_ew(): assert resolve_daylight_yard_rule("MINAB",True,"SIDE_YARD","EAST")["effective"]["minimum_width_m"]==2
def test_16_ns(): assert resolve_daylight_yard_rule("MINAB",True,"REAR_YARD","NORTH")["effective"]["minimum_width_m"]==1.7
def test_17_topic4_wins(): assert resolve_daylight_yard_rule("MINAB",True,"LOCAL_DAYLIGHT_YARD","NORTH",True)["effective"]["minimum_width_m"]==3
def test_18_previous_registry(): assert {f"HL-{i:03d}" for i in range(1,27)}<={x["id"] for x in cumulative_learning_items() if x["active"]}
def test_19_symbols(): assert len(SYMBOL_IDS)==len(set(SYMBOL_IDS)) and len(SYMBOL_IDS)>=30
def test_20_no_raster(): assert FURNITURE_LIBRARY["vector_only"] and not FURNITURE_LIBRARY["raster_dependencies"]
def test_21_dwg(): assert all("future_dwg_block_mapping" in x for x in FURNITURE_LIBRARY["symbols"])
def test_22_excluded_reasons(): assert all(x["reason"] for x in ResidentialPatternSelectorV1().select(ctx(daylight_deficit=False))["excluded_patterns"])
def test_23_topology_diversity(): assert diversity_assessment(ResidentialPatternSelectorV1().compose_grammars(ctx()))["distinct_topologies"]>=3
