from core.brain import Brain


def main():

    brain = Brain()


    print(
        "\n=== FULL DESIGN EXECUTION FLOW TEST ==="
    )


    design = {

        "geometry": {

            "rooms":[

                {
                    "x":0,
                    "y":0,
                    "w":5,
                    "h":5,
                    "height":3
                }

            ]

        }

    }


    decisions = [

        {

            "action":
            "add_horizontal_shading",

            "target":
            "facade",

            "reason":
            "solar control"

        },

        {

            "action":
            "prefer_thermal_materials",

            "target":
            "materials",

            "reason":
            "energy optimization"

        }

    ]


    execution_actions = brain.decision_adapter.convert(
        decisions
    )


    print(
        "Converted Actions:",
        execution_actions
    )


    result = brain.execution_bridge.process(

        design,

        execution_actions

    )


    print(
        "Bridge Status:",
        result.get("status")
    )


    print(
        "BIM Status:",
        result.get("bim_result", {})
        .get("status")
    )


    assert result["status"] == "completed"


    print(
        "\n✅ FULL DESIGN EXECUTION FLOW PASSED"
    )



if __name__ == "__main__":

    main()