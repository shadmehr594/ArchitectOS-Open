import ifcopenshell
import ifcopenshell.guid
import os


class IFCWriter:

    VERSION = "1.3"


    def __init__(self):

        self.model = None

        print(
            f"🏗️ IFC Writer v{self.VERSION} ACTIVE"
        )


    # ==========================================
    # INIT MODEL
    # ==========================================

    def create_model(self):

        self.model = ifcopenshell.file(
            schema="IFC4"
        )


        self.project = self.model.create_entity(
            "IfcProject",
            GlobalId=ifcopenshell.guid.new(),
            Name="ArchitectOS BIM Project"
        )


        self.site = self.model.create_entity(
            "IfcSite",
            GlobalId=ifcopenshell.guid.new(),
            Name="ArchitectOS Site"
        )


        self.building = self.model.create_entity(
            "IfcBuilding",
            GlobalId=ifcopenshell.guid.new(),
            Name="ArchitectOS Building"
        )


        self.storey = self.model.create_entity(
            "IfcBuildingStorey",
            GlobalId=ifcopenshell.guid.new(),
            Name="Level 0"
        )


        return self.model



    # ==========================================
    # GEOMETRY HELPERS
    # ==========================================

    def normalize_point(self, p):

        if p is None:
            return (
                0.0,
                0.0,
                0.0
            )


        if isinstance(p, dict):

            return (
                float(p.get("x",0)),
                float(p.get("y",0)),
                float(p.get("z",0))
            )


        if len(p) == 2:

            return (
                float(p[0]),
                float(p[1]),
                0.0
            )


        return (
            float(p[0]),
            float(p[1]),
            float(p[2])
        )



    def create_point(
        self,
        p
    ):

        return self.model.create_entity(
            "IfcCartesianPoint",
            Coordinates=self.normalize_point(p)
        )



    def create_polyline(
        self,
        points
    ):

        return self.model.create_entity(
            "IfcPolyline",
            Points=[
                self.create_point(p)
                for p in points
            ]
        )



    # ==========================================
    # WALL
    # ==========================================

    def add_wall(
        self,
        wall
    ):

        element = self.model.create_entity(
            "IfcWall",
            GlobalId=ifcopenshell.guid.new(),
            Name="ArchitectOS Wall"
        )


        if (
            "start" in wall
            and
            "end" in wall
        ):

            self.create_polyline(
                [
                    wall["start"],
                    wall["end"]
                ]
            )


        return element



    # ==========================================
    # SLAB
    # ==========================================

    def add_slab(
        self,
        floor
    ):

        return self.model.create_entity(
            "IfcSlab",
            GlobalId=ifcopenshell.guid.new(),
            Name="ArchitectOS Floor"
        )



    # ==========================================
    # SPACE
    # ==========================================

    def add_space(
        self,
        room
    ):

        return self.model.create_entity(
            "IfcSpace",
            GlobalId=ifcopenshell.guid.new(),
            Name=room.get(
                "name",
                "Room"
            )
        )



    # ==========================================
    # COLUMN
    # ==========================================

    def add_column(
        self,
        column
    ):

        return self.model.create_entity(
            "IfcColumn",
            GlobalId=ifcopenshell.guid.new(),
            Name="ArchitectOS Column"
        )



    # ==========================================
    # BEAM
    # ==========================================

    def add_beam(
        self,
        beam
    ):

        return self.model.create_entity(
            "IfcBeam",
            GlobalId=ifcopenshell.guid.new(),
            Name="ArchitectOS Beam"
        )



    # ==========================================
    # EXPORT
    # ==========================================

    def export(
        self,
        geometry,
        structure,
        output="exports/ArchitectOS_Project.ifc"
    ):


        self.create_model()


        count = 0


        for wall in geometry.get(
            "walls",
            []
        ):

            self.add_wall(
                wall
            )

            count += 1



        for floor in geometry.get(
            "floors",
            []
        ):

            self.add_slab(
                floor
            )

            count += 1



        for room in geometry.get(
            "rooms",
            []
        ):

            self.add_space(
                room
            )

            count += 1



        for col in structure.get(
            "columns",
            []
        ):

            self.add_column(
                col
            )

            count += 1



        for beam in structure.get(
            "beams",
            []
        ):

            self.add_beam(
                beam
            )

            count += 1



        os.makedirs(
            os.path.dirname(output),
            exist_ok=True
        )


        self.model.write(
            output
        )


        return {

            "status":
                "exported",

            "file":
                output,

            "schema":
                self.model.schema,

            "elements":
                count

        }