# ==================================================
# ArchitectOS CAD Site Boundary Detector v1.0
# ==================================================

class SiteBoundaryDetector:


    VERSION = (
        "architectos_site_boundary_detector_v1.0"
    )


    def __init__(self):

        print(
            "📐 CAD Site Boundary Detector v1.0 ACTIVE"
        )



    # ==================================================
    # DETECT SITE
    # ==================================================

    def detect(
        self,
        geometry
    ):


        candidates = []


        # ----------------------------------
        # CLOSED POLYLINES
        # ----------------------------------

        for poly in geometry.get(
            "polylines",
            []
        ):


            if poly.get(
                "closed"
            ):


                score = self._score_layer(
                    poly.get("layer")
                )


                candidates.append({

                    "source":
                        "LWPOLYLINE",

                    "layer":
                        poly.get("layer"),

                    "score":
                        score,

                    "points":
                        poly.get("points")

                })



        # ----------------------------------
        # HATCH
        # ----------------------------------

        for hatch in geometry.get(
            "hatches",
            []
        ):


            score = self._score_layer(
                hatch.get("layer")
            )


            candidates.append({

                "source":
                    "HATCH",

                "layer":
                    hatch.get("layer"),

                "score":
                    score,

                "points":
                    hatch.get("boundary", [])

            })



        if not candidates:


            return {

                "status":
                    "failed",

                "reason":
                    "no_boundary_found"

            }



        best = max(
            candidates,
            key=lambda x:x["score"]
        )



        return {


            "status":
                "detected",


            "confidence":
                best["score"],


            "source":
                best["source"],


            "layer":
                best["layer"],


            "polygon":
                best["points"]


        }



    # ==================================================
    # LAYER SCORE
    # ==================================================

    def _score_layer(
        self,
        layer
    ):


        if not layer:

            return 0



        name = layer.lower()



        score = 0



        keywords = [

            "hach",
            "parcel",
            "kol",
            "kadr",
            "boundary",
            "حد",
            "site"

        ]


        for k in keywords:

            if k in name:

                score += 20



        return min(
            score,
            100
        )