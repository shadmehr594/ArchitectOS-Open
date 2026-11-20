from __future__ import annotations

"""Canonical semantic/vector plan-symbol library.

Coordinates in ``vector_primitives`` are normalized to the symbol footprint.  The
same data is consumed by PDF/SVG today and can be mapped to DWG blocks later.
Nominal dimensions are design heuristics, never regulatory assertions.
"""

def _rect(x, y, w, h, role="outline", rx=0.0): return {"kind":"rect","x":x,"y":y,"w":w,"h":h,"rx":rx,"role":role}
def _line(x1,y1,x2,y2,role="detail"): return {"kind":"line","x1":x1,"y1":y1,"x2":x2,"y2":y2,"role":role}
def _ellipse(cx,cy,rx,ry,role="detail"): return {"kind":"ellipse","cx":cx,"cy":cy,"rx":rx,"ry":ry,"role":role}
def _circle(cx,cy,r,role="detail"): return {"kind":"circle","cx":cx,"cy":cy,"r":r,"role":role}
def _arc(cx,cy,r,start,extent,role="detail"): return {"kind":"arc","cx":cx,"cy":cy,"r":r,"start":start,"extent":extent,"role":role}

def _bed(double=False):
    p=[_rect(0,0,1,1,"frame",.03),_line(0,.25,1,.25,"frame"),_rect(.07,.04,.38,.17,"pillow",.04)]
    if double: p.append(_rect(.55,.04,.38,.17,"pillow",.04))
    return p
def _sofa(seats=3):
    p=[_rect(.03,.05,.94,.9,"frame",.12),_rect(.12,.17,.76,.62,"seat",.08),_line(.12,.2,.88,.2,"back")]
    for i in range(1,seats): p.append(_line(.12+.76*i/seats,.2,.12+.76*i/seats,.79,"cushion"))
    p += [_rect(.03,.2,.1,.58,"arm",.03),_rect(.87,.2,.1,.58,"arm",.03)]
    return p
def _dining(seats):
    p=[_rect(.15,.22,.7,.56,"table",.08)]; n=seats//2
    for i in range(n):
        x=.2+i*.6/max(1,n-1); p += [_rect(x-.06,.03,.12,.14,"chair",.02),_rect(x-.06,.83,.12,.14,"chair",.02)]
    return p

