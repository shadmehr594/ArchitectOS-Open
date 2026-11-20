"""Coordinate-free residential pattern selection and knowledge contracts."""
from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json

PROV=["HUMAN_REFERENCE_PATTERN","GENERALIZED_HUMAN_REVIEW_LEARNING"]
SPECS={
"P01":("FRONT_PUBLIC_REAR_PRIVATE","عمومی جلو، خصوصی عقب","ENTRY -> PUBLIC; TRANSITION -> PRIVATE","public frontage; quieter deeper bedrooms"),
"P02":("LEFT_PRIVATE_RIGHT_PUBLIC","خصوصی چپ، عمومی راست","ENTRY -> LEFT_DOMAIN + RIGHT_DOMAIN","lateral split; side follows context, never a universal south rule"),
"P03":("ENTRY_BIFURCATION_PUBLIC_PRIVATE","دوشاخه ورود عمومی و خصوصی","ENTRY_NODE -> PUBLIC_BRANCH + PRIVATE_BRANCH; private route excludes LIVING","immediate decision node"),
"P04":("DUAL_ENTRY_PUBLIC_PRIVATE_SPLIT","دو مسیر متمایز پس از ورود","ARRIVAL -> PUBLIC_DOORWAY; ARRIVAL -> PRIVATE_DOORWAY","guest/family flows differentiated"),
"P05":("CENTRAL_NEUTRAL_DISTRIBUTOR","توزیع‌کننده خنثی مرکزی","PUBLIC -> NEUTRAL_DISTRIBUTOR -> BEDROOMS + BATH + COURTYARD","compact node serves >=3 destinations; wet/private rooms are leaves"),
"P06":("SHORT_PRIVATE_CORRIDOR","راهروی خصوصی کوتاه","TRANSITION -> PRIVATE_CORRIDOR -> MULTIPLE_PRIVATE_DESTINATIONS","corridor justified only by privacy/access"),
"P07":("PUBLIC_OPEN_FIELD","میدان پیوسته عمومی","LIVING <-> DINING <-> OPEN_KITCHEN via WIDE_OPENING","continuous public field; doors not mandatory"),
"P08":("MID_PLAN_DAYLIGHT_YARD","حیاط نورده میانی","NEUTRAL_ACCESS -> NEEDED_DAYLIGHT_YARD -> MULTIPLE_SPACES","middle/upper third allowed; demonstrated deficit required"),
"P09":("WET_CORE_CLUSTER","خوشه فشرده فضاهای تر","CIRCULATION -> each WET_LEAF; cluster never blocks route","compact services without transit wet rooms"),
"P10":("PRIVATE_WING_WITH_NO_GUEST_VIEW","بال خصوصی بدون دید مهمان","GUEST_PATH -> PUBLIC; OFFSET_THRESHOLD -> PRIVATE_WING","shield bedroom doors from dominant guest sightlines"),
"P11":("GUEST_WC_AT_PRIVACY_THRESHOLD","سرویس مهمان در آستانه حریم","PUBLIC -> PRIVACY_THRESHOLD -> GUEST_WC; excludes SLEEPING_CLUSTER","guest never enters sleeping cluster"),
"P12":("FAMILY_BATH_IN_PRIVATE_DOMAIN","حمام خانواده در حوزه خصوصی","PRIVATE_HALL -> FAMILY_BATH_LEAF","no direct living exposure"),
"P13":("KITCHEN_TO_USABLE_REAR_OR_SIDE_YARD","اتصال آشپزخانه به حیاط قابل استفاده","KITCHEN_SERVICE -> USABLE_YARD","physical access without wet-room transit"),
"P14":("BEDROOMS_AS_LEAF_DESTINATIONS","اتاق‌ها مقصد نهایی","DISTRIBUTOR -> BEDROOM_LEAVES","bedrooms never transit"),
"P15":("ENTRY_YARD_ARRIVAL_SEQUENCE","توالی ورود از حیاط جلو","STREET -> PEDESTRIAN_GATE -> PATH -> PORCH_PLATFORM_STEPS_CANOPY -> ENTRY","front-yard arrival legibility"),
"P16":("PARKING_IN_FRONT_YARD_WITH_CLEAR_MANEUVER","پارکینگ حیاط جلو با مانور","STREET -> VEHICLE_GATE -> DRIVEWAY -> MANEUVER -> BAY; pedestrian semantics distinct","maneuver proof required"),
"P17":("PUBLIC_PRIVATE_LATERAL_SPLIT_WITH_SERVICE_SPINE","تفکیک جانبی با ستون خدماتی","PUBLIC_DOMAIN <-> SERVICE_SPINE <-> PRIVATE_DOMAIN; service rooms are leaves","service mediator must not block circulation"),
"P18":("COURTYARD_SERVES_MULTIPLE_HABITABLE_SPACES","حیاط نورده چندفضایی","NEUTRAL_ACCESS -> OPEN_SPACE; OPEN_SPACE serves MULTIPLE_HABITABLE_SPACES","maximize useful daylight service")}

