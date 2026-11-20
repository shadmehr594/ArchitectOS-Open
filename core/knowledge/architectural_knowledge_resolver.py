import json
import os
import re

# ARCHITECTURAL_MATERIAL_INTENT_FIDELITY_V1 — the material resolver must not
# turn a material the user REJECTED into a positive render requirement. The
# negation decision is the project's single shared one; nothing here re-parses
# text or adds material vocabulary.
from core.chat.negation_scope_v1 import (
    is_prohibited,
    negated_requirement,
)


class ArchitecturalKnowledgeResolver:


    VERSION = "1.1"


    def __init__(self):

        print(
            "🧠 ARCHITECTURAL KNOWLEDGE RESOLVER v1.1 ONLINE"
        )


        base_path = os.path.dirname(__file__)


        ontology_path = os.path.join(
            base_path,
            "architectural_ontology.json"
        )


        with open(
            ontology_path,
            "r",
            encoding="utf-8"
        ) as f:

            self.data = json.load(f)



        self.site_data = {


            "building_position": {

                "north": [
                    "شمال",
                    "شمال زمین",
                    "ضلع شمال",
                    "ضلع شمال زمین",
                    "سمت شمال"
                ],

                "south": [
                    "جنوب",
                    "جنوب زمین",
                    "ضلع جنوب",
                    "ضلع جنوب زمین",
                    "سمت جنوب"
                ],

                "east": [
                    "شرق",
                    "شرق زمین",
                    "ضلع شرق",
                    "ضلع شرق زمین",
                    "سمت شرق"
                ],

                "west": [
                    "غرب",
                    "غرب زمین",
                    "ضلع غرب",
                    "ضلع غرب زمین",
                    "سمت غرب"
                ],

                "center": [
                    "وسط زمین",
                    "مرکز زمین",
                    "وسط سایت"
                ]

            },


            "setbacks": {

                "neighbor_distance": [

                    "فاصله از همسایه",
                    "فاصله با همسایه",
                    "حریم همسایه",
                    "عقب نشینی از همسایه"

                ],


                "street_setback": [

                    "عقب نشینی خیابان",
                    "فاصله از خیابان",
                    "حریم خیابان"

                ]

            },


            "open_spaces": {

                "yard": [

                    "حیاط",
                    "فضای باز",
                    "محوطه",
                    "حیاط باز"

                ],


                "garden": [

                    "باغ",
                    "فضای سبز",
                    "گرین اسپیس"

                ]

            }

        }
    # ==================================================
    # HELPERS
    # ==================================================

    def append_unique(
        self,
        target,
        value
    ):

        if value not in target:

            target.append(
                value
            )


    # ======================================================
    # MATERIAL NEGATION EVIDENCE
    # ======================================================

    def rejected_material_region(self, text):
        """The character region of `text` that states the REJECTED requirement.

        Returns ``None`` when the request rejects nothing. The evidence is the
        shared negation layer's, trimmed at the affirmed replacement, so the
        material rule and the instruction's prohibition cannot disagree.
        """

        requirement = negated_requirement(text)

        if not requirement:

            return None

        base = str(text).rfind(requirement)

        if base < 0:

            return None

        return (base, base + len(requirement))


    def only_rejected_occurrences(self, text_lower, synonym, region):
        """True when every occurrence of `synonym` lies inside `region`.

        A synonym that also appears OUTSIDE the rejected region is still the
        user's requirement ("نه آجر قرمز بلکه سنگ" keeps سنگ), so only an
        entirely-rejected synonym is dropped.
        """

        if not region:

            return False

        low, high = region

        position = text_lower.find(synonym)

        if position < 0:

            return False

        while position >= 0:

            if not (low <= position < high):

                return False

            position = text_lower.find(synonym, position + len(synonym))

        return True


    def affirmed_synonym_span(self, text_lower, synonyms, region):
        """The LONGEST affirmed `(start, end)` occurrence among `synonyms`.

        MATERIAL_VOCABULARY_COMPLETENESS_V1 — the longest synonym wins so a
        specific form ("stone facade", "red brick") outranks the generic form
        ("stone", "brick") of the same record, and any occurrence inside the
        rejected region is ignored.
        """

        best = None

        for synonym in synonyms or ():

            lowered = str(synonym).lower()

            if not lowered:

                continue

            position = text_lower.find(lowered)

            while position >= 0:

                inside = bool(region) and (
                    region[0] <= position < region[1]
                )

                if not inside:

                    length = len(lowered)

                    if best is None or length > (best[1] - best[0]):

                        best = (position, position + length)

                position = text_lower.find(lowered, position + len(lowered))

        return best


    def material_candidates(self, text, text_lower):
        """Every affirmed material match, with the span that produced it.

        Returns dicts of `{id, normalized, start, end}` in ontology order.

        MATERIAL_NORMALIZATION_SPECIFICITY_V1
        -------------------------------------
        `normalized` used to be one fixed string per record, so it could not
        distinguish a generic phrase from the qualified form of the same
        record: `concrete wall` and `exposed concrete wall` both published
        `exposed concrete`, and the generic phrase acquired a surface
        treatment, a product form or an application the text never named.

        A record now declares the canonical (generic) form in `normalized` and,
        optionally, `qualified_forms` — the synonyms whose meaning is MORE
        specific than the canonical one, each with the form to publish. The
        matched span is the evidence: the qualifier is echoed only when the
        text itself contains it, and nothing is ever added to it. No second
        detection engine and no new identity is involved — the same longest
        synonym span that already decided the match decides the wording.
        """

        region = self.rejected_material_region(text)

        candidates = []

        for name, item in self.data.get("materials", {}).items():

            span = self.affirmed_synonym_span(
                text_lower,
                item.get("synonyms", []),
                region
            )

            if not span:

                continue

            qualified = item.get("qualified_forms") or {}

            normalized = item.get("normalized", name)

            if isinstance(qualified, dict):

                matched = text_lower[span[0]:span[1]].strip()

                normalized = qualified.get(matched, normalized)

            candidates.append({
                # ARCHITECTURAL_KNOWLEDGE_HANDOFF_V1 — the ontology IDENTITY,
                # not only its display form. A consumer that must explain what
                # a term MEANS (the vision knowledge handoff) needs the record
                # key; the request path keeps using `normalized` unchanged.
                "id": name,
                "normalized": normalized,
                "start": span[0],
                "end": span[1],
            })

        return candidates


    def suppress_contained_materials(self, candidates):
        """Drop a material whose match is contained in a LONGER match.

        "brick" inside "red brick" and "سنگ" inside "سنگ مرمر" are not
        additional requirements: the specific material already names them.
        Equal spans are kept (two records legitimately naming the same words).
        """

        kept = []

        for candidate in candidates:

            width = candidate["end"] - candidate["start"]

            swallowed = any(
                other["start"] <= candidate["start"]
                and candidate["end"] <= other["end"]
                and (other["end"] - other["start"]) > width
                for other in candidates
            )

            if not swallowed:

                kept.append(candidate)

        return kept


    def synonym_present(self, text_lower, synonym):
        """True when `synonym` occurs in the request as a WHOLE token.

        ARCHITECTURAL_REQUIREMENT_GROUNDING_V1 — "store" is a synonym of the
        `retail` space, and a plain substring test found it inside "two-storey",
        so a purely residential request acquired a COMMERCIAL function
        ("functional spaces including retail"). A lexicon entry names a word,
        not a fragment of one, so the match is token-bounded. A Persian suffix
        attached through a ZWNJ is still a boundary, and an attached inflection
        ("مغازه‌ها") keeps matching.
        """

        lowered = str(synonym or "").lower().strip()

        if not lowered:

            return False

        return re.search(
            r"(?<!\w)" + re.escape(lowered) + r"(?!\w)",
            text_lower
        ) is not None


    def normalize_list(
        self,
        values
    ):

        result = []

        for value in values:

            if value not in result:

                result.append(
                    value
                )

        return result



    def has_text(
        self,
        text,
        keywords
    ):

        text_lower = text.lower()


        for keyword in keywords:

            if keyword.lower() in text_lower:

                return True


        return False



    # ==================================================
    # SITE RESOLUTION
    # ==================================================

    def resolve_site(
        self,
        text,
        intent
    ):


        if "site_constraints" not in intent:


            intent["site_constraints"] = {

                "coverage": None,

                "density": None,

                "setbacks": {},

                "building_position": {

                    "side": None,
                    "alignment": None,
                    "distance_from_boundary": None

                },

                "open_spaces": []

            }



        text_lower = text.lower()



        # ==================================================
        # BUILDING POSITION
        # ==================================================

        for position, synonyms in self.site_data.get(
            "building_position",
            {}
        ).items():


            for synonym in synonyms:


                if synonym.lower() in text_lower:


                    intent[
                        "site_constraints"
                    ][
                        "building_position"
                    ][
                        "side"
                    ] = position


                    break



        # ==================================================
        # SETBACKS
        # ==================================================

        for setback, synonyms in self.site_data.get(
            "setbacks",
            {}
        ).items():


            for synonym in synonyms:


                if synonym.lower() in text_lower:


                    intent[
                        "site_constraints"
                    ][
                        "setbacks"
                    ][
                        setback
                    ] = True


                    break



        # ==================================================
        # OPEN SPACES
        # ==================================================

        for space, synonyms in self.site_data.get(
            "open_spaces",
            {}
        ).items():


            for synonym in synonyms:


                if synonym.lower() in text_lower:


                    self.append_unique(

                        intent[
                            "site_constraints"
                        ][
                            "open_spaces"
                        ],

                        space

                    )


                    break



        return intent
    # ==================================================
    # RESOLVE
    # ==================================================

    def resolve(
        self,
        text,
        intent
    ):


        text_lower = text.lower()


        detected_building = None



        # ==================================================
        # BUILDING TYPE DETECTION
        # ==================================================

        for name, item in self.data.get(
            "building_types",
            {}
        ).items():


            for synonym in item.get(
                "synonyms",
                []
            ):


                if synonym.lower() in text_lower:

                    # VISUAL_ACCEPTANCE_BLOCKER_REPAIR_V1 — a building type the
                    # user PROHIBITED must not be detected. "کاربری تجاری …
                    # اضافه نکن" selected the commercial record and activated
                    # its knowledge defaults (lobby, retail).
                    if is_prohibited(text, synonym):

                        continue

                    detected_building = name

                    break



            if detected_building:

                break



        # ==================================================
        # BUILDING KNOWLEDGE
        # ==================================================

        if detected_building:


            intent["building_type"] = (
                detected_building
            )


            building_data = self.data[
                "building_types"
            ].get(
                detected_building,
                {}
            )



            knowledge = {


                "category":
                    building_data.get(
                        "category"
                    ),


                "required_spaces":
                    building_data.get(
                        "required_spaces",
                        []
                    ),


                "optional_spaces":
                    building_data.get(
                        "optional_spaces",
                        []
                    ),


                "relationships":
                    building_data.get(
                        "relationships",
                        []
                    )

            }



            intent["knowledge"] = knowledge



            if knowledge.get(
                "category"
            ):

                intent["category"] = (
                    knowledge["category"]
                )



            # REQUIRED SPACES

            for space in knowledge.get(
                "required_spaces",
                []
            ):

                self.append_unique(
                    intent["spaces"],
                    space
                )



            # OPTIONAL SPACES
            #
            # ARCHITECTURAL_REQUIREMENT_GROUNDING_V1 — an OPTIONAL space is a
            # design suggestion the knowledge base offers, not something the
            # user asked for. It used to be appended to `intent["spaces"]`,
            # which is the field PromptBuilder renders as
            # "functional spaces including …", so a bare "villa" request
            # asserted a POOL and a TERRACE as if they were requirements.
            # They stay recorded in `intent["knowledge"]["optional_spaces"]`
            # (evidence, not requirement) and are only promoted when the user
            # names them, which the SPACE DETECTION loop below already does.



            # RELATIONSHIPS

            if "relationships" not in intent:

                intent["relationships"] = []



            for relation in knowledge.get(
                "relationships",
                []
            ):


                if relation not in intent["relationships"]:

                    intent["relationships"].append(
                        relation
                    )



        # ==================================================
        # SPACE DETECTION
        # ==================================================

        for name, item in self.data.get(
            "spaces",
            {}
        ).items():


            for synonym in item.get(
                "synonyms",
                []
            ):


                if self.synonym_present(text_lower, synonym):

                    # VISUAL_ACCEPTANCE_BLOCKER_REPAIR_V1 — a space the user
                    # PROHIBITED is not a requested space. Persian puts the
                    # prohibition after its objects ("استخر و تراس اضافه
                    # نکن"), so a substring test alone turned a rejection into
                    # "functional spaces including pool, terrace". The span
                    # comes from the shared negation layer, the same evidence
                    # the material rule uses.
                    if is_prohibited(text, synonym):

                        continue


                    self.append_unique(
                        intent["spaces"],
                        name
                    )



                    zone = item.get(
                        "zone"
                    )


                    if zone:


                        if zone not in intent["zones"]:

                            intent["zones"][zone] = []



                        self.append_unique(
                            intent["zones"][zone],
                            name
                        )


                    break



        # ==================================================
        # ALIAS NORMALIZATION
        # ==================================================

        aliases = {

            "shop": "retail"

        }



        normalized_spaces = []



        for space in intent["spaces"]:


            value = aliases.get(
                space,
                space
            )


            self.append_unique(
                normalized_spaces,
                value
            )



        intent["spaces"] = normalized_spaces



        # ==================================================
        # SITE
        # ==================================================

        intent = self.resolve_site(
            text,
            intent
        )
        # ==================================================
        # FINAL ZONE CLEANUP
        # ==================================================

        for zone, values in intent.get(
            "zones",
            {}
        ).items():


            cleaned = []


            for value in values:


                value = aliases.get(
                    value,
                    value
                )


                self.append_unique(
                    cleaned,
                    value
                )



            intent["zones"][zone] = cleaned



        # ==================================================
        # MATERIAL RESOLUTION
        # ==================================================
        #
        # ARCHITECTURAL_MATERIAL_INTENT_FIDELITY_V1 — a rejected material is
        # not a requirement. "نه آجر قرمز بلکه سنگ" matched both the brick and
        # the stone synonym, so BOTH `red brick facade` and `natural stone
        # facade` reached the render prompt: the rejected material was asserted
        # as a positive requirement while the instruction's prohibition forbade
        # it. The rejected region comes from the shared negation layer (the same
        # evidence the prohibition uses); only occurrences INSIDE it are
        # ignored.
        #
        # MATERIAL_VOCABULARY_COMPLETENESS_V1 — generic vocabulary ("brick",
        # "stone", "نمای آجری") is resolvable without inventing a colour or
        # subtype, and a generic match contained in a LONGER match is not an
        # extra requirement ("brick" inside "red brick", "سنگ" inside
        # "سنگ مرمر"). Both rules use the existing records and the existing
        # resolution loop; no second material path is introduced.
        candidates = self.material_candidates(text, text_lower)

        for candidate in self.suppress_contained_materials(candidates):

            self.append_unique(
                intent["materials"],
                candidate["normalized"]
            )



        # ==================================================
        # SPACE ZONE UPDATE AFTER KNOWLEDGE
        # ==================================================

        for space in intent.get(
            "spaces",
            []
        ):


            for name, item in self.data.get(
                "spaces",
                {}
            ).items():


                if name != space:

                    continue



                zone = item.get(
                    "zone"
                )


                if zone:


                    if zone not in intent["zones"]:

                        intent["zones"][zone] = []



                    self.append_unique(
                        intent["zones"][zone],
                        name
                    )



        # ==================================================
        # NORMALIZATION
        # ==================================================

        intent["spaces"] = self.normalize_list(
            intent.get(
                "spaces",
                []
            )
        )


        if "relationships" not in intent:

            intent["relationships"] = []



        if "knowledge" in intent:


            for relation in intent["knowledge"].get(
                "relationships",
                []
            ):


                if relation not in intent["relationships"]:

                    intent["relationships"].append(
                        relation
                    )



        for zone in intent.get(
            "zones",
            {}
        ):


            intent["zones"][zone] = (
                self.normalize_list(
                    intent["zones"][zone]
                )
            )



        return intent