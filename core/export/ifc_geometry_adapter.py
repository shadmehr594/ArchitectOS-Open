import ifcopenshell
import ifcopenshell.geom


class IFCGeometryAdapter:


    VERSION = "1.0"


    def __init__(self, model):

        self.model = model

        print(
            "🏗️ IFC Geometry Adapter v1.0 ACTIVE"
        )


    def create_box_geometry(
        self,
        entity,
        width,
        depth,
        height
    ):

        print(
            "CREATE BOX GEOMETRY:",
            entity.Name
        )


        context = self.model.create_entity(
            "IfcGeometricRepresentationContext",
            ContextIdentifier="Body",
            ContextType="Model",
            CoordinateSpaceDimension=3,
            Precision=0.00001
        )


        return context