def _entry(pid,s):
    en,fa,flow,intent=s
    return {"id":pid,"name_fa":fa,"name_en":en,"intent":intent,
      "applicable_site_program_conditions":["context predicate evaluated by selector"],
      "required_spatial_roles":[x for x in ("ENTRY","PUBLIC","PRIVATE","SERVICE") if x in (flow+intent)],
      "public_private_service_zoning_behavior":intent,"access_circulation_grammar":flow,
      "daylight_strategy":"use legal open edges; insert yard only for demonstrated need; serve multiple spaces when possible",
      "allowed_variations":["context-responsive topology variant"],
      "disqualifying_conditions":["required role/route cannot be satisfied","cosmetic orientation-only duplicate"],
      "soft_quality_indicators":["route clarity","privacy","low redundant circulation","daylight utility"],
      "negative_counter_patterns":[],"provenance":PROV,"coordinate_policy":"NO_COORDINATES"}
PATTERNS=[_entry(k,v) for k,v in SPECS.items()]

NEG_NAMES=["MECHANICAL_EQUAL_GRID_PACKING","BEDROOM_AS_TRANSIT","BATH_OR_WC_AS_TRANSIT","COURTYARD_ACCESS_THROUGH_WET_ROOM","GUEST_WC_INSIDE_SLEEPING_CLUSTER","ROOM_TO_ROOM_DAYLIGHT_WINDOW","ARBITRARY_WINDOW_PLACEMENT","LONG_REDUNDANT_CORRIDOR","DOOR_ON_EVERY_SPACE","PARKING_WITHOUT_MANEUVER","KITCHEN_WITHOUT_CABINET_GEOMETRY","PUBLIC_TO_PRIVATE_REQUIRES_LIVING_CROSSING_WITHOUT_NEED","PRIVATE_ZONE_EXPOSED_TO_GUEST_SIGHTLINE","DAYLIGHT_YARD_WITH_SINGLE_LOW_VALUE_SERVICE_ONLY_USE_WHEN_BETTER_COMPOSITION_EXISTS","OPEN_SPACE_INSERTED_WITHOUT_FUNCTIONAL_DAYLIGHT_DEFICIT"]
NEGATIVE_PATTERNS=[{"id":f"N{i:02d}","name_en":n,"failure_codes":[n],"regression_fixture_references":[f"RPL-N{i:02d}"],"provenance":"GENERALIZED_HUMAN_REVIEW_LEARNING"} for i,n in enumerate(NEG_NAMES,1)]

REFERENCE_EVIDENCE={"schema":"REFERENCE_PATTERN_EVIDENCE_V1","source_policy":"RELATIONS_ONLY_NO_PIXELS_NO_TRACED_POLYGONS_NO_COPIED_DIMENSIONS_NO_COORDINATES","samples":[
 {"sample_id":"REVIEW_A","conceptual_contributions":["side-by-side public/private split","entry bifurcation","private hall serving bedrooms and bath","guest WC at privacy threshold","kitchen access to usable outdoor space"]},
 {"sample_id":"REVIEW_B","conceptual_contributions":["dual entry paths","private wing without guest view","open dining/living/kitchen field","rear-side outdoor access"],"negative_observation":"guest WC inside sleeping cluster"},
 {"sample_id":"CUMULATIVE_SYNTHESIS","conceptual_contributions":["mid-plan yard serving kitchen and bedrooms","front-yard parking and pedestrian entry separation"]}],"provenance":PROV}

MINAB_OVERLAY={"id":"MINAB_USER_DAYLIGHT_YARD_OVERLAY_V1","activation":{"jurisdiction":"MINAB","user_requests_minab_daylight_overlay":True},"global_mandatory":False,"provenance":"USER_DEFINED_LOCAL_RULE","semantic_scope":["REAR_YARD","SIDE_YARD","LOCAL_DAYLIGHT_YARD"],"rules":{"NORTH_SOUTH_REAR_YARD":{"minimum_width_m":1.7,"minimum_area_m2":12.0},"EAST_WEST_SIDE_YARD":{"minimum_width_m":2.0,"minimum_area_m2":12.0}},"excluded_semantics":["COURTYARD","PATIO"],"conflict_policy":"VERIFIED_MANDATORY_NATIONAL_RULE_PREVAILS_FOR_SAME_SPACE"}
TOPIC4={"id":"T4-4-5-8-3-5","minimum_width_m":3.0,"minimum_area_m2":12.0,"semantic_scope":["COURTYARD","PATIO"],"provenance":"IRAN_NATIONAL_VERIFIED_REGULATION","priority":"MANDATORY_WHEN_APPLICABLE"}

