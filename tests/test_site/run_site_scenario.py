"""
ArchitectOS Site Scenario Runner v1.0

Runs complete site intelligence pipeline
"""



from scenarios.scenario_01_north_residential import get_scenario

from core.site.model.site_model import SiteModel

from core.site.site_analyzer import SiteAnalyzer

from core.site.neighbor_detector import NeighborDetector

from core.site.setback_engine import SetbackEngine

from core.site.courtyard_engine import CourtyardEngine

from core.site.building_form_solver import BuildingFormSolver

from core.site.site_design_engine import SiteDesignEngine



def run():



    scenario = get_scenario()



    print(
        "\n========== RUNNING SCENARIO =========="
    )


    print(
        scenario["name"]
    )



    # =====================================
    # SITE MODEL
    # =====================================


    site_data = scenario["site"]



    boundary = [

        [0,0],

        [
            site_data["width"],
            0
        ],

        [
            site_data["width"],
            site_data["depth"]
        ],

        [
            0,
            site_data["depth"]
        ]

    ]



    site = SiteModel(

        boundary=boundary,

        roads=site_data.get(
            "roads",
            []
        )

    )



    # =====================================
    # ANALYSIS
    # =====================================


    analyzer = SiteAnalyzer()



    site_dict = site.to_dict()


    site_dict["neighbors"] = site_data.get(
        "neighbors",
        {}
    )


    analysis = analyzer.analyze(

        site_dict

    )



    # =====================================
    # NEIGHBORS
    # =====================================


    neighbor_engine = NeighborDetector()



    neighbors = neighbor_engine.analyze(

        {

            "neighbors":

            [

                {

                    "side":
                        "east",

                    "type":
                        "building"

                },


                {

                    "side":
                        "west",

                    "type":
                        "building"

                }

            ]

        }

    )



    analysis["neighbors"] = neighbors



    # =====================================
    # COURTYARD
    # =====================================


    courtyard_engine = CourtyardEngine()



    courtyard = courtyard_engine.generate(

        {

            "width":
                site_data["width"],

            "depth":
                site_data["depth"]

        },

        scenario["requirements"]["courtyard"]

    )



    analysis["courtyard"] = courtyard.get(

        "courtyard",

        {}

    )



    # =====================================
    # BUILDING FORM
    # =====================================


    form_solver = BuildingFormSolver()



    building_form = form_solver.solve(

        {

            "width":
                site_data["width"],

            "depth":
                site_data["depth"]

        },

        scenario["requirements"]

    )



    # =====================================
    # FINAL DECISION
    # =====================================


    design_engine = SiteDesignEngine()



    result = design_engine.generate(

        site.to_dict(),

        analysis,

        building_form.get(
            "building",
            building_form
        ),

        {

            "separation_joints":

            {}

        }

    )



    print(

        "\n========== FINAL SITE DESIGN =========="

    )


    print(

        result

    )



    assert result["building"]["placement"] == "north"



    print(

        "\n✅ SCENARIO FULL PIPELINE PASSED"

    )



if __name__ == "__main__":

    run()