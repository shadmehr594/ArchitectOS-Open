"""
ArchitectOS IFC Containment Builder V2.1

Architecture-driven IFC spatial containment.

Architectural Semantic Context
            |
            v
       Level Registry
            |
            v
    IFC Building Storeys
            |
            +-- IfcSpace
            +-- IfcWall
            +-- IfcSlab
            +-- IfcWindow
            +-- IfcDoor
            +-- IfcStair
            +-- IfcRoof

Design Principle
----------------
Containment MUST be derived from the Architectural Semantic Context.

This builder MUST NOT infer levels from:

- entity names
- entity ids
- geometry coordinates
- element ordering

If an architectural element has no semantic level,
it remains uncontained rather than being assigned
to an arbitrary storey.
"""

import ifcopenshell


class IFCContainmentBuilderV1:

    VERSION = "2.1"

    SUPPORTED_TYPES = (

        "IfcSpace",

        "IfcWall",

        "IfcSlab",

        "IfcWindow",

        "IfcDoor",

        "IfcStair",

        "IfcRoof",

    )

    def __init__(
        self,
        model,
        semantic_context=None,
        entity_levels=None
    ):

        self.model = model

        self.semantic_context = (
            semantic_context
            or {}
        )

        self.entity_levels = (
            entity_levels
            if isinstance(
                entity_levels,
                dict
            )
            else {}
        )

        print(
            f"IFC CONTAINMENT BUILDER v{self.VERSION} ONLINE"
        )


    # ======================================
    # BUILD
    # ======================================

    def build(
        self,
        semantic_context=None,
        entity_levels=None
    ):

        if semantic_context is not None:

            self.semantic_context = (
                semantic_context
                or {}
            )

        if entity_levels is not None:

            self.entity_levels = (
                entity_levels
                if isinstance(
                    entity_levels,
                    dict
                )
                else {}
            )

        storeys = self.model.by_type(
            "IfcBuildingStorey"
        )

        if not storeys:

            print(
                "NO IFC BUILDING STOREYS FOUND"
            )

            return []

        print(
            "\n=== IFC SEMANTIC CONTAINMENT ==="
        )

        # ==================================
        # STOREY INDEX
        # ==================================

        storey_by_level = (
            self._build_storey_index(
                storeys
            )
        )

        if not storey_by_level:

            print(
                "STOREY INDEX IS EMPTY"
            )

            return []

        # ==================================
        # SEMANTIC LEVEL INDEX
        # ==================================

        level_by_name = (
            self._build_semantic_level_index()
        )

        print(
            "\n=== SEMANTIC ENTITY LEVEL INDEX ==="
        )

        for name, level in (
            level_by_name.items()
        ):

            print(
                "ENTITY:",
                name,
                "->",
                level
            )

        # ==================================
        # BUILD TARGET CONTAINMENT
        # ==================================

        entity_by_level = {}

        for ifc_type in self.SUPPORTED_TYPES:

            entities = self.model.by_type(
                ifc_type
            )

            for entity in entities:

                name = getattr(
                    entity,
                    "Name",
                    None
                )

                if not name:

                    continue

                level = level_by_name.get(
                    name
                )

                # --------------------------------
                # No semantic level = no inference
                # --------------------------------

                if not level:

                    print(
                        "SKIP UNRESOLVED LEVEL:",
                        ifc_type,
                        name
                    )

                    continue

                storey = storey_by_level.get(
                    level
                )

                if not storey:

                    print(
                        "SKIP UNKNOWN STOREY:",
                        ifc_type,
                        name,
                        "->",
                        level
                    )

                    continue

                entity_by_level.setdefault(
                    level,
                    []
                ).append(
                    entity
                )

                print(
                    ifc_type + ":",
                    name,
                    "->",
                    level
                )

        # ==================================
        # SYNCHRONIZE RELATIONS
        # ==================================

        relations = []

        for level, elements in (
            entity_by_level.items()
        ):

            storey = storey_by_level.get(
                level
            )

            if not storey:

                continue

            unique_elements = (
                self._unique_entities(
                    elements
                )
            )

            if not unique_elements:

                continue

            relation = (
                self._get_or_create_relation(
                    storey
                )
            )

            # --------------------------------
            # Remove these entities from
            # previous storey containment
            # --------------------------------

            self._remove_from_other_storeys(
                unique_elements,
                storey
            )

            # --------------------------------
            # Merge with current relation
            # --------------------------------

            existing_elements = list(
                getattr(
                    relation,
                    "RelatedElements",
                    None
                )
                or []
            )

            merged = (
                self._unique_entities(
                    existing_elements
                    +
                    unique_elements
                )
            )

            relation.RelatedElements = (
                merged
            )

            relations.append(
                relation
            )

            print(
                "SYNCED CONTAINMENT:",
                level,
                "ELEMENTS:",
                len(
                    merged
                )
            )

        # ==================================
        # FINAL DEBUG
        # ==================================

        print(
            "\n=== IFC CONTAINMENT RESULT ==="
        )

        for relation in relations:

            storey = getattr(
                relation,
                "RelatingStructure",
                None
            )

            if not storey:

                continue

            level = getattr(
                storey,
                "Name",
                None
            )

            related = list(
                getattr(
                    relation,
                    "RelatedElements",
                    None
                )
                or []
            )

            print(
                "STOREY:",
                level,
                "ELEMENTS:",
                len(
                    related
                )
            )

        return relations

    # ======================================
    # STOREY INDEX
    # ======================================

    def _build_storey_index(
        self,
        storeys
    ):

        storey_by_level = {}

        for storey in storeys:

            level = getattr(
                storey,
                "Name",
                None
            )

            if not level:

                continue

            storey_by_level[level] = (
                storey
            )

            print(
                "STOREY:",
                level
            )

        return storey_by_level

    # ======================================
    # SEMANTIC LEVEL INDEX
    # ======================================

    def _build_semantic_level_index(
        self
    ):

        level_by_name = {}

        # ==================================
        # BUILDER ENTITY LEVELS
        # ==================================
        #
        # These levels are produced directly
        # by the IFC Entity Builder.
        #
        # They are authoritative and must be
        # preserved before consulting the
        # broader semantic context.
        #

        if isinstance(
            self.entity_levels,
            dict
        ):

            for entity, level in (
                self.entity_levels.items()
            ):

                if not level:
                    continue

                name = getattr(
                    entity,
                    "Name",
                    None
                )

                if not name:
                    continue

                level_by_name[name] = level

        # ==================================
        # SPACES
        # ==================================

        semantic_spaces = (
            self.semantic_context.get(
                "spaces",
                []
            )
        )

        if isinstance(
            semantic_spaces,
            list
        ):

            for item in semantic_spaces:

                if not isinstance(
                    item,
                    dict
                ):

                    continue

                name = item.get(
                    "name"
                )

                level = (
                    item.get(
                        "level"
                    )
                    or
                    item.get(
                        "floor"
                    )
                )

                if name and level:

                    level_by_name[
                        name
                    ] = level

        # ==================================
        # ARCHITECTURAL ELEMENTS
        # ==================================

        semantic_elements = (
            self.semantic_context.get(
                "elements",
                []
            )
        )

        if isinstance(
            semantic_elements,
            list
        ):

            for item in semantic_elements:

                if not isinstance(
                    item,
                    dict
                ):

                    continue

                name = item.get(
                    "name"
                )

                level = (
                    item.get(
                        "level"
                    )
                    or
                    item.get(
                        "floor"
                    )
                )

                if name and level:

                    level_by_name[
                        name
                    ] = level

        # ==================================
        # FINAL ENTITY LEVEL OVERRIDE
        # ==================================
        #
        # Entity-level assignments generated
        # by the IFC Entity Builder are the
        # authoritative containment mapping.
        #

        if isinstance(
            self.entity_levels,
            dict
        ):

            for entity, level in (
                self.entity_levels.items()
            ):

                if not level:
                    continue

                name = getattr(
                    entity,
                    "Name",
                    None
                )

                if not name:
                    continue

                level_by_name[name] = level

        return level_by_name

    # ======================================
    # GET / CREATE RELATION
    # ======================================

    def _get_or_create_relation(
        self,
        storey
    ):

        existing = (
            self._find_existing_relation(
                storey
            )
        )

        if existing:

            return existing

        relation = (
            self.model.create_entity(

                "IfcRelContainedInSpatialStructure",

                GlobalId=(
                    ifcopenshell.guid.new()
                ),

                RelatedElements=[],

                RelatingStructure=(
                    storey
                )

            )
        )

        print(
            "CREATED CONTAINMENT:",
            getattr(
                storey,
                "Name",
                None
            )
        )

        return relation

    # ======================================
    # EXISTING RELATION
    # ======================================

    def _find_existing_relation(
        self,
        storey
    ):

        relations = (
            self.model.by_type(
                "IfcRelContainedInSpatialStructure"
            )
        )

        for relation in relations:

            relating_structure = getattr(
                relation,
                "RelatingStructure",
                None
            )

            if not relating_structure:

                continue

            if (
                relating_structure.id()
                ==
                storey.id()
            ):

                return relation

        return None

    # ======================================
    # REMOVE FROM OTHER STOREYS
    # ======================================

    def _remove_from_other_storeys(
        self,
        entities,
        target_storey
    ):

        entity_ids = {
            entity.id()
            for entity in entities
        }

        relations = (
            self.model.by_type(
                "IfcRelContainedInSpatialStructure"
            )
        )

        for relation in relations:

            relating_structure = getattr(
                relation,
                "RelatingStructure",
                None
            )

            if not relating_structure:

                continue

            if (
                relating_structure.id()
                ==
                target_storey.id()
            ):

                continue

            existing_elements = list(
                getattr(
                    relation,
                    "RelatedElements",
                    None
                )
                or []
            )

            filtered = [

                entity

                for entity in existing_elements

                if entity.id()
                not in entity_ids

            ]

            if len(filtered) != len(
                existing_elements
            ):

                relation.RelatedElements = (
                    filtered
                )

                print(
                    "REMOVED FROM OLD STOREY:",
                    getattr(
                        relating_structure,
                        "Name",
                        None
                    ),
                    "REMOVED:",
                    len(
                        existing_elements
                    )
                    -
                    len(
                        filtered
                    )
                )

    # ======================================
    # UNIQUE ENTITIES
    # ======================================

    def _unique_entities(
        self,
        entities
    ):

        unique = []

        seen_ids = set()

        for entity in entities:

            if entity is None:

                continue

            entity_id = entity.id()

            if entity_id in seen_ids:

                continue

            seen_ids.add(
                entity_id
            )

            unique.append(
                entity
            )

        return unique