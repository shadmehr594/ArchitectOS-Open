def test_brain_execution_bridge_flow():

    brain = Brain()

    design = {
        "geometry": {
            "rooms": [
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
            "module":"facade",
            "action":"solar_protection",
            "parameters":{
                "level":"high"
            }
        }
    ]

    result = brain.execution_bridge.process(
        design,
        decisions
    )

    assert result["status"] == "completed"
    assert "bim_result" in result