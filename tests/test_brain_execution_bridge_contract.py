from core.brain import Brain


def main():

    brain = Brain()


    print(
        "Execution Bridge:",
        type(
            brain.execution_bridge
        ).__name__
    )


    design = {

        "geometry": {

            "rooms": []

        }

    }


    actions = [

        {

            "module":
            "facade",

            "action":
            "add_shading",

            "parameters":
            {

                "type":
                "horizontal"

            },

            "reason":
            "test"

        }

    ]


    result = brain.execution_bridge.process(
        design,
        actions
    )


    print(
        "STATUS:",
        result.get("status")
    )


    print(
        "ACTION COUNT:",
        result.get("action_count")
    )


    assert result["status"] == "completed"


    print(
        "✅ BRAIN EXECUTION BRIDGE CONTRACT OK"
    )



if __name__ == "__main__":

    main()