from .building_image_analyzer import BuildingImageAnalyzer
from .facade_understanding import FacadeUnderstanding
from .image_to_bim_mapper import ImageToBIMMapper
from .building_parser import BuildingParser
from .bim_element_mapper import BIMElementMapper



class VisionPipeline:


    def __init__(self):

        self.analyzer = BuildingImageAnalyzer()

        self.facade = FacadeUnderstanding()

        self.parser = BuildingParser()

        self.mapper = ImageToBIMMapper()

        self.element_mapper = BIMElementMapper()


        print(
            "🧠 Vision Pipeline v66.3 ACTIVE"
        )



    def run(self, image_path):


        building = self.analyzer.analyze(
            image_path
        )


        facade = self.facade.analyze(
            building
        )


        structure = self.parser.parse(
            building
        )


        bim = self.mapper.convert(
            building,
            facade
        )


        bim["structure"] = structure



        elements = self.element_mapper.map(
            structure
        )


        bim["elements"] = elements



        return {


            "vision_result":

            building,


            "facade_result":

            facade,


            "structure_result":

            structure,


            "bim_result":

            bim

        }