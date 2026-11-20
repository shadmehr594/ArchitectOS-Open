from core.bim.ifc_health_report import IFCHealthReportV1



def test_ifc_health_report_v1():


    print(
        "\n====== IFC HEALTH REPORT V1 ======"
    )



    validator_result = {


        "engine":
            "IFC_QUALITY_VALIDATOR_V2",


        "version":
            "2.2",


        "status":
            "passed",



        "health":
        {

            "score":
                100,


            "geometry":
                "passed",


            "placement":
                "passed",


            "geometry_content":
                "passed",


            "placement_chain":
                "passed"

        },



        "statistics":
        {

            "storeys":
                1,


            "walls":
                1,


            "columns":
                1,


            "beams":
                0,


            "slabs":
                0,


            "doors":
                0,


            "windows":
                1

        },



        "geometry_errors":
            [],


        "placement_errors":
            [],


        "placement_chain_errors":
            [],


        "geometry_content_errors":
            []

    }




    report_engine = IFCHealthReportV1()



    report = report_engine.generate(

        validator_result

    )



    print(

        "\n====== HEALTH REPORT RESULT ======"

    )


    print(

        report

    )



    assert (

        report["engine"]

        ==

        "IFC_HEALTH_REPORT_V1"

    )


    assert (

        report["status"]

        ==

        "passed"

    )


    assert (

        report["health"]["score"]

        ==

        100

    )


    assert (

        report["health"]["geometry"]

        ==

        "passed"

    )


    assert (

        report["health"]["placement"]

        ==

        "passed"

    )


    assert (

        report["model"]["walls"]

        ==

        1

    )


    assert (

        report["model"]["columns"]

        ==

        1

    )


    assert (

        report["model"]["windows"]

        ==

        1

    )


    assert (

        len(report["errors"]["geometry"])

        ==

        0

    )


    assert (

        "IFC model is healthy"

        in

        report["recommendations"]

    )



    print(

        "\n====== TEST PASSED ======"

    )




if __name__ == "__main__":


    test_ifc_health_report_v1()