_RAW={
"SINGLE_BED":("BEDROOM_PRIVATE","تخت یک‌نفره",(.90,2.00),_bed()),
"DOUBLE_BED":("BEDROOM_PRIVATE","تخت دونفره",(1.60,2.00),_bed(True)),
"MASTER_BED":("BEDROOM_PRIVATE","تخت مستر",(1.80,2.00),_bed(True)),
"BEDSIDE_TABLE":("BEDROOM_PRIVATE","پاتختی",(.45,.45),[_rect(0,0,1,1,"cabinet",.05),_circle(.5,.5,.04,"handle")]),
"WARDROBE":("BEDROOM_PRIVATE","کمد لباس",(1.80,.60),[_rect(0,0,1,1,"cabinet"),_line(.5,0,.5,1,"leaf"),_line(.08,.12,.46,.88,"hatch"),_line(.54,.88,.92,.12,"hatch")]),
"DRESSER_VANITY":("BEDROOM_PRIVATE","میز آرایش",(1.0,.5),[_rect(0,0,1,1,"cabinet"),_ellipse(.5,.5,.28,.2,"mirror")]),
"STUDY_DESK_CHAIR":("BEDROOM_PRIVATE","میز مطالعه",(1.2,.9),[_rect(0,0,1,.48,"table"),_rect(.38,.62,.24,.3,"chair",.05)]),
"SOFA_1":("LIVING","مبل یک‌نفره",(.85,.85),_sofa(1)),"SOFA_1_SEAT":("LIVING","مبل یک‌نفره",(.85,.85),_sofa(1)),
"SOFA_2":("LIVING","مبل دونفره",(1.55,.85),_sofa(2)),"SOFA_2_SEAT":("LIVING","مبل دونفره",(1.55,.85),_sofa(2)),
"SOFA_3":("LIVING","مبل سه‌نفره",(2.15,.90),_sofa(3)),"SOFA_3_SEAT":("LIVING","مبل سه‌نفره",(2.15,.90),_sofa(3)),
"L_SOFA":("LIVING","مبل ال",(2.4,1.8),_sofa(3)+[_rect(.62,.2,.32,.75,"chaise",.07)]),
"ARMCHAIR":("LIVING","صندلی راحتی",(.8,.8),_sofa(1)),
"COFFEE_TABLE":("LIVING","میز جلو مبلی",(1.1,.6),[_ellipse(.5,.5,.47,.42,"table")]),
"SIDE_TABLE":("LIVING","میز کنار مبل",(.45,.45),[_circle(.5,.5,.45,"table")]),
"TV_MEDIA_UNIT":("LIVING","میز تلویزیون",(1.6,.4),[_rect(0,0,1,1,"cabinet"),_rect(.12,.2,.76,.6,"screen")]),
"CONSOLE":("LIVING","کنسول",(1.2,.4),[_rect(0,0,1,1,"cabinet"),_line(.33,0,.33,1,"leaf"),_line(.66,0,.66,1,"leaf")]),
"RUG":("LIVING","فرش",(2.0,1.4),[_rect(0,0,1,1,"rug",.04)]),
"DINING_TABLE_4":("DINING","میز چهار نفره",(1.2,.8),_dining(4)),"DINING_TABLE_6":("DINING","میز شش نفره",(1.8,.9),_dining(6)),"DINING_TABLE_8":("DINING","میز هشت نفره",(2.2,1.0),_dining(8)),
"KITCHEN_BASE_CABINET":("KITCHEN","کابینت زمینی",(1.2,.6),[_rect(0,0,1,1,"cabinet"),_line(.5,0,.5,1,"leaf")]),
"TALL_CABINET":("KITCHEN","کابینت بلند",(.6,.6),[_rect(0,0,1,1,"cabinet"),_line(0,0,1,1,"hatch"),_line(0,1,1,0,"hatch")]),
"REFRIGERATOR":("KITCHEN","یخچال",(.75,.75),[_rect(0,0,1,1,"appliance",.04),_line(.12,.5,.88,.5,"door"),_line(.16,.12,.16,.42,"handle")]),
"SINK":("KITCHEN","سینک",(.8,.6),[_rect(0,0,1,1,"counter"),_ellipse(.47,.55,.3,.28,"bowl"),_arc(.75,.25,.14,180,180,"faucet")]),
"COOKTOP":("KITCHEN","اجاق",(.6,.6),[_rect(0,0,1,1,"counter")]+[_circle(x,y,.13,"burner") for x in (.28,.72) for y in (.28,.72)]),
"OVEN":("KITCHEN","فر",(.6,.6),[_rect(0,0,1,1,"appliance"),_rect(.14,.25,.72,.58,"door",.03),_circle(.25,.13,.04,"control"),_circle(.5,.13,.04,"control"),_circle(.75,.13,.04,"control")]),
"DISHWASHER":("KITCHEN","ماشین ظرفشویی",(.6,.6),[_rect(0,0,1,1,"appliance"),_line(.12,.22,.88,.22,"handle"),_circle(.2,.1,.035,"control")]),
"PENINSULA":("KITCHEN","پنینسولا",(1.8,.8),[_rect(0,0,1,1,"counter",.03),_line(.1,.15,.9,.15,"worktop")]),
"ISLAND":("KITCHEN","جزیره",(1.8,.9),[_rect(0,0,1,1,"counter",.05),_rect(.08,.12,.84,.76,"cabinet",.03)]),
"BREAKFAST_BAR":("KITCHEN","بار صبحانه",(1.6,.55),[_rect(0,0,1,1,"counter",.04),_circle(.25,1.18,.11,"stool"),_circle(.75,1.18,.11,"stool")]),
"WC_IRANIAN":("BATH_WC","توالت ایرانی",(.6,.8),[_rect(0,0,1,1,"fixture",.08),_ellipse(.5,.52,.22,.32,"bowl"),_rect(.12,.35,.15,.3,"foot"),_rect(.73,.35,.15,.3,"foot")]),
"WC_WESTERN":("BATH_WC","توالت فرنگی",(.7,.8),[_rect(.25,0,.5,.3,"cistern",.04),_ellipse(.5,.62,.34,.34,"bowl")]),
"WASHBASIN":("BATH_WC","روشویی",(.6,.5),[_rect(0,0,1,1,"fixture",.08),_ellipse(.5,.58,.34,.28,"bowl"),_arc(.5,.2,.14,180,180,"faucet")]),
"VANITY":("BATH_WC","کابین روشویی",(.8,.55),[_rect(0,0,1,1,"cabinet"),_ellipse(.5,.55,.28,.25,"bowl")]),
"SHOWER":("BATH_WC","دوش",(.9,.9),[_rect(0,0,1,1,"fixture"),_line(0,0,1,1,"slope"),_line(0,1,1,0,"slope"),_circle(.5,.5,.06,"drain")]),
"SHOWER_ZONE":("BATH_WC","محدوده دوش",(.9,.9),[_rect(0,0,1,1,"fixture"),_line(0,0,1,1,"slope"),_line(0,1,1,0,"slope"),_circle(.5,.5,.06,"drain")]),
"SHOWER_TRAY":("BATH_WC","زیردوشی",(.9,.9),[_rect(0,0,1,1,"fixture",.04),_rect(.05,.05,.9,.9,"bowl",.03),_circle(.5,.5,.055,"drain")]),
"BATHTUB":("BATH_WC","وان",(1.7,.75),[_rect(0,0,1,1,"fixture",.16),_rect(.08,.1,.84,.8,"bowl",.14),_circle(.16,.5,.04,"drain")]),
"FLOOR_DRAIN":("BATH_WC","کفشور",(.15,.15),[_circle(.5,.5,.45,"drain"),_line(.18,.18,.82,.82,"grate"),_line(.18,.82,.82,.18,"grate")]),
"WASHING_MACHINE":("BATH_WC","ماشین لباسشویی",(.65,.65),[_rect(0,0,1,1,"appliance",.04),_circle(.5,.58,.3,"door"),_circle(.18,.15,.04,"control")]),
"WET_SHAFT":("BATH_WC","داکت فضای تر",(.4,.4),[_rect(0,0,1,1,"shaft"),_line(0,0,1,1,"hatch"),_line(0,1,1,0,"hatch")]),
"BIDET":("BATH_WC","بیده",(.6,.6),[_ellipse(.5,.55,.35,.38,"bowl"),_circle(.5,.18,.05,"faucet")]),
"SHOE_CABINET":("ENTRY","جاکفشی",(1.0,.38),[_rect(0,0,1,1,"cabinet"),_line(.33,0,.33,1,"leaf"),_line(.66,0,.66,1,"leaf")]),
"PORCH_PLATFORM":("ENTRY","سکوی ورودی",(2.2,1.2),[_rect(0,0,1,1,"platform"),_line(0,.82,1,.82,"threshold")]),
"ENTRY_STEPS":("ENTRY","پله ورودی",(2.2,.9),[_rect(0,0,1,1,"steps")]+[_line(0,y,1,y,"tread") for y in (.25,.5,.75)]),
"CANOPY":("ENTRY","سایبان",(2.2,1.2),[_rect(0,0,1,1,"canopy")]),
"RAMP":("ENTRY","رمپ",(1.2,3.0),[_rect(0,0,1,1,"ramp"),_line(.5,.85,.5,.15,"direction")]),
"PARKED_CAR":("PARKING","خودرو",(2.6,5.0),[_rect(.04,0,.92,1,"body",.16),_rect(.17,.19,.66,.6,"glass",.12),_rect(0,.16,.08,.18,"wheel",.02),_rect(.92,.16,.08,.18,"wheel",.02),_rect(0,.68,.08,.18,"wheel",.02),_rect(.92,.68,.08,.18,"wheel",.02)]),
"PARKING_BAY":("PARKING","جای پارک",(2.6,5.0),[_rect(0,0,1,1,"bay")]),
"TREE":("LANDSCAPE","درخت",(1.2,1.2),[_circle(.5,.5,.48,"canopy"),_circle(.5,.5,.09,"trunk")]),
"PLANTER_TREE":("LANDSCAPE","درختچه",(1,1),[_circle(.5,.5,.47,"canopy"),_line(.2,.5,.8,.5,"branch"),_line(.5,.2,.5,.8,"branch")]),
"SHRUB_PLANTER":("LANDSCAPE","باغچه",(1.2,.6),[_rect(0,0,1,1,"planter",.1),_circle(.25,.5,.17,"shrub"),_circle(.5,.5,.17,"shrub"),_circle(.75,.5,.17,"shrub")]),
"GARDEN_SEAT":("LANDSCAPE","نشیمن باغ",(1.4,.55),[_rect(0,.2,1,.45,"seat"),_line(.1,.65,.1,1,"leg"),_line(.9,.65,.9,1,"leg")]),
}

