import json
from copy import deepcopy
from pathlib import Path

from core.architecture.knowledge.building_program_knowledge import (
    BuildingProgramKnowledge
)

from core.architecture.reasoning.program_schema_validator import (
    ProgramSchemaValidator
)

from core.architecture.reasoning.space_identity_mapper import (
    SpaceIdentityMapper
)

from core.architecture.knowledge.floor_aware_building_program_v1 import (
    get_floor_aware_program,
    is_floor_aware_type
)

# =============================================================================
# NOT THE PRIMARY ARCHITECTOS PLAN GENERATOR.
# HouseDiffusion is the locked primary plan generator under
# HOUSE_DIFFUSION_GENERATION_POLICY_V1.
# Do not extend this branch as the normal product design path.
#
# Entrypoint: KnowledgeSpaceGenerator.generate  (internal plan synthesis branch)
# Enforced by core/architecture/routing/generation_policy_guard_v1.py
# =============================================================================
ARCHITECTOS_GENERATION_ROLE = "DIAGNOSTIC_OR_EXPLICIT_FALLBACK"
PRODUCTION_PRIMARY = False


class KnowledgeSpaceGenerator:

    VERSION = "1.2"

    def __init__(self):

        print(
            f"🧠 KNOWLEDGE SPACE GENERATOR v{self.VERSION} ONLINE"
        )

        knowledge_path = (
            Path(__file__).resolve().parents[2]
            / "knowledge"
            / "architectural_ontology.json"
        )

        with open(
            knowledge_path,
            "r",
            encoding="utf-8"
        ) as f:

            self.knowledge = json.load(f)

        self.program_knowledge = BuildingProgramKnowledge()

        self.identity_mapper = SpaceIdentityMapper()

        self.program_validator = ProgramSchemaValidator()

    # ==================================================
    # SITE SPACE CONTRACT v1
    #
    # A site-level program space (floor == "site_level") is NOT a
    # building floor space. It is resolved into
    # result["generated_site_spaces"] and never into
    # result["generated_spaces"].
    #
    # Classification is data-driven on the AUTHORITATIVE PROGRAM FLOOR
    # - deliberately NOT a name whitelist - so future site spaces
    # (yard, ramp, ...) are covered without a code change.
    #
    # "site_level" is NOT a building floor and must never be added to
    # allowed_floors, and a site space must never be relocated to a
    # building floor.
    # ==================================================

    SITE_FLOOR = "site_level"
    SITE_PLACEMENT_DOMAIN = "site"

    @classmethod
    def _is_site_level_space(cls, space):

        return (
            isinstance(space, dict)
            and space.get("floor") == cls.SITE_FLOOR
        )

    @classmethod
    def _resolve_site_template(cls, entry, site_space_templates):
        """Resolve a request entry to an authoritative site template.

        An entry requests a site space when its authoritative floor is
        site_level, or when it declares no floor at all and its name matches a
        site_level typology template.

        An entry that explicitly declares a BUILDING floor (for example
        parking @ ground_floor) is never a site space, even when its name
        matches a site template.
        """

        if isinstance(entry, dict):
            name = entry.get("name")
            floor = entry.get("floor")
        else:
            name = entry
            floor = None

        if not name:
            return None

        if floor and floor != cls.SITE_FLOOR:
            return None

        return site_space_templates.get(str(name).lower())

    def _build_site_space(self, template, space_ontology):
        """Build one site-space semantic record from an authoritative template.

        Mirrors semantic space generation: the same core fields, the same
        identity enrichment, and the same verbatim merge of extra
        authoritative program metadata.
        """

        space_name = template.get("name")

        canonical_name = self.identity_mapper.canonicalize(
            space_name
        )

        ontology = space_ontology.get(
            canonical_name,
            {}
        )

        zone = template.get("zone") or ontology.get("zone")

        architectural_intent = template.get(
            "architectural_intent",
            {}
        )

        if not isinstance(architectural_intent, dict):
            architectural_intent = {}

        # protected_zone may be declared at the top level or inside
        # architectural_intent (villa parking declares it inside). Preserve
        # whichever authoritative value is available.
        protected_zone = template.get("protected_zone")

        if protected_zone is None:
            protected_zone = architectural_intent.get(
                "protected_zone",
                False
            )

        site_space = {
            "name": space_name,
            "canonical_name": canonical_name,
            "zone": zone,
            "space_type": ontology.get("space_type"),
            "access": list(ontology.get("access", [])),
            "adjacent_to": list(ontology.get("adjacent_to", [])),
            "floor": self.SITE_FLOOR,
            "dimensional_requirements": dict(
                template.get("dimensional_requirements", {})
            ),
            "environmental_requirements": dict(
                template.get("environmental_requirements", {})
            ),
            "privacy_requirements": dict(
                template.get("privacy_requirements", {})
            ),
            "architectural_intent": dict(architectural_intent),
            "spatial_intent": {},
            "access_requirements": dict(
                template.get("access_requirements", {})
            ),
            "protected_zone": bool(protected_zone),
            "circulation_profile": template.get("circulation_profile"),
            "role": template.get("role"),
            "resolved_dimensions": template.get("resolved_dimensions"),
            "placement_domain": self.SITE_PLACEMENT_DOMAIN,
        }

        site_space = (
            self.identity_mapper
            .enrich_space_identity(site_space)
        )

        # PRESERVE EXTRA PROGRAM METADATA
        #
        # Same philosophy as semantic space generation: keep authoritative
        # keys such as placement_scope, access_requirement or
        # floor_constraints rather than dropping them.
        for key, value in template.items():

            if key not in site_space:

                site_space[key] = value

        # The site contract is authoritative about these two fields.
        site_space["floor"] = self.SITE_FLOOR
        site_space["placement_domain"] = self.SITE_PLACEMENT_DOMAIN

        return site_space

    # ==================================================
    # GENERATE SEMANTIC SPACES
    # ==================================================

    def generate(
        self,
        intent
    ):

        result = {

            "generated_spaces": [],

            # SITE SPACE CONTRACT v1
            #
            # Semantic spaces whose authoritative program floor is
            # "site_level". They are deliberately kept OUT of
            # generated_spaces, which continues to represent
            # building / floor architectural spaces only.
            "generated_site_spaces": [],

            "relationships": [],

            "source":
                "building_program_knowledge"

        }

        building_type = intent.get(
            "building_type"
        )

        functions = intent.get(
            "functions",
            []
        )


        if not isinstance(
            functions,
            list
        ):

            functions = []

        requirements = intent.get(
            "requirements",
            []
        )

        if not isinstance(
            requirements,
            list
        ):

            requirements = []

        # ==================================================
        # PROGRAM KNOWLEDGE
        # ==================================================

        program_data = self.program_knowledge.get_program(
            building_type,
            functions
        )

        if not program_data:

            # FLOOR-AWARE BUILDING PROGRAM EXTENSION (ARCH-PROGRAM-01)
            #
            # Additive only. The extension answers for the building domains it
            # defines (apartment, shop, retail, office, gym, storage). Every
            # building type already served by BuildingProgramKnowledge is
            # untouched, so generated_spaces / generated_site_spaces and the
            # Architectural Spatial Contract stay compatible.
            if is_floor_aware_type(
                building_type
            ):

                program_data = get_floor_aware_program(
                    building_type,
                    functions
                )

        if not program_data:
            return result


        validation = self.program_validator.validate(
            program_data
        )

        if not validation.get("valid"):

            print(
                "❌ PROGRAM SCHEMA INVALID:",
                validation.get("errors", [])
            )

            return result

        program_data = deepcopy(program_data)
        if intent.get("explicit_program_complete") is True:
            # The project contract declares its supplied room list complete;
            # typology templates must not silently add extra required rooms.
            program_data["required_spaces"] = []
            program_data["optional_spaces"] = []
        typology_space_templates = deepcopy(
            (program_data.get("required_spaces", []) or [])
            + (program_data.get("optional_spaces", []) or [])
        )

        # ==================================================
        # SITE SPACE TEMPLATES (PRE-FLOOR-FILTER)
        #
        # Captured BEFORE the allowed_floors filter below, because that
        # filter removes every site_level space from optional_spaces.
        # This is the only authoritative copy of the site templates.
        #
        # The building-floor filter itself is deliberately NOT changed.
        # ==================================================

        site_space_templates = {}

        site_required_names = set()

        for template in typology_space_templates:

            if not self._is_site_level_space(template):
                continue

            template_name = template.get("name")

            if not template_name:
                continue

            site_space_templates.setdefault(
                str(template_name).lower(),
                template
            )

        for template in (program_data.get("required_spaces", []) or []):

            if not self._is_site_level_space(template):
                continue

            template_name = template.get("name")

            if template_name:

                site_required_names.add(
                    str(template_name).lower()
                )

        levels = intent.get("levels", {})
        levels = levels if isinstance(levels, dict) else {}
        above_ground = levels.get("above_ground")
        basement_count = levels.get("basement", 0) or 0
        mezzanine_count = levels.get("mezzanine", 0) or 0

        try:
            above_ground = int(above_ground)
            basement_count = int(basement_count)
            mezzanine_count = int(mezzanine_count)
        except (TypeError, ValueError):
            above_ground = None

        allowed_floors = {"ground_floor"}

        # "site_level" is deliberately NOT a building floor and is NOT added
        # here. A site-level space is preserved by the PRE-FILTER site
        # template capture above and resolved through
        # generated_site_spaces, so the building-floor filter below needs no
        # site special case and no name list.
        if isinstance(above_ground, int) and above_ground > 1:
            allowed_floors.add("upper_floor")
        if basement_count > 0:
            allowed_floors.add("basement")
        if mezzanine_count > 0:
            allowed_floors.add("mezzanine")

        explicit_space_names = {
            str(item.get("name") if isinstance(item, dict) else item).lower()
            for item in intent.get("spaces", []) or []
        }
        explicit_stair = bool(
            {"stair", "stairs", "راه پله", "راه‌پله"} & explicit_space_names
            or (intent.get("vertical_transport", {}) or {}).get("stairs")
        )
        vertical_transition_exists = (
            (isinstance(above_ground, int) and above_ground > 1)
            or basement_count > 0
            or mezzanine_count > 0
        )

        filtered_required = []
        for program_space in program_data.get("required_spaces", []) or []:
            if not isinstance(program_space, dict):
                continue
            floor = program_space.get("floor")
            if floor and floor not in allowed_floors:
                continue
            if (
                program_space.get("name") == "stairs"
                and not vertical_transition_exists
                and not explicit_stair
            ):
                continue
            item = dict(program_space)
            if item.get("name") == "stairs" and vertical_transition_exists:
                if basement_count > 0 and above_ground == 1 and not mezzanine_count:
                    connects = ["basement", "ground_floor"]
                elif mezzanine_count > 0 and above_ground == 1:
                    connects = ["ground_floor", "mezzanine"]
                else:
                    connects = ["ground_floor", "upper_floor"]
                item["connects"] = connects
                item["vertical_connection"] = {
                    "type": "stairs",
                    "status": "resolved_from_explicit_level_evidence",
                    "connects": list(connects),
                }
            filtered_required.append(item)
        program_data["required_spaces"] = filtered_required
        program_data["optional_spaces"] = [
            item for item in program_data.get("optional_spaces", []) or []
            if not isinstance(item, dict)
            or not item.get("floor")
            or item.get("floor") in allowed_floors
        ]

        if basement_count > 0 and not any(
            isinstance(item, dict) and item.get("floor") == "basement"
            for item in program_data["required_spaces"]
        ):
            program_data["required_spaces"].append({
                "name": "basement",
                "zone": "service",
                "floor": "basement",
                "source": "explicit_basement_level_evidence",
            })
        if mezzanine_count > 0 and not any(
            isinstance(item, dict) and item.get("floor") == "mezzanine"
            for item in program_data["required_spaces"]
        ):
            program_data["required_spaces"].append({
                "name": "mezzanine",
                "zone": "semi_public",
                "floor": "mezzanine",
                "source": "explicit_mezzanine_level_evidence",
            })

        result["floor_authority"] = {
            "status": "resolved_from_architectural_intent_levels",
            "allowed_floors": sorted(allowed_floors),
            "above_ground": above_ground,
            "basement": basement_count,
            "mezzanine": mezzanine_count,
        }

        # ==================================================
        # ONTOLOGY
        # ==================================================

        space_ontology = self.knowledge.get(
            "spaces",
            {}
        )

        # ==================================================
        # REQUIRED / OPTIONAL SPACE SELECTION
        #
        # IMPORTANT:
        # Keep the full program-space record.
        #
        # Space identity is not only the name.
        # The same semantic space may exist on
        # multiple floors:
        #
        # corridor @ ground_floor
        # corridor @ upper_floor
        #
        # Therefore selection must preserve:
        #     name + floor + program data
        # ==================================================

        selected_spaces = []

        selected_keys = set()

        # ==================================================
        # PRE-ADAPTED ARCHITECTURAL SPACES
        # Preserve upstream semantic contracts
        # ==================================================

        upstream_spaces = intent.get(
            "spaces",
            []
        )

        if isinstance(
            upstream_spaces,
            list
        ):

            for space in upstream_spaces:

                if not isinstance(
                    space,
                    dict
                ):
                    continue

                if not space.get(
                    "name"
                ):
                    continue

                # SITE SPACE CONTRACT v1
                #
                # A site-level request is resolved through
                # generated_site_spaces, never appended here as a
                # building space.
                if self._resolve_site_template(
                    space,
                    site_space_templates
                ):
                    continue

                selected_spaces.append(
                    dict(space)
                )

                selected_keys.add(
                    (
                        space.get(
                            "name"
                        ),
                        space.get(
                            "floor"
                        )
                    )
                )

        for space in program_data.get(
            "required_spaces",
            []
        ):

            if not isinstance(
                space,
                dict
            ):

                continue

            name = space.get(
                "name"
            )

            floor = space.get(
                "floor"
            )

            if not name:

                continue

            selection_key = (
                name,
                floor
            )

            if selection_key in selected_keys:

                continue

            selected_spaces.append(
                dict(space)
            )

            selected_keys.add(
                selection_key
            )

        # ==================================================
        # OPTIONAL SPACES
        # ONLY WHEN REQUESTED
        # ==================================================

        normalized_requirements = {

            str(item).lower()

            for item in requirements

            if item is not None

        }

        for space in program_data.get(
            "optional_spaces",
            []
        ):

            if not isinstance(
                space,
                dict
            ):

                continue

            name = space.get(
                "name"
            )

            floor = space.get(
                "floor"
            )

            if not name:

                continue

            if str(name).lower() not in normalized_requirements:

                continue

            selection_key = (
                name,
                floor
            )

            if selection_key in selected_keys:

                continue

            selected_spaces.append(
                dict(space)
            )

            selected_keys.add(
                selection_key
            )

        # ==================================================
        # EXPLICIT INTENT SPACES
        # ==================================================
        #
        # Spaces explicitly requested by ArchitecturalIntent
        # must not be lost simply because they are not present
        # in BuildingProgramKnowledge.required_spaces or
        # optional_spaces.
        #
        # Priority:
        #
        # 1. Reuse full program-space metadata when available.
        # 2. Otherwise preserve the explicit requested space.
        # 3. Resolve its zone from intent["zones"] when possible.
        #
        # This keeps BuildingProgramKnowledge as the typology
        # knowledge source without allowing it to erase explicit
        # user / ontology requirements.
        # ==================================================

        explicit_spaces = intent.get(
            "spaces",
            []
        )


        if not isinstance(
            explicit_spaces,
            list
        ):

            explicit_spaces = []


        intent_zones = intent.get(
            "zones",
            {}
        )


        if not isinstance(
            intent_zones,
            dict
        ):

            intent_zones = {}


        program_space_index = {}


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


            program_name = program_space.get(
                "name"
            )


            if not program_name:

                continue


            program_space_index[
                str(
                    program_name
                ).lower()
            ] = program_space

        # Explicitly requested spaces may reuse typology dimensions even when
        # their typical floor was filtered out by an authoritative one-storey
        # contract.  The floor assignment is relocated to the confirmed ground
        # level; the rejected upper-floor default is not restored.
        for template in typology_space_templates:
            if not isinstance(template, dict) or not template.get("name"):
                continue
            template_name = str(template["name"]).lower()
            if template_name not in explicit_space_names:
                continue
            # SITE SPACE CONTRACT v1
            #
            # A site-level space must NEVER be relocated onto a building
            # floor. It is resolved through generated_site_spaces instead.
            if self._is_site_level_space(template):
                continue
            relocated = dict(template)
            if relocated.get("floor") not in allowed_floors:
                relocated["floor"] = "ground_floor"
                relocated["floor_assignment_source"] = (
                    "explicit_storey_count_overrides_typology_default"
                )
            program_space_index[template_name] = relocated


        # ==================================================
        # EXPLICIT SPACE OVERRIDE INDEX
        #
        # FloorProgramKnowledgeAdapter /
        # ArchitecturalIntent metadata
        # has higher priority than typology defaults.
        #
        # Explicit ArchitecturalIntent spaces are indexed
        # separately and can override program knowledge.
        # ==================================================

        explicit_name = None
        explicit_name_lower = None
        explicit_space = None


        for explicit_space in explicit_spaces:

            if not isinstance(
                explicit_space,
                dict
            ):

                continue


            explicit_name = explicit_space.get(
                "name"
            )


            if not explicit_name:

                continue


            program_space_index[
                str(
                    explicit_name
                ).lower()
            ] = explicit_space



        # ==================================================
        # NORMALIZE EXPLICIT SPACE ITERATION STATE
        #
        # This state is consumed by:
        #
        # - canonical identity resolution
        # - semantic duplicate detection
        # - program space reuse
        #
        # It must NOT run inside program_space_index build.
        # ==================================================

        for explicit_space in explicit_spaces:

            if isinstance(
                explicit_space,
                dict
            ):

                explicit_name = explicit_space.get(
                    "name"
                )

            else:

                explicit_name = explicit_space

            # SITE SPACE CONTRACT v1
            #
            # Site-level requests - both "parking" and {"name": "parking"} -
            # are resolved through generated_site_spaces. Skipping them here
            # keeps them out of selected_spaces and prevents the ground_floor
            # default below from ever applying to a site space.
            if self._resolve_site_template(
                explicit_space,
                site_space_templates
            ):
                continue


            if not explicit_name:

                continue


            explicit_name = str(
                explicit_name
            )


            explicit_name_lower = explicit_name.lower()

            # ----------------------------------------------
            # CANONICAL IDENTITY
            # ----------------------------------------------

            if explicit_name:

                explicit_canonical_name = (
                    self.identity_mapper.canonicalize(
                        explicit_name
                    )
                )

            else:

                explicit_canonical_name = None


            # ----------------------------------------------
            # CHECK IF SEMANTIC SPACE ALREADY SELECTED
            #
            # Example:
            #
            #     living
            #         canonical_name = living_room
            #
            # must satisfy an explicit request for:
            #
            #     living_room
            #
            # without generating a duplicate space.
            # ----------------------------------------------

            already_selected = False
            selected_match = None


            for selected_space in selected_spaces:

                if not isinstance(
                    selected_space,
                    dict
                ):

                    continue


                selected_name = selected_space.get(
                    "name"
                )


                if not selected_name:

                    continue


                selected_canonical_name = (
                    self.identity_mapper.canonicalize(
                        selected_name
                    )
                )


                if (
                    str(
                        selected_canonical_name
                    ).lower()
                    ==
                    str(
                        explicit_canonical_name
                    ).lower()
                ):

                    already_selected = True
                    selected_match = selected_space

                    break


            if already_selected:

                # Explicit ArchitecturalIntent is allowed to complete an
                # existing program-space contract (notably a basement whose
                # geometry cannot be invented by typology knowledge).  Keep
                # program semantics, but preserve authoritative dimensions
                # and placement evidence supplied by the project.
                if (
                    isinstance(explicit_space, dict)
                    and isinstance(selected_match, dict)
                ):

                    for key in (
                        "dimensional_requirements",
                        "resolved_dimensions",
                        "floor_constraints",
                        "placement_scope",
                        "access_requirement",
                        "role",
                        "protected_zone",
                    ):

                        if key in explicit_space:

                            value = explicit_space.get(key)
                            selected_match[key] = (
                                dict(value)
                                if isinstance(value, dict)
                                else value
                            )

                continue


            # ----------------------------------------------
            # REUSE PROGRAM KNOWLEDGE WHEN AVAILABLE
            # ----------------------------------------------

            known_program_space = None

            if explicit_name_lower:

                known_program_space = program_space_index.get(
                    explicit_name_lower
                )


            if known_program_space is not None:

                print(
                    "### ENTER KNOWN PROGRAM SPACE ###"
                )

                print(
                    "DEBUG KNOWN PROGRAM SPACE:",
                    known_program_space
                )

                print(
                    "DEBUG EXPLICIT SPACE:",
                    explicit_space
                )

                merged_program_space = dict(
                    known_program_space
                )


                if isinstance(
                    explicit_space,
                    dict
                ):

                    for key, value in explicit_space.items():

                        if key not in merged_program_space:

                            merged_program_space[key] = value


                        elif key in {
                            "protected_zone",
                            "circulation_profile",
                            "role",
                            "resolved_dimensions"
                        }:

                            merged_program_space[key] = value


                selected_spaces.append(
                    merged_program_space
                )


                selected_keys.add(
                    (
                        merged_program_space.get(
                            "name"
                        ),
                        merged_program_space.get(
                            "floor"
                        )
                    )
                )


                continue


            # ----------------------------------------------
            # RESOLVE ZONE FROM ARCHITECTURAL INTENT
            # ----------------------------------------------

            resolved_zone = None


            for zone_name, zone_spaces in intent_zones.items():

                if not isinstance(
                    zone_spaces,
                    list
                ):

                    continue


                normalized_zone_spaces = {

                    str(
                        item
                    ).lower()

                    for item in zone_spaces

                    if item is not None

                }


                if explicit_name_lower in normalized_zone_spaces:

                    resolved_zone = zone_name

                    break

            # ----------------------------------------------
            # PRESERVE UNKNOWN BUT EXPLICIT SPACE
            #
            # Explicit ArchitecturalIntent metadata has
            # authority over fallback semantic defaults.
            #
            # Unknown spaces must therefore preserve any
            # explicit floor / ownership / dimensional data
            # instead of being reduced to name + zone.
            # ----------------------------------------------

            if isinstance(
                explicit_space,
                dict
            ):

                explicit_program_space = dict(
                    explicit_space
                )

            else:

                explicit_program_space = {
                    "name":
                        explicit_name
                }


            explicit_program_space[
                "name"
            ] = explicit_name


            if not explicit_program_space.get(
                "zone"
            ):

                explicit_program_space[
                    "zone"
                ] = resolved_zone


            if not explicit_program_space.get("floor"):
                explicit_program_space["floor"] = "ground_floor"


            explicit_program_space.setdefault(
                "dimensional_requirements",
                {}
            )


            selected_spaces.append(
                explicit_program_space
            )


            selected_keys.add(
                (
                    explicit_name,
                    explicit_program_space.get(
                        "floor"
                    )
                )
            )
        # ==================================================
        # SITE SPACE CONTRACT v1
        #
        # Site-level spaces are emitted HERE, from the PRE-FILTER
        # templates, and never enter selected_spaces /
        # generated_spaces.
        #
        # Request channels:
        #   intent["requirements"]  -> normalized_requirements
        #   intent["spaces"]        -> explicit_space_names
        #
        # Required site-level templates are always emitted, so a future
        # required site space cannot be silently lost.
        #
        # Deduplication identity is (name, floor): a space requested
        # through BOTH channels appears exactly once.
        # ==================================================

        # SITE SPACE INVARIANT
        #
        # A site-level space must NEVER be a building space. Any site-level
        # entry that reached selected_spaces is removed here; it is still
        # emitted through generated_site_spaces below, because the site
        # templates are captured BEFORE building-floor filtering.
        #
        # This invariant is what makes the contract independent of HOW a
        # site space survived the building-floor filter. It deliberately
        # overrides any name-based allowance, because site classification is
        # data-driven on the authoritative program floor, never on names.
        selected_spaces = [
            space
            for space in selected_spaces
            if not self._is_site_level_space(space)
        ]

        site_requests = set(
            normalized_requirements
        ) | set(
            explicit_space_names
        )

        site_selected = []

        site_keys = set()

        for site_template_name, site_template in site_space_templates.items():

            if (
                site_template_name not in site_requests
                and site_template_name not in site_required_names
            ):
                continue

            site_space = self._build_site_space(
                site_template,
                space_ontology
            )

            site_key = (
                site_space.get("name"),
                site_space.get("floor")
            )

            if site_key in site_keys:
                continue

            site_keys.add(site_key)

            site_selected.append(site_space)

        result["generated_site_spaces"] = site_selected

        # ==================================================
        # SEMANTIC SPACE GENERATION
        # ==================================================

        for program_space in selected_spaces:

            space_name = program_space.get(
                "name"
            )

            if not space_name:

                continue

            # ----------------------------------------------
            # ONTOLOGY ENRICHMENT
            # ----------------------------------------------

            canonical_name = self.identity_mapper.canonicalize(
                space_name
            )


            ontology = space_ontology.get(
                canonical_name,
                {}
            )

            # ----------------------------------------------
            # PRESERVE PROGRAM DATA
            # ----------------------------------------------

            zone = program_space.get(
                "zone"
            )

            if not zone:

                zone = ontology.get(
                    "zone"
                )

            floor = program_space.get(
                "floor"
            )

            dimensional_requirements = dict(
                program_space.get(
                    "dimensional_requirements",
                    {}
                )
            )

            semantic_space = {

                "name":
                    space_name,

                "canonical_name":
                    canonical_name,

                "zone":
                    zone,

                "space_type":
                    # Program knowledge owns space_type when it declares one;
                    # the ontology remains the fallback. No existing program
                    # space declares space_type, so this is additive.
                    program_space.get(
                        "space_type"
                    )
                    or ontology.get(
                        "space_type"
                    ),

                "access":
                    list(
                        ontology.get(
                            "access",
                            []
                        )
                    ),

                "adjacent_to":
                    list(
                        ontology.get(
                            "adjacent_to",
                            []
                        )
                    ),

                "floor":
                    floor,

                "dimensional_requirements":
                    dimensional_requirements,

                "environmental_requirements":
                    dict(
                        program_space.get(
                            "environmental_requirements",
                            {}
                        )
                    ),

                "privacy_requirements":
                    dict(
                        program_space.get(
                            "privacy_requirements",
                            {}
                        )
                    ),

                "architectural_intent":
                    dict(
                        program_space.get(
                            "architectural_intent",
                            {}
                        )
                    ),

                "spatial_intent":
                    {},


                "access_requirements":
                    dict(
                        program_space.get(
                            "access_requirements",
                            {}
                        )
                    ),

                "protected_zone":
                    bool(
                        program_space.get(
                            "protected_zone",
                            False
                        )
                    ),

                "environmental_requirements":

                    dict(
                        program_space.get(
                            "environmental_requirements",
                            {}
                        )
                    ),

                "circulation_profile":
                    program_space.get(
                        "circulation_profile"
                    ),

                "role":
                    program_space.get(
                        "role"
                    ),

                "resolved_dimensions":
                    program_space.get(
                        "resolved_dimensions"
                    )

            }

            # ==================================================
            # SPACE IDENTITY ARCHITECTURAL INTENT BRIDGE v1.0
            #
            # Convert BuildingProgramKnowledge intent into
            # spatial identity intelligence.
            # ==================================================

            semantic_space = (
                self.identity_mapper
                .enrich_space_identity(
                    semantic_space
                )
            )



            # ----------------------------------------------
            # PRESERVE EXTRA PROGRAM METADATA
            #
            # Keep future architectural contracts such as:
            # placement_scope
            # spatial_ownership
            # site_relation
            # adaptive_reuse constraints
            #
            # without expanding this mapper every time.
            # ----------------------------------------------

            for key, value in program_space.items():

                if key not in semantic_space:

                    semantic_space[
                        key
                    ] = value

            result[
                "generated_spaces"
            ].append(
                semantic_space
            )

        # ==================================================
        # RELATIONSHIPS
        # ==================================================
        #
        # Relationship knowledge has two valid sources:
        #
        # 1. BuildingProgramKnowledge
        # 2. Explicit ArchitecturalIntent / Ontology
        #
        # Program knowledge must not erase explicit semantic
        # relationships requested or inferred upstream.
        #
        # Relationship endpoints are normalized back to the
        # actual generated-space names so canonical aliases
        # such as:
        #
        #     living_room -> living
        #
        # remain connected to real plan spaces.
        # ==================================================

        generated_names = set()

        generated_names_by_canonical = {}


        for generated_space in result.get(
            "generated_spaces",
            []
        ):

            if not isinstance(
                generated_space,
                dict
            ):

                continue


            generated_name = generated_space.get(
                "name"
            )


            canonical_name = generated_space.get(
                "canonical_name"
            )


            if not generated_name:

                continue


            generated_name_key = str(
                generated_name
            ).lower()


            generated_names.add(
                generated_name_key
            )


            if not canonical_name:

                canonical_name = (
                    self.identity_mapper.canonicalize(
                        generated_name
                    )
                )


            canonical_key = str(
                canonical_name
            ).lower()


            generated_names_by_canonical.setdefault(
                canonical_key,
                []
            ).append(
                generated_name
            )


        def resolve_relationship_endpoint(
            endpoint
        ):

            if endpoint is None:

                return None


            endpoint_name = str(
                endpoint
            )


            endpoint_key = endpoint_name.lower()


            # ------------------------------------------
            # INSTANCE IDENTITY HAS FIRST PRIORITY
            #
            # If the relationship already references
            # a real generated-space name, preserve it.
            #
            # Example:
            #
            #     master_bedroom
            #
            # must not collapse into:
            #
            #     bedroom
            # ------------------------------------------

            if endpoint_key in generated_names:

                return endpoint_name


            # ------------------------------------------
            # CANONICAL ALIAS RESOLUTION
            #
            # Only use canonical identity when the
            # endpoint is not already an exact
            # generated-space instance name.
            # ------------------------------------------

            canonical_name = (
                self.identity_mapper.canonicalize(
                    endpoint_name
                )
            )


            canonical_key = str(
                canonical_name
            ).lower()


            candidates = (
                generated_names_by_canonical.get(
                    canonical_key,
                    []
                )
            )


            # ------------------------------------------
            # SAFE CANONICAL RESOLUTION
            #
            # Canonical alias may resolve automatically
            # only when it identifies exactly one real
            # generated-space instance.
            #
            # Multiple candidates are ambiguous and must
            # not collapse graph identity.
            # ------------------------------------------

            if len(candidates) == 1:

                return candidates[0]


            return endpoint_name


        relationship_sources = []


        program_relationships = program_data.get(
            "relationships",
            []
        )


        if isinstance(
            program_relationships,
            list
        ):

            relationship_sources.extend(
                program_relationships
            )


        intent_relationships = intent.get(
            "relationships",
            []
        )


        if isinstance(
            intent_relationships,
            list
        ):

            relationship_sources.extend(
                intent_relationships
            )

        # ==================================================
        # SEMANTIC ADJACENCY → RELATIONSHIP EVIDENCE v1.0
        #
        # `adjacent_to` belongs to semantic space knowledge.
        # Convert it into graph relationship evidence only
        # when no explicit Program/Intent relationship already
        # exists between the same pair.
        #
        # IMPORTANT:
        # - Explicit relationships always win.
        # - Do not duplicate reverse relationships.
        # - Do not invent endpoints that are not generated.
        # ==================================================

        explicit_relationship_pairs = set()

        for relation in relationship_sources:

            if not isinstance(
                relation,
                dict
            ):

                continue

            relation_from = resolve_relationship_endpoint(
                relation.get(
                    "from"
                )
            )

            relation_to = resolve_relationship_endpoint(
                relation.get(
                    "to"
                )
            )

            if not relation_from or not relation_to:

                continue

            explicit_relationship_pairs.add(
                frozenset(
                    [
                        relation_from,
                        relation_to
                    ]
                )
            )

        for generated_space in result.get(
            "generated_spaces",
            []
        ):

            if not isinstance(
                generated_space,
                dict
            ):

                continue

            source_name = generated_space.get(
                "name"
            )

            if not source_name:

                continue

            adjacent_names = generated_space.get(
                "adjacent_to",
                []
            )

            if not isinstance(
                adjacent_names,
                list
            ):

                continue

            for adjacent_name in adjacent_names:

                relation_from = (
                    resolve_relationship_endpoint(
                        source_name
                    )
                )

                relation_to = (
                    resolve_relationship_endpoint(
                        adjacent_name
                    )
                )

                if not relation_from or not relation_to:

                    continue

                if relation_from == relation_to:

                    continue

                # Endpoint must resolve to a real generated
                # space instance/name.
                if (
                    str(
                        relation_from
                    ).lower()
                    not in generated_names
                    or
                    str(
                        relation_to
                    ).lower()
                    not in generated_names
                ):

                    continue

                relationship_pair = frozenset(
                    [
                        relation_from,
                        relation_to
                    ]
                )

                # Explicit Program/Intent relationship has
                # higher authority than semantic adjacency.
                if relationship_pair in explicit_relationship_pairs:

                    continue

                relationship_sources.append(
                    {
                        "from":
                            relation_from,

                        "to":
                            relation_to,

                        "type":
                            "semantic_adjacent",

                        "source":
                            "space_ontology_adjacent_to"
                    }
                )

                explicit_relationship_pairs.add(
                    relationship_pair
                )


        relationship_keys = set()


        for relation in relationship_sources:

            if not isinstance(
                relation,
                dict
            ):

                continue


            relation_from = (
                resolve_relationship_endpoint(
                    relation.get(
                        "from"
                    )
                )
            )


            relation_to = (
                resolve_relationship_endpoint(
                    relation.get(
                        "to"
                    )
                )
            )


            relation_type = relation.get(
                "type"
            )


            if not relation_from or not relation_to:

                continue


            relationship_key = (
                relation_from,
                relation_to,
                relation_type
            )


            if relationship_key in relationship_keys:

                continue


            normalized_relation = dict(
                relation
            )


            normalized_relation[
                "from"
            ] = relation_from


            normalized_relation[
                "to"
            ] = relation_to


            result[
                "relationships"
            ].append(
                normalized_relation
            )


            relationship_keys.add(
                relationship_key
            )


        return result
