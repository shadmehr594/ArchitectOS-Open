from core.bim.bim_level_manager import BIMLevelManager
from core.bim.spatial_hierarchy_engine import SpatialHierarchyEngine
from core.bim.room_intelligence_engine import RoomIntelligenceEngine
from core.bim.bim_object_intelligence_engine import BIMObjectIntelligenceEngine
from core.bim.bim_furniture_placement_engine import BIMFurniturePlacementEngine
from core.bim.semantic_bim_engine import SemanticBIMEngine
from core.bim.opening_intelligence_engine import OpeningIntelligenceEngine
from core.bim.circulation_intelligence_engine import CirculationIntelligenceEngine
from core.bim.mep_intelligence_engine import MEPIntelligenceEngine
from core.bim.bim_coordination_engine import BIMCoordinationEngine
from core.bim.bim_clash_detection_engine import BIMClashDetectionEngine
from core.bim.bim_validation_intelligence_engine import BIMValidationIntelligenceEngine
from core.bim.bim_query_intelligence_engine import BIMQueryIntelligenceEngine
from core.bim.bim_reasoning_engine import BIMReasoningIntelligenceEngine
from core.bim.bim_ai_planner_engine import BIMAIPlannerEngine
from core.bim.bim_export_engine import BIMExportIntelligenceEngine
from core.bim.bim_ifc_intelligence_engine import BIMIFCIntelligenceEngine
from core.bim.bim_revit_family_intelligence import BIMRevitFamilyIntelligenceEngine
from core.bim.bim_digital_twin_layer import BIMDigitalTwinLayer
from core.bim.bim_simulation_intelligence_engine import BIMSimulationIntelligenceEngine
from core.bim.bim_scenario_intelligence_engine import BIMScenarioIntelligenceEngine
from core.bim.bim_optimization_intelligence_engine import BIMOptimizationIntelligenceEngine
from core.bim.bim_knowledge_intelligence_engine import BIMKnowledgeIntelligenceEngine
from core.intelligence.experience_memory import ExperienceMemoryEngine
from core.intelligence.decision_intelligence import DecisionIntelligenceEngine
from core.intelligence.autonomous_agent import AutonomousAgentEngine
from core.intelligence.cross_domain_intelligence import CrossDomainIntelligenceEngine
from core.bim.geometry_adapter import GeometryAdapter



