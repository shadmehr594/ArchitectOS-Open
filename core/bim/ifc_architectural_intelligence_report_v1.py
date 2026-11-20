# ==========================================================
# IFC ARCHITECTURAL INTELLIGENCE REPORT V1
# ARCHITECTOS BIM ARCHITECTURAL ANALYSIS
# ==========================================================


import ifcopenshell



class IFCArchitecturalIntelligenceReportV1:


    VERSION = "1.0"



    def __init__(self):

        print(
            "🧠 IFC Architectural Intelligence Report v1.0 ACTIVE"
        )



    # ======================================================
    # GENERATE REPORT
    # ======================================================


    def generate(
        self,
        ifc_path
    ):


        model = ifcopenshell.open(
            ifc_path
        )



        walls = model.by_type(
            "IfcWall"
        )


        doors = model.by_type(
            "IfcDoor"
        )


        windows = model.by_type(
            "IfcWindow"
        )


        storeys = model.by_type(
            "IfcBuildingStorey"
        )



        # ==============================================
        # ARCHITECTURAL SUMMARY
        # ==============================================


        summary = {


            "floors":
                len(storeys),


            "walls":
                len(walls),


            "doors":
                len(doors),


            "windows":
                len(windows),


            "openings":
                len(doors)
                +
                len(windows)

        }



        # ==============================================
        # OBSERVATIONS
        # ==============================================


        observations = []



        observations.append(

            f"{len(storeys)} storeys detected"

        )



        observations.append(

            f"{len(walls)} architectural walls detected"

        )



        observations.append(

            f"{len(doors)} doors and {len(windows)} windows detected"

        )



        # ==============================================
        # HEALTH SCORE
        # ==============================================


        score = 100



        if len(walls) == 0:

            score -= 30



        if len(storeys) == 0:

            score -= 20



        if len(doors) + len(windows) == 0:

            score -= 10



        status = (

            "healthy"

            if score >= 90

            else

            "warning"

        )



        # ==============================================
        # FINAL REPORT
        # ==============================================


        return {


            "engine":
                "IFC_ARCHITECTURAL_INTELLIGENCE_REPORT_V1",


            "version":
                self.VERSION,


            "file":
                ifc_path,


            "building_summary":
                summary,


            "architectural_quality":
            {

                "score":
                    score,

                "status":
                    status

            },


            "observations":
                observations,


            "planner_ready":
                True


        }