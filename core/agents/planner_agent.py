import re

from core.architecture.knowledge.building_program_knowledge import (
    BuildingProgramKnowledge
)

from core.architecture.reasoning.architectural_space_dimension_resolver import (
    ArchitecturalSpaceDimensionResolver
)


class PlannerAgent:


    VERSION = "v67.10"


    def __init__(self):

        print(
            "📐 Planner Agent v67.10 ACTIVE"
        )



    def plan(
        self,
        text,
        intent,
        context=None
    ):


        text_lower = text.lower()

        print(
            "\n====== PLANNER CONTEXT DEBUG ======"
        )

        print(
            context
        )

        print(
            "===================================="
        )



        # ==================================================
        # ARCHITECTURAL INTENT EXTRACTION
        # ==================================================

        architectural_intent = {}


        if isinstance(context, dict):


            # Direct planner context
            architectural_intent = context.get(
                "architectural_intent",
                {}
            )


            # Runtime context fallback
            if not architectural_intent:

                runtime_context = context.get(
                    "runtime_context",
                    {}
                )


                if isinstance(
                    runtime_context,
                    dict
                ):

                    architectural_intent = runtime_context.get(
                        "architectural_intent",
                        {}
                    )



        if not isinstance(
            architectural_intent,
            dict
        ):

            architectural_intent = {}


        # PLAN_REQUIREMENTS_CONNECTION_V1 — the existing intent owner passes
        # one provenance-aware semantic contract.  Planner templates remain a
        # fallback only when that contract has no explicit required program.
        plan_requirements = architectural_intent.get(
            "plan_requirements"
        )

        if not (
            isinstance(plan_requirements, dict)
            and plan_requirements.get("contract")
            == "ArchitecturalPlanRequirementsV1"
        ):

            plan_requirements = None

        program_source = "template_defaults"
        authoritative_space_instances = []
        unassigned_required_spaces = []
        authoritative_plan_program = None




        # ==================================================
        # FLOORS
        # ==================================================

        floors = 1


        print(
            "🔥 FLOOR TEXT INPUT:",
            text_lower
        )


        floor_patterns = [

            r'(\d+)\s*floor',
            r'(\d+)\s*story',
            r'(\d+)\s*storey',
            r'(\d+)\s*طبقه'

        ]


        for pattern in floor_patterns:


            print(
                "🔥 TEST FLOOR PATTERN:",
                pattern
            )


            match = re.search(
                pattern,
                text_lower
            )


            if match:


                floors = int(
                    match.group(1)
                )


                print(
                    "🔥 FLOOR DETECTION:",
                    floors
                )


                print(
                    "🔥 ORIGINAL TEXT:",
                    text
                )


                break




        print(
            "🔥 FINAL FLOOR SOURCE:",
            floors
        )



        # ==================================================
        # FLOORS FROM ARCHITECTURAL INTENT
        # ==================================================

        if floors == 1 and isinstance(
            architectural_intent,
            dict
        ):

            intent_levels = architectural_intent.get(
                "levels",
                {}
            )


            if isinstance(
                intent_levels,
                dict
            ):

                total = intent_levels.get(
                    "total"
                )


                if isinstance(
                    total,
                    int
                ) and total > floors:

                    floors = total


        if plan_requirements:

            required_floor_count = plan_requirements.get(
                "floor_count",
                {}
            )

            if not isinstance(required_floor_count, dict):
                required_floor_count = {}

            required_floor_value = required_floor_count.get("value")

            if (
                required_floor_count.get("source") == "user_explicit"
                and isinstance(required_floor_value, int)
                and required_floor_value > 0
            ):

                floors = required_floor_value

        print(
            "🔥 FLOORS AFTER ARCHITECTURAL INTENT:",
            floors
        )

        print(
            "🔥 INTENT LEVELS USED BY PLANNER:",
            architectural_intent.get(
                "levels",
                {}
            )
            if isinstance(
                architectural_intent,
                dict
            )
            else None
        )


        # ==================================================
        # SITE
        # ==================================================

        site = {

            "width": None,

            "depth": None,

            "area": None

        }



        site_match = re.search(

            r'(\d+)\s*x\s*(\d+)',

            text_lower

        )



        if site_match:


            site["width"] = int(
                site_match.group(1)
            )


            site["depth"] = int(
                site_match.group(2)
            )


            site["area"] = (

                site["width"]

                *

                site["depth"]

            )





        # ==================================================
        # BUILDING TYPE
        # Architectural Intent Priority
        # ==================================================

        building_type = "generic"



        intent_building = None



        if isinstance(intent, dict):


            intent_building = intent.get(
                "building_type"
            )



        if architectural_intent.get(
            "building_type"
        ):


            building_type = architectural_intent.get(
                "building_type"
            )



        elif intent_building:


            building_type = intent_building



        else:


            combined = (

                text_lower

                +

                " "

                +

                str(intent).lower()

            )



            if any(

                x in combined

                for x in [

                    "villa",

                    "ویلا"

                ]

            ):


                building_type = "villa"



            elif any(

                x in combined

                for x in [

                    "house",

                    "home",

                    "خانه"

                ]

            ):


                building_type = "house"



            elif any(

                x in combined

                for x in [

                    "apartment",

                    "آپارتمان"

                ]

            ):


                building_type = "apartment"



            elif any(

                x in combined

                for x in [

                    "tower",

                    "برج"

                ]

            ):


                building_type = "tower"


        if building_type == "shopping_mall" and floors == 1:

            floors = 2


        # ==================================================
        # SCALE INTELLIGENCE
        # ==================================================

        scale = (

            architectural_intent.get(
                "scale"
            )

            or

            "normal"

        )



        if any(

            x in text_lower

            for x in [

                "small",

                "small house",

                "کوچک",

                "خانه کوچک"

            ]

        ):


            scale = "small"



        elif any(

            x in text_lower

            for x in [

                "large",

                "big",

                "بزرگ"

            ]

        ):


            scale = "large"




        # ==================================================
        # MATERIAL INTELLIGENCE
        # ==================================================

        materials = architectural_intent.get(

            "materials",

            []

        )


        if not isinstance(

            materials,

            list

        ):


            materials = []


        materials_source = (
            "user_explicit"
            if materials
            else "planner_default"
        )


        if any(

            x in text_lower

            for x in [

                "brick",

                "آجر",

                "آجری"

            ]

        ):


            materials_source = "user_explicit"


            if "traditional brick masonry" not in materials:


                materials.append(

                    "traditional brick masonry"

                )




        if not materials:


            materials = [

                "concrete",

                "glass"

            ]




        # ==================================================
        # STYLE
        # ==================================================

        style = architectural_intent.get(
            "style"
        )

        style_source = (
            "user_explicit"
            if style
            else "planner_default"
        )

        if not style:
            style = "balanced"

        
        # ==================================================
        # REQUIREMENTS
        # ==================================================

        requirements = {


            "parking":

                any(

                    x in text_lower

                    for x in [

                        "parking",

                        "garage",

                        "پارکینگ"

                    ]

                ),



            "garden":

                any(

                    x in text_lower

                    for x in [

                        "garden",

                        "yard",

                        "حیاط"

                    ]

                ),



            "green_roof":

                any(

                    x in text_lower

                    for x in [

                        "green roof",

                        "green_roof",

                        "بام سبز"

                    ]

                ),



            "pool":

                any(

                    x in text_lower

                    for x in [

                        "pool",

                        "swimming",

                        "استخر"

                    ]

                ),



            "elevator":

                any(

                    x in text_lower

                    for x in [

                        "elevator",

                        "lift",

                        "آسانسور"

                    ]

                )

        }


        # ==================================================
        # FLOOR-AWARE BUILDING PROGRAM KNOWLEDGE
        # ==================================================

        program_knowledge = BuildingProgramKnowledge()

        intent_functions = architectural_intent.get(
            "functions",
            []
        )

        if not isinstance(
            intent_functions,
            list
        ):
            intent_functions = []

        program_data = program_knowledge.get_program(
            building_type,
            intent_functions
        )

        if not isinstance(
            program_data,
            dict
        ):
            program_data = {}


        relationships = []


        zones = {

            "public": [],

            "semi_public": [],

            "private": [],

            "service": [],

            "external": []

        }


    


        # ==================================================
        # UNIT DETECTION
        # ==================================================

        units = {

            "per_floor": 1

        }



        unit_match = re.search(

            r'(\d+)\s*(unit|units|apartment|apartments)',

            text_lower

        )



        if unit_match:


            units["per_floor"] = int(

                unit_match.group(1)

            )





        # ==================================================
        # MEMORY STYLE CONTEXT
        # ==================================================

        context_style = None



        if isinstance(context, dict):


            context_style = context.get(

                "architecture_style"

            )



            if not context_style:


                runtime_context = context.get(

                    "runtime_context",

                    {}

                )



                if isinstance(

                    runtime_context,

                    dict

                ):



                    memory_context = runtime_context.get(

                        "memory_context",

                        {}

                    )



                    if isinstance(

                        memory_context,

                        dict

                    ):


                        context_style = memory_context.get(

                            "architecture_style"

                        )



                        if not context_style:


                            personal_context = memory_context.get(

                                "personal_context",

                                {}

                            )


                            if isinstance(

                                personal_context,

                                dict

                            ):


                                context_style = personal_context.get(

                                    "architecture_style"

                                )



                                if not context_style:


                                    preferences = personal_context.get(

                                        "preferences",

                                        {}

                                    )


                                    if isinstance(

                                        preferences,

                                        dict

                                    ):


                                        context_style = preferences.get(

                                            "architecture_style"

                                        )




        if not context_style and isinstance(

            intent,

            dict

        ):


            context_style = intent.get(

                "architecture_style"

            )





        # ==================================================
        # STYLE PRIORITY FIX
        # Current Request > Architectural Intent > Memory
        # ==================================================

        style_keywords = [

            "modern",

            "minimal",

            "classic",

            "luxury",

            "traditional",

            "industrial"

        ]


        requested_style = None


        for s in style_keywords:

            if s in text_lower:

                requested_style = s

                break



        if requested_style:

            style = requested_style
            style_source = "user_explicit"


        elif architectural_intent.get("style"):

            style = architectural_intent.get(
                "style"
            )

        elif context_style:

            style = context_style




        # ==================================================
        # LEVELS
        # ==================================================

        levels = []



        for i in range(floors):


            levels.append({

                "level":

                    i + 1,


                "type":

                    "ground"

                    if i == 0

                    else

                    "upper",


                "units":

                    units["per_floor"]

            })

        if building_type == "shopping_mall":


            levels = [

                {
                    "level": -1,
                    "type": "basement",
                    "units": 1
                },

                {
                    "level": 0,
                    "type": "ground",
                    "units": 1
                },

                {
                    "level": 1,
                    "type": "upper",
                    "units": 1
                }

            ]




        # ==================================================
        # SPACE PROGRAM
        # ==================================================

        if building_type == "house":



            if scale == "small" and floors == 1:


                spaces = {


                    "ground_floor": [

                        "entrance",

                        "living",

                        "kitchen",

                        "bedroom",

                        "bathroom"

                    ]

                }


            else:


                spaces = {


                    "ground_floor": [

                        "entrance",

                        "living",

                        "kitchen",

                        "stairs"

                    ],


                    "typical_floor": [

                        "bedroom",

                        "bathroom"

                    ]

                }



        elif building_type == "shopping_mall":


            spaces = {


                "basement": [

                    "parking",

                    "service",

                    "storage"

                ],


                "ground_floor": [

                    "main_entrance",

                    "mall_lobby",

                    "retail",

                    "food_court",

                    "public_circulation"

                ],


                "typical_floor": [

                    "retail_units",

                    "shops",

                    "escalator",

                    "elevator",

                    "service_core"

                ],


                "roof": [

                    "green_roof",

                    "terrace"

                ]

            }


        elif building_type == "villa":

            spaces = {
                "ground_floor": [],
                "typical_floor": [],
                "site": []
            }

            required_program_spaces = program_data.get(
                "required_spaces",
                []
            )

            if not isinstance(
                required_program_spaces,
                list
            ):
                required_program_spaces = []

            optional_program_spaces = program_data.get(
                "optional_spaces",
                []
            )

            if not isinstance(
                optional_program_spaces,
                list
            ):
                optional_program_spaces = []

            # ==============================================
            # REQUIRED FLOOR-AWARE SPACES
            # ==============================================

            for program_space in required_program_spaces:

                if not isinstance(
                    program_space,
                    dict
                ):
                    continue

                space_name = program_space.get(
                    "name"
                )

                floor_role = program_space.get(
                    "floor"
                )

                zone = program_space.get(
                    "zone"
                )

                if not space_name:
                    continue

                if floor_role == "ground_floor":

                    if space_name not in spaces[
                        "ground_floor"
                    ]:
                        spaces[
                            "ground_floor"
                        ].append(
                            space_name
                        )

                elif floor_role == "upper_floor":

                    if space_name not in spaces[
                        "typical_floor"
                    ]:
                        spaces[
                            "typical_floor"
                        ].append(
                            space_name
                        )

                else:

                    if zone == "external":

                        if space_name not in spaces[
                            "site"
                        ]:
                            spaces[
                                "site"
                            ].append(
                                space_name
                            )

                if zone in zones:

                    if space_name not in zones[
                        zone
                    ]:
                        zones[
                            zone
                        ].append(
                            space_name
                        )

            # ==============================================
            # OPTIONAL SPACES — INTENT DRIVEN ONLY
            # ==============================================

            requested_space_names = set()

            intent_spaces = architectural_intent.get(
                "spaces",
                []
            )

            if isinstance(
                intent_spaces,
                list
            ):

                requested_space_names.update(
                    str(space_name).lower()
                    for space_name in intent_spaces
                    if space_name is not None
                )

            for requirement_name, required in (
                requirements.items()
            ):

                if required is True:
                    requested_space_names.add(
                        str(
                            requirement_name
                        ).lower()
                    )

            for program_space in optional_program_spaces:

                if not isinstance(
                    program_space,
                    dict
                ):
                    continue

                space_name = program_space.get(
                    "name"
                )

                floor_role = program_space.get(
                    "floor"
                )

                zone = program_space.get(
                    "zone"
                )

                if not space_name:
                    continue

                normalized_space_name = str(
                    space_name
                ).lower()

                if normalized_space_name not in (
                    requested_space_names
                ):
                    continue

                if floor_role == "ground_floor":

                    if space_name not in spaces[
                        "ground_floor"
                    ]:
                        spaces[
                            "ground_floor"
                        ].append(
                            space_name
                        )

                elif floor_role == "upper_floor":

                    if space_name not in spaces[
                        "typical_floor"
                    ]:
                        spaces[
                            "typical_floor"
                        ].append(
                            space_name
                        )

                elif zone == "external":

                    if space_name not in spaces[
                        "site"
                    ]:
                        spaces[
                            "site"
                        ].append(
                            space_name
                        )

                if zone in zones:

                    if space_name not in zones[
                        zone
                    ]:
                        zones[
                            zone
                        ].append(
                            space_name
                        )

            # ==============================================
            # PROGRAM RELATIONSHIPS
            # ==============================================

            program_relationships = program_data.get(
                "relationships",
                []
            )

            if isinstance(
                program_relationships,
                list
            ):
                relationships = [
                    dict(relation)
                    for relation in program_relationships
                    if isinstance(
                        relation,
                        dict
                    )
                ]


        elif building_type == "apartment":


            spaces = {


                "ground_floor": [

                    "lobby",

                    "parking",

                    "stairs",

                    "elevator"

                ],



                "typical_floor": [

                    "living",

                    "kitchen",

                    "bedroom",

                    "bathroom"

                ]

            }




        elif building_type == "tower":


            spaces = {


                "ground_floor": [

                    "lobby",

                    "security",

                    "elevator",

                    "stairs"

                ],



                "typical_floor": [

                    "office",

                    "meeting_room",

                    "service"

                ]

            }




        else:


            spaces = {


                "ground_floor": [

                    "entrance"

                ],



                "typical_floor": [

                    "space"

                ]

            }





        # ==================================================
        # REQUIREMENT INJECTION
        # ==================================================

        if requirements["parking"]:


            spaces.setdefault(

                "site",

                []

            )


            if "parking" not in spaces["site"]:


                spaces["site"].append(

                    "parking"

                )




        if requirements["garden"]:


            spaces.setdefault(

                "site",

                []

            )


            if "garden" not in spaces["site"]:


                spaces["site"].append(

                    "garden"

                )




        if requirements["pool"]:


            spaces.setdefault(

                "site",

                []

            )


            if "pool" not in spaces["site"]:


                spaces["site"].append(

                    "pool"

                )




        if requirements["green_roof"]:


            spaces["roof"] = [


                "green_roof",

                "terrace"

            ]





        # ==================================================
        # PLAN REQUIREMENTS CONNECTION V1
        #
        # Explicit program requirements replace generic typology templates at
        # the semantic-plan boundary. Optional suggestions and required spaces
        # whose floor is unknown remain outside the placed floor list.
        # ==================================================

        if plan_requirements:

            requested_relationships = plan_requirements.get(
                "relationships",
                []
            )

            if isinstance(requested_relationships, list):
                relationships = [
                    dict(item)
                    for item in requested_relationships
                    if isinstance(item, dict)
                ]

            required_space_contracts = [
                item
                for item in plan_requirements.get("spaces", [])
                if isinstance(item, dict)
                and item.get("required") is True
            ]

            if required_space_contracts:

                program_source = "plan_requirements"
                spaces = {
                    "ground_floor": [],
                    "typical_floor": [],
                }
                zones = {
                    "public": [],
                    "semi_public": [],
                    "private": [],
                    "service": [],
                    "circulation": [],
                    "external": [],
                }

                semantic_name_map = {
                    "living_room": "living",
                    "living": "living",
                    "kitchen": "kitchen",
                    "bedroom": "bedroom",
                    "bathroom": "bathroom",
                    "stairs": "stairs",
                    "parking": "parking",
                    "workspace": "workspace",
                }
                zone_map = {
                    "living": "public",
                    "kitchen": "semi_public",
                    "bedroom": "private",
                    "bathroom": "service",
                    "stairs": "circulation",
                    "parking": "external",
                    "workspace": "private",
                }

                for requirement in required_space_contracts:

                    space_type = semantic_name_map.get(
                        str(requirement.get("space_type") or "").lower(),
                        str(requirement.get("space_type") or "").lower()
                    )

                    if not space_type:
                        continue

                    requested_count = requirement.get("count")
                    instance_count = (
                        requested_count
                        if isinstance(requested_count, int)
                        and requested_count > 0
                        else 1
                    )

                    if requirement.get("floor_assignment") == "unspecified":

                        if space_type not in unassigned_required_spaces:
                            unassigned_required_spaces.append(space_type)

                        for index in range(instance_count):
                            authoritative_space_instances.append({
                                "instance_id": f"{space_type}_{index + 1}",
                                "space_type": space_type,
                                "planner_floor": None,
                                "floor_assignment_source": "missing_information",
                                "requirement_source": requirement.get("source"),
                            })

                        continue

                    for index in range(instance_count):

                        spaces["ground_floor"].append(space_type)
                        authoritative_space_instances.append({
                            "instance_id": f"{space_type}_{index + 1}",
                            "space_type": space_type,
                            "planner_floor": "ground_floor",
                            "floor_assignment_source": (
                                "user_explicit_single_floor"
                                if floors == 1
                                else "planner_semantic_option_pending_validation"
                            ),
                            "requirement_source": requirement.get("source"),
                        })

                    zone_name = zone_map.get(space_type)
                    if zone_name and space_type not in zones[zone_name]:
                        zones[zone_name].append(space_type)

                # Preserve only explicitly requested legacy site/roof features.
                if requirements.get("garden"):
                    spaces.setdefault("site", []).append("garden")
                if requirements.get("pool"):
                    spaces.setdefault("site", []).append("pool")
                if requirements.get("green_roof"):
                    spaces.setdefault("roof", []).append("green_roof")

                authoritative_plan_program = {
                    "contract": "AuthoritativeSemanticPlanProgramV1",
                    "source": "plan_requirements",
                    "spaces": spaces,
                    "space_instances": authoritative_space_instances,
                    "unassigned_required_spaces": unassigned_required_spaces,
                    "area": plan_requirements.get("area"),
                    "relationships": relationships,
                    "circulation": plan_requirements.get("circulation"),
                    "geometry_validation": plan_requirements.get(
                        "geometry_validation"
                    ),
                }


        # ==================================================
        # COMPLEXITY
        # ==================================================

        if building_type == "house":


            if scale == "small" and floors == 1:


                complexity = "low"


            elif floors <= 2:


                complexity = "medium"


            else:


                complexity = "high"




        elif building_type == "villa":


            complexity = "medium"



        elif building_type in [


            "apartment",

            "tower",

            "shopping_mall"

        ]:


            complexity = "high"



        else:


            complexity = "medium"





        # ==================================================
        # FINAL ARCHITECTURAL INTENT NORMALIZATION
        # ==================================================

        architectural_intent.update({


            "building_type":

                building_type,



            "scale":

                scale,



            "style":

                style,



            "materials":

                materials

        })

        design_option_provenance = {
            "style": {
                "source": style_source,
                "classification": (
                    "explicit_user_request"
                    if style_source == "user_explicit"
                    else "inferred_architectural_option"
                ),
            },
            "materials": {
                "source": materials_source,
                "classification": (
                    "explicit_user_request"
                    if materials_source == "user_explicit"
                    else "inferred_architectural_option"
                ),
            },
        }
        architectural_intent[
            "design_option_provenance"
        ] = design_option_provenance


        # ==================================================
        # FLOOR-AWARE SPACE PROGRAM CONTRACT v1.0
        #
        # Preserve full BuildingProgramKnowledge metadata
        # for every space selected into the final Planner
        # space program.
        #
        # IMPORTANT:
        # - `spaces` remains name-based for backward
        #   compatibility.
        # - `space_program` carries architectural metadata.
        # - Same semantic name may exist on multiple floors.
        # - Final requirement-injected spaces must not be lost.
        # ==================================================

        space_program = []

        space_dimension_resolver = (
            ArchitecturalSpaceDimensionResolver()
        )

        program_space_records = []

        for program_space in (
            program_data.get(
                "required_spaces",
                []
            )
            +
            program_data.get(
                "optional_spaces",
                []
            )
        ):

            if not isinstance(
                program_space,
                dict
            ):
                continue

            program_space_records.append(
                program_space
            )


        seen_space_program_keys = set()
        space_program_occurrence_counts = {}


        for planner_floor_role, floor_spaces in (
            spaces.items()
        ):

            if not isinstance(
                floor_spaces,
                list
            ):
                continue


            if planner_floor_role == "typical_floor":

                knowledge_floor_role = (
                    "upper_floor"
                )

            elif planner_floor_role == "ground_floor":

                knowledge_floor_role = (
                    "ground_floor"
                )

            elif planner_floor_role == "basement":

                knowledge_floor_role = (
                    "basement"
                )

            elif planner_floor_role == "roof":

                knowledge_floor_role = (
                    "roof"
                )

            else:

                # Site/external spaces commonly have no
                # explicit floor in program knowledge.
                knowledge_floor_role = None


            for space_name in floor_spaces:

                if space_name is None:
                    continue


                normalized_space_name = str(
                    space_name
                ).lower()


                occurrence_key = (
                    normalized_space_name,
                    planner_floor_role
                )
                occurrence_index = (
                    space_program_occurrence_counts.get(
                        occurrence_key,
                        0
                    )
                    +
                    1
                )
                space_program_occurrence_counts[
                    occurrence_key
                ] = occurrence_index


                selection_key = (
                    normalized_space_name,
                    planner_floor_role,
                    occurrence_index
                )


                if selection_key in (
                    seen_space_program_keys
                ):
                    continue


                matched_program_space = None


                # ------------------------------------------
                # FIRST PASS
                # Exact name + floor-aware match.
                # ------------------------------------------

                for program_space in (
                    program_space_records
                ):

                    program_name = program_space.get(
                        "name"
                    )

                    if (
                        str(
                            program_name
                        ).lower()
                        !=
                        normalized_space_name
                    ):
                        continue


                    program_floor = program_space.get(
                        "floor"
                    )


                    if (
                        knowledge_floor_role is None
                        and
                        program_floor is None
                    ):

                        matched_program_space = (
                            program_space
                        )

                        break


                    if (
                        knowledge_floor_role is not None
                        and
                        program_floor
                        ==
                        knowledge_floor_role
                    ):

                        matched_program_space = (
                            program_space
                        )

                        break


                # ------------------------------------------
                # SECOND PASS
                # Name-only fallback for spaces whose
                # knowledge record has no explicit floor.
                # ------------------------------------------

                if matched_program_space is None:

                    for program_space in (
                        program_space_records
                    ):

                        program_name = (
                            program_space.get(
                                "name"
                            )
                        )

                        if (
                            str(
                                program_name
                            ).lower()
                            ==
                            normalized_space_name
                        ):

                            matched_program_space = (
                                program_space
                            )

                            break


                if matched_program_space is not None:

                    space_contract = dict(
                        matched_program_space
                    )

                    dimensional_requirements = (
                        matched_program_space.get(
                            "dimensional_requirements"
                        )
                    )

                    if isinstance(
                        dimensional_requirements,
                        dict
                    ):

                        space_contract[
                            "dimensional_requirements"
                        ] = dict(
                            dimensional_requirements
                        )

                else:

                    # --------------------------------------
                    # FINAL SPACE WITHOUT KNOWLEDGE RECORD
                    #
                    # Preserve it rather than inventing
                    # dimensional requirements.
                    # --------------------------------------

                    space_contract = {
                        "name":
                            space_name
                    }


                # Planner floor identity is always explicit
                # even when knowledge has no floor field.
                space_contract[
                    "planner_floor"
                ] = planner_floor_role

                space_contract["instance_index"] = occurrence_index
                space_contract["instance_id"] = (
                    f"{normalized_space_name}_{occurrence_index}"
                )


                if (
                    space_contract.get(
                        "floor"
                    )
                    is None
                    and
                    knowledge_floor_role is not None
                ):

                    space_contract[
                        "floor"
                    ] = knowledge_floor_role


                if not space_contract.get(
                    "zone"
                ):

                    for zone_name, zone_spaces in (
                        zones.items()
                    ):

                        if not isinstance(
                            zone_spaces,
                            list
                        ):
                            continue

                        if space_name in zone_spaces:

                            space_contract[
                                "zone"
                            ] = zone_name

                            break

                dimensional_requirements = (
                    space_contract.get(
                        "dimensional_requirements",
                        {}
                    )
                )

                if isinstance(
                    dimensional_requirements,
                    dict
                ) and dimensional_requirements:

                    space_contract[
                        "original_dimensional_requirements"
                    ] = dict(
                        dimensional_requirements
                    )

                    dimension_result = (
                        space_dimension_resolver.resolve(
                            dimensional_requirements,
                            space_contract.get(
                                "name"
                            ),
                            space_contract.get(
                                "canonical_name",
                                space_contract.get(
                                    "name"
                                )
                            )
                        )
                    )

                    space_contract[
                        "dimensional_requirements"
                    ] = dimension_result.get(
                        "dimensional_requirements",
                        dimensional_requirements
                    )

                    resolved_dimensions = (
                        dimension_result.get(
                            "resolved_dimensions"
                        )
                    )

                    if resolved_dimensions is not None:

                        space_contract[
                            "resolved_dimensions"
                        ] = resolved_dimensions


                space_program.append(
                    space_contract
                )

                seen_space_program_keys.add(
                    selection_key
                )




        # DEBUG

        print(

            "🏛️ FINAL PLANNER ARCHITECTURAL INTENT:",

            architectural_intent

        )




        print(

            "📐 FINAL SPACE PROGRAM:",

            spaces

        )




        print(
            "🔥 PLANNER FINAL FLOORS:",
            floors
        )

        print(
            "🔥 PLANNER FINAL LEVELS:",
            levels
        )

        print(
            "🔥 PLANNER FINAL SPACES:",
            spaces
        )




        # ==================================================
        # FINAL PLAN RETURN
        # ==================================================
        return {


            "intent":

                intent,



            "building_type":

                building_type,



            "floors":

                floors,



            "site":

                site,



            "levels":

                levels,



            "units":

                units,



            "style":

                style,



            "scale":

                scale,



            "materials":

                materials,



            "design_context":

            {

                "style":

                    style,


                "scale":

                    scale


            },



            "requirements":

                requirements,


            "plan_requirements":

                plan_requirements,


            "program_source":

                program_source,


            "authoritative_plan_program":

                authoritative_plan_program,


            "space_instances":

                authoritative_space_instances,


            "unassigned_required_spaces":

                unassigned_required_spaces,


            "circulation":

                plan_requirements.get("circulation")
                if plan_requirements
                else None,


            "geometry_validation":

                plan_requirements.get("geometry_validation")
                if plan_requirements
                else None,


            "design_option_provenance":

                design_option_provenance,



            "spaces":

                spaces,


            "space_program":

                space_program,


            "zones":

                zones,


            "relationships":

                relationships,



            "complexity":

                complexity,



            "strategy":

                "multi_agent_parallel",



            "architectural_intent":

                architectural_intent


        }