def resolve_daylight_yard_rule(jurisdiction=None,user_requests_minab_daylight_overlay=False,semantic_space="LOCAL_DAYLIGHT_YARD",edge_orientation=None,topic4_applies=False):
    active=str(jurisdiction or "").upper()=="MINAB" and user_requests_minab_daylight_overlay
    local=None
    if active and semantic_space in MINAB_OVERLAY["semantic_scope"]:
        key="EAST_WEST_SIDE_YARD" if str(edge_orientation or "").upper() in {"EAST","WEST"} else "NORTH_SOUTH_REAR_YARD"
        local=deepcopy(MINAB_OVERLAY["rules"][key])|{"rule_key":key,"provenance":"USER_DEFINED_LOCAL_RULE"}
    if topic4_applies:
        return {"active":True,"effective":deepcopy(TOPIC4),"local_candidate":local,"resolution":"NATIONAL_PREVAILS_WHEN_SAME_SPACE"}
    return {"active":bool(local),"effective":local,"local_candidate":local,"resolution":"OPTIONAL_LOCAL_OVERLAY" if local else "NO_APPLICABLE_OVERLAY"}

@dataclass(frozen=True)
class SelectionContext:
    site_width_m:float; site_depth_m:float; open_legal_edges:tuple; street_location:str; bedroom_count:int
    public_space_priority:str="MEDIUM"; daylight_deficit:bool=False; privacy_requirement:str="HIGH"
    yard_courtyard_available:bool=True; parking_required:bool=False; building_placement_preference:str|None=None
    user_preferences:tuple=(); jurisdiction:str|None=None

def topology_signature(g):
    data={"nodes":sorted(g.get("nodes",[])),"edges":sorted(tuple(sorted(e)) for e in g.get("edges",[])),"patterns":sorted(g.get("pattern_ids",[]))}
    return sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()
def diversity_assessment(gs):
    count=len(set(map(topology_signature,gs)))
    return {"candidate_count":len(gs),"distinct_topologies":count,"diversity_score":count/max(1,len(gs)),"failure_codes":["COSMETIC_VARIATION_ONLY"] if len(gs)>1 and count==1 else []}

class ResidentialPatternSelectorV1:
    def select(self,c):
        excluded=[]; applicable=[]
        for p in PATTERNS:
            i=p["id"]; reason=None
            if i in {"P08","P18"} and not c.daylight_deficit: reason="NO_DEMONSTRATED_DAYLIGHT_DEFICIT"
            elif i=="P16" and not c.parking_required: reason="PARKING_NOT_REQUIRED"
            elif i=="P15" and not c.yard_courtyard_available: reason="FRONT_YARD_NOT_AVAILABLE"
            elif i in {"P02","P17"} and c.site_width_m<7: reason="SITE_TOO_NARROW_FOR_LATERAL_SPLIT"
            elif i=="P01" and c.site_depth_m/c.site_width_m<1.35: reason="SITE_NOT_ELONGATED"
            (excluded if reason else applicable).append({"pattern_id":i,"reason":reason} if reason else i)
        allowed=set(applicable); seeds=[["P01","P06","P11","P12","P14"],["P02","P17","P10","P11"],["P03","P05","P10","P12"],["P04","P06","P10","P14"],["P07","P08","P09","P13","P18"]]
        combos=[[x for x in s if x in allowed] for s in seeds]; combos=[x for x in combos if x][:5]
        return {"applicable_patterns":applicable,"excluded_patterns":excluded,"preferred_combinations":combos,"diversity_plan":{"target_count":"3-5","structural_not_cosmetic":True,"failure_code":"COSMETIC_VARIATION_ONLY"},"winner_selected":False,"geometry_generation":"DEFERRED"}
    def compose_grammars(self,c):
        templates=[("FRONT_REAR",["ENTRY","PUBLIC","PRIVATE_HALL","BEDROOMS"],[("ENTRY","PUBLIC"),("ENTRY","PRIVATE_HALL"),("PRIVATE_HALL","BEDROOMS")]),("LATERAL_SPINE",["ENTRY","PUBLIC","SERVICE_SPINE","PRIVATE"],[("ENTRY","PUBLIC"),("ENTRY","PRIVATE"),("SERVICE_SPINE","PUBLIC"),("SERVICE_SPINE","PRIVATE")]),("ENTRY_BIFURCATION",["ENTRY_NODE","PUBLIC_BRANCH","PRIVATE_BRANCH","PRIVATE_LEAVES"],[("ENTRY_NODE","PUBLIC_BRANCH"),("ENTRY_NODE","PRIVATE_BRANCH"),("PRIVATE_BRANCH","PRIVATE_LEAVES")]),("DUAL_THRESHOLD",["ARRIVAL","PUBLIC_DOORWAY","PRIVATE_DOORWAY","PUBLIC","PRIVATE"],[("ARRIVAL","PUBLIC_DOORWAY"),("ARRIVAL","PRIVATE_DOORWAY"),("PUBLIC_DOORWAY","PUBLIC"),("PRIVATE_DOORWAY","PRIVATE")]),("COURTYARD_FIELD",["ENTRY","PUBLIC_FIELD","DISTRIBUTOR","DAYLIGHT_YARD","PRIVATE"],[("ENTRY","PUBLIC_FIELD"),("PUBLIC_FIELD","DISTRIBUTOR"),("DISTRIBUTOR","DAYLIGHT_YARD"),("DISTRIBUTOR","PRIVATE")])]
        return [{"grammar_family":f,"pattern_ids":p,"nodes":n,"edges":[list(e) for e in es],"geometry":None} for (f,n,es),p in zip(templates,self.select(c)["preferred_combinations"])]

