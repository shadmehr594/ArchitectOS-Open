class BIMCriticEngine:


    def __init__(self):

        print(
            "🧠 AI BIM Critic Engine v26.0 ACTIVE"
        )


    def analyze(
        self,
        scene_graph
    ):


        graph = scene_graph.get(
            "graph",
            {}
        )


        nodes = graph.get(
            "nodes",
            []
        )


        issues = []

        recommendations = []

        score = 100


        spaces = [
            n for n in nodes
            if n.get("type") == "space"
        ]


        facades = [
            n for n in nodes
            if n.get("type") == "facade"
        ]


        overhangs = [
            n for n in nodes
            if n.get("type") == "overhang"
        ]


        roof = [
            n for n in nodes
            if n.get("type") == "roof"
        ]



        # Space Analysis

        if len(spaces) == 0:

            issues.append(
                "no_spaces_defined"
            )

            score -= 20

        else:

            recommendations.append(
                "spatial_layout_detected"
            )



        # Facade Analysis

        if len(facades) > 0:

            recommendations.append(
                "facade_orientation_available"
            )

        else:

            issues.append(
                "missing_facade_information"
            )

            score -= 10



        # Solar Control

        if len(overhangs) > 0:

            recommendations.append(
                "solar_shading_strategy_active"
            )

        else:

            recommendations.append(
                "consider_solar_control_elements"
            )



        # Roof Analysis

        if len(roof) > 0:

            recommendations.append(
                "roof_defined"
            )



        # Final Rating


        if score < 0:

            score = 0



        return {


            "engine":
            "bim_critic_v26.0",


            "status":
            "analyzed",


            "score":
            score,


            "issues":
            issues,


            "recommendations":
            recommendations,


            "analysis":
            {

                "spaces":
                len(spaces),

                "facades":
                len(facades),

                "overhangs":
                len(overhangs),

                "roof":
                len(roof)

            }

        }