class BIMSceneGraphEngine:


    """
    ArchitectOS BIM Scene Graph Core v56


    Intelligence:

        BIMLevelManager v38

        SpatialHierarchyEngine v39

        RoomIntelligenceEngine v40

        BIMObjectIntelligenceEngine v41.1

        BIMFurniturePlacementEngine v42.1

        SemanticBIMEngine v43

        OpeningIntelligenceEngine v44

        CirculationIntelligenceEngine v45

        MEPIntelligenceEngine v46

        BIMCoordinationEngine v47

        BIMClashDetectionEngine v48

        BIMValidationIntelligenceEngine v49

        BIMQueryIntelligenceEngine v50

        BIMReasoningIntelligenceEngine v51

        BIMAIPlannerIntelligenceEngine v52

        BIMExportIntelligenceEngine v53


    """



    def __init__(self):

        print(
            "🏗️ BIM Scene Graph Core Engine v56.0 ACTIVE"
        )


        self.level_manager = BIMLevelManager()

        self.spatial_engine = SpatialHierarchyEngine()

        self.room_engine = RoomIntelligenceEngine()

        self.object_engine = BIMObjectIntelligenceEngine()

        self.furniture_engine = BIMFurniturePlacementEngine()

        self.semantic_engine = SemanticBIMEngine()

        self.opening_engine = OpeningIntelligenceEngine()

        self.circulation_engine = CirculationIntelligenceEngine()

        self.mep_engine = MEPIntelligenceEngine()

        self.coordination_engine = BIMCoordinationEngine()

        self.clash_engine = BIMClashDetectionEngine()

        self.validation_engine = BIMValidationIntelligenceEngine()

        self.query_engine = BIMQueryIntelligenceEngine()

        self.reasoning_engine = BIMReasoningIntelligenceEngine()

        self.planner_engine = BIMAIPlannerEngine()

        self.export_engine = BIMExportIntelligenceEngine()

        self.ifc_engine = BIMIFCIntelligenceEngine()

        self.revit_engine = BIMRevitFamilyIntelligenceEngine()

        self.digital_twin_engine = BIMDigitalTwinLayer()

        self.simulation_engine = BIMSimulationIntelligenceEngine()

        self.scenario_engine = BIMScenarioIntelligenceEngine()

        self.optimization_engine = BIMOptimizationIntelligenceEngine()
        
        self.knowledge_engine = BIMKnowledgeIntelligenceEngine()

        self.experience_engine = ExperienceMemoryEngine()

        self.decision_engine = DecisionIntelligenceEngine()

        self.agent_engine = AutonomousAgentEngine()

        self.cross_domain_engine = CrossDomainIntelligenceEngine()




    def build(
        self,
        structural,
        geometry
    ):


        print(
            "▶️ BUILD BIM SCENE GRAPH v56"
        )


        structural = self._unwrap(structural)

        geometry = self._unwrap(geometry)

        geometry_adapter = GeometryAdapter(geometry)



        graph = {


            "type":
                "Building",


            "version":
                "BIM_GRAPH_v50.0",


            "levels": [],

            "elements": [],

            "relationships": [],


            "spatial": {},

            "rooms": {},

            "objects": {},

            "furniture": {},

            "semantic": {},

            "openings": {},

            "circulation": {},

            "mep": {},

            "coordination": {},

            "clashes": {},

            "validation": {},

            "query": {},

            "reasoning": {},

            "planner": {},

            "export": {},

            "ifc": {},

            "revit": {},

            "digital_twin": {},



            "systems":
            {
                "materials": {},
                "furniture": {},
                "lighting": {},
                "camera": {}
            }

        }


        elements = []



        for category in [

            "columns",
            "beams",
            "slabs",
            "walls"

        ]:


            items = structural.get(
                category,
                []
            )


            for index,item in enumerate(items):


                element = dict(item)



                element.setdefault(
                    "id",
                    f"{category}_{index}"
                )



                element.setdefault(
                    "category",
                    "structural"
                )



                element["bim_type"] = category[:-1]



                element.setdefault(
                    "properties",
                    {}
                )



                element = self.level_manager.normalize(
                    element
                )


                elements.append(
                    element
                )




        graph["elements"] = elements





        graph["levels"] = self.level_manager.generate(
            elements
        )





        for element in elements:


            graph["relationships"].append(

                {

                    "from":
                        element["id"],


                    "to":
                        element["level"],


                    "type":
                        "belongs_to"

                }

            )






        columns = [

            e for e in elements

            if e["bim_type"] == "column"

        ]



        beams = [

            e for e in elements

            if e["bim_type"] == "beam"

        ]





        for column in columns:


            for beam in beams:


                if column["level"] == beam["level"]:


                    graph["relationships"].append(

                        {

                            "from":
                                column["id"],


                            "to":
                                beam["id"],


                            "type":
                                "supports"

                        }

                    )







        # ===============================
        # SPATIAL v39
        # ===============================


        graph["spatial"] = self.spatial_engine.build(

            elements,

            graph["levels"]

        )



        graph["spatial"]["geometry_connected"] = isinstance(
            geometry,
            dict
        )



        graph["spatial"]["mesh_count"] = len(

            geometry.get(
                "walls",
                []
            )

        )





        # ===============================
        # ROOM v40
        # ===============================


        graph["rooms"] = self.room_engine.build(

            graph["spatial"]

        )






        # ===============================
        # OBJECT v41
        # ===============================


        graph["objects"] = self.object_engine.build(

            graph["rooms"]

        )






        # ===============================
        # FURNITURE v42
        # ===============================


        graph["furniture"] = self.furniture_engine.build(

            graph["objects"]

        )






        # ===============================
        # SEMANTIC v43
        # ===============================


        graph["semantic"] = self.semantic_engine.build(

            graph["rooms"],

            graph["objects"],

            elements

        )






        # ===============================
        # OPENINGS v44
        # ===============================


        graph["openings"] = self.opening_engine.build(

            graph["rooms"],

            geometry

        )






        # ===============================
        # CIRCULATION v45
        # ===============================


        graph["circulation"] = self.circulation_engine.build(

            graph["rooms"],

            graph["openings"]

        )






        # ===============================
        # MEP v46
        # ===============================


        graph["mep"] = self.mep_engine.build(

            graph["rooms"],

            elements

        )






        # ===============================
        # COORDINATION INTELLIGENCE v47
        # ===============================


        graph["coordination"] = self.coordination_engine.build(

            graph["rooms"],

            graph["openings"],

            graph["circulation"],

            graph["mep"],

            graph["elements"]

        )





        # ===============================
        # CLASH DETECTION INTELLIGENCE v48
        # ===============================


        graph["clashes"] = self.clash_engine.build(

            graph["elements"],

            graph["mep"],

            graph["rooms"],

            graph["furniture"]

        )





        # ===============================
        # VALIDATION INTELLIGENCE v49
        # ===============================


        graph["validation"] = self.validation_engine.build(

            graph["rooms"],

            graph["objects"],

            graph["furniture"],

            graph["mep"],

            graph["coordination"],

            graph["clashes"]

        )




        # ===============================
        # QUERY INTELLIGENCE v50
        # ===============================

        graph["query"] = self.query_engine.build(

            graph

        )




        # ===============================
        # REASONING v51
        # ===============================

        graph["reasoning"] = self.reasoning_engine.build(

            graph

        )




        # ===============================
        # AI PLANNER INTELLIGENCE v52
        # ===============================

        graph["planner"] = self.planner_engine.build(

            graph

        )




        # ===============================
        # EXPORT INTELLIGENCE v53
        # ===============================

        graph["export"] = self.export_engine.build(

            graph

        )




        # ===============================
        # IFC INTELLIGENCE v54
        # ===============================

        graph["ifc"] = self.ifc_engine.build(

            graph

        )




        # ===============================
        # REVIT FAMILY INTELLIGENCE v55
        # ===============================

        graph["revit"] = self.revit_engine.build(

            graph

        )




        # ===============================
        # DIGITAL TWIN v56
        # ===============================

        graph["digital_twin"] = self.digital_twin_engine.build(

            graph

        )




        # ===============================
        # SIMULATION INTELLIGENCE v57
        # ===============================

        graph["simulation"] = self.simulation_engine.build(

            graph

        )



        # ===============================
        # SCENARIO INTELLIGENCE v58
        # ===============================

        print(
            "⚙️ BIM Scenario Intelligence Engine v58.0 ACTIVE"
        )

        print(
            "▶️ BUILD BIM SCENARIO v58"
        )

        graph["scenario"] = self.scenario_engine.build(
            graph
        )




        # ===============================
        # OPTIMIZATION INTELLIGENCE v59
        # ===============================

        print(
            "⚙️ BIM Optimization Intelligence Engine v59.0 ACTIVE"
        )

        print(
            "▶️ BUILD BIM OPTIMIZATION v59"
        )

        graph["optimization"] = self.optimization_engine.build(
            graph
        )




        # ===============================
        # KNOWLEDGE INTELLIGENCE v60
        # ===============================

        print(
            "🧠 BIM Knowledge Intelligence Engine v60.0 ACTIVE"
        )

        print(
            "▶️ BUILD BIM KNOWLEDGE v60"
        )

        graph["knowledge"] = self.knowledge_engine.build(
            graph
        )




        # ===============================
        # EXPERIENCE MEMORY v61
        # ===============================

        print(
            "🧠 ArchitectOS Experience Memory v61.0 ACTIVE"
        )

        print(
            "▶️ BUILD EXPERIENCE MEMORY v61"
        )

        graph["experience"] = self.experience_engine.build(
            graph
        )




        # ===============================
        # DECISION INTELLIGENCE v62
        # ===============================

        print(
            "🧠 ArchitectOS Decision Intelligence v62.0 ACTIVE"
        )

        print(
            "▶️ BUILD DECISION INTELLIGENCE v62"
        )

        graph["decision"] = self.decision_engine.build(
            graph
        )




        # ===============================
        # AUTONOMOUS AGENT v63
        # ===============================

        print(
            "🤖 ArchitectOS Autonomous Agent v63.0 ACTIVE"
        )

        print(
            "▶️ BUILD AUTONOMOUS AGENT v63"
        )

        graph["agent"] = self.agent_engine.build(
            graph
        )




        # ===============================
        # CROSS DOMAIN INTELLIGENCE v64
        # ===============================

        print(
            "🌐 ArchitectOS Cross Domain Intelligence v64.0 ACTIVE"
        )

        print(
            "▶️ BUILD CROSS DOMAIN INTELLIGENCE v64"
        )

        graph["cross_domain"] = self.cross_domain_engine.build(
            graph
        )




        # ===============================
        # MATERIAL INDEX
        # ===============================


        for element in elements:


            material = element.get(
                "material"
            )


            if material:


                graph["systems"]["materials"].setdefault(

                    material,

                    []

                )


                graph["systems"]["materials"][material].append(

                    element["id"]

                )







        print(
            f"✅ BIM GRAPH GENERATED: {len(elements)} elements"
        )


        print(
            f"🏢 LEVELS GENERATED: {len(graph['levels'])}"
        )


        print(
            f"🚪 ROOMS GENERATED: {len(graph['rooms'].get('rooms',[]))}"
        )


        print(
            f"🪑 OBJECTS GENERATED: {len(graph['objects'].get('objects',[]))}"
        )


        print(
            f"🛋️ FURNITURE GENERATED: {len(graph['furniture'].get('placements',[]))}"
        )


        print(
            f"🧠 SEMANTIC ROOMS: {len(graph['semantic'].get('rooms',[]))}"
        )


        print(
            f"🚪 DOORS GENERATED: {len(graph['openings'].get('doors',[]))}"
        )


        print(
            f"🪟 WINDOWS GENERATED: {len(graph['openings'].get('windows',[]))}"
        )


        print(
            f"🚶 CONNECTIONS GENERATED: {len(graph['circulation'].get('connections',[]))}"
        )


        print(
            f"🛣️ PATHS GENERATED: {len(graph['circulation'].get('paths',[]))}"
        )


        print(
            f"💡 LIGHTS GENERATED: {len(graph['mep'].get('electrical',{}).get('lights',[]))}"
        )


        print(
            f"🌬️ HVAC GENERATED: {len(graph['mep'].get('hvac',{}).get('units',[]))}"
        )


        print(
            f"🤝 COORDINATION ISSUES: {len(graph['coordination'].get('issues',[]))}"
        )

        print(
            f"💥 CLASHES GENERATED: {len(graph['clashes'].get('clashes',[]))}"
        )

        print(
            f"📦 EXPORT ENGINE: {graph['export'].get('engine')}"
        )

        print(
            f"📦 EXPORT LEVELS: {graph['export'].get('statistics',{}).get('levels',0)}"
        )


        print(
            f"⚠️ CLASH WARNINGS: {len(graph['clashes'].get('warnings',[]))}"
        )


        print(
            f"✅ VALIDATION ISSUES: {len(graph['validation'].get('issues',[]))}"
        )


        print(
            f"🔗 RELATIONSHIPS GENERATED: {len(graph['relationships'])}"
        )



        return graph



    # =====================================================
    # DATA UNWRAPPER
    # =====================================================

    def _unwrap(
        self,
        data
    ):


        if not isinstance(data, dict):

            return {}



        wrappers = [

            "structural_result",

            "geometry_result",

            "bim_result",

            "result",

            "data"

        ]



        for key in wrappers:


            if key in data:


                return self._unwrap(

                    data[key]

                )



        return data