def _record(sid, row):
    cat,fa,nom,prims=row; wall=cat in {"KITCHEN","BEDROOM_PRIVATE","ENTRY"}
    clear={"BATH_WC":.65,"DINING":.75,"KITCHEN":1.0,"PARKING":.8}.get(cat,.6)
    return {"semantic_id":sid,"category":cat,"name_fa":fa,"nominal_footprint_m":list(nom),"dimension_provenance":"DESIGN_HEURISTIC","anchor":"LOWER_LEFT","rotation_support":True,"mirror_support":cat in {"BEDROOM_PRIVATE","LIVING","KITCHEN","ENTRY"},"wall_alignment_required":wall,"clearance_envelope_m":clear,"activity_use_envelope_m":clear,"collision_mask":"FOOTPRINT_PLUS_CLEARANCE","preferred_host_wall_logic":"longest usable wall; preserve openings" if wall else "free zone / circulation aware","vector_primitives":prims,"pdf_renderer_mapping":"CANONICAL_VECTOR_PRIMITIVES","svg_renderer_mapping":"CANONICAL_VECTOR_PRIMITIVES","future_dwg_block_name":f"AOS_{sid}","future_dwg_layer":f"A-{cat}","qa_tag":f"SYMBOL::{cat}::{sid}::RECOGNIZABLE"}

