"""
ArchitectOS Site Scenarios Test
"""


from scenarios.scenario_01_north_residential import get_scenario



def test_scenarios():


    scenario = get_scenario()



    print(
        "\n========== SCENARIO =========="
    )


    print(
        scenario
    )



    assert scenario.get(
        "name"
    ) == "north_residential"



    assert scenario.get(
        "requirements",
        {}
    ).get(
        "coverage"
    ) == 60



    assert scenario.get(
        "requirements",
        {}
    ).get(
        "floors"
    ) == 5



    print(
        "\n✅ SCENARIO 01 READY"
    )



if __name__ == "__main__":

    test_scenarios()