print("USING structural_span_reasoner.py StructuralSpanReasoner")


class StructuralSpanReasoner:


    VERSION = "1.0"


    def __init__(self):

        print(
            "🏗️ Structural Span Reasoner v1.0 ACTIVE"
        )


        # constraint only
        self.min_span = 3.0
        self.max_span = 8.0


        self.candidate_spans = [

            3.0,
            3.5,
            4.0,
            4.5,
            5.0,
            5.5,
            6.0,
            6.5,
            7.0,
            7.5,
            8.0

        ]



    # ==================================================
    # MAIN DECISION
    # ==================================================

    def solve(
        self,
        length,
        anchors=None,
        building_type="residential"
    ):


        anchors = anchors or []


        candidates = []


        for span in self.candidate_spans:


            divisions = self._generate_divisions(
                length,
                span
            )


            if not divisions:
                continue


            score = self._score_layout(
                divisions,
                anchors,
                building_type
            )


            candidates.append(

                {

                    "span":
                        span,


                    "axis":
                        divisions,


                    "score":
                        score

                }

            )


        if not candidates:

            return {

                "axis": [0, length],

                "span": length,

                "reason":
                    "no_candidate"

            }


        best = max(
            candidates,
            key=lambda x: x["score"]
        )


        return {

            "axis":
                best["axis"],

            "span":
                best["span"],

            "score":
                best["score"],

            "reason":
                "adaptive_span_selection"

        }



    # ==================================================
    # CREATE AXIS
    # ==================================================

    def _generate_divisions(
        self,
        length,
        span
    ):


        count = round(
            length / span
        )


        if count < 1:
            return None


        actual_span = length / count


        if (

            actual_span < self.min_span

            or

            actual_span > self.max_span

        ):

            return None



        axis = []


        for i in range(
            count + 1
        ):

            axis.append(
                i * actual_span
            )


        return axis



    # ==================================================
    # LAYOUT SCORE
    # ==================================================

    def _score_layout(
        self,
        axis,
        anchors,
        building_type
    ):


        score = 100


        # fewer columns preferred

        score -= (
            len(axis) * 2
        )


        # architectural alignment

        for anchor in anchors:


            if min(
                abs(x-anchor)
                for x in axis
            ) > 0.5:


                score -= 10



        # commercial prefers larger spans

        if building_type in [

            "commercial",
            "mall"

        ]:

            score += (
                axis[-1] / len(axis)
            )


        return round(
            score,
            2
        )