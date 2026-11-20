from core.prompt_intelligence.architectural_intent import ArchitecturalIntent


PROMPT = """
جنوب معبر است و شمال شرق غرب پلاک همسایه است. ساختمان در شمال باشد.
همکف 100 درصد سطح اشغال و واحد تجاری با مساحت 100 مترمربع، پشت تجاری
پارکینگ و راه پله و آسانسور باشد. طبقات مسکونی 60 درصد سطح اشغال و در
شمال حیاط خلوت با مساحت 12 مترمربع و عرض حیاط خلوت 1.7 متر باشد.
یک واحد پارکینگ تجاری و 3 واحد پارکینگ مسکونی تامین شود. طبقه اول یک
واحد و طبقه دوم دو واحد مسکونی باشد. طبقه سوم خرپشته و اتاق آسانسور
باشد. همه واحدها بالکن داشته باشند و پیش آمدگی 1 متر در ضلع جنوبی همکف
و طبقات مسکونی باشد. درز انقطاع بر اساس ارتفاع ساختمان در شمال شرق غرب
رعایت شود.
"""


def test_detailed_mixed_use_program_is_preserved_without_false_road_width():
    intent = ArchitecturalIntent().extract(PROMPT)
    program = intent["program_constraints"]

    assert intent["building_type"] == "mixed_use_commercial_residential"
    assert intent["site_constraints"].get("road") is None
    assert intent["site_constraints"]["building_position"]["side"] == "north"
    assert program["site_edges"] == {
        "road_side": "south",
        "neighbor_sides": ["north", "east", "west"],
    }
    assert program["coverage_by_level"] == {"ground": 1.0, "residential": 0.6}
    assert program["commercial"] == {"area": 100.0, "floor": "ground"}
    assert program["backyard"] == {"side": "north", "area": 12.0, "width": 1.7}
    assert program["parking"] == {
        "commercial": 1,
        "residential": 3,
        "location": "behind_commercial",
    }
    assert program["residential_units_by_floor"] == {"F1": 1, "F2": 2}
    assert program["roof_level"] == {
        "floor": "F3",
        "stair_headroom": True,
        "elevator_room": True,
    }
    assert program["balcony_required_for_all_units"] is True
    assert program["projection"] == {
        "depth": 1.0,
        "side": "south",
        "levels": ["ground", "residential"],
    }
    assert program["separation_joint"] == {
        "required": True,
        "sides": ["north", "east", "west"],
        "basis": "building_height",
    }
