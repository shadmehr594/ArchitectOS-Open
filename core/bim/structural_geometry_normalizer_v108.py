# ==================================================
# ArchitectOS BIM Structural Geometry Normalizer v108.0
# ==================================================

from collections import Counter


class StructuralGeometryNormalizer:

    VERSION = "108.0"

    def __init__(self):

        print(
            "🏗️ Structural Geometry Normalizer v108.0 ACTIVE"
        )

    # ==================================================
    # NORMALIZE STRUCTURAL GEOMETRY
    # ==================================================

    def normalize(
        self,
        elements
    ):

        print("\n========== STRUCTURAL NORMALIZER DEBUG ==========")

        print(
            "INPUT ELEMENT COUNT:",
            len(elements)
        )

        print(
            "INPUT TYPES:"
        )

        input_counter = Counter(
            [
                e.get("ifc_type")
                or e.get("type")
                for e in elements
            ]
        )

        print(input_counter)


        print("\n====== STRUCTURAL LEVEL NORMALIZER DEBUG ======")

        for e in elements:

            if not isinstance(e, dict):
                continue

            if e.get("ifc_type") not in [
                "IfcBeam",
                "IfcColumn"
            ]:
                continue

            print(
                {
                    "id": e.get("id"),
                    "type": e.get("type"),
                    "ifc_type": e.get("ifc_type"),
                    "level": e.get("level"),
                    "data_level": e.get(
                    "data",
                        {}
                    ).get("level"),
                    "z": e.get(
                        "z"
                    ),
                    "data_z": e.get(
                        "data",
                        {}
                    ).get("z"),
                    "start": e.get(
                        "data",
                        {}
                    ).get("start"),
                    "end": e.get(
                        "data",
                        {}
                    ).get("end")
                }
            )

        cleaned = []

        removed = []

        seen = set()

        duplicate_beams = []

        zero_length_beams = []

        print("\n====== NORMALIZER INPUT BEAM TRACE FULL ======")

        for e in elements:

            if e.get("ifc_type") == "IfcBeam":

                data = e.get(
                    "data",
                    {}
                )

                print(
                    {
                        "id": e.get("id"),
                        "type": e.get("type"),
                        "level": e.get("level"),
                        "data_level": data.get("level"),
                        "start": data.get("start"),
                        "end": data.get("end"),
                        "z": data.get("z")
                    }
                )

        print("==============================================")

        # ----------------------------------
        # MAIN NORMALIZATION
        # ----------------------------------

        for element in elements:

            element_type = (
                element.get("type")
            )

            data = (
                element.get("data", {})
            )

            if element.get("ifc_type") in [
                "IfcBeam",
                "IfcColumn"
            ]:

                print(
                    "NORMALIZER STRUCTURE INPUT:",
                    {
                        "id": element.get("id"),
                        "type": element.get("type"),
                        "ifc_type": element.get("ifc_type"),
                        "level": data.get("level"),
                        "z": data.get("z"),
                        "start": data.get("start"),
                        "end": data.get("end")
                    }
                )


            # ----------------------------------
            # NORMALIZE STRUCTURAL LEVEL
            # ----------------------------------

            if element.get("type") in [
                "beam",
                "column"
            ]:

                if element.get("level") == 0:

                    element["level"] = "F1"

            # ----------------------------------
            # ONLY BEAMS
            # ----------------------------------

            if element_type == "beam":

                start = data.get(
                    "start"
                )

                end = data.get(
                    "end"
                )

                # ------------------------------
                # ZERO LENGTH
                # ------------------------------

                if (
                    start is not None
                    and
                    end is not None
                    and
                    start == end
                ):

                    zero_length_beams.append(
                        element.get("id")
                    )

                    removed.append({

                        "id":
                        element.get("id"),

                        "reason":
                        "zero_length_beam"

                    })

                    continue

                # ------------------------------
                # DUPLICATE GEOMETRY
                # ------------------------------

                if (
                    start is not None
                    and
                    end is not None
                ):

                    geometry_key = (
                        element.get("level"),
                        tuple(start),
                        tuple(end)
                    )

                    if geometry_key in seen:

                        duplicate_beams.append(
                            element.get("id")
                        )

                        removed.append({

                            "id":
                            element.get("id"),

                            "reason":
                            "duplicate_beam_geometry"

                        })

                        continue

                    seen.add(
                        geometry_key
                    )

            if element.get("type") == "beam":

                if element.get("level") == 0:

                    print(
                        "⚠️ BEAM LEVEL FIX REQUIRED:",
                        element.get("id")
                    )

            cleaned.append(
                element
            )

        # ----------------------------------
        # DEBUG AFTER FILTER
        # ----------------------------------

        print("\n------ FILTER RESULT ------")

        print(
            "REMOVED:",
            len(removed)
        )

        print(
            "ZERO LENGTH:",
            len(zero_length_beams)
        )

        if zero_length_beams:

            print(
                zero_length_beams
            )

        print(
            "DUPLICATE:",
            len(duplicate_beams)
        )

        if duplicate_beams:

            print(
                duplicate_beams
            )

        print(
            "OUTPUT ELEMENT COUNT:",
            len(cleaned)
        )


        print("\n========== NORMALIZER BEAM OUTPUT CHECK ==========")

        for e in cleaned:

            if e.get("type") == "beam":

                data = e.get(
                "data",
                {}
            )

            print(
                {
                    "id": e.get("id"),
                    "level": e.get("level"),
                    "z": e.get("z"),
                    "data_z": data.get("z"),
                    "start": data.get("start"),
                    "end": data.get("end")
                }
            )


        # ----------------------------------
        # REINDEX IDS
        # ----------------------------------

        counters = {

            "column": 1,
            "beam": 1,
            "slab": 1,
            "wall": 1,
            "door": 1,
            "window": 1,
            "space": 1

        }

        for element in cleaned:

            element_type = element.get(
                "type"
            )

            if element_type in counters:

                element["id"] = (

                    f"{element_type}_"
                    f"{counters[element_type]:03}"

                )

                counters[element_type] += 1


        # ----------------------------------
        # PROMOTE LEVEL DATA
        # ----------------------------------

        for element in cleaned:

            data = element.get(
                "data",
                {}
            )

            if element.get("level") is None:

                if data.get("level") is not None:

                    element["level"] = data.get(
                        "level"
                    )

            if element.get("z") is None:

                if data.get("z") is not None:

                    element["z"] = data.get(
                        "z"
                    )

            if element.get("type") == "beam":

                if data.get("elevation") is not None:

                    element["elevation"] = data.get(
                        "elevation"
                    )


        # ----------------------------------
        # STRUCTURAL Z VALIDATION
        # ----------------------------------

        FLOOR_HEIGHT = 3.2

        for element in cleaned:

            if element.get("type") not in [
                "beam",
                "column"
            ]:
                continue


            level = element.get(
                "level"
            )


            if level in [
                "F1",
                "F2",
                "F3"
            ]:

                floor_index = {
                    "F1": 0,
                    "F2": 1,
                    "F3": 2
                }[level]


                if element.get("type") == "column":

                    expected_z = (
                        floor_index
                        *
                        FLOOR_HEIGHT
                    )


                elif element.get("type") == "beam":

                    expected_z = (
                        (floor_index + 1)
                        *
                        FLOOR_HEIGHT
                    )


                old_z = element.get(
                    "z"
                )


                if old_z != expected_z:

                    print(
                        "⚠️ STRUCTURAL Z CORRECTION:",
                        element.get("id"),
                        old_z,
                        "→",
                        expected_z
                    )


                    element["z"] = expected_z


                    if "data" in element:

                        element["data"]["z"] = expected_z

        # ----------------------------------
        # NORMALIZE BEAM ELEVATION
        # ----------------------------------

        for element in cleaned:

            if element.get("type") != "beam":
                continue


            data = element.get(
                "data",
                {}
            )


            elevation = element.get(
                "elevation"
            )


            if elevation is None:

                elevation = data.get(
                    "elevation"
                )


            if elevation is not None:

                element["z"] = elevation

                data["z"] = elevation



            start = data.get(
                "start"
            )

            end = data.get(
                "end"
            )


            if isinstance(start, tuple):

                start = list(start)


            if isinstance(start, list):

                if len(start) > 2:

                    start = start[:2]


                data["start"] = start



            if isinstance(end, tuple):

                end = list(end)


            if isinstance(end, list):

                if len(end) > 2:

                    end = end[:2]


                data["end"] = end



            element["data"] = data



            print(
                "========== NORMALIZED BEAM FINAL =========="
            )

            print(
                {
                    "id": element.get("id"),
                    "level": element.get("level"),
                    "z": element.get("z"),
                    "start": data.get("start"),
                    "end": data.get("end")
                }
            )


            print("\n====== NORMALIZER FINAL LEVEL SUMMARY ======")

            print(
                "FINAL TYPES:",
                Counter(
                    e.get("type")
                    for e in cleaned
                )
            )


            print(
                "FINAL LEVELS:"
            )

            print(
                Counter(
                    (
                        e.get("type"),
                        e.get("level")
                    )
                    for e in cleaned
                    if e.get("type") in [
                        "beam",
                        "column"
                    ]
                )
            )


            print(
                "\nFINAL STRUCTURE Z SAMPLE:"
            )


            for e in cleaned:

                if e.get("type") in [
                    "beam",
                    "column"
                ]:

                    print(
                        e.get("type"),
                        e.get("level"),
                        e.get("z")
                    )

                    if e.get("type") == "beam":
                        break


            print(
                "============================================"
            )

        return {

            "engine":
                f"structural_geometry_normalizer_v{self.VERSION}",

            "status":
                "completed",

            "removed":
                removed,

            "elements":
                cleaned,

            "statistics": {

                "input":
                    len(elements),

                "output":
                    len(cleaned),

                "removed_count":
                    len(removed),

                "duplicates_removed":
                    len(duplicate_beams),

                "zero_length_removed":
                    len(zero_length_beams)

            }

        }