class ParcelExtractor:


    VERSION = "PARCEL_EXTRACTOR_v3_SELECTOR"



    def extract(
        self,
        geometry,
        target_parcel=None
    ):


        candidates = geometry.get(
            "parcel_candidates",
            []
        )


        if not candidates:


            return {

                "status":
                    "failed",

                "reason":
                    "no parcel candidate"

            }


        # ==========================================
        # TARGET PARCEL SELECTION
        # ==========================================

        if target_parcel is not None:

            target_value = str(
                target_parcel
            ).strip()


            labels = [

                item

                for item in geometry.get(
                    "text",
                    []
                )

                if (
                    item.get("value") == target_value
                    and
                    item.get("layer", "").upper() == "CODE"
                )

            ]


            best_match = None
            best_distance = None


            for label in labels:

                position = label.get(
                    "position"
                )

                if not position:
                    continue


                lx, ly = position


                for candidate in candidates:

                    points = candidate.get(
                        "points",
                        []
                    )


                    if len(points) < 3:
                        continue

                    if target_value in candidate.get("contained_code_labels", []):
                        candidate_distance = 0.0
                        if (
                            best_match is None
                            or candidate.get("source") == "closed_lwpolyline"
                        ):
                            best_match = candidate
                            best_distance = candidate_distance
                        continue


                    cx = sum(
                        p[0]
                        for p in points
                    ) / len(points)


                    cy = sum(
                        p[1]
                        for p in points
                    ) / len(points)


                    distance = (
                        (
                            lx - cx
                        ) ** 2
                        +
                        (
                            ly - cy
                        ) ** 2
                    ) ** 0.5


                    if (
                        best_distance is None
                        or
                        distance < best_distance
                    ):

                        best_distance = distance
                        best_match = candidate


            if best_match is not None:

                parcel = best_match

            else:

                parcel = max(

                    candidates,

                    key=lambda x: x.get(
                        "score",
                        0
                    )

                )

        else:

            parcel = max(

                candidates,

                key=lambda x: x.get(
                    "score",
                    0
                )

            )



        score = parcel.get(
            "score",
            0
        )



        confidence = min(

            round(
                score / 100,
                2
            ),

            0.99

        )



        return {


            "status":
                "ready",



            "geometry_type":
                "polygon",



            "source":
                parcel.get(
                    "source",
                    "unknown"
                ),



            "layer":
                parcel.get(
                    "layer"
                ),



            "pattern":
                parcel.get(
                    "pattern"
                ),



            "points":
                parcel.get(
                    "points",
                    []
                ),



            "area":
                parcel.get(
                    "area",
                    0
                ),

            "perimeter":
                parcel.get("perimeter"),

            "closed":
                parcel.get("closed", False),

            "valid":
                parcel.get("valid", True),

            "handle":
                parcel.get("handle"),

            "elevation_ignored_for_2d":
                parcel.get("elevation_ignored_for_2d"),



            "score":
                score,



            "target_parcel":
                target_parcel,



            "selection_distance":
                best_distance
                if target_parcel is not None
                else None,



            "confidence":
                confidence

        }
