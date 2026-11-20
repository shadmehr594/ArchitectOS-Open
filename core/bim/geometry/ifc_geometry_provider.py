import ifcopenshell
import ifcopenshell.guid


print("########################################")
print("USING IFC_GEOMETRY_PROVIDER V2.1")
print(__file__)
print("########################################")


class IFCGeometryProvider:

    VERSION = "2.1"


    def __init__(
        self,
        model,
        owner_history,
        context=None
    ):

        self.model = model
        self.owner_history = owner_history
        self.context = context


        print(
            "\n====== IFC GEOMETRY PROVIDER INIT ======"
        )

        print(
            "CONTEXT:",
            self.context
        )


        if self.context:

            print(
                "CONTEXT TYPE:",
                self.context.is_a()
            )

        else:

            print(
                "⚠️ CONTEXT IS NONE"
            )



    # ==================================================
    # HELPERS
    # ==================================================


    def create_point(
        self,
        x,
        y,
        z=0.0
    ):

        return self.model.create_entity(

            "IfcCartesianPoint",

            Coordinates=(
                float(x),
                float(y),
                float(z)
            )

        )



    def create_direction(
        self,
        x,
        y,
        z
    ):

        return self.model.create_entity(

            "IfcDirection",

            DirectionRatios=(
                float(x),
                float(y),
                float(z)
            )

        )


    def create_axis_placement(
        self,
        x=0,
        y=0,
        z=0,
        rotation=0
    ):

        point = self.create_point(
            x,
            y,
            z
        )


        placement = self.model.create_entity(

            "IfcAxis2Placement3D",

            Location=point

        )


        return placement



    def create_beam_axis_placement(
        self,
        x,
        y,
        z,
        direction
    ):

        point = self.create_point(
            x,
            y,
            z
        )


        if direction == "Y":

            placement = self.model.create_entity(

                "IfcAxis2Placement3D",

                Location=point,

                Axis=self.create_direction(
                    0,
                    0,
                    1
                ),

                RefDirection=self.create_direction(
                    0,
                    1,
                    0
                )

            )

        else:

            placement = self.model.create_entity(

                "IfcAxis2Placement3D",

                Location=point,

                Axis=self.create_direction(
                    0,
                    0,
                    1
                ),

                RefDirection=self.create_direction(
                    1,
                    0,
                    0
                )

            )


        return placement



    def get_element_position(
        self,
        data
    ):

        return self.create_axis_placement(

            float(data.get("x", 0)),

            float(data.get("y", 0)),

            float(data.get("z", 0))

        )



    def create_shape_representation(
        self,
        solid
    ):


        shape = self.model.create_entity(

            "IfcShapeRepresentation",

            ContextOfItems=self.context,

            RepresentationIdentifier="Body",

            RepresentationType="SweptSolid",

            Items=[solid]

        )


        return self.model.create_entity(

            "IfcProductDefinitionShape",

            Representations=[shape]

        )



    # ==================================================
    # WALL GEOMETRY
    # ==================================================


    def create_wall_geometry(
        self,
        wall_data
    ):


        print(
            "\n====== CREATE WALL GEOMETRY INPUT ======"
        )

        print(
            {
                "id": wall_data.get("id"),
                "level": wall_data.get("level"),
                "z": wall_data.get("z"),
                "start": wall_data.get("start"),
                "end": wall_data.get("end"),
                "x": wall_data.get("x"),
                "y": wall_data.get("y"),
                "width": wall_data.get("width"),
                "length": wall_data.get("length"),
                "height": wall_data.get("height"),
                "thickness": wall_data.get("thickness")
            }
        )

        print(
            "========================================"
        )


        print(
            "\n====== IFC WALL INPUT DEBUG ======"
        )

        print(
            wall_data
        )

        print(
            "================================="
        )

        print(
            "🧱 CREATE WALL GEOMETRY v2.2:",
            wall_data
        )


        print(
            "\n====== WALL PROVIDER INPUT CHECK ======"
        )

        print(
            {
                "id": wall_data.get("id"),
                "start": wall_data.get("start"),
                "end": wall_data.get("end"),
                "length": wall_data.get("length"),
                "thickness": wall_data.get("thickness"),
                "level": wall_data.get("level")
            }
        )

        print(
            "========================================"
        )

        start = wall_data.get(
            "start"
        )

        end = wall_data.get(
            "end"
        )

        print(
            "========== WALL AXIS COUNT DEBUG =========="
        )

        print(
            {
                "id": wall_data.get("id"),
                "start": start,
                "end": end,
                "dx": end[0]-start[0],
                "dy": end[1]-start[1]
            }
        )

        print(
            "============================================"
        )


        print(
            "\n====== WALL AXIS SOURCE CHECK ======"
        )

        print(
            {
                "id": wall_data.get("id"),
                "start": start,
                "end": end,
                "dx": end[0] - start[0],
                "dy": end[1] - start[1]
            }
        )

        print(
            "===================================="
        )
        

        print(
            "\n====== WALL AXIS INPUT SUMMARY ======"
        )

        print(
            {
                "id": wall_data.get("id"),
                "level": wall_data.get("level"),
                "start": start,
                "end": end,
                "dx": end[0] - start[0],
                "dy": end[1] - start[1]
            }
        )

        print(
            "======================================"
        )


        print(
            "\n====== WALL RAW COORD DEBUG ======"
        )

        print(
            {
                "id": wall_data.get("id"),
                "start": start,
                "end": end,
                "length": wall_data.get("length")
            }
        )

        print(
            "=================================="
        )

        height = float(
            wall_data.get(
                "height",
                3.2
            )
        )

        thickness = float(
            wall_data.get(
                "thickness",
                0.20
            )
        )

        # ==========================================
        # WALL LENGTH RESOLUTION
        # ==========================================

        length = wall_data.get(
            "length"
        )

        if length is not None:

            length = float(
                length
            )

        elif start is not None and end is not None:

            if len(start) < 2 or len(end) < 2:

                raise ValueError(
                    "Wall start/end must contain x and y coordinates."
                )

            x1, y1 = start[:2]

            x2, y2 = end[:2]


            length = (
                (x2 - x1) ** 2
                +
                (y2 - y1) ** 2
            ) ** 0.5

        else:

            raise ValueError(
                "Wall geometry requires either "
                "'length' or both 'start' and 'end'."
            )

        if length <= 0:

            raise ValueError(
                f"Wall length must be greater than zero. "
                f"Received: {length}"
            )

            print(
                "\n====== WALL RESOLVED LENGTH DEBUG ======"
            )

            print(
                {
                    "id": wall_data.get("id"),
                    "resolved_length": length,
                    "height": height,
                    "thickness": thickness
                }
            )

            print(
                "========================================"
            )

        if height <= 0:

            raise ValueError(
                f"Wall height must be greater than zero. "
                f"Received: {height}"
            )

        if thickness <= 0:

            raise ValueError(
                f"Wall thickness must be greater than zero. "
                f"Received: {thickness}"
            )

        print(
            "WALL DIMENSIONS:",
            {
                "length": length,
                "height": height,
                "thickness": thickness
            }
        )


        # ==========================================
        # WALL DIRECTION
        # ==========================================


        x1, y1 = start[:2]
        x2, y2 = end[:2]

        dx = x2 - x1
        dy = y2 - y1

        if abs(dy) > abs(dx):

            print(
                "🟦 WALL Y AXIS DETECTED"
            )

        else:

            print(
                "🟥 WALL X AXIS DETECTED"
            )

        print(
            {
                "id": wall_data.get("id"),
                "start": start,
                "end": end
            }
        )


        # ==========================================
        # WALL PROFILE
        # ==========================================

        print(
            "\n====== WALL PROFILE INPUT DEBUG ======"
        )

        print(
            {
                "XDim": length,
                "YDim": thickness
            }
        )

        print(
            "====================================="
        )

        print(
            "====== WALL PROFILE AXIS INPUT ======"
        )

        print(
            {
                "start": start,
                "end": end,
                "dx": dx,
                "dy": dy,
                "abs_dx": abs(dx),
                "abs_dy": abs(dy),
                "condition_Y": abs(dy) > abs(dx)
            }
        )

        print(
            "====================================="
        )

        if abs(dy) > abs(dx):

            print(
                "====== WALL RAW GEOMETRY ENTER PROVIDER ======"
            )

            print(
                {
                    "start": start,
                    "end": end,
                    "length": length,
                    "thickness": thickness
                }
            )

            print(
                "=============================================="
            )

            # ==============================
            # Y AXIS WALL
            # ==============================

            print(
                "🟦 USING Y WALL PROFILE"
            )

            profile = self.model.create_entity(
                "IfcRectangleProfileDef",
                ProfileType="AREA",
                XDim=float(thickness),
                YDim=float(length)
            )


        else:

            # ==============================
            # X AXIS WALL
            # ==============================

            print(
                "🟥 USING X WALL PROFILE"
            )

            profile = self.model.create_entity(
                "IfcRectangleProfileDef",
                ProfileType="AREA",
                XDim=float(length),
                YDim=float(thickness)
            )

        print(
            "====== WALL PROFILE CREATED ======"
        )

        print(
            {
                "axis": "Y" if abs(dy) > abs(dx) else "X",
                "XDim": profile.XDim,
                "YDim": profile.YDim
            }
        )

        print(
            "=================================="
        )

        # ==========================================
        # WALL Z
        # ==========================================


        wall_z = wall_data.get(
            "z",
            0
        )


        # ==========================================
        # WALL PLACEMENT
        # ==========================================

        print(
            "RAW WALL BEFORE AXIS CHECK:",
            {
                "start": (x1, y1),
                "end": (x2, y2),
                "dx": dx,
                "dy": dy
            }
        )


        if abs(dy) > abs(dx):

            # ==============================
            # Y AXIS WALL
            # ==============================

            print(
                "🟦 WALL Y AXIS PLACEMENT"
            )

            wall_position = self.create_axis_placement(
                x1 + thickness / 2,
                y1 + length / 2,
                0
            )


        else:

            # ==============================
            # X AXIS WALL
            # ==============================

            print(
                "🟥 WALL X AXIS PLACEMENT"
            )

            wall_position = self.create_axis_placement(
                x1 + length / 2,
                y1 + thickness / 2,
                0
            )


        print(
            "====== WALL AXIS DECISION ======"
        )

        print(
            {
                "id": wall_data.get("id"),
                "start": (x1, y1),
                "end": (x2, y2),
                "dx": dx,
                "dy": dy,
                "axis": "Y"
                    if abs(dy) > abs(dx)
                    else "X",
                "length": length,
                "thickness": thickness,
                "position":
                    wall_position.Location.Coordinates
            }
        )

        print(
            "================================"
        )


        print(
            "\n====== WALL FINAL POSITION DEBUG ======"
        )

        print(
            {
                "id": wall_data.get("id"),
                "axis": wall_position.Location.Coordinates,
                "direction": "Y"
                    if abs(dy) > abs(dx)
                    else "X"
            }
        )

        print(
            "========================================"
        )


        print(
            "====== WALL DIRECTION DEBUG ======"
        )

        print(
            {
                "id": wall_data.get("id"),
                "start": start,
                "end": end,
                "dx": dx,
                "dy": dy
            }
        )

        print(
            "=================================="
        )

        

        print(
            "\n====== WALL PLACEMENT Z DEBUG ======"
        )

        print(
            {
                "id": wall_data.get("id"),
                "level": wall_data.get("level"),
                "wall_z": wall_z,
                "x": x1,
                "y": y1
            }
        )

        print(
            "===================================="
        )

        print(
            {
                "id": wall_data.get("id"),
                "level": wall_data.get("level"),
                "wall_z": wall_z,
                "x": x1,
                "y": y1
            }
        )

        print(
            "===================================="
        )

        # ==========================================
        # WALL EXTRUSION
        # ==========================================
        print(
            "\n====== WALL POSITION BEFORE SOLID DEBUG ======"
        )

        print(
            {
                "id": wall_data.get("id"),
                "start": wall_data.get("start"),
                "end": wall_data.get("end"),
                "length": length,
                "profile_center_offset_expected": length / 2
            }
        )

        print(
            "==============================================="
        )

        print(
            "\n====== WALL LOCAL ORIGIN DEBUG ======"
        )

        print(
            {
                "start": start,
                "end": end,
                "length": length
            }
        )

        print(
            "====================================="
        )

        print(
            "\n====== WALL POSITION BEFORE EXTRUSION ======"
        )

        print(
            {
                "id": wall_data.get("id"),
                "wall_position":
                    wall_position.Location.Coordinates
                    if wall_position
                    else None
            }
        )

        print(
            "============================================="
        )



        solid = self.create_extrusion(
            profile,
            height,
            wall_position
        )


        print(
            "\n====== WALL GEOMETRY COORDINATE TEST ======"
        )

        print(
            {
                "wall_id": wall_data.get("id"),
                "axis": "Y" if abs(dy) > abs(dx) else "X",

                "source_start": start,
                "source_end": end,

                "profile_XDim":
                    float(solid.SweptArea.XDim),

                "profile_YDim":
                    float(solid.SweptArea.YDim),

                "solid_position":
                    solid.Position.Location.Coordinates,

                "depth":
                    float(solid.Depth)
            }
        )

        print(
            "============================================"
        )


        print(
            "\n====== WALL EXTRUSION INPUT OBJECT DEBUG ======"
        )

        print(
            {
                "profile": profile,
                "position_argument": wall_position
            }
        )

        print(
            "==============================================="
        )

        print(
            "\n====== WALL POSITION AFTER EXTRUSION ======"
        )

        print(
            {
                "id": wall_data.get("id"),
                "solid_position":
                    solid.Position.Location.Coordinates
            }
        )

        print(
            "==========================================="
        )


        print(
            "\n====== WALL SOLID DEBUG ======"
        )
 
        print(
            {
                "id": wall_data.get("id"),
                "position":
                    solid.Position.Location.Coordinates,

                "profile_x":
                    solid.SweptArea.XDim,

                "profile_y":
                    solid.SweptArea.YDim,

                "depth":
                    solid.Depth
            }
        )

        print(
            "================================"
        )

        print(
            "\n====== WALL SOLID RESULT DEBUG ======"
        )

        print(
            {
                "id": wall_data.get("id"),
                "level": wall_data.get("level"),
                "wall_z": wall_data.get("z"),
                "height": height,
                "position": wall_position
            }
        )

        print(
            "====================================="
        )

        # ==========================================
        # IFC SHAPE REPRESENTATION
        # ==========================================

        result = self.create_shape_representation(
            solid
        )

        print(
            "✅ WALL SHAPE CREATED",
            result
        )

        print(
            "\n====== WALL SOLID BEFORE REPRESENTATION DEBUG ======"
        )

        print(
            {
                "id": wall_data.get("id"),
                "start": wall_data.get("start"),
                "end": wall_data.get("end"),
                "length": length,
                "profile": {
                    "x": length,
                    "y": thickness
                }
            }
        )

        print(
            "SOLID:",
            solid
        )

        print(
            "===================================================="
        )

        return result
    # ==================================================
    # COLUMN GEOMETRY
    # ==================================================


    def create_column_geometry(
        self,
        column_data
    ):


        print(
            "\n====== IFC COLUMN GEOMETRY INPUT ======"
        )

        print(
            column_data
        )

        print(
            "======================================"
        )


        print(
            "\n====== OCC COLUMN GEOMETRY INPUT ======",
            {
                "id": column_data.get("id"),

                "x": column_data.get("x"),
                "y": column_data.get("y"),
                "z": column_data.get("z"),

                "width": column_data.get("width"),
                "depth": column_data.get("depth"),

                "height": column_data.get("height"),

                "level": column_data.get("level")
            }
        )


        print(

            "🏛 CREATE COLUMN GEOMETRY:",

            column_data

        )


        x = float(

            column_data.get(
                "x",
                0
            )

        )


        y = float(

            column_data.get(
                "y",
                0
            )

        )

        print(
            "\n====== COLUMN XYZ AFTER CAST DEBUG ======"
        )

        print(
            {
                "id": column_data.get("id"),
                "x": x,
                "y": y,
                "width": column_data.get("width"),
                "depth": column_data.get("depth")
            }
        )

        print(
            "========================================="
        )


        print(
            "====== COLUMN CORNER TEST ======",
            {
                "id": column_data.get("id"),
                "x": x,
                "y": y,
                "width": column_data.get("width"),
                "depth": column_data.get("depth"),
                "corner_end_x": x + column_data.get("width",0.3),
                "corner_end_y": y + column_data.get("depth",0.3)
            }
        )

        print(
            "================================"
        )


        z = 0.0

        print(
            "COLUMN GEOMETRY Z:",
            {
                "id": column_data.get("id"),
                "z": z,
                "level": column_data.get("level")
            }
        )


        print(
            "COLUMN GEOMETRY Z:",
            {
                "id": column_data.get("id"),
                "z": z,
                "level": column_data.get("level")
            }
        )


        height = float(

            column_data.get(
                "height",
                3.2
            )

        )


        size_x = float(
            column_data.get(
                "width",
                0.30
            )
        )


        size_y = float(
            column_data.get(
                "depth",
                0.30
            ) 
        )
        



        profile = self.model.create_entity(

            "IfcRectangleProfileDef",

            ProfileType="AREA",

            XDim=size_x,

            YDim=size_y

        )


        print(
            "\n====== COLUMN RAW SIZE DEBUG ======"
        )

        print(
            {
                "id": column_data.get("id"),
                "size_x": size_x,
                "size_y": size_y
            }
        )

        print(
            "==================================="
        )



        print(
            "====== BEFORE COLUMN AXIS PLACEMENT ======",
            {
                "x": x,
                "y": y,
                "z": z,
                "height": height
            }
        )


        print(
            "COLUMN GEOMETRY FINAL POSITION BEFORE AXIS:",
            {
                "id": column_data.get("id"),
                "x": x,
                "y": y,
                "z": z,
                "level": column_data.get("level")
            }
        )

        column_position = self.create_axis_placement(
            size_x / 2,
            size_y / 2,
            z
        )


        print(
            "\n====== COLUMN AXIS FINAL DEBUG ======"
        )

        print(
            {
                "id": column_data.get("id"),

                "axis_xyz":
                    column_position.Location.Coordinates,

                "profile":
                    {
                        "x": size_x,
                        "y": size_y
                    },

                "height":
                    height,

                "level":
                    column_data.get("level")
            }
        )

        print(
            "======================================"
        )




        solid = self.model.create_entity(

            "IfcExtrudedAreaSolid",

            SweptArea=profile,

            Position=column_position,

            ExtrudedDirection=self.create_direction(
                0,
                0,
                1
            ),

            Depth=height

        )


        print(
            "\n====== COLUMN SOLID DEBUG ======"
        )

        print(
            {
                "id": column_data.get("id"),

                "solid_position":
                    solid.Position.Location.Coordinates,

                "depth":
                    solid.Depth,

                "profile":
                    {
                        "x":
                            solid.SweptArea.XDim,

                        "y":
                            solid.SweptArea.YDim
                    }
                }
            )

        print(
            "================================="
        )



        shape = self.create_shape_representation(

            solid

        )


        print(
            "\n====== COLUMN FINAL GEOMETRY DEBUG ======"
        )

        print(
            {
                "id": column_data.get("id"),
                "profile_x": size_x,
                "profile_y": size_y,
                "height": height,
                "placement": column_position.Location.Coordinates
            }
        )

        print(
            "=========================================="
        )


        print(

            "✅ COLUMN SHAPE CREATED",

            shape

        )

        print(
            "\n====== FINAL COLUMN GEOMETRY CONTRACT ======"
        )

        print(
            {
                "id": column_data.get("id"),
                "level": column_data.get("level"),

                "profile_x":
                    solid.SweptArea.XDim,

                "profile_y":
                    solid.SweptArea.YDim,

                "depth":
                    solid.Depth,

                "placement":
                    solid.Position.Location.Coordinates
            }
        )

        print(
            "============================================="
        )


        return shape




    # ==================================================
    # BEAM GEOMETRY
    # ==================================================


    def create_beam_geometry(
        self,
        beam_data
    ):


        print(
            "\n====== IFC BEAM GEOMETRY INPUT ======"
        )

        print(
            beam_data
        )

        print(
            "===================================="
        )


        print(
            "\n====== BEAM GEOMETRY INTERNAL DEBUG ======"
        )

        print(
            {
                "id": beam_data.get("id"),
                "start": beam_data.get("start"),
                "end": beam_data.get("end"),
                "height": beam_data.get("height"),
                "depth": beam_data.get("depth")
            }
        )

        print(
            "=========================================="
        )


        print(
            "====== IFC BEAM GEOMETRY INPUT ======"
        )

        print(
            {
                "id": beam_data.get("id"),
                "start": beam_data.get("start"),
                "end": beam_data.get("end"),
                "z": beam_data.get("z"),
                "height": beam_data.get("height"),
                "depth": beam_data.get("depth")
            }
        )

        print(
            "===================================="
        )


        print(
            "\n====== GEOMETRY PROVIDER BEAM INPUT ======"
        )

        print(
            beam_data
        )

        print(
            "=========================================="
        )

        print(
            "====== RAW BEAM DATA ENTERED PROVIDER ======",
            beam_data
        )


        print(
            "\n====== OCC BEAM GEOMETRY INPUT ======",
            {
                "start": beam_data.get("start"),
                "end": beam_data.get("end"),
                "z": beam_data.get("z"),
                "height": beam_data.get("height"),
                "depth": beam_data.get("depth"),
                "level": beam_data.get("level")
            }
        )


        print(
            "BEAM GEOMETRY INTERNAL Z:",
            {
                "id": beam_data.get("id"),
                "level": beam_data.get("level"),
                "z": beam_data.get("z"),
                "start": beam_data.get("start"),
                "end": beam_data.get("end")
            }
        )


        print(

            "🏗 CREATE BEAM GEOMETRY:",

            beam_data

        )


        start = beam_data.get(

            "start",

            (0,0)

        )


        end = beam_data.get(

            "end",

            (0,0)

        )

        beam_z = beam_data.get(
            "z",
            beam_data.get(
                "elevation",
                0.0
            )
        )

        print(
            "\n====== BEAM GEOMETRY INPUT DEBUG ======"
        )

        print(
            {
                "id": beam_data.get("id"),
                "start": start,
                "end": end,
                "length": beam_data.get("length"),
                "rotation": beam_data.get("rotation")
            }
        )

        print(
            "======================================="
        )

        

        print(
            "BEAM GEOMETRY INPUT Z:",
            beam_z
        )



        x1,y1 = start

        x2,y2 = end

        dx = x2 - x1

        dy = y2 - y1

        if abs(dy) > abs(dx):

            print(
                "VERTICAL BEAM DETECTED",
                beam_data.get("id")
            )

        else:

            print(
                "HORIZONTAL BEAM DETECTED",
                beam_data.get("id")
            )

        print(
            "BEAM DIRECTION TEST",
            {
                "id": beam_data.get("id"),
                "dx": dx,
                "dy": dy
            }
        )

            


        print(
            "====== RAW BEAM COORDINATE CHECK ======"
        )

        print(
            {
                "id": beam_data.get("id"),
                "start": start,
                "end": end,
                "x1": x1,
                "y1": y1,
                "x2": x2,
                "y2": y2
            }
        )

        print(
            "======================================="
        )


        print(
            "====== FINAL BEAM GEOMETRY POSITION DEBUG ======",
            {
                "id": beam_data.get("id"),
                "level": beam_data.get("level"),
                "start": beam_data.get("start"),
                "end": beam_data.get("end"),
                "x1": x1,
                "y1": y1,
                "x2": x2,
                "y2": y2,
                "z": beam_z,
                "height": beam_data.get("height"),
                "depth": beam_data.get("depth")
            }
        )



        length = (

            (x2-x1)**2 +

            (y2-y1)**2

        ) ** 0.5



        if length == 0:

            print(

                "⚠️ ZERO BEAM LENGTH"

            )

            return None



        beam_depth = beam_data.get(
            "depth",
            0.25
        )




        profile = self.model.create_entity(

            "IfcRectangleProfileDef",

            ProfileType="AREA",

            XDim=float(length),

            YDim=float(beam_depth)

        )


        print(
            "\n====== BEAM PROFILE DEBUG ======"
        )

        print(
            {
                "XDim": length,
                "YDim": beam_depth,
                "length": length,
                "depth": beam_depth,
                "id": beam_data.get("id"),
                "level": beam_data.get("level")
            }
        )

        print(
            "================================"
        )


        print(
            "BEAM GEOMETRY INPUT Z:",
            beam_z
        )


        print(
            "====== BEFORE BEAM AXIS PLACEMENT ======"
        )

        print(
            {
                "beam_id": beam_data.get("id"),
                "level": beam_data.get("level"),
                "x1": x1,
                "y1": y1,
                "beam_z": beam_z
            }
        )



        beam_height = beam_data.get(
            "height",
            0.35
        )


        print(
            "FINAL BEAM AXIS INPUT:",
            {
                "beam_z": beam_z,
                "beam_height": beam_height,
                "level": beam_data.get("level")
            }
        )




        if abs(dy) > abs(dx):

            print(
                "USING Y BEAM PLACEMENT"
            )

            beam_position = self.create_axis_placement(
                length / 2,
                -beam_depth / 2,
                0
            )

        else:

            print(
                "USING X BEAM PLACEMENT"
            )

            beam_position = self.create_axis_placement(
                length / 2,
                beam_depth / 2,
                0
            )
        

        print(
            "====== BEAM AXIS FINAL DEBUG ======"
        )

        print(
            {
                "start": (x1, y1),
                "end": (x2, y2),
                "axis": beam_position.Location.Coordinates
            }
        )

        print(
            "==================================="
        )


        print(
            "====== BEAM CENTER CHECK ======"
        )


        print(
            "====== CREATED BEAM PLACEMENT ======",
            {
                "x": x1,
                "y": y1,
                "z": beam_z,
                "level": beam_data.get("level")
            }
        )


        print(
            "====== BEFORE BEAM AXIS PLACEMENT ======",
            {
                "x1": x1,
                "y1": y1,
                "beam_z": beam_z,
                "length": length,
                "height": beam_height if "beam_height" in locals() else None
            }
        )




        print(
            "====== BEAM SOLID PROFILE DEBUG ======",
            {
                "id": beam_data.get("id"),
                "z": beam_data.get("z"),
                "height": beam_height,
                "depth": beam_data.get("depth")
            }
        )


        print(
            "====== BEAM PROFILE POSITION CHECK ======",
            {
                "id": beam_data.get("id"),
                "axis_z": beam_z,
                "height": beam_height,
                "depth": beam_data.get("depth"),
                "profile_position":
                    beam_position.Location.Coordinates
                    if beam_position
                    else None
            }
        )


        solid = self.model.create_entity(

            "IfcExtrudedAreaSolid",

            SweptArea=profile,

            Position=beam_position,

            ExtrudedDirection=self.create_direction(
                0,
                0,
                1
            ),


            Depth=float(beam_height)
        )


        print(
            "====== SOLID DEBUG ======"
        )

        print(
            {
                "profile": solid.SweptArea,
                "x": solid.SweptArea.XDim,
                "y": solid.SweptArea.YDim,
                "depth": solid.Depth,
                "direction": solid.ExtrudedDirection.DirectionRatios
            }
        )

        print(
            "========================="
        )


        print(
            "\n====== BEAM SOLID POSITION DEBUG ======"
        )

        print(
            {
                "beam_id": beam_data.get("id"),
                "level": beam_data.get("level"),
                "solid_position": solid.Position,
                "position_location": solid.Position.Location.Coordinates
            }
        )

        print(
            "========================================"
        )




        shape = self.create_shape_representation(

            solid

        )


        print(

            "✅ BEAM SHAPE CREATED",

            shape

        )


        print(
            "\n====== PROVIDER BEAM OUTPUT DEBUG ======"
        )

        print({
            "input": beam_data,
            "shape": shape
        })

        print("========================================")


        print(
            "\n====== FINAL BEAM GEOMETRY LOCAL CHECK ======"
        )

        print(
            {
                "beam": beam_data.get("id"),

                "solid_position":
                    solid.Position.Location.Coordinates,

                "solid_depth":
                    solid.Depth,

                "representation":
                    shape
            }
        )

        print(
            "=============================================="
        )

        print(
            "\n====== FINAL BEAM GEOMETRY CONTRACT ======"
        )

        print(
            {
                "id": beam_data.get("id"),
                "level": beam_data.get("level"),

                "profile_x":
                    solid.SweptArea.XDim,

                "profile_y":
                    solid.SweptArea.YDim,

                "depth":
                    solid.Depth,

                "placement":
                    solid.Position.Location.Coordinates
            }
        )

        print(
            "=========================================="
        )



        return shape




    # ==================================================
    # SLAB GEOMETRY
    # ==================================================


    def create_slab_geometry(
        self,
        slab_data
    ):


        print(

            "⬛ CREATE SLAB GEOMETRY:",

            slab_data

        )


        width = float(

            slab_data.get(

                "width",

                4

            )

        )


        depth = float(

            slab_data.get(

                "depth",

                4

            )

        )


        print(
            "SLAB THICKNESS INPUT:",
            slab_data.get("thickness")
        )


        thickness = float(

            slab_data.get(

                "thickness",

                0.20

            )

        )



        profile = self.model.create_entity(

            "IfcRectangleProfileDef",

            ProfileType="AREA",

            XDim=width,

            YDim=depth

        )



        slab_position = self.get_element_position(
            slab_data
        )


        solid = self.model.create_entity(

            "IfcExtrudedAreaSolid",

            SweptArea=profile,

            Position=slab_position,

            ExtrudedDirection=self.create_direction(

                0,
                0,
                1

            ),

            Depth=thickness

        )



        return self.create_shape_representation(

            solid

        )
    # ==================================================
    # DOOR GEOMETRY
    # ==================================================


    def create_door_geometry(
        self,
        door_data
    ):


        x = float(
            door_data.get(
                "x",
                0
            )
        )


        y = float(
            door_data.get(
                "y",
                0
            )
        )


        z = float(
            door_data.get(
                "z",
                0
            )
        )


        print(

            "🚪 CREATE DOOR GEOMETRY:",

            door_data

        )


        width = float(

            door_data.get(

                "width",

                1.0

            )

        )


        height = float(

            door_data.get(

                "height",

                2.2

            )

        )


        z = float(
            door_data.get(
                "z",
                0
            )
        )


        print(

            "🚪 CREATE DOOR GEOMETRY:",

            door_data

        )


        width = float(

            door_data.get(

                "width",

                1.0

            )

        )


        height = float(

            door_data.get(

                "height",

                2.2

            )

        )


        door_position = self.create_axis_placement(
            0,
            0,
            0
        )


        thickness = 0.12



        profile = self.model.create_entity(

            "IfcRectangleProfileDef",

            ProfileType="AREA",

            XDim=width,

            YDim=thickness

        )




        solid = self.model.create_entity(

            "IfcExtrudedAreaSolid",

            SweptArea=profile,

            Position=door_position,

            ExtrudedDirection=self.create_direction(
                0,
                0,
                1
            ),

            Depth=height

        )



        shape = self.create_shape_representation(

            solid

        )


        print(

            "✅ DOOR SHAPE CREATED:",

            shape

        )


        return shape





    # ==================================================
    # WINDOW GEOMETRY
    # ==================================================


    def create_window_geometry(
        self,
        window_data
    ):


        print(

            "🪟 CREATE WINDOW GEOMETRY:",

            window_data

        )


        width = float(

            window_data.get(

                "width",

                2.0

            )

        )


        height = float(

            window_data.get(

                "height",

                1.5

            )

        )


        window_position = self.create_axis_placement(
            0,
            0,
            0
        )



        thickness = 0.10



        profile = self.model.create_entity(

            "IfcRectangleProfileDef",

            ProfileType="AREA",

            XDim=width,

            YDim=thickness

        )



        solid = self.model.create_entity(

            "IfcExtrudedAreaSolid",

            SweptArea=profile,

            Position=window_position,

            ExtrudedDirection=self.create_direction(

                0,
                0,
                1

            ),

            Depth=height

        )



        shape = self.create_shape_representation(

            solid

        )


        print(

            "✅ WINDOW SHAPE CREATED:",

            shape

        )


        return shape

    # ==================================================
    # STAIR GEOMETRY
    # ==================================================

    def create_stair_geometry(
        self,
        element
    ):

        data = element.get("data", element)
        centerline = data.get("centerline") or data.get("walking_line")
        if data.get("geometry_status") == "resolved" and centerline:
            return self.create_authoritative_path_geometry(centerline)

        polygon = element.get(
            "geometry",
            []
        )


        if len(polygon) < 2:

            return None


        x1, y1 = polygon[0]
        x2, y2 = polygon[1]


        points = [

            [x1, y1],

            [x2, y1],

            [x2, y2],

            [x1, y2]

        ]


        profile_points = [

            [x1, y1],

            [x2, y1],

            [x2, y2],

            [x1, y2]

        ]


        points = []


        for p in profile_points:

            points.append(

                self.create_point(

                    p[0],

                    p[1],

                    0

                )

            )



        points.append(points[0])



        polyline = self.model.create_entity(

            "IfcPolyline",

            Points=points

        )



        profile = self.model.create_entity(

            "IfcArbitraryClosedProfileDef",

            ProfileType="AREA",

            OuterCurve=polyline

        )


        position = self.create_axis_placement(

            0,

            0,

            0

        )


        solid = self.create_extrusion(

            profile,

            3.2,

            position

        )


        return self.create_shape_representation(

            solid

        )

    def create_stair_flight_geometry(self, flight):
        return self.create_authoritative_path_geometry(flight.get("centerline") or [])


    def create_authoritative_path_geometry(self, points):
        if not isinstance(points, list) or len(points) < 2 or self.context is None:
            return None
        ifc_points = []
        for point in points:
            if not isinstance(point, (list, tuple)) or len(point) < 2:
                return None
            z = point[2] if len(point) > 2 else 0.0
            ifc_points.append(self.create_point(point[0], point[1], z))
        curve = self.model.create_entity("IfcPolyline", Points=ifc_points)
        shape = self.model.create_entity(
            "IfcShapeRepresentation",
            ContextOfItems=self.context,
            RepresentationIdentifier="Body",
            RepresentationType="Curve3D",
            Items=[curve],
        )
        return self.model.create_entity(
            "IfcProductDefinitionShape",
            Representations=[shape],
        )


    def create_vehicle_ramp_geometry(self, data):
        return self.create_authoritative_path_geometry(
            data.get("centerline_3d") or data.get("geometry") or []
        )


    def create_driveway_geometry(self, data):
        start_z = data.get("start_z", 0.0)
        end_z = data.get("end_z", start_z)
        if start_z != end_z and data.get("centerline"):
            centerline = data.get("centerline")
            points3d = []
            for index, point in enumerate(centerline):
                ratio = index / max(len(centerline) - 1, 1)
                points3d.append([
                    point[0], point[1], start_z + (end_z - start_z) * ratio
                ])
            return self.create_authoritative_path_geometry(points3d)
        points = data.get("polygon") or data.get("centerline") or []
        if points and points[0] != points[-1] and data.get("polygon"):
            points = list(points) + [points[0]]
        z = start_z
        points3d = [
            [point[0], point[1], point[2] if len(point) > 2 else z]
            for point in points
        ]
        return self.create_authoritative_path_geometry(points3d)



    # ==================================================
    # TRANSPORT ELEMENT GEOMETRY
    # ==================================================

    def create_transport_geometry(
        self,
        element
    ):


        polygon = element.get(

            "geometry",

            []

        )


        if len(polygon) < 2:

            return None



        x1, y1 = polygon[0]

        x2, y2 = polygon[1]



        profile_points = [

            [x1,y1],

            [x2,y1],

            [x2,y2],

            [x1,y2]

        ]



        points = []


        for p in profile_points:

            points.append(

                self.create_point(

                    p[0],

                    p[1],

                    0

                )

            )



        points.append(points[0])



        polyline = self.model.create_entity(

            "IfcPolyline",

            Points=points

        )


        profile = self.model.create_entity(

            "IfcArbitraryClosedProfileDef",

            ProfileType="AREA",

            OuterCurve=polyline

        )




        position = self.create_axis_placement(

            0,

            0,

            0

        )



        solid = self.create_extrusion(

            profile,

            0.25,

            position

        )


        return self.create_shape_representation(

            solid

        )



    # ==================================================
    # VERTICAL CORE / PROXY GEOMETRY
    # ==================================================

    def create_proxy_geometry(
        self,
        element
    ):


        polygon = element.get(

            "geometry",

            []

        )


        if len(polygon) < 2:

            return None



        x1,y1 = polygon[0]

        x2,y2 = polygon[1]



        profile_points = [

            [x1,y1],

            [x2,y1],

            [x2,y2],

            [x1,y2]

        ]



        points = []


        print(
            "PROXY PROFILE POINTS:",
            profile_points
        )


        for p in profile_points:

            points.append(

                self.create_point(

                    p[0],

                    p[1],

                    0

                )

            )



        points.append(points[0])



        polyline = self.model.create_entity(

            "IfcPolyline",

            Points=points

        )



        profile = self.model.create_entity(

            "IfcArbitraryClosedProfileDef",

            ProfileType="AREA",

            OuterCurve=polyline

        )




        position = self.create_axis_placement(

            0,

            0,

            0

        )



        solid = self.create_extrusion(

            profile,

            3.2,

            position

        )


        print(
            "VERTICAL GEOMETRY LOCAL ORIGIN:",
            x1,
            y1
        )

        print(
            "VERTICAL PRODUCT PLACEMENT:",
            element.get("geometry")[0]
        )


        return self.create_shape_representation(

            solid

        )





    # ==================================================
    # GENERIC EXTRUSION
    # ==================================================


    def create_extrusion(
        self,
        profile,
        depth,
        position=None
    ):


        direction = self.create_direction(
            0,
            0,
            1
        )


        print(
            "\n====== CREATE EXTRUSION POSITION DEBUG ======"
        )

        print(
            position.Location.Coordinates
        )

        print(
            "============================================="
        )


        solid = self.model.create_entity(

            "IfcExtrudedAreaSolid",

            SweptArea=profile,

            Position=position,

            ExtrudedDirection=direction,

            Depth=float(depth)

        )


        return solid





    # ==================================================
    # SHAPE REPRESENTATION
    # ==================================================


    def create_shape_representation(
        self,
        solid
    ):


        if self.context is None:

            print(

                "⚠️ NO IFC CONTEXT"

            )

            return None



        representation = self.model.create_entity(

            "IfcShapeRepresentation",

            ContextOfItems=self.context,

            RepresentationIdentifier="Body",

            RepresentationType="SweptSolid",

            Items=[solid]

        )



        return self.model.create_entity(

            "IfcProductDefinitionShape",

            Representations=[representation]

        )