SYMBOL_IDS="SINGLE_BED DOUBLE_BED MASTER_BED BEDSIDE_TABLE WARDROBE SOFA_1_SEAT SOFA_2_SEAT SOFA_3_SEAT L_SOFA ARMCHAIR COFFEE_TABLE TV_MEDIA_UNIT DINING_TABLE_4 DINING_TABLE_6 DINING_TABLE_8 KITCHEN_BASE_CABINET KITCHEN_TALL_CABINET SINK COOKTOP REFRIGERATOR ISLAND PENINSULA WC_IRANIAN WC_WESTERN WASHBASIN SHOWER BATHTUB WASHING_MACHINE PARKED_CAR TREE PLANTER LANDSCAPE_PROXY".split()
FURNITURE_LIBRARY={"schema":"FURNITURE_VECTOR_LIBRARY_CONTRACT_V1","vector_only":True,"raster_dependencies":[],"symbols":[{"semantic_id":s,"vector_drawing_primitives":["PATH","LINE","ARC","POLYLINE"],"nominal_real_world_footprint":{"width_m":None,"depth_m":None,"status":"HEURISTIC_TO_BE_CALIBRATED","provenance":"DESIGN_HEURISTIC"},"anchor_points":["INSERTION","CENTER","ALIGNMENT_EDGE"],"rotation":{"unit":"degrees","allowed":True},"clearance_envelope":{"required":True,"representation":"VECTOR_PATH"},"svg_pdf_representation_contract":"VECTOR_GROUP_AND_PATHS","future_dwg_block_mapping":None} for s in SYMBOL_IDS]}

def library_documents(): return {
 "RESIDENTIAL_PATTERN_LIBRARY.json":{"schema":"RESIDENTIAL_PATTERN_LIBRARY_V1","patterns":PATTERNS},
 "RESIDENTIAL_NEGATIVE_PATTERN_LIBRARY.json":{"schema":"RESIDENTIAL_NEGATIVE_PATTERN_LIBRARY_V1","patterns":NEGATIVE_PATTERNS},
 "REFERENCE_PATTERN_EVIDENCE.json":REFERENCE_EVIDENCE,
 "PATTERN_SELECTION_MODEL.json":{"schema":"PATTERN_SELECTION_MODEL_V1","pipeline":["SITE+PROGRAM+USER_CONSTRAINTS+JURISDICTION","APPLICABLE_FAMILIES","3-5_DISTINCT_GRAMMARS","ZONING_ACCESS_DAYLIGHT_GRAPHS","GEOMETRY_LATER","VALIDATE","SCORE","HUMAN_REVIEW"],"selector_factors":list(SelectionContext.__dataclass_fields__),"no_hardcoded_winner":True,"failure_code":"COSMETIC_VARIATION_ONLY"},
 "MINAB_USER_DAYLIGHT_YARD_OVERLAY.json":MINAB_OVERLAY,"FURNITURE_VECTOR_LIBRARY_CONTRACT.json":FURNITURE_LIBRARY}
def export_documents(path):
    path=Path(path); path.mkdir(parents=True,exist_ok=True)
    for n,d in library_documents().items(): (path/n).write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding="utf-8")