SYMBOL_LIBRARY={sid:_record(sid,row) for sid,row in _RAW.items()}
SPACE_FURNITURE_BUNDLES={
"LIVING":["SOFA_3","ARMCHAIR","COFFEE_TABLE","TV_MEDIA_UNIT"],"DINING":["DINING_TABLE_6"],
"BEDROOM_SINGLE":["SINGLE_BED","WARDROBE","STUDY_DESK_CHAIR"],"BEDROOM_DOUBLE":["DOUBLE_BED","WARDROBE","BEDSIDE_TABLE"],
"MASTER":["MASTER_BED","WARDROBE","BEDSIDE_TABLE","BEDSIDE_TABLE"],"OPEN_KITCHEN":["KITCHEN_BASE_CABINET","SINK","COOKTOP","REFRIGERATOR"],
"BATH":["SHOWER_ZONE","WASHBASIN","FLOOR_DRAIN","WET_SHAFT"],"GUEST_WC":["WC_IRANIAN","WASHBASIN","WET_SHAFT"],"LAUNDRY":["WASHING_MACHINE","TALL_CABINET","FLOOR_DRAIN"],"PARKING":["PARKING_BAY","PARKED_CAR"]}

def get_symbol(symbol_id): return SYMBOL_LIBRARY[symbol